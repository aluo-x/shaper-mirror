#!/usr/bin/env bash
CFG="configs/baselines/pointnet2msg_part_seg.yaml"

for i in 1 2 3
do
   CUDA_VISIBLE_DEVICES=0,1 python tools/train_net.py --cfg=$CFG OUTPUT_DIR "@_$i"
   CUDA_VISIBLE_DEVICES=0 python tools/test_net.py --cfg=$CFG OUTPUT_DIR "@_$i" \
    INPUT.NUM_POINTS 2048
done
