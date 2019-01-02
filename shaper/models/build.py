"""
Build models

Notes:
    When a new model is implemented, please provide a builder to build the model with config,
    and register it in _MODEL_BUILDERS

    How to implement a model:
    1. Modularize the model
    2. Try to add in_channels, out_channels to all the modules' attributes
    3. For the complete model, like PointNetCls, output a non-nested dictionary instead of single tensor or tuples
    4. Implement loss module whose inputs are preds and labels. Both of inputs are dict.
    5. Implement metric module (or use a general module in 'metric.py')

"""

from .pointnet import build_pointnet
from .dgcnn import build_dgcnn
from .pn2_ssg import build_pointnet2ssg
from .pn2_msg import build_pointnet2msg
from .pn2_s2cnn import build_pns2cnn
from .s2cnn import build_s2cnn

_MODEL_BUILDERS = {
    "POINTNET": build_pointnet,
    "DGCNN": build_dgcnn,
    "PN2SSG": build_pointnet2ssg,
    "PN2MSG": build_pointnet2msg,
    "PNS2CNN": build_pns2cnn,
    "S2CNN": build_s2cnn,
}


def build_model(cfg):
    return _MODEL_BUILDERS[cfg.MODEL.TYPE](cfg)


def register_model_builder(name, builder):
    if name in _MODEL_BUILDERS:
        raise KeyError(
            "Duplicate keys for {:s} with {} and {}."
            "Solve key conflicts first!".format(name, _MODEL_BUILDERS[name], builder))
    _MODEL_BUILDERS[name] = builder
