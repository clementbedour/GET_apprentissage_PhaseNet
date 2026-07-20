#requête pour WI.SAM
#http://ws.ipgp.fr/fdsnws/station/1/query?network=WI&station=SAM&level=station&format=text

#requête pour MQ.BAM
#http://ws.ipgp.fr/fdsnws/station/1/query?network=MQ&station=BAM&level=station&format=text

import urllib.request
import urllib.error
import os

#Génére les fichiers CSV pour toutes les stations
#Je prend le fichier station (dans data/station) avec comme nom "all_station_2"
#Je fais les requêtes dans IPGP (je prend les latitudes et longitudes dans les requêtes. Donc pas forcément les mêmes que dans le fichier station)
#Création dans data/csv

PATH_STATION = "../data/station/all_station_2"

GEOCSV_HEADER = """#dataset: GeoCSV 2.0
#delimiter: |
#field_unit: unitless | unitless | degrees_north | degrees_east | meters | unitless | ISO_8601 | ISO_8601
#field_type: string | string | float | float | float | string | datetime | datetime
Network|Station|Latitude|Longitude|Elevation|SiteName|StartTime|EndTime
"""

def get_fdsn_metadata(network, station):
    """
    Requête sur IPGP pour récupérer les metadatas
    """
    url = f"http://ws.ipgp.fr/fdsnws/station/1/query?network={network}&station={station}&level=station&format=text"
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            data = response.read().decode('utf-8').strip()
            lines = data.split('\n')
            if len(lines) >= 2:
                #on retourne la seconde ligne de données (la première est déjà noté dans GEOCSV_HEADER)
                #print(lines[1])
                return lines[1].strip()
    except urllib.error.HTTPError as e:
        print(f"[{network}.{station}] Erreur HTTP {e.code} - Station introuvable sur l'IPGP.")
    except Exception as e:
        print(f"[{network}.{station}] Erreur de connexion : {e}")
    return None

def main():
    #verification si fichier station existe
    if not os.path.exists(PATH_STATION):
        print(f"Erreur : Le fichier '{PATH_STATION}' est introuvable.")
        return 1
    
    print("Lecture des stations\n")
    with open(PATH_STATION, 'r') as f:
        lines = f.readlines()
    
    for line in lines:
        #on ignore les lignes de composantes, elles commencent par un espace
        if line.startswith(' '):
            continue
            
        parts = line.strip().split()
        if not parts:
            continue
            
        code = parts[0] #on recupere le premier indice (MQ.BAM.91)
        if '.' in code: #on decoupe pour bon format
            net_sta_loc = code.split('.')
            network = net_sta_loc[0]
            station = net_sta_loc[1]
            
            net_sta = network + "." + station
            print("Recherche des métadonnées pour",net_sta)
            fdsn_data = get_fdsn_metadata(network, station)
            
            if fdsn_data:
                #print("fdsn_data : ",fdsn_data,"\n")
                if "T00:00:00|" in fdsn_data: #pour ressembler au fichier de base
                    fdsn_data = fdsn_data.replace("T00:00:00|", "T00:00:00.0000|")
                
                filename = "../data/csv/"+station +".csv"
                with open(filename, 'w',) as out_f:
                    out_f.write(GEOCSV_HEADER)
                    out_f.write(fdsn_data + "\n")
                
                print("     Création réussie : ",filename,"\n")
            else:
                print("     Échec pour ",net_sta," Fichier sauté. \n")

if __name__ == '__main__':
    main()