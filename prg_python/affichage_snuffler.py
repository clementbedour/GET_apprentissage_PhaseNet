import os
import glob
from datetime import datetime, timezone
from pyrocko.gui.marker import load_markers,EventMarker
from obspy import read
from pyrocko import trace as ptrace
from pyrocko.model.station import load_stations

# Variables d'environnement pour snuffler (sur WSL y'a des problèmes)
os.environ['LD_LIBRARY_PATH'] = os.environ.get('CONDA_PREFIX', '') + '/lib:' + os.environ.get('LD_LIBRARY_PATH', '')
os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['QT_XCB_GL_INTEGRATION'] = 'none'
os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = '/home/guiga/miniconda3/envs/phasenet/plugins/platforms'

# --- PARAMÈTRES ET CHEMINS ---
#On cible le dossier avec l'étoile pour prendre tous les .txt 
#c'est dans "phase_evenement" que nous avons toutes les marques des phases
MARKERS_PATTERN = '../data/phase_evenement/*.txt'
#Repertoire où il y a toutes la data des miniseed
#aprés MQ il y a doit y avoir les répertoires BAM,IA2,...
DATA_DIR = '../data/2014/MQ'
#juste pour dire qu'on prend EHZ comme HHN
CHANNEL_PATTERN = '*' 
#chemin d'accé au fichier avec les stations
PATH_STATIONS = '../data/station/all_station_2'

def main():
    '''Lance snuffler en boucle, choix du fichier depuis le terminal'''
    #Liste de tout les fichiers
    marker_files = sorted(glob.glob(MARKERS_PATTERN))
    if not marker_files:
        print("Aucun fichier de marqueurs trouvé.")
        return

    print(f"{len(marker_files)} fichiers trouvés.")
    
    start_input = input("Par quel fichier commencer ?\nEntrez le nom du fichier ou Entrée pour le premier fichier : ").strip()
    
    #var d'index pour savoir où on est (0 si Entrée, sinon on doit l'init jusqu'à trouver start_input)
    start_idx = 0
    if start_input: #donc diff de 0
        for i, f in enumerate(marker_files):
            if start_input in os.path.basename(f):#on a trouvé le bon index
                start_idx = i
                break

    #boucle sur les fichier entre index et nbr de fichier
    for i in range(start_idx, len(marker_files)):
        current_file = marker_files[i]
        print(f"\n--- Traitement de : {os.path.basename(current_file)} ---")
        
        try:
            markers = load_markers(current_file)
            print(f"{len(markers)} marqueurs chargés")
        except Exception as e:
            print(f"Erreur lors du chargement des marqueurs dans affichage_snuffler.main() : {e}")
            continue

        if not markers:
            print(f"Aucun marqueur trouvé dans le fichier : {e}")
            continue

        #prend le minimum du tmp des markers de la "liste"
        #donc logiquement le temps de l'event
        min_time = min(m.tmin for m in markers)
        #print("min_time d'event en jour until : ",min_time)
        #print("min_time YYYY-MM... : ",datetime.fromtimestamp(min_time, tz=timezone.utc))
        event_date = datetime.fromtimestamp(min_time, tz=timezone.utc)
        
        year = event_date.strftime('%Y')
        jday = event_date.strftime('%j')
        
        tmin_global = min_time - 40
        tmax_global = min_time + 30
        
        print(f"Événement du {event_date.strftime('%Y-%m-%d %H:%M:%S')} UTC | Jour julien : {jday}")
        
        #liste qui stocke l'id des stations dans data (BAM, CPM,...)
        all_stations_in_dir = []
        for element in os.listdir(DATA_DIR):
            chemin_complet = os.path.join(DATA_DIR, element)
            #si repertoire on a trouvé une station alors on garde
            if os.path.isdir(chemin_complet):
                all_stations_in_dir.append(element)
        
        
        
        traces = []
        nb_chopp=0
        #on va récupérer toutes nos traces de toutes nos stations
        for id_station in all_stations_in_dir:
            mseed_pattern = os.path.join(DATA_DIR, id_station, f"*.{id_station}.*.{CHANNEL_PATTERN}.D.{year}.{jday}.mseed")
            #matching files : liste temporaire des fichiers dans le repertoire de l'id_station
            matching_files = glob.glob(mseed_pattern)
            #print ("matching_files : ",matching_files)
            if not matching_files:
                continue
            
            #on boucle sur les fichiers de la station.
            for mseed_path in matching_files:
                try:
                    stream = read(mseed_path)
                    #au cas où on est plusieurs traces (cas rares, mais déjà arrivé), alors on combine
                    stream.merge() 
                    
                    #formatage de obspy vers pyrocko / on fais juste copié collé
                    for tr in stream:
                        t = ptrace.Trace(
                            network=tr.stats.network,
                            station=tr.stats.station,
                            location=tr.stats.location,
                            channel=tr.stats.channel,
                            tmin=tr.stats.starttime.timestamp,
                            deltat=tr.stats.delta,
                            ydata=tr.data.astype(float)
                        )
                        
                        #on ségmente le signal pour economiser de la RAM 
                        chopp = t.chop(tmin_global, tmax_global, inplace=False)
                        
                        if chopp and chopp.data_len() > 0:
                            traces.append(chopp)
                            nb_chopp = nb_chopp +1
                            #print(f"Chargé : {mseed_path}")
                except Exception as e:
                    print(f"Erreur de chargement pour {mseed_path} : {type(e).__name__} - {e}")
        print(nb_chopp,"segments chargés\n")
        
        
        if not traces:
            print("Aucune trace MiniSEED n'a pu être chargée.")
            continue
    
        try:
            stations = load_stations(PATH_STATIONS)
        except Exception as e:
            print("Problème lors du chargement de station\n")
            stations = []
        
        
        #on extrait l'evenement de la liste de marqueurs
        event = []
        for m in markers:
            #on regarde si c'est un evenement, sinon on l'ignore
            if isinstance(m, EventMarker):
                objet_evenement = m.get_event()
                event.append(objet_evenement)
        
        print("Ouverture de Snuffler... \nAppuyez sur 'q' pour fermer")
        ptrace.snuffle(traces, markers=markers, stations=stations, events=event)

        #Fermeture de Snuffler, donc on regarde si on a pas fini de traiter, sinon on continue
        
        
        #On regarde si prochain fichier c NL.txt
        next_is_NL = False
        if i + 1 < len(marker_files):
            next_is_NL = (os.path.basename(marker_files[i + 1]) == "NL.txt")

        #S'il reste un fichier et que c pas NL alors
        if i < len(marker_files) - 1 and not next_is_NL:
            choix = input("Entrée pour continuer ou 1 pour arrêter : ").strip()
            if choix == '1':
                print(f"\nArrêt du programme. Dernier fichier traité : {os.path.basename(current_file)}")
                break
        #Si le dernier fichier est NL
        else:
            if next_is_NL:
                print(f"\nNL.txt détecté juste après. Fin du parcours.")
                print("\nTout les fichiers ont été traités !")
                break
    else:
        #Seulement si le programme arrive au bout et que pas de NL
        print("\nTout les fichiers ont été traités !")

if __name__ == '__main__':
    main()