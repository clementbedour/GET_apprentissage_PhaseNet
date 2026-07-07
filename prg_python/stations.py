from obspy import read
import os
from genericpath import exists

chemin = "../data/station/"

with open(chemin + "bb_mq.xy", 'r') as f:
    texte1 = f.read()

with open(chemin+"cp_mq.xy", 'r') as f:
    texte2 = f.read()

with open(chemin+"all_station.txt",'w') as f:
        f.write(texte1 + texte2)