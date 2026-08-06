import os
import sys
import torch
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import butter, sosfiltfilt
import seisbench.data as sbd
import seisbench.models as sbm
import seisbench.generate as sbg

# pb affichage WSL
os.environ['LD_LIBRARY_PATH'] = os.environ.get('CONDA_PREFIX', '') + '/lib:' + os.environ.get('LD_LIBRARY_PATH', '')
os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['QT_XCB_GL_INTEGRATION'] = 'none'
os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = '/home/guiga/miniconda3/envs/phasenet/plugins/platforms'

#------------ARGUMENTS--------------------
# Valeurs par défaut
mode_modele = 1 
qualite = 'c'

#version du modele
if len(sys.argv) > 1:
    try:
        mode_modele = int(sys.argv[1])
    except ValueError:
        print("Erreur : Le premier argument doit être un entier (1 ou 2).")
        sys.exit(1)

#qualite
if len(sys.argv) > 2:
    qualite = sys.argv[2].lower()

if qualite == 'a':
    DOSSIER_QUALITE = "seisbenchA"
elif qualite == 'b':
    DOSSIER_QUALITE = "seisbenchB"
else:
    DOSSIER_QUALITE = "seisbench"

BASE_DIR = "../data"
SEIS_PATH = DOSSIER_QUALITE



#path celon arguments
if mode_modele == 1:
    DATASET_DIR = os.path.join(BASE_DIR, DOSSIER_QUALITE, "seisbench_dataset")
    MODEL = "phasenet_volcan_v1.pt"
    print(f"--- Lancement : Modèle V1 | Qualité '{qualite.upper()}' ---")
    OUTPUT_DIR = os.path.join("../images",DOSSIER_QUALITE,"V1")
elif mode_modele == 2:
    DATASET_DIR = os.path.join(BASE_DIR, DOSSIER_QUALITE, "seisbench_dataset_ultime")
    MODEL = "phasenet_volcan_v2.pt"
    print(f"--- Lancement : Modèle V2 | Qualité '{qualite.upper()}' ---")
    OUTPUT_DIR = os.path.join("../images",DOSSIER_QUALITE,"V2")
else:
    print("Erreur : Valeur inconnue pour le modèle (utiliser 1 ou 2)")
    sys.exit(1)
    
#dossier destination images
os.makedirs(OUTPUT_DIR, exist_ok=True)

MODEL_PATH = os.path.join(SEIS_PATH, MODEL)

#------------PARAMETRES--------------------
SEUIL_PROB = 0.8            #seuil de proba min pour save l'image
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

SAMPLING_RATE = 100

NB_EXEMPLES_SAVE = 20
SEUIL_AFFICHER_POINTE = 0.3     #on affiche pas si plus petit (pour pas avoir S si petit)


#passe bande
FREQ_MIN = 3.0
FREQ_MAX = 20.0


print(f"Chargement du modèle depuis : {MODEL_PATH}")
model = sbm.PhaseNet()

if not os.path.exists(MODEL_PATH) and os.path.exists(MODEL):
    MODEL_PATH = MODEL

model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
model.to(DEVICE)
model.eval()

#------------DATA--------------------
nyq = 0.5 * SAMPLING_RATE
sos_filter = butter(4, [FREQ_MIN / nyq, min(FREQ_MAX / nyq, 0.99)], btype='bandpass', output='sos')

dataset = sbd.WaveformDataset(DATASET_DIR, component_order="ZNE", sampling_rate=SAMPLING_RATE)
test_dataset = dataset.test()
print(f"{len(test_dataset)} traces disponibles dans test")

transforms = [
    sbg.WindowAroundSample("center_sample", samples_before=1500, windowlen=3001, strategy="pad"),
    sbg.Normalize(detrend_axis=-1, amp_norm_axis=-1),
    sbg.ChangeDtype(np.float32),
]

test_gen = sbg.GenericGenerator(test_dataset)
test_gen.add_augmentations(transforms)

