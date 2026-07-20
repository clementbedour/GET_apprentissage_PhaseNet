import os
import glob
import pandas as pd
import obspy
from obspy import UTCDateTime
import seisbench.data as sbd
from seisbench.util import stream_to_array
import numpy as np
import random
from obspy.signal.trigger import recursive_sta_lta
from collections import Counter

#------------PARAMETRES--------------------
BASE_DIR = "../data"
MSEED_DIR = os.path.join(BASE_DIR, "2014/MQ")
EXISTING_METADATA_CSV = os.path.join(BASE_DIR, "seisbench/seisbench_format/metadata.csv") 

OUTPUT_DIR = os.path.join(BASE_DIR, "seisbench/seisbench_format_noise")
os.makedirs(OUTPUT_DIR, exist_ok=True)
path_csv = os.path.join(OUTPUT_DIR, "metadata.csv")
path_hdf5 = os.path.join(OUTPUT_DIR, "waveforms.hdf5")

START_DAY = 51
END_DAY = 151
YEAR = 2014

# Paramètres d'extraction
NBR_NOISE_PER_STATION = 100
WINDOW_LENGTH_SEC = 60
SAFE_MARGIN_SEC = 180 # voir si pointé dans les parages (3 minutes)
max_attempts = NBR_NOISE_PER_STATION * 20 #nbr de trace total pour trouver le bruit (contrainte de boucle)


# Paramètres STA/LTA
STA_SEC = 1.0
LTA_SEC = 10.0
STA_LTA_THRESHOLD = 2 #pas en dessous de 2, trop de pic

FREQ_MIN = 3.0
FREQ_MAX = 15.0



df_metadata = pd.read_csv(EXISTING_METADATA_CSV)

known_events_by_station = {}
for stat in df_metadata['station_code'].unique():
    station_traces = df_metadata[df_metadata['station_code'] == stat]
    event_times = []
    for start_time_str in station_traces['trace_start_time']:
        try:
            event_times.append(UTCDateTime(start_time_str))
        except (ValueError, TypeError) as e:
            print(f"[Station {stat}] Erreur de parsing sur '{start_time_str}': {e}")
            continue
    known_events_by_station[stat] = event_times


