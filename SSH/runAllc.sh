#!/bin/bash

export PATH=/home/sila/dir_NVIDIA/cuda-12.6.1/bin:/home/sila/dir_NVIDIA/cuda-12.6.1/DRIVER${PATH:+:${PATH}}
export LD_LIBRARY_PATH=/home/sila/dir_NVIDIA/cuda-12.6.1/DRIVER:/home/sila/dir_NVIDIA/cuda-12.6.1/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}

source activate phasenet
set -e
cd /home/clov/seisbench_VT/prg_python

echo "c"

#python format_csv_hdf5.py d
#python gene_noise.py

python format_csv_hdf5.py c
python fusion_data.py c
python IA_seisbench_Tuning.py 1 c


cd /home/clov/seisbench_VT/images
rm -rf seisbenchC
cd /home/clov/seisbench_VT/prg_python


python test_IA.py 1 c
python loss_curve.py 1 c
python compare_trust.py 1 c
python compare_noise.py 1 c

python detection_nouv.py c
python extraire_nouv.py c
python fusion_dataset.py c
python IA_seisbench_Tuning.py 2 c


python test_IA.py 2 c
python image_event_day.py c
python loss_curve.py 2 c
python compare_trust.py 2 c
python compare_noise.py 2 c

echo "FIN"
conda deactivate
exit
