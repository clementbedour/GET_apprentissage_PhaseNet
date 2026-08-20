import gc
import os
import glob
import numpy as np
import torch
import obspy
import pandas as pd
import seisbench.models as sbm
from obspy import UTCDateTime
import sys

# ------------ PARAMÈTRES ------------
BASE_DIR = "../data"

#valeurs de détection
THRESHOLD_P = 0.90
THRESHOLD_S = 0.40

START_DAY = 51
END_DAY = 151
YEAR = 2014

EXPECTED_COMPONENTS = {"Z", "N", "E"}
MIN_GAP_SECONDS = 3.0
STATIONS_MONO = {"BAM", "CPM", "GBM", "MLM"}

#params association
ASSOCIATION_WINDOW_SECONDS = 5.0  #fenetre max entre arrive sur 2 stats
#filtre pour event
MIN_STATIONS = 4          #nbr min de stat 
MIN_PROBA_EVENT = 0.90    #score confiance minimal
MAX_EVENT_DAY = 200        #nbr d'event max par jour (aprés association)
MAX_EVENT_DURATION = 10.0 #tmp max event (pas plus de 10 sec)

# --- PARAMÈTRES FILTRE ---
FREQ_MIN = 3.0
FREQ_MAX = 20.0

if len(sys.argv) > 1:
    var = sys.argv[1].lower()
    if var=='a' :
        MODEL_PATH = "seisbenchA/ml_model_v1.pt"
        BASE_OUT = "../data/seisbenchA/seisbench_nouv"
    elif var=='b' :
        MODEL_PATH = "seisbenchB/ml_model_v1.pt"
        BASE_OUT = "../data/seisbenchB/seisbench_nouv"
    else :
        var = 'c'
        MODEL_PATH = "seisbenchC/ml_model_v1.pt"
        BASE_OUT = "../data/seisbenchC/seisbench_nouv"
else :
    var = 'c'
    MODEL_PATH = "seisbenchC/ml_model_v1.pt"
    BASE_OUT = "../data/seisbenchC/seisbench_nouv"

print(f"On veux une qualité minimal de {var}")


os.makedirs(BASE_OUT, exist_ok=True)

#fichiers sortie CSV
OUTPUT_CSV = os.path.join(BASE_OUT, "catalogue_vt_detectes.csv")
OUTPUT_EVENTS_CSV = os.path.join(BASE_OUT, "catalogue_vt_detectes_evenements_valides.csv")

BASE_MSEED = "/get/ggs/clov/mseed_data/martinique"
MSEED_DIR = os.path.join(BASE_MSEED, "MQ")

#BASE_MSEED ="../data"
#MSEED_DIR = os.path.join(BASE_MSEED, "2014/MQ")


DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

#enleve doublons et garde la picks la plus probable si rapproché
def dedupliquer_picks(df, min_gap_seconds=MIN_GAP_SECONDS):
    if df.empty:
        return df
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

#regroupe les detection individuelle de P pour voir si event sur les autres stations
def associer_evenements(df, fenetre_secondes=ASSOCIATION_WINDOW_SECONDS, min_stations=MIN_STATIONS, phase_filtre="P", duree_max=MAX_EVENT_DURATION):
    df = df.copy()
    df["time"] = pd.to_datetime(df["time"], format="ISO8601")
    if phase_filtre: #si P arrive alors debut event
        df = df[df["phase"] == phase_filtre]
    
    if df.empty: #si pas de P alors return vide
        return pd.DataFrame(columns=["time_debut", "time_fin", "n_stations", "stations", "n_picks", "probabilite_max"])
    
    df = df.sort_values("time").reset_index(drop=True) #trie chronologique
    evenements = [] #aura le catalogue events detecté
    cluster_courant = [df.iloc[0]] #init liste avec le 1er event
    
    def finaliser(cluster):
        stations_impliquees = set(r["station"] for r in cluster) #liste station qui ont detecté l'event
        if len(stations_impliquees) >= min_stations: #pour le filtre, on créer le dictionnaire
            evenements.append({
                "time_debut": cluster[0]["time"],
                "time_fin": cluster[-1]["time"],
                "n_stations": len(stations_impliquees),
                "stations": ",".join(sorted(stations_impliquees)),
                "n_picks": len(cluster),
                "probabilite_max": max(r["probability"] for r in cluster),
            })
    
    
    for _, row in df.iloc[1:].iterrows(): #on regarde tout les events (sauf 1er car déjà ajouté)
        delta = (row["time"] - cluster_courant[-1]["time"]).total_seconds() #calcul delta temps entre les 2 events
        delta_start = (row["time"] - cluster_courant[0]["time"]).total_seconds()
        
        #fix : Le cluster s'agrandit que si gap court ET event ne dure pas plus de MAX_EVENT_DURATION
        if delta <= fenetre_secondes and delta_start <= duree_max:
            cluster_courant.append(row)
        else: #alors nouvel event
            finaliser(cluster_courant) #on fini l'event précédent
            cluster_courant = [row] #on réinit pour entamer un nv groupe
    finaliser(cluster_courant) #on ferme le dernier groupe
    
    
    #convertit liste event en data frame structuré
    df_evenements = pd.DataFrame(evenements)
    if not df_evenements.empty: #pour format csv
        df_evenements["time_debut"] = df_evenements["time_debut"].apply(lambda t: t.isoformat())
        df_evenements["time_fin"] = df_evenements["time_fin"].apply(lambda t: t.isoformat())
    
    return df_evenements

