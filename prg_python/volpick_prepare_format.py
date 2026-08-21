import os
import sys
import numpy as np
import random
import seisbench
import seisbench.data as sbd

os.environ["SEISBENCH_CACHE_ROOT"] = "/get/ggs/clov/volpick"

#------------PARAMETRES--------------------
BASE_DIR = "../data/volpick"
seisbench.cache_root = "/get/ggs/clov/volpick"

if len(sys.argv) > 1:
    arg = sys.argv[1].upper
    if arg == "LPVT":
        OUTPUT_DIR = os.path.join(BASE_DIR, "volpick_format_LPVT")
        print("Extraction des events VT et LP")
    elif arg == "VT":
        OUTPUT_DIR = os.path.join(BASE_DIR, "volpick_format_VT")
        print("Extraction des events VT")
    else:
        print("Usage: python volpick_prepare_format.py (LPVT ou VT)")
        sys.exit(1)
else:
    print("Usage: python volpick_prepare_format.py (LPVT ou VT)")
    sys.exit(1)

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("Chargement de la base locale")
dataset = sbd.VCSEIS()

# VT
print("Extraction VT...")
vt_dataset = dataset.get_regular_earthquakes()
print(f"  -> {len(vt_dataset)} traces VT trouvées.")

# LP
print("Extraction LP...")
lp_dataset = dataset.get_long_period_earthquakes()
print(f"  -> {len(lp_dataset)} traces LP trouvées.")

path_csv = os.path.join(OUTPUT_DIR, "metadata.csv")
path_hdf5 = os.path.join(OUTPUT_DIR, "waveforms.hdf5")

total_traces = 0

with sbd.WaveformDataWriter(path_csv, path_hdf5) as writer:

    writer.data_format = {
        "dimension_order": "CW",
        "measurement": "velocity",
        "unit": "counts",
    }

    # Création d'une fonction pour éviter de dupliquer la boucle d'écriture
    def process_dataset(sub_dataset, is_noise=False):
        global total_traces
        for i in range(len(sub_dataset)):
            meta_dict = sub_dataset.metadata.iloc[i].to_dict()
            meta_dict.pop("level_0", None)

            waveform = sub_dataset.get_waveforms(i)

            # Si argument = 2 : on transforme LP en noise
            if is_noise:
                for col in list(meta_dict.keys()):
                    # mise a 0 (nan)
                    if "trace_p_" in col or "trace_s_" in col:
                        meta_dict[col] = np.nan

            # Logique de split aléatoire (imitation de format_csv_hdf5.py)
            rand = random.random()
            if rand < 0.8:
                split = "train"
            elif rand < 0.9:
                split = "dev"
            else:
                split = "test"
            
            meta_dict["split"] = split

            writer.add_trace(meta_dict, waveform)
            total_traces += 1

    # Application de la fonction aux datasets
    process_dataset(vt_dataset, is_noise=False)
    process_dataset(lp_dataset, is_noise=(arg == "2"))

print(f"\n Conversion terminée ! {total_traces} traces enregistrées avec succès dans {OUTPUT_DIR}")