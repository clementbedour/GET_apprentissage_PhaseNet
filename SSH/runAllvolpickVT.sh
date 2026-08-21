#!/bin/bash

export PATH=/home/sila/dir_NVIDIA/cuda-12.6.1/bin:/home/sila/dir_NVIDIA/cuda-12.6.1/DRIVER${PATH:+:${PATH}}
export LD_LIBRARY_PATH=/home/sila/dir_NVIDIA/cuda-12.6.1/DRIVER:/home/sila/dir_NVIDIA/cuda-12.6.1/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}

source activate phasenet
set -e
cd /home/clov/seisbench_VT/prg_python
echo "VOLPICK VT"


python volpick_prepare_format.py VT
python volpick_prepare_noise.py
python volpick_fusion_data.py VT
python IA_volpick_Tuning.py VT 1
python IA_volpick_Tuning.py VT 2


#python volpick_detection_nouv.py 2 VT
#python volpick_extraire_nouv.py 2 VT

cd /home/clov/seisbench_VT/images/volpick
rm -rf VT
cd /home/clov/seisbench_VT/prg_python


#python volpick_test_IA.py 2 VT
#python volpick_image_event_day.py 2 VT
#python volpick_metrics.py 2 VT
#python volpick_compare_trust.py 2 VT


echo "FIN"
conda deactivate
exit
