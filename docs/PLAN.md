# Plan — Finish

Chaque jalon laisse l’application lançable. On n’ouvre pas le jalon suivant tant que le précédent n’a pas été validé par une utilisation réelle, pas seulement par les tests automatiques.

## Jalon 0 — Cadrage

Statut : fait.

Livrables :

- `docs/ARCHITECTURE.md`
- `docs/PLAN.md`
- `docs/DECISIONS.md`

Sortie : les décisions structurantes sont écrites, y compris celles qui attendent un essai sur le matériel.

## Jalon 1 — Direct

Statut : validé le 3 octobre 2026. Caméra 0, DirectShow, YUY2, 1920×1080, environ 29,8 images/s, horodatage en haut à gauche, capture indépendante de l’interface.

Livré :

- ouverture et fermeture de la webcam dans un thread dédié ;
- affichage du direct, ratio conservé ;
- horodatage local visible, à la milliseconde, dessiné dans l’image ;
- résolution réelle affichée ;
- FPS mesuré sur une seconde de temps monotonic ;
- erreurs caméra visibles ;
- tests sans webcam sur l’horloge, le calcul de FPS, le dessin et la configuration.

Le bandeau rappelle que les images ne sont pas enregistrées. Le buffer est arrivé au jalon 2.

### Validation humaine

1. Créer l’environnement et lancer l’application (commandes dans `README.md`).
2. Brancher la webcam. Fermer les logiciels qui pourraient la garder (visioconférence, OBS).
3. Démarrer le direct. L’image apparaît sans bloquer la fenêtre pendant la suite.
4. Lire l’horodatage : `jj/mm/aaaa hh:mm:ss.mmm`, lisible, dans un coin, sans masquer la scène.
5. Noter la résolution réelle et le FPS. Les comparer à 1920×1080 et 30.
6. Noter le fourcc de capture dans `logs/finish.log` (`Capture fourcc=`).
7. Laisser tourner au moins une minute. Le FPS affiché reste stable. Le journal ne spamme pas.
8. Arrêter. La caméra se libère (un autre logiciel peut la rouvrir).
9. Redémarrer le direct dans la même fenêtre.
10. Fermer la fenêtre pendant le direct. Le processus se termine. `Camera released` puis `Application stopped` sont dans le journal.
11. Retirer la caméra, ou mettre un index faux dans `src/config.py`, et vérifier le message d’erreur.

Critère de sortie : image fluide, horloge lisible, FPS cohérent avec ce que l’œil voit, arrêt propre.

## Jalon 2 — Buffer

Statut : validé le 3 octobre 2026. 1920×1080, environ 30 images/s, JPEG qualité 80, encodage moyen 4,9 ms dans le thread de capture, buffer stabilisé vers 903 images, 30 s et 213–214 Mo. Aucun second thread d’encodage.

Livré :

- buffer circulaire JPEG qualité 80, purgé par l’âge monotonic, pas par un nombre d’images ;
- `BufferedFrame` avec timestamp monotonic, heure locale et octets JPEG ;
- `snapshot_last_seconds` pour 10, 20 et 30 secondes, indépendant du buffer vivant ;
- durée du buffer affichée dans la fenêtre ;
- logo `finish.png` dans la fenêtre et comme icône, chemin ancré à la racine du projet ;
- modèle de nom de fichier (slug). La course et la session sont distinguées depuis le jalon 3. Pas d’enregistrement.

Mesures du 3 octobre 2026, écrites dans `docs/ARCHITECTURE.md` : FPS inchangé autour de 30, JPEG moyen 4,9 ms, environ 903 images et 214 Mo après 30 secondes, CPU autour de 51 % d’un cœur. L’encodage reste dans le thread de capture.

### Validation humaine

1. Lancer l’application. Le logo FINISH est visible, y compris si le lancement ne se fait pas depuis le dossier du projet.
2. Démarrer le direct. L’image et l’horloge du jalon 1 sont inchangées.
3. Laisser tourner plus de 30 secondes. Le compteur Buffer se stabilise vers 30 s. Le FPS reste proche de 29,8.
4. Arrêter. La caméra se libère. Le compteur revient à l’attente.
5. Fermer la fenêtre pendant le direct. Le processus se termine.