#clean et alignement des traces
def preparer_stream_station(st, stat, min_duration=35.0):
    if len(st) == 0:
        return obspy.Stream()
    
    start_time_brut = min([tr.stats.starttime for tr in st])
    end_time_brut = max([tr.stats.endtime for tr in st])
    duree_brute = end_time_brut - start_time_brut
    
    #si duree totale > 2 jours (172800 secondes), les dates sont fausses
    #charge trop en ram et peux crash (Killed)
    if duree_brute > 172800.0: # Plus de 2 jours d'écart dans les fichiers lus
        print(f"    [ALERTE RAM] Station {stat} ignorée : écart temporel brut de {duree_brute:.0f}s (> 2 jours). Abandon avant merge.")
        return obspy.Stream()
    
    
    #on enleve doublons identiques
    traces_uniques = []
    vus = set()
    for tr in st:
        #rend chaque trace unique
        identifiant = (tr.id, str(tr.stats.starttime), str(tr.stats.endtime))
        if identifiant not in vus:
            vus.add(identifiant)
            traces_uniques.append(tr)
            
    #remplace par la bonne
    st.traces = traces_uniques
    
    #fusion
    try:
        #on garde le plus recent
        st.merge(method=1, fill_value="interpolate")
    except Exception:
        #sinon classique
        st.merge(-1)
    
    st = st.split()
    st_filtre = obspy.Stream()
    
    for tr in st:
        #rejet des traces mortes
        if np.all(tr.data == 0) or np.std(tr.data) < 1e-12:
            continue
            
        #rejet fragment trop court
        duree = tr.stats.npts / tr.stats.sampling_rate
        if duree < min_duration:
            continue
        
        if tr.stats.sampling_rate != 100.0:
            try: tr.interpolate(100.0)
            except Exception: tr.resample(100.0)
            
        tr.data = np.nan_to_num(tr.data)
        tr.detrend("linear")
        tr.taper(max_percentage=0.01, type="cosine") 
        
        
        nyquist = tr.stats.sampling_rate / 2.0
        safe_freq_max = min(FREQ_MAX, nyquist - 0.1)  # S'assure de rester sous Nyquist
        
        # Si le signal est trop pauvre pour le passe-bande, on ignore
        if safe_freq_max <= FREQ_MIN :
            continue
        else:
            tr.filter("bandpass", freqmin=FREQ_MIN, freqmax=safe_freq_max)
        
        st_filtre.append(tr)
        
    if len(st_filtre) == 0:
        return obspy.Stream()
    
    #force alignement temp
    if len(st_filtre) > 0:
        #debut et fin min max
        start_time = min([tr.stats.starttime for tr in st_filtre])
        end_time = max([tr.stats.endtime for tr in st_filtre])
        
        #full 0 pour remplir
        st_filtre.trim(starttime=start_time, endtime=end_time, pad=True, fill_value=0.0)
    
    st_filtre.sort()
    
    #gestion compos manquantes
    existing_comps = set(tr.stats.channel[-1] for tr in st_filtre)
    
    if stat in STATIONS_MONO or len(existing_comps) < 3:
        ref_comp = "Z" if "Z" in existing_comps else list(existing_comps)[0]
        ref_traces = st_filtre.select(component=ref_comp)
        
        for comp in EXPECTED_COMPONENTS:
            if comp not in existing_comps:
                #recré compo manquante
                for tr_ref in ref_traces:
                    tr_fictive = tr_ref.copy()
                    tr_fictive.stats.channel = tr_ref.stats.channel[:-1] + comp
                    #on prend Z*0.05
                    tr_fictive.data = (tr_ref.data * 0.05).astype(tr_ref.data.dtype)
                    st_filtre.append(tr_fictive)
    
    st_filtre.sort()
    return st_filtre

#chargement du modele
print(f"Chargement du modèle local depuis : {MODEL_PATH}")
model = sbm.PhaseNet() 
model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
model.to(DEVICE)
model.eval() #choix du bon mode pour poids stable


#detection
toutes_les_detections = []
tous_les_evenements = []
tous_les_picks_dedup = []

