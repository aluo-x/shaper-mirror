"""PointNet++

References:
    @article{qi2017pointnetplusplus,
      title={PointNet++: Deep Hierarchical Feature Learning on Point Sets in a Metric Space},
      author={Qi, Charles R and Yi, Li and Su, Hao and Guibas, Leonidas J},
      journal={arXiv preprint arXiv:1706.02413},
      year={2017}
    }
"""

import torch
import torch.nn as nn

from shaper.nn import MLP, SharedMLP
from shaper.models.pn2_utils import PointNetSAModule
from shaper.nn.init import set_bn
from shaper.models.loss import ClsLoss
from shaper.models.metric import Accuracy
from shaper.models.dgcnn import TNet


# class TNet(nn.Module):
#     """Transformation Network for PN2SSG"""
#
#     def __init__(self,
#                  in_channels=3,
#                  out_channels=3,
#                  num_centroids=-1,
#                  radius=0.3,
#                  num_neighbours=48,
#                  sa_channels=(64, 64, 128),
#                  local_channels=(1024,),
#                  global_channels=(512, 256),
#                  ):
#         super(TNet, self).__init__()
#
#         self.in_channels = in_channels
#         self.out_channels = out_channels
#         self.radius = radius
#
#         self.sa_module = PointNetSAModule(in_channels=in_channels - 3,
#                                           mlp_channels=sa_channels,
#                                           num_centroids=num_centroids,
#                                           radius=radius,
#                                           num_neighbours=num_neighbours,
#                                           use_xyz=True)
#
#         self.mlp_local = SharedMLP(sa_channels[-1]+3, local_channels, bn=True)
#         self.mlp_global = MLP(local_channels[-1], global_channels)
#         self.linear = nn.Linear(global_channels[-1], self.out_channels * self.out_channels, bias=True)
#
#         self.init_weights()
#
#     def forward(self, xyz, feature=None):
#         xyz, feature = self.sa_module(xyz, feature)
#         x = torch.cat([xyz, feature], dim=1)
#
#         x = self.mlp_local(x)
#         x, _ = torch.max(x, 2)
#
#         x = self.mlp_global(x)
#         x = self.linear(x)
#         x = x.view(-1, self.out_channels, self.out_channels)
#         I = torch.eye(self.out_channels, self.out_channels, device=x.device)
#         x = x.add(I)
#         return x
#
#     def init_weights(self):
#         # set linear transform be 0
#         nn.init.zeros_(self.linear.weight)
#         nn.init.zeros_(self.linear.bias)


