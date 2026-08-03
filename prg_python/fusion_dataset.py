import os
import seisbench.data as sbd
import sys

#------------PARAMETRES--------------------
BASE_DIR = "../data"

if len(sys.argv) > 1:
    var = sys.argv[1].lower()
    if 'a'==var :
        SOURCES = {
                "Original": os.path.join(BASE_DIR, "seisbenchA/seisbench_format"),
                "Bruit": os.path.join(BASE_DIR, "seisbench/seisbench_format_noise"),
                "Gold": os.path.join(BASE_DIR, "seisbenchA/seisbench_format_gold")
            }
        DIR_FINAL = os.path.join(BASE_DIR, "seisbenchA/seisbench_dataset_ultime")

    elif 'b'==var :
        SOURCES = {
                "Original": os.path.join(BASE_DIR, "seisbenchB/seisbench_format"),
                "Bruit": os.path.join(BASE_DIR, "seisbench/seisbench_format_noise"),
                "Gold": os.path.join(BASE_DIR, "seisbenchB/seisbench_format_gold")
            }
        DIR_FINAL = os.path.join(BASE_DIR, "seisbenchB/seisbench_dataset_ultime")

else :
    var = 'c'
    #les 3 repertoires à fusionner 
    SOURCES = {
        "Original": os.path.join(BASE_DIR, "seisbench/seisbench_format"),
        "Bruit": os.path.join(BASE_DIR, "seisbench/seisbench_format_noise"),
        "Gold": os.path.join(BASE_DIR, "seisbench/seisbench_format_gold")
    }
    #dossier final
    DIR_FINAL = os.path.join(BASE_DIR, "seisbench/seisbench_dataset_ultime")

print(f"On veux une qualité minimal de {var}")
os.makedirs(DIR_FINAL, exist_ok=True)

path_csv = os.path.join(DIR_FINAL, "metadata.csv")
path_hdf5 = os.path.join(DIR_FINAL, "waveforms.hdf5")

# ------------ FUSION ------------
print("Chargement des datasets sources")
datasets = {}
for name, path in SOURCES.items():
    try:
        ds = sbd.WaveformDataset(path, sampling_rate=100, component_order="ZNE")
        datasets[name] = ds
        print(f"-> {name} : {len(ds)} traces chargées.")
    except Exception as e:
        print(f"!!! Erreur lors du chargement de {name} : {e}")

print(f"\nDébut de la fusion dans {DIR_FINAL}")

with sbd.WaveformDataWriter(path_csv, path_hdf5) as writer:
    #on précise le format pour être sur
    writer.data_format = {
        "dimension_order": "CW",
        "measurement": "velocity",
        "unit": "counts",
    }
    
    #fusion des datasets
    for name, ds in datasets.items():
        print(f"Copie des traces depuis : {name}")
        for i in range(len(ds)):
            trace_metadata = ds.metadata.iloc[i].to_dict()
            waveform_data = ds.get_waveforms(i)
            
            #ecriture dans le nouveau dataset
            writer.add_trace(trace_metadata, waveform_data)

print(f"\nFusion terminée")
print(f"Dataset final prêt à l'emploi : {DIR_FINAL}")