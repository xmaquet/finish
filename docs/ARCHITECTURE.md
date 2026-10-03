# Architecture — Finish

Outil vidéo local pour une course à pied d’enfants. Il montre la ligne d’arrivée en direct, permettra de revoir les dernières secondes sans interrompre la prise de vue, et conservera chaque session pour une relecture ultérieure.

Ce n’est pas un photo-finish, ni un chronomètre homologué, ni un système de classement ou de reconnaissance.

Statut : jalons 1 à 7 validés. Jalon 8 (distribution Windows) implémenté. Aucun jalon suivant n’est commencé.

## Principes

1. La capture ne dépend jamais de l’affichage, du replay ou de l’interface.
2. Le direct, le replay instantané et la session archivée sont trois objets distincts.
3. L’interface n’a pas de file d’images. Elle affiche soit la dernière image capturée, soit l’image courante d’un replay ou d’un archive.
4. Le temps affiché est l’heure locale du PC. Le temps utilisé pour les durées est `time.monotonic()`.
5. On retient la solution la plus simple qui répond au besoin réel : un PC, une webcam, un opérateur.

## Identité

L’application s’appelle FINISH. Le seul fichier graphique est `finish.png`, à la racine du projet. Il n’est pas recopié ailleurs. Le même fichier sert de logo dans l’écran et d’icône de fenêtre.

`LOGO_PATH` dans `src/config.py` est calculé depuis l’emplacement du code, pas depuis le répertoire courant. La fenêtre l’affiche dans une bande noire et s’en sert comme icône. Il n’y a pas de thème ni de ressource Qt compilée.

## Course et session

Une course est l’événement filmé. Une session est une période continue d’enregistrement à l’intérieur de cette course. Trois sessions peuvent appartenir à la même course, séparées par des temps morts. Une seule course est active à la fois. Il n’y a pas de gestion d’événements.

| Champ | Rôle | Exemple |
| --- | --- | --- |
| `course_name` | Nom saisi, conservé tel quel | `Cross école 2026` |
| `course_slug` | Forme du nom pour les fichiers | `cross-ecole-2026` |
| `session_id` | Numéro technique de la session dans la course active | `2` |

Le nom de la course n’est pas l’identifiant technique. S’il est vide, l’affichage devient `Course` et le slug `course`.

Cycle de la course. Le nom est demandé au premier « Démarrer session ». Il reste affiché pour les démarrages suivants. « Nouvelle course » demande une confirmation si une course est déjà active, puis le nouveau nom. Aucune archive n’est supprimée. Le prochain numéro vient des fichiers de ce slug. Annuler ne change rien.

Cycle d’une session. `ActiveCourse` attribue 1, puis 2, puis 3, au moment où une session d’enregistrement s’ouvrira. Le jalon 3 n’ouvre pas encore de session : la ligne Session reste « — ». Aucun fichier n’est écrit.

Le fichier, à partir du jalon 4, reprendra la date, l’heure de début, le slug et le numéro :

```
2026-10-03_10-02-15_cross-ecole-2026_session-001.mp4
2026-10-03_10-02-15_cross-ecole-2026_session-001.json
```

Le slug retire les accents, supprime les apostrophes, remplace le reste des caractères hors `a-z` et `0-9` par un tiret, retire ce qui est interdit dans un nom Windows et tronque à 48 caractères. Un nom fait seulement de symboles devient `session`.

## Pipeline cible

```
webcam USB
    |
    v
thread camera-capture
    |
    |  lit une image
    |  note datetime.now() et time.monotonic()
    |  dessine l'horodatage dans l'image
    |
    +----> dernière image (verrou) ----> timer de l'interface --> DIRECT
    |
    +----> buffer circulaire JPEG -----> instantané --> REPLAY
    |
    +----> file bornée ----------------> thread d'écriture --> SESSION (fichier)
```

La session active couvre le direct, le buffer, le replay et le fichier. Le lecteur d’archive est un chemin à part : il ouvre un MP4 déjà écrit, sans caméra.

Pendant un replay, le thread de capture continue d’alimenter le direct et le buffer. Le lecteur ne commande pas la caméra.

## Retour au direct

L’interface ne met jamais les images en file d’attente.

- En direct, le timer lit la dernière image publiée et ignore les images intermédiaires s’il est en retard.
- En replay, un second `QTimer` (33 ms) fait avancer `ReplayPlayer` et décode une seule image JPEG.
- « Retour LIVE » abandonne le lecteur et peint tout de suite la dernière image BGR déjà publiée. Le buffer n’est pas vidé. La caméra n’est pas rouverte. Les images manquées ne sont pas rejouées.

Conséquence : si le replay 20 s est lancé à 12:00:00 et que l’opérateur revient au direct 12 secondes plus tard, l’écran montre l’image d’environ 12:00:12. Il ne rattrape pas 12:00:00.

