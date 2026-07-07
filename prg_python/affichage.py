import os
#Gemini m'a rajouté ça car passé par wsl puis utiliser snuffler il aime pas trop
os.environ['LD_LIBRARY_PATH'] = os.environ.get('CONDA_PREFIX', '') + '/lib:' + os.environ.get('LD_LIBRARY_PATH', '')
os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['QT_XCB_GL_INTEGRATION'] = 'none'
os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = '/home/guiga/miniconda3/envs/phasenet/plugins/platforms'

import glob

from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from pyrocko import io
from pyrocko.gui.marker import PhaseMarker, load_markers
from obspy import read
from pyrocko import trace as ptrace
from pyrocko.model.station import load_stations

#pour lancer le code
#python affichage.py


# --- PARAMÈTRES ET CHEMINS ---
#Phase_File est le fichier phase que l'on va étudier
PHASE_FILE = '../data/phase_vt/2014-05-295.txt'

PATH_MARKERS = '../data/phase_evenement/201405280555.txt'

#Dans quelle répertoire retrouver tout les établissements
#qui ont mes .mseed 
#(je sais c pas full MQ mais j'ai tout mis dans MQ, même WI et G)
DATA_DIR = '../data/2014/MQ'

# On cherche n'importe quel canal se terminant par HZ (EHZ, HHZ, etc.)
CHANNEL_PATTERN = '*H*'

#chemin vers data des stations
PATH_STATIONS = '../data/station/all_station_2'

#on a le fichier de phase et on extrait les infos de toutes les stations
#return : liste de dictionnaires avec pointés
def parse_phase_file(filepath):
    picks = []
    
    with open(filepath, 'r') as f:
        for line in f:
            
            if not line[0:3].strip(): # or len(line) < 24 ça marche pas bien avec ça
                #On ne prend pas les lignes qui on aucun caractere au début (genre LAM,BAM,GBM,IA2)
                #S'il y avait 1 ou 2 caractere on aurait pris, mais j'ai que 3 dans ma bdd
                continue
                
            #Si on a l'id de la station qui est pas tjr 3 faut changer ça
            id_station = line[0:3].strip()
            #Je pense que peux importe l'id de la station, date et heure sont toujours ici
            #C une structure qui ne bouge pas
            p_date_time_station = line[9:24].strip()
            
            #Résolution de bug : si la dixaine des seconde = 0 alors on a " " à la place
            #donc ça fait bugger au moment de le passer sous YYYY-MM-DD ...
            # Convertir en liste pour pouvoir modifier les caractères
            p_date_time_station = list(p_date_time_station)
            for i in (range(len(p_date_time_station))):
                if p_date_time_station[i]== " ":
                    p_date_time_station[i] = "0"
            
            #fin du bug, donc on remets au format chaine
            p_date_time_station = "".join(p_date_time_station)


            try:
                #on mets un meilleur format :
                #YYYY-MM-DD HH-MM-SS.ss
                #print("p_date_time_station :",p_date_time_station)
                p_date_time_station_format = datetime.strptime(p_date_time_station, "%y%m%d%H%M%S.%f").replace(tzinfo=timezone.utc)
                #print("p_date_time_station_format : ",p_date_time_station_format)
                picks.append({'station': id_station, 'phase': 'P', 'time': p_date_time_station_format.timestamp(), 'datetime': p_date_time_station_format})
            except ValueError:
                print("On a un probleme dans le format dans la fonction parse_phase_file() pour P")
                continue
            
            #On recupere la  valeur de la phase S et on regarde si elle existe
            s_time = line[31:36].strip()
            if s_time:
                try:
                    s_sec = float(s_time)
                    p_sec = float(line[19:24].strip())
                    
                    #j'ai pas trouvé d'exemple pour vérifier que le +1 minute marche
                    #mais en théorie c bon
                    #on regarde si s_sec n'est pas arrivé pile entre 2 minutes
                    if p_sec > s_sec: #ici faire +1 minutes
                        s_delta = timedelta(seconds = s_sec, minutes=1)
                    else : #baleck
                        s_delta = timedelta(seconds = s_sec,minutes=0)
                    
                    #on a donc bien S au format voulu avec le potentiel decalage de minutes
                    s_date_time_station_format = p_date_time_station_format.replace(second=0, microsecond=0) + s_delta
                    
                    picks.append({'station': id_station, 'phase': 'S', 'time': s_date_time_station_format.timestamp(), 'datetime': s_date_time_station_format})
                except ValueError:
                    print("On a un probleme dans le format dans la fonction parse_phase_file() pour S")
                    pass
    return picks

