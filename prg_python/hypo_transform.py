import numpy as np
from datetime import datetime
from pyproj import Transformer
from datetime import datetime, timedelta, timezone
import hypo
# faire git clone https://github.com/groupeLIAMG/hypopy/tree/master
#puis pip install ttcrpy vtk scipy matplotlib pyproj numpy 


# ---------------------------------------------------------------
# CONSTANTE

PATH_STATION='../data/station/all_station_2'
PATH_PHASE = '../data/phase_evenement/20140528T555_b (2)'
HASH = ""
Vp = 5.5   # km/s (cf question)
Vs = Vp / 1.66 #(cf question)
MAX_ITER = 20
CONVERG_CRIT = 0.001

# ---------------------------------------------------------------
# INIT et rangement des latitudes,longitudes et hauteur dans matrice rcv
# on a l'ordre des stations qui correspond avec sta_index
def read_stations(path):
    stations = {}  # key = (exemple)"MQ.BAM.91" -> (latitude, longitude, hauteur (en metre !!!))
    with open(path) as f:
        for line in f:
            if line.startswith(' ') or line.strip() == '':
                continue # on ignore car ligne vide
            parts = line.split()
            #print("parts : ",parts,"\n")
            code, lat, lon, elev = parts[0], float(parts[1]), float(parts[2]), float(parts[3])
            # on récupere la key et mets dans le dictionnaire les 3 coordonées de la station
            stations[code] = (lat, lon, elev)
            #print("stations dans read : ",stations,"\n")
    return stations




def read_snuffler(path):
    event = {}
    with open(path) as f:
        for line in f:
            if line.startswith('phase:'):
                p = line.split()
                date, time_ = p[1], p[2] #2014-05-20 13:16:36.6500
                id_comp = p[4] #MQ.GBM.91.EHZ
                hash = p[5] #key unique EV_20140520131636
                phase = p[8] #P ou S
                net, sta, loc, comp = id_comp.split('.')
                net_sta_loc = f"{net}.{sta}.{loc}"
                date_format = datetime.strptime(date + ' ' + time_, "%Y-%m-%d %H:%M:%S.%f")
                #on range ajoute au dico un élément dans le bon ordre. Attention il
                #faudra vérifier combien de hash différent on a (normalement qu'un seul)
                event.setdefault(hash,[]).append((net_sta_loc, phase, date_format))
    return event



#on récupere le dictionnaire rempli des stations
stations = read_stations(PATH_STATION)
#print("stations : ",stations,"\n")

#on trie les keys car voulu dans hypo je crois
#G puis MQ puis WI
sta_list = sorted(stations.keys())

#verification ou changement de zone géographique avec "https://epsg.io/"
#EPSG:4326 base world  latitude / longitude (en angles)
#EPSG:32620 UTM 20 Nord (petite antilles donc Martinique )
# always_xy=True si on a mettra dans l'ordre les données long/lat ou Est/Nord
to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32620", always_xy=True)

rcv = np.zeros((len(sta_list), 3))
sta_index = {}

#initialisation de la matrice rcv pour hypo
for i, code in enumerate(sta_list):
    lat, lon, elev = stations[code]
    x, y = to_utm.transform(lon, lat)
    rcv[i, 0] = x / 1000.0          # km
    rcv[i, 1] = y / 1000.0          # km
    rcv[i, 2] = -elev / 1000.0      # km, positif vers le bas -> station en altitude = z negatif
    sta_index[code] = i
#print("rcv apres for : ",rcv,"\n")
#print("sta_index apres for :",sta_index,"\n")
#print("sta_list apres for :",sta_list,"\n")

#for i in range(len(sta_list)) :
#    print("sta_index :",sta_index[sta_list[i]],"\n")


print("Récepteurs : code -> latitude,longitude,hauteur","\n")
for code, i in sta_index.items():
    print(f"  {i}: {code} -> {rcv[i]}")


#on créé un dico avec 
event = read_snuffler(PATH_PHASE)
HASH = list(event.keys())[0]

if (len(event)) == 1 :
    print(f"\n{len(event)} événement trouvé (normal) \n")
else :
    print("Problème, plusieurs event trouvé dans le fichier de phase :",PATH_PHASE,"\n")

# ---------------------------------------------------------------
# Construction data et hinit pour hyro
data_rows = []
hinit_rows = []

# position moyenne des stations = estimation initiale de l'epicentre (sans reflexion, purement bête)
# il faut un point de départ (mieux c plus ça sera opti)
x0, y0 = rcv[:, 0].mean(), rcv[:, 1].mean()
z0 = 0.7 #denivelé de 1.4 km donc /2

for eid, (ev_hash, picks) in enumerate(event.items()):
    print(eid, (ev_hash, picks))

for eid, (ev_hash, picks) in enumerate(event.items()):
    seen = set() #juste sécu, au cas ou que (station, phase) soit déjà traité.
    times = []
    for net_sta, phase, dt in picks:
        if net_sta not in sta_index:
            print(f"  ATTENTION: station {net_sta} absente du fichier stations, pick ignore")
            continue
        key = (net_sta, phase)
        if key in seen:
            continue  # deux composantes horizontales -> on ne garde qu'un pick S par station
        seen.add(key)
        ts = dt.timestamp()
        times.append(ts)
        phase_code = 0.0 if phase == 'P' else 1.0
        data_rows.append([eid, ts, sta_index[net_sta], phase_code])

    t0_guess = min(times) - 0.3   # estimation grossiere du temps origine
    hinit_rows.append([eid, t0_guess,
                        x0 + 0.01 * eid, y0 + 0.01 * eid, z0])  # perturbation pour eviter deux hypocentres identiques

data = np.array(data_rows)
hinit = np.array(hinit_rows)

print("\nTableau data (eid, t_arrivee, idx_recepteur, phase[0=P,1=S]):")
print(data)
print("\nTableau hinit (eid, t0, x, y, z):")
print(hinit)

# ---------------------------------------------------------------
# 4) LOCALISATION A VITESSE CONSTANTE (hypoloc.hypolocPS)
# ---------------------------------------------------------------

loc, res = hypo.hypolocPS(data, rcv, V=(Vp, Vs), hinit=hinit, maxit=MAX_ITER, convh=CONVERG_CRIT, verbose=True)

print("\nRESULTAT (eid, t0, x_km, y_km, z_km):")
print(loc)

# reconversion vers lat/lon
to_ll = Transformer.from_crs("EPSG:32620", "EPSG:4326", always_xy=True)
for row in loc:
    eid, t0, x, y, z = row
    lon, lat = to_ll.transform(x * 1000, y * 1000)
    print(f"Event {int(eid)}: lat={lat:.5f}, lon={lon:.5f}, prof={z:.3f} km, "
        f"t0={datetime.fromtimestamp(t0)}")