À la dernière image du snapshot, le lecteur se termine tout seul et le même retour au direct a lieu. L’écran ne reste pas figé.

Mesure du 3 octobre 2026 : le retour manuel peint l’image courante en 5 à 8 ms. Après un replay de 20 s, l’index affiché était égal à l’index de capture. À la fin naturelle d’un replay de 10 s, l’horloge de l’image live (12:33:00.061) et l’horloge du PC (12:33:00.095) coïncidaient.

## Threads et communication

Un seul processus. Pas de `multiprocessing`, pas d’`asyncio` : OpenCV est bloquant, et le GIL est relâché pendant `VideoCapture.read`, l’encodage JPEG et `VideoWriter.write`.

| Thread | Rôle | Créé |
| --- | --- | --- |
| Interface Qt | Fenêtre, timer d’affichage, commandes | Jalon 1 |
| `camera-capture` | Ouvrir la webcam, horodater, publier, encoder le JPEG du buffer | Jalons 1 et 2 |
| `video-writer` | Encoder le fichier de session | Jalon 4 |
| Replay | `ReplayPlayer` et `QTimer` dans le thread interface. Pas de thread de replay | Jalon 3 |
| Archive | Lecture du fichier, dans le thread interface | Jalon 6 |

`threading.Thread` est préféré à `QThread`. Le worker caméra n’importe pas Qt, ce qui permet de le tester et de le raisonner sans l’interface. L’interface tire les données vers elle. Elle ne reçoit pas un signal par image : une rafale de signaux Qt remplirait la file d’événements et donnerait l’illusion d’un direct en retard.

### Contrat de la dernière image

Le worker publie, sous un verrou tenu très peu de temps :

- l’image BGR déjà horodatée ;
- le numéro d’image ;
- l’heure locale et le temps monotonic de cette image ;
- la résolution, le FPS mesuré, l’état et l’éventuelle erreur.

L’image n’est plus modifiée après publication. `VideoCapture.read` renvoie un tableau NumPy neuf à chaque appel. L’interface convertit ce tableau en `QImage` copiée, puis peut le relâcher.

Le verrou ne couvre ni la lecture caméra, ni le dessin, ni un futur encodage.

### Contrat du buffer

Seul le thread de capture modifie le buffer. Chaque image conservée est une `BufferedFrame` :

- `monotonic_timestamp`, issu de `time.monotonic()` au moment de la capture ;
- `wall_clock_timestamp`, l’heure locale déjà dessinée dans l’image ;
- `jpeg_data`, des `bytes` immuables.

`snapshot_last_seconds(10)`, `snapshot_last_seconds(20)` et `snapshot_last_seconds(30)` prennent le verrou, construisent une nouvelle liste des mêmes objets `BufferedFrame`, et le relâchent. Les `bytes` JPEG ne sont pas recopiés : ils sont immuables, et le lecteur en garde la référence. Le buffer peut ensuite ajouter ou oublier des images sans changer le contenu du snapshot.

Une image sort quand son âge dépasse 30 secondes : `timestamp < plus_récent - 30`. Une image âgée d’exactement 30 secondes reste. Le nombre d’images n’est pas fixé à `30 × FPS`. Si la demande de snapshot dépasse la durée réellement présente, toute la durée disponible est renvoyée.

L’encodage JPEG qualité 80 est fait dans le thread de capture, après le dessin de l’horloge et avant la publication du direct. Un second thread n’est ajouté que si cette étape fait baisser le débit de capture. L’arrêt de la caméra vide le buffer : il ne survit pas à la session de direct.

### Contrat de l’enregistrement

```
camera-capture --put_nowait--> queue.Queue bornée (30 images) --get--> video-writer
```

La capture dépose l’image BGR déjà horodatée. Elle ne décode pas le JPEG du buffer pour fabriquer le MP4. `put_nowait` ne bloque pas. Si la file est pleine, l’image nouvelle est abandonnée, `recording_dropped_frames` augmente, et le journal écrit au plus une fois par seconde `Recording queue overflow — dropped frame total=N`. La capture n’attend jamais le disque.

Le thread `video-writer` appelle `VideoWriter.write`. Cette méthode renvoie `None` avec ces bindings : le compteur d’images écrites augmente à chaque appel, pas selon la valeur de retour. À l’arrêt, on cesse d’envoyer, on vide la file, on ferme le writer, puis on écrit le JSON. Un fichier déjà présent n’est jamais ouvert.

## Temps

| Besoin | Horloge | Motif |
| --- | --- | --- |
| Texte dans l’image, noms de fichiers, métadonnées | `datetime.now()`, heure locale | C’est l’heure que lit l’opérateur |
| FPS, durée du buffer, rythme du replay, intervalles | `time.monotonic()` | Elle ne recule pas si Windows resynchronise l’heure |

