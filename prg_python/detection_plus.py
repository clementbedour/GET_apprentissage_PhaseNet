import os
import glob
import gc
import numpy as np
import torch
import obspy
import pandas as pd
import seisbench.models as sbm
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Thread, Lock

# ------------ PARAMÈTRES ------------
BASE_DIR = "../data"
MODEL_PATH = "seisbench/phasenet_volcan_v1.pt"
BASE_OUT = "../data/seisbench/seisbench_nouv"
os.makedirs(BASE_OUT, exist_ok=True)

# Fichiers sortie CSV
OUTPUT_CSV = os.path.join(BASE_OUT, "catalogue_vt_detectes.csv")
OUTPUT_EVENTS_CSV = os.path.join(BASE_OUT, "catalogue_vt_detectes_evenements_valides.csv")

BASE_MSEED = "/get/ggs/clov/mseed_data/martinique"
MSEED_DIR = os.path.join(BASE_MSEED, "MQ")

# Valeurs de détection
THRESHOLD_P = 0.95
THRESHOLD_S = 0.95

# Filtre
FREQ_MIN = 3.0
FREQ_MAX = 15.0

START_DAY = 51
END_DAY = 151
YEAR = 2014

EXPECTED_COMPONENTS = {"Z", "N", "E"}
MIN_GAP_SECONDS = 1.0
STATIONS_MONO = {"BAM", "CPM", "GBM", "MLM"}

# Params association
ASSOCIATION_WINDOW_SECONDS = 5.0
MIN_STATIONS = 4          
MIN_PROBA_EVENT = 0.85    

# Optimisations matérielles
MAX_CPU_THREADS = 24       # Réservation de cœurs pour la lecture/filtrage
QUEUE_BUFFER_SIZE = 40     # Stockage tampon en RAM pour alimenter les 2 GPUs
BATCH_SIZE_INFERENCE = 2048 # Exploitation massive des 96 Go de VRAM par H100

# Optimisation PyTorch pour les H100
torch.backends.cudnn.benchmark = True 

# ------------ FONCTIONS DE PRÉPARATION CPU ------------

def preparer_station(stat, mseed_files, freq_min, freq_max, stations_mono, expected_comp):
    """ Exécuté par les threads CPU : lecture, fusion, filtrage ObsPy. """
    try:
        st = obspy.Stream()
        for f in mseed_files:
            st += obspy.read(f)
            
        if len(st) == 0:
            return None, stat, None
            
        st.merge(method=1, fill_value=0) 
        
        for tr in st:
            tr.detrend("linear") 
            nyquist = tr.stats.sampling_rate / 2.0 
            safe_freq_max = min(freq_max, nyquist - 0.1) 
            tr.filter("bandpass", freqmin=freq_min, freqmax=safe_freq_max) 
        
        existing_components = list(set([tr.stats.channel[-1] for tr in st]))
        if stat in stations_mono or len(existing_components) < 3:
            ref_comp = "Z" if "Z" in existing_components else existing_components[0] 
            traces_modeles = st.select(component=ref_comp) 
            for comp in expected_comp:
                if comp not in existing_components: 
                    for tr in traces_modeles:
                        tr_vide = tr.copy()
                        tr_vide.stats.channel = tr.stats.channel[:-1] + comp
                        tr_vide.data = np.zeros_like(tr.data)
                        st.append(tr_vide)
                        
        st.sort() 
        return st, stat, None
        
    except Exception as e:
        return None, stat, str(e)

def producteur_cpu(queue_donnees):
    """ Thread d'arrière-plan alimentant la file d'attente. """
    with ThreadPoolExecutor(max_workers=MAX_CPU_THREADS) as executor:
        for julian_day in range(START_DAY, END_DAY + 1):
            taches_du_jour = []
            for stat_folder in glob.glob(os.path.join(MSEED_DIR, "*")): 
                stat = os.path.basename(stat_folder) 
                search_pattern = os.path.join(stat_folder, f"*{YEAR}*{julian_day}*") 
                mseed_files = glob.glob(search_pattern)
                
                if mseed_files:
                    taches_du_jour.append((stat, mseed_files))

            if not taches_du_jour:
                continue

            futures = [
                executor.submit(preparer_station, stat, files, FREQ_MIN, FREQ_MAX, STATIONS_MONO, EXPECTED_COMPONENTS) 
                for stat, files in taches_du_jour
            ]

            for future in futures:
                st, stat, erreur = future.result()
                if erreur:
                    print(f"  [CPU] Erreur prépa station {stat} : {erreur}")
                    continue
                if st is not None and len(st) > 0:
                    queue_donnees.put((julian_day, stat, st))

    # Signal de fin de transmission pour les DEUX threads GPU
    queue_donnees.put(None)
    queue_donnees.put(None)

