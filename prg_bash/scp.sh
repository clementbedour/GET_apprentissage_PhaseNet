#!/bin/bash
set -e

<<<<<<< HEAD
MDP="AZERTY" #sinon 123456
=======
MDP="AZERTY" #essaye 123456 sinon
>>>>>>> 5f77d33 (Ajout initial de scp.sh)

echo "Transfert des fichiers vers le serveur"

script -q -c "sshpass -p '$MDP' scp ../prg_python/format_csv_hdf5.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
script -q -c "sshpass -p '$MDP' scp ../prg_python/gene_noise.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
script -q -c "sshpass -p '$MDP' scp ../prg_python/fusion_data.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
script -q -c "sshpass -p '$MDP' scp ../prg_python/IA_seisbench_Tuning.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
script -q -c "sshpass -p '$MDP' scp ../prg_python/detection_nouv.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
script -q -c "sshpass -p '$MDP' scp ../prg_python/extraire_nouv.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
script -q -c "sshpass -p '$MDP' scp ../prg_python/fusion_dataset.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null

echo "FIN"