Les deux valeurs sont prises l’une après l’autre au moment de la capture, puis attachées à l’image.

L’heure dessinée suit l’exemple du cahier des charges, avec trois chiffres de millisecondes :

```
03/10/2026 10:42:17.533
```

Le format `%f` de `strftime` produirait six chiffres. Il n’est pas utilisé pour l’affichage. Les microsecondes sont tronquées, pas arrondies, pour ne jamais afficher `1000`.

Ces millisecondes identifient une image. Elles ne donnent pas une discrimination à la milliseconde. À environ 30 images/s, la caméra ne produit qu’une image toutes les 33 ms environ. C’est la résolution temporelle effective de Finish. Pour départager deux coureurs, on met le replay en pause et on avance image par image.

Le texte est dessiné dans l’image par le worker, avant toute publication. Le direct, le replay et le futur fichier montrent donc la même horloge, sans dépendre de l’interface.

Présentation : coin supérieur gauche, texte blanc sur rectangle noir, taille proportionnelle à la largeur. Le reste de l’image n’est pas couvert.

Cette horloge aide à comparer deux arrivées. Elle n’est pas une mesure homologuée. Un saut NTP de l’horloge Windows peut apparaître dans le texte ; il ne fausse pas les durées calculées avec `time.monotonic()`.

## Direct (jalon 1)

1. L’opérateur clique sur « Démarrer session ». L’interface reste active. L’enregistrement du fichier démarre dès la première image.
2. Le worker ouvre l’index configuré. Sous Windows il essaie DirectShow, puis le backend par défaut.
3. Il demande la résolution et le FPS configurés, puis réduit le tampon du driver si le backend l’accepte.
4. Il lit la résolution sur l’image réellement reçue. La valeur demandée et la valeur obtenue sont journalisées. Un écart n’arrête pas la capture.
5. Chaque image reçoit l’horodatage, puis remplace la dernière image publiée.
6. Un `QTimer` (33 ms) lit cette image. Si le numéro n’a pas changé, il ne redessine pas. L’image est mise à l’échelle en conservant le ratio.
7. Le FPS affiché est calculé sur une fenêtre d’une seconde de temps monotonic. Le FPS annoncé par le driver est seulement journalisé.
8. « Arrêter », ou la fermeture de la fenêtre, signale l’arrêt, attend la fin du thread (au plus 5 s à la fermeture) et libère `VideoCapture`.

États du jalon 1 : `starting`, `running`, `stopped`, `error`. Les états complets de l’application arriveront avec les sessions :

| État futur | Signification |
| --- | --- |
| `IDLE` | Pas de session |
| `LIVE_RECORDING` | Caméra et fichier actifs, écran sur le direct |
| `LIVE_REPLAY` | Caméra et fichier toujours actifs, écran sur le replay |
| `ARCHIVE_PLAYBACK` | Lecture d’un fichier, webcam non requise |

## Buffer mémoire (décision pour le jalon 2)

Une image 1920×1080 BGR occupe 1920 × 1080 × 3 = 6 220 800 octets, soit 5,9 Mo.

À 30 images/s pendant 30 s, cela fait 900 images et environ 5,6 Go. Ce stockage est exclu.

Le buffer conserve des JPEG qualité 80 (`JPEG_QUALITY`). L’encodage reste dans le thread de capture : la mesure ci-dessous ne montre pas de baisse du débit.

### Mesure du 3 octobre 2026

Webcam index 0, DirectShow, YUY2, 1920×1080. Même poste que le jalon 1.

| | Sans buffer | Avec buffer |
| --- | --- | --- |
| FPS mesuré | 29,8 | 30,2 en régime, après 45 s |
| Encodage JPEG moyen | — | 4,9 ms (de 3,4 ms à 13,4 ms) |
| CPU du processus | — | environ 51 % d’un cœur |

Le point à 13,4 ms est un maximum isolé. La moyenne reste à 4,9 ms, et le FPS ne quitte pas la zone des 30 images/s. Aucun thread d’encodage supplémentaire n’est ajouté.

Après remplissage, le buffer se stabilise. Il ne continue pas de grossir :

| Instant | Images | Durée couverte | Octets JPEG |
| --- | --- | --- | --- |
| 30 s | 902 | 29,97 s | 213 Mo |
| 35 s | 904 | 30,00 s | 214 Mo |
| 40 s | 903 | 29,99 s | 214 Mo |
| 45 s | 903 | 29,98 s | 214 Mo |

Taille JPEG sur cette scène : moyenne 237 Ko, minimum 193 Ko, maximum 275 Ko. Aucun échec d’encodage.