def main():
    
    #On commence par créer notre dictionnaire des pointés
    picks = parse_phase_file(PHASE_FILE)
    if not picks:
        print("Aucun pointé trouvé dans le fichier de phase.")
        return

    #Heure de l'événement (pour fenêtre Snuffler)
    event_date = picks[0]['datetime'] #correspond à p_date_time_format
    year = event_date.strftime('%Y')  #2014 dans 100% de mes cas
    jday = event_date.strftime('%j')  #valeur du jour en jour Julien
    
    #Fenêtre temporelle choisit
    tmin_global = picks[0]['time'] -10
    tmax_global = tmin_global + 30
    
    #print("tmin_global : ",tmin_global)
    #print("event_date : ",event_date)
    #print("tmin_global UTC : ", datetime.fromtimestamp(tmin_global, tz=timezone.utc))    #print("tmax_global : ",tmax_global)

    #print("PHASE_FILE = ",PHASE_FILE)
    #print(event_date)
    
    unique_stations=[] #liste avec id des stations
    for station in picks :
        unique_stations.append(station['station']) #on récupere toutes les stations mais on a doublons
    unique_stations = list(dict.fromkeys(unique_stations)) #plus de doublons et conservation de l'ordre
    
    
    print(f"Événement du {event_date.strftime('%Y-%m-%d')} | Jour julien : {jday}") #affichage correct
    traces = [] #faut l'init avant les boucles
    
    
    #On va boucler pour trouver tout les fichiers qui correspondent à notre événement
    for id_station in unique_stations:
        #pattern global pour trouver tous les fichiers (.mseed) pour une station
        mseed_pattern = os.path.join(DATA_DIR, id_station, f"*.{id_station}.*.{CHANNEL_PATTERN}.D.{year}.{jday}.mseed")
        
        #avec mon pattern je récupère tout les fichiers correspondant dans une liste 
        matching_files = glob.glob(mseed_pattern)
        #print("matching_files : ",matching_files)
        
        
        if not matching_files:
            print(f"Attention: Aucun fichier trouvé pour la station {id_station} (Motif : {mseed_pattern})")
            continue


        for mseed_path in matching_files:
            try:
                #charge les traces
                
                st = read(mseed_path)
                st.merge() # Fusionne les fragments (les 0.74s + 24h)
                
                #trace_load = io.load(mseed_path)
                #print("trace_load : ",trace_load)
                
                for tr in st:
                    # Création d'une trace Pyrocko depuis les données ObsPy
                    t = ptrace.Trace(
                        network=tr.stats.network,
                        station=tr.stats.station,
                        location=tr.stats.location,
                        channel=tr.stats.channel,
                        tmin=tr.stats.starttime.timestamp,
                        deltat=tr.stats.delta,
                        ydata=tr.data.astype(float)
                    )
                    
                    
                    
                    #On découpe pour garder de l'espace mémoire | inplace c pour pas toucher à la donné de base
                    chopp = t.chop(tmin_global,tmax_global,inplace=False)
                    
                    if chopp and chopp.data_len()>0:
                        #on l'ajoute dans la liste car état final (normalement pas de doublons)
                        traces.append(chopp)
                        print(f"Chargé : {mseed_path}")
                    else :
                        print(f"Ignoré (Hors fenêtre ou vide) : {mseed_path}")
            except Exception as e:
                print(f"Erreur de chargement ou le découpage pour {mseed_path} : {type(e).__name__} - {e}")

    if not traces:
        print("Aucune trace MiniSEED n'a pu être chargée.")
        return

    #Chargement du fichier avec toutes locs des stations
    stations = load_stations(PATH_STATIONS)
    print(f"Chargement des stations réussi.")

    #On associe id_ station à son NSLC complet
    station_to_nslc = {}
    for t in traces:
        net, id_station, loc, cha = t.nslc_id
        station_to_nslc[id_station] = t.nslc_id

    # créer les marqueurs
    markers = []
    for pick in picks:
        id_station = pick['station']
        
        # Si on n'a pas pu charger la trace de cette station, on ignore ce pointé
        if id_station not in station_to_nslc:
            print("On n'a pas pu charger la trace de cette station")
            continue
            
        # On utilise le NSLC exact qu'on a récupéré
        marker = PhaseMarker(
            nslc_ids=[station_to_nslc[id_station]],
            tmin=pick['time'],
            tmax=pick['time'],
            phasename=pick['phase']
        )
        markers.append(marker)
        
    # On charge directement le fichier de marqueurs déjà existant
    markers = load_markers(PATH_MARKERS)
    print(f"{len(markers)} marqueur(s) chargé(s) depuis {PATH_MARKERS}")

    #Snuffler
    print("Ouverture de Snuffler")
    ptrace.snuffle(traces, markers=markers, stations=stations) # on charge les traces, les marques et les stations

if __name__ == '__main__':
    main()