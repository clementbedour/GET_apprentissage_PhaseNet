import os
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import seisbench.data as sbd
import seisbench.models as sbm
import seisbench.generate as sbg
import sys


#------------ARGUMENTS--------------------

#val défault
mode_entrainement = 1 
qualite = 'c'

#arg 1 : mode learning
if len(sys.argv) > 1:
    try:
        mode_entrainement = int(sys.argv[1])
    except ValueError:
        print("Erreur : Le premier argument doit être un entier (1 ou 2).")
        sys.exit(1)

#arg 2 : qualite
if len(sys.argv) > 2:
    qualite = sys.argv[2].lower()

BASE_DIR = "../data"

#dossier en fonction de la qualité
if qualite == 'a':
    DOSSIER_QUALITE = "seisbenchA"
elif qualite == 'b':
    DOSSIER_QUALITE = "seisbenchB"
else:
    DOSSIER_QUALITE = "seisbench"


LOCAL_MODEL_PATH = os.path.join(DOSSIER_QUALITE, "phasenet_volcan_v1.pt")
SAVE_MODEL_PATH = os.path.join(DOSSIER_QUALITE, "phasenet_volcan_v2.pt")
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

if mode_entrainement == 1:
    START_FROM_ZERO = True
    DATASET_DIR = os.path.join(BASE_DIR, DOSSIER_QUALITE, "seisbench_dataset")
    EPOCHS = 300
    LEARNING_RATE = 1e-4
    SIGMA=35
    print("Mode : Entraînement DE ZÉRO")
    
    # on donne un poids de 2.0 pour P, 1.0 pour S, et 0.5 pour le Bruit
    #on veux qu'il se concentre surtout sur P et un peu S
    poids_classes = torch.tensor([2.0, 1.0, 0.8], dtype=torch.float32).to(DEVICE)
else:
    DATASET_DIR = os.path.join(BASE_DIR, DOSSIER_QUALITE, "seisbench_dataset_ultime")
    START_FROM_ZERO = False 
    EPOCHS = 150           # Moins d'époques nécessaires car Fine-Tuning
    LEARNING_RATE = 5e-5
    SIGMA = 15
    print(f"Mode : FINE-TUNING LOCAL depuis {LOCAL_MODEL_PATH}")
    
    #on durcit et on veux qu'il fasse attention à ne pas détecter du bruit
    poids_classes = torch.tensor([1.5, 1.0, 1.2], dtype=torch.float32).to(DEVICE)

print(f"On veux une qualité minimal de {qualite}")

#------------PARAMETRES--------------------
PATIENCE = 10 #nombre d'epoque sans changement pour arrêt modèle

BATCH_SIZE = 32
# chargement des données
dataset = sbd.WaveformDataset(DATASET_DIR, component_order="ZNE", sampling_rate=100)
train_dataset = dataset.train()
val_dataset = dataset.dev()
print(f"Succès ! Dataset chargé. Train: {len(train_dataset)} | Val: {len(val_dataset)}")

phase_dict = {
    "trace_p_arrival_sample": "P", 
    "trace_s_arrival_sample": "S"
}

def add_noise_channel(sample):
    """Calcule le canal bruit en gérant correctement les tuples de SeisBench"""
    x_data, x_meta = sample["X"]
    y_data, y_meta = sample["y"]
    
    target_len = x_data.shape[-1]
    
    y_clean = []
    
    #orce la selection de P et S
    for arr in y_data[:2]: 
        arr = np.array(arr, dtype=np.float32)
        if len(arr) < target_len:
            arr = np.pad(arr, (0, target_len - len(arr)))
        elif len(arr) > target_len:
            arr = arr[:target_len]
        y_clean.append(arr)
        
    #empile pour cree une matrice 2D (2, target_len)
    y = np.vstack(y_clean)
    
    #bruit = 1 - (P + S)
    noise = 1.0 - np.sum(y, axis=0, keepdims=True)
    noise = np.clip(noise, 0.0, 1.0)
    
    # forme (3, target_len) [P, S, Bruit]
    y_final = np.concatenate([y, noise], axis=0)
    
    sample["y"] = (y_final, y_meta)
    
    return sample
# pipeline d'augmentation
transforms = [
    #recupere une fenêtre de 6000 point (3000 avant le centre) et full 0 si pas de data
    sbg.WindowAroundSample(
        "center_sample", 
        samples_before=3000, 
        windowlen=6000, 
        strategy="pad"
    ),
    #decoupe 3001 point dans cette fenêtre (ce n'est plus centré)
    sbg.RandomWindow(windowlen=3001, strategy="pad"),
    sbg.ChangeDtype(np.float32),
    sbg.Normalize(detrend_axis=-1, amp_norm_axis=-1),
    #créer une courbe gaussienne pour le pointé
    sbg.ProbabilisticLabeller(
        label_columns=phase_dict, 
        sigma=SIGMA, 
        dim=0
    ),
    add_noise_channel
]

