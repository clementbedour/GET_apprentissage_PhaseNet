import h5py
from obspy import read
import os
from genericpath import exists
#------------------------------
#Inutile, juste pour vérifier si on a pas triplé les composantes
#------------------------------

#repertoire à verifier
repertoire='PCM'
# Chemin du répertoire que vous souhaitez explorer
chemin = '../data/2014/MQ/'+repertoire

#création repertoire d'ecriture
if not exists("../data/trace"):
    os.mkdir("../data/trace")


#fichier ou j'ecris mon résultat
fichier='../data/trace/'+repertoire+'.txt'
# Obtenir la liste de tous les fichiers et dossiers
contenu = os.listdir(chemin)
# Afficher le contenu
for element in contenu:
    nom_fichier = chemin+"/"+element;
    print(nom_fichier);
    st = read(nom_fichier);
    
    contenu = st[0]
    with open(fichier, 'a') as f:
        f.write(str(contenu)+'\n')
        print(nom_fichier)