"""Helpers for operating weights/params"""
import re

import torch.nn as nn


def freeze_bn(module, bn_eval, bn_frozen):
    """Freeze Batch Normalization in Module

    Args:
        module (nn.Module)
        bn_eval (bool): whether to using global stats
        bn_frozen (bool): whether to freeze bn params

    """
    for module_name, m in module.named_modules():
        if isinstance(m, nn.BatchNorm2d):
            if bn_eval:
                # Notice the difference between the behaviors of
                # BatchNorm.eval() and BatchNorm(track_running_stats=False)
                m.eval()
                # print('BN: %s in eval mode.' % module_name)
            if bn_frozen:
                for param_name, params in m.named_parameters():
                    params.requires_grad = False
                    # print('BN: %s is frozen.' % (module_name + '.' + param_name))


def freeze_params(module, frozen_params):
    """Freeze params and/or convert them into eval mode

    Args:
        module (torch.nn.Module):
        frozen_params (sequence of str): strings which define all the patterns of interests

    """
    for name, params in module.named_parameters():
        for pattern in frozen_params:
            assert isinstance(pattern, str)
            if re.search(pattern, name):
                params.requires_grad = False
                # print('Params %s is frozen.' % name)


def freeze_modules(module, frozen_modules, prefix=''):
    """Set module's eval mode and freeze its params

    Args:
        module (torch.nn.Module):
        frozen_modules (list[str]):
        prefix (str, optional)

    """
    for name, m in module._modules.items():
        for pattern in frozen_modules:
            assert isinstance(pattern, str)
            full_name = prefix + ('.' if prefix else '') + name
            if re.search(pattern, full_name):
                m.eval()
                freeze_all_params(m)
                # print('Module %s is frozen.' % full_name)
            else:
                freeze_modules(m, frozen_modules, prefix=full_name)


def freeze_by_patterns(module, patterns):
    """Freeze by matching patterns"""
    frozen_params = []
    frozen_modules = []
    for pattern in patterns:
        if pattern.startswith('module:'):
            frozen_modules.append(pattern[7:])
        else:
            frozen_params.append(pattern)
    freeze_params(module, frozen_params)
    freeze_modules(module, frozen_modules)


def freeze_all_params(module):
    """Freeze all params in a module"""
    for name, params in module.named_parameters():
        params.requires_grad = False


def unfreeze_params(module, frozen_params):
    """Unfreeze params and/or convert them into eval mode

    Args:
        module (torch.nn.Module):
        frozen_params: a list/tuple of strings,
            which define all the patterns of interests

    """
    for name, params in module.named_parameters():
        for pattern in frozen_params:
            assert isinstance(pattern, str)
            if re.search(pattern, name):
                params.requires_grad = True
                # print('Params %s is unfrozen.' % name)


def unfreeze_modules(module, frozen_modules, prefix=''):
    """Set module's eval mode and freeze its params

    Args:
        module (torch.nn.Module):
        frozen_modules (list[str]):
        prefix (str, optional):

    """
    for name, m in module._modules.items():
        for pattern in frozen_modules:
            assert isinstance(pattern, str)
            full_name = prefix + ('.' if prefix else '') + name
            if re.search(pattern, full_name):
                m.train()
                unfreeze_all_params(m)
                # print('Module %s is unfrozen.' % full_name)
            else:
                unfreeze_modules(m, frozen_modules, prefix=full_name)


def unfreeze_by_patterns(module, patterns):
    """Unfreeze Module by matching patterns"""
    frozen_params = []
    frozen_modules = []
    for pattern in patterns:
        if pattern.startswith('module:'):
            frozen_modules.append(pattern[7:])
        else:
            frozen_params.append(pattern)
    unfreeze_params(module, frozen_params)
    unfreeze_modules(module, frozen_modules)


def unfreeze_all_params(module):
    """Freeze all params in a module"""
    for name, params in module.named_parameters():
        params.requires_grad = True
        # print('Params %s is unfrozen.' % name)


def check_frozen_modules(module, logger=None):
    """Check which modules are frozen.

    Args:
        module (torch.nn.Module):
        logger (optional):

    """
    for name, m in module.named_modules():
        if not m.training:
            log_str = "Module {} is frozen.".format(name)
            if logger:
                logger.info(log_str)
            else:
                print(log_str)


def check_frozen_params(module, logger=None):
    """Check which params are frozen.

    Args:
        module (torch.nn.Module):
        logger (optional):

    """
    for name, params in module.named_parameters():
        if not params.requires_grad:
            log_str = "Param {} is frozen.".format(name)
            if logger:
                logger.info(log_str)
            else:
                print(log_str)