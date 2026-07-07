from genericpath import exists
import os
from datetime import datetime, timedelta, timezone
import glob
#objectif : prendre toutes les phases dans phases_vt
#mettre à la première lignes "# Snuffler Markers File Version 0.2"
#à la seconde ligne :
#       event: YYYY-MM-DD HH:MM:SS.ssss  0 id_keys= 0.0 0.0 None None None EventTest None
#puis toutes les traces lignes par lignes, les P et S sont séparées
#YYYY-MM-DD HH:MM:SS.ssss  0 MQ.GBM.91.EHZ

#fichier ou il faut regarder les phases et les mettres sous le bon format
PATH_PHASE = "../data/phase_vt/"

#repertoire où on va créer les docs bien
PATH_EVENEMENT = "../data/phase_evenement"
PATH_DATA = "../data/2014/MQ/"

CHANNEL_PATTERN = '*H*'


unique_stations=[] #liste avec id des stations

if not exists(PATH_EVENEMENT):
    os.makedirs(PATH_EVENEMENT)

#c'est un peu chiant les gars en gros Luden c'est un mythique qui donne de la péné magique 
#et donc en en gros ça donne 6 de péné magique flat donc à 2 items complets.. 
#donc il a 10 de péné flat donc il monte à 16, il a les bottes ça fait 18.
#Donc 16+18 ça fait 34 si j'dis pas de conneries donc 34 plus il avait shadow flame 
#donc il a 44 et après du coup le void staff faut faire 44 divisé par 0.6
#en gros il fait des dégats purs à un mec jusqu'à 73 d'rm j'avais dit 70 dans le cast à peu près
#et en gros bah les mecs ils ont pas 70 d'rm parce que globalement y'a eu un patch, 
#en gros y'a le patch qui fait 0.8 d'rm sur les carrys et en gros de base sur lol y'avait pas ça
#et en gros la botlane va jamais prendre de la rm en lane en tout cas pas beaucoup
#donc c'est pas ouf en vrai j'pense que son item est nul donc en vrai j'pense soit il enlève shadow flame 
#soit le void staff mais j'pense qu'il vaut mieux enlever shadow flame
def event(content):
    return "event: \n"





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


def pattern(picks):
    event_date = picks[0]['datetime'] #premier picks (pas la peine de savoir qui c, on veux juste years et Julien days)
    year = event_date.strftime('%Y')  #2014 dans 100% de mes cas
    jday = event_date.strftime('%j')  #valeur du jour en jour Julien
    
    unique_stations=[]
    for station in picks :
        unique_stations.append(station['station']) #on récupere toutes les stations mais on a doublons
    unique_stations = list(dict.fromkeys(unique_stations)) #plus de doublons et conservation de l'ordre
    print("unique_ stations : ",unique_stations,"\n")
    
    for id_station in unique_stations:
        #pattern global pour trouver tous les fichiers (.mseed) pour une station
        mseed_pattern = os.path.join(PATH_DATA, id_station, f"*.{id_station}.*.{CHANNEL_PATTERN}.D.{year}.{jday}.mseed")
        print("test fin ",mseed_pattern,"\n")
        
        #avec mon pattern je récupère tout les fichiers correspondant dans une liste 
        matching_files = glob.glob(mseed_pattern)
        for i in range(len(matching_files)) :
            
            print(" matching files CHOPP ",str(matching_files)[22:35])
            #ici 
        print("len matching files :",len(matching_files))
        print("matching_files : ",matching_files)
        
        print("test pour glob glob recollé : " + str(mseed_pattern) + str(matching_files) + "\n")
        
        if not matching_files:
            print(f"Attention: Aucun fichier trouvé pour la station {id_station} (Motif : {mseed_pattern})")
            continue



def phase(line):
    id_station = line[0:3].strip
    
    line_content=""
    date = line[9:24].strip()

    #on recupere remplace le " " par un 0
    date = date.replace(" ","0")
    date_format = datetime.strptime(date, "%y%m%d%H%M%S.%f").replace(tzinfo=timezone.utc)
    line_content = line_content + str(date_format)[0:24] + "  0 "
    
    return (line_content +"\n")








def main(filename):
    #dans CONTENT il va y avoir toutes les lignes de mon fichier
    CONTENT = []
    with open(filename, 'r') as f:
        for i in f:
            CONTENT.append(i)
    
    #on vérifie si doc pas vide
    if not CONTENT or not CONTENT[0].strip():
        print("La première ligne du fichier est vide, nom du fichier :", filename)
        return (1)

    #on créé le titre pour le doc créé
    title = "20" + CONTENT[0][9:19] + ".txt"
    
    with open(PATH_EVENEMENT +'/'+ title, 'w') as g:
        #première ligne obligatoire
        g.write("# Snuffler Markers File Version 0.2\n")
        
        #ça fait la seconde ligne. Là où on a l'event
        g.write(event(CONTENT))
        
        #ça le fait le nombre d'événement (ok pour phase)
        for line in CONTENT:
            #on saute les lignes vides
            if line.strip(): 
                #print("ligne : ", line.strip())
                g.write(phase(line))
                
                
    return (0)

#On commence par créer notre dictionnaire des pointés
FILE_TEST = os.path.join(PATH_PHASE, "2014-05-295.txt")
picks = parse_phase_file(FILE_TEST)
if not picks:
    print("Aucun pointé trouvé dans le fichier de phase.")
if main(FILE_TEST):
    print("Impossible de traiter le fichier, erreur dans la fonction parse_phase_file()")
    
else:
        print("picks : ",picks,"\n")
        pattern(picks)
print("PROGRAMME FINI")

