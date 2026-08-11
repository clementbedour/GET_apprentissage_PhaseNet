# Explication du projet

## Description
Ce répertoire a pour but d'automatiser et d'utiliser **SeisBench** et **PhaseNet** pour le traitement de signaux sismologiques. Il propose un pipeline complet allant de la préparation des données brutes et des pointages manuels, jusqu'à l'entraînement de modèles d'Intelligence Artificielle (from scratch puis par Fine-Tuning) et la génération de métriques d'évaluation.

---

## Étape 1 : Préparation des données et pointages (SeisBench / Snuffler)

Cette première phase permet de formater les données brutes et de valider visuellement les événements sismologiques.

*   **Découpage des événements :** Exécutez `phase.py` pour découper les fichiers d'événements mensuels (il devra être situés dans `data/phase`) en sous-fichiers individuels (générés dans `data/phase_separe`). Le script trie également les événements (par défaut, seuls les événements VT sont conservés dans `data/phase_vt`). Pour garder d'autres types d'événements, décommentez les lignes correspondantes dans la fonction `evenement_particulie()`. Il est aussi possible de les trier par magnitude avec la fonction  `trier_magnitude()` qui seront triés dans  `../data/phase_magnitude/M=0`, `../data/phase_magnitude/M=1`, ... 

*   **Formatage pour Snuffler :** Lancez `phase_to_evenement.py` pour créer des fichiers lisibles par l'outil de visualisation. Le script utilise la date d'origine présente dans `data/phase_evenement_doc/2014.CATALOG.txt`. Si un événement est introuvable ou non identifiable, la ligne `event:` sera vide et l'événement sera listé dans le fichier `NL.txt`. A la fin de ce script, vous aurez 1 fichier par événement présent dans le catalogue. Cette étape nécessite une configuration manuelle (les données `.mseed` doivent être dans `/data/2014/MQ`). Le chemin peut être changé à la ligne 8.

*   **Préparation des stations :** Assurez-vous d'avoir placé le fichier de configuration des stations (ex : `all_station_2`) dans le répertoire `data/station`. Puis, vous pouvez lancer `recup_csv.py` pour créer un fichier par station au bon format pour Snuffler.

