import pandas as pd
import matplotlib.pyplot as plt
import os
import sys

# ------------ ARGUMENTS ------------
if len(sys.argv) < 3:
    print("Erreur : Il manque des arguments. Utilisation : python metrics.py (1|2) (VT|LPVT)")
    sys.exit(1)

mode_entrainement = int(sys.argv[1])
qualite = sys.argv[2].upper()

BASE_DIR = "../data"
IMAGE_DIR = "../images"
DOSSIER_QUALITE = "volpick"

#path pour lire les data
path_folder_data = os.path.join(BASE_DIR, DOSSIER_QUALITE)
mode_str_file = "scratch" if mode_entrainement == 1 else "finetuning"

filepath = os.path.join(path_folder_data, f"loss_history_{qualite}_{mode_str_file}.csv")

if not os.path.exists(filepath):
    print(f"Erreur : Le fichier {filepath} n'existe pas.")
    sys.exit(1)

#load data
df = pd.read_csv(filepath)

#creation figure
plt.figure(figsize=(10, 6))

plt.plot(df["epoch"], df["train_loss"], label="Train Loss", color="blue", linewidth=2)
plt.plot(df["epoch"], df["val_loss"], label="Validation Loss", color="red", linewidth=2, linestyle="--")

mode_str = "Fine-Tuning" if mode_entrainement == 2 else "Depuis Zéro"
plt.title(f"Évolution de la perte - Qualité {qualite.upper()} ({mode_str})", fontsize=14, fontweight="bold")
plt.xlabel("Époque", fontsize=12)
plt.ylabel("Loss (Cross Entropy)", fontsize=12)
plt.grid(True, linestyle=":", alpha=0.7)
plt.legend(fontsize=12)

plt.tight_layout()


image_name = f"loss_curve_{qualite}_{mode_str_file}.png"

#path vers dossier images
path_folder_images = os.path.join(IMAGE_DIR, DOSSIER_QUALITE, qualite)

#repertoire existe ou pas
os.makedirs(path_folder_images, exist_ok=True)

#save figure
image_path = os.path.join(path_folder_images, image_name)
plt.savefig(image_path, dpi=300)
print(f"\n-> Graphique Train et Val loss sauvegardé avec succès sous : {image_path}")
#plt.show()