train_gen = sbg.GenericGenerator(train_dataset)
train_gen.add_augmentations(transforms)

val_gen = sbg.GenericGenerator(val_dataset)
val_gen.add_augmentations(transforms)

train_loader = DataLoader(train_gen, batch_size=BATCH_SIZE, shuffle=True)
val_loader = DataLoader(val_gen, batch_size=BATCH_SIZE, shuffle=False)

# init modele et fonction de perte
model = sbm.PhaseNet()

if START_FROM_ZERO:
    print("Initialisation du modèle avec des poids aléatoires")
else:
    if os.path.exists(LOCAL_MODEL_PATH):
        # si Fine Tuning alors on charge le modele deja entraine
        model.load_state_dict(torch.load(LOCAL_MODEL_PATH, map_location=DEVICE))
    else:
        raise FileNotFoundError(f"Fichier {LOCAL_MODEL_PATH} introuvable !")

#envoie au GPU ou CPU
model.to(DEVICE)

#algo d'optimisation, calcul en fonction des erreurs des poids
optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

# perte pondéré
criterion = nn.CrossEntropyLoss(weight=poids_classes)

# entrainement
best_val_loss = float('inf') #init à l'infini
patience_counter = 0 #init meilleur modèle ressent


# --- save pour affichage graphique ---
mode_str_file = "scratch" if START_FROM_ZERO else "finetuning"
history_file = os.path.join(BASE_DIR, DOSSIER_QUALITE, f"loss_history_{mode_str_file}.csv")
training_history = []
# -------------------------------------------------------------

print("\nDébut de l'entraînement")
for epoch in range(EPOCHS):
    model.train() #mode training
    train_loss = 0
    for batch in train_loader:
        X, y = batch["X"].to(DEVICE), batch["y"].to(DEVICE) #envoie signaux et cible vers DEVICE
        optimizer.zero_grad() #reset à 0
        output = model(X) #passe avant (passe la trace dans le reseau)
        loss = criterion(output, y) #calcul erreur globale via CrossEntropy
        loss.backward() #regarde quelle point doivent être modifié
        optimizer.step() #on les modifie
        train_loss += loss.item() * X.size(0) #calcule erreur globale
    
    model.eval() #mode eval
    val_loss = 0
    with torch.no_grad(): #pas besoin du calcul des gradients
        for batch in val_loader:
            X, y = batch["X"].to(DEVICE), batch["y"].to(DEVICE)
            val_loss += criterion(model(X), y).item() * X.size(0)
            
    train_loss /= len(train_dataset) #pour pour voir l'amélioration de l'entrainement
    val_loss /= len(val_dataset) # pareil mais pour la validation
    
    print(f"Époque {epoch+1:02d}/{EPOCHS} | Train Loss: {train_loss:.5f} | Val Loss: {val_loss:.5f}")
    
    #sauvegarde pour affichage graphique
    training_history.append({
        "epoch": epoch + 1,
        "train_loss": train_loss,
        "val_loss": val_loss
    })
    pd.DataFrame(training_history).to_csv(history_file, index=False)
    
    
    # On sauvegarde le meilleur model si meilleur
    if val_loss < best_val_loss:
        best_val_loss = val_loss
        patience_counter = 0 # reset car meilleur modèle ressent
        
        if qualite == 'a':
            save_name = "seisbenchA/phasenet_volcan_v2.pt" if not START_FROM_ZERO else LOCAL_MODEL_PATH
        elif qualite == 'b':
            save_name = "seisbenchB/phasenet_volcan_v2.pt" if not START_FROM_ZERO else LOCAL_MODEL_PATH
        else:
            save_name = "seisbench/phasenet_volcan_v2.pt" if not START_FROM_ZERO else LOCAL_MODEL_PATH
        
        dossier_parent = os.path.dirname(save_name)
        if dossier_parent != "":
            os.makedirs(dossier_parent, exist_ok=True)
            
        torch.save(model.state_dict(), save_name)
        print(f"  -> Nouveau meilleur modèle")
    else:
        patience_counter += 1
        if patience_counter >= PATIENCE:
            print(f"Arrêt car pas d'amélioration depuis {PATIENCE} Epoche \nFin au bout de {epoch} EPOCHE\n")
            break

#sauvegarde pour affichage graphique
df_history = pd.DataFrame(training_history)
df_history.to_csv(history_file, index=False)
print(f"Historique d'entraînement sauvegardé sous : {history_file}")

print("\nEntraînement terminé avec succès.")