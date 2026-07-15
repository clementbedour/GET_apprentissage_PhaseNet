## Ce repertoire à pour but d'automatiser et d'utiliser de SeisBench et PhaseNet


## Les étapes à suivre :
On commence par faire **phase.py** pour découper les fichiers événements mensuel (dans data/phase) par des sous fichier (dans data/phase_separe). Chaque fichier sera un événement unique
Attention, ici nous allons aussi trier les événements. Dans mon exemple j'ai gardé que les VT (dans data/phase_vt).
Si on veux garder les autres il faut décommanter dans la fonction "evenement_particulie()"

Avant de pouvoir afficher sur snuffler, on doit créer un fichier événement au bon format. Il faut lancer **phase_to_evenement.py**. Il nous faut le fichier avec la date d'origine de l'event dans "data/phase_evenement_doc/2014.CATALOG.txt"
Si l'event n'existe pas dans le fichier car il n'est pas possible de l'identifier, alors la ligne "event:" sera vide et il sera marqué dans le fichier NL.txt dans le même répertoire.

Maintenant on va afficher tous les événements à la chaine. Il faut les .mseed dans /data/2014/MQ et aprés la liste des stations (BAM, CPM, FDF, ...)
Juste avant il faudra le fichier de station dans data/station qui s'appelera all_station_2 (modifiable dans le code). Je n'est pas fais de code pour l'automatiser
On va pouvoir lancer **affichage_snuffler.py**. Dans un premier temps, il va nous demander par quel fichier commencer, si on n'entre rien, on commencera par le premier fichier.
Sinon, nous pouvons rentrer le nom du fichier (trouvable dans data/phase_evenement).
Nous voyons l'événement à -40 et + 30 secondes à partir de la création de l'événement (ou du premier pointé s'il n'a pas été identifié).
Nous pouvons modifier les pointés. Qu'ils soient modifié ou pas, nous devons faire "File" -> "Save Markers..." Que nous enregistrerons dans le fichier /data/phase_snuffler avec comme nom, le nom du fichier d'origine.
Il est affiché dans le terminal aprés "Traitement du fichier :" (ne pas mettre .txt), on pourra rajouter '_a', '_b', '_c' ou '_d' pour la confiance des pointés. Les pointés '_d' ne seront pas pris en compte pour la suite.

Une fois l'enregistrement terminé, vous pouvez quitter snuffler. A ce moment, le terminal va vous demander si vous voulez continuer le parcour de vos fichier.
Si vous mettez '1' le programme va s'arreter en affichant le dernier fichier traité (utile pour reprendre le lendemain), sinon il va continuer jusqu'à la fin (ou jusqu'à trouver NL.txt, ce qui revient à la même chose).
Bravo, vous avez fini de faire tout vos pointés, nous allons pouvoir passer sur SeisBench.


Alors si vous avais bien tout les fichiers au bon endroit, il suffit de lancer **format_csv_hdf5.py** et vous aurais (au bout de 2-3 minutes d'attentes) 2 fichiers dans ../data/seisbench_format, metadata.csv et waveform.hdf5

Le reste est en cours de programmation ...
