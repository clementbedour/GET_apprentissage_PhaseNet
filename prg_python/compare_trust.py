import os
import sys
import torch
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, sosfiltfilt
import seisbench.data as sbd
import seisbench.models as sbm
import seisbench.generate as sbg

# ------------ ARGUMENTS ------------
mode_modele = 1 
qualite = 'c'

#version
if len(sys.argv) > 1:
    try:
        mode_modele = int(sys.argv[1])
    except ValueError:
        print("Erreur : Le premier argument doit être un entier (1 ou 2).")
        sys.exit(1)

#qualite
if len(sys.argv) > 2:
    qualite = sys.argv[2].lower()

BASE_DIR = "../data"
IMAGE_DIR = "../images"

if qualite == 'a':
    DOSSIER_QUALITE = "seisbenchA"
elif qualite == 'b':
    DOSSIER_QUALITE = "seisbenchB"
else:
    DOSSIER_QUALITE = "seisbench"

#path modele
MODEL_V1_PATH = os.path.join(DOSSIER_QUALITE, "phasenet_volcan_v1.pt")
MODEL_V2_PATH = os.path.join(DOSSIER_QUALITE, "phasenet_volcan_v2.pt")

if mode_modele == 1:
    DATASET_DIR = os.path.join(BASE_DIR, DOSSIER_QUALITE, "seisbench_dataset")
else:
    DATASET_DIR = os.path.join(BASE_DIR, DOSSIER_QUALITE, "seisbench_dataset_ultime")
    if not os.path.exists(DATASET_DIR):
        DATASET_DIR = os.path.join(BASE_DIR, DOSSIER_QUALITE, "seisbench_dataset")

# ------------ PARAMÈTRES ------------
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
SAMPLING_RATE = 100
FREQ_MIN = 3.0
FREQ_MAX = 20.0

nyq = 0.5 * SAMPLING_RATE
sos_filter = butter(4, [FREQ_MIN / nyq, min(FREQ_MAX / nyq, 0.99)], btype='bandpass', output='sos')

# ------------ FONCTION D'ÉVALUATION ------------
def evaluer_modele(path_modele, dataset_path):
    if not os.path.exists(path_modele):
        print(f"Erreur : Le fichier {path_modele} n'existe pas.")
        sys.exit(1)
        
    #print(f"Chargement du modèle : {path_modele}")
    model = sbm.PhaseNet().to(DEVICE)
    model.load_state_dict(torch.load(path_modele, map_location=DEVICE))
    model.eval()

    dataset = sbd.WaveformDataset(dataset_path, component_order="ZNE", sampling_rate=SAMPLING_RATE)
    test_dataset = dataset.test()

    transforms = [
        sbg.WindowAroundSample("center_sample", samples_before=1500, windowlen=3001, strategy="pad"),
        sbg.Normalize(detrend_axis=-1, amp_norm_axis=-1),
        sbg.ChangeDtype(np.float32),
    ]

    test_gen = sbg.GenericGenerator(test_dataset)
    test_gen.add_augmentations(transforms)

    scores_p, scores_s = [], []

    print(f"Évaluation sur {len(test_dataset)} traces dans {dataset_path}...")
    with torch.no_grad():
        for idx in range(len(test_dataset)):
            sample = test_gen[idx]
            trace_brute = sample["X"]
            trace_filtree = sosfiltfilt(sos_filter, trace_brute, axis=-1)
            tensor_trace = torch.tensor(trace_filtree.copy(), dtype=torch.float32).unsqueeze(0).to(DEVICE)
            
            predictions = model(tensor_trace).cpu().numpy()[0]
            scores_p.append(np.max(predictions[0])) #proba max P
            scores_s.append(np.max(predictions[1])) #proba max S

    return scores_p, scores_s

#path dossier sortie image
path_folder_images = os.path.join(IMAGE_DIR, DOSSIER_QUALITE)
os.makedirs(path_folder_images, exist_ok=True)
bins = np.linspace(0, 1.0, 25)

# ------------ EXÉCUTION EN FONCTION DU MODE ------------
if mode_modele == 1:
    print(f"\n--- Repartition du Score de confiance V1 (Qualité {qualite.upper()}) ---")
    scores_v1_p, scores_v1_s = evaluer_modele(MODEL_V1_PATH, DATASET_DIR)
    
    #V1 nbr de trace
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    axes[0].hist(scores_v1_p, bins=bins, color="blue", alpha=0.7, edgecolor="black")
    axes[0].set_title("Onde P", fontsize=12, fontweight="bold")
    axes[0].set_xlabel("Score de confiance")
    axes[0].set_ylabel("Nombre de traces")
    axes[0].grid(True, linestyle=":", alpha=0.6)
    
    axes[1].hist(scores_v1_s, bins=bins, color="navy", alpha=0.7, edgecolor="black")
    axes[1].set_title("Onde S", fontsize=12, fontweight="bold")
    axes[1].set_xlabel("Score de confiance")
    axes[1].set_ylabel("Nombre de traces")
    axes[1].grid(True, linestyle=":", alpha=0.6)

    plt.suptitle(f"Distribution des scores de confiance - Modèle V1 ({qualite.upper()})", fontsize=14, fontweight="bold")
    plt.tight_layout()

    out_path = os.path.join(path_folder_images, f"confiance_V1_{qualite}.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"-> Graphique V1 sauvegardé sous : {out_path}")

elif mode_modele == 2:
    print("\n--- Modèle V2 ---")
    scores_v2_p, scores_v2_s = evaluer_modele(MODEL_V2_PATH, DATASET_DIR)
    
    #V2 nbr de trace
    fig1, axes1 = plt.subplots(1, 2, figsize=(12, 5))
    
    axes1[0].hist(scores_v2_p, bins=bins, color="green", alpha=0.7, edgecolor="black")
    axes1[0].set_title("Onde P", fontsize=12, fontweight="bold")
    axes1[0].set_xlabel("Score de confiance")
    axes1[0].set_ylabel("Nombre de traces")
    axes1[0].grid(True, linestyle=":", alpha=0.6)
    
    axes1[1].hist(scores_v2_s, bins=bins, color="darkgreen", alpha=0.7, edgecolor="black")
    axes1[1].set_title("Onde S", fontsize=12, fontweight="bold")
    axes1[1].set_xlabel("Score de confiance")
    axes1[1].set_ylabel("Nombre de traces")
    axes1[1].grid(True, linestyle=":", alpha=0.6)
    
    fig1.suptitle(f"Distribution des scores de confiance - Modèle V2 ({qualite.upper()})", fontsize=14, fontweight="bold")
    fig1.tight_layout()
    
    out_path_v2 = os.path.join(path_folder_images, f"confiance_V2_{qualite}.png")
    fig1.savefig(out_path_v2, dpi=300)
    plt.close(fig1)
    print(f"-> Graphique V2 seule sauvegardé sous : {out_path_v2}")
    

print("Graphique score de confiance terminé avec succès.")