for julian_day in range(START_DAY, END_DAY + 1):
    julian_day_str = f"{julian_day:03d}"  # Transforme 51 en "051"
    print(f"\n--- Traitement du jour {julian_day_str} ---")
    
    detections_du_jour = []
    
    for stat_folder in glob.glob(os.path.join(MSEED_DIR, "*")): #parcour tout les sous dossier pour mseed
        stat = os.path.basename(stat_folder) #recup nom dossier (BAM, ...)
        search_pattern = os.path.join(stat_folder, f"*{YEAR}*{julian_day_str}*") #construit pattern
        mseed_files = glob.glob(search_pattern)
        
        if not mseed_files: #fichier mseed manquand, donc on passe a une autre
            print(f"Station {stat} : Aucun fichier .mseed trouvé.")
            continue
            
        st = obspy.Stream()
        for f in mseed_files:
            try: 
                st += obspy.read(f) #empile toutes les composantes et toutes les stations
            except Exception: 
                pass
                
        if len(st) == 0: 
            print(f"Station {stat} : Les fichiers n'ont pas pu être lus ou sont vides.")
            continue
        
        try:
            st = preparer_stream_station(st, stat, min_duration=35.0)
            if len(st) == 0:
                print(f"Station {stat} : Données rejetées (traces mortes, < 30.0s ou mauvais chevauchement).")
                continue
            
            with torch.no_grad():
                output = model.classify(
                    st, 
                    P_threshold=THRESHOLD_P, 
                    S_threshold=THRESHOLD_S,
                    batch_size=32
                )
            
            picks = list(getattr(output, "picks", output)) #recup liste picks
            
            
            picks = sorted(picks, key=lambda x: x.peak_time) #trie par ordre chrono
            
            dernier_temps_P = None
            picks_valides = []
            
            #filtrage logique (S doit suivre P)
            for pick in picks:
                if pick.phase == "P": #Si P on enregistre direct
                    dernier_temps_P = pick.peak_time
                    picks_valides.append(pick)
                elif pick.phase == "S":
                    if stat in STATIONS_MONO: #on peux pas avoir de S en monocompo
                        continue
                    if dernier_temps_P and 0 < (pick.peak_time - dernier_temps_P) <= 5.0: #enregistre S si delta temps entre P et S moins de 5 sec
                        picks_valides.append(pick)
            
            #on transforme la liste en dictionnaire
            for pick in picks_valides:
                toutes_les_detections.append({
                    "day": julian_day_str, "station": stat, "phase": pick.phase,
                    "time": pick.peak_time.isoformat(), "probability": pick.peak_value
                })
                detections_du_jour.append(toutes_les_detections[-1])
            
            if picks_valides:
                print(f"  Station {stat} : {len(picks_valides)} phases VT filtrées.") #affiche nbr de VT gardé pour la station
            else:
                print(f"Station {stat} : Aucune phase au-dessus du seuil (P>={THRESHOLD_P}, S>={THRESHOLD_S}).")
                
        except Exception as e:
            print(f"  Erreur station {stat} : {e}")
        finally:
            #liberation mémoire aprés chaque station
            if 'st' in locals(): del st
            if 'output' in locals(): del output
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()
    
    
    if detections_du_jour:
        df_jour = pd.DataFrame(detections_du_jour) #transforme en dataframe 
        df_jour_dedup = dedupliquer_picks(df_jour) #on enleve les doublons
        df_evenements = associer_evenements(df_jour_dedup, min_stations=MIN_STATIONS) #on regroupe toutes les P des même event
        print(f"=== Bilan Jour {julian_day_str} : {len(df_jour_dedup)} phases -> {len(df_evenements)} évènements ===") #bilan journalier
        if len(df_evenements) > MAX_EVENT_DAY:
            print(f"  -> Jour {julian_day_str} ignoré : trop d'événements ({len(df_evenements)} > {MAX_EVENT_DAY}).")
        else:
            #on ajoute le jour
            tous_les_picks_dedup.append(df_jour_dedup)
            if not df_evenements.empty:
                tous_les_evenements.append(df_evenements)



print("\n--- Sauvegarde des catalogues ---")

if tous_les_picks_dedup:
    df_picks_total = pd.concat(tous_les_picks_dedup, ignore_index=True)
    df_picks_total.to_csv(OUTPUT_CSV, index=False)
    print(f"Catalogue des picks sauvegardé : {OUTPUT_CSV}")

#event brutes
if tous_les_evenements:
    df_events_total = pd.concat(tous_les_evenements, ignore_index=True)
    
    #application filtre strict pour proba car MIN_STATION déjà appliqué
    masque_strict = df_events_total["probabilite_max"] >= MIN_PROBA_EVENT
    df_events_valides = df_events_total[masque_strict].reset_index(drop=True)
    
    # On sauvegarde les deux catalogues (le brut et le validé)
    df_events_valides.to_csv(OUTPUT_EVENTS_CSV, index=False)
    print(f"Événements valides (stricts) sauvegardés ({len(df_events_valides)} événements) : {OUTPUT_EVENTS_CSV}")
else:
    print("Aucun événement multi-station reconstitué.")