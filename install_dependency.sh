#!/usr/bin/env bash
conda create -n shaper python=3.6
conda activate shaper
conda install pytorch torchvision cuda92 -c pytorch h5py cupy
pip install cython yacs h5py
pip install matplotlib opencv-python
# 3D visualization
pip install open3d-python
# s2cnn
pip install requests scipy pynvrtc