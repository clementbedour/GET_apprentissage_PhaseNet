# =============================================
# PATCH POUR EQTRANSFORMER (À PLACER TOUT EN HAUT)
# =============================================
import sys
import keras.utils
import numpy as np
import warnings

# Fix missing multi_gpu_model in Keras
if not hasattr(keras.utils, 'multi_gpu_model'):
    keras.utils.multi_gpu_model = lambda model, gpus: model

# Fix missing np.warnings in newer NumPy
if not hasattr(np, 'warnings'):
    np.warnings = warnings
# -----------------------------------------------------------------

# 3. Forcer le patch pour les sous-modules
import tensorflow as tf
if hasattr(tf.keras, 'utils') and not hasattr(tf.keras.utils, 'multi_gpu_model'):
    tf.keras.utils.multi_gpu_model = lambda model, gpus: model

import os
import json
import random
import pandas as pd
from pathlib import Path

import obspy
from obspy import UTCDateTime

print("[DEBUG] Interpréteur :", sys.executable)
assert "phasenet" in str(sys.executable), "Mauvais interpréteur !"

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION — adaptez ces chemins à votre arborescence
# ──────────────────────────────────────────────────────────────────────────────
CFG = {
    # Entrées
    "mseed_dir"       : "../data/2014/MQ",
    "csv_dir"         : "../data/csv",
    "picks_dir"       : "../data/phase_snuffler",

    # Sorties intermédiaires
    "stations_json"   : "../data/stations.json",
    "hdf5_dir"        : "../data/hdf5_eqt",       # produit par preprocessor
    "npz_dir"         : "../data/npz_dataset",    # fenêtres découpées pour training
    "model_dir"       : "../data/models",         # modèle pré-entraîné + fine-tuné

    # Détection
    "detection_dir"   : "../data/detections",

    # Fenêtre autour du pick (secondes)
    "window_before_s" : 10,
    "window_after_s"  : 50,   # → fenêtre totale 60s = 6000 samples à 100 Hz

    # Split train/dev
    "train_ratio"     : 0.85,
}

def generate_stations_json():
    print("\n[1/3] Génération de stations.json...")
    csv_dir = Path(CFG["csv_dir"])
    stations = {}

    for file in csv_dir.glob("*.csv"):
        try:
            df = pd.read_csv(file, delimiter='|', comment='#')
            for _, row in df.iterrows():
                net = str(row['Network']).strip()
                sta = str(row['Station']).strip()
                channels = _detect_channels(net, sta)

                stations[sta] = {
                    "network" : net,
                    "channels": channels,
                    "coords"  : [
                        float(row['Latitude']),
                        float(row['Longitude']),
                        float(row['Elevation'])
                    ]
                }
        except Exception as e:
            print(f"  [!] Erreur lecture {file.name} : {e}")
            continue

    out = Path(CFG["stations_json"])
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w') as f:
        json.dump(stations, f, indent=2)

    print(f"  -> {len(stations)} stations écrites dans {out}")
    return stations

def _detect_channels(net, sta):
    channels = set()
    mseed_dir = Path(CFG["mseed_dir"])
    for fp in mseed_dir.rglob("*"):
        if not fp.is_file():
            continue
        name = fp.name.upper()
        if sta.upper() not in name:
            continue
        try:
            st = obspy.read(str(fp), headonly=True)
            for tr in st:
                if tr.stats.station == sta and tr.stats.network == net:
                    channels.add(tr.stats.channel)
        except Exception:
            continue
        if channels:
            break

    if not channels:
        channels = {"EHZ", "EHN", "EHE"}
    return sorted(channels)

def make_hdf5():
    print("\n[2/3] Conversion MiniSEED → HDF5 (EQTransformer preprocessor)...")
    try:
        from EQTransformer.utils.hdf5_maker import preprocessor, process
    except ImportError:
        print("  [!] EQTransformer non installé. Lancez : pip install EQTransformer")
        return

    # --- PATCH : Adapter les noms de fichiers pour EQTransformer ---
    def patched_process(file_list, *args, **kwargs):
        adapted_file_list = []
        for file_path in file_list:
            parts = os.path.basename(file_path).split('.')
            if len(parts) >= 6:
                reseau = parts[1]
                station = parts[2]
                date = f"{parts[4]}.{parts[5]}"  # 2014.051
                dirname = os.path.dirname(file_path)
                new_name = f"{reseau}__{station}__{date}.mseed"
                adapted_file_list.append(os.path.join(dirname, new_name))
            else:
                adapted_file_list.append(file_path)
        return process(adapted_file_list, *args, **kwargs)

    import EQTransformer.utils.hdf5_maker as hdf5_maker_module
    hdf5_maker_module.process = patched_process
    # --- Fin du patch ---

    hdf5_dir = Path(CFG["hdf5_dir"])
    hdf5_dir.mkdir(parents=True, exist_ok=True)

    preprocessor(
        preproc_dir   = str(hdf5_dir),
        mseed_dir     = CFG["mseed_dir"],
        stations_json = CFG["stations_json"],
        overlap       = 0.3,
        n_processor   = 2,
    )
    print(f"  -> HDF5 généré dans {hdf5_dir}")

