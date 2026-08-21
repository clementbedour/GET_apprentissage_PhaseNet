#!/bin/bash

export PATH=/home/sila/dir_NVIDIA/cuda-12.6.1/bin:/home/sila/dir_NVIDIA/cuda-12.6.1/DRIVER${PATH:+:${PATH}}
export LD_LIBRARY_PATH=/home/sila/dir_NVIDIA/cuda-12.6.1/DRIVER:/home/sila/dir_NVIDIA/cuda-12.6.1/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}

source activate phasenet
set -e
cd /home/clov/seisbench_VT/prg_python

echo "image"

python test_IA.py 1 b 
python test_IA.py 2 b
python test_IA.py 1 a
python test_IA.py 2 a

#python volpick_test_IA.py 1 VT
#python volpick_test_IA.py 2 VT

#python volpick_metrics.py 1 VT
#python volpick_metrics.py 2 VT

#python volpick_compare_trust.py 1 VT
#python volpick_compare_trust.py 2 VT

#echo ""
#echo ""
#echo ""
#echo "image LPVT"
#python volpick_test_IA.py 1 LPVT
#python volpick_test_IA.py 2 LPVT

#python volpick_metrics.py 1 LPVT
#python volpick_metrics.py 2 LPVT

#python volpick_compare_trust.py 1 LPVT
#python volpick_compare_trust.py 2 LPVT


echo "FIN"
conda deactivate
exit
