import os
import sys

os.environ["SEISBENCH_CACHE_ROOT"] = "/get/ggs/clov/volpick"

import pandas as pd
import seisbench.data as sbd
import random

#argument
if len(sys.argv) != 2 or sys.argv[1] not in ["1", "2"]:
    print("Usage: python volpick_fusion_dataset.py (1 ou 2)")
    print("  1 -> Sauvegarde VT + LP")
    print("  2 -> Sauvegarde VT")
    sys.exit(1)

arg = sys.argv[1]
BASE_DIR = "../data/volpick"

#noise
DIR_NOISE = os.path.join(BASE_DIR, "volpick_format_noise")

#PATH en fonction de l'argument
if arg == "1":
    DIR_EVENTS = os.path.join(BASE_DIR, "volpick_format_LPVT")
    DIR_FINAL = os.path.join(BASE_DIR, "volpick_dataset_LPVT")
    print("Fusion LPVT et Bruit.")
else:
    DIR_EVENTS = os.path.join(BASE_DIR, "volpick_format_VT")
    DIR_FINAL = os.path.join(BASE_DIR, "volpick_dataset_VT")
    print("Fusion VT et Bruit.")

SOURCES = {
    "event": DIR_EVENTS,
    "noise": DIR_NOISE
}

os.makedirs(DIR_FINAL, exist_ok=True)

#normaliser les secondes en dates
def fix_metadata_dates(folder_path):
    csv_path = os.path.join(folder_path, "metadata.csv")
    if not os.path.exists(csv_path):
        return
    df = pd.read_csv(csv_path, low_memory=False)
    time_cols = [c for c in df.columns if "time" in c]
    for col in time_cols:
        dts = pd.to_datetime(df[col], errors="coerce")
        df[col] = dts.dt.strftime("%Y-%m-%d %H:%M:%S.%f%z")
    df.to_csv(csv_path, index=False)


#debut fusion
print("\nNormalisation format des dates")
for name, path in SOURCES.items():
    fix_metadata_dates(path)


datasets = {}

for name, path in SOURCES.items():
    if not os.path.exists(path):
        print(f"!!! Erreur : Le dossier {path} est introuvable")
        sys.exit(1)
    try:
        ds = sbd.WaveformDataset(path, sampling_rate=100, component_order="ZNE")
        datasets[name] = ds
        print(f" -> {name} : {len(ds)} traces chargées depuis {path}.")
    except Exception as e:
        print(f"!!! Erreur lors du chargement de {name} : {e}")
        sys.exit(1)

print(f"\nEcriture du dataset dans {DIR_FINAL}")

metadata_path = os.path.join(DIR_FINAL, "metadata.csv")
waveforms_path = os.path.join(DIR_FINAL, "waveforms.hdf5")

total_traces = 0

with sbd.WaveformDataWriter(metadata_path, waveforms_path) as writer:
    writer.data_format = {
        "dimension_order": "CW",
        "component_order": "ZNE",
        "sampling_rate": 100
    }
    
    for name, ds in datasets.items():
        print(f"Copie des traces depuis : {name}")
        for i in range(len(ds)):
            trace_metadata = ds.metadata.iloc[i].to_dict()
            waveform_data = ds.get_waveforms(i)
            
            rand = random.random()
            if rand < 0.8:
                split = "train"
            elif rand < 0.9:
                split = "dev"
            else:
                split = "test"
            
            trace_metadata["split"]=split
            writer.add_trace(trace_metadata, waveform_data)
            total_traces += 1

print(f"\nFusion termine avec succès ! {total_traces} traces enregistrées dans : {DIR_FINAL}")