#------------AFFICHAGE--------------------
def tracer_predictions(index_trace, sample):
    trace_brute = sample["X"]  # Shape (3, 3001)
    
    #passe bande
    trace_filtree = sosfiltfilt(sos_filter, trace_brute, axis=-1)
    
    tensor_trace = torch.tensor(trace_filtree.copy(), dtype=torch.float32).unsqueeze(0).to(DEVICE)
    
    #PhaseNet
    with torch.no_grad():
        predictions = model(tensor_trace).cpu().numpy()[0]  # Shape (3, 3001)
        
    prob_P = predictions[0]
    prob_S = predictions[1]
    prob_Noise = predictions[2]
    
    temps = np.arange(trace_filtree.shape[1]) / SAMPLING_RATE
    
    #metadata
    meta = test_dataset.metadata.iloc[index_trace]
    center_sample = meta['center_sample']
    start_sample_window = center_sample - 1500
    
    p_arrival_abs = meta.get('trace_p_arrival_sample', np.nan)
    s_arrival_abs = meta.get('trace_s_arrival_sample', np.nan)
    
    p_sec = (p_arrival_abs - start_sample_window) / SAMPLING_RATE if pd.notna(p_arrival_abs) else None
    s_sec = (s_arrival_abs - start_sample_window) / SAMPLING_RATE if pd.notna(s_arrival_abs) else None
    
    station = meta.get('station_code', 'Inconnue')
    
    date_val = meta.get('trace_start_time', None)
    jour = "?"
    mois = "?"
    if date_val is not None and pd.notna(date_val):
        try:
            dt = pd.to_datetime(str(date_val))
            jour = dt.day
            mois = dt.month
        except Exception:
            pass

    #pointe IA
    p_ai_sec = temps[np.argmax(prob_P)] if np.max(prob_P) >= SEUIL_AFFICHER_POINTE else None
    s_ai_sec = temps[np.argmax(prob_S)] if np.max(prob_S) >= SEUIL_AFFICHER_POINTE else None

    #manuel ou IA
    is_ai = 'gold_standard' in meta and pd.notna(meta['gold_standard']) and meta['gold_standard'] == True
    label_source = " | [Trouvé par IA]" if is_ai else " | [Manuel]"

    #trace graphique
    fig, axs = plt.subplots(4, 1, figsize=(12, 9), sharex=True)
    fig.suptitle(f"Modèle {mode_modele}{label_source} | Trace n°{index_trace} | Station: {station} | Date: {jour}/{mois}")
    
    canaux = ["Z", "N", "E"]
    couleurs = ["black", "black", "black"]
    
    for i in range(3):
        axs[i].plot(temps, trace_filtree[i], color=couleurs[i], linewidth=0.8)
        axs[i].set_ylabel(canaux[i])
        axs[i].grid(True, linestyle="--", alpha=0.5)
        
        #pointe originel
        if p_sec is not None and 0 <= p_sec <= temps[-1]:
            axs[i].axvline(x=p_sec, color="cyan", linestyle=":", linewidth=1.8, label="Pointé P (Réf/CSV)" if i == 0 else "")
        if s_sec is not None and 0 <= s_sec <= temps[-1]:
            axs[i].axvline(x=s_sec, color="magenta", linestyle=":", linewidth=1.8, label="Pointé S (Réf/CSV)" if i == 0 else "")
            
        #pointe par model
        if p_ai_sec is not None:
            axs[i].axvline(x=p_ai_sec, color="blue", linestyle="--", linewidth=1.5, label="Pointé P (IA live)" if i == 0 else "")
        if s_ai_sec is not None:
            axs[i].axvline(x=s_ai_sec, color="red", linestyle="--", linewidth=1.5, label="Pointé S (IA live)" if i == 0 else "")
        
    #gaussiens (P, S et Bruit)
    axs[3].plot(temps, prob_P, color="blue", label="Probabilité P (IA)", linewidth=1.5)
    axs[3].plot(temps, prob_S, color="red", label="Probabilité S (IA)", linewidth=1.5)
    axs[3].plot(temps, prob_Noise, color="green", label="Probabilité Bruit (IA)", linewidth=1.5, alpha=0.7)
    
    axs[3].axhline(SEUIL_PROB, color="orange", linestyle="--", alpha=0.8, label=f"Seuil P/S {SEUIL_PROB}")
    
    if p_sec is not None and 0 <= p_sec <= temps[-1]:
        axs[3].axvline(x=p_sec, color="cyan", linestyle=":", linewidth=1.8, label="Pointé P (Réf/CSV)")
    if s_sec is not None and 0 <= s_sec <= temps[-1]:
        axs[3].axvline(x=s_sec, color="magenta", linestyle=":", linewidth=1.8, label="Pointé S (Réf/CSV)")

    if p_ai_sec is not None:
        axs[3].axvline(x=p_ai_sec, color="blue", linestyle="--", linewidth=1.5, label="Pointé P (IA live)")
    if s_ai_sec is not None:
        axs[3].axvline(x=s_ai_sec, color="red", linestyle="--", linewidth=1.5, label="Pointé S (IA live)")

    axs[3].set_ylabel("Probabilité")
    axs[3].set_xlabel("Temps (secondes)")
    axs[3].set_ylim(0, 1.05)
    
    handles, labels = axs[3].get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    axs[3].legend(by_label.values(), by_label.keys(), loc="upper right")
    axs[3].grid(True, linestyle="--", alpha=0.5)
    
    plt.tight_layout()
    
    print(f"Echantillon n°{index_trace}{label_source} | proba P max : {np.max(prob_P):.3f}")
    
    #save image
    output_path = os.path.join(OUTPUT_DIR, f"trace_{index_trace}_modele_{mode_modele}_qualite_{qualite}.png")
    plt.savefig(output_path, bbox_inches='tight')
    plt.close(fig) #free memoire
    #print(f"Image sauvegardée : {output_path}")

#------------RECHERCHE EVENT--------------------
print(f"Recherche échantillons avec proba P/S >= {SEUIL_PROB}")
indices_valides = []
echantillons_stockes = {}

for idx in range(len(test_dataset)):
    sample = test_gen[idx]
    trace_brute = sample["X"]
    trace_filtree = sosfiltfilt(sos_filter, trace_brute, axis=-1)
    tensor_trace = torch.tensor(trace_filtree.copy(), dtype=torch.float32).unsqueeze(0).to(DEVICE)
    
    with torch.no_grad():
        predictions = model(tensor_trace).cpu().numpy()[0]
        
    prob_P = predictions[0]
    prob_S = predictions[1]
    
    if np.max(prob_P) >= SEUIL_PROB or np.max(prob_S) >= SEUIL_PROB:
        indices_valides.append(idx)
        echantillons_stockes[idx] = sample

print(f"-> {len(indices_valides)} échantillons trouvés")

if len(indices_valides) > 0:
    nb_save = min(NB_EXEMPLES_SAVE, len(indices_valides))
    indices_aleatoires = np.random.choice(indices_valides, nb_save, replace=False)

    for idx in indices_aleatoires:
        tracer_predictions(idx, echantillons_stockes[idx])
else:
    print(f"Aucun échantillon ne dépasse le seuil de {SEUIL_PROB} dans le jeu de test.")