import sys
import os
import pandas as pd
import numpy as np
import pyocto
from datetime import timedelta

#arg
BASE_DIR = "../data"

if len(sys.argv) > 1:
    var = sys.argv[1].lower()
    if var == 'a':
        DOSSIER_QUALITE = "seisbenchA"
    elif var == 'b':
        DOSSIER_QUALITE = "seisbenchB"
    else:
        var = 'c'
        DOSSIER_QUALITE = "seisbenchC"
else:
    var = 'c'
    DOSSIER_QUALITE = "seisbenchC"

print(f"Lancement de PyOcto pour la qualité : {var}")

# Définition dynamique des chemins en fonction de la qualité choisie
stations_path = os.path.join(BASE_DIR, 'station/all_station')
dataset_dir = os.path.join(BASE_DIR, DOSSIER_QUALITE, "seisbench_format_gold")
picks_path = os.path.join(dataset_dir, 'metadata.csv')

output_dir = os.path.join(BASE_DIR, DOSSIER_QUALITE, "results_pyocto")
os.makedirs(output_dir, exist_ok=True)

#preparation station
print("Chargement des stations")
# Lecture du fichier de stations
stations = pd.read_csv(stations_path, sep='\s+', header=None,
                    names=['station_code', 'latitude', 'longitude', 'elevation', 'network_code'])


#premiere colonne ("MQ.BAM")
stations['id'] = stations['network_code'] + '.' + stations['station_code']

#force la correspondance avec les picks pour SAM (car j'ai appele MQ.SAM dans les autres codes)
stations['id'] = stations['id'].replace('WI.SAM', 'MQ.SAM')

#PyOcto utilise km pour elevation et vitesse
stations['elevation'] = stations['elevation'] / 1000.0  

#garde colonnes utile
stations = stations[['id', 'longitude', 'latitude', 'elevation']]


#preparation donnees
print("Chargement et formatage des données")
picks_raw = pd.read_csv(picks_path)

#convertion date debut de trace en datetime
picks_raw['start_time'] = pd.to_datetime(picks_raw['trace_start_time'], format='ISO8601')

picks_list = []
#boucle pour extraire les temps arrivee P et S
for idx, row in picks_raw.iterrows():
    #id station doit correspondre à celui des stations
    stat_id = f"{row['station_network_code']}.{row['station_code']}"
    
    #pick P present
    if pd.notna(row['trace_p_arrival_sample']):
        delta_p = row['trace_p_arrival_sample'] / row['trace_sampling_rate_hz']
        #Convert POSIX timestamp avec .timestamp()
        p_time = (row['start_time'] + pd.Timedelta(seconds=delta_p)).timestamp() 
        picks_list.append({'station': stat_id, 'time': p_time, 'phase': 'P', 'trace_name': row['trace_name'], 'raw_idx': idx})
        
    #pick S present
    if pd.notna(row['trace_s_arrival_sample']):
        delta_s = row['trace_s_arrival_sample'] / row['trace_sampling_rate_hz']
        #Convert POSIX timestamp avec .timestamp()
        s_time = (row['start_time'] + pd.Timedelta(seconds=delta_s)).timestamp() 
        picks_list.append({'station': stat_id, 'time': s_time, 'phase': 'S', 'trace_name': row['trace_name'], 'raw_idx': idx})


#creation DataFrame attendu par PyOcto
picks = pd.DataFrame(picks_list)


#modele de vitesse
print("Création du modèle de vitesse")

#profondeurs strictement croissantes
depths = [0.0, 2.99, 3.0, 4.0, 5.0, 10.0, 14.99, 15.0, 60.0]
vp     = [3.5, 3.5,  6.0, 6.0, 6.0, 6.0,  6.0,   7.0,  7.0]

model_df = pd.DataFrame({
    "depth": depths,
    "vp": vp
})
model_df["vs"] = model_df["vp"] / 1.76

model_path = os.path.join(output_dir, "velocity_model.obj")
pyocto.VelocityModel1D.create_model(
    model=model_df,
    delta=1.0,         
    xdist=350.0,       
    zdist=60.0,        
    path=model_path
)

