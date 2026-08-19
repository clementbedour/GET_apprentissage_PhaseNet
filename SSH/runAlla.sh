#!/bin/bash

export PATH=/home/sila/dir_NVIDIA/cuda-12.6.1/bin:/home/sila/dir_NVIDIA/cuda-12.6.1/DRIVER${PATH:+:${PATH}}
export LD_LIBRARY_PATH=/home/sila/dir_NVIDIA/cuda-12.6.1/DRIVER:/home/sila/dir_NVIDIA/cuda-12.6.1/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}

source activate phasenet
set -e
cd /home/clov/seisbench_VT/prg_python

echo "a"

#python format_csv_hdf5.py c
#python gene_noise.py

python format_csv_hdf5.py a
python fusion_data.py a
python IA_seisbench_Tuning.py 1 a


cd /home/clov/seisbench_VT/images
rm -rf seisbenchA
cd /home/clov/seisbench_VT/prg_python


python test_IA.py 1 a
python metrics.py 1 a
python compare_trust.py 1 a


python detection_nouv.py a
python extraire_nouv.py a
python fusion_dataset.py a
python IA_seisbench_Tuning.py 2 a		


python test_IA.py 2 a
python image_event_day.py a
python metrics.py 2 a
python compare_trust.py 2 a


echo "FIN"
conda deactivate
exit
