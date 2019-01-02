from shaper.config.classification import _C, CN

_C.TASK = "classification"

_C.MODEL.POINTNET.BEFORE_CHANNELS = 40
_C.MODEL.PN2SSG.BEFORE_CHANNELS = 40
_C.MODEL.PN2MSG.BEFORE_CHANNELS = 40
_C.MODEL.DGCNN.BEFORE_CHANNELS = 40
_C.MODEL.PNS2CNN.BEFORE_CHANNELS = 40

_C.DATASET.MODELNET_FEWSHOT = CN()
_C.DATASET.MODELNET_FEWSHOT.NUM_PER_CLASS = 1
_C.DATASET.MODELNET_FEWSHOT.CROSS_NUM = 0

_C.DATASET.SHAPENET_FEWSHOT = CN()
_C.DATASET.SHAPENET_FEWSHOT.NUM_PER_CLASS = 1
_C.DATASET.SHAPENET_FEWSHOT.CROSS_NUM = 0

_C.DATASET.SHAPENET55_FEWSHOT = CN()
_C.DATASET.SHAPENET55_FEWSHOT.NUM_PER_CLASS = 1
_C.DATASET.SHAPENET55_FEWSHOT.CROSS_NUM = 0

_C.TRAIN.LOAD_PRETRAIN = False
# Freeze layers other than classifier

_C.TRAIN.FREEZE_PARAMS = ()
_C.TRAIN.WARM_UP = CN()
_C.TRAIN.WARM_UP.ENABLE = False
_C.TRAIN.WARM_UP.WARM_STEP_LAMBDA = (0.01, 0.01, 0.01, 0.01, 0.01, 0.1, 0.1, 0.1, 0.1, 0.1)
_C.TRAIN.WARM_UP.GAMMA = 0.1
_C.TRAIN.WARM_UP.STEP_SIZE = 20

_C.TRAIN.MID_UNFREEZE = CN()
_C.TRAIN.MID_UNFREEZE.ENABLE = False
_C.TRAIN.MID_UNFREEZE.PATTERNS = ()
_C.TRAIN.MID_UNFREEZE.STEPS = 0
