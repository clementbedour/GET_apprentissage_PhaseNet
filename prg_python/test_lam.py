from obspy import read
import os

fichiers = [
    "../data/2014/MQ/LAM/MQ.LAM.00.HHZ.D.2014.063.mseed",
    "../data/2014/MQ/IA2/MQ.IA2.00.EHZ.D.2014.063.mseed"
]

for f in fichiers:
    if os.path.exists(f):
        print(f"\nLecture de : {f}")
        try:
            st = read(f)
            print(st)
        except Exception as e:
            print(f"Erreur avec ObsPy : {e}")
    else:
        print(f"Fichier non trouvé : {f}")