import os.path as osp
from collections import OrderedDict

import numpy as np
import h5py
import json

from torch.utils.data import Dataset
from shaper.data.datasets.utils import crop_or_pad_points


class ShapeNet(Dataset):
    """ShapeNetCore dataset

    Each class of ShapeNetCore is assigned a catid/offset, like "02691156".
    Each part is associated with one class.

    Args:
        root_dir (str): the root directory of data.
        dataset_names (list of str): the names of dataset, e.g. ["train", "test"]
        transform: methods to transform inputs.
        num_points (int): the number of input points. -1 means using all.
        shuffle_points (bool): whether to shuffle input points.
        load_seg (bool): whether to load segmentation labels

    Attributes:
        classes (list): the names of classes
        meta_data (list of dict): meta information of data

    """
    URL = "https://shapenet.cs.stanford.edu/ericyi/shapenetcore_partanno_segmentation_benchmark_v0.zip"
    ROOT_DIR = "../../../data/shapenet"
    cat_file = "synsetoffset2category.txt"
    split_dir = "train_test_split"
    dataset_map = {
        "train": "shuffled_train_file_list.json",
        "val": "shuffled_val_file_list.json",
        "test": "shuffled_test_file_list.json",
    }

    def __init__(self, root_dir, dataset_names, transform=None,
                 num_points=-1, shuffle_points=False,
                 load_seg=False):
        self.root_dir = root_dir
        self.datasets_names = dataset_names
        self.num_points = num_points
        self.shuffle_points = shuffle_points
        self.transform = transform
        self.load_seg = load_seg

        # classes
        self.class_to_offset_map = self._load_cat_file()
        self.offset_to_class_map = {v: k for k, v in self.class_to_offset_map.items()}
        self.classes = list(self.class_to_offset_map.keys())
        self.classes_to_ind_map = {c: i for i, c in enumerate(self.classes)}

        # meta data
        self.meta_data = []
        for dataset_name in dataset_names:
            meta_data = self._load_dataset(dataset_name)
            self.meta_data.extend(meta_data)
        print("{} classes with {} models".format(len(self.classes), len(self.meta_data)))

    def _load_cat_file(self):
        class_to_offset_map = OrderedDict()
        with open(osp.join(self.root_dir, self.cat_file), 'r') as fid:
            for line in fid:
                class_name, class_dir = line.strip().split()
                class_to_offset_map[class_name] = class_dir
        return class_to_offset_map

    def _load_pts(self, fname):
        return np.loadtxt(fname).astype(np.float32)

    def _load_seg(self, fname):
        return np.loadtxt(fname).astype(int)

    def _load_dataset(self, dataset_name):
        split_fname = osp.join(self.root_dir, self.split_dir, self.dataset_map[dataset_name])
        fname_list = json.load(open(split_fname, 'r'))
        meta_data = []
        for fname in fname_list:
            # fname = fname.replace("shape_data", self.root_dir)
            _, offset, token = fname.split("/")
            pts_path = osp.join(self.root_dir, offset, "points", token + '.pts')
            class_name = self.offset_to_class_map[offset]
            data = {
                "token": token,
                "class": class_name,
                "pts_path": pts_path,
            }
            if self.load_seg:
                seg_path = osp.join(self.root_dir, offset, "points_label", token + '.seg')
                data["seg_path"] = seg_path
            meta_data.append(data)
        return meta_data

    def __getitem__(self, index):
        meta_data = self.meta_data[index]
        class_name = meta_data["class"]
        cls_label = self.classes_to_ind_map[class_name]
        points = self._load_pts(meta_data["pts_path"])
        seg_label = None

        points, choice = crop_or_pad_points(points, self.num_points, self.shuffle_points)
        if self.load_seg:
            seg_label = self._load_seg(meta_data["seg_path"])
            seg_label = seg_label[choice]

        if self.transform is not None:
            points = self.transform(points)

        out_dict = {
            "points": points,
            "cls_label": cls_label
        }

        if self.load_seg:
            # TODO: change to normal dataset or add category offset
            out_dict["seg_label"] = seg_label

        return out_dict

    def __len__(self):
        return len(self.meta_data)


