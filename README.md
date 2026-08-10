## Ce répertoire a pour but d'automatiser et utiliser SeisBench et PhaseNet


## Les étapes à suivre :

---------------SEISBENCH---------------<br>
On commence par faire **phase.py** pour découper les fichiers événements mensuels (dans data/phase) par des sous-fichiers (dans data/phase_separe). Chaque fichier sera un événement unique
Attention, ici nous allons aussi trier les événements. Dans mon exemple j'ai gardé que les VT (dans data/phase_vt).<br>
Si on veut garder les autres il faut décommenter dans la fonction "evenement_particulie()"<br>

Avant de pouvoir afficher sur snuffler, on doit créer un fichier événement au bon format. Il faut lancer **phase_to_evenement.py**. Il nous faut le fichier avec la date d'origine de l'événement dans "data/phase_evenement_doc/2014.CATALOG.txt"<br>
Si l'événement n'existe pas dans le fichier car il n'est pas possible de l'identifier, alors la ligne "event:" sera vide et il sera marqué dans le fichier NL.txt dans le même répertoire.<br>

Maintenant, on va afficher tous les événements à la chaîne. Il faut les .mseed dans /data/2014/MQ et après la liste des stations (BAM, CPM, FDF, ...)<br>
Juste avant il faudra le fichier de station dans data/station qui s'appellera all_station_2 (modifiable dans le code). Je n'ai pas fait de code pour l'automatiser.<br>
On va pouvoir lancer **affichage_snuffler.py**. Dans un premier temps, il va nous demander par quel fichier commencer, si on n'entre rien, on commencera par le premier fichier.<br>
Sinon, nous pouvons rentrer le nom du fichier (trouvable dans data/phase_evenement).<br>
Nous voyons l'événement à -40 et + 30 secondes à partir de la création de l'événement (ou du premier pointé s'il n'a pas été identifié).<br>
Nous pouvons modifier les pointés. Qu'ils soient modifiés ou pas, nous devons faire "File" -> "Save Markers...". Que nous enregistrerons dans le fichier /data/phase_snuffler avec comme nom, le nom du fichier d'origine.<br>
Il est affiché dans le terminal après "Traitement du fichier :" (ne pas mettre .txt), on pourra rajouter '_a', '_b', '_c' ou '_d' pour la confiance des pointés. Les pointés '_d' ne seront pas pris en compte pour la suite.<br>

Une fois l'enregistrement terminé, vous pouvez quitter snuffler. A ce moment, le terminal va vous demander si vous voulez continuer le parcours de vos fichiers.<br>
Si vous mettez '1' le programme va s'arrêter en affichant le dernier fichier traité (utile pour reprendre le lendemain), sinon il va continuer jusqu'à la fin (ou jusqu'à trouver NL.txt, ce qui revient à la même chose).<br>
Bravo, vous avez fini de faire tous vos pointages, nous allons pouvoir passer sur SeisBench.<br>

---------------IA---------------<br>
Tous les prochains fichiers vont être dans data/seisbench, pour les fichiers qui possèdent les poids des 2 modèles, ils seront dans prg_python/seisbench<br><br>
Alors si vous avez bien tous les fichiers au bon endroit, il suffit de lancer **format_csv_hdf5.py** et vous allez avoir 2 fichiers dans le répertoire seisbench_format, metadata.csv et waveform.hdf5. Cette base de données est aussi appelée "Ground Truth" (car nos pointés est la vérité absolue, absolue/20).<br>
Après nous allons générer une base de données pour le bruit. Il faut exécuter **gene_noise.py**, si vous voulez changer le ratio du bruit pour les fenêtres STA et LTA il faut faire varier la variable STA_LTA_THRESHOLD (en dessous de 1,6 ça devient vraiment compliqué). Vous allez avoir les "mêmes" fichiers que format_csv_hdf5.py dans seisbench_format_noise, nous avons donc la base de données Noise.<br>
Nous allons fusionner les 4 fichiers dans le répertoire seisbench_dataset, ça sera notre base d'apprentissage pour notre modèle from scratch. Il faut lancer **fusion_data.py**<br>
Nous avons tout ce qu'il faut pour lancer l'apprentissage from scratch, il faut lancer **IA_seisbench_Tuning.py 1**. Le paramètre '1' indique que nous allons créer la 1ère version. Vous pouvez faire varier les paramètres EPOCHS, LEARNING_RATE, SIGMA à la ligne 25. Mais d'après moi, il ne faut modifier que SIGMA. La localisation du fichier avec notre ML sera dans /prg_python/seisbench, il s'appelle phasenet_volcan_v1.pt<br>

Nous avons donc notre premier modèle, nous allons lancer la détection de nouveaux événements. Exécutez **detection_nouv.py**, attention, ce programme est très long. Il va créer 2 fichiers dans le répertoire seisbench_nouv, le catalogue des VT détectées, utile si on veut juste changer le filtre sans relancer le code car il a toutes les picks. Et le catalogue des VT détectées valides, c'est le fichier qui va respecter notre filtre (MIN_STATIONS et MIN_PROBA_EVENT). Il a regroupé certaines informations (date de début l'événement, date de fin, stations impliquées,...). Vous pouvez faire varier MIN_STATIONS et MIN_PROBA_EVENT en fonction de la contrainte que vous voulez. Je conseille de ne pas descendre MIN_PROBA_EVENT en dessous de 0.8 et MIN_STATIONS plus ou moins la moitié des stations totales.<br>

