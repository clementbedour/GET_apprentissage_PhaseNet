import os
import numpy as np
import random

os.environ["SEISBENCH_CACHE_ROOT"] = "/get/ggs/clov/volpick"

import seisbench
import seisbench.data as sbd

#------------PARAMETRES--------------------
BASE_DIR = "../data/volpick"
OUTPUT_DIR = os.path.join(BASE_DIR, "volpick_format_noise")

os.makedirs(OUTPUT_DIR, exist_ok=True)
path_csv = os.path.join(OUTPUT_DIR, "metadata.csv")
path_hdf5 = os.path.join(OUTPUT_DIR, "waveforms.hdf5")

# Pointeur vers dossier local pour pas download
seisbench.cache_root = "/get/ggs/clov/volpick"

print("Chargement de la base locale Volpick")
dataset = sbd.VCSEIS()

# extraction bruit
noise_dataset = dataset.get_noise_traces() # merci vcseis pour les travaux

print(f"  -> {len(noise_dataset)} traces de bruit trouvées.")
print(f"Début de l'extraction vers {OUTPUT_DIR}.")

noise_extracted = 0

with sbd.WaveformDataWriter(path_csv, path_hdf5) as writer:
    
    writer.data_format = {
        "dimension_order": "CW",
        "measurement": "velocity",
        "unit": "counts",
    }

    for i in range(len(noise_dataset)):
        meta_dict = noise_dataset.metadata.iloc[i].to_dict()
        meta_dict.pop("level_0", None)
        
        # Pour le bruit pur, on s'assure que les échantillons P et S sont NaN
        meta_dict["trace_p_arrival_sample"] = np.nan
        meta_dict["trace_s_arrival_sample"] = np.nan
        
        # Séparation aléatoire
        rand = random.random()
        if rand < 0.8: 
            split = "train"
        elif rand < 0.9: 
            split = "dev"
        else: 
            split = "test"
            
        meta_dict["split"] = split
        
        waveform = noise_dataset.get_waveforms(i)
        writer.add_trace(meta_dict, waveform)
        noise_extracted += 1

print("\nExtraction du bruit terminée avec succès !!!")
print(f"     Détail des ajouts : {noise_extracted} traces de bruit pur enregistrées dans {OUTPUT_DIR}")