Critère de sortie : le direct reste fluide, le buffer ne grossit plus après 30 secondes, l’arrêt est propre.

## Jalon 3 — Replay

Statut : validé le 3 octobre 2026. Le replay continu à environ 20 images/s est accepté. Le départage précis se fait en pause, image par image. On n’optimise pas cette cadence.

Livré :

- course active demandée une fois, bouton Nouvelle course, session non ouverte tant qu’il n’y a pas d’enregistrement ;
- Replay 10 s, Replay 20 s, Replay 30 s, Retour LIVE, Pause / Lecture, image précédente et image suivante en pause ;
- lecture par timestamps monotonic, un JPEG décodé à la fois, fin du snapshot qui revient au direct ;
- bandeau et libellé de mode, sans rien incruster dans l’image.

Essai webcam du 3 octobre 2026, écrit dans `docs/ARCHITECTURE.md` : la caméra reste vers 30 images/s pendant le replay, le buffer reste vers 30 s, le retour au direct prend moins de 10 ms, la mémoire du snapshot partage les octets JPEG du buffer. L’affichage continu du replay saute des images (environ 20 images montrées par seconde) pour rester à l’heure ; l’image par image en pause les montre toutes.

### Validation humaine

1. Démarrer le direct. Saisir le nom de course une seule fois. Le logo est inchangé.
2. Attendre au moins 35 secondes. Noter l’heure incrustée.
3. Replay 10 s : l’horloge de l’image recule d’environ 10 secondes. Le bandeau REPLAY est visible. Le mot n’est pas dans l’image.
4. Laisser jouer jusqu’au bout : l’écran revient au direct tout seul, sur l’heure courante.
5. Replay 20 s, quelques secondes, puis Retour LIVE : l’heure affichée rejoint l’heure courante, sans rejouer le trou.
6. Recommencer avec Replay 30 s, y compris si le buffer est encore plus court : pas de message d’erreur, tout le disponible est joué.
7. Pause : l’image reste fixe, le compteur Buffer continue. Image suivante et image précédente ne marchent qu’en pause.
8. Après plusieurs replays, le direct reste fluide et le buffer reste vers 30 s.
9. Arrêter. La caméra se libère.

Critère de sortie : impossible de confondre direct et replay, retour immédiat à l’heure courante, buffer et caméra intacts.

## Jalon 4 — Enregistrement

Statut : validé le 3 octobre 2026.

Livré :

- session enregistrée à côté du direct et du buffer, file bornée de 30 images, thread `video-writer` ;
- codec `mp4v`, images BGR déjà horodatées, sans repasser par le JPEG ;
- `Session : 001` seulement pendant l’enregistrement, bandeau `● REC`, durée de session ;
- nom `aaaa-mm-jj_hh-mm-ss_<course_slug>_session-NNN`, JSON du même nom, aucun écrasement ;
- prochain numéro lu dans `recordings/` pour ce slug, y compris après redémarrage.

Mesure du 3 octobre 2026, détaillée dans `docs/ARCHITECTURE.md` : 153 s, 4 603 images, 0 perte, FPS caméra resté vers 30 y compris pendant un replay, fichier 131 Mo par minute, écart de durée 0,31 s. VLC n’est pas installé sur ce PC.

### Validation humaine

1. Démarrer le direct. Le nom de course n’est pas redemandé s’il existe déjà.
2. Démarrer l’enregistrement. Lire `Session : 001` et le bandeau REC.
3. Laisser tourner au moins deux minutes. Lancer un replay, une pause, une image, puis Retour LIVE. Le bandeau REC reste.
4. Arrêter l’enregistrement. La ligne Session revient à « — ». La course reste. La caméra peut continuer.
5. Ouvrir le MP4. L’horloge incrustée avance sans trou sur la période du replay. La durée du fichier est proche du temps réel.
6. Lire le JSON à côté du MP4. Le nom de course est celui qui a été saisi.
7. Enregistrer une seconde session : `session-002`, sans remplacer la première.
8. Relancer l’application et enregistrer encore : le numéro suivant, pas un écrasement.

