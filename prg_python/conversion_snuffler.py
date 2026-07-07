from datetime import datetime, timedelta
import base64
import hashlib

def generer_id_unique(station, date_str):
    # Génère un ID unique similaire à celui de Snuffler (base64)
    graine = f"{station}_{date_str}".encode('utf-8')
    return base64.b64encode(hashlib.md5(graine).digest()[:16]).decode('utf-8').replace('=', '') + '=='

def convertir_fichier_phase(fichier_entree, fichier_sortie, temps_origine_evenement=None):
    with open(fichier_entree, 'r') as f:
        lignes = f.readlines()
        
    marqueurs = []
    entete_ajoutee = False
    
    # Étape 1 : Analyser le fichier pour trouver la date de base et les stations
    for ligne in lignes:
        if not ligne.strip():
            continue
        
        elements = ligne.split()
        if len(elements) < 5:
            continue
            
        station = elements[0]
        phase_p = elements[1] # ex: EP
        # elements[2] est souvent la qualité/poids
        date_brute = elements[3] # ex: 1405280555
        try:
            sec_p = float(elements[4]) # ex: 2.46
        except ValueError:
            continue

        # Convertir la date brute en objet datetime (Ajout de 2000 pour l'année)
        date_base = datetime.strptime("20" + date_brute, "%Y%m%d%H%M")
        
        # Calcul du temps exact de la phase P
        temps_p = date_base + timedelta(seconds=sec_p)
        temps_p_str = temps_p.strftime("%Y-%m-%d %H:%M:%S.%f")[:-2] # Garde 4 décimales
        
        # Format de la ligne de phase pour Snuffler
        # Note : MQ.{station}.91.EHZ est un exemple, à adapter selon votre réseau (Réseau.Station.Emplacement.Canal)
        ligne_snuffler_p = f"{temps_p_str}  0 MQ.{station}.91.EHZ"
        marqueurs.append((temps_p, ligne_snuffler_p))
        
        # Vérifier s'il y a une phase S (ex: 2.98ES) sur la même ligne
        for el in elements[5:]:
            if 'ES' in el:
                try:
                    # On extrait les chiffres avant 'ES'
                    sec_s = float(el.replace('ES', ''))
                    temps_s = date_base + timedelta(seconds=sec_s)
                    temps_s_str = temps_s.strftime("%Y-%m-%d %H:%M:%S.%f")[:-2]
                    ligne_snuffler_s = f"{temps_s_str}  0 MQ.{station}.91.EHN" # EHN ou EHE pour la S
                    marqueurs.append((temps_s, ligne_snuffler_s))
                except ValueError:
                    pass

    # Étape 2 : Trier les marqueurs par ordre chronologique
    marqueurs.sort(key=lambda x: x[0])
    
    # Étape 3 : Insérer l'événement principal
    # Si aucun temps d'origine n'est donné, on prend par défaut 0.5s avant la première phase P
    if temps_origine_evenement is None and marqueurs:
        temps_origine_evenement = marqueurs[0][0] - timedelta(seconds=0.0)
        
    if temps_origine_evenement:
        t_orig_str = temps_origine_evenement.strftime("%Y-%m-%d %H:%M:%S.%f")[:-2]
        id_ev = generer_id_unique("EVENT", t_orig_str)
        # Ligne complexe de l'événement
        ligne_event = f"event: {t_orig_str}  0 {id_ev}         0.0          0.0 None         None None  Mon_Evenement None"
        
        # Trouver la bonne position chronologique pour insérer l'événement
        insere = False
        for i, (t, _) in enumerate(marqueurs):
            if t > temps_origine_evenement:
                marqueurs.insert(i, (temps_origine_evenement, ligne_event))
                insere = True
                break
        if not insere:
            marqueurs.append((temps_origine_evenement, ligne_event))

    # Étape 4 : Écriture du fichier final
    with open(fichier_out, 'w') as f_out:
        f_out.write("# Snuffler Markers File Version 0.2\n")
        for _, ligne in marqueurs:
            f_out.write(ligne + "\n")

# --- COMMENT L'UTILISER ---
if __name__ == "__main__":
    fichier_in = "mon_nouveau_fichier_de_phase.txt"
    fichier_out = "evenement_markers.txt"
    
    # Optionnel : Définir explicitement le temps d'origine si vous le connaissez (AAAA, MM, JJ, HH, MM, SS, Microsec)
    # Si laissé à None, le script le calculera automatiquement avant la première arrivée.
    temps_origine = datetime(2014, 5, 28, 5, 5, 2, 41100) 
    
    convertir_fichier_phase(fichier_in, fichier_out, temps_origine_evenement=None)
    print(f"Fichier de marqueurs Snuffler créé avec succès : {fichier_out}")