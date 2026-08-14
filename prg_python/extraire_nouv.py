import os
import glob
import pandas as pd
import numpy as np
import obspy
from obspy import UTCDateTime
import seisbench.data as sbd
from seisbench.util import stream_to_array
import random
import sys
#------------PARAMETRES--------------------
BASE_DIR = "../data"

if len(sys.argv) > 1:
    var = sys.argv[1].lower()
    if var=='a' :
        BASE_OUT = "../data/seisbenchA/seisbench_nouv"
        OUTPUT_DATASET_DIR = os.path.join(BASE_DIR, "seisbenchA/seisbench_format_gold")
    elif var=='b' :
        BASE_OUT = "../data/seisbenchB/seisbench_nouv"
        OUTPUT_DATASET_DIR = os.path.join(BASE_DIR, "seisbenchB/seisbench_format_gold")
else :
    var = 'c'
    BASE_OUT = "../data/seisbench/seisbench_nouv"
    OUTPUT_DATASET_DIR = os.path.join(BASE_DIR, "seisbench/seisbench_format_gold")

print(f"On veux une qualité minimal de {var}")


#BASE_MSEED ="../data"
#MSEED_DIR = os.path.join(BASE_MSEED, "2014/MQ")

BASE_MSEED ="/get/ggs/clov/mseed_data/martinique"
MSEED_DIR = os.path.join(BASE_MSEED, "MQ")

PICKS_CSV = os.path.join(BASE_OUT, "catalogue_vt_detectes.csv")
EVENTS_CSV = os.path.join(BASE_OUT, "catalogue_vt_detectes_evenements_valides.csv")

os.makedirs(OUTPUT_DATASET_DIR, exist_ok=True)
PATH_METADATA = os.path.join(OUTPUT_DATASET_DIR, "metadata.csv")
PATH_HDF5 = os.path.join(OUTPUT_DATASET_DIR, "waveforms.hdf5")

OLD_DATASET_DIR = os.path.join(BASE_DIR, "seisbench/seisbench_format")
OLD_METADATA_CSV = os.path.join(OLD_DATASET_DIR, "metadata.csv")

# Paramètres d'extraction
PRE_PICK_SEC = 30
POST_PICK_SEC = 30
EXPECTED_COMPONENTS = ["Z", "N", "E"]
# --- PARAMÈTRES FILTRE ---
FREQ_MIN = 3.0
FREQ_MAX = 20.0
TMP_DUPLICATES = 5.0  # Tolérance temporelle (s)

#chargement des catalogues
print("Chargement des catalogues")
df_picks = pd.read_csv(PICKS_CSV)
df_gold_events = pd.read_csv(EVENTS_CSV)

df_picks["time"] = pd.to_datetime(df_picks["time"], format="ISO8601")
df_gold_events["time_debut"] = pd.to_datetime(df_gold_events["time_debut"], format="ISO8601")
df_gold_events["time_fin"] = pd.to_datetime(df_gold_events["time_fin"], format="ISO8601")

# --- CHARGEMENT HISTORIQUE ET CONVERSION VECTORIELLE ---
known_picks_raw = {}
known_picks_arrays = {}
total_known_traces = 0
matched_known_picks = set()

if os.path.exists(OLD_METADATA_CSV):
    print(f"Chargement de l'historique pour filtrage des doublons : {OLD_METADATA_CSV}")
    df_old = pd.read_csv(OLD_METADATA_CSV)
    df_old_p = df_old.dropna(subset=['trace_p_arrival_sample']).copy()
    
    df_old_p['start_dt'] = pd.to_datetime(df_old_p['trace_start_time'], format="ISO8601")
    df_old_p['p_time'] = df_old_p['start_dt'] + pd.to_timedelta(df_old_p['trace_p_arrival_sample'] / df_old_p['trace_sampling_rate_hz'], unit='s')
    
    total_known_traces = len(df_old_p)
        
    print(f" -> {total_known_traces} pointés existants chargés depuis la base initiale.")
else:
    print("Attention : Ancien dataset introuvable. Aucun filtrage des doublons ne sera effectué.")

print(f"{len(df_gold_events)} événements à analyser/extraire")

if len(df_gold_events) == 0:
    print("Aucun événement ne correspond à ces critères stricts") #baisser le seuil
    sys.exit()

#extraction des données
traces_ajoutees = 0
erreurs_lecture = 0

print(f"\nDébut de l'extraction vers {OUTPUT_DATASET_DIR}")

with sbd.WaveformDataWriter(PATH_METADATA, PATH_HDF5) as writer:
    
    writer.data_format = {
        "dimension_order": "CW",
        "measurement": "velocity",
        "unit": "counts",
    }
    
    for index, event in df_gold_events.iterrows():
        event_start = event["time_debut"]
        event_end = event["time_fin"]
        # On récupère les picks exacts correspondants à la fenêtre de l'événement
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
            
            # --- VERIF ANTI-DOUBLON VECTORIELLE ---
            is_duplicate = False
            if stat in known_picks_arrays and len(known_picks_arrays[stat]) > 0:
                t_p_ts = t_p.timestamp
                diffs = np.abs(known_picks_arrays[stat] - t_p_ts)
                
                if np.any(diffs < TMP_DUPLICATES):
                    is_duplicate = True
                    idx_match = np.argmin(diffs)
                    matched_known_picks.add((stat, known_picks_raw[stat][idx_match]))
            
            if is_duplicate:
                continue
            # ---------------------------------------
            
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
                #passe bande
                st.filter("bandpass", freqmin=FREQ_MIN, freqmax=FREQ_MAX)
            except Exception:
                continue
                
            #force la freq a 100 Hz
            for tr in st:
                if tr.stats.sampling_rate != 100.0:
                    try:
                        tr.interpolate(100.0)
                    except Exception:
                        tr.resample(100.0)

            # 2. Complète les composantes manquantes avec du zéro au lieu de tout jeter
            existing_components = [tr.stats.channel[-1] for tr in st]
            trace_modele = st[0]

            for comp in EXPECTED_COMPONENTS:
                if comp not in existing_components:
                    tr_vide = trace_modele.copy()
                    tr_vide.stats.channel = trace_modele.stats.channel[:-1] + comp
                    tr_vide.data = np.zeros_like(trace_modele.data)
                    st.append(tr_vide)

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
                "trace_start_time": actual_start.isoformat(),
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

nb_retrouves = len(matched_known_picks)
pct_retrouves = (nb_retrouves / total_known_traces * 100) if total_known_traces > 0 else 0.0

print(f"\nCréation du dataset terminée.")
print(f"Événements/Traces initialement connus  : {total_known_traces}")
print(f"Événements/Traces connus RETROUVÉS     : {nb_retrouves} ({pct_retrouves:.1f}%)")
print(f"-> {traces_ajoutees} traces ont été sauvegardées dans {OUTPUT_DATASET_DIR}")
if erreurs_lecture > 0:
    print(f"-> {erreurs_lecture} fichiers MiniSEED ont été ignorés erreurs de lecture")