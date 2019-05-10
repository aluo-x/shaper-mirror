# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved.
# Modified by Jiayuan Gu
import logging
import os

import torch


class Checkpointer(object):
    def __init__(
        self,
        model,
        optimizer=None,
        scheduler=None,
        save_dir="",
        logger=None,
    ):
        self.model = model
        self.optimizer = optimizer
        self.scheduler = scheduler
        self.save_dir = save_dir
        if logger is None:
            logger = logging.getLogger(__name__)
        self.logger = logger

    def save(self, name, tag_file='last_checkpoint', **kwargs):
        if not self.save_dir:
            return

        data = {}
        data["model"] = self.model.state_dict()
        if self.optimizer is not None:
            data["optimizer"] = self.optimizer.state_dict()
        if self.scheduler is not None:
            data["scheduler"] = self.scheduler.state_dict()
        data.update(kwargs)

        save_file = os.path.join(self.save_dir, "{}.pth".format(name))
        self.logger.info("Saving checkpoint to {}".format(os.path.abspath(save_file)))
        torch.save(data, save_file)
        self.tag_last_checkpoint(save_file, tag_file)

    def load(self, f=None, resume=True, tag_file='last_checkpoint'):
        if resume and self.has_checkpoint(tag_file):
            # override argument with existing checkpoint
            f = self.get_checkpoint_file(tag_file)
        if not f:
            # no checkpoint could be found
            self.logger.info("No checkpoint found. Initializing model from scratch")
            return {}
        self.logger.info("Loading checkpoint from {}".format(f))
        checkpoint = self._load_file(f)
        self.model.load_state_dict(checkpoint.pop("model"))
        if "optimizer" in checkpoint and self.optimizer:
            self.logger.info("Loading optimizer from {}".format(f))
            self.optimizer.load_state_dict(checkpoint.pop("optimizer"))
        if "scheduler" in checkpoint and self.scheduler:
            self.logger.info("Loading scheduler from {}".format(f))
            self.scheduler.load_state_dict(checkpoint.pop("scheduler"))

        # return any further checkpoint data
        return checkpoint

    def has_checkpoint(self, tag_file='last_checkpoint'):
        save_file = os.path.join(self.save_dir, tag_file)
        return os.path.exists(save_file)

    def get_checkpoint_file(self, tag_file='last_checkpoint'):
        save_file = os.path.join(self.save_dir, tag_file)
        try:
            with open(save_file, "r") as f:
                last_saved = f.read().strip()
            # If not absolute path, add save_dir as prefix
            if not os.path.isabs(last_saved):
                last_saved = os.path.join(self.save_dir, last_saved)
        except IOError:
            # if file doesn't exist, maybe because it has just been
            # deleted by a separate process
            last_saved = ""
        return last_saved

    def tag_last_checkpoint(self, last_filename, tag_file='last_checkpoint'):
        save_file = os.path.join(self.save_dir, tag_file)
        # If not absolute path, only save basename
        if not os.path.isabs(last_filename):
            last_filename = os.path.basename(last_filename)
        with open(save_file, "w") as f:
            f.write(last_filename)

    def _load_file(self, f):
        return torch.load(f, map_location=torch.device("cpu"))
