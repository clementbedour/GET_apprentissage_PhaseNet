#!/bin/bash
set -e

MDP="AZERTY" #sinon 123456

echo "Transfert des fichiers vers le serveur"

#fichier pour IA base personnelle
script -q -c "sshpass -p '$MDP' scp ../prg_python/format_csv_hdf5.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
script -q -c "sshpass -p '$MDP' scp ../prg_python/gene_noise.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
script -q -c "sshpass -p '$MDP' scp ../prg_python/fusion_data.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
script -q -c "sshpass -p '$MDP' scp ../prg_python/IA_seisbench_Tuning.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
script -q -c "sshpass -p '$MDP' scp ../prg_python/detection_nouv.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
script -q -c "sshpass -p '$MDP' scp ../prg_python/extraire_nouv.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
script -q -c "sshpass -p '$MDP' scp ../prg_python/fusion_dataset.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null

#fichier image IA classique
script -q -c "sshpass -p '$MDP' scp ../prg_python/test_IA.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
script -q -c "sshpass -p '$MDP' scp ../prg_python/image_event_day.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
script -q -c "sshpass -p '$MDP' scp ../prg_python/metrics.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
script -q -c "sshpass -p '$MDP' scp ../prg_python/compare_trust.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null

#fichier pour IA base VCSEIS
#script -q -c "sshpass -p '$MDP' scp ../prg_python/volpick_prepare_format.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
#script -q -c "sshpass -p '$MDP' scp ../prg_python/volpick_prepare_noise.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
#script -q -c "sshpass -p '$MDP' scp ../prg_python/volpick_fusion_dataset.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
#script -q -c "sshpass -p '$MDP' scp ../prg_python/IA_volpick_Tuning.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
#script -q -c "sshpass -p '$MDP' scp ../prg_python/volpick_detection_nouv.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
#script -q -c "sshpass -p '$MDP' scp ../prg_python/volpick_extraire_nouv.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null

#fichier image IA volpick
#script -q -c "sshpass -p '$MDP' scp ../prg_python/volpick_test_IA.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
#script -q -c "sshpass -p '$MDP' scp ../prg_python/volpick_image_event_day.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
#script -q -c "sshpass -p '$MDP' scp ../prg_python/volpick_metrics.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null
#script -q -c "sshpass -p '$MDP' scp ../prg_python/volpick_compare_trust.py clov@nuwa.aero.obs-mip.fr:/home/clov/seisbench_VT/prg_python" /dev/null

echo "FIN"
