#!/bin/bash

export PATH=/home/sila/dir_NVIDIA/cuda-12.6.1/bin:/home/sila/dir_NVIDIA/cuda-12.6.1/DRIVER${PATH:+:${PATH}}
export LD_LIBRARY_PATH=/home/sila/dir_NVIDIA/cuda-12.6.1/DRIVER:/home/sila/dir_NVIDIA/cuda-12.6.1/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}

source activate phasenet
set -e
cd /home/clov/seisbench_VT/prg_python

echo "b"

#python format_csv_hdf5.py d
#python gene_noise.py

#python format_csv_hdf5.py b
#python fusion_data.py b
#python IA_seisbench_Tuning.py 1 b


#cd /home/clov/seisbench_VT/images
#rm -rf seisbenchB
#cd /home/clov/seisbench_VT/prg_python


#python test_IA.py 1 b
#python loss_curve.py 1 b
#python compare_trust.py 1 b
#python compare_noise.py 1 b


#python detection_nouv.py b
#python extraire_nouv.py b



python association_pyocto.py b
python fusion_dataset.py b
python IA_seisbench_Tuning.py 2 b		


python test_IA.py 2 b
python image_event_day.py b
python image_event_day.py pyocto
python loss_curve.py 2 b
python compare_trust.py 2 b
python compare_noise.py 2 b

echo "FIN"
conda deactivate
exit