def load_snuffler_picks():
    picks = {}
    path = Path(CFG["picks_dir"])
    files = list(path.glob("*")) if path.is_dir() else [path]

    print("  Chargement des pointés Snuffler...")
    for file_path in files:
        if not file_path.is_file():
            continue
        suffix = file_path.name.rsplit('_', 1)[-1].lower()
        if suffix.startswith('d'):
            continue

        with open(file_path, 'r') as f:
            for line in f:
                if not line.startswith("phase:"):
                    continue
                parts = line.strip().split()
                if len(parts) < 9:
                    continue

                nslc       = parts[4]
                phase_name = parts[8]
                nslc_parts = nslc.split('.')
                if len(nslc_parts) < 2:
                    continue

                clean_phase = (
                    'P' if phase_name.upper() == 'P'
                    else 'S' if phase_name.upper() == 'S'
                    else None
                )
                if not clean_phase:
                    continue

                try:
                    pick_time = UTCDateTime(f"{parts[1]} {parts[2]}")
                    net, sta  = nslc_parts[0], nslc_parts[1]
                    key       = (net, sta, pick_time.date)
                    picks.setdefault(key, {})[clean_phase] = pick_time
                except Exception:
                    continue

    print(f"  -> {len(picks)} couples station/jour chargés.")
    return picks

def make_npz_dataset():
    print("\n[3/3] Génération du dataset NPZ pour fine-tuning...")
    snuffler_picks = load_snuffler_picks()
    npz_dir        = Path(CFG["npz_dir"])
    mseed_dir      = Path(CFG["mseed_dir"])
    wb             = CFG["window_before_s"]
    wa             = CFG["window_after_s"]

    for split in ["train", "dev"]:
        (npz_dir / split).mkdir(parents=True, exist_ok=True)

    print("  Indexation MiniSEED...")
    files_by_day = {}
    for fp in mseed_dir.rglob("*"):
        if not fp.is_file():
            continue
        try:
            for tr in obspy.read(str(fp), headonly=True):
                day = tr.stats.starttime.date
                files_by_day.setdefault(day, set()).add(fp)
        except Exception:
            continue
    print(f"  -> {len(files_by_day)} jours indexés.")

    random.seed(42)
    event_count = 0

    # ---------------------------------------------------------
    # GÉNÉRATION DES ÉVÉNEMENTS
    # ---------------------------------------------------------
    for (net, sta, day), day_picks in sorted(snuffler_picks.items()):
        if not day_picks:
            continue

        first_pick      = min(day_picks.values())
        t_start         = first_pick - wb
        t_end           = first_pick + wa
        candidate_files = files_by_day.get(day, set())
        if not candidate_files:
            continue

        st = obspy.Stream()
        for fp in candidate_files:
            try:
                st += obspy.read(str(fp), starttime=t_start, endtime=t_end)
            except Exception:
                continue
        if not st:
            continue

        st.merge(method=1, fill_value=0)
        for tr in st:
            if hasattr(tr.data, 'filled'):
                tr.data = tr.data.filled(0).astype(np.float32)

        st = st.select(network=net, station=sta)
        if not st:
            continue

        sr          = st[0].stats.sampling_rate
        target_npts = int((wb + wa) * sr)
        data = _stream_to_3c_array(st, target_npts)
        if data is None:
            continue

        actual_start = st[0].stats.starttime
        p_idx = int((day_picks['P'] - actual_start) * sr) if 'P' in day_picks else -1
        s_idx = int((day_picks['S'] - actual_start) * sr) if 'S' in day_picks else -1

        if p_idx < 0 or p_idx >= target_npts: p_idx = -1
        if s_idx < 0 or s_idx >= target_npts: s_idx = -1
        if p_idx == -1 and s_idx == -1: continue

        split      = "train" if random.random() < CFG["train_ratio"] else "dev"
        fname      = f"{net}_{sta}_{day.strftime('%Y%m%d')}_{int(first_pick.timestamp)}.npz"
        out_path   = npz_dir / split / fname

        np.savez(
            out_path,
            data  = data.astype(np.float32),
            p_idx = np.array([p_idx], dtype=np.int32),
            s_idx = np.array([s_idx], dtype=np.int32),
            sr    = np.array([sr], dtype=np.float32),
            net   = net,
            sta   = sta,
        )
        event_count += 1

    print(f"  -> {event_count} événements écrits dans {npz_dir}")

def _stream_to_3c_array(st, target_npts):
    unique = {}
    for tr in st:
        comp = tr.stats.channel[-1].upper()
        if comp not in unique or tr.stats.npts > unique[comp].stats.npts:
            unique[comp] = tr
    if not unique:
        return None
    data = np.zeros((3, target_npts), dtype=np.float32)
    for i, comp in enumerate(['Z', 'N', 'E']):
        if comp in unique:
            arr = unique[comp].data.astype(np.float32)
            n   = min(len(arr), target_npts)
            data[i, :n] = arr[:n]
    return data

if __name__ == "__main__":
    generate_stations_json()
    make_hdf5()
    make_npz_dataset()
    print("\n[INFO] Étape de préparation des données terminée avec succès !")