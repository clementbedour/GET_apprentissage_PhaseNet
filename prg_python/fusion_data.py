import os
import seisbench.data as sbd

# ------------ PARAMATRES ------------
BASE_DIR = "../data"

# fichiers à fusionner
DIR_EVENTS = os.path.join(BASE_DIR, "seisbench/seisbench_format")
DIR_NOISE = os.path.join(BASE_DIR, "seisbench/seisbench_format_noise")

# Le fichier final
DIR_FINAL = os.path.join(BASE_DIR, "seisbench/seisbench_dataset")
os.makedirs(DIR_FINAL, exist_ok=True)

path_csv = os.path.join(DIR_FINAL, "metadata.csv")
path_hdf5 = os.path.join(DIR_FINAL, "waveforms.hdf5")

# chargement des fichiers
print("Chargement des datasets sources")
ds_events = sbd.WaveformDataset(DIR_EVENTS, component_order="ZNE", sampling_rate=100)
ds_noise = sbd.WaveformDataset(DIR_NOISE, component_order="ZNE", sampling_rate=100)


print(f"-> {len(ds_events)} vrais événements trouvés.")
print(f"-> {len(ds_noise)} traces de bruit trouvées.")

# fusion + ecriture
print("\nDébut de la fusion")

with sbd.WaveformDataWriter(path_csv, path_hdf5) as writer:
    
    # On garde le même format
    writer.data_format = {
        "dimension_order": "CW",
        "measurement": "velocity",
        "unit": "counts",
    }
    
    # ecriture des events 
    print("Copie des événements")
    for i in range(len(ds_events)):
        # recupere les metadata en dictionnaire
        trace_metadata = ds_events.metadata.iloc[i].to_dict()
        # recupere la matrice de signal
        waveform_data = ds_events.get_waveforms(i)
        
        writer.add_trace(trace_metadata, waveform_data)
        
    # ecriture des traces de bruit
    print("Copie des traces de bruit")
    for i in range(len(ds_noise)):
        trace_metadata = ds_noise.metadata.iloc[i].to_dict()
        waveform_data = ds_noise.get_waveforms(i)
        
        writer.add_trace(trace_metadata, waveform_data)

print(f"\nFusion terminée avec succès !")
print(f"Total : {len(ds_events) + len(ds_noise)} traces prêtes pour l'entraînement.")