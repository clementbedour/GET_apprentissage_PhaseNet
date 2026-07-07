import os
import glob
from datetime import datetime, timedelta, timezone

# --- PARAMÈTRES ET CHEMINS ---
PATH_PHASE = "../data/phase_vt/"
PATH_EVENEMENT = "../data/phase_evenement"
PATH_STATIONS = "../data/station/all_station_2" # Ton fichier contenant toutes les stations

# Paramètres par défaut de l'événement (vu que les coordonnées ne sont pas dans les fichiers de phase)
EVENT_LAT = "14.811"
EVENT_LON = "-61.167"
EVENT_DEPTH = "2500.0"
EVENT_MAG = "1.2"

if not os.path.exists(PATH_EVENEMENT):
    os.makedirs(PATH_EVENEMENT)

def load_station_map(filepath):
    """
    Lit le fichier all_station_2.txt et génère dynamiquement 
    le dictionnaire de mapping NSLC pour chaque station.
    """
    nslc_map = {}
    current_station = None
    current_net_sta_loc = None
    
    with open(filepath, 'r') as f:
        for line in f:
            line_stripped = line.strip('\n')
            if not line_stripped:
                continue
            
            # Si la ligne ne commence pas par un espace, c'est une ligne d'en-tête de station
            if not line.startswith(' ') and not line.startswith('\t'):
                parts = line_stripped.split()
                # Exemple : "MQ.BAM.91 14.81708 -61.14453 674 0.0 BAM"
                current_net_sta_loc = parts[0] # "MQ.BAM.91"
                current_station = parts[-1]    # "BAM"
                nslc_map[current_station] = {'P': [], 'S': []}
            
            # Sinon, c'est une ligne de canal de la station courante
            elif current_station is not None:
                parts = line_stripped.split()
                channel = parts[0] # Exemple : "EHZ" ou "HHE"
                full_nslc = f"{current_net_sta_loc}.{channel}"
                
                # Assignation P (Z) et S (E, N)
                if channel.endswith('Z'):
                    nslc_map[current_station]['P'].append(full_nslc)
                elif channel.endswith('E') or channel.endswith('N'):
                    nslc_map[current_station]['S'].append(full_nslc)

    # Gestion de secours : si une station n'a pas de composante horizontale (S vide)
    # on copie la composante verticale (P) pour pouvoir quand même inscrire la phase S si elle existe
    for sta, phases in nslc_map.items():
        if not phases['S'] and phases['P']:
            phases['S'] = phases['P'].copy()
        if not phases['P'] and phases['S']:
            phases['P'] = phases['S'].copy()
            
    return nslc_map

def format_snuffler_datetime(dt):
    # Formate le datetime au format attendu par Snuffler: YYYY-MM-DD HH:MM:SS.ssss
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:24]

def parse_phase_file(filepath):
    """Extrait les pointés P et S d'un fichier de phase spécifique."""
    picks = []
    
    with open(filepath, 'r') as f:
        for line in f:
            if not line[0:3].strip():
                continue
                
            id_station = line[0:3].strip()
            
            # Correction des espaces vides dans les dixièmes/secondes
            p_str = list(line[9:24].strip())
            for i in range(len(p_str)):
                if p_str[i] == " ":
                    p_str[i] = "0"
            p_str = "".join(p_str)

            try:
                p_datetime = datetime.strptime(p_str, "%y%m%d%H%M%S.%f").replace(tzinfo=timezone.utc)
                picks.append({'station': id_station, 'phase': 'P', 'datetime': p_datetime})
            except ValueError:
                print(f"[{filepath}] Problème de format P ignoré : {line.strip()}")
                continue
            
            # Phase S
            s_time = line[31:36].strip()
            if s_time:
                try:
                    s_sec = float(s_time)
                    p_sec = float(line[19:24].strip())
                    
                    minutes_add = 1 if p_sec > s_sec else 0
                    s_delta = timedelta(seconds=s_sec, minutes=minutes_add)
                    
                    s_datetime = p_datetime.replace(second=0, microsecond=0) + s_delta
                    picks.append({'station': id_station, 'phase': 'S', 'datetime': s_datetime})
                except ValueError:
                    pass # Ignore silencieusement s'il n'y a pas de S valide

    return picks

def create_snuffler_file(picks, output_filepath, nslc_map):
    """Génère le fichier formaté pour Snuffler."""
    if not picks:
        return False

    # Génère un ID unique pour l'événement basé sur la date du premier pointé
    event_origin = picks[0]['datetime'] - timedelta(seconds=0.4189)
    event_id = f"EV_{event_origin.strftime('%Y%m%d%H%M%S')}"
    
    event_date_str = format_snuffler_datetime(event_origin)
    event_day_str = event_origin.strftime("%Y-%m-%d")
    
    with open(output_filepath, 'w') as f:
        f.write("# Snuffler Markers File Version 0.2\n")
        f.write(f"event: {event_date_str} 0 {event_id} {EVENT_LAT} {EVENT_LON} {EVENT_DEPTH} {EVENT_MAG} None {event_day_str} None\n")
        
        for pick in picks:
            station = pick['station']
            phase = pick['phase']
            pick_time_str = format_snuffler_datetime(pick['datetime'])
            
            # Récupération dynamique depuis la map de stations générée
            # Fallback (au cas où la station n'est pas dans all_station_2.txt)
            nslc_list = nslc_map.get(station, {}).get(phase, [f"MQ.{station}..EHZ"]) 
            
            for nslc in nslc_list:
                line = f"phase: {pick_time_str}  0 {nslc:<15} {event_id}   {event_day_str}   {event_origin.strftime('%H:%M:%S.%f')[:13]} {phase}        None False\n"
                f.write(line)
                
    return True

def main():
    # 1. Chargement de la configuration des stations
    if not os.path.exists(PATH_STATIONS):
        print(f"Fichier station introuvable : {PATH_STATIONS}")
        return
        
    print(f"Chargement des stations depuis {PATH_STATIONS}...")
    nslc_map = load_station_map(PATH_STATIONS)
    print(f"{len(nslc_map)} stations chargées avec succès.")

    # 2. Recherche de tous les fichiers de phase dans le dossier
    phase_files = glob.glob(os.path.join(PATH_PHASE, "*.txt"))
    if not phase_files:
        print(f"Aucun fichier .txt trouvé dans {PATH_PHASE}")
        return

    # 3. Boucle de traitement sur tous les fichiers trouvés
    print(f"{len(phase_files)} fichiers de phases trouvés. Début du traitement...")
    
    for filepath in phase_files:
        filename = os.path.basename(filepath)
        picks = parse_phase_file(filepath)
        
        if not picks:
            print(f"  -> Ignoré : {filename} (aucun pointé valide)")
            continue
            
        # Création du nom de sortie (ex: 20140528_055502.txt)
        output_filename = picks[0]['datetime'].strftime("%Y%m%d_%H%M%S.txt")
        output_filepath = os.path.join(PATH_EVENEMENT, output_filename)
        
        if create_snuffler_file(picks, output_filepath, nslc_map):
            print(f"  -> OK : {filename} converti en {output_filename}")
        else:
            print(f"  -> Erreur lors de la création pour : {filename}")

    print("\nPROGRAMME FINI. Tous les fichiers ont été traités.")

if __name__ == '__main__':
    main()