velocity_model = pyocto.VelocityModel1D(
    path=model_path,
    tolerance=2.0      
)

print("Configuration de PyOcto")

lat_min = stations['latitude'].min() - 2.0
lat_max = stations['latitude'].max() + 2.0
lon_min = stations['longitude'].min() - 2.0
lon_max = stations['longitude'].max() + 2.0


associator = pyocto.OctoAssociator.from_area(
    lat=(lat_min, lat_max),
    lon=(lon_min, lon_max),
    zlim=(0, 50),         # Zone de recherche en profondeur (km)
    time_before=300.0,
    velocity_model=velocity_model,
    n_picks=4,            # Min de picks totaux
    n_p_picks=1,          # Min de picks P
    n_s_picks=1           # Min de picks S
)

print("Association en cours")

#transformation stations en coordonnées locales requises par PyOcto
stations = associator.transform_stations(stations)

#lance PyOcto prend les picks et les stations
events, assignments = associator.associate(picks, stations)
events = associator.transform_events(events)

print(f"Terminé ! {len(events)} événements trouvés.")
print("\nAperçu des événements :")
print(events.head())

print("\nAperçu des assignations (picks rattachés aux événements) :")
print(assignments.head())

#sauvegarde des events
#liste, heure origine et loc de chaque event identifie
events_path = f"{output_dir}/catalogue_evenements.csv"
events.to_csv(events_path, index=False)
print(f"Les événements ont été sauvegardés dans : {events_path}")

#sauvegarde des associations
#quel P et/ou S appartient à quel event
assignments_path = f"{output_dir}/picks_associes.csv"
assignments.to_csv(assignments_path, index=False)
print(f"Les assignations ont été sauvegardées dans : {assignments_path}")


#repasse à SeisBench
print("Mise à jour du fichier metadata au format SeisBench")

#copie du metadata original
metadata_seisbench = picks_raw.copy()

#ajout des colonnes standard SeisBench
metadata_seisbench['source_id'] = pd.Series(dtype='object')
metadata_seisbench['source_latitude'] = np.nan
metadata_seisbench['source_longitude'] = np.nan
metadata_seisbench['source_depth_km'] = np.nan
metadata_seisbench['source_origin_time'] = pd.NaT

#recuperation de l'index d'origine
if not assignments.empty:
    assignments['raw_idx'] = picks.loc[assignments['pick_idx'], 'raw_idx'].values

    #fusion infos event et picks
    events_renamed = events.rename(columns={
        'idx': 'event_idx',
        'latitude': 'source_latitude',
        'longitude': 'source_longitude',
        'depth': 'source_depth_km',
        'time': 'source_origin_time'
    })
    events_renamed = events_renamed[['event_idx', 'source_latitude', 'source_longitude', 'source_depth_km', 'source_origin_time']]
    
    assignments = assignments.merge(events_renamed, on='event_idx', how='left')

    #injection dans le dataframe SeisBench
    for _, row in assignments.iterrows():
        r_idx = row['raw_idx']
        metadata_seisbench.at[r_idx, 'source_id'] = f"ev_{int(row['event_idx'])}"
        metadata_seisbench.at[r_idx, 'source_latitude'] = row['source_latitude']
        metadata_seisbench.at[r_idx, 'source_longitude'] = row['source_longitude']
        metadata_seisbench.at[r_idx, 'source_depth_km'] = row['source_depth_km']
        metadata_seisbench.at[r_idx, 'source_origin_time'] = pd.to_datetime(row['source_origin_time'], unit='s')

#nettoyage colonne temporaire
metadata_seisbench = metadata_seisbench.drop(columns=['start_time'])

#save dans le dossier de resultats PyOcto
output_metadata = os.path.join(output_dir, 'metadata_associated_seisbench.csv')
metadata_seisbench.to_csv(output_metadata, index=False)

print(f"Fichier SeisBench mis à jour sauvegardé ici : {output_metadata}")