class ShapeNetH5(Dataset):
    """ShapeNetCore HDF5 dataset

    Each class of ShapeNetCore is assigned a catid/offset, like "02691156".
    Each part is associated with one class.
    HDF5 data has already converted catid_partid to a global seg_id.

    Args:
        root_dir (str): the root directory of data.
        dataset_names (list of str): the names of dataset, e.g. ["train", "test"]
        transform: methods to transform inputs.
        num_points (int): the number of input points. -1 means using all.
        shuffle_points (bool): whether to shuffle input points.
        load_seg (bool): whether to load segmentation labels

    Attributes:
        classes (list): the names of classes
        meta_data (list of dict): meta information of data
        data_x (list): data of certain types

    TODO:
        Add the description of how points are sampled from raw data.
        Support tranforms related to seg_labels

    """
    URL = ""
    ROOT_DIR = "../../../data/shapenet_hdf5"
    cat_file = "all_object_categories.txt"
    seg_file = "overallid_to_catid_partid.json"
    dataset_map = {
        "train": "train_hdf5_file_list.txt",
        "val": "val_hdf5_file_list.txt",
        "test": "test_hdf5_file_list.txt",
    }

    def __init__(self, root_dir, dataset_names, transform=None,
                 num_points=-1, shuffle_points=False,
                 load_seg=False):
        self.root_dir = root_dir
        self.num_points = num_points
        self.shuffle_points = shuffle_points
        self.transform = transform
        self.load_seg = load_seg

        # classes
        self.class_to_catid_map = self._load_cat_file()
        self.offset_to_class_map = {v: k for k, v in self.class_to_catid_map.items()}
        self.classes = list(self.class_to_catid_map.keys())
        self.classes_to_ind_map = {c: i for i, c in enumerate(self.classes)}

        # segid to (catid, partid). Notice that partid start from 1
        if self.load_seg:
            self.segid_map = self._load_seg_file()

        # meta data and cache
        self.meta_data = []
        self.cache_points = []
        self.cache_cls_label = []
        if self.load_seg:
            self.cache_seg_label = []

        for dataset_name in dataset_names:
            self._load_dataset(dataset_name)

        self.cache_points = np.concatenate(self.cache_points, axis=0)
        self.cache_cls_label = np.concatenate(self.cache_cls_label, axis=0).astype(int)
        if self.load_seg:
            self.cache_seg_label = np.concatenate(self.cache_seg_label, axis=0).astype(int)

    def _load_cat_file(self):
        class_to_catid_map = OrderedDict()
        with open(osp.join(self.root_dir, self.cat_file), 'r') as fid:
            for line in fid:
                class_name, offset = line.strip().split()
                class_to_catid_map[class_name] = offset
        return class_to_catid_map

    def _load_seg_file(self):
        return json.load(open(osp.join(self.root_dir, self.seg_file), 'r'))

    def _load_dataset(self, dataset_name):
        split_fname = osp.join(self.root_dir, self.dataset_map[dataset_name])
        fname_list = [line.rstrip() for line in open(split_fname, 'r')]

        for fname in fname_list:
            data_path = osp.join(self.root_dir, osp.basename(fname))
            with h5py.File(data_path) as f:
                num_samples = f['label'].shape[0]
                self.cache_points.append(f['data'][:])
                self.cache_cls_label.append(f['label'][:].squeeze(1))
                if self.load_seg:
                    self.cache_seg_label.append(f['pid'][:])
            for ind in range(num_samples):
                self.meta_data.append({
                    "offset": ind,
                    "size": num_samples,
                    "path": data_path,
                })

    def __getitem__(self, index):
        points = self.cache_points[index]
        cls_label = self.cache_cls_label[index]
        seg_label = None

        points, choice = crop_or_pad_points(points, self.num_points, self.shuffle_points)
        if self.load_seg:
            seg_label = self.cache_seg_label[index][choice]

        if self.transform is not None:
            points = self.transform(points)

        out_dict = {
            "points": points,
            "cls_label": cls_label
        }

        if self.load_seg:
            out_dict["seg_label"] = seg_label

        return out_dict

    def __len__(self):
        return len(self.meta_data)


if __name__ == "__main__":
    # shapenet = ShapeNet(ShapeNet.ROOT_DIR, ["test"], load_seg=True)
    shapenet = ShapeNetH5(ShapeNetH5.ROOT_DIR, ["test"], load_seg=True)
    print("The number of samples:", shapenet.__len__())
    data = shapenet[0]
    points = data["points"]
    cls_label = data["cls_label"]
    seg_label = data["seg_label"]
    print(points.shape, points.dtype)
    print(cls_label, shapenet.classes[cls_label])
    print(seg_label.shape, seg_label.dtype)

    from shaper.utils.open3d_visualize import Visualizer

    # Visualizer.visualize_points(points)
    # part_label = seg_label
    part_label = np.asarray([shapenet.segid_map[label][1] for label in seg_label])
    Visualizer.visualize_points_with_labels(points, labels=part_label)
