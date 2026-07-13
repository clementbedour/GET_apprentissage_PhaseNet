import argparse
import urllib.request
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION — Doit correspondre au fichier de préparation
# ──────────────────────────────────────────────────────────────────────────────
CFG = {
    "mseed_dir"           : "../data/2014/MQ",
    "stations_json"       : "../data/stations.json",
    "npz_dir"             : "../data/npz_dataset",
    "model_dir"           : "../data/models",
    "detection_dir"       : "../data/detections",
    
    # Entraînement
    "epochs"              : 200,
    "batch_size"          : 32,
    "patience"            : 12,

    # Seuils de détection
    "detection_threshold" : 0.3,
    "P_threshold"         : 0.1,
    "S_threshold"         : 0.1,
}

def download_pretrained():
    print("\n[1/3] Téléchargement du modèle pré-entraîné EQTransformer...")
    model_dir = Path(CFG["model_dir"])
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "EqT_model.h5"

    if model_path.exists():
        print(f"  -> Modèle déjà présent : {model_path}")
        return

    url = "https://raw.githubusercontent.com/smousavi05/EQTransformer/master/EQTransformer/utils/EqT_model.h5"
    print(f"  Téléchargement depuis {url}...")
    try:
        urllib.request.urlretrieve(url, model_path)
        print(f"  -> Modèle sauvegardé : {model_path}")
    except Exception as e:
        print(f"  [!] Échec du téléchargement : {e}")

def train():
    print("\n[2/3] Fine-tuning EQTransformer...")
    try:
        from EQTransformer.core.trainer import trainer
    except ImportError:
        print("  [!] EQTransformer non installé.")
        return

    npz_dir   = Path(CFG["npz_dir"])
    model_dir = Path(CFG["model_dir"])

    train_files = list((npz_dir / "train").glob("*.npz"))
    if not train_files:
        print("  [!] Aucun fichier NPZ trouvé. Exécutez d'abord le script de préparation.")
        return

    trainer(
        input_hdf5        = None,                           # Utilise le dataset NPZ fenêtré
        input_trainset    = str(npz_dir / "train"),
        input_devset      = str(npz_dir / "dev"),
        input_testset     = str(npz_dir / "dev"),
        output_name       = "EqT_MQ_finetuned",
        output_dir        = str(model_dir),
        pretrained_model  = str(model_dir / "EqT_model.h5"),
        loss_weights      = [0.05, 0.40, 0.55],
        loss_types        = ['binary_crossentropy'] * 3,
        train_valid_test  = [0.85, 0.10, 0.05],
        mode              = 'transfer',                     # Mode Fine-tuning / Transfer Learning
        epochs            = CFG["epochs"],
        batch_size        = CFG["batch_size"],
        patience          = CFG["patience"],
        gpuid             = None,                           # Mettez 0 si vous avez un GPU
        gpu_limit         = 0.5,
    )
    print(f"  -> Modèle fine-tuné sauvegardé dans {model_dir}/EqT_MQ_finetuned/")

def detect():
    print("\n[3/3] Détection sur les données MiniSEED...")
    try:
        from EQTransformer.core.mseed_predictor import mseed_predictor
    except ImportError:
        print("  [!] EQTransformer non installé.")
        return

    model_dir     = Path(CFG["model_dir"])
    detection_dir = Path(CFG["detection_dir"])
    detection_dir.mkdir(parents=True, exist_ok=True)

    finetuned = list(model_dir.rglob("*.h5"))
    finetuned = [f for f in finetuned if "finetuned" in f.name or "MQ" in f.name]
    model_path = str(finetuned[0]) if finetuned else str(model_dir / "EqT_model.h5")
    print(f"  Modèle utilisé : {model_path}")

    mseed_predictor(
        input_dir            = CFG["mseed_dir"],
        input_model          = model_path,
        stations_json        = CFG["stations_json"],
        output_dir           = str(detection_dir),
        detection_threshold  = CFG["detection_threshold"],
        P_threshold          = CFG["P_threshold"],
        S_threshold          = CFG["S_threshold"],
        number_of_plots      = 10,
        plot_mode            = 'time_frequency',
        overlap              = 0.3,
        gpuid                = None,
        gpu_limit            = 0.5,
    )
    print(f"  -> Détections sauvegardées dans {detection_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EQTransformer - Entraînement et Détection")
    parser.add_argument("--action", choices=["all", "train", "detect"], default="all", help="Action à exécuter")
    args = parser.parse_args()

    download_pretrained()
    
    if args.action in ["all", "train"]:
        train()
    if args.action in ["all", "detect"]:
        detect()
