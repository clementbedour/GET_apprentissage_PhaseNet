import pandas as pd
import numpy as np
from pathlib import Path

def reindex_dataset(npz_dir_path):
    npz_dir = Path(npz_dir_path)
    rows = []
    # Parcourt tous les fichiers npz dans tous les sous-dossiers (train, dev, noise)
    for fp in npz_dir.rglob("*.npz"):
        try:
            d = np.load(fp, allow_pickle=True)
            split = fp.parent.name # Le nom du dossier parent (train/dev/noise)
            rows.append({
                "fname" : str(fp),
                "split" : split,
                "p_idx" : int(d["p_idx"][0]),
                "s_idx" : int(d["s_idx"][0]),
                "sr"    : float(d["sr"][0]),
            })
        except Exception as e:
            print(f"Erreur sur le fichier {fp}: {e}")
            
    df = pd.DataFrame(rows)
    df.to_csv(npz_dir / "dataset_index.csv", index=False)
    print(f"Index mis à jour avec {len(df)} fichiers dans {npz_dir / 'dataset_index.csv'}")

if __name__ == "__main__":
    reindex_dataset("../data/npz_dataset")