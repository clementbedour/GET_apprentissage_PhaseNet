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
EXISTING_METADATA_CSV = os.path.join(BASE_DIR, "seisbenchD/seisbench_format/metadata.csv") 


BASE_MSEED ="/get/ggs/clov/mseed_data/martinique"
MSEED_DIR = os.path.join(BASE_MSEED, "MQ")

#BASE_MSEED ="../data"
#MSEED_DIR = os.path.join(BASE_MSEED, "2014/MQ")

OUTPUT_DIR = os.path.join(BASE_DIR, "seisbenchD/seisbench_format_noise")
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
max_attempts = NBR_NOISE_PER_STATION * 50 #nbr de trace total pour trouver le bruit (contrainte de boucle)


# Paramètres STA/LTA
STA_SEC = 1.0
LTA_SEC = 10.0
STA_LTA_THRESHOLD = 1.60 #pas en dessous de 1.6

# --- PARAMÈTRES FILTRE ---
FREQ_MIN = 3.0
FREQ_MAX = 20.0
FILTER_MARGIN_SEC = 10.0  #marge ajoute pour effet de bord



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
        
        #extraire metadata
        stat_info = df_metadata[df_metadata['station_code'] == stat].iloc[0]
        
        #conversion en timestamps
        events_timestamps = np.array([ev.timestamp for ev in known_events_by_station[stat]])
        
        search_pattern = os.path.join(stat_folder, f"*{YEAR}*")
        mseed_files_available = glob.glob(search_pattern)
        
        if not mseed_files_available:
            rejections["pas_de_fichier"] += 1
            continue

        noise_extracted = 0
        attempts = 0
        #augmenter si on a pas récupéré assez de bruit (dépend des params STA/LTA)
        
        while noise_extracted < NBR_NOISE_PER_STATION and attempts < max_attempts:
            attempts += 1
            random_file = random.choice(mseed_files_available)
            
            try:
                st_head = obspy.read(random_file, headonly=True)
                file_start = st_head[0].stats.starttime
                file_end = st_head[-1].stats.endtime
            except Exception:
                rejections["erreur_lecture_header"] += 1
                continue
            
            if (file_end - file_start) < WINDOW_LENGTH_SEC:
                rejections["fichier_trop_court"] += 1
                continue
                
            max_start = file_end - WINDOW_LENGTH_SEC
            random_offset = random.uniform(0, max_start - file_start)
            t_start = file_start + random_offset
            t_end = t_start + WINDOW_LENGTH_SEC
            
            #on verifie que l'événement est pas à 300 sec d'un pointé (pour la sécu)
            if len(events_timestamps) > 0:
                time_diffs = np.abs(events_timestamps - t_start.timestamp)
                #fenêtre aléatoire pas loin d'un pointé donc on sort
                if np.any(time_diffs < SAFE_MARGIN_SEC):
                    rejections["proche_evenement_connu"] += 1
                    continue
                
            try:
                #ajout et soustrait marge lors de la lecture
                read_start = t_start - FILTER_MARGIN_SEC
                read_end = t_end + FILTER_MARGIN_SEC
                st = obspy.read(random_file, starttime=read_start, endtime=read_end)
            except Exception:
                rejections["erreur_lecture_donnees"] += 1
                continue
            
            if len(st) == 0:
                rejections["lecture_vide"] += 1
                continue
                
            try:
                st.merge(method=1)
                if any(np.ma.is_masked(tr.data) for tr in st):
                    rejections["gaps"] += 1
                    continue
                    
                st.detrend("linear")
                
            except Exception:
                rejections["erreur_traitement"] += 1
                continue

            #on verif que la taille est correcte
            if (st[0].stats.endtime - st[0].stats.starttime) < (WINDOW_LENGTH_SEC - 1):
                rejections["duree_insuffisante"] += 1
                continue

            #filtre bande passante
            filter_error = False
            for tr in st:
                #force 100 Hz si pas ok
                if tr.stats.sampling_rate != 100.0:
                    try:
                        tr.interpolate(100.0)
                    except Exception:
                        tr.resample(100.0)

                nyquist = tr.stats.sampling_rate / 2.0
                safe_freq_max = min(FREQ_MAX, nyquist - 0.1)

                #rejette si pas bon
                if safe_freq_max <= FREQ_MIN:
                    filter_error = True
                    break
                else:
                    tr.filter("bandpass", freqmin=FREQ_MIN, freqmax=safe_freq_max)

            if filter_error:
                rejections["filtre_nyquist"] += 1
                continue

            #troncature AVANT analyse STA/LTA
            st.trim(starttime=t_start, endtime=t_end)
            # --- VÉRIFICATION STA/LTA ---
            is_pure_noise = True
            for tr in st:
                if np.std(tr.data) < 1e-12:
                    is_pure_noise = False
                    break

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
            
            # --- FINALISATION ---
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
            except Exception:
                rejections["erreur_stream_array"] += 1
                continue
            
            rand = random.random()
            if rand < 0.8: split = "train"
            elif rand < 0.9: split = "dev"
            else: split = "test"
            
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
                "split": split,
                "name": "noise"
            }
            
            #on ajoute la trace et +1 car enfin fini
            writer.add_trace(trace_metadata, data_array)
            noise_extracted += 1
            
        print(f"  -> Station {stat} : {noise_extracted} fenêtres de bruit pur ajoutées (en {attempts} tentatives).")

print("\nExtraction du bruit terminée avec succès !!!")
print(f"     Détail des rejets : {dict(rejections)}")