*   **Affichage et correction :** Lancez `affichage_snuffler.py` pour visualiser les événements à la chaîne (-40s et +30s autour de la création de l'événement, changeable à la ligne 74 et 75). Vous pouvez spécifier un fichier précis pour commencer, ou appuyer sur Entrée pour démarrer au début.

*   **Sauvegarde des pointés :** Dans Snuffler, après vérification et/ou modification des pointés, faites *File -> Save Markers...* et enregistrez dans `/data/phase_snuffler` en utilisant le nom exact du fichier d'origine. Trouvable facilement dans la sortie du terminal à côté de "Traitement de ...".

*   **Gestion de la confiance :** Lors de l'enregistrement des pointés, je vous conseille fortement d'ajouter un suffixe de confiance `_a`, `_b`, `_c` ou `_d` (ou même `_dTE`). Attention, les pointés avec `_d` seront exclus des étapes suivantes.

*   **Reprise de session :** En quittant Snuffler, le terminal vous propose de continuer. Entrez `1` pour arrêter le programme (le dernier fichier traité s'affichera pour faciliter la reprise), ou laissez continuer jusqu'à la fin. Pour reprendre là où vous en étiez, relancer simplement `affichage_snuffler.py` en indiquant le dernier document traité.

*   **Bravo :** Félicitations !!! Vous avez fini de vérifier tous les pointés, ça peut être long mais c'est terminé.

---

## Étape 2 : Machine Learning (IA)

Tous les fichiers générés à cette étape seront stockés dans `data/seisbench`. Les poids des modèles entraînés seront sauvegardés dans `prg_python/seisbench`. En fonction des qualités choisies, la localisation des sauvegardes pourra légèrement différer (seisbenchB ou seisbenchA au lieu de seisbench).<br>
Pour tous les programmes suivants, nous devons rentrer comme paramètres le minimum de qualité voulu `a` (que les qualités a), `b` (les qualités a et b) ou `c`(les qualités a, b et c). Si aucun argument n'est donné, il prendra par défaut la qualité `c`.

*   **Création de la base "Ground Truth" :** Lancez `format_csv_hdf5.py <qualite>`. Cela génère `metadata.csv` et `waveform.hdf5` dans le répertoire `seisbench_format` à partir de vos pointés validés. Ce programme crée juste 2 fichiers pour être au bon format pour SeisBench.

*   **Génération du bruit :** Exécutez `gene_noise.py` pour créer la base de données de bruit dans `seisbench_format_noise`. L'ajustement des fenêtres STA/LTA se fait via la variable `STA_LTA_THRESHOLD`, valeur du rapport signal sur bruit (une valeur inférieure à 1.6 est déconseillée). La création du fichier sera forcément générée dans `data/seisbench`.

*   **Fusion pour l'entraînement initial :** Lancez `fusion_data.py <qualite>` pour combiner le Ground Truth et le bruit dans `seisbench_dataset`.

*   **Entraînement *From Scratch* (Modèle 1) :** Exécutez `IA_seisbench_Tuning.py 1 <qualite>`. Le modèle généré sera sauvegardé sous `prg_python/seisbench<qualite>/phasenet_volcan_v1.pt`. Les paramètres modifiables sont `SIGMA`, `EPOCHS`, `LEARNING_RATE` et `poids_classes` (de la ligne 47 à 56). Je trouve que seule la modification de `SIGMA` est nécessaire. Sauf si nous arrivons à la fin de l'exécution avec `EPOCHS`=300. Je n'ai pas trop modifié `poids_classes`, il peut être intéressant d'augmenter le bruit pour éviter les fausses détections.

*   **Détection de nouveaux événements :** Lancez `detection_nouv.py <qualite>` (processus le plus long). Il génère deux catalogues dans `seisbench_nouv` : un catalogue complet des VT détectés, et un catalogue filtré des VT valides. Vous pouvez ajuster les filtres `MIN_STATIONS` ligne 30, nombre de stations minimal pour le filtre multi-association (conseil : environ la moitié du nombre total des stations), `MIN_PROBA_EVENT` ligne 31, probabilités minimales pour l'enregistrement de l'événement (conseil : minimum 0.8). Ainsi que `THRESHOLD_P`,`THRESHOLD_S` ligne 16/17 pour la détection du pick (conseil : minimum 0.8).

*   **Extraction de la base "Gold" :** Exécutez `extraire_nouv.py <qualite>` pour formater les nouvelles détections validées dans `seisbench_format_gold`. A partir de ce moment, nous avons la base de données "Gold-Standar" qui ne contient que les meilleurs événements.

*   **Base de données ultime :** Lancez `fusion_dataset.py <qualite>` pour regrouper le Ground Truth, le Bruit et la base Gold dans `seisbench_dataset_ultime`.

*   **Affinement par Fine-Tuning (Modèle 2) :** Exécutez `IA_seisbench_Tuning.py 2 <qualite>` pour reprendre les poids du Modèle 1 et les affiner sur la base de données Gold. Les paramètres `EPOCHS`, `LEARNING_RATE` et `SIGMA` sont réduits par défaut pour cette étape de précision (ligne 60 à 62). Je trouve que les paramètres choisis sont optimaux pour ma base de données.

---

## Étape 2 bis : Machine Learning automatisé sur Serveur SSH

Pour les utilisateurs opérant sur le serveur SSH, l'intégralité du pipeline d'apprentissage (de la création de la base Ground Truth jusqu'au Fine-Tuning final) peut être exécutée via des scripts Bash.

*   **Pré-requis :** Lancez le script `scp.sh` qui permet de copier tous les fichiers du répertoire pour l'IA. Vous allez devoir modifier votre mot de passe et le chemin d'accès vers votre session.
*   **Commande :** Exécutez `sbatch batch_Singb` (il lancera tout pour la qualité `b` ), vous allez sûrement devoir modifier quelques lignes comme le nom et le nombre de coeurs que vous voulez réserver.
*   **Fonctionnement :** Le script prend en charge toute la chaîne et génère un fichier de type `output_classiqueb.out` pour suivre l'avancement. Que ce soit la réservation de ressources, et le lancement de toutes les fonctions. 

---

## Étape 3 : Affichage des résultats 

Le pipeline génère des graphiques de performance sans nécessiter d'affichage interactif. Toutes les images produites sont directement sauvegardées dans le répertoire `images/`.

*   **Visualisation des pointés de l'IA :** Lancez `test_IA.py 1 <qualite>` (pour le modèle 1) ou `test_IA.py 2 <qualite>` (pour le modèle 2) pour vérifier les distributions gaussiennes générées. La base de test est tirée aléatoirement à 10% du dataset global et reste invisible pour l'IA durant l'entraînement. La constante que vous pouvez changer est `SEUIL_PROB` à la ligne 69 pour afficher la probabilité minimale à enregistrer (conseil : rester à 0.8). Vous pouvez aussi modifier `NB_EXEMPLES_SAVE` ligne 74.

*   **Affichage fonction de perte :** Lancez `compare_trust.py 1 <qualite>` ou `compare_trust.py 1 <qualite>` pour vérifier l'évolution des courbes des pertes (courbes d'apprentissage) au fur et à mesure des epochs.

*   **Scores de confiance :** Lancez `metrics.py 1 <qualite>` ou `metrics.py 2 <qualite>` pour constater le score de confiance sur tous les événements détectés.

*   **Répartition temporelle :** Lancez `image_event_day.py <qualite>` pour visualiser la répartition du nombre de nouveaux événements découverts.

---

## Étape 4 : Base de données Volpick

Maintenant je vais essayer de faire la même chose mais en partant d'une base bien plus grande.<br>
Etude scientifique de référence **Volpick** ([https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2024GL108438](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2024GL108438)).<br>
En cours de programmation...