print(f"Début de l'extraction. Tolérance STA/LTA fixée à {STA_LTA_THRESHOLD}.")
#extraction et verification du bruit
with sbd.WaveformDataWriter(path_csv, path_hdf5) as writer:
    
    writer.data_format = {
        "dimension_order": "CW",
        "measurement": "velocity",
        "unit": "counts",
    }
    
    #on fait tout dans cette boucle 
    rejections = Counter()
    for stat_folder in glob.glob(os.path.join(MSEED_DIR, "*")):
        stat = os.path.basename(stat_folder)
        #on regarde si la station a au moins 1 événement, sinon on la sort
        if stat not in known_events_by_station:
            continue
            
        print(f"Traitement de la station {stat}")
        events_for_stat = known_events_by_station[stat]
        noise_extracted = 0
        attempts = 0
        #augmenter si on a pas récupéré assez de bruit (dépend des params STA/LTA)
        
        # on récupérer 3 000 événements aléatoire
        while noise_extracted < NBR_NOISE_PER_STATION and attempts < max_attempts:
            attempts += 1
            random_day = random.randint(START_DAY, END_DAY)
            search_pattern = os.path.join(stat_folder, f"*{YEAR}*{random_day:03d}*")
            mseed_files = glob.glob(search_pattern)
            
            #fichier mseed pas trouvé avec un jour aléatoire
            if not mseed_files:
                rejections["pas_de_fichier"] += 1
                continue
                
            random_hour = random.randint(0, 23)
            random_minute = random.randint(0, 59)
            
            #temps du fichier mseed pas trouvé (trou)
            try:
                t_start = UTCDateTime(year=YEAR, julday=random_day, hour=random_hour, minute=random_minute)
            except:
                continue
                
            t_end = t_start + WINDOW_LENGTH_SEC
            
            is_safe = True
            #on verifie que l'événement est pas à 300 sec d'un pointé (pour la sécu)
            for ev_time in events_for_stat:
                if abs(t_start - ev_time) < SAFE_MARGIN_SEC:
                    is_safe = False
                    break
            
            #fenêtre aléatoire pas loin d'un pointé donc on sort
            if not is_safe:
                rejections["proche_evenement_connu"] += 1
                continue
                
            #on lis notre fichier mseed
            st = obspy.Stream()
            for f in mseed_files:
                try:
                    st_temp = obspy.read(f, starttime=t_start, endtime=t_end)
                    st += st_temp
                except:
                    pass
            
            if len(st) == 0:
                rejections["lecture_vide"] += 1
                continue
                
            try:
                st.merge(method=1)
                
                has_gaps = False
                #si on a un trou alors on sort
                #on a tellement de data qu'on peux se permettre
                for tr in st:
                    if np.ma.is_masked(tr.data):
                        has_gaps = True
                        break
                
                if has_gaps:
                    rejections["gaps"] += 1
                    continue
                    
                st.detrend("linear")
                
            except Exception:
                continue

            #on verif que la taille est correcte
            if (st[0].stats.endtime - st[0].stats.starttime) < (WINDOW_LENGTH_SEC - 1):
                rejections["duree_insuffisante"] += 1
                continue

            # --- VÉRIFICATION STA/LTA ---
            st_test = st.copy()
            st_test.filter("bandpass", freqmin=FREQ_MIN, freqmax=FREQ_MAX)
            
            is_pure_noise = True
            for tr in st_test:
                #on converti en nbr d'echantillon
                df_rate = tr.stats.sampling_rate
                sta_len = int(STA_SEC * df_rate)
                lta_len = int(LTA_SEC * df_rate)
                
                #si trop peux de donnée (plus petit que fenêtre LTA on sort)
                if len(tr.data) <= lta_len:
                    is_pure_noise = False
                    break
                
                #la fonction qui fait tout (et merci python)
                #return un tableau donc on prend le max et on compare
                cft = recursive_sta_lta(tr.data, sta_len, lta_len)
                if np.max(cft) > STA_LTA_THRESHOLD:
                    is_pure_noise = False
                    break
            
            if not is_pure_noise:
                rejections["sta_lta"] += 1
                continue
            
            
            
            # --- FILTRAGE FINAL SUR LA DONNÉE ORIGINALE ---
            filter_error = False
            for tr in st:
                #TH de Shannon Nyquist
                nyquist = tr.stats.sampling_rate / 2.0
                safe_freq_max = min(FREQ_MAX, nyquist - 0.1)
                if safe_freq_max <= FREQ_MIN or safe_freq_max < FREQ_MAX:
                    print(f"[{stat}] Filtre non standard, fenêtre rejetée.")
                    filter_error = True
                    break
                else:
                    tr.filter("bandpass", freqmin=FREQ_MIN, freqmax=FREQ_MAX)
                
            if filter_error:
                rejections["filtre_nyquist"] += 1
                continue
            
            
            expected_components = ["Z", "N", "E"]
            existing_components = [tr.stats.component for tr in st]
            trace_modele = st[0] #on prend Z car on l'a "toujours"
            
            #si trace manquantes, alors full 0
            for comp in expected_components:
                if comp not in existing_components:
                    tr_vide = trace_modele.copy()
                    tr_vide.stats.component = comp
                    tr_vide.data = np.zeros_like(trace_modele.data)
                    st.append(tr_vide)
            
            st.sort()
                
            try:
                #convertion du Stream obspy en tableau numpy
                #on ne s'occupe pas du premier et dernier argument return, inutile
                _, data_array, _ = stream_to_array(st, component_order=expected_components)
            except:
                continue
            
            rand = random.random()
            if rand < 0.8: split = "train"
            elif rand < 0.9: split = "dev"
            else: split = "test"
            
            stat_info = df_metadata[df_metadata['station_code'] == stat].iloc[0]
            
            #construction du dico metadonnée
            trace_metadata = {
                "trace_name": f"{stat_info['station_network_code']}_{stat}_NOISE_{t_start.strftime('%Y%m%d_%H%M%S')}",
                "station_network_code": stat_info['station_network_code'],
                "station_code": stat,
                "station_latitude_deg": stat_info['station_latitude_deg'],
                "station_longitude_deg": stat_info['station_longitude_deg'],
                "station_elevation_m": stat_info['station_elevation_m'],
                "trace_p_arrival_sample": np.nan, 
                "trace_s_arrival_sample": np.nan,
                "center_sample": int((WINDOW_LENGTH_SEC / 2) * st[0].stats.sampling_rate),
                "trace_sampling_rate_hz": st[0].stats.sampling_rate,
                "trace_component_order": "ZNE",
                "split": split
            }
            
            #on ajoute la trace et +1 car enfin fini
            writer.add_trace(trace_metadata, data_array)
            noise_extracted += 1
            
        print(f"  -> Station {stat} : {noise_extracted} fenêtres de bruit pur ajoutées (en {attempts} tentatives).")

print("\nExtraction du bruit terminée avec succès !!!")
print(f"     Détail des rejets : {dict(rejections)}")