import os
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import seisbench.data as sbd
import seisbench.models as sbm
import seisbench.generate as sbg



#------------PARAMETRES--------------------

# FROM SCRATCH
#DATASET_DIR = "../data/seisbench/seisbench_dataset"
#START_FROM_ZERO = True  

# PAS FROM SCRATCH
DATASET_DIR = "../data/seisbench/seisbench_dataset_ultime"
START_FROM_ZERO = False  


BATCH_SIZE = 32
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Le chemin du modèle local qu'on va sauvegarder ou charger
LOCAL_MODEL_PATH = "seisbench/phasenet_volcan_v1.pt"

if START_FROM_ZERO:
    EPOCHS = 30
    LEARNING_RATE = 1e-4
    SIGMA=50
    print("Mode : Entraînement DE ZÉRO")
else:
    EPOCHS = 15           # Moins d'époques nécessaires car Fine-Tuning
    LEARNING_RATE = 5e-5
    SIGMA = 30
    print(f"Mode : FINE-TUNING LOCAL depuis {LOCAL_MODEL_PATH}")

# chargement des données
dataset = sbd.WaveformDataset(DATASET_DIR, component_order="ZNE", sampling_rate=100)
train_dataset = dataset.train()
val_dataset = dataset.dev()
print(f"Succès ! Dataset chargé. Train: {len(train_dataset)} | Val: {len(val_dataset)}")

phase_dict = {
    "trace_p_arrival_sample": "P", 
    "trace_s_arrival_sample": "S"
}

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
    )
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
# on donne un poids de 2.0 pour P, 1.0 pour S, et 0.5 pour le Bruit
poids_canaux = torch.tensor([2.0, 1.0, 0.5]).view(1, 3, 1).to(DEVICE)



#calcul erreur quasratique moyenne brut
def weighted_mse_loss(pred, target):
    loss_brute = (pred - target) ** 2
    loss_ponderee = loss_brute * poids_canaux
    return loss_ponderee.mean()

# entrainement
best_val_loss = float('inf') #init à l'infini

print("\nDébut de l'entraînement")
for epoch in range(EPOCHS):
    model.train() #mode training
    train_loss = 0
    for batch in train_loader:
        X, y = batch["X"].to(DEVICE), batch["y"].to(DEVICE) #envoie signaux et cible vers DEVICE
        optimizer.zero_grad() #reset à 0
        output = model(X) #passe avant (passe la trace dans le reseau)
        loss = weighted_mse_loss(output, y) #calcul erreur globale
        loss.backward() #regarde quelle point doivent être modifié
        optimizer.step() #on les modifie
        train_loss += loss.item() * X.size(0) #calcule erreur globale
    
    model.eval() #mode eval
    val_loss = 0
    with torch.no_grad(): #pas besoin du calcul des gradients
        for batch in val_loader:
            X, y = batch["X"].to(DEVICE), batch["y"].to(DEVICE)
            val_loss += weighted_mse_loss(model(X), y).item() * X.size(0)
            
    train_loss /= len(train_dataset) #pour pour voir l'amélioration de l'entrainement
    val_loss /= len(val_dataset) # pareil mais pour la validation
    
    print(f"Époque {epoch+1:02d}/{EPOCHS} | Train Loss: {train_loss:.5f} | Val Loss: {val_loss:.5f}")
    
    
    # On sauvegarde le meilleur model si meilleur
    if val_loss < best_val_loss:
        best_val_loss = val_loss
        
        save_name = "seisbench/phasenet_volcan_v2.pt" if not START_FROM_ZERO else LOCAL_MODEL_PATH
        
        dossier_parent = os.path.dirname(save_name)
        if dossier_parent != "":
            os.makedirs(dossier_parent, exist_ok=True)
            
        torch.save(model.state_dict(), save_name)
        print(f"  -> Nouveau meilleur modèle")

print("\nEntraînement terminé avec succès.")