Un instantané de 10 s contenait 302 images sur 10,00 s, celui de 30 s les 903 images du buffer. L’arrêt vide le buffer et libère la caméra. Avec la fenêtre ouverte, le compteur de buffer avançait, le FPS affiché restait autour de 29, et Arrêter revenait à l’attente.

### Mémoire d’un snapshot

Le snapshot ne décompresse rien. `ReplayPlayer` conserve le tuple de frames et l’interface décode un JPEG à la fois (`cv2.imdecode`), puis oublie la matrice BGR au prochain affichage. Il n’y a jamais 900 images 1080p décodées ensemble.

Au moment du clic Replay 30 s, la somme des octets du snapshot et le compteur du buffer étaient le même nombre : 202 696 959 octets. Le premier JPEG du lecteur était encore celui du buffer. Il n’y a donc pas une seconde copie de 200 Mo à la création.

Ensuite le buffer continue. Une image trop vieille sort du tampon circulaire, mais reste en mémoire tant que le lecteur la référence. Après 3 s de replay 30 s, le premier JPEG du snapshot n’était plus dans le buffer vivant. Le surplus est seulement cette tranche déjà évincée, pas un second buffer complet. Si l’opérateur garde un snapshot de 30 s pendant que la capture en produit 30 de plus, le plafond pratique est d’environ deux fenêtres JPEG (autour de 400 Mo sur cette scène), plus une image décodée.

Décodage moyen mesuré pendant les replays : 5,1 ms (347 images). La résolution native est conservée.

La relecture image par image doit garder la résolution native. Réduire le buffer à 720p est exclu : le jugement d’une arrivée serrée se ferait sur une image moins nette que l’enregistrement.

## Replay (jalon 3)

`ReplayPlayer` (`src/video/replay.py`) ne connaît ni la caméra ni Qt. L’interface lui donne le snapshot et un temps monotonic.

La position de lecture est `timestamp de départ + temps écoulé depuis le clic`. Le timer avance l’index jusqu’à la frame dont le timestamp est encore inférieur ou égal à cette cible. S’il a du retard, il saute les images intermédiaires pour rester à l’heure réelle. Il ne suppose pas un 30 images/s fixe.

L’horloge incrustée est celle de la capture : elle est déjà dans le JPEG. L’affichage ne la redessine pas.

L’écran distingue les modes par le libellé `LIVE` ou `REPLAY — 10 s` (ou la durée réelle si le buffer est plus court, par exemple `REPLAY — 12.4 s`) et par un bandeau `REPLAY`. Ce bandeau n’est pas incrusté dans l’image.

Pause gèle l’index. La webcam et le buffer continuent. « Lecture » reprend depuis l’image en pause, sans sauter le temps passé à l’arrêt. « < Image » et « Image > » ne marchent qu’en pause, une frame à la fois. La ligne `Replay` montre `6.4 / 10.0 s`.

Si le buffer ne couvre pas encore la durée demandée, tout ce qui est disponible est joué. Un buffer vide laisse l’écran en direct et affiche une indication. Pas de boîte d’erreur.

### Mesure du replay, 3 octobre 2026

Même webcam, 1920×1080, YUY2, DirectShow. Scène un peu plus simple que celle du jalon 2 : les JPEG font environ 227 Ko au lieu de 237 Ko, donc le buffer plein pèse 200 à 205 Mo au lieu de 213 à 214 Mo. Le nombre d’images reste autour de 900 et la durée autour de 30 s. Ce n’est pas une fuite.

| Situation | FPS caméra | Mémoire JPEG du buffer | Snapshot |
| --- | --- | --- | --- |
| LIVE, buffer plein | 30,3 | 205 Mo, 901 images, 29,98 s | — |
| Replay 10 s | 30,3 | 205 Mo | 69 Mo, écart d’horloge 10,00 s, octets partagés |
| Replay 20 s | 30,3 puis 29,6 | environ 203 Mo | 135 Mo, écart 19,95 s, octets partagés |
| Replay 30 s | 29,6 puis 29,7 | environ 203 Mo | 203 Mo au clic, identiques au buffer |

Après plusieurs replays, le FPS caméra était encore à 30,2 et le buffer à 902 images / 29,97 s / 201 Mo. L’arrêt a rendu `worker` nul : la caméra est libérée.

Le lecteur a décodé 162 images sur 241 pendant un replay de 8,1 s, soit environ 20 images affichées par seconde, pendant que la caméra restait à 29,7. Le timer a sauté des images pour tenir l’heure, parce que décoder puis mettre à l’échelle une image 1080p dépasse l’intervalle d’une frame. La pause et l’image par image, elles, montrent chaque frame. Le CPU du processus pendant ces 8 s était d’environ 130 % d’un cœur (capture, encodage et décodage ensemble), contre environ 51 % en direct seul au jalon 2. Le débit de la caméra n’a pas baissé.

Cette limite d’environ 20 images/s en lecture continue est acceptée. Le replay continu sert à retrouver une arrivée et à revenir sur les dernières secondes. Le départage précis reste Pause, image précédente, image suivante. On ne cherche pas à porter le replay continu à 30 images/s.

## Enregistrement (jalon 4)

`SessionRecorder` ouvre un MP4 `mp4v`, dans un thread `video-writer`. L’interface affiche `Session : 001`, la durée `00:02:33` et un bandeau `● REC`. Le bandeau n’est pas incrusté dans l’image. Arrêter l’enregistrement remet la ligne Session à « — » et garde la course. Arrêter la caméra, ou fermer la fenêtre, finalise d’abord le fichier.

Le numéro vient du plus grand `session-NNN` déjà présent pour ce `course_slug`, et du compteur en mémoire, puis on avance encore si ce chemin existe. Deux courses de même nom à des dates différentes restent distinctes grâce à la date et à l’heure dans le nom. Il n’y a pas de base. Le slug n’est pas une clé unique.

La cadence du conteneur est fixée à l’ouverture. Si le FPS mesuré est à moins de 2 images/s de la demande, on écrit à la cadence demandée (30 sur cette machine). Sinon on prend la mesure. On n’écrit pas une image sur deux et on ne rééchantillonne pas. La durée lue vaut donc `frames_written / file_fps`. L’horloge dans l’image reste celle de la capture, pas celle de l’écriture.

### Mesure du 3 octobre 2026, session de 153 s

Webcam 1920×1080, YUY2, DirectShow, `file_fps` 30. Replay 20 s, pause et image suivante pendant l’enregistrement. Le bandeau REC est resté affiché. Aucune image perdue par la file.

| | Valeur |
| --- | --- |
| FPS caméra pendant l’enregistrement | 30,2 à 30,3 |
| FPS caméra pendant replay et enregistrement | 30,1 |
| Images écrites | 4 603 |
| Images perdues | 0 |
| Durée réelle | 153,12 s |
| Durée du fichier (`4603 / 30`) | 153,43 s |
| Écart | 0,31 s |
| Taille | 334 Mo, soit 131 Mo par minute |
| Buffer pendant l’enregistrement | environ 900 images, 30 s, 196 à 210 Mo |
| JPEG moyen | 3,9 ms, aucun échec |
| CPU du processus sur les 12 premières secondes | environ 116 % d’un cœur |
| Retour LIVE pendant l’enregistrement | 5,5 ms |

Extrapolation de cette scène, codec `mp4v` : 10 minutes ≈ 1,3 Go, 30 minutes ≈ 3,9 Go, 60 minutes ≈ 7,8 Go. Ce n’est pas une estimation H.264.

Une image extraite pendant le replay porte l’heure de capture `13:25:21.364`, une seconde après le début du replay, pas l’heure du début du snapshot. Le fichier n’a pas de trou à cet endroit. L’horloge reste lisible. VLC n’est pas installé sur ce PC : la relecture de contrôle a été faite avec OpenCV, qui a rendu les 4 603 images.

Un redémarrage de l’application a ouvert `session-003` parce que `session-001` et `session-002` existaient déjà. Il ne les a pas remplacées.

## Encodage Windows

Cible : un fichier `.mp4`. Le codec retenu pour le jalon 4 est `mp4v`.

Le wheel `opencv-python` pour Windows embarque FFmpeg sans libx264 (licence). `avc1` demande une DLL OpenH264 absente et a produit, sur l’essai synthétique, un fichier plus gros que `mp4v`. FFmpeg externe n’est pas ajouté.

Ordre d’essai prévu :

| FourCC | Conteneur | Intérêt | Risque |
| --- | --- | --- | --- |
| `mp4v` | MP4 | Présent dans presque tous les wheels OpenCV, lecture VLC fiable | Fichiers plus gros, Films et TV parfois réticent |
| `H264` ou `avc1` | MP4 | Plus compact, souvent accepté par les lecteurs Windows si l’encodeur système existe | Souvent absent du wheel officiel |
| `XVID` | AVI | Très compatible | Ce n’est pas le MP4 demandé |

FFmpeg en processus séparé n’est ajouté que si aucun fourcc OpenCV ne produit un MP4 acceptable. On n’en fait pas une dépendance du jalon 1.

La cadence réellement écrite est décrite dans la section Enregistrement. Le texte dans l’image reste la référence de temps pour l’opérateur.

### Espace disque

La mesure `mp4v` de cette webcam, scène d’intérieur peu mouvante, est 131 Mo par minute. L’écran affiche l’espace libre du disque qui contient `recordings/`, par exemple `Espace disponible : 82 Go`. Sous `DISK_FREE_WARNING_BYTES` (10 Go, soit un peu plus d’une heure à ce débit), la ligne passe en avertissement. L’enregistrement n’est pas bloqué par ce seuil. Il s’arrête seulement si l’écriture échoue vraiment.

## États

L’interface n’a pas de machine à états séparée. Les quatre situations sont :

| Situation | Écran | Caméra |
| --- | --- | --- |
| `IDLE` | EN ATTENTE | fermée |
| `SESSION_ACTIVE` | LIVE — ENREGISTREMENT, bandeau REC | ouverte, fichier en cours |
| `LIVE_REPLAY` | REPLAY — N s, ou REPLAY EN PAUSE, bandeau REC | toujours ouverte, fichier en cours |
| `ARCHIVE_PLAYBACK` | ARCHIVE | fermée |

Démarrer session ouvre la caméra puis l’enregistrement, dès la première image. Arrêter session demande une confirmation, puis ferme le fichier et la caméra. Le bouton Archives est inactif pendant la capture. Un clic qui arriverait quand même prévient que la capture ne sera pas interrompue.

Pendant l’enregistrement, le bandeau `● REC — 00:12:43` reste visible, y compris en replay. Après l’arrêt, la session affichée redevient « — » et le bandeau disparaît.

Raccourcis, ignorés dans un champ de saisie et dans une boîte de dialogue : `1` ou `F1` replay 10 s, `2` ou `F2` replay 20 s, `3` ou `F3` replay 30 s, `Espace` pause ou reprise, flèches gauche et droite une image en pause, `Échap` retour LIVE. Les mêmes flèches et `Espace` marchent aussi dans l’archive. Le retour LIVE affiche tout de suite la dernière image BGR.

## Données de l’opérateur

Les préférences et les journaux sont dans `%LOCALAPPDATA%\Finish`. L’exécutable enregistre par défaut dans `Documents\Finish\recordings`. En développement, les vidéos restent dans `recordings/` à la racine du projet, pour que les archives déjà là restent visibles. Le dossier peut toujours être changé dans les paramètres avancés.

La version est `version.py`. Elle est écrite dans le journal au démarrage et dans le `course.json` exporté.

## Écrans

Trois vues dans la même fenêtre : Pré-course, Course en cours, Archives. Le style est dans `ui/theme.py`. La capture reçoit l’index, la résolution, le FPS, la durée de buffer et la qualité JPEG choisis à l’écran. Sans choix, les constantes de `config.py` restent celles des jalons validés.

Les archives sont des `CourseArchive` calculées à la lecture des JSON, toujours dans le dossier plat. L’export copie les octets. Il refuse un dossier absent, un fichier déjà présent ou un disque trop petit. Il vérifie la taille après copie. La suppression des originaux est une action séparée.

## Journal de session

Chaque passage important est écrit dans `logs/finish.log`, avec l’horodatage du journal, le nom de course et le numéro de session quand il est connu :

`SESSION START REQUESTED`, `CAMERA STARTED`, `RECORDER STARTED`, `SESSION RECORDING`, `STOP REQUESTED`, `RECORDER STOPPING`, `RECORDER CLOSED`, `CAMERA STOPPED`, `SESSION CLOSED`.

Une caméra absente produit `CAMERA UNAVAILABLE`, aucun MP4, et `SESSION CLOSED`. Les threads `camera-capture` et `video-writer` attrapent toute exception et appellent `logging.exception`, donc la trace complète va dans le même fichier. L’arrêt inexpliqué de 51 s reste sans cause : cette prise n’écrivait pas dans le journal. Aucun correctif n’a été ajouté sur une hypothèse.

## Consultation des sessions

`scan_recordings` lit `recordings/` à l’ouverture de l’écran Archives. Chaque session valide est un MP4 et un JSON de même radical. Les champs affichés viennent du JSON. Le nom de fichier ne fait qu’associer les deux.

Un MP4 sans JSON, ou un JSON sans MP4, est `INCOMPLETE` dans le journal et n’apparaît pas dans la liste. Un JSON illisible, un nom de vidéo qui ne correspond pas, ou une vidéo que OpenCV n’ouvre pas, est `INVALID`. L’application continue.

La liste groupe par `course_name`. La course la plus récente est en haut. Dans une course, la session la plus récente est en haut. Une ligne montre la date, l’heure, `Session 003` et la durée, par exemple `02:33`.

`ArchivePlayer` ouvre le MP4 tout seul. Il ne connaît ni `CameraCapture`, ni le buffer, ni `ReplayPlayer`. Lecture, pause, stop, barre de position, temps `00:01:12 / 00:02:33`. En pause, image suivante et image précédente. L’horloge incrustée n’est pas redessinée.

La lecture continue suit le temps du fichier : si l’affichage est en retard, des images sont sautées pour que deux minutes de vidéo durent deux minutes. L’image par image, elle, avance ou recule d’un index exact. Sur les MP4 `mp4v` produits ici, `CAP_PROP_POS_FRAMES` puis une lecture tombe sur l’index demandé. Si un autre codec se calait sur une image-clé, le journal dirait `Archive seek mismatch` et l’image montrée serait celle réellement décodée.

« Aller à l’heure » accepte `HH:MM:SS` et `HH:MM:SS.mmm`. L’heure est placée sur le jour de `start_time`, puis convertie avec `file_fps`. Avant le début, la lecture va à la première image. Après la fin, à la dernière. Un texte illisible affiche un exemple, sans boîte d’erreur. Ce repérage n’est pas un chronométrage : à 30 images/s une image vaut environ 33 ms, et l’horloge incrustée peut différer de quelques dixièmes parce que la durée du fichier est `images / file_fps`. Sur la session 003, `13:25:21` a affiché l’image incrustée `13:25:20.968`. L’ajustement se fait ensuite en pause, image par image. Une session qui passe minuit n’est pas gérée : l’heure est toujours celle du jour de début.

Mesure du 3 octobre 2026, sans ouvrir la caméra : les trois sessions sont listées, la 003 se lit, la pause et l’image par image tombent sur l’index voisin, un saut à l’image 1680 affiche `13:25:21.364`. Trois secondes de lecture font avancer le fichier d’environ 89 images, soit le temps réel. Le CPU du processus pendant cette lecture est d’environ 250 % d’un cœur. Une seule image décodée est gardée à la fois.

## Essai de 15 minutes

Le 3 octobre 2026, une session « Endurance jalon 6 » a tourné 900,8 s. Replays 10, 20 et 30 s, pause, image par image et retour LIVE pendant l’enregistrement. Le bandeau REC est resté affiché. Arrêt confirmé, puis deux autres sessions de la même course, une course « Course CE1 », et une reprise du même nom après redémarrage. Aucun ancien fichier n’a été réécrit. 0 image perdue. Les threads `camera-capture` et `video-writer` étaient encore là à la fin. Le buffer est resté sur 30 s.

Cette prise n’est pas restée à 30 images/s. 15 338 images en 900,8 s, soit 17 images/s en moyenne. Le compteur instantané a varié entre 11 et 28. Le PC faisait autre chose en même temps. Une sonde plus calme, juste après, a tenu 26 images/s sur 40 s, encode JPEG 9,8 ms, buffer 30 s, 0 perte. Le fichier de 15 minutes pèse 1,13 Go, soit environ 75 Mo par minute à ce débit, et se déclare à 30 images/s parce que ce taux est choisi à l’ouverture. Il dure donc environ 8 min 31 s dans un lecteur, alors que l’horloge incrustée couvre bien les 15 minutes : la première image porte `13:53:57.413`, l’image 15 000 porte `14:08:31.545`. « Aller à l’heure » suit le taux du fichier, pas cette baisse. L’horloge incrustée reste la référence. Le pipeline n’a pas été modifié pour cela.

La mémoire de travail du processus et le CPU n’ont pas pu être lus par l’appel utilisé pendant l’essai. Le buffer, lui, ne dépasse pas 30 s.

## Sessions et archive

Une session est une période continue, avec son propre fichier et son propre JSON. La suivante ne réécrit jamais la précédente.

Nom, pour une course appelée « Course CM2 filles » démarrée le 3 octobre 2026 à 14:32:08 :

```
recordings/2026-10-03_14-32-08_course-cm2-filles_session-001.mp4
recordings/2026-10-03_14-32-08_course-cm2-filles_session-001.json
```

Le JSON garde `course_name` avec la graphie saisie, `course_slug` et `session_id`. Le prochain numéro est le plus grand déjà présent pour ce slug, y compris après un redémarrage. Une course dont le slug n’a encore aucun fichier repart à 1. Pas de base de données. Un nom vide produit le slug `course`.

La lecture d’archive ouvre le fichier avec OpenCV, dans l’interface, sans démarrer le worker caméra. Pause, image précédente, image suivante et barre de temps agissent sur ce lecteur seulement.

## Configuration

Toutes les constantes modifiables sont dans `src/config.py`. Les chemins sont ancrés au dossier du projet (`Path(__file__)`), pas au répertoire courant.

Valeurs initiales : caméra 0, 1920×1080, 30 images/s demandées, buffer 30 s, JPEG 80, dossier `recordings`.

Si la webcam refuse 1920×1080, la résolution réelle est conservée et affichée. L’application ne parcourt pas une liste de modes.

## Journaux

Module `logging`, niveau INFO, console et `logs/finish.log`.

Messages du jalon 1, en anglais, comme dans le cahier des charges :

```
Application started
Camera open requested index=0
Camera opened index=0 backend=DSHOW
Requested resolution=1920x1080
Actual resolution=1920x1080
Requested FPS=30
Driver reported FPS=30.0
Capture fourcc=YUY2
Measured FPS=29.8
Ring buffer started
Buffer duration=30.0s
JPEG quality=80
Average JPEG size=236777
Buffer frames=903
Buffer memory=214071436
JPEG encode average=4.9 ms
Camera read failed index=0
Camera released
Application stopped
Replay requested duration=10s
Replay snapshot frames=302
Replay finished
Returned to LIVE
Return LIVE delay_ms=6.7
Recording started file=2026-10-03_13-24-25_cross-ecole-2026_session-003.mp4
Recording codec=mp4v
Recording fps=30.00
Session id=3
Recording stopped frames=4603 dropped=0
Recording queue overflow — dropped frame total=1
```

`Measured FPS` et le résumé du buffer sont écrits au plus toutes les 30 secondes. Aucune ligne par image. Le fourcc de capture indique si le driver a choisi le MJPEG ; il ne faut pas le confondre avec le codec du futur fichier.

## Arborescence définitive

Le replay, l’enregistrement et l’archive utilisent la même zone d’image. Le lecteur d’archive est `archive_player.py`, pas le replay du direct.

```
Finish/
|-- finish.png                  identité, une seule copie
|-- README.md
|-- requirements.txt
|-- .gitignore
|-- src/
|   |-- main.py                 créé
|   |-- config.py               créé
|   |-- camera/
|   |   |-- capture.py          créé, worker
|   |   |-- fps_meter.py        créé
|   |   |-- timestamp.py        créé
|   |   |-- overlay.py          créé
|   |   |-- fourcc.py           créé
|   |-- video/
|   |   |-- ring_buffer.py      créé
|   |   |-- jpeg_encode.py      créé
|   |   |-- jpeg_meter.py       créé
|   |   |-- replay.py           créé
|   |   |-- recorder.py         créé
|   |   |-- archive_player.py   créé
|   |-- sessions/
|   |   |-- names.py            créé
|   |   |-- course.py           créé
|   |   |-- archive.py          créé
|   |   |-- catalog.py          créé
|   |   |-- metadata.py         créé
|   |-- ui/
|       |-- main_window.py      créé
|       |-- live_view.py        créé
|       |-- branding.py         créé
|       |-- archive_panel.py    créé
|-- recordings/
|-- logs/
|-- docs/
|   |-- ARCHITECTURE.md
|   |-- PLAN.md
|   |-- DECISIONS.md
|-- tests/
```

`camera/` n’importe pas PySide6. `ui/` peut importer OpenCV et `camera`.

## Constat sur le PC de développement

Mesuré le 3 octobre 2026, sans en faire une généralité :

- la webcam 0 s’ouvre en DirectShow et livre 1920×1080, YUY2, à 29,8 images/s ;
- l’ouverture jusqu’à la première image prend environ 6 secondes, pendant lesquelles l’interface reste utilisable ;
- `mp4v` produit un MP4 qu’OpenCV relit. `avc1` aussi, avec une erreur `openh264` au démarrage et un fichier d’essai beaucoup plus gros. Le détail est dans `docs/DECISIONS.md`, décision D9 ;
- la taille d’une heure de course n’a pas été mesurée ;
- avec le buffer JPEG, le débit reste à environ 30 images/s. La mémoire JPEG se stabilise vers 214 Mo sur la scène du jalon 2, et vers 200 à 205 Mo sur celle du jalon 3 ;
- le replay 10, 20 et 30 s laisse la caméra à environ 30 images/s. Le retour au direct prend moins de 10 ms. Le détail est dans la section Replay.

## Ce qui peut échouer

| Situation | Comportement du jalon 1 |
| --- | --- |
| Caméra absente ou déjà ouverte | Message, journal, retour à l’attente |
| Débranchement pendant le direct | Même traitement, après l’échec de `read` |
| Résolution ou FPS différents de la demande | Affichés tels quels |
| Fermeture de la fenêtre | Arrêt du thread, `release` |
| Driver bloqué dans `read` | La fermeture attend au plus 5 s, puis le processus peut rester vivant tant que le thread n’est pas daemon |
| Coupure électrique, crash, disque corrompu | Hors périmètre. Pas de récupération promise |
| Disque plein | Concernera le jalon 4 : arrêt propre de la session, message, fichier conservé dans l’état où l’encodeur a pu le clore |

## Limite assumée

Aucune protection n’est prévue contre une coupure d’alimentation, un plantage du PC ou une corruption de disque. Un MP4 interrompu de cette façon peut être illisible. La fermeture normale de l’application, elle, devra finaliser le fichier dès que l’enregistrement existera.
