#!/bin/bash

source ~/.bashrc


export PATH=/home/sila/dir_NVIDIA/cuda-12.6.1/bin:/home/sila/dir_NVIDIA/cuda-12.6.1/DRIVER${PATH:+:${PATH}}
export LD_LIBRARY_PATH=/home/sila/dir_NVIDIA/cuda-12.6.1/DRIVER:/home/sila/dir_NVIDIA/cuda-12.6.1/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}

conda activate phasenet

cd /home/clov/seisbench_VT/prg_python

python format_csv_hdf5.py
echo "fin format_csv_hdf5.py"

python gene_noise.py
echo "fin gene_noise.py"

python fusion_data.py
echo "fin fusion_data.py"

python IA_seisbench_Tuning.py 1
echo "fin IA 1"

python detection_nouv.py
echo "fin detection_nouv.py"

python extraire_nouv.py
echo "fin extraire_nouv.py"

python fusion_dataset.py
echo "fin fusion_dataset.py"

python IA_seisbench_Tuning.py 2
echo "fin IA 2"
echo "FIN"

conda deactivate
exit
