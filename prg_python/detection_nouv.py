import os
import glob
import numpy as np
import torch
import obspy
import pandas as pd
import seisbench.models as sbm
from obspy import UTCDateTime

# PARAMETRES
BASE_DIR = "../data"
MSEED_DIR = os.path.join(BASE_DIR, "2014/MQ")
MODEL_PATH = "seisbench/phasenet_volcan_v1.pt"
BASE_OUT = "../data/seisbench/seisbench_nouv"
os.makedirs(BASE_OUT, exist_ok=True)
OUTPUT_CSV = os.path.join(BASE_OUT, "catalogue_vt_detectes.csv")

# Valeurs seuils ajustées pour la précision
THRESHOLD_P = 0.95
THRESHOLD_S = 0.95

FREQ_MIN = 3.0
FREQ_MAX = 15.0

START_DAY = 51
END_DAY = 151
YEAR = 2014

EXPECTED_COMPONENTS = {"Z", "N", "E"}
MIN_GAP_SECONDS = 1.0
STATIONS_MONO = {"BAM", "CPM", "GBM", "MLM", "FDF"}

ASSOCIATION_WINDOW_SECONDS = 5.0
MIN_STATIONS = 4

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ============================================================
# FONCTIONS REQUISES
# ============================================================
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

def associer_evenements(df, fenetre_secondes=ASSOCIATION_WINDOW_SECONDS,
                        min_stations=MIN_STATIONS, phase_filtre="P",
                        retourner_diagnostic=False):
    df = df.copy()
    df["time"] = pd.to_datetime(df["time"], format="ISO8601")
    if phase_filtre:
        df = df[df["phase"] == phase_filtre]

    if df.empty:
        vide = pd.DataFrame(columns=["time_debut", "time_fin", "n_stations", "stations", "n_picks", "probabilite_max"])
        return (vide, {}) if retourner_diagnostic else vide

    df = df.sort_values("time").reset_index(drop=True)
    evenements = []
    tous_les_clusters = []
    cluster_courant = [df.iloc[0]]

    def finaliser(cluster):
        stations_impliquees = set(r["station"] for r in cluster)
        tous_les_clusters.append(len(stations_impliquees))
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

    if retourner_diagnostic:
        from collections import Counter
        diagnostic = {
            "n_clusters_total": len(tous_les_clusters),
            "distribution_taille": dict(Counter(tous_les_clusters)),
            "n_phases_utilisees": len(df),
        }
        return df_evenements, diagnostic

    return df_evenements

# ============================================================
# 1. INITIALISATION DU MODÈLE
# ============================================================
print(f"Chargement du modèle local depuis : {MODEL_PATH}")
model = sbm.PhaseNet() 
model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
model.to(DEVICE)
model.eval()

# ============================================================
# 2. BOUCLE DE DÉTECTION
# ============================================================
toutes_les_detections = []

for julian_day in range(START_DAY, END_DAY + 1):
    print(f"\n--- Traitement du jour {julian_day:03d} de l'année {YEAR} ---")
    
    detections_du_jour = []
    
    for stat_folder in glob.glob(os.path.join(MSEED_DIR, "*")):
        stat = os.path.basename(stat_folder)
        search_pattern = os.path.join(stat_folder, f"*{YEAR}*{julian_day:03d}*")
        mseed_files = glob.glob(search_pattern)
        
        if not mseed_files: continue
            
        st = obspy.Stream()
        for f in mseed_files:
            try: st += obspy.read(f)
            except: pass
                
        if len(st) == 0: continue

        try:
            st.merge(method=1, fill_value=0)
            
            # Filtrage
            for tr in st:
                tr.detrend("linear")
                nyquist = tr.stats.sampling_rate / 2.0
                safe_freq_max = min(FREQ_MAX, nyquist - 0.1)
                tr.filter("bandpass", freqmin=FREQ_MIN, freqmax=safe_freq_max)

            # --- GESTION DES MONO-COMPOSANTES ---
            existing_components = list(set([tr.stats.channel[-1] for tr in st]))
            if stat in STATIONS_MONO or len(existing_components) < 3:
                ref_comp = "Z" if "Z" in existing_components else existing_components[0]
                traces_modeles = st.select(component=ref_comp)
                for comp in EXPECTED_COMPONENTS:
                    if comp not in existing_components:
                        for tr in traces_modeles:
                            tr_vide = tr.copy()
                            tr_vide.stats.channel = tr.stats.channel[:-1] + comp
                            tr_vide.data = np.zeros_like(tr.data)
                            st.append(tr_vide)
                            
            st.sort() 

            # Détection
            output = model.classify(st, P_threshold=THRESHOLD_P, S_threshold=THRESHOLD_S)
            picks = list(getattr(output, "picks", output))
            
            # Filtrage logique
            picks = sorted(picks, key=lambda x: x.peak_time)
            dernier_temps_P = None
            picks_valides = []

            for pick in picks:
                if pick.phase == "P":
                    dernier_temps_P = pick.peak_time
                    picks_valides.append(pick)
                elif pick.phase == "S":
                    if stat in STATIONS_MONO: continue
                    if dernier_temps_P and 0 < (pick.peak_time - dernier_temps_P) <= 10.0:
                        picks_valides.append(pick)

            for pick in picks_valides:
                toutes_les_detections.append({
                    "day": julian_day, "station": stat, "phase": pick.phase,
                    "time": pick.peak_time.isoformat(), "probability": pick.peak_value
                })
                detections_du_jour.append(toutes_les_detections[-1])

            if picks_valides:
                print(f"  Station {stat} : {len(picks_valides)} phases VT filtrées.")
                
        except Exception as e:
            print(f"  Erreur station {stat} : {e}")

    # Bilan du jour
    if detections_du_jour:
        df_jour = pd.DataFrame(detections_du_jour)
        df_jour_dedup = dedupliquer_picks(df_jour)
        # On récupère juste la valeur retournée par la fonction
        df_evenements = associer_evenements(df_jour_dedup, min_stations=MIN_STATIONS)
        print(f"=== Bilan Jour {julian_day:03d} : {len(df_jour_dedup)} phases -> {len(df_evenements)} évènements ===")

# Sauvegarde finale
if toutes_les_detections:
    pd.DataFrame(toutes_les_detections).to_csv(OUTPUT_CSV, index=False)