# ------------ FONCTION CONSOMMATEUR GPU (MULTI-THREAD) ------------

def consommateur_gpu(gpu_id, queue_donnees, resultats_dict, lock_resultats):
    """ Thread dédié à un GPU spécifique qui dépile la file d'attente. """
    device_name = f"cuda:{gpu_id}"
    device = torch.device(device_name if torch.cuda.is_available() else "cpu")
    
    print(f"[{device_name}] Initialisation du modèle...")
    model = sbm.PhaseNet() 
    model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
    model.to(device)
    model.eval()

    while True:
        item = queue_donnees.get()
        if item is None:
            break # Fin du traitement pour ce GPU

        julian_day, stat, st = item

        try:
            output = model.classify(
                st, 
                P_threshold=THRESHOLD_P, 
                S_threshold=THRESHOLD_S,
                batch_size=BATCH_SIZE_INFERENCE
            )
            
            picks = list(getattr(output, "picks", output)) 
            picks = sorted(picks, key=lambda x: x.peak_time) 
            dernier_temps_P = None
            picks_valides = []
            
            for pick in picks:
                if pick.phase == "P": 
                    dernier_temps_P = pick.peak_time
                    picks_valides.append(pick)
                elif pick.phase == "S":
                    if stat in STATIONS_MONO: 
                        continue
                    if dernier_temps_P and 0 < (pick.peak_time - dernier_temps_P) <= 5.0: 
                        picks_valides.append(pick)
            
            # Formater les résultats
            resultats_formates = [{
                "day": julian_day, "station": stat, "phase": pick.phase,
                "time": pick.peak_time.isoformat(), "probability": pick.peak_value
            } for pick in picks_valides]

            # Écriture sécurisée dans le dictionnaire partagé
            with lock_resultats:
                if julian_day not in resultats_dict:
                    resultats_dict[julian_day] = []
                resultats_dict[julian_day].extend(resultats_formates)
            
            if picks_valides:
                print(f"  [{device_name}] Jour {julian_day} - Station {stat} : {len(picks_valides)} phases VT.") 

        except Exception as e:
            print(f"  [{device_name}] Erreur inférence station {stat} : {e}")
            
        finally:
            del st
            if 'output' in locals():
                del output
            # Indique à la Queue que la tâche est terminée
            queue_donnees.task_done()

# ------------ FONCTIONS POST-TRAITEMENT ------------

def dedupliquer_picks(df, min_gap_seconds=MIN_GAP_SECONDS):
    if df.empty: return df
    df = df.copy()
    df["time"] = pd.to_datetime(df["time"], format="ISO8601")
    resultats = []
    
    for (station, phase), groupe in df.groupby(["station", "phase"]):
        groupe = groupe.sort_values("time").reset_index(drop=True)
        garde = []
        dernier_temps_garde = None
        
        for _, row in groupe.iterrows():
            if dernier_temps_garde is None or (row["time"] - dernier_temps_garde).total_seconds() > min_gap_seconds:
                garde.append(row)
                dernier_temps_garde = row["time"]
            else:
                if row["probability"] > garde[-1]["probability"]:
                    garde[-1] = row
                    dernier_temps_garde = row["time"]
        resultats.extend(garde)
    
    df_dedup = pd.DataFrame(resultats).sort_values(["station", "time"]).reset_index(drop=True)
    df_dedup["time"] = df_dedup["time"].apply(lambda t: t.isoformat())
    return df_dedup

