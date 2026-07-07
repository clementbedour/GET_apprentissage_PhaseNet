import h5py
from obspy import read
import os

#repertoire à verifier
repertoire='SAM'
# Chemin du répertoire que vous souhaitez explorer
chemin = '../data/mseed/'+repertoire
#fichier ou j'ecris mon résultat
fichier='../data/trace/'+repertoire+'.txt'
# Obtenir la liste de tous les fichiers et dossiers
contenu = os.listdir(chemin)
# Afficher le contenu
i=0
for element in contenu:
    nom_fichier = chemin+"/"+element;
    st = read(nom_fichier);
    
    contenu = st[0]
    with open(fichier, 'a') as f:
        f.write(str(contenu)+'\n')
        i=i+1
        print(nom_fichier)
        print(i)
