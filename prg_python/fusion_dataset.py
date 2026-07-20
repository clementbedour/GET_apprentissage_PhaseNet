import os
import seisbench.data as sbd

# ------------ CONFIGURATION ------------
BASE_DIR = "../data"

# Tes trois sources de données
SOURCES = {
    "Original": os.path.join(BASE_DIR, "seisbench/seisbench_format"),
    "Bruit": os.path.join(BASE_DIR, "seisbench/seisbench_format_noise"),
    "Gold": os.path.join(BASE_DIR, "seisbench/seisbench_format_gold")
}

# Le dossier final qui contiendra le dataset fusionné
DIR_FINAL = os.path.join(BASE_DIR, "seisbench/seisbench_dataset_ultime")
os.makedirs(DIR_FINAL, exist_ok=True)

path_csv = os.path.join(DIR_FINAL, "metadata.csv")
path_hdf5 = os.path.join(DIR_FINAL, "waveforms.hdf5")

# ------------ FUSION ------------
print("Chargement des datasets sources...")
datasets = {}
for name, path in SOURCES.items():
    try:
        ds = sbd.WaveformDataset(path, sampling_rate=100, component_order="ZNE")
        datasets[name] = ds
        print(f"-> {name} : {len(ds)} traces chargées.")
    except Exception as e:
        print(f"!!! Erreur lors du chargement de {name} : {e}")

print(f"\nDébut de la fusion dans {DIR_FINAL}...")

with sbd.WaveformDataWriter(path_csv, path_hdf5) as writer:
    # On définit le format pour garantir la cohérence
    writer.data_format = {
        "dimension_order": "CW",
        "measurement": "velocity",
        "unit": "counts",
    }
    
    # Fusion des datasets
    for name, ds in datasets.items():
        print(f"Copie des traces depuis : {name}...")
        for i in range(len(ds)):
            # Récupération propre
            trace_metadata = ds.metadata.iloc[i].to_dict()
            waveform_data = ds.get_waveforms(i)
            
            # Écriture dans le nouveau dataset
            writer.add_trace(trace_metadata, waveform_data)

print(f"\nMAGNIFIQUE ! Fusion terminée.")
print(f"Ton dataset ultime est prêt à l'emploi : {DIR_FINAL}")