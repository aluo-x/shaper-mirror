"""DGCNN

References:
    @article{dgcnn,
      title={Dynamic Graph CNN for Learning on Point Clouds},
      author={Yue Wang, Yongbin Sun, Ziwei Liu, Sanjay E. Sarma, Michael M. Bronstein, Justin M. Solomon},
      journal={arXiv preprint arXiv:1801.07829},
      year={2018}
    }
"""

import torch
import torch.nn as nn

from shaper.nn import MLP, SharedMLP, Conv1d, Conv2d
from shaper.models.dgcnn.functions import get_edge_feature
from shaper.models.dgcnn.modules import EdgeConvBlockV2
from shaper.nn.init import xavier_uniform, set_bn


class TNet(nn.Module):
    """Transformation Network for DGCNN

    Structure: input -> [EdgeFeature] -> [EdgeConv]s -> [EdgePool] -> features -> [MLP] -> local features
    -> [MaxPool] -> global features -> [MLP] -> [Linear] -> logits

    Args:
        conv_channels (tuple of int): the numbers of channels of edge convolution layers
        k: the number of neareast neighbours for edge feature extractor

    """

    def __init__(self,
                 in_channels=3,
                 out_channels=3,
                 conv_channels=(64, 128),
                 local_channels=(1024,),
                 global_channels=(512, 256),
                 k=20):
        super(TNet, self).__init__()

        self.in_channels = in_channels
        self.out_channels = out_channels
        self.k = k

        self.edge_conv = SharedMLP(2 * in_channels, conv_channels, ndim=2)
        self.mlp_local = SharedMLP(conv_channels[-1], local_channels)
        self.mlp_global = MLP(local_channels[-1], global_channels)
        self.linear = nn.Linear(global_channels[-1], self.in_channels * out_channels, bias=True)

        self.init_weights()

    def forward(self, x):
        """TNet forward

        Args:
            x (torch.Tensor): (batch_size, in_channels, num_points)

        Returns:
            torch.Tensor: (batch_size, out_channels, in_channels)

        """
        x = get_edge_feature(x, self.k)  # (batch_size, 2 * in_channels, num_points, k)
        x = self.edge_conv(x)
        x, _ = torch.max(x, 3)  # (batch_size, edge_channels[-1], num_points)
        x = self.mlp_local(x)
        x, _ = torch.max(x, 2)  # (batch_size, local_channels[-1], num_points)
        x = self.mlp_global(x)
        x = self.linear(x)
        x = x.view(-1, self.out_channels, self.in_channels)
        I = torch.eye(self.out_channels, self.in_channels, device=x.device)
        x = x.add(I)  # broadcast first dimension
        return x

    def init_weights(self):
        self.edge_conv.init_weights(xavier_uniform)
        self.mlp_local.init_weights(xavier_uniform)
        self.mlp_global.init_weights(xavier_uniform)
        # Set linear transform be 0
        nn.init.zeros_(self.linear.weight)
        nn.init.zeros_(self.linear.bias)


# -----------------------------------------------------------------------------
# DGCNN for classification
# -----------------------------------------------------------------------------

class DGCNNCls(nn.Module):
    """DGCNN for classification

       Structure: input (-> [TNet] -> transform_input) -> [EdgeConvBlock]s -> [Concat EdgeConvBlock features]
       -> [MLP] -> intermediate features -> [MaxPool] -> gloal features -> [MLP] -> [Linear] -> logits

       [EdgeConvBlock]: in_features -> [EdgeFeature] -> [EdgeConv] -> [EdgePool] -> out_features

       Args:
           edge_conv_channels (tuple of int): the numbers of channels of edge convolution layers
           inter_channels (int): the number of channels of intermediate features before MaxPool
           k (int): the number of neareast neighbours for edge feature extractor

    """

    def __init__(self,
                 in_channels,
                 out_channels,
                 edge_conv_channels=(64, 64, 64, 128),
                 inter_channels=1024,
                 global_channels=(512, 256),
                 k=20,
                 dropout_prob=0.5,
                 with_transform=True):
        super(DGCNNCls, self).__init__()

        self.in_channels = in_channels
        self.out_channels = out_channels
        self.k = k
        self.with_transform = with_transform

        # input transform
        if self.with_transform:
            self.transform_input = TNet(in_channels, in_channels, k=k)

        self.mlp_edge_conv = nn.ModuleList()
        for out_channels in edge_conv_channels:
            # self.mlp_edge_conv.append(Conv2d(2 * in_channels, out_channels, 1))
            self.mlp_edge_conv.append(EdgeConvBlockV2(in_channels, out_channels, k))
            in_channels = out_channels
        self.mlp_local = Conv1d(sum(edge_conv_channels), inter_channels, 1)
        self.mlp_global = MLP(inter_channels, global_channels, dropout=dropout_prob)
        self.classifier = nn.Linear(global_channels[-1], self.out_channels, bias=True)

        self.init_weights()

    def forward(self, data_batch):
        end_points = {}
        x = data_batch["points"]
        # input transform
        if self.with_transform:
            trans_input = self.transform_input(x)
            x = torch.bmm(trans_input, x)
            end_points['trans_input'] = trans_input

        # EdgeConvMLP
        features = []
        for edge_conv in self.mlp_edge_conv:
            # x = get_edge_feature(x, self.k)
            x = edge_conv(x)
            # x, _ = torch.max(x, 3)
            features.append(x)

        x = torch.cat(features, dim=1)

        x = self.mlp_local(x)
        x, max_indices = torch.max(x, 2)
        end_points['key_point_inds'] = max_indices
        x = self.mlp_global(x)
        x = self.classifier(x)
        preds = {
            'cls_logit': x
        }
        preds.update(end_points)

        return preds

    def init_weights(self):
        for edge_conv in self.mlp_edge_conv:
            edge_conv.init_weights(xavier_uniform)
        self.mlp_local.init_weights(xavier_uniform)
        self.mlp_global.init_weights(xavier_uniform)
        xavier_uniform(self.classifier)
        set_bn(self, momentum=0.01)


if __name__ == "__main__":
    batch_size = 4
    in_channels = 3
    num_points = 1024
    num_classes = 40

    points = torch.rand(batch_size, in_channels, num_points).cuda()
    transform = TNet().cuda()
    out = transform(points)
    print('TNet: ', out.size())

    dgcnn = DGCNNCls(in_channels, num_classes, with_transform=False).cuda()
    out_dict = dgcnn({"points": points})
    for k, v in out_dict.items():
        print('DGCNN:', k, v.shape)