Après avoir eu tous les événements, nous avons besoin de les extraire proprement et de les mettre au bon format pour SeisBench. En lançant **extraire_nouv.py**. Nous avons donc 2 fichiers créés dans seisbench_format_gold avec juste nos nouvelles données. Cette base de données est aussi appelée "Gold" (car on a que les meilleures détections)<br>
Nous allons regrouper toutes nos données, Ground Truth, Noise et Gold pour avoir notre base de données finale avec **fusion_dataset.py**. Cette base de données sera dans seisbench_dataset_ultime, avec toujours un .csv et un .hdf5.<br>

Nous avons donc maintenant absolument tout pour lancer une deuxième fois notre modèle. Mais cette fois-ci, nous allons utiliser une méthode très utile en Machine Learning, le Transfert (Fine-Tuning).<br>
Il nous permet de ne pas recalculer tous les poids si nous avons un modèle satisfaisant au début. Donc en lançant **IA_seisbench_Tuning.py 2** nous allons partir du modèle 1 et l'affiner. Pareil qu'avant, vous pouvez faire varier EPOCHS, LEARNING_RATE, SIGMA. J'ai réduit SIGMA car nous avons déjà une base que je pense suffisante et ça nous permet d'avoir des résultats plus précis. J'ai aussi réduit EPOCHS et LEARNING_RATE car nous avons besoin de moins d'époque car nous faisons du Fine-Tuning, et pour le LEARNING_RATE, nous affinons simplement le modèle créé.<br>
Et voilà, vous avez donc un modèle (normalement) viable. Vous pouvez vérifier au fur et à mesure avec **test_IA.py 1** pour voir les courbes gaussiennes que le modèle nous rend pour le premier entraînement. En changeant le paramètre à 2, nous voyons le second modèle. La base de données "test" est tirée aléatoirement depuis notre dataset. Donc il est différent après chaque lancement complet.<br>


Pour les personnes étant sur le serveur SSH du GET. Vous pouvez directement exécuter tous les codes automatiquement. Avec la commande **sbatch batch_Sing**. Il va créer un fichier de sortie appelé slurm-"id du processus".out. Il va commencer par format_csv_hdf5 et finir avec IA_seisbench_Tuning.py 2.<br>


---------------RENDU GRAPHIQUE---------------<br>
Toutes les images vont être enregistrées dans le dossier "images".<br>
J'ai séparé la base entière avec 80% pour le training, 10% pour la validation et 10% pour le test. L'IA n'a jamais accès à la base avec le tag "test". Donc nous voulons savoir après chaque entraînement si l'IA nous donne des probabilités cohérentes ou pas. Pour ça vous pouvez lancer **test_IA.py 1 b**. Le premier argument est le même que IA_seisbench_Tuning.py, c'est la version que l'on veut utiliser (1 ou 2).<br>
Pour le second argument, c'est simplement pour comparer les différents modèles en fonction de la qualité des pointés (a, b ou c). Il va enregistrer 20 images (modifiables avec le paramètre NB_EXEMPLES_SAVE) avec une proba min choisie avec SEUIL_PROB (je conseille 0.8, plus bas n'est pas nécessaire).<br>

Le dernier graphique est **metrics.py** qui prend les mêmes paramètres que les autres. Il va enregistrer un graphique qui nous montre la distribution des scores de confiance sur toute la base de données test.<br>

Nous avons aussi la fonction **compare_trust.py** qui prend soit 1 ou 2 en premier argument et a, b ou c en second argument. Il va créer un graphique nous affichant l'évolution de la moyenne quadratique des valeurs durant l'apprentissage. Il utilise les valeurs Train et Val affichées durant l'exécution de IA_seisbench_Tuning.py <br>

Le dernier graphique est **image_event_day.py** qui prend comme argument a, b ou c. Il doit être exécuté au minimum après extraire_nouv.py. Il nous montre la répartition des nouveaux événements trouvés sur l'ensemble des jours.<br>


---------------VOLPICK---------------<br>
Le reste est en cours de programmation...
