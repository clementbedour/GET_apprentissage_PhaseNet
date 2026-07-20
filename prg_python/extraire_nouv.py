import os
import glob
import pandas as pd
import numpy as np
import obspy
from obspy import UTCDateTime
import seisbench.data as sbd
from seisbench.util import stream_to_array
import random

# ============================================================
# PARAMÈTRES ET CHEMINS
# ============================================================
BASE_DIR = "../data"
MSEED_DIR = os.path.join(BASE_DIR, "2014/MQ")

BASE_OUT = "../data/seisbench/seisbench_nouv"
PICKS_CSV = os.path.join(BASE_OUT, "catalogue_vt_detectes.csv")
EVENTS_CSV = os.path.join(BASE_OUT, "catalogue_vt_detectes_evenements_valides.csv")

OUTPUT_DATASET_DIR = os.path.join(BASE_DIR, "seisbench/seisbench_format_gold")
os.makedirs(OUTPUT_DATASET_DIR, exist_ok=True)
PATH_METADATA = os.path.join(OUTPUT_DATASET_DIR, "metadata.csv")
PATH_HDF5 = os.path.join(OUTPUT_DATASET_DIR, "waveforms.hdf5")

# Paramètres d'extraction (Fenêtre de 60 secondes centrée sur le P)
PRE_PICK_SEC = 30
POST_PICK_SEC = 30
EXPECTED_COMPONENTS = ["Z", "N", "E"]

# --- NOUVEAUX PARAMÈTRES DE FILTRAGE GOLD STANDARD ---
MIN_STATIONS = 3          # Nombre minimum de stations ayant détecté l'événement
MIN_PROBA_EVENT = 0.85    # Seuil de confiance : probabilité maximale de l'événement
FREQ_MIN = 3.0            # Filtre passe-bande
FREQ_MAX = 15.0

# ============================================================
# 1. CHARGEMENT ET FILTRAGE DES DONNÉES
# ============================================================
print("Chargement des catalogues...")
df_picks = pd.read_csv(PICKS_CSV)
df_events = pd.read_csv(EVENTS_CSV)

df_picks["time"] = pd.to_datetime(df_picks["time"], format="ISO8601")
df_events["time_debut"] = pd.to_datetime(df_events["time_debut"], format="ISO8601")
df_events["time_fin"] = pd.to_datetime(df_events["time_fin"], format="ISO8601")

# --- FILTRAGE STRICT (Stations + Probabilité) ---
masque = (df_events["n_stations"] >= MIN_STATIONS) & (df_events["probabilite_max"] >= MIN_PROBA_EVENT)
df_gold_events = df_events[masque].reset_index(drop=True)

print(f"Événements Gold Standard trouvés ({MIN_STATIONS}+ stations, proba >= {MIN_PROBA_EVENT}) : {len(df_gold_events)}")

if len(df_gold_events) == 0:
    print("Aucun événement ne correspond à ces critères stricts. Essayez de baisser le seuil. Arrêt du script.")
    exit()

# ============================================================
# 2. EXTRACTION ET CRÉATION DU DATASET SEISBENCH
# ============================================================
traces_ajoutees = 0
erreurs_lecture = 0

print(f"\nDébut de l'extraction vers {OUTPUT_DATASET_DIR}...")

with sbd.WaveformDataWriter(PATH_METADATA, PATH_HDF5) as writer:
    
    writer.data_format = {
        "dimension_order": "CW",
        "measurement": "velocity",
        "unit": "counts",
    }
    
    for index, event in df_gold_events.iterrows():
        event_start = event["time_debut"]
        event_end = event["time_fin"]
        
        mask = (df_picks["time"] >= event_start - pd.Timedelta(seconds=2)) & \
               (df_picks["time"] <= event_end + pd.Timedelta(seconds=2))
        picks_event = df_picks[mask]
        
        for stat in picks_event["station"].unique():
            picks_stat = picks_event[picks_event["station"] == stat]
            
            p_picks = picks_stat[picks_stat["phase"] == "P"]
            s_picks = picks_stat[picks_stat["phase"] == "S"]
            
            if p_picks.empty:
                continue 
                
            t_p = UTCDateTime(p_picks.iloc[0]["time"])
            t_s = UTCDateTime(s_picks.iloc[0]["time"]) if not s_picks.empty else None
            
            start_window = t_p - PRE_PICK_SEC
            end_window = t_p + POST_PICK_SEC
            year = t_p.year
            julian_day = t_p.julday
            
            search_pattern = os.path.join(MSEED_DIR, stat, f"*{year}*{julian_day:03d}*")
            mseed_files = glob.glob(search_pattern)
            
            if not mseed_files:
                continue
                
            st = obspy.Stream()
            for f in mseed_files:
                try:
                    st += obspy.read(f, starttime=start_window, endtime=end_window)
                except Exception:
                    erreurs_lecture += 1
                    pass
            
            if len(st) == 0:
                continue
                
            try:
                st.merge(method=1, fill_value=0)
                st.detrend("linear")
                # --- APPLICATION DU FILTRE PASSE-BANDE ---
                st.filter("bandpass", freqmin=FREQ_MIN, freqmax=FREQ_MAX)
            except:
                continue
                
            existing_components = [tr.stats.channel[-1] for tr in st]
            if not all(c in existing_components for c in EXPECTED_COMPONENTS):
                continue
                
            st.sort()
            
            try:
                _, data_array, _ = stream_to_array(st, component_order=EXPECTED_COMPONENTS)
            except Exception:
                continue
                
            sampling_rate = st[0].stats.sampling_rate
            actual_start = st[0].stats.starttime
            
            p_arrival_sample = int((t_p - actual_start) * sampling_rate)
            s_arrival_sample = int((t_s - actual_start) * sampling_rate) if t_s else np.nan
            center_sample = p_arrival_sample
            
            rand = random.random()
            if rand < 0.8: split = "train"
            elif rand < 0.9: split = "dev"
            else: split = "test"
            
            trace_metadata = {
                "trace_name": f"MQ_{stat}_GOLD_{t_p.strftime('%Y%m%d_%H%M%S')}",
                "station_network_code": "MQ",
                "station_code": stat,
                "trace_p_arrival_sample": p_arrival_sample,
                "trace_s_arrival_sample": s_arrival_sample,
                "center_sample": center_sample,
                "trace_sampling_rate_hz": sampling_rate,
                "trace_component_order": "ZNE",
                "split": split,
                "gold_standard": True
            }
            
            writer.add_trace(trace_metadata, data_array)
            traces_ajoutees += 1

print(f"\nMAGNIFIQUE ! Création du dataset terminée.")
print(f"-> {traces_ajoutees} traces parfaites à 3 composantes ont été sauvegardées dans {OUTPUT_DATASET_DIR}.")
if erreurs_lecture > 0:
    print(f"-> {erreurs_lecture} fichiers MiniSEED ont été ignorés (erreurs de lecture locales).")