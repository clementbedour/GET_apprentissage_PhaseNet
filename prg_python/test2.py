from genericpath import exists
import os
from datetime import datetime, timedelta, timezone
import glob
import re 

# Fichier ou il faut regarder les phases et les mettres sous le bon format
PATH_PHASE = "../data/phase_vt/"

# Répertoire où on va créer les docs
PATH_EVENEMENT = "../data/phase_evenement"
PATH_DATA = "../data/2014/MQ/"
PATH_CATALOG = "../data/phase_evenement_doc/2014.CATALOG.txt"

CHANNEL_PATTERN = '*H*'
title = ""
unique_stations = [] 

# On s'assure que le répertoire de sortie existe dès le début
if not exists(PATH_EVENEMENT):
    os.makedirs(PATH_EVENEMENT)

def event(content):
    # 1. On cherche l'identifiant .mq0 dans le fichier de phase
    event_id = None
    for line in content:
        match = re.search(r'\S+\.mq0', line)
        if match:
            event_id = match.group(0)
            break
            
    if not event_id:
        raise ValueError("Aucun identifiant '.mq0' trouvé dans le fichier de phase.")
        
    # 2. On cherche la ligne correspondante dans le catalogue
    catalog_parts = None
    try:
        with open(PATH_CATALOG, 'r') as f:
            for line in f:
                parts = line.split()
                if parts and parts[-1] == event_id:
                    catalog_parts = parts
                    break
    except FileNotFoundError:
        raise FileNotFoundError(f"Le fichier catalogue est introuvable à l'adresse : {PATH_CATALOG}")

    if not catalog_parts:
        raise ValueError(f"L'événement {event_id} n'a pas été trouvé dans le catalogue.")

    # 3. Extraction et parsing des données du catalogue
    raw_date  = catalog_parts[0]  
    raw_time  = catalog_parts[1]  
    raw_sec   = catalog_parts[2]  
    raw_lat   = catalog_parts[3]  
    raw_lon   = catalog_parts[4]  
    raw_depth = catalog_parts[5]  
    raw_mag   = catalog_parts[7]  

    date_formatted = f"{raw_date[0:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
    try:
        sec_float = float(raw_sec)
        time_formatted = f"{raw_time[0:2]}:{raw_time[2:4]}:{sec_float:07.4f}"
    except ValueError:
        time_formatted = f"{raw_time[0:2]}:{raw_time[2:4]}:{raw_sec}"

    def to_decimal(coord_str, is_longitude=False):
        is_neg = False
        if coord_str.startswith('-'):
            is_neg = True
            coord_str = coord_str[1:]
        
        if '-' in coord_str:
            p = coord_str.split('-')
            deg = float(p[0])
            minutes = float(p[1])
            val = deg + (minutes / 60.0)
        else:
            val = float(coord_str)
            
        if is_neg:
            val = -val
        if is_longitude and val > 0:
            val = -val
        return val

    try:
        lat = to_decimal(raw_lat)
        lon = to_decimal(raw_lon, is_longitude=True)
        depth = float(raw_depth)
        mag = float(raw_mag)
    except Exception as e:
        raise ValueError(f"Erreur de conversion numérique des données catalogue : {e}")

    event_id_short = event_id.replace('.mq0', '')
    event_line = f"event: {date_formatted} {time_formatted}  0 {event_id_short}  {lat:.4f}  {lon:.4f}  {depth:.2f}  {mag:.2f}  None  M={mag:.2f}  None\n"
    return event_line


