import os
import glob
import pandas as pd
import obspy
from obspy import UTCDateTime
import seisbench.data as sbd
from seisbench.util import stream_to_array
from collections import defaultdict
import numpy as np
from genericpath import exists
import random

#------------PARAMETRES--------------------
BASE_DIR = "../data"
STATION_CSV_DIR = os.path.join(BASE_DIR, "csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "seisbench/seisbench_format")
PICK_DIR = os.path.join(BASE_DIR, "phase_snuffler")
os.makedirs(OUTPUT_DIR, exist_ok=True)


#BASE_MSEED ="../data"
#MSEED_DIR = os.path.join(BASE_MSEED, "2014/MQ")

BASE_MSEED ="/get/ggs/clov/mseed_data/martinique"
MSEED_DIR = os.path.join(BASE_MSEED, "MQ")


# --- Fenêtre autour du pick ---
WINDOW_LENGTH_SEC = 60
PRE_PICK_MIN_SEC = 5
PRE_PICK_MAX_SEC = 55
POST_S_MARGIN_SEC = 5

GAP_ACCEPT = 1.0  # en secondes

# --- PARAMÈTRES FILTRE ---
FREQ_MIN = 3.0
FREQ_MAX = 15.0

stations_info = {}
# construction du dico station grâce au repertoire ../data/csv
for csv_file in glob.glob(os.path.join(STATION_CSV_DIR, "*.csv")):
    try:
        df_stat = pd.read_csv(csv_file, sep="|", comment="#")

        # si fichier vide on passe
        if not df_stat.empty:
            # on recup que la première ligne utile
            row = df_stat.iloc[0]
            stations_info[row['Station']] = {
                'network': row['Network'],
                'latitude': row['Latitude'],
                'longitude': row['Longitude'],
                'elevation': row['Elevation']
            }
    except Exception as e:
        print(f"Erreur avec la station {csv_file}: {e}")
print("Voici toutes les stations du dictionnaire : ", *stations_info.keys())

# Tout les pointés
all_pick_files = os.listdir(PICK_DIR)
pick_files = []

# on enleve les fichiers qui on un 'd'
for f in all_pick_files:
    files_without_d = 'd' not in f
    path_good_files = os.path.join(PICK_DIR, f)

    if files_without_d and os.path.isfile(path_good_files):
        pick_files.append(f)

print("Utilisation de", len(pick_files), "fichiers de pointé,", len(all_pick_files), "au total (avec 'd')")

pick_exctract = []
nbr_p = 0
nbr_s_solo = 0

# on aura dans pick_exctract tout les pointés de toutes les stations de tout les jours
for file in pick_files:
    full_path = os.path.join(PICK_DIR, file)

    # var pour stocker P et S de chaque station durant un même event
    # obligé de l'initialiser pour modif aprés
    pick_stat = defaultdict(lambda: {"t_p": None, "t_s": None})

    with open(full_path, 'r') as f:
        for ligne in f:
            if ligne.startswith("phase:"):
                # format fichier
                # phase: YYYY-MM-DD HH:MM:SS.FFFF 0 NET.STA.LOC.CHA None None None PHASE None False
                parts = ligne.split()
                try:
                    date_str = parts[1]
                    time_str = parts[2]
                    station = parts[4].split(".")[1]
                    phase_type = parts[8].upper()
                    timestamp = f"{date_str}T{time_str}"

                    if phase_type == 'P':
                        pick_stat[station]["t_p"] = timestamp
                    elif phase_type == 'S':
                        pick_stat[station]["t_s"] = timestamp
                except IndexError:
                    continue  # ignore les lignes mal formatés

    for station, times in pick_stat.items():
        # au cas où on est des pointés pas identifié et/ou des stations vides
        if (times["t_p"] is not None) or (times["t_s"] is not None):
            pick_exctract.append({
                "station": station,
                "t_p": times["t_p"],
                "t_s": times["t_s"]
            })
            if times["t_p"] is None:
                nbr_s_solo = 1 + nbr_s_solo
            else:
                nbr_p = 1 + nbr_p

print("Nombre de P trouvé :", nbr_p)
print("Nombre de S solo trouvé :", nbr_s_solo)


def build_random_window(t_p, t_s):
    if t_p is not None:
        ref_time = t_p

        if t_s is not None:
            #faut aussi S
            required_post = (t_s - t_p) + POST_S_MARGIN_SEC
            max_pre_pick = WINDOW_LENGTH_SEC - required_post

            if max_pre_pick < PRE_PICK_MIN_SEC:
                #si S trop loin de P on priiligie P
                pre_pick = PRE_PICK_MIN_SEC
            else:
                pre_pick = random.uniform(PRE_PICK_MIN_SEC, min(PRE_PICK_MAX_SEC, max_pre_pick))
        else:
            pre_pick = random.uniform(PRE_PICK_MIN_SEC, PRE_PICK_MAX_SEC)

    elif t_s is not None:
        ref_time = t_s
        pre_pick = random.uniform(PRE_PICK_MIN_SEC, PRE_PICK_MAX_SEC)

    else:
        return None

    post_pick = WINDOW_LENGTH_SEC - pre_pick
    start_window = ref_time - pre_pick
    end_window = ref_time + post_pick

    return start_window, end_window, ref_time.year, ref_time.julday


path_csv = os.path.join(OUTPUT_DIR, "metadata.csv")
path_hdf5 = os.path.join(OUTPUT_DIR, "waveforms.hdf5")

with sbd.WaveformDataWriter(path_csv, path_hdf5) as writer:

    writer.data_format = {
        "dimension_order": "CW",
        "measurement": "velocity",
        "unit": "counts",
    }
    nbr_pick_pass = 0
    nbr_read_fail = 0

    # boucle sur tout les pointés
    for pick in pick_exctract:
        stat = pick["station"]

        t_p = UTCDateTime(pick["t_p"]) if pick["t_p"] is not None else None
        t_s = UTCDateTime(pick["t_s"]) if pick["t_s"] is not None else None

        # anomalie physique : S ne peut pas arriver avant P
        if t_p is not None and t_s is not None and t_s <= t_p:
            print(f" Anomalie physique ignorée (S avant P) pour la station {stat}")
            t_s = None

        window = build_random_window(t_p, t_s)
        if window is None:
            continue
        start_window, end_window, year, julian_day = window

        folder_mseed = os.path.join(MSEED_DIR, stat)
        if not os.path.exists(folder_mseed):
            print(f"Attention: Dossier introuvable -> {folder_mseed}")
            continue

        # on construit le pattern voulu pour un jour précis et une station
        search_pattern = os.path.join(folder_mseed, f"*{year}*{julian_day:03d}*")
        # on cherche avec le pattern les fichiers correspondant que l'on mets dans une liste
        mseed_files = glob.glob(search_pattern)

        # si pas de fichier trouvé on pass
        if not mseed_files:
            nbr_pick_pass = 1 + nbr_pick_pass
            continue

        st = obspy.Stream()
        for f in mseed_files:
            try:
                st_temp = obspy.read(f, starttime=start_window, endtime=end_window)
                st += st_temp
            except Exception as e:
                nbr_read_fail = 1 + nbr_read_fail
                print("Erreur de lecture pour ", f, " : ", e)
                pass

        if len(st) == 0:
            continue

        # verifie s'il y a des trous (il faudrait surtout vérifier si le gap est pas pile sur P ou S)
        gaps = st.get_gaps()
        if len(gaps) > 0:
            total_gap_duration = sum(g[6] for g in gaps)
            if total_gap_duration > GAP_ACCEPT:
                continue  # on ignore ce pick, trop de data manquantes

        # merge si trace coupé en plusieurs morceaux et trous pas trop long
        st.merge(method=1)

        st.detrend("linear")

        # --- APPLICATION DU FILTRE PASSE-BANDE HOMOGÈNE ---
        for tr in st:
            nyquist = tr.stats.sampling_rate / 2.0
            safe_freq_max = min(FREQ_MAX, nyquist - 0.1)  # S'assure de rester sous Nyquist

            # Si le signal est trop pauvre pour le passe-bande, on fait un simple passe-haut
            if safe_freq_max <= FREQ_MIN :
                tr.filter("highpass", freq=FREQ_MIN)
            else:
                tr.filter("bandpass", freqmin=FREQ_MIN, freqmax=safe_freq_max)

        expected_components = ["Z", "N", "E"]
        existing_components = []
        for tr in st:
            component = tr.stats.component
            existing_components.append(component)

        # on prend la premiere trace pour copier sa fréquence, sa longueur,...
        trace_modele = st[0]

        # on regarde toutes les composantes
        for comp in expected_components:
            if comp not in existing_components:
                # trace full 0
                tr_vide = trace_modele.copy()
                tr_vide.stats.component = comp
                tr_vide.data = np.zeros_like(trace_modele.data)
                st.append(tr_vide)

        st.sort()

        # conversion du Stream Obspy en matrice NumPy, qui sera toujours (3, N)
        try:
            # on force l'ordre Z, N, E pour l'IA
            _, data_array, _ = stream_to_array(st, component_order=expected_components)
        except Exception as e:
            print("Erreur de conversion en array NumPy pour ", stat, " : ", e)
            continue

        # init données pour hdf5 et csv
        sampling_rate = st[0].stats.sampling_rate
        actual_start = st[0].stats.starttime

        p_arrival_sample = int((t_p - actual_start) * sampling_rate) if t_p else None
        s_arrival_sample = int((t_s - actual_start) * sampling_rate) if t_s else None

        # Choix du centre pour le futur fenêtrage SeisBench
        if p_arrival_sample is not None:
            center_sample = p_arrival_sample
        elif s_arrival_sample is not None:
            center_sample = s_arrival_sample
        else:
            continue

        rand = random.random()
        if rand < 0.8:
            split = "train"
        elif rand < 0.9:
            split = "dev"
        else:
            split = "test"

        s_info = stations_info.get(stat, {"network": "MQ", "latitude": None, "longitude": None, "elevation": None})
        temps_ref = t_p if t_p is not None else t_s

        trace_metadata = {
            "trace_name": f"{s_info['network']}_{stat}_{temps_ref.strftime('%Y%m%d_%H%M%S')}",
            "trace_start_time": actual_start.isoformat(),
            "station_network_code": s_info['network'],
            "station_code": stat,
            "station_latitude_deg": s_info['latitude'],
            "station_longitude_deg": s_info['longitude'],
            "station_elevation_m": s_info['elevation'],
            "trace_p_arrival_sample": p_arrival_sample,
            "trace_s_arrival_sample": s_arrival_sample,
            "center_sample": center_sample,
            "trace_sampling_rate_hz": sampling_rate,
            "trace_component_order": "ZNE",
            "split": split
        }

        writer.add_trace(trace_metadata, data_array)


print(nbr_pick_pass, "pointés ignorés faute de fichier MiniSEED correspondant.")
print(nbr_read_fail, "fichiers MiniSEED n'ont pas pu être lus (erreur ObsPy).")
print("\n Conversion terminée !")