def associer_evenements(df, fenetre_secondes=ASSOCIATION_WINDOW_SECONDS, min_stations=MIN_STATIONS):
    df = df.copy()
    df["time"] = pd.to_datetime(df["time"], format="ISO8601")
    df = df[df["phase"] == "P"]
    
    if df.empty: 
        return pd.DataFrame(columns=["time_debut", "time_fin", "n_stations", "stations", "n_picks", "probabilite_max"])
    
    df = df.sort_values("time").reset_index(drop=True) 
    evenements = [] 
    cluster_courant = [df.iloc[0]] 
    
    def finaliser(cluster):
        stations_impliquees = set(r["station"] for r in cluster) 
        if len(stations_impliquees) >= min_stations: 
            evenements.append({
                "time_debut": cluster[0]["time"],
                "time_fin": cluster[-1]["time"],
                "n_stations": len(stations_impliquees),
                "stations": ",".join(sorted(stations_impliquees)),
                "n_picks": len(cluster),
                "probabilite_max": max(r["probability"] for r in cluster),
            })
    
    for _, row in df.iloc[1:].iterrows(): 
        delta = (row["time"] - cluster_courant[-1]["time"]).total_seconds() 
        if delta <= fenetre_secondes: 
            cluster_courant.append(row)
        else: 
            finaliser(cluster_courant) 
            cluster_courant = [row] 
    finaliser(cluster_courant) 
    
    df_evenements = pd.DataFrame(evenements)
    if not df_evenements.empty: 
        df_evenements["time_debut"] = df_evenements["time_debut"].apply(lambda t: t.isoformat())
        df_evenements["time_fin"] = df_evenements["time_fin"].apply(lambda t: t.isoformat())
    
    return df_evenements

# ------------ SCRIPT PRINCIPAL ------------
if __name__ == "__main__":
    print(f"--- DÉMARRAGE PIPELINE MULTI-GPU H100 ---")
    
    queue_donnees = Queue(maxsize=QUEUE_BUFFER_SIZE)
    detections_par_jour = {}
    lock_resultats = Lock()

    # 1. Lancement du Producteur CPU
    print(f"Démarrage des threads CPU ({MAX_CPU_THREADS} workers)...")
    thread_cpu = Thread(target=producteur_cpu, args=(queue_donnees,))
    thread_cpu.start()

    # 2. Lancement des Consommateurs GPU (1 Thread par carte physique)
    num_gpus = torch.cuda.device_count() if torch.cuda.is_available() else 1
    gpu_threads = []
    
    print(f"Démarrage de {num_gpus} thread(s) GPU...")
    for i in range(num_gpus):
        t = Thread(target=consommateur_gpu, args=(i, queue_donnees, detections_par_jour, lock_resultats))
        t.start()
        gpu_threads.append(t)

    # 3. Attente de la fin de tous les traitements
    thread_cpu.join()
    for t in gpu_threads:
        t.join()

    print("\n--- Inférence terminée. Assemblage et association ---")
    
    toutes_les_detections = []
    tous_les_evenements = []

    # Tri pour s'assurer que les jours sont traités dans l'ordre chronologique
    for julian_day in sorted(detections_par_jour.keys()):
        detections_du_jour = detections_par_jour[julian_day]
        if detections_du_jour:
            toutes_les_detections.extend(detections_du_jour)
            df_jour = pd.DataFrame(detections_du_jour) 
            df_jour_dedup = dedupliquer_picks(df_jour) 
            df_evenements = associer_evenements(df_jour_dedup, min_stations=MIN_STATIONS) 
            print(f"=== Bilan Jour {julian_day} : {len(df_jour_dedup)} phases -> {len(df_evenements)} évènements ===") 
            
            if not df_evenements.empty:
                tous_les_evenements.append(df_evenements)

    print("\n--- Sauvegarde des catalogues ---")

    if toutes_les_detections:
        df_picks_total = pd.DataFrame(toutes_les_detections)
        df_picks_total.to_csv(OUTPUT_CSV, index=False)
        print(f"Détections brutes sauvegardées ({len(df_picks_total)} picks) : {OUTPUT_CSV}")

    if tous_les_evenements:
        df_events_total = pd.concat(tous_les_evenements, ignore_index=True)
        masque_strict = df_events_total["probabilite_max"] >= MIN_PROBA_EVENT
        df_events_valides = df_events_total[masque_strict].reset_index(drop=True)
        
        df_events_valides.to_csv(OUTPUT_EVENTS_CSV, index=False)
        print(f"Événements valides sauvegardés ({len(df_events_valides)} événements) : {OUTPUT_EVENTS_CSV}")