import os
import glob
import numpy as np
import torch
import obspy
import pandas as pd
import seisbench.models as sbm
from obspy import UTCDateTime

# ------------ PARAMÈTRES ------------
BASE_DIR = "../data"
MODEL_PATH = "seisbench/phasenet_volcan_v1.pt"
BASE_OUT = "../data/seisbench/seisbench_nouv"
os.makedirs(BASE_OUT, exist_ok=True)

#fichiers sortie CSV
OUTPUT_CSV = os.path.join(BASE_OUT, "catalogue_vt_detectes.csv")
OUTPUT_EVENTS_CSV = os.path.join(BASE_OUT, "catalogue_vt_detectes_evenements_valides.csv")

BASE_MSEED = "/get/ggs/clov/mseed_data/martinique"
MSEED_DIR = os.path.join(BASE_MSEED, "MQ")

#BASE_MSEED ="../data"
#MSEED_DIR = os.path.join(BASE_MSEED, "2014/MQ")


#valeurs de détection
THRESHOLD_P = 0.95
THRESHOLD_S = 0.95

#filtre
FREQ_MIN = 3.0
FREQ_MAX = 15.0

START_DAY = 51
END_DAY = 151
YEAR = 2014

EXPECTED_COMPONENTS = {"Z", "N", "E"}
MIN_GAP_SECONDS = 1.0
STATIONS_MONO = {"BAM", "CPM", "GBM", "MLM"}

#params association
ASSOCIATION_WINDOW_SECONDS = 5.0
#filtre pour event
MIN_STATIONS = 4          #nbr min de stat 
MIN_PROBA_EVENT = 0.85    #score confiance minimal

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

#prend les detection individuelle pour voir si event sur les autres stations
def associer_evenements(df, fenetre_secondes=ASSOCIATION_WINDOW_SECONDS,
                        min_stations=MIN_STATIONS, phase_filtre="P",
                        retourner_diagnostic=False):
    df = df.copy()
    df["time"] = pd.to_datetime(df["time"], format="ISO8601")
    if phase_filtre: #si P arrive alors debut event
        df = df[df["phase"] == phase_filtre]
    
    if df.empty: #si pas de P alors return vide
        vide = pd.DataFrame(columns=["time_debut", "time_fin", "n_stations", "stations", "n_picks", "probabilite_max"])
        return (vide, {}) if retourner_diagnostic else vide
    
    df = df.sort_values("time").reset_index(drop=True) #trie chronologique
    evenements = [] #aura le catalogue events detecté
    tous_les_clusters = [] #pour savoir cmb de station
    cluster_courant = [df.iloc[0]] #init liste avec le 1er event
    
    def finaliser(cluster):
        stations_impliquees = set(r["station"] for r in cluster) #liste station qui ont detecté l'event
        tous_les_clusters.append(len(stations_impliquees)) #stocke le nbr de station
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
        if delta <= fenetre_secondes: #si delta petit, alors même event
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
    
    
    #créer un dictionnaire
    if retourner_diagnostic:
        from collections import Counter
        diagnostic = {
            "n_clusters_total": len(tous_les_clusters), #nbr total de clusters créés
            "distribution_taille": dict(Counter(tous_les_clusters)), #repartition nbr de stations impliquées par cluster
            "n_phases_utilisees": len(df), #nbr total de phases analysé
        }
        return df_evenements, diagnostic
    
    return df_evenements


#chargement du modele
print(f"Chargement du modèle local depuis : {MODEL_PATH}")
model = sbm.PhaseNet() 
model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
model.to(DEVICE)
model.eval() #choix du bon mode pour poids stable


#detection
toutes_les_detections = []
tous_les_evenements = []

