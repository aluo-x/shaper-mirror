import torch
import torch.nn as nn

from shaper.nn import MLP, SharedMLP
from shaper.models.pn2_utils import PointNetSAModule
from shaper.nn.init import set_bn


class PointNet2SSGFeature(nn.Module):
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
                 num_centroids=(512, 128),
                 radius=(0.2, 0.4),
                 num_neighbours=(32, 64),
                 sa_channels=((64, 64, 128), (128, 128, 256)),
                 local_channels=(256, 512, 1024),
                 global_channels=(512, 256),
                 dropout_prob=0.5,
                 use_xyz=True):
        super(PointNet2SSGFeature, self).__init__()

        self.in_channels = in_channels
        self.out_channels = global_channels[-1]
        self.use_xyz = use_xyz

        # sanity check
        num_layers = len(num_centroids)
        assert len(radius) == num_layers
        assert len(num_neighbours) == num_layers
        assert len(sa_channels) == num_layers

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

        set_bn(self, momentum=0.01)

    def forward(self, point):

        end_points = {}

        # torch.Tensor.narrow; share same memory
        xyz = point.narrow(1, 0, 3)
        if point.size(1) > 3:
            feature = point.narrow(1, 3, point.size(1) - 3)
        else:
            feature = None

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

        return x


def build_pointnet2ssg_feature(cfg):
    net = PointNet2SSGFeature(
        in_channels=cfg.INPUT.IN_CHANNELS,
        num_centroids=cfg.MODEL.PN2SSG.NUM_CENTROIDS,
        radius=cfg.MODEL.PN2SSG.RADIUS,
        num_neighbours=cfg.MODEL.PN2SSG.NUM_NEIGHBOURS,
        sa_channels=cfg.MODEL.PN2SSG.SA_CHANNELS,
        local_channels=cfg.MODEL.PN2SSG.LOCAL_CHANNELS,
        global_channels=cfg.MODEL.PN2SSG.GLOBAL_CHANNELS,
        dropout_prob=cfg.MODEL.PN2SSG.DROPOUT_PROB,
        use_xyz=cfg.MODEL.PN2SSG.USE_XYZ
    )

    return net
