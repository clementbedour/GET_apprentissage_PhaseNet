import torch
import numpy as np
import pandas as pd
import random
import matplotlib.pyplot as plt
import seisbench.data as sbd
import seisbench.models as sbm
from scipy.signal import butter, filtfilt
import os

# Variables d'environnement pour snuffler (sur WSL y'a des problèmes)
os.environ['LD_LIBRARY_PATH'] = os.environ.get('CONDA_PREFIX', '') + '/lib:' + os.environ.get('LD_LIBRARY_PATH', '')
os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['QT_XCB_GL_INTEGRATION'] = 'none'
os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = '/home/guiga/miniconda3/envs/phasenet/plugins/platforms'


# ============================================================
# CONFIGURATION
# ============================================================
DATASET_DIR = "../data/seisbench/seisbench_format_gold"
MODEL_PATH = "seisbench/phasenet_volcan_v2_FINAL.pt"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
SAMPLING_RATE = 100.0
# Seuil de confiance minimal pour afficher (80%)
CONFIDENCE_THRESHOLD = 0.65 
NOMBRE_ECHANTILLONS = 20 # J'ai augmenté un peu car beaucoup seront filtrés

# Fonction pour le filtre passe-bande
def apply_bandpass(data, lowcut=5.0, highcut=12.0, fs=100.0, order=4):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, data, axis=1)

# ============================================================
# 1. CHARGEMENT
# ============================================================
print(f"Chargement du dataset...")
dataset = sbd.WaveformDataset(DATASET_DIR, component_order="ZNE", sampling_rate=100)
model = sbm.PhaseNet()
model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
model.eval()
model.to(DEVICE)

# Tirage aléatoire (on prend plus large car on va filtrer par confiance)
indices = random.sample(range(len(dataset)), min(NOMBRE_ECHANTILLONS * 5, len(dataset)))
results = []
traces_affichees = 0

print(f"Analyse en cours (Seuil de confiance > {CONFIDENCE_THRESHOLD})...\n")

# ============================================================
# 2. BOUCLE D'ANALYSE
# ============================================================
for i in indices:
    if traces_affichees >= NOMBRE_ECHANTILLONS: break
    
    waveform = dataset.get_waveforms(i)
    metadata = dataset.metadata.iloc[i]
    
    center = int(metadata.get("center_sample", waveform.shape[1] // 2))
    start = max(0, center - 1500)
    end = min(waveform.shape[1], start + 3001)
    if end - start < 3001: start = max(0, end - 3001)
    
    waveform_subset = waveform[:, start:end]
    if waveform_subset.shape[1] != 3001: continue

    # Normalisation pour IA
    waveform_norm = waveform_subset.copy()
    for c in range(3):
        waveform_norm[c] -= np.mean(waveform_norm[c])
        max_val = np.max(np.abs(waveform_norm[c]))
        if max_val > 0: waveform_norm[c] /= max_val

    X = torch.tensor(waveform_norm, dtype=torch.float32).unsqueeze(0).to(DEVICE)
    
    with torch.no_grad():
        preds = model(X)[0].cpu().numpy()
        
    # --- FILTRAGE PAR CONFIANCE ---
    max_prob_p = np.max(preds[0])
    max_prob_s = np.max(preds[1])
    
    # Si ni P ni S n'atteignent 80%, on ignore cette trace
    if max_prob_p < CONFIDENCE_THRESHOLD and max_prob_s < CONFIDENCE_THRESHOLD:
        continue
    
    # Si on arrive ici, l'IA est confiante !
    traces_affichees += 1
    
    ia_p = np.argmax(preds[0]) + start if max_prob_p > 0.35 else np.nan
    ia_s = np.argmax(preds[1]) + start if max_prob_s > 0.35 else np.nan
    
    gold_p = metadata.get("trace_p_arrival_sample", np.nan)
    gold_s = metadata.get("trace_s_arrival_sample", np.nan)
    
    results.append({"Trace": metadata.get("trace_name", i), "Conf_P": max_prob_p, "Conf_S": max_prob_s})

    # --- VISUALISATION ---
    waveform_filtered = apply_bandpass(waveform_subset)
    fig, axs = plt.subplots(4, 1, figsize=(10, 6), sharex=True)
    time_ax = np.arange(start, start + 3001) / SAMPLING_RATE
    
    for ch in range(3):
        axs[ch].plot(time_ax, waveform_filtered[ch], color='k', lw=0.6)
        if not np.isnan(gold_p): axs[ch].axvline(gold_p/100, color='blue', ls='--', label='Gold P')
        if not np.isnan(ia_p): axs[ch].axvline(ia_p/100, color='blue', ls=':', label='IA P')
    
    axs[3].plot(time_ax, preds[0], color='blue', label=f'Prob P ({max_prob_p:.2f})')
    axs[3].plot(time_ax, preds[1], color='red', label=f'Prob S ({max_prob_s:.2f})')
    axs[3].legend(loc='upper right')
    plt.suptitle(f"Trace: {metadata.get('trace_name')} - IA Confiance > {CONFIDENCE_THRESHOLD}")
    plt.show()

# ============================================================
# 3. STATISTIQUES
# ============================================================
df = pd.DataFrame(results)
print(f"\n--- ANALYSE TERMINÉE ---")
print(f"Nombre de traces affichées avec haute confiance : {len(df)}")