## Jalon 5 — Consultation

Statut : validé le 3 octobre 2026.

Livré :

- écran Archives, sans caméra, y compris après redémarrage ;
- liste groupée par course, la plus récente en haut, données lues dans le JSON ;
- archives incomplètes ou invalides écartées et journalisées ;
- lecteur dédié : lecture, pause, stop, barre, temps, image par image en pause ;
- Démarrer session ouvre le direct et l’enregistrement ensemble. Arrêter session ferme les deux ;
- les archives restent fermées tant qu’une session est active.

Les anciens jalons « relecture d’archive » et « image par image sur le fichier » sont couverts ici.

## Jalon 6 — Ergonomie terrain

Statut : implémenté le 3 octobre 2026. En attente de validation. Rien n’est commencé après.

Livré, sans modifier le pipeline vidéo :

- écran recentré sur l’image, la course, l’état, le replay et la session ;
- états EN ATTENTE, LIVE — ENREGISTREMENT, REPLAY, REPLAY EN PAUSE, ARCHIVE, et bandeau REC avec la durée ;
- confirmation pour une nouvelle course déjà active, et pour arrêter une session ;
- raccourcis 1/2/3, F1/F2/F3, Espace, flèches, Échap ;
- aller à l’heure dans l’archive ;
- espace disque, avertissement sous 10 Go, sans bloquer l’écriture ;
- journal du cycle SESSION START REQUESTED, CAMERA STARTED, RECORDER STARTED, SESSION RECORDING, STOP REQUESTED, RECORDER STOPPING, RECORDER CLOSED, CAMERA STOPPED, SESSION CLOSED, avec la course et le numéro.

L’essai de 15 minutes est dans `docs/ARCHITECTURE.md`. Le débit moyen de cette prise est de 17 images/s, avec 0 perte et un buffer resté à 30 s. Une sonde suivante, PC plus calme, est à 26 images/s.

## Jalon 7 — Interface, réglages et export

Statut : validé le 3 octobre 2026.

Construit dans l’ordre 7A, 7B, 7C, 7D, 7E, 7F :

- écran plat en trois vues : Pré-course, Course en cours, Archives ;
- caméra, résolution, FPS, et réglages avancés (buffer, JPEG, dossier, codec affiché) ;
- test caméra de quelques secondes, sans fichier ;
- contrôle avant départ : nom, dossier, espace disque ;
- archives regroupées par course, lecture, session précédente et suivante ;
- export d’une session ou de la course entière, sans réencodage, avec contrôle d’espace et de taille ;
- suppression locale seulement après un export réussi, ou par une confirmation explicite.

La fusion de toute une course en une seule vidéo n’est pas faite. Elle demanderait un réencodage.

## Jalon 8 — Préparation terrain et distribution Windows

Statut : implémenté le 3 octobre 2026. Le test prolongé sur Finish.exe, et l’essai sur un second PC, restent à faire sur le terrain. Rien n’est commencé après.

Livré :

- dossier portable `dist/Finish/Finish.exe`, construit par `scripts/build.ps1` ;
- préférences JSON dans `%LOCALAPPDATA%\Finish` ;
- vidéos par défaut dans `Documents\Finish\recordings` pour l’exécutable, et dans `recordings/` du projet en développement ;
- journaux tournants `finish.log`, `finish.log.1`, `finish.log.2` ;
- version 0.1.0, dialogue À propos, estimation d’autonomie, fin de course ;
- `course.json` d’export avec `export_time` et `finish_version`.

La fusion vidéo et un codec plus compact restent hors de ce jalon.

## Après le socle

Ces idées sont notées pour ne pas être redécouvertes. Elles ne sont pas planifiées :

affichage simultané direct et replay, marqueur d’arrivée, zoom sur image arrêtée, export d’un extrait ou d’une photo, ligne d’arrivée dessinée, choix de caméra dans l’interface, plein écran, exécutable Windows, reprise après crash, 60 ou 120 images/s.

## Vérification automatique

Les tests couvrent les parties déterministes. Ils ne remplacent pas l’essai webcam.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
