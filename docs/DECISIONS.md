# Décisions — Finish

Les décisions retenues engagent le code actuel. Les décisions proposées sont assez précises pour le jalon suivant, et ne sont pas implémentées. Celles qui dépendent de la webcam restent ouvertes jusqu’à l’essai du jalon 1.

## D1 — Périmètre

Statut : retenue.

L’application est un outil local de direct, de replay court et d’archive. Elle ne classe pas les coureurs, ne les reconnaît pas, et ne fournit pas un temps officiel.

Conséquence : pas de Docker, de serveur, de navigateur, de base de données, de cloud, ni de compte utilisateur.

## D2 — Langage et bibliothèques

Statut : retenue.

Python 3.11 ou plus, OpenCV, PySide6, et la bibliothèque standard (`threading`, `queue`, `logging`, `dataclasses`, `pathlib`, `json`, `datetime`, `time`). Les tests utilisent `unittest`.

`collections.deque` sera le support du buffer au jalon 2.

FFmpeg n’est pas une dépendance tant qu’OpenCV ne s’est pas montré insuffisant pour le MP4.

## D3 — Thread de capture, interface en tirage

Statut : retenue.

Options écartées :

| Option | Motif du rejet |
| --- | --- |
| Lire la webcam dans le thread Qt | Un `read` lent figerait les boutons. Interdit par le cahier des charges |
| `QThread` plus un signal par image | La file d’événements peut prendre du retard et afficher un direct périmé |
| `multiprocessing` | Coût et complexité inutiles : OpenCV relâche déjà le GIL |
| `asyncio` | `VideoCapture.read` est bloquant |

Choix : `threading.Thread` nommé `camera-capture`. L’interface lit la dernière image avec un `QTimer` de 33 ms. Si l’interface est lente, elle saute des images à l’écran. La capture, elle, ne l’attend pas.

Le worker n’importe pas PySide6.

## D4 — DirectShow, puis backend par défaut

Statut : validé sur ce PC le 3 octobre 2026. À recontrôler si la caméra change.

Sous Windows, beaucoup de webcams UVC s’ouvrent de façon plus prévisible avec `CAP_DSHOW` qu’avec Media Foundation. Le worker essaie DirectShow, puis `CAP_ANY` si l’ouverture échoue.

Le tampon interne du driver est demandé à 1 image (`CAPTURE_BUFFER_SIZE`) pour limiter la latence. Certains backends ignorent cet appel ; ce n’est pas une erreur.

Vérifié sur ce PC : l’image n’est pas noire, le journal indique `backend=DSHOW`, et un arrêt demandé pendant l’ouverture libère le thread.

`PREFER_DIRECTSHOW` dans `src/config.py` permet de désactiver cet essai sans modifier le worker.

## D5 — Ne pas forcer le MJPEG de capture

Statut : maintenu. Sur ce PC, le 3 octobre 2026, la caméra 0 fournit déjà 1920×1080 en YUY2 à 29,8 images/s. Forcer le MJPEG n’apporte rien ici.

Le 1920×1080 non compressé à 30 images/s dépasse souvent l’USB 2.0 (environ 124 Mo/s en YUY2). Les webcams ne tiennent alors cette cadence qu’en MJPEG.

Forcer `CAP_PROP_FOURCC = MJPG` avant d’avoir vu le matériel peut empêcher une caméra de s’ouvrir. Le jalon 1 n’impose donc pas de format. Il journalise le fourcc réel.

Si le FPS mesuré est nettement sous 30 à la résolution voulue, l’essai suivant consiste à demander le MJPEG, pas à changer d’architecture.

## D6 — Heure locale affichée à la milliseconde

Statut : retenue.

`datetime.now()` fournit le texte. Le fuseau est celui du PC, pas l’UTC : l’opérateur compare l’image à sa montre.

Le cahier des charges cite à la fois `TIMESTAMP_FORMAT = "%d/%m/%Y %H:%M:%S.%f"` et l’exemple `03/10/2026 10:42:17.533`. `%f` écrit six chiffres. L’affichage suit l’exemple, sur trois chiffres, par troncature.

`time.monotonic()` est la seule horloge des durées, du FPS et, plus tard, du buffer et du replay.

## D7 — Accepter la résolution réelle

Statut : retenue, avec une vérification visuelle.

La demande est 1920×1080 à 30 images/s. Beaucoup de webcams de portable livrent 1280×720. L’application affiche et journalise la taille de l’image reçue. Elle ne considère pas l’écart comme une panne et ne teste pas une cascade de modes.

L’index par défaut est 0. Une caméra virtuelle (OBS, téléphone) peut occuper cet index. C’est `CAMERA_INDEX` qu’il faut changer. Il n’y a pas de sélecteur dans l’interface.

Le nom convivial Windows (« USB Camera ») n’est pas lu : il demanderait une bibliothèque ou un appel WMI supplémentaire. L’interface montre l’index et le backend.

## D8 — Buffer JPEG qualité 80, dans le thread de capture

Statut : retenue le 3 octobre 2026.

Options écartées :

| Option | Motif |
| --- | --- |
| BGR brut en mémoire | Environ 5,6 Go pour 30 s en 1080p |
| Sous-échantillonner à 720p | L’image par image servirait à départager une arrivée sur une image dégradée |
| Garder une image sur deux | On perdrait l’image décisive |

Choix : `deque` de JPEG qualité 80, éviction par timestamp monotonic, instantané par copie de la liste de références. Les octets ne sont pas recopiés. Détail des tailles dans `docs/ARCHITECTURE.md`.

L’encodage JPEG du buffer et l’encodage du fichier sont deux opérations. Le fichier ne doit pas être produit en réencodant le JPEG, sinon l’archive aurait les artefacts du buffer.

Qualité 80 : assez légère pour la mémoire, assez propre pour un arrêt sur image. On ne descendra pas sans un essai visuel sur deux silhouettes proches.

Mesure sur la webcam 1920×1080 : encodage moyen 4,9 ms, FPS resté à environ 30,2 contre 29,8 sans buffer, 903 images et 214 Mo une fois les 30 secondes pleines. Le maximum observé, 13,4 ms, n’a pas fait baisser le débit. Le second thread d’encodage n’est pas créé. Le CPU du processus pendant la capture avec buffer est d’environ 51 % d’un cœur.

## D9 — MP4 via OpenCV, `mp4v`

Statut : retenue le 3 octobre 2026 pour le jalon 4.

`mp4v` est le codec du fichier. `avc1` n’est pas utilisé : la DLL OpenH264 manque, et l’essai synthétique était plus gros. FFmpeg externe n’est pas ajouté. La cadence du conteneur est 30 images/s quand la mesure est à moins de 2 images/s de la demande, sinon la mesure arrondie.

Sonde locale du 3 octobre 2026, OpenCV 4.14, image synthétique 640×480, 25 images. Lecture de contrôle faite avec OpenCV, pas encore avec VLC.

| FourCC | Fichier relu | Écart moyen avec l’image source | Taille |
| --- | --- | --- | --- |
| `mp4v` | 25 images | environ 1,8 niveau sur 255 | 37 Ko |
| `avc1` | 25 images | environ 0,3 niveau | 801 Ko |
| `XVID` | 25 images, conteneur AVI | environ 1,8 niveau | 43 Ko |

`avc1` et `H264` affichent une erreur : la bibliothèque `openh264-2.5.0-win64.dll` est absente, puis OpenCV annonce que l’encodeur n’a pas pu s’ouvrir. Un fichier lisible par OpenCV est pourtant produit. Ce chemin n’est pas retenu tant qu’il n’a pas été ouvert dans VLC et comparé sur une vraie scène : l’erreur au démarrage le rend fragile, et le fichier d’essai est beaucoup plus gros que `mp4v`.

`VideoWriter.write` renvoie `None` dans ces bindings. Le nombre d’images écrites compte les appels, pas cette valeur de retour.

L’essai synthétique ne sert pas à estimer une course. La mesure webcam du 3 octobre 2026 est 131 Mo par minute en `mp4v` 1920×1080, soit environ 1,3 Go, 3,9 Go et 7,8 Go pour 10, 30 et 60 minutes.

## D10 — File d’écriture bornée, perte explicite

Statut : retenue et en place. Trente images au plus, soit environ une seconde. Sur la session de 153 s, aucune image n’a été perdue et le FPS caméra est resté vers 30.

La capture dépose l’image BGR déjà horodatée avec `put_nowait`. Si la file est pleine, l’image nouvelle est comptée comme perdue et la capture continue. Le journal le dit au plus une fois par seconde, avec le total.

Une perte se verra dans le fichier : l’horloge incrustée saute, parce que l’écriture est à cadence constante.

Attendre une place dans la file est refusé : le disque bloquerait la webcam.

## D11 — Pas de file d’affichage

Statut : retenue.

C’est le mécanisme du retour au direct immédiat. Documenté dans `docs/ARCHITECTURE.md`. Le jalon 1 l’applique déjà : le timer n’affiche que la dernière image publiée.

## D12 — Chemins ancrés au projet

Statut : retenue.

`RECORDINGS_DIR`, `logs/` et `finish.png` sont calculés depuis l’emplacement de `src/config.py`, pas depuis le répertoire courant. Lancer `python src\main.py` depuis un autre dossier n’écrit pas les journaux ailleurs et trouve quand même le logo.

## D13 — Journaux anglais, interface française

Statut : retenue.

Les messages de log reprennent les exemples du cahier des charges, en anglais, pour rester stables et comparables. Les libellés vus par l’opérateur sont en français.

Pas de rotation de fichiers, pas de niveaux multiples. Un fichier `logs/finish.log` en ajout, plus la console.

## D14 — Mise à l’échelle rapide

Statut : retenue.

L’affichage utilise `FastTransformation` et `KeepAspectRatio`. L’interpolation lisse à chaque image 1080p coûterait du CPU dans le thread interface sans aider à voir une arrivée. Le zoom soigné, plus tard, concerne l’image en pause, pas le direct.

## D15 — Fermeture

Statut : retenue.

Le thread caméra n’est pas daemon, pour que `VideoCapture.release` ait lieu. À la fermeture de la fenêtre, l’interface demande l’arrêt et attend au plus 5 secondes.

Limite : si le driver reste bloqué dans `read`, le processus peut survivre à la fenêtre. Ce cas est journalisé. Il n’y a pas de `os._exit`.

Dès le jalon 4, cette même fermeture devra vider la file d’écriture et clore le MP4 avant de quitter. Un crash ou une coupure électrique restent hors garantie.

## D16 — Course et session

Statut : le vocabulaire et le modèle en mémoire sont en place. L’écriture disque arrive au jalon 4. La protection contre un redémarrage qui réutiliserait un numéro arrive au jalon 5.

Une course a `course_name` (texte saisi, jamais réécrit) et `course_slug` (fichier seulement). Une session a `session_id`, entier, à l’intérieur de la course active. Le nom de la course n’identifie pas la session.

Une seule course est active. Elle est demandée au premier direct et conservée. « Nouvelle course » la remplace et remet les numéros de session à 1, sans toucher à la caméra. Le jalon 3 n’affiche pas de faux numéro : la ligne Session reste « — » tant qu’aucun enregistrement n’est ouvert.

Le nom de fichier prévu est `aaaa-mm-jj_hh-mm-ss_<course_slug>_session-001`. Le slug est déterministe. Le JSON conservera la graphie d’origine.

## D19 — Snapshot par références, décodage d’une image

Statut : retenue le 3 octobre 2026.

`snapshot_last_seconds` renvoie une nouvelle liste des mêmes `BufferedFrame`. Les `bytes` JPEG ne sont pas copiés. `ReplayPlayer` garde ces références. L’interface décode un JPEG, l’affiche, puis le remplace.

Mesure : au clic Replay 30 s, la taille du snapshot et celle du buffer étaient identiques (202 696 959 octets). Le surplus n’apparaît qu’ensuite, pour les images que le tampon circulaire a déjà évincées et que le lecteur tient encore. Pas de second bloc de 200 Mo, pas de 900 matrices BGR.

## D20 — Replay dans le thread interface

Statut : retenue le 3 octobre 2026.

Pas de thread de replay. Un `QTimer` de 33 ms appelle `ReplayPlayer.advance`. La cible est le timestamp monotonic de la première image, plus le temps réel écoulé. Un tick en retard saute des images pour que l’horloge incrustée suive l’heure de capture, au lieu de ralentir le replay.

Conséquence mesurée : environ 20 images affichées par seconde sur 30 capturées, parce que le décodage et la mise à l’échelle 1080p dépassent l’intervalle d’une frame. La caméra, elle, est restée vers 30 images/s. L’image par image en pause parcourt chaque frame.

Validé le 3 octobre 2026 : on ne cherche pas à afficher le replay continu à 30 images/s. Le départage de deux coureurs se fait en pause, image par image. Les millisecondes incrustées identifient l’image ; à 30 images/s, la résolution temporelle réelle est d’environ 33 ms.

## D21 — Retour LIVE immédiat

Statut : retenue le 3 octobre 2026.

Retour LIVE et fin naturelle du snapshot font la même chose : arrêter le timer de replay, oublier le lecteur, peindre la dernière image BGR déjà publiée. Pas de décodage JPEG pour ce retour, pas de vidage du buffer, pas de redémarrage caméra. Délai mesuré : 5 à 8 ms. L’index affiché était celui de la capture au même instant.

## D17 — Logo unique

Statut : retenue.

`finish.png` reste à la racine. La fenêtre et l’icône le lisent via `LOGO_PATH`. Pas de copie, pas de fichier de ressources Qt.

## D18 — Nom vide

Statut : retenue.

Un nom vide ou composé d’espaces devient `Course` à l’affichage et `course` dans le fichier. Le démarrage n’est pas bloqué. Un nom fait seulement de symboles garde son texte à l’écran, et le fichier reçoit le slug de repli `session`, parce qu’un nom de fichier ne peut pas être vide.

## Constat du 3 octobre 2026

PC de développement, Python 3.13, OpenCV 4.14, PySide6 6.11, webcam index 0 :

- backend DirectShow ;
- résolution réelle 1920×1080, identique à la demande ;
- fourcc de capture `YUY2` ;
- FPS mesuré 29,8 ;
- première image environ 6 secondes après la demande d’ouverture ;
- arrêt du thread et `Camera released` confirmés ;
- la fenêtre, via le bouton Démarrer, affiche le direct puis revient à l’attente avec Arrêter.

Le jalon 1 a été validé sur cette configuration, y compris l’horodatage en haut à gauche.

## D22 — Pas d’écrasement, numéro lu sur le disque

Statut : retenue le 3 octobre 2026.

Avant d’ouvrir un MP4, Finish cherche les `session-NNN` déjà rangés pour ce `course_slug` et prend le numéro suivant. Si le chemin exact existe quand même, il avance encore. Il n’ouvre jamais un fichier existant. Le slug seul n’identifie pas l’événement : la date et l’heure sont dans le nom. Pas de base de données.

## FUTURE OPTIMIZATION — compact video codec

Statut : notée, pas commencée.

Le MP4 en `mp4v`, 1080p et 30 fps occupe environ 131 Mo par minute. C’est accepté pour Finish 0.1. Réduire cette taille demanderait FFmpeg ou un autre codec, donc un réencodage. On ne le fait pas avant un essai terrain.

La fusion de plusieurs sessions en une seule vidéo reste aussi pour plus tard. L’export principal est une copie des fichiers, sans réencodage.

## Emplacement des données

Statut : retenue.

À côté de l’exécutable, Windows peut refuser l’écriture. Les préférences et les journaux vont dans `%LOCALAPPDATA%\Finish`. Les vidéos de l’application packagée vont dans `Documents\Finish\recordings`, sauf si l’opérateur choisit un autre dossier. En développement, les vidéos restent dans le `recordings/` du projet.

Il n’y a pas de corbeille interne.

## Dossiers d’archives

Les sessions déjà enregistrées restent des fichiers à plat dans `recordings/`. Un dossier par course rendrait l’archive plus lisible, mais déplacer les fichiers existants les rendrait introuvables pour le catalogue actuel. Ce déplacement n’est pas fait.

L’export d’une course crée, lui, un dossier au nom de la course, avec `session-001.mp4`, le JSON ajusté au nouveau nom de vidéo, et un `course.json`. Les originaux ne sont pas modifiés.

Il n’y a pas de corbeille. Supprimer une session ou une course retire les fichiers pour de bon, après confirmation. Après un export, la suppression locale n’est proposée que si chaque copie a la taille attendue. Un export annulé, incomplet ou trop gros pour la destination ne donne pas le droit d’effacer.

La fusion de toutes les sessions en une seule vidéo n’est pas livrée. Elle demanderait FFmpeg ou un réencodage.

## KNOWN ISSUE — arrêt d’enregistrement observé une fois

Le 3 octobre 2026, une prise ouverte à 13:18:37 s’est terminée au bout de 51,5 s, avant le replay prévu. Le MP4 et le JSON sont complets : 1 547 images, 0 perte, `end_time` renseigné. Le fichier se relit. Ce n’est donc pas un `VideoWriter` resté ouvert ni un fichier corrompu.

`logs/finish.log` n’a aucune ligne entre 12:17:34 et 13:24:20. Cette prise a été lancée par un script qui n’appelait pas la configuration des journaux. Il n’existe donc aucune trace d’exception, d’arrêt demandé par l’interface, d’erreur caméra, d’erreur disque ou de fermeture de fenêtre. La fenêtre était visible à l’écran. La cause n’est pas identifiée. Aucun correctif n’est ajouté sur une hypothèse. Les prises suivantes, dont celle de 153 s, se sont arrêtées sur une demande explicite (`stop-recording`) et sont dans le journal. Le jalon 6 ajoute les lignes de cycle, avec la course et le numéro : demande de démarrage, caméra, enregistreur, arrêt, fermeture. Si l’incident se reproduit, le journal doit maintenant le situer. Le pipeline d’enregistrement n’a pas été modifié pour cela.

## Décisions qui attendent un œil humain

1. `mp4v` pèse 131 Mo par minute sur cette scène. Faut-il le garder, sachant que 60 minutes font environ 7,8 Go, ou chercher plus tard un codec plus compact ?
2. VLC n’est pas installé sur le PC de développement. L’ouverture du fichier dans VLC reste à faire sur un poste qui l’a.
3. Le libellé par défaut `Course`, et le slug `course` pour un nom vide, conviennent-ils à l’opérateur ?