class PointNet2SSGCls(nn.Module):
    """PointNet2 with single-scale grouping for classfication

    Structure: input -> [PointNetSA]s -> [MLP]s -> [MaxPooling] -> [MLP]s -> [Linear] -> logits

    Args:
        in_channels (int): The number of input channels
        out_channels (int): The number of semantics classes to predict over
        num_centroids (tuple of int): The numbers of centroids to sample in each set abstraction module
        radius (tuple of float): A tuple of radius to query neighbours in each set abstraction module
        num_neighbours(tuple of int): The numbers of neighbours to query for each centroid
        sa_channels (tuple of tuple of int): The numbers of channels to within each set abstraction module
        local_channels (tuple of int): The numbers of channels to extract local features after set abstraction
        global_channels (tuple of int): The numbers of channels to extract global features
        dropout_prob (float): The probability to dropout input features
        use_xyz (bool): Whether or not to use the xyz position of a point as a feature
    """

    def __init__(self,
                 in_channels,
                 out_channels,
                 num_centroids=(512, 128),
                 radius=(0.2, 0.4),
                 num_neighbours=(32, 64),
                 sa_channels=((64, 64, 128), (128, 128, 256)),
                 local_channels=(256, 512, 1024),
                 global_channels=(512, 256),
                 dropout_prob=0.5,
                 use_xyz=True,
                 with_transform=False):
        super(PointNet2SSGCls, self).__init__()

        self.in_channels = in_channels
        self.out_channels = out_channels
        self.use_xyz = use_xyz
        self.with_transform = with_transform

        # sanity check
        num_layers = len(num_centroids)
        assert len(radius) == num_layers
        assert len(num_neighbours) == num_layers
        assert len(sa_channels) == num_layers

        if self.with_transform:
            self.transform_input = TNet(3, 3, k=20)

        feature_channels = in_channels - 3
        self.sa_modules = nn.ModuleList()
        for ind in range(num_layers):
            sa_module = PointNetSAModule(in_channels=feature_channels,
                                         mlp_channels=sa_channels[ind],
                                         num_centroids=num_centroids[ind],
                                         radius=radius[ind],
                                         num_neighbours=num_neighbours[ind],
                                         use_xyz=use_xyz)
            self.sa_modules.append(sa_module)
            feature_channels = sa_channels[ind][-1]

        if use_xyz:
            feature_channels += 3
        self.mlp_local = SharedMLP(feature_channels, local_channels, bn=True)
        self.mlp_global = MLP(local_channels[-1], global_channels, dropout=dropout_prob)
        self.classifier = nn.Linear(global_channels[-1], out_channels, bias=True)

        self.init_weights()
        set_bn(self, momentum=0.01)

    def forward(self, data_batch):
        point = data_batch["points"]
        end_points = {}

        # torch.Tensor.narrow; share same memory
        xyz = point.narrow(1, 0, 3)
        if point.size(1) > 3:
            feature = point.narrow(1, 3, point.size(1) - 3)
        else:
            feature = None

        if self.with_transform:
            trans_input = self.transform_input(xyz)
            xyz = torch.bmm(trans_input, xyz)
            end_points['trans_input'] = trans_input

        for sa_module in self.sa_modules:
            xyz, feature = sa_module(xyz, feature)

        if self.use_xyz:
            x = torch.cat([xyz, feature], dim=1)
        else:
            x = feature
        x = self.mlp_local(x)
        x, max_indices = torch.max(x, 2)
        end_points['key_point_inds'] = max_indices
        x = self.mlp_global(x)

        cls_logits = self.classifier(x)

        preds = {
            'cls_logits': cls_logits
        }
        preds.update(end_points)

        return preds

    def init_weights(self):
        nn.init.xavier_uniform_(self.classifier.weight)
        nn.init.zeros_(self.classifier.bias)


def build_pointnet2ssg(cfg):
    if cfg.TASK == "classification":
        net = PointNet2SSGCls(
            in_channels=cfg.INPUT.IN_CHANNELS,
            out_channels=cfg.DATASET.NUM_CLASSES,
            num_centroids=cfg.MODEL.PN2SSG.NUM_CENTROIDS,
            radius=cfg.MODEL.PN2SSG.RADIUS,
            num_neighbours=cfg.MODEL.PN2SSG.NUM_NEIGHBOURS,
            sa_channels=cfg.MODEL.PN2SSG.SA_CHANNELS,
            local_channels=cfg.MODEL.PN2SSG.LOCAL_CHANNELS,
            global_channels=cfg.MODEL.PN2SSG.GLOBAL_CHANNELS,
            dropout_prob=cfg.MODEL.PN2SSG.DROPOUT_PROB,
            use_xyz=cfg.MODEL.PN2SSG.USE_XYZ,
            with_transform=cfg.MODEL.PN2SSG.TRANSFORM,
        )
        loss_fn = ClsLoss()
        metric_fn = Accuracy()
    else:
        raise NotImplementedError

    return net, loss_fn, metric_fn


if __name__ == '__main__':
    batch_size = 8
    in_channels = 3
    num_points = 1024
    num_classes = 40

    data = torch.rand(batch_size, in_channels, num_points)
    data = data.cuda()

    pn2ssg = PointNet2SSGCls(in_channels, num_classes,
                             num_centroids=(-1, -1), with_transform=True)
    pn2ssg.cuda()
    out_dict = pn2ssg({"points": data})
    for k, v in out_dict.items():
        print('PointNet2SSG:', k, v.shape)