for julian_day in range(START_DAY, END_DAY + 1):
    print(f"\n--- Traitement du jour {julian_day} ---")
    
    detections_du_jour = []
    
    for stat_folder in glob.glob(os.path.join(MSEED_DIR, "*")): #parcour tout les sous dossier pour mseed
        stat = os.path.basename(stat_folder) #recup nom dossier (BAM, ...)
        search_pattern = os.path.join(stat_folder, f"*{YEAR}*{julian_day}*") #construit pattern
        mseed_files = glob.glob(search_pattern)
        
        if not mseed_files: #fichier mseed manquand, donc on passe a une autre
            continue
            
        st = obspy.Stream()
        for f in mseed_files:
            try: 
                st += obspy.read(f) #empile toutes les composantes et toutes les stations
            except Exception: 
                pass
                
        if len(st) == 0: 
            continue
        
        try:
            st.merge(method=1, fill_value=0) #comble signal avec 0
            
            #filtrage
            for tr in st:
                tr.detrend("linear") #enlève tendance linéaire
                nyquist = tr.stats.sampling_rate / 2.0 
                safe_freq_max = min(FREQ_MAX, nyquist - 0.1) #TH Shannon Nyquist
                tr.filter("bandpass", freqmin=FREQ_MIN, freqmax=safe_freq_max) #applique passe bande
            
            #mono composantes
            existing_components = list(set([tr.stats.channel[-1] for tr in st]))
            if stat in STATIONS_MONO or len(existing_components) < 3:
                ref_comp = "Z" if "Z" in existing_components else existing_components[0] #on mets Z en compo de base, sinon la première dispo (N puis E)
                traces_modeles = st.select(component=ref_comp) #on duplique
                for comp in EXPECTED_COMPONENTS:
                    if comp not in existing_components: #s'il manque une composante alors on applique copie et full 0
                        for tr in traces_modeles:
                            tr_vide = tr.copy()
                            tr_vide.stats.channel = tr.stats.channel[:-1] + comp
                            tr_vide.data = np.zeros_like(tr.data)
                            st.append(tr_vide)
                            
            st.sort() #trie car tout le monde à 3 compos donc homogène
            
            
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
            
            #filtrage logique
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
                    "day": julian_day, "station": stat, "phase": pick.phase,
                    "time": pick.peak_time.isoformat(), "probability": pick.peak_value
                })
                detections_du_jour.append(toutes_les_detections[-1])
            
            if picks_valides:
                print(f"  Station {stat} : {len(picks_valides)} phases VT filtrées.") #affiche nbr de VT gardé pour la station
                
        except Exception as e:
            print(f"  Erreur station {stat} : {e}")
    
    
    if detections_du_jour:
        df_jour = pd.DataFrame(detections_du_jour) #transforme en dataframe 
        df_jour_dedup = dedupliquer_picks(df_jour) #on enleve les doublons
        df_evenements = associer_evenements(df_jour_dedup, min_stations=MIN_STATIONS) #on regroupe toutes les P des même event
        print(f"=== Bilan Jour {julian_day} : {len(df_jour_dedup)} phases -> {len(df_evenements)} évènements ===") #bilan journalier
        
        if not df_evenements.empty:
            tous_les_evenements.append(df_evenements)



print("\n--- Sauvegarde des catalogues ---")

#event brutes
if toutes_les_detections:
    df_picks_total = pd.DataFrame(toutes_les_detections)
    df_picks_total.to_csv(OUTPUT_CSV, index=False)
    print(f"Détections brutes sauvegardées ({len(df_picks_total)} picks) : {OUTPUT_CSV}")
else:
    print("Aucune détection brute enregistrée.")

#event avec filtre (MIN_STATIONS et MIN_PROBA_EVENT)
if tous_les_evenements:
    df_events_total = pd.concat(tous_les_evenements, ignore_index=True)
    
    #application filtre strict
    masque_strict = (df_events_total["n_stations"] >= MIN_STATIONS) & (df_events_total["probabilite_max"] >= MIN_PROBA_EVENT)
    df_events_valides = df_events_total[masque_strict].reset_index(drop=True)
    
    df_events_valides.to_csv(OUTPUT_EVENTS_CSV, index=False)
    print(f"Événements valides (stricts) sauvegardés ({len(df_events_valides)} événements) : {OUTPUT_EVENTS_CSV}")
else:
    print("Aucun événement multi-station reconstitué.")