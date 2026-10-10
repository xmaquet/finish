"""Texte de l'aide affichée dans l'application."""

HELP_HTML = """
<h2>Finish</h2>
<p>Aide vidéo pour revoir une arrivée. Ce n'est pas un chronométrage homologué.</p>
<h3>Pré-course</h3>
<p>Écrire le nom de la course avant de la démarrer. Le lieu est facultatif.</p>
<p><b>Détecter les caméras</b> remplit la liste. <b>Tester caméra</b> montre l'image
dans cet écran, sans créer de fichier. <b>Arrêter le test</b> libère la caméra.</p>
<p><b>Démarrer la course</b> ouvre le direct et enregistre une session.</p>
<p><b>Terminer la course</b> n'est disponible qu'une fois la course démarrée,
et seulement si aucune session n'est en cours. Une confirmation est demandée.</p>
<h3>Course en cours</h3>
<p>Chaque enregistrement est une session. <b>Arrêter session</b> ferme le fichier
et laisse la course ouverte. <b>Démarrer une session</b> en tourne une autre.</p>
<p><b>Replay 10 s</b>, <b>20 s</b> ou <b>30 s</b> revient en arrière sans arrêter
l'enregistrement. <b>Pause</b>, puis <b>&lt; Image</b> et <b>Image &gt;</b>.
<b>Retour LIVE</b> reprend le direct.</p>
<p>Raccourcis : 1, 2, 3, Espace, flèches, Échap.</p>
<h3>Archives</h3>
<p><b>Lecture</b> joue la session à vitesse normale, celle de l'horloge incrustée.
<b>x2</b> et <b>x3</b> accélèrent. <b>x1</b> revient au temps réel.</p>
<p><b>Aller à l'heure</b> accepte 13:25:21. <b>Session précédente</b> et
<b>Session suivante</b> passent d'un segment à l'autre.</p>
<h3>Exporter</h3>
<p>Depuis Archives, l'export copie les vidéos et les fiches sans les recompresser.
La suppression des originaux n'est proposée qu'après une copie vérifiée.</p>
"""
