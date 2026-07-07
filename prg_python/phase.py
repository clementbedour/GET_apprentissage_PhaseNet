import h5py
from obspy import read
import os
from genericpath import exists


#------------------------------
#Je prend un fichier phase (genre 2014-03) et je split tout les ' 10\n'
#pour séparer tout les différents événements
#puis je trie les différents événements dans différents repertoire (vt,lp,pas_classe)
#------------------------------


#Il faut avoir fait la fonction split_phase() avant OBLIGE
#Je regarde chaque événement, et je regarde si la chaîne ' V' ou ' T'  apparaît
#Je les regroupes tous dans un repertoire classé. 
#Nous pouvons avoir jusqu'à 3 repertoires (vt,lp,pas_classe)
def evenement_particulie():
    chemin = '../data/phase_separe'
    contenu = os.listdir(chemin)
    
    vt=0
    #lp=0
    #pas_classe=0
    
    #ici boucle sur les fichiers separé mais pas trié
    for element in contenu:
        nom_fichier = element
        fichier_lu = chemin + '/' + nom_fichier
        with open(fichier_lu, 'r') as f:
            texte = f.read()
            
            # Vérifier si la sous-chaine se trouve dans la chaine principale 
            #Ici tout les fichiers avec VA1, VE1, VB, ...
            if " V" in texte:
                vt = vt+1
                if not exists("../data/phase_vt"):
                    os.mkdir("../data/phase_vt")
                    
                with open("../data/phase_vt"+"/" +element, 'w') as f:
                    f.write(str(texte))
                    
            #Ici tout les fichiers avec TA1, TE1, TB, ...
            elif " T" in texte :
                #Si on veux que les LP alors on décommente les lignes suivantes
                #lp = lp+1
                if not exists("../data/phase_lp"):
                    os.mkdir("../data/phase_lp")
                with open("../data/phase_lp"+ "/"+element, 'w') as f:
                    f.write(str(texte))
                    
            
            #Si on veux tout les autres événements (LP + non classé ou juste non classé)
            #alors on décommande les lignes suivantes
            #else :
                #pas_classe = pas_classe +1
                #if not exists("../data/phase_pas_classe"):
                    #os.mkdir("../data/phase_pas_classe")
                #with open("../data/phase_pas_classe"+ "/"+element, 'w') as f:
                    #f.write(str(texte))

    print("Nombre de VT",vt)
    #print("Nombre de LP",lp)
    #print("Nombre de pas_classe",pas_classe)
    #print("Total",vt+lp+pas_classe)






#Cette fonction va split tout les différents événements dans un fichier
#Sans différencier si c'est un VT ou LP ou pas classé
#Attention il faut avoir un fichier avec data et prg_python dans le même repertoire
#Dans prg_python avoir ce code
#Dans data avoir un repertoire "phase" avec directement les fichiers .txt des phases
def split_phase():
    chemin = '../data/phase'

    #ici boucle pour tout les fichiers de phase pas separé
    contenu = os.listdir(chemin)
    for element in contenu:

        nom_fichier = element
        fichier_lu = chemin+'/'+ nom_fichier
        fichier_ecrit = '../data/phase_separe/' + nom_fichier.strip('.txt')

        #creation du repertoire d'ecriture
        if not exists("../data/phase_separe"):
            os.mkdir("../data/phase_separe")

        with open(fichier_lu, 'r') as f:
            content = f.read()
            lines = content.split(' 10\n')
            #print(f"Nombre de ligne: {len(lines)}")

            for i in range(len(lines)) :
                fichier_ecrit_i = fichier_ecrit + '-' + str(i+1) +'.txt'
                with open(fichier_ecrit_i, 'w') as f:
                    f.write(str(lines[i])+'\n')
                print(i)

def trier_magnitude(nom_repertoire):
    #Il faut, au moins avoir fait obligatoirement split_phase()
    #Nous ne somme pas obligé de garder le VT ou LP mais forcément 1 fichier par événement
    #@param le nom du repertoire sur lequel on va classer les magnitudes

    chemin = nom_repertoire
    contenu = os.listdir(chemin)
    
    #repertoire ou tout sera rangé
    if not exists("../data/phase_magnetude"):
            os.mkdir("../data/phase_magnetude")
    
    #faire changer la range si magnétude plus grande
    #vous pouver verifier ça dans le repertoire ../data/phase_magnetude/M=?
    for i in range(3) :
        if not exists("../data/phase_magnetude/M="+str(i)):
            os.mkdir("../data/phase_magnetude/M="+str(i))
    
    if not exists("../data/phase_magnetude/M=autre"):
        os.mkdir("../data/phase_magnetude/M=autre")
    
    #element est l'ensemble des fichiers que nous allons regarder
    #m=m0=m1=m2=0
    for element in contenu:
        with open(chemin + element, 'r') as f:
            content = f.read()
            
            #magnétude [0.0 ; 0.9]
            if "M=0" in content:
                #m0=m0+1
                fichier_ecrit_i = "../data/phase_magnetude/M=0/" + element
                with open(fichier_ecrit_i, 'w') as f:
                    f.write(str(content))
            
            
            #magnetude [1.0 ; 1.9]
            elif "M=1." in content:
                #m1=m1+1
                fichier_ecrit_i = "../data/phase_magnetude/M=1/" + element
                with open(fichier_ecrit_i, 'w') as f:
                    f.write(str(content))
                    
            
            #magnetude [2.0 ; 2.9]
            elif "M=2" in content:
                #m2=m2+1
                fichier_ecrit_i = "../data/phase_magnetude/M=2/" + element
                with open(fichier_ecrit_i, 'w') as f:
                    f.write(str(content))

            #tout les autres
            else :
                #m=m+1
                fichier_ecrit_i = "../data/phase_magnetude/M=autre/" + element
                with open(fichier_ecrit_i, 'w') as f:
                    f.write(str(content))
                    
    #print("m0 =",m0)
    #print("m1 =",m1)
    #print("m2 =",m2)
    #print("m =",m)

#split_phase()
evenement_particulie()
#trier_magnitude("../data/phase_vt/")