def parse_phase_file(filepath):
    picks = []
    with open(filepath, 'r') as f:
        for line in f:
            if not line[0:3].strip(): 
                continue
                
            id_station = line[0:3].strip()
            p_date_time_station = line[9:24].strip()
            
            p_date_time_station = list(p_date_time_station)
            for i in (range(len(p_date_time_station))):
                if p_date_time_station[i] == " ":
                    p_date_time_station[i] = "0"
            p_date_time_station = "".join(p_date_time_station)

            try:
                p_date_time_station_format = datetime.strptime(p_date_time_station, "%y%m%d%H%M%S.%f").replace(tzinfo=timezone.utc)
                picks.append({'station': id_station, 'phase': 'P', 'time': p_date_time_station_format.timestamp(), 'datetime': p_date_time_station_format})
            except ValueError:
    # On affiche ce que le script a tenté de lire entre les colonnes 9 et 24
                print(f" -> Problème format P sur '{p_date_time_station}' dans {os.path.basename(filepath)}")
                continue
            
            s_time = line[31:36].strip()
            if s_time:
                try:
                    s_sec = float(s_time)
                    p_sec = float(line[19:24].strip())
                    
                    if p_sec > s_sec: 
                        s_delta = timedelta(seconds=s_sec, minutes=1)
                    else : 
                        s_delta = timedelta(seconds=s_sec, minutes=0)
                    
                    s_date_time_station_format = p_date_time_station_format.replace(second=0, microsecond=0) + s_delta
                    picks.append({'station': id_station, 'phase': 'S', 'time': s_date_time_station_format.timestamp(), 'datetime': s_date_time_station_format})
                except ValueError:
                    print(f" -> Problème format S sur une ligne de {os.path.basename(filepath)}")
                    pass
    return picks


def pattern(picks, g):
    event_date = picks[0]['datetime'] 
    year = event_date.strftime('%Y')  
    jday = event_date.strftime('%j')  
    
    unique_stations = list(dict.fromkeys([station['station'] for station in picks]))
    chosen_picks = {}
    
    for id_station in unique_stations:
        mseed_pattern = os.path.join(PATH_DATA, id_station, f"*.{id_station}.*.{CHANNEL_PATTERN}.D.{year}.{jday}.mseed")
        matching_files = glob.glob(mseed_pattern)
        
        station_picks = [p for p in picks if p['station'] == id_station]
        
        if not matching_files:
            for pick in station_picks:
                key = (pick['datetime'], id_station, pick['phase'])
                component = "HHZ" if pick['phase'] == 'P' else "HHE"
                chosen_picks[key] = f"MQ.{id_station}.00.{component}"
            continue
        
        for filepath in matching_files:
            filename = os.path.basename(filepath)
            parts = filename.split('.')
            
            if len(parts) >= 4:
                net = parts[0]   
                sta = parts[1]   
                loc = parts[2]   
                cha = parts[3]   
                
                for pick in station_picks:
                    key = (pick['datetime'], id_station, pick['phase'])
                    if pick['phase'] == 'S':
                        if cha.endswith('Z'):
                            cha_s = cha[:-1] + 'E'  
                            chosen_picks[key] = f"{net}.{sta}.{loc}.{cha_s}"
                        else:
                            chosen_picks[key] = f"{net}.{sta}.{loc}.{cha}"
                    else:
                        if cha.endswith('E') or cha.endswith('N'):
                            cha_p = cha[:-1] + 'Z'  
                            chosen_picks[key] = f"{net}.{sta}.{loc}.{cha_p}"
                        else:
                            chosen_picks[key] = f"{net}.{sta}.{loc}.{cha}"

    lines_to_write = []
    for (pick_time, id_station, phase_type), station_code in chosen_picks.items():
        time_str = pick_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-2]
        phase = "phase: "
        line_str = f"{phase} {time_str}  0 {station_code} {None} {None} {None} {phase_type} {None} {False}\n"
        lines_to_write.append((pick_time, line_str))
    
    lines_to_write.sort(key=lambda x: x[0])
    for pick_time, line_str in lines_to_write:
        g.write(line_str)


def main(filename):
    global title
    CONTENT = []
    with open(filename, 'r') as f:
        for i in f:
            CONTENT.append(i)
    
    if not CONTENT or not CONTENT[0].strip():
        raise ValueError("La première ligne du fichier est vide ou absente.")

    # Nettoyage direct des espaces dans le titre au cas où
    title = "20" + CONTENT[0][9:19].replace(" ", "0") + ".txt"
    
    with open(os.path.join(PATH_EVENEMENT, title), 'w') as g:
        g.write("# Snuffler Markers File Version 0.2\n")
        g.write(event(CONTENT)) 
        
    return (0)


# --- BOUCLE D'AUTOMATISATION GLOBALE ---
if __name__ == "__main__":
    
    # Définition du chemin absolu pour le fichier de log (dans le dossier de sortie)
    path_NL = os.path.join(PATH_EVENEMENT, "NL.txt")
    
    # Sécurité : On vérifie d'abord si le dossier des phases existe
    if not os.path.exists(PATH_PHASE):
        print(f"ERREUR CRITIQUE : Le dossier '{PATH_PHASE}' est introuvable depuis cet emplacement.")
        with open(path_NL, "w") as f_prob:
            f_prob.write(f"Dossier source introuvable : {os.path.abspath(PATH_PHASE)}\n")
    else:
        for filename in os.listdir(PATH_PHASE):
            old_path = os.path.join(PATH_PHASE, filename)
            
            if os.path.isdir(old_path) or filename.startswith("NL"):
                continue
                
            if re.search(r'[\s\xa0]', filename):
                new_filename = re.sub(r'[\s\xa0]+', '0', filename)
                new_path = os.path.join(PATH_PHASE, new_filename)
                try:
                    os.rename(old_path, new_path)
                    print(f"Renommé avec succès : '{filename}' -> '{new_filename}'")
                except Exception as e:
                    print(f"Impossible de renommer '{filename}' : {e}")

        # 2. TRAITEMENT : On liste les fichiers mis à jour
        all_files = [f for f in os.listdir(PATH_PHASE) if os.path.isfile(os.path.join(PATH_PHASE, f)) and not f.startswith("NL")]
        failed_files = [] 
        
        if not all_files:
            print(f"\nErreur : Aucun fichier trouvé à traiter dans le dossier {PATH_PHASE}")
        else:
            print(f"\n--- Début du traitement global ({len(all_files)} fichiers détectés) ---")
            
            for filename in sorted(all_files):
                filepath = os.path.join(PATH_PHASE, filename)
                #print(f"Traitement de : {filename}...")
                
                try:
                    picks = parse_phase_file(filepath)
                    if not picks:
                        raise ValueError("Aucun pointé valide trouvé dans le fichier de phase.")
                    
                    main(filepath)
                    
                    output_file = os.path.join(PATH_EVENEMENT, title)
                    with open(output_file, 'a') as g:
                        pattern(picks, g)
                        
                    print(f" -> Réussi ! Fichier créé : {title}")
                    
                except Exception as e:
                    print(f" -> ÉCHEC : {e}")
                    failed_files.append((filename, str(e)))

            # 3. CRÉATION DU RAPPORT "NL.txt" DANS LE DOSSIER DE SORTIE
            with open(path_NL, "w") as f_prob:
                if failed_files:
                    f_prob.write("Voici la liste des fichiers qui n'ont pas pu être convertis :\n")
                    f_prob.write("Il n'y a probablement pas de correspondance dans le catalogue\n\n")
                    for fname, error_msg in failed_files:
                        f_prob.write("-" * 40 + "\n")
                        f_prob.write(f"Fichier : {fname}\n")
                    print(f"\n[ATTENTION] Tous les dates des centres n'ont pas été trouvé. Le fichier NL est ici : {os.path.abspath(path_NL)}")
                else:
                    f_prob.write("Aucun problème détecté ! Tous les fichiers ont été convertis avec succès.\n")
                    print(f"\n--- TOUS LES FICHIERS ONT ÉTÉ TRAITÉS AVEC SUCCÈS. NL disponible ici : {os.path.abspath(path_NL)} ---")