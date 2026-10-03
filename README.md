# Finish

Caméra d’arrivée locale pour une petite course à pied. Le direct affiche l’heure dans l’image, le débit mesuré et la durée du buffer de 30 secondes. Replay 10, 20 et 30 secondes, puis retour au direct. Une session peut être enregistrée dans un fichier MP4.

L’heure incrustée porte des millisecondes pour identifier chaque image. À environ 30 images par seconde, deux images sont séparées d’environ 33 ms. Finish ne départage pas une arrivée à la milliseconde. Le replay continu affiche environ 20 images par seconde ; le départage précis se fait en pause, image par image.

## Installation

Depuis le dossier du projet, avec Python 3.11 ou plus :

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Lancement

Pour le développement :

```powershell
.\.venv\Scripts\python.exe src\main.py
```

Pour le PC de course, construire le dossier portable, puis lancer `dist\Finish\Finish.exe`. Python n’est pas nécessaire sur ce PC.

```powershell
.\scripts\build.ps1
```

L’écran d’accueil est la pré-course : nom, caméra, résolution, FPS, puis **Démarrer la course**. Les réglages de buffer, de JPEG et de dossier sont sous **Paramètres avancés**. **Tester caméra** montre l’image quelques secondes sans créer de fichier.

**Arrêter session**, ou la fermeture de la fenêtre, ferme le fichier puis libère la webcam.

**Archives** regroupe les sessions par course et les relit sans ouvrir la caméra. Cet écran reste fermé pendant une session en cours. Dans une archive, **Aller à l’heure** accepte `13:25:21` ou `13:25:21.350`, puis l’image par image sert à ajuster. **Session précédente** et **Session suivante** passent d’un segment à l’autre. **Exporter** copie les fichiers vers un dossier, une clé ou un disque, sans réencodage. La suppression des originaux n’est proposée qu’une fois la copie vérifiée.

**Nouvelle course** demande une confirmation si une course est déjà choisie. **Arrêter session** demande une confirmation. Les archives déjà écrites ne sont pas effacées.

Raccourcis pendant une session : `1` replay 10 s, `2` replay 20 s, `3` replay 30 s, `Espace` pause, flèches gauche et droite une image, `Échap` retour au direct. `F1`, `F2` et `F3` font les mêmes replays.

L’écran indique l’espace libre du disque des enregistrements. Sous 10 Go, un avertissement s’affiche. L’enregistrement continue tant que le disque accepte l’écriture.

Les journaux vont dans `%LOCALAPPDATA%\Finish\logs`. **À propos** ouvre ce dossier. Quelques fichiers sont conservés, puis les plus anciens sont écartés.

L’exécutable propose `Documents\Finish\recordings`. En développement, les vidéos restent dans `recordings/` du projet. Le dernier dossier choisi est mémorisé, ainsi que la caméra, la résolution, le FPS, le buffer, la qualité JPEG et le lieu. Le nom de la course ne l’est pas.

## Utilisation le jour de la course

1. Brancher la webcam.
2. Lancer Finish. L’écran Pré-course s’ouvre.
3. Choisir la caméra, vérifier la résolution et le FPS, saisir le nom de la course.
4. Démarrer la course.
5. Surveiller le direct et le bandeau REC.
6. Replay 10, 20 ou 30 s en cas de doute, puis retour au direct.
7. Arrêter session pendant les temps morts, puis relancer une session.
8. Ouvrir Archives après la course.
9. Revoir une session, l’exporter, puis supprimer la copie locale seulement si l’export est réussi.

## Tests

Les tests ne nécessitent pas de webcam.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

L’essai avec la vraie caméra est décrit dans `docs/PLAN.md`.

## Documentation

- `docs/ARCHITECTURE.md` — pipeline, threads, mémoire, codec, risques
- `docs/PLAN.md` — jalons
- `docs/DECISIONS.md` — choix techniques

Les jalons 1 à 7 sont validés. Le jalon 8 (distribution Windows) est implémenté. Le guide de l’opérateur est `docs/USER_GUIDE.md`.
