# Description du projet
Ce répertoire a pour but d'automatiser et d'utiliser **SeisBench** et **PhaseNet** pour le traitement de signaux sismologiques. Il propose un pipeline complet allant de la préparation des données brutes et des pointages manuels, jusqu'à l'entraînement de modèles d'Intelligence Artificielle (from scratch puis par Fine-Tuning) et la génération de métriques d'évaluation.<br>
**Contact :** Si vous avez des questions, vous pouvez me contacter sur [clementbedour@gmail.com](mailto:clementbedour@gmail.com).


## Table des matières
1. [Architecture du Projet](#architecture-du-projet)
2. [Étape 1 : Préparation des données et pointages (SeisBench / Snuffler)](#étape-1--préparation-des-données-et-pointages-seisbench--snuffler)
3. [Étape 2 : Machine Learning (IA)](#étape-2--machine-learning-ia)
4. [Étape 2 bis : Machine Learning automatisé sur Serveur SSH](#étape-2-bis--machine-learning-automatisé-sur-serveur-ssh)
5. [Étape 3 : Affichage des résultats](#étape-3--affichage-des-résultats)
6. [Étape 4 : Base de données Volpick](#étape-4--base-de-données-volpick)
7. [Tags](#les-tags)


## Architecture du Projet

Pour le bon fonctionnement des scripts, il est impératif de respecter cette structure. **Tous les codes doivent être lancés depuis le dossier `prg_python/`.**
```text
📦 GET_apprentissage_PhaseNet
 ┣ 📂 prg_python/             # Contient tous les scripts Python (à exécuter d'ici)
 ┃ ┣ 📜 phase.py
 ┃ ┣ 📜 IA_seisbench_Tuning.py
 ┃ ┣ ...
 ┃ ┣ 📂 seisbench<qualite>/   # Poids des modèles entraînés (.pt)
 ┃ ┗ 📂 volpick/              # Poids des modèles entraînés (.pt)
 ┣ 📂 data/                   # Dossier à créer par l'utilisateur :
 ┃ ┣ 📂 2014/MQ/              # Données brutes .mseed
 ┃ ┣ 📂 phase/                # Fichiers d'événements (journaliers, mensuels, annuels)
 ┃ ┣ 📂 phase_snuffler/       # Pointés corrigés manuellement (code pour l'affichage automatique disponible)
 ┃ ┣ 📂 station/              # Fichiers de configuration des stations
 ┃ ┗ 📂 seisbench<qualite>/   # Données générées par les scripts pour l'IA (HDF5, CSV)
 ┣ 📂 images/                 # Graphiques générés par l'Étape 3
 ┣ 📂 SSH/                    # Scripts Bash pour exécution sur serveur distant
 ┣ 📂 out/                    # Exemple de sortie du terminal
 ┗ 📜 README.md
```

---

## Étape 1 : Préparation des données et pointages (SeisBench / Snuffler)

Cette première phase permet de formater les données brutes et de valider visuellement les événements sismologiques.

*   **Découpage des événements :** Exécutez `phase.py` pour découper les fichiers d'événements mensuels (il devra être situés dans `data/phase`) en sous-fichiers individuels (générés dans `data/phase_separe`). Le script trie également les événements (par défaut, seuls les événements VT sont conservés dans `data/phase_vt`). Pour garder d'autres types d'événements, décommentez les lignes correspondantes dans la fonction `evenement_particulie()`. Il est aussi possible de les trier par magnitude avec la fonction  `trier_magnitude()` qui seront triés dans  `../data/phase_magnitude/M=0`, `../data/phase_magnitude/M=1`, ... 

*   **Formatage pour Snuffler :** Cette étape nécessite une configuration manuelle (les données `.mseed` doivent être dans `/data/2014/MQ`). Le chemin peut être changé à la ligne 8. Lancez `phase_to_evenement.py` pour créer des fichiers au bon format. Le script utilise la date d'origine présente dans `data/phase_evenement_doc/2014.CATALOG.txt`. Si un événement est introuvable ou non identifiable, la ligne `event:` ne sera pas présente et l'événement sera listé dans le fichier `NL.txt`. A la fin de ce script, vous aurez 1 fichier par événement présent dans `data/phase_vt` et la sortie sera dans le répertoire `data/phase_evenement/`.

*   **Préparation des stations :** Assurez-vous d'avoir placé le fichier de configuration des stations (ex : `all_station_2`) dans le répertoire `data/station`. Puis, vous pouvez lancer `recup_csv.py` pour créer un fichier par station au bon format pour Snuffler. Les fichiers seront créés dans `data/csv`.

*   **Affichage et correction :** Lancez `affichage_snuffler.py` pour visualiser les événements à la chaîne (-40s et +30s autour de la création de l'événement, changeable à la ligne 74 et 75). Vous pouvez spécifier un fichier précis pour commencer, ou appuyer sur Entrée pour démarrer au début.

*   **Sauvegarde des pointés :** Dans Snuffler, après vérification et/ou modification des pointés, faites *File -> Save Markers...* et enregistrez dans `/data/phase_snuffler` en utilisant le nom exact du fichier d'origine. Trouvable facilement dans la sortie du terminal à côté de "Traitement de ...".

*   **Gestion de la confiance :** Lors de l'enregistrement des pointés, je vous conseille fortement d'ajouter un suffixe de confiance `_a`, `_b`, `_c` ou `_d` (ou même `_dTE`). Attention, les pointés avec `_d` seront exclus des étapes suivantes.

*   **Reprise de session :** En quittant Snuffler, le terminal vous propose de continuer. Entrez `1` pour arrêter le programme (le dernier fichier traité s'affichera pour faciliter la reprise), ou laissez continuer jusqu'à la fin. Pour reprendre là où vous en étiez, relancer simplement `affichage_snuffler.py` en indiquant le dernier document traité.

*   **Bravo :** Félicitations !!! Vous avez fini de vérifier tous les pointés, c'était long mais c'est terminé.

---

## Étape 2 : Machine Learning (IA)

Tous les fichiers générés à cette étape seront stockés dans `data/seisbench<qualite>`. Les poids des modèles entraînés seront sauvegardés dans `prg_python/seisbench<qualite>`. En fonction des qualités choisies, la localisation des sauvegardes pourra légèrement différer (mais tout sera semblable à l'intérieur).<br>
Pour tous les programmes suivants, nous devons rentrer comme paramètres le minimum de qualité voulu `a` (que les qualités a), `b` (les qualités a et b) ou `c`(les qualités a, b et c). Si aucun argument n'est donné, il prendra par défaut la qualité `c`.<br>
Pour l'emplacement des miniseed, le chemin d'accés va probablement différé. La constante est toujours vers le début des programmes `BASE_MSEED`. Il faudra modifier les programmes format_csv_hdf5, gene_noise, detection_nouv.py et extraire_nouv.py.<br>
Tous les codes vont générer un fichier `metadata.csv` et `waveform.hdf5` (les noms ne sont malheureusement pas changeables, obligation SeisBench), je préciserais donc seulement le dossier où ils seront créés.

*   **Création de la base "Ground Truth" :** Lancez `format_csv_hdf5.py <qualite>`. Cela génère le répertoire `seisbench_format` à partir de vos pointés validés. Ce programme met au bon format nos pointés modifiés grâce à Snuffler pour utiliser SeisBench.

*   **Génération du bruit :** Il faut lancer `format_csv_hdf5.py c` avant si ça n'a pas été fait, c'est **obligatoire** pour ne pas trouver du bruit sur un événement, même avec une mauvaise qualité. Maintenant, exécutez `gene_noise.py`, pour créer la base de données de bruit dans `seisbench_format_noise`. L'ajustement des fenêtres STA/LTA se fait via la variable `STA_LTA_THRESHOLD`, valeur du rapport signal sur bruit (une valeur inférieure à 1.6 est déconseillée). La création du fichier sera forcément générée dans `data/seisbench` (peu importe la qualité).

*   **Fusion pour l'entraînement initial :** Lancez `fusion_data.py <qualite>` pour combiner le Ground Truth et le bruit dans `seisbench_dataset`. C'est notre première base de données (dataset) pour l'entraînement de notre modèle.

*   **Entraînement *From Scratch* (Modèle 1) :** Exécutez `IA_seisbench_Tuning.py 1 <qualite>`. Le modèle généré sera sauvegardé sous `prg_python/seisbench<qualite>/ml_model_v1.pt`. Les paramètres modifiables sont `SIGMA`, `EPOCHS`, `LEARNING_RATE` et `poids_classes` (de la ligne 47 à 56). Je trouve que seule la modification de `SIGMA` est nécessaire. Sauf si nous arrivons à la fin de l'exécution avec `EPOCHS`= 300 avant l'arrêt automatique. J'ai un peu modifié `poids_classes`, mais il peut être intéressant de le faire varier en fonction de la précision voulue pour votre catalogue (faux positif ou faux négatif).

*   **Détection de nouveaux événements :** Lancez `detection_nouv.py <qualite>` (processus le plus long). Si vous avez des stations avec une seule composante, il faudra les renseigner à la ligne 25 `STATIONS_MONO`. Il génère deux catalogues dans `seisbench_nouv` : un catalogue complet des VT détectés, et un catalogue filtré des événements valides.<br>
Vous pouvez ajuster les filtres `MIN_STATIONS` ligne 30, nombre de stations minimal pour le filtre multi-association (conseil : environ la moitié du nombre total des stations), `MIN_PROBA_EVENT` ligne 31, probabilités minimales pour l'enregistrement de l'événement (conseil : minimum 0.8). Ainsi que `THRESHOLD_P`,`THRESHOLD_S` ligne 16/17 pour la détection du pick (conseil : minimum 0.8 pour P et 0.3 pour S).<br>
Un autre paramètre pouvant être changé est `MAX_EVENT_DAY`. Il supprime entièrement la journée si, après les filtres et la multi-association, il y a plus de `MAX_EVENT_DAY` événements. J'ai choisi 200 assez arbitrairement.

*   **Extraction de la base "Gold" :** Exécutez `extraire_nouv.py <qualite>` pour mettre au bon format les nouvelles détections valides dans `seisbench_format_gold`. A partir de ce moment, nous avons la base de données "Gold-Standard" qui ne contient que les meilleurs événements.<br>
Vous avez la ligne `Événements/Traces connus RETROUVÉS :` qui sera affichée à la fin. Le nombre d'événements retrouvés est cherché parmi la base avec comme qualité minimum `c`, donc le maximum d'événements connus.

*   **Base de données ultime :** Lancez `fusion_dataset.py <qualite>` pour regrouper le Ground Truth, le Bruit et la base Gold dans `seisbench_dataset_ultime`. Nous avons donc maintenant la base de données pour le second entraînement prête. Nous allons pouvoir faire du transfert pour affiner nos poids.

*   **Affinement par Fine-Tuning (Modèle 2) :** Exécutez `IA_seisbench_Tuning.py 2 <qualite>`. Les paramètres `EPOCHS`, `LEARNING_RATE` et `SIGMA` sont réduits pour cette étape de précision (ligne 60 à 62). Je trouve que les paramètres choisis sont optimaux pour ma base de données. Seulement le paramètre `poids_classes` n'est pas changé, je n'ai pas réussi à trouver une certaine logique pour lui indiquer la marche à suivre.

---

## Étape 2 bis : Machine Learning automatisé sur Serveur SSH

Pour les utilisateurs opérant sur le serveur SSH, l'intégralité du pipeline d'apprentissage (de la création de la base Ground Truth jusqu'au Fine-Tuning final) peut être exécutée via des scripts Bash déjà prêts. Les utilisateurs ne se servant pas d'un serveur SSH pourront aussi utiliser mais seulement  `runAll.sh`, `batch_Singb` ne devrait pas.

*   **Pré-requis :** Lancez le script `scp.sh` qui permet de copier tous les fichiers du répertoire pour l'IA. Vous allez devoir modifier votre **mot de passe** et le **chemin d'accès** vers votre session.
*   **Commande :** Exécutez `sbatch batch_Singb` (il lancera tout pour la qualité `b` ), vous allez sûrement devoir modifier quelques lignes comme le noeud et/ou le nombre de coeurs que vous voulez réserver.
*   **Fonctionnement :** Le script prend en charge toute la chaîne et génère un fichier de type `output_classiqueb.out` pour suivre l'avancement. Que ce soit la réservation de ressources, et le lancement de toutes les fonctions. 

---

## Étape 3 : Affichage des résultats 

Le pipeline génère des graphiques de performance sans nécessiter d'affichage interactif. Toutes les images produites sont directement sauvegardées dans le répertoire `images/`.

*   **Visualisation des pointés de l'IA :** Lancez `test_IA.py 1 <qualite>` (pour le modèle 1) ou `test_IA.py 2 <qualite>` (pour le modèle 2) pour vérifier les distributions gaussiennes générées. La base de test est tirée aléatoirement à 10% du dataset global et reste invisible pour l'IA durant l'entraînement. La constante que vous pouvez changer est `SEUIL_PROB` à la ligne 69 pour afficher la probabilité minimale à enregistrer (conseil : rester à 0.8). Vous pouvez aussi modifier `NB_EXEMPLES_SAVE` ligne 74.<br>
Pour le modèle 1, les pointés manuels sont en magenta et cyan, les pointés de la V1 sont bleu et rouge (s'ils dépassent 0.3 surtout pour la S).<br>
Pour le modèle 2, les pointés magenta et cyan sont les pointés trouvés par la V1 pour détecter l'événement. Les pointés rouges et bleus sont ceux de la V2.<br
Pour les images de la V2, si vous avez [Manuels] alors l'événement fait partie de votre base de données Ground Truth et si [Trouvé par l'IA] alors l'événement et tous les pointés ont été faits par l'IA.
<div align="center">
    <img src="https://github.com/clementbedour/GET_apprentissage_PhaseNet/blob/main/images/seisbenchB/V2/trace_182_modele_2_qualite_b.png" alt="Picture Modele 2" width="50%">
</div>

*   **Affichage fonction de perte :** Lancez `compare_trust.py 1 <qualite>` ou `compare_trust.py 2 <qualite>` pour vérifier l'évolution des courbes des pertes (courbes d'apprentissage) au fur et à mesure des epochs.
<div align="center">
    <img src="https://github.com/clementbedour/GET_apprentissage_PhaseNet/blob/main/images/seisbenchB/loss_curve_b_scratch.png" alt="Picture Loss Curve scratch" width="49%">
    <img src="https://github.com/clementbedour/GET_apprentissage_PhaseNet/blob/main/images/seisbenchB/loss_curve_b_finetuning.png" alt="Picture Loss Curve finetuning" width="49%">
</div>

*   **Scores de confiance :** Lancez `metrics.py 1 <qualite>` ou `metrics.py 2 <qualite>` pour constater la répartition du score de confiance sur tous les événements détectés.
<div align="center">
    <img src="https://github.com/clementbedour/GET_apprentissage_PhaseNet/blob/main/images/seisbenchB/confiance_V1_b.png" alt="Picture Score Confidence scratch" width="49%">
    <img src="https://github.com/clementbedour/GET_apprentissage_PhaseNet/blob/main/images/seisbenchB/confiance_V2_b.png" alt="Picture Score Confidence detection" width="49%">
</div>

*   **Répartition temporelle :** Lancez `image_event_day.py <qualite>` pour visualiser la répartition du nombre de nouveaux événements découverts.
<div align="center">
    <img src="https://github.com/clementbedour/GET_apprentissage_PhaseNet/blob/main/images//seisbenchB/distribution_journaliere_vt.png" alt="Picture Event Day" width="75%">
</div>

---

## Étape 4 : Base de données Volpick

J'ai essayé de faire la même chose mais en partant d'une base bien plus grande.<br>
Etude scientifique de référence **Volpick** ([https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2024GL108438](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2024GL108438)). Cette base a été choisie pour sa taille, sa propreté et au vu des résultats obtenus dans l'étude.<br><br>

Les codes marchent plus ou moins, je n'ai pas eu le temps de les finaliser, de les tester suffisamment et de vérifier les résultats. Mais sinon tout marche quasiment pareil, il faut juste remplacer la qualité par `LPVT` si on veut les LP et les VT dans la base d'apprentissage. Sinon on met `VT` si on veut que les VT dans cette base.<br>
Pour voir l'ordre d'exécution, vous pouvez regarder dans `SSH/runAllvolpick.sh` pour les LP et VT dans la base ou `SSH/runAllvolpick2.sh` pour seulement les VT (on retire les pointés des LP pour les ajouter dans le bruit).

# Les tags

## Tag 1 : v1

Ce tag est juste une version antérieure. Si vous avez des problèmes avec la dernière version, vous pouvez l'essayer. Mais elle est moins optimisée, moins performante et moins protégée contre les problèmes.

---

## Tag 2 : version final

Tous les codes liés à l'utilisation d'une base manuelle sont corrects et marchent.<br>
Pour Volpick, je n'ai malheureusement pas eu le temps de finir. Les codes sont présents mais je pense qu'il existe des problèmes après le second entraînement (via Fine-Tuning sur toutes nos données). L'affichage de `test_IA` n'est pas complet.


enlever truc affichage wsl (compliqué affichage)