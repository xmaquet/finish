"""Fenêtre FINISH.

États visibles : EN ATTENTE, LIVE — ENREGISTREMENT, REPLAY, REPLAY EN PAUSE,
ARCHIVE. L'archive ne démarre pas la caméra.

Raccourcis, hors champ de saisie : 1 ou F1 replay 10 s, 2 ou F2 replay 20 s,
3 ou F3 replay 30 s, Espace pause ou lecture, flèches gauche et droite une
image en pause, Échap retour LIVE.
"""

from __future__ import annotations

import html
import logging
import threading
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QGuiApplication, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from camera.capture import CameraCapture, CaptureSnapshot
from camera.devices import CameraChoice, detect_cameras
from config import (
    CAMERA_INDEX,
    CAMERA_STOP_TIMEOUT_SECONDS,
    DISK_FREE_WARNING_BYTES,
    DISPLAY_INTERVAL_MS,
    JPEG_QUALITY,
    MAX_BUFFER_SECONDS,
    RECORDING_CODEC,
    RECORDING_STOP_TIMEOUT_SECONDS,
    REQUESTED_FPS,
    REQUESTED_HEIGHT,
    REQUESTED_WIDTH,
)
from disk_space import autonomy_message, disk_space_message, format_byte_size, free_bytes
from sessions.archive import reserve_new_session
from sessions.catalog import RecordedSession, format_duration_minutes, scan_recordings
from sessions.course import ActiveCourse, start_course
from sessions.library import CourseArchive, build_courses, format_course_summary, format_summary, library_size
from sessions.readiness import Readiness, course_readiness
from sessions.transfer import (
    ExportResult,
    delete_local_files,
    export_course,
    export_session,
    may_remove_sources,
)
from paths import backdrop_path, default_recordings_dir, logs_dir, preferences_path
from preferences import Preferences, load_preferences, save_preferences
from ui.backdrop import AppBackdrop
from ui.branding import logo_icon, logo_pixmap
from version import ABOUT_TEXT, VERSION
from ui.course_browser import CourseBrowser
from ui.live_view import LiveView
from ui.theme import APP_STYLE
from video.archive_player import ArchivePlayer, locate_frame_for_clock_text, seconds_for_frame
from video.jpeg_encode import decode_jpeg
from video.recorder import RecorderError, SessionRecorder, file_frame_rate
from video.replay import ReplayPlayer

logger = logging.getLogger("finish.ui")
replay_logger = logging.getLogger("finish.replay")


def _format_hms(seconds: float) -> str:
    whole = max(0, int(seconds))
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FINISH")
        self.setWindowIcon(logo_icon())

        self._worker: CameraCapture | None = None
        self._course: ActiveCourse | None = None
        self._player: ReplayPlayer | None = None
        self._recorder: SessionRecorder | None = None
        self._record_when_ready = False
        self._archive_player = ArchivePlayer()
        self._archive_session: RecordedSession | None = None
        self._archive_playing = False
        self._archive_anchor_index = 0
        self._archive_anchor_mono = 0.0
        self._archive_slider_dragging = False
        self._open_session_id: int | None = None
        self._logged_camera_started = False
        self._view = "idle"
        self._preview_mode = False
        self._preview_until = 0.0
        self._recordings_dir = default_recordings_dir()
        self._preferred_camera = CAMERA_INDEX
        self._loading_preferences = False
        self._active_fps = REQUESTED_FPS
        self._pending_cameras: list[CameraChoice] | None = None
        self._archive_course: CourseArchive | None = None
        self._camera_choices = []
        self._detecting = False
        self._export_thread: threading.Thread | None = None
        self._export_cancel = threading.Event()
        self._export_lock = threading.Lock()
        self._export_progress = (0, 0, 0, 0)
        self._export_result = None
        self._export_sources: list[Path] = []
        self._stopping = False
        self._closing = False
        self._shown_index = -1
        self._replay_shown_index = -1
        self._error_shown = False
        self._decode_count = 0
        self._decode_total_ms = 0.0
        self._last_return_live_ms = 0.0

        self._logo = QLabel()
        self._logo.setStyleSheet("background-color: #000000;")
        self._logo.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        pixmap = logo_pixmap()
        if pixmap is not None:
            self._logo.setPixmap(
                pixmap.scaledToHeight(72, Qt.TransformationMode.SmoothTransformation)
            )
        else:
            self._logo.setText("FINISH")

        self._status = QLabel("EN ATTENTE")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_status("EN ATTENTE", "idle")

        self._rec_banner = QLabel("● REC")
        self._rec_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._rec_banner.setStyleSheet(
            "background-color: #9d1c1c; color: white; font-weight: 700; "
            "font-size: 18px; padding: 8px;"
        )
        self._rec_banner.hide()

        self._course_value = QLabel("Course : —")
        self._course_value.setStyleSheet(
            "font-size: 22px; font-weight: 700; background: rgba(255, 255, 255, 180); "
            "border-radius: 6px; padding: 2px 8px;"
        )
        self._session_value = QLabel("Session : —")
        self._session_value.setStyleSheet(
            "font-size: 22px; font-weight: 700; background: rgba(255, 255, 255, 180); "
            "border-radius: 6px; padding: 2px 8px;"
        )
        self._meta_line = QLabel("")
        self._meta_line.setStyleSheet("font-size: 15px;")
        self._meta_line.hide()

        self._live = LiveView()
        self._replay_value = QLabel("")
        self._replay_value.setStyleSheet("font-size: 14px; font-weight: 600;")
        self._tech_label = QLabel("")
        self._tech_label.setStyleSheet("color: #666666; font-size: 12px;")
        self._tech_label.setWordWrap(True)
        self._disk_label = QLabel("")
        self._disk_label.setStyleSheet("color: #666666; font-size: 12px;")
        self._hint = QLabel("Renseignez la course, puis démarrez.")
        self._hint.setObjectName("hint")
        self._hint.setWordWrap(True)
        self._keys_label = QLabel(
            "Raccourcis : 1 · 10 s    2 · 20 s    3 · 30 s    "
            "Espace · pause    flèches · une image    Échap · retour LIVE"
        )
        self._keys_label.setStyleSheet("color: #666666; font-size: 11px;")

        self._start_button = QPushButton("Démarrer la course")
        self._start_button.setObjectName("primary")
        self._start_session_button = QPushButton("Démarrer une session")
        self._start_session_button.setObjectName("primary")
        self._stop_button = QPushButton("Arrêter session")
        self._stop_button.setObjectName("danger")
        self._new_course_button = QPushButton("Nouvelle course")
        self._archives_button = QPushButton("Archives")
        self._replay_10 = QPushButton("Replay 10 s")
        self._replay_20 = QPushButton("Replay 20 s")
        self._replay_30 = QPushButton("Replay 30 s")
        self._return_live = QPushButton("Retour LIVE")
        self._pause_button = QPushButton("Pause")
        self._previous_button = QPushButton("< Image")
        self._next_button = QPushButton("Image >")
        self._open_archive_button = QPushButton("Ouvrir")
        self._back_button = QPushButton("Retour")
        self._archive_play_button = QPushButton("Lecture")
        self._archive_pause_button = QPushButton("Pause")
        self._archive_stop_button = QPushButton("Stop")
        self._archive_previous_button = QPushButton("< Image")
        self._archive_next_button = QPushButton("Image >")
        self._archive_close_button = QPushButton("Fermer")
        self._archive_info_button = QPushButton("Infos")
        self._goto_edit = QLineEdit()
        self._goto_edit.setPlaceholderText("13:25:21")
        self._goto_edit.setFixedWidth(110)
        self._goto_button = QPushButton("Aller à l'heure")

        self._start_button.clicked.connect(self._start)
        self._start_session_button.clicked.connect(self._start)
        self._stop_button.clicked.connect(self._confirm_stop)
        self._new_course_button.clicked.connect(self._new_course)
        self._goto_button.clicked.connect(self._go_to_archive_time)
        self._goto_edit.returnPressed.connect(self._go_to_archive_time)
        self._replay_10.clicked.connect(lambda: self._start_replay(10))
        self._replay_20.clicked.connect(lambda: self._start_replay(20))
        self._replay_30.clicked.connect(lambda: self._start_replay(30))
        self._return_live.clicked.connect(lambda: self._return_to_live(automatic=False))
        self._pause_button.clicked.connect(self._toggle_pause)
        self._previous_button.clicked.connect(lambda: self._step_replay(-1))
        self._next_button.clicked.connect(lambda: self._step_replay(1))
        self._archives_button.clicked.connect(self._on_archives_clicked)
        self._open_archive_button.clicked.connect(self._open_selected_archive)
        self._back_button.clicked.connect(self._leave_archives)
        self._archive_play_button.clicked.connect(self._play_archive)
        self._archive_pause_button.clicked.connect(self._pause_archive)
        self._archive_stop_button.clicked.connect(self._stop_archive)
        self._archive_previous_button.clicked.connect(lambda: self._step_archive(-1))
        self._archive_next_button.clicked.connect(lambda: self._step_archive(1))
        self._archive_close_button.clicked.connect(self._show_archive_list)
        self._archive_info_button.clicked.connect(self._show_archive_info)
        self._stop_button.setEnabled(False)

        self._prepare_nav = QPushButton("Pré-course")
        self._course_nav = QPushButton("Course en cours")
        self._archives_nav = QPushButton("Archives")
        for button in (self._prepare_nav, self._course_nav, self._archives_nav):
            button.setObjectName("nav")
            button.setCheckable(True)
        self._prepare_nav.setChecked(True)
        nav_group = QButtonGroup(self)
        nav_group.setExclusive(True)
        nav_group.addButton(self._prepare_nav)
        nav_group.addButton(self._course_nav)
        nav_group.addButton(self._archives_nav)
        self._prepare_nav.clicked.connect(self._show_prepare)
        self._course_nav.clicked.connect(self._show_course_page)
        self._archives_nav.clicked.connect(self._on_archives_clicked)

        self._course_name_edit = QLineEdit()
        self._course_name_edit.setPlaceholderText("Cross école 2026")
        self._place_edit = QLineEdit()
        self._place_edit.setPlaceholderText("Optionnel")
        self._camera_combo = QComboBox()
        self._camera_combo.addItem("Recherche des caméras…", None)
        self._resolution_combo = QComboBox()
        self._resolution_combo.addItem("1920 × 1080", (1920, 1080))
        self._resolution_combo.addItem("1280 × 720", (1280, 720))
        self._resolution_combo.addItem("640 × 480", (640, 480))
        self._fps_combo = QComboBox()
        for fps in (30, 25, 15):
            self._fps_combo.addItem(str(fps), fps)
        self._buffer_combo = QComboBox()
        for seconds in (30, 20, 10):
            self._buffer_combo.addItem(f"{seconds} s", seconds)
        self._jpeg_combo = QComboBox()
        for quality in (80, 60, 95):
            self._jpeg_combo.addItem(str(quality), quality)
        self._detect_button = QPushButton("Détecter les caméras")
        self._test_button = QPushButton("Tester caméra")
        self._folder_button = QPushButton("Choisir le dossier")
        self._folder_label = QLabel()
        self._folder_label.setObjectName("folderLink")
        self._folder_label.setWordWrap(True)
        self._folder_label.setTextFormat(Qt.TextFormat.RichText)
        self._folder_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self._folder_label.setOpenExternalLinks(False)
        self._folder_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._folder_label.linkActivated.connect(lambda _url: self._open_recordings_folder())
        self._set_folder_label(self._recordings_dir)
        self._readiness = QLabel("À vérifier")
        self._readiness.setObjectName("screenTitle")
        self._autonomy = QLabel("")
        self._autonomy.setObjectName("muted")
        self._autonomy.setWordWrap(True)
        self._camera_report = QLabel("Caméra non testée")
        self._camera_report.setObjectName("muted")
        self._camera_report.setWordWrap(True)
        self._finish_button = QPushButton("Terminer la course")
        self._finish_course_button = QPushButton("Terminer la course")
        self._about_button = QPushButton("À propos")
        self._about_button.setObjectName("nav")
        self._detect_button.clicked.connect(self._detect_cameras)
        self._test_button.clicked.connect(self._start_preview)
        self._folder_button.clicked.connect(self._choose_recordings_folder)
        self._finish_button.clicked.connect(self._finish_course)
        self._finish_course_button.clicked.connect(self._finish_course)
        self._about_button.clicked.connect(self._show_about)
        self._course_name_edit.textChanged.connect(lambda _text: self._refresh_readiness())
        self._place_edit.editingFinished.connect(self._persist_preferences)
        self._camera_combo.currentIndexChanged.connect(lambda _index: self._persist_preferences())
        self._resolution_combo.currentIndexChanged.connect(lambda _index: self._persist_preferences())
        self._fps_combo.currentIndexChanged.connect(lambda _index: self._persist_preferences())
        self._buffer_combo.currentIndexChanged.connect(lambda _index: self._persist_preferences())
        self._jpeg_combo.currentIndexChanged.connect(lambda _index: self._persist_preferences())

        self._tech_toggle = QPushButton("Infos techniques")
        self._tech_toggle.setCheckable(True)
        self._tech_panel = QWidget()
        self._tech_panel.hide()
        self._tech_toggle.toggled.connect(self._tech_panel.setVisible)

        self._course_browser = CourseBrowser()
        self._course_browser.play_requested.connect(self._open_recorded)
        self._course_browser.export_session_requested.connect(self._export_one_session)
        self._course_browser.delete_session_requested.connect(self._delete_one_session)
        self._course_browser.export_course_requested.connect(self._export_one_course)
        self._course_browser.delete_course_requested.connect(self._delete_one_course)
        self._library_label = QLabel("")
        self._library_label.setObjectName("muted")
        self._export_label = QLabel("")
        self._export_label.hide()
        self._export_cancel_button = QPushButton("Annuler l'export")
        self._export_cancel_button.hide()
        self._export_cancel_button.clicked.connect(self._export_cancel.set)
        self._prev_session_button = QPushButton("Session précédente")
        self._next_session_button = QPushButton("Session suivante")
        self._prev_session_button.clicked.connect(self._open_previous_session)
        self._next_session_button.clicked.connect(self._open_next_session)

        self._archive_slider = QSlider(Qt.Orientation.Horizontal)
        self._archive_slider.setEnabled(False)
        self._archive_slider.sliderPressed.connect(self._on_archive_slider_pressed)
        self._archive_slider.sliderReleased.connect(self._on_archive_slider_released)
        self._archive_time = QLabel("—")

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_prepare_page())
        self._stack.addWidget(self._build_course_page())
        self._stack.addWidget(self._build_archives_page())

        root = AppBackdrop(backdrop_path())
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.addWidget(self._logo)
        header_layout.addStretch(1)
        header_layout.addWidget(self._about_button)
        header_layout.addWidget(self._prepare_nav)
        header_layout.addWidget(self._course_nav)
        header_layout.addWidget(self._archives_nav)
        layout.addWidget(header)
        layout.addWidget(self._stack, stretch=1)
        layout.addWidget(self._hint)
        self.setCentralWidget(root)
        self.setStyleSheet(APP_STYLE)

        self._timer = QTimer(self)
        self._timer.setInterval(DISPLAY_INTERVAL_MS)
        self._timer.timeout.connect(self._refresh)
        self._replay_timer = QTimer(self)
        self._replay_timer.setInterval(DISPLAY_INTERVAL_MS)
        self._replay_timer.timeout.connect(self._on_replay_tick)
        self._archive_timer = QTimer(self)
        self._archive_timer.timeout.connect(self._on_archive_tick)
        self._camera_timer = QTimer(self)
        self._camera_timer.setInterval(200)
        self._camera_timer.timeout.connect(self._apply_pending_cameras)
        self._disk_timer = QTimer(self)
        self._disk_timer.setInterval(5000)
        self._disk_timer.timeout.connect(self._refresh_disk_space)
        self._disk_timer.timeout.connect(self._poll_export)
        self._disk_timer.start()
        self._apply_preferences()
        self._refresh_disk_space()
        self._refresh_readiness()
        self._set_tech("—", "—", "—", "—")
        self._detect_cameras()
        application = QApplication.instance()
        if application is not None:
            application.installEventFilter(self)
        self._update_transport_buttons()
        self._fit_to_screen()

    def _fit_to_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(1100, 720)
            return
        area = screen.availableGeometry()
        width = min(1100, max(640, area.width() - 32))
        height = min(840, max(480, area.height() - 80))
        self.setMinimumSize(min(720, width), min(480, height))
        self.resize(width, height)
        self.move(area.x() + max(0, (area.width() - width) // 2), area.y() + 8)

    def _build_prepare_page(self) -> QWidget:
        page = QWidget()
        course_body = QWidget()
        course_form = QVBoxLayout(course_body)
        course_form.setContentsMargins(0, 0, 0, 0)
        course_form.addWidget(QLabel("Nom de la course"))
        course_form.addWidget(self._course_name_edit)
        course_form.addWidget(QLabel("Lieu"))
        course_form.addWidget(self._place_edit)
        date = QLabel("Date : aujourd'hui, au moment du démarrage")
        date.setObjectName("muted")
        course_form.addWidget(date)

        camera_body = QWidget()
        camera_form = QVBoxLayout(camera_body)
        camera_form.setContentsMargins(0, 0, 0, 0)
        camera_form.addWidget(QLabel("Caméra"))
        camera_form.addWidget(self._camera_combo)
        camera_form.addWidget(QLabel("Résolution"))
        camera_form.addWidget(self._resolution_combo)
        camera_form.addWidget(QLabel("FPS demandé"))
        camera_form.addWidget(self._fps_combo)
        camera_actions = QHBoxLayout()
        camera_actions.addWidget(self._detect_button)
        camera_actions.addWidget(self._test_button)
        camera_actions.addStretch(1)
        camera_form.addLayout(camera_actions)
        camera_form.addWidget(self._camera_report)

        advanced = QWidget()
        advanced_form = QVBoxLayout(advanced)
        advanced_form.setContentsMargins(0, 0, 0, 0)
        advanced_form.addWidget(QLabel("Durée du buffer"))
        advanced_form.addWidget(self._buffer_combo)
        advanced_form.addWidget(QLabel("Qualité JPEG du buffer"))
        advanced_form.addWidget(self._jpeg_combo)
        advanced_form.addWidget(QLabel(f"Codec : {RECORDING_CODEC}"))
        advanced_form.addWidget(self._folder_label)
        advanced_form.addWidget(self._folder_button)

        content = QWidget()
        content.setObjectName("prepareForm")
        content.setAutoFillBackground(False)
        content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        content_layout = QVBoxLayout(content)
        content_layout.addWidget(self._accordion("Course", course_body))
        content_layout.addWidget(self._accordion("Caméra", camera_body))
        content_layout.addWidget(
            self._accordion("Paramètres", advanced, open_by_default=False)
        )
        content_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        viewport = scroll.viewport()
        viewport.setObjectName("scrollViewport")
        viewport.setAutoFillBackground(False)
        viewport.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(page)
        title = QLabel("Pré-course")
        title.setObjectName("screenTitle")
        layout.addWidget(title)
        layout.addWidget(scroll, stretch=1)
        status = QFrame()
        status.setObjectName("card")
        status_layout = QVBoxLayout(status)
        status_layout.setContentsMargins(12, 8, 12, 8)
        status_layout.addWidget(self._readiness)
        status_layout.addWidget(self._autonomy)
        layout.addWidget(status)
        layout.addWidget(self._start_button)
        layout.addWidget(self._finish_button)
        return page

    def _build_course_page(self) -> QWidget:
        page = QWidget()
        self._course_layout = QVBoxLayout(page)
        session_row = QHBoxLayout()
        session_row.addWidget(self._session_value)
        session_row.addWidget(self._rec_banner)
        session_row.addStretch(1)
        self._course_layout.addWidget(self._course_value)
        self._course_layout.addLayout(session_row)
        self._course_layout.addWidget(self._status)

        body = QHBoxLayout()
        body.setSpacing(12)
        video_host = QWidget()
        self._course_video_layout = QVBoxLayout(video_host)
        self._course_video_layout.setContentsMargins(0, 0, 0, 0)
        self._course_video_layout.addWidget(self._live, stretch=1)
        body.addWidget(video_host, stretch=5)

        side = QWidget()
        side.setObjectName("side")
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(6)
        side_layout.addWidget(self._replay_10)
        side_layout.addWidget(self._replay_20)
        side_layout.addWidget(self._replay_30)
        transport = QHBoxLayout()
        transport.addWidget(self._pause_button)
        transport.addWidget(self._return_live)
        side_layout.addLayout(transport)
        frames = QHBoxLayout()
        frames.addWidget(self._previous_button)
        frames.addWidget(self._next_button)
        side_layout.addLayout(frames)
        side_layout.addWidget(self._replay_value)
        self._keys_label.setWordWrap(True)
        side_layout.addWidget(self._keys_label)
        side_layout.addWidget(self._start_session_button)
        side_layout.addWidget(self._stop_button)
        side_layout.addWidget(self._finish_course_button)
        side_layout.addWidget(self._tech_toggle)
        tech_layout = QVBoxLayout(self._tech_panel)
        tech_layout.setContentsMargins(0, 0, 0, 0)
        tech_layout.addWidget(self._tech_label)
        tech_layout.addWidget(self._disk_label)
        tech_layout.addWidget(self._meta_line)
        side_layout.addWidget(self._tech_panel)
        side_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(side)
        body.addWidget(scroll, stretch=3)
        self._course_layout.addLayout(body, stretch=1)
        return page

    def _build_archives_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._library_label)
        export_row = QHBoxLayout()
        export_row.addWidget(self._export_label, stretch=1)
        export_row.addWidget(self._export_cancel_button)
        layout.addLayout(export_row)
        layout.addWidget(self._course_browser, stretch=1)
        self._player_page = QWidget()
        self._player_heading = QLabel("")
        self._player_heading.setObjectName("screenTitle")
        self._player_heading.setWordWrap(True)
        self._player_heading.setStyleSheet(
            "font-size: 18px; font-weight: 700; background: rgba(255, 255, 255, 180); "
            "border-radius: 6px; padding: 4px 8px;"
        )
        self._player_layout = QVBoxLayout(self._player_page)
        self._player_layout.setContentsMargins(0, 0, 0, 0)
        self._player_layout.addWidget(self._player_heading)
        body = QHBoxLayout()
        body.setSpacing(12)
        video_host = QWidget()
        self._player_video_layout = QVBoxLayout(video_host)
        self._player_video_layout.setContentsMargins(0, 0, 0, 0)
        body.addWidget(video_host, stretch=5)
        side = QWidget()
        side.setObjectName("side")
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(6)
        playback = QHBoxLayout()
        playback.addWidget(self._archive_play_button)
        playback.addWidget(self._archive_pause_button)
        playback.addWidget(self._archive_stop_button)
        side_layout.addLayout(playback)
        frames = QHBoxLayout()
        frames.addWidget(self._archive_previous_button)
        frames.addWidget(self._archive_next_button)
        side_layout.addLayout(frames)
        side_layout.addWidget(self._archive_slider)
        side_layout.addWidget(self._archive_time)
        goto = QHBoxLayout()
        goto.addWidget(self._goto_edit)
        goto.addWidget(self._goto_button)
        side_layout.addLayout(goto)
        side_layout.addWidget(self._prev_session_button)
        side_layout.addWidget(self._next_session_button)
        side_layout.addWidget(self._archive_info_button)
        side_layout.addWidget(self._archive_close_button)
        side_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(side)
        body.addWidget(scroll, stretch=3)
        self._player_layout.addLayout(body, stretch=1)
        self._player_page.hide()
        layout.addWidget(self._player_page, stretch=1)
        return page

    def _accordion(self, title: str, body: QWidget, *, open_by_default: bool = True) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        heading = title.upper()
        header = QPushButton(self._accordion_label(heading, open_by_default))
        header.setObjectName("accordion")
        header.setCheckable(True)
        header.setChecked(open_by_default)
        body.setVisible(open_by_default)

        def toggle(checked: bool) -> None:
            body.setVisible(checked)
            header.setText(self._accordion_label(heading, checked))

        header.toggled.connect(toggle)
        layout.addWidget(header)
        layout.addWidget(body)
        return frame

    def _accordion_label(self, heading: str, opened: bool) -> str:
        mark = "▼" if opened else "▶"
        return f"{mark}  {heading}"

    def _attach_live(self, layout: QVBoxLayout, index: int) -> None:
        if layout.indexOf(self._live) >= 0:
            return
        self._live.setParent(None)
        layout.insertWidget(index, self._live, stretch=1)

    def _show_prepare(self) -> None:
        if self._session_controls_live() or self._recorder is not None:
            self._course_nav.setChecked(True)
            return
        self._leave_archives()
        self._attach_live(self._course_video_layout, 0)
        self._stack.setCurrentIndex(0)
        self._prepare_nav.setChecked(True)
        self._refresh_start_label()
        self._refresh_readiness()
        if self._course is not None:
            self._hint.setText("La course continue. Démarrez une session, ou terminez la course.")

    def _show_course_page(self) -> None:
        if self._view in {"list", "archive"}:
            self._leave_archives()
        self._attach_live(self._course_video_layout, 0)
        self._stack.setCurrentIndex(1)
        self._course_nav.setChecked(True)

    def set_course_name(self, raw_name: str | None) -> None:
        self._course = start_course(raw_name)
        self._set_course_text(self._course.course_name)
        self._course_name_edit.setText(self._course.course_name)
        self._refresh_start_label()
        logger.info(
            "COURSE SET course=%s slug=%s",
            self._course.course_name,
            self._course.course_slug,
        )

    def _set_course_text(self, name: str) -> None:
        self._course_value.setText(f"Course : {name}")

    def _set_session_text(self, label: str) -> None:
        self._session_value.setText(f"Session : {label}")

    def _set_status(self, text: str, kind: str) -> None:
        colors = {
            "idle": "#4a4a4a",
            "opening": "#4a4a4a",
            "live": "#1d6b3a",
            "replay": "#c45500",
            "pause": "#8a3d00",
            "archive": "#1f4e79",
        }
        color = colors.get(kind, "#4a4a4a")
        self._status.setText(text)
        self._status.setStyleSheet(
            f"background-color: {color}; color: white; font-weight: 700; "
            "font-size: 16px; padding: 8px;"
        )

    def _set_tech(self, camera: str, resolution: str, fps: str, buffer: str) -> None:
        self._tech_label.setText(
            f"Infos techniques — Caméra {camera} · {resolution} · FPS {fps} · Buffer {buffer}"
        )

    def _set_meta(self, start: str, duration: str) -> None:
        if start == "—":
            self._meta_line.hide()
            self._meta_line.setText("")
            return
        self._meta_line.setText(f"Début : {start}    Durée : {duration}")
        self._meta_line.show()

    def _log_life(self, event: str, session_id: int | None = None, detail: str = "") -> None:
        course = "-" if self._course is None else self._course.course_name
        chosen = self._open_session_id if session_id is None else session_id
        sid = "-" if chosen is None else f"{chosen:03d}"
        if detail:
            logger.info("%s course=%s session_id=%s detail=%s", event, course, sid, detail)
        else:
            logger.info("%s course=%s session_id=%s", event, course, sid)

    def _refresh_disk_space(self) -> None:
        self._apply_pending_cameras()
        try:
            free = self._free_for_recordings()
        except OSError:
            logger.exception("Disk space check failed")
            self._disk_label.setText("Espace disponible : inconnu")
            self._autonomy.setText("Espace libre : inconnu")
        else:
            text, low = disk_space_message(free, DISK_FREE_WARNING_BYTES)
            self._disk_label.setText(text)
            self._autonomy.setText(
                autonomy_message(free) + "\nEstimation à partir d'environ 131 Mo/min."
            )
            if low:
                self._disk_label.setStyleSheet(
                    "color: #9d1c1c; font-size: 14px; font-weight: 700;"
                )
            else:
                self._disk_label.setStyleSheet("color: #666666; font-size: 12px;")
        self._refresh_readiness()
        self._refresh_library_space()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - signature Qt
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            if self._shortcut_applies() and self._handle_shortcut(event):
                return True
        return super().eventFilter(watched, event)

    def _shortcut_applies(self) -> bool:
        if QApplication.activeModalWidget() is not None:
            return False
        focus = QApplication.focusWidget()
        return not isinstance(focus, QLineEdit)

    def _handle_shortcut(self, event: QKeyEvent) -> bool:
        if event.modifiers() & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
        ):
            return False
        key = event.key()
        if event.isAutoRepeat() and key not in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            return key in (
                Qt.Key.Key_Space,
                Qt.Key.Key_Escape,
                Qt.Key.Key_1,
                Qt.Key.Key_2,
                Qt.Key.Key_3,
                Qt.Key.Key_F1,
                Qt.Key.Key_F2,
                Qt.Key.Key_F3,
            )
        live = self._session_controls_live()
        replay = self._player is not None
        archive = self._view == "archive" and self._archive_player.is_open
        if live and key in (Qt.Key.Key_1, Qt.Key.Key_F1):
            self._start_replay(10)
            return True
        if live and key in (Qt.Key.Key_2, Qt.Key.Key_F2):
            self._start_replay(20)
            return True
        if live and key in (Qt.Key.Key_3, Qt.Key.Key_F3):
            self._start_replay(30)
            return True
        if replay and key == Qt.Key.Key_Escape:
            self._return_to_live(automatic=False)
            return True
        if replay and key == Qt.Key.Key_Space:
            self._toggle_pause()
            return True
        if archive and key == Qt.Key.Key_Space:
            if self._archive_playing:
                self._pause_archive()
            else:
                self._play_archive()
            return True
        if replay and self._player is not None and self._player.paused:
            if key == Qt.Key.Key_Left:
                self._step_replay(-1)
                return True
            if key == Qt.Key.Key_Right:
                self._step_replay(1)
                return True
        if archive and not self._archive_playing:
            if key == Qt.Key.Key_Left:
                self._step_archive(-1)
                return True
            if key == Qt.Key.Key_Right:
                self._step_archive(1)
                return True
        return False

    def _session_controls_live(self) -> bool:
        return (
            self._worker is not None
            and self._worker.is_alive()
            and not self._stopping
            and not self._closing
        )

    def _start(self) -> None:
        if self._worker is not None:
            return
        if not self._prepare_course_start():
            return
        if self._view != "idle":
            self._leave_archives()
        self._begin_capture(record=True)

    def _prepare_course_start(self) -> bool:
        name = self._course_name_edit.text().strip()
        if not name and self._course is not None:
            name = self._course.course_name
        ready = self._current_readiness(name)
        self._show_readiness(ready)
        if not ready.allowed:
            self._hint.setText(ready.detail)
            return False
        if (
            self._course is not None
            and name
            and name != self._course.course_name
        ):
            answer = QMessageBox.question(
                self,
                "FINISH",
                "Créer une nouvelle course ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
        if name:
            self.set_course_name(name)
            return True
        return self._ensure_course()

    def _begin_capture(self, *, record: bool) -> None:
        self._stopping = False
        self._error_shown = False
        self._shown_index = -1
        self._open_session_id = None
        self._logged_camera_started = False
        self._preview_mode = not record
        self._record_when_ready = record
        self._active_fps = self._selected_fps()
        width, height = self._selected_resolution()
        self._start_button.setEnabled(False)
        self._stop_button.setEnabled(True)
        self._set_status("OUVERTURE…" if record else "TEST CAMÉRA", "opening")
        self._set_tech(f"index {self._selected_camera()}", "—", "—", "—")
        self._hint.setText(
            "Ouverture de la session… cela peut prendre quelques secondes."
            if record
            else "Test de la caméra, sans enregistrement."
        )
        if record:
            self._log_life("SESSION START REQUESTED")
        else:
            self._preview_until = time.monotonic() + 5
            self._stop_button.setText("Arrêter le test")
            logger.info("CAMERA TEST REQUESTED index=%s", self._selected_camera())
        self._worker = CameraCapture(
            self._selected_camera(),
            store_ring_buffer=record,
            width=width,
            height=height,
            fps=self._active_fps,
            buffer_seconds=self._selected_buffer(),
            jpeg_quality=self._selected_jpeg(),
        )
        self._worker.start()
        self._timer.start()
        self._show_course_page()
        self._update_transport_buttons()

    def _start_preview(self) -> None:
        if self._worker is not None:
            return
        if not self._camera_available():
            self._hint.setText("Aucune caméra détectée.")
            return
        self._begin_capture(record=False)

    def _selected_camera(self) -> int:
        value = self._camera_combo.currentData()
        return CAMERA_INDEX if value is None else int(value)

    def _selected_resolution(self) -> tuple[int, int]:
        value = self._resolution_combo.currentData()
        if value is None:
            return REQUESTED_WIDTH, REQUESTED_HEIGHT
        return int(value[0]), int(value[1])

    def _selected_fps(self) -> int:
        value = self._fps_combo.currentData()
        return REQUESTED_FPS if value is None else int(value)

    def _selected_buffer(self) -> int:
        value = self._buffer_combo.currentData()
        return MAX_BUFFER_SECONDS if value is None else int(value)

    def _selected_jpeg(self) -> int:
        value = self._jpeg_combo.currentData()
        return JPEG_QUALITY if value is None else int(value)

    def _fill_camera_combo(self, choices: list[CameraChoice]) -> None:
        self._camera_combo.blockSignals(True)
        self._camera_combo.clear()
        for choice in choices:
            self._camera_combo.addItem(choice.label, choice.index)
        preferred = self._camera_combo.findData(self._preferred_camera)
        self._camera_combo.setCurrentIndex(preferred if preferred >= 0 else 0)
        self._camera_combo.blockSignals(False)

    def _detect_cameras(self) -> None:
        if self._detecting or self._worker is not None:
            return
        self._detecting = True
        self._detect_button.setEnabled(False)
        self._camera_report.setText("Recherche des caméras…")
        self._camera_timer.start()
        threading.Thread(target=self._detect_worker, name="camera-detect", daemon=True).start()

    def _detect_worker(self) -> None:
        try:
            choices = detect_cameras()
        except Exception:
            logger.exception("Camera detection failed")
            choices = []
        self._pending_cameras = choices
        self._detecting = False

    def _apply_pending_cameras(self) -> None:
        pending = self._pending_cameras
        if pending is None:
            return
        self._pending_cameras = None
        self._camera_timer.stop()
        self._camera_choices = pending
        if pending:
            self._fill_camera_combo(pending)
            self._camera_report.setText(" · ".join(choice.label for choice in pending))
            self._persist_preferences()
        else:
            self._camera_combo.blockSignals(True)
            self._camera_combo.clear()
            self._camera_combo.addItem("Aucune caméra détectée", None)
            self._camera_combo.blockSignals(False)
            self._camera_report.setText("Aucune caméra détectée")
        self._detect_button.setEnabled(self._worker is None)

    def _camera_available(self) -> bool:
        return isinstance(self._camera_combo.currentData(), int)

    def _apply_preferences(self) -> None:
        self._loading_preferences = True
        preferences = load_preferences(preferences_path())
        self._preferred_camera = preferences.camera_index
        self._select_combo(self._resolution_combo, (preferences.width, preferences.height))
        self._select_combo(self._fps_combo, preferences.fps)
        self._select_combo(self._buffer_combo, preferences.buffer_seconds)
        self._select_combo(self._jpeg_combo, preferences.jpeg_quality)
        self._place_edit.setText(preferences.place)
        folder = default_recordings_dir()
        if preferences.recordings_dir:
            chosen = Path(preferences.recordings_dir)
            if chosen.is_dir():
                folder = chosen
            else:
                logger.warning("Recordings folder missing, using default path=%s", chosen)
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.exception("Recordings folder unavailable path=%s", folder)
        self._recordings_dir = folder
        self._set_folder_label(folder)
        self._loading_preferences = False

    def _select_combo(self, combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _persist_preferences(self) -> None:
        if self._loading_preferences:
            return
        width, height = self._selected_resolution()
        camera = self._camera_combo.currentData()
        if isinstance(camera, int):
            self._preferred_camera = camera
        try:
            save_preferences(
                preferences_path(),
                Preferences(
                    camera_index=self._preferred_camera,
                    width=width,
                    height=height,
                    fps=self._selected_fps(),
                    buffer_seconds=self._selected_buffer(),
                    jpeg_quality=self._selected_jpeg(),
                    recordings_dir=str(self._recordings_dir),
                    place=self._place_edit.text().strip(),
                ),
            )
        except OSError:
            logger.exception("Preferences could not be saved")

    def _current_readiness(self, name: str | None = None):
        if name is None:
            name = self._course_name_edit.text().strip()
            if not name and self._course is not None:
                name = self._course.course_name
        if self._detecting:
            return Readiness("À vérifier", "Recherche des caméras…", False)
        return course_readiness(
            name or "",
            self._recordings_dir,
            self._free_for_recordings(),
            DISK_FREE_WARNING_BYTES,
            camera_available=self._camera_available(),
        )

    def _show_readiness(self, ready) -> None:
        self._readiness.setText(f"{ready.headline}\n{ready.detail}")

    def _set_folder_label(self, folder: Path) -> None:
        shown = html.escape(str(folder))
        self._folder_label.setText(
            f'<a href="recordings" style="color:#0d6efd; text-decoration:underline;">{shown}</a>'
        )

    def _open_recordings_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._recordings_dir)))

    def _choose_recordings_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Dossier des enregistrements", str(self._recordings_dir))
        if not chosen:
            return
        folder = Path(chosen)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            probe = folder / ".finish-write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError:
            self._readiness.setText("Le dossier d'enregistrement n'est pas accessible.")
            return
        self._recordings_dir = folder
        self._set_folder_label(folder)
        self._persist_preferences()
        self._refresh_readiness()

    def _free_for_recordings(self) -> int:
        try:
            return free_bytes(self._recordings_dir)
        except OSError:
            return 0

    def _refresh_readiness(self) -> None:
        self._show_readiness(self._current_readiness())

    def _ensure_course(self) -> bool:
        if self._course is not None:
            return True
        name, accepted = QInputDialog.getText(self, "FINISH", "Nom de la course :")
        if not accepted:
            return False
        self.set_course_name(name)
        return True

    def _new_course(self) -> None:
        if self._recorder is not None or self._session_controls_live():
            return
        if self._course is not None:
            answer = QMessageBox.question(
                self,
                "FINISH",
                "Créer une nouvelle course ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        name, accepted = QInputDialog.getText(self, "FINISH", "Nom de la course :")
        if not accepted:
            return
        self.set_course_name(name)

    def _start_recording(self) -> None:
        if self._recorder is not None or self._course is None or self._worker is None:
            return
        if not self._worker.is_alive() or self._stopping or self._closing:
            return
        snapshot = self._worker.snapshot()
        if snapshot.width < 1 or snapshot.height < 1:
            self._hint.setText("La caméra n'a pas encore d'image.")
            return
        reserved = reserve_new_session(
            self._recordings_dir,
            self._course.course_name,
            self._course.course_slug,
            datetime.now(),
            minimum_id=self._course.next_session_floor(),
        )
        self._course.note_opened_session(reserved.session_id)
        try:
            recorder = SessionRecorder(
                reserved,
                course_name=self._course.course_name,
                course_slug=self._course.course_slug,
                width=snapshot.width,
                height=snapshot.height,
                file_fps=file_frame_rate(snapshot.measured_fps, snapshot.fps_ready, self._active_fps),
                camera_index=snapshot.camera_index,
                backend=snapshot.backend,
                pixel_format=snapshot.pixel_format,
                requested_fps=float(self._active_fps),
                measured_fps=snapshot.measured_fps if snapshot.fps_ready else 0.0,
            )
            recorder.start()
        except RecorderError:
            logger.exception("Recording open failed")
            self._log_life("RECORDER START FAILED")
            self._record_when_ready = False
            if not self._closing:
                QMessageBox.warning(self, "FINISH", "Impossible d'ouvrir le fichier vidéo.")
            return
        self._record_when_ready = False
        self._recorder = recorder
        self._open_session_id = reserved.session_id
        self._worker.set_recording_offer(recorder.offer)
        self._set_session_text(reserved.session_id_label)
        self._rec_banner.setText("● REC — 00:00:00")
        self._rec_banner.show()
        self._log_life("RECORDER STARTED", reserved.session_id)
        self._log_life("SESSION RECORDING", reserved.session_id)
        if self._player is None:
            self._set_status("LIVE — ENREGISTREMENT", "live")
            self._hint.setText("Session en cours.")
        else:
            self._hint.setText("Replay. L'enregistrement continue.")
        self._update_transport_buttons()

    def _stop_recording(self) -> None:
        self._finalize_recording(announce=True, reason="stop-recording")

    def _finalize_recording(self, *, announce: bool, reason: str) -> None:
        recorder = self._recorder
        if recorder is None:
            return
        logger.info("Recording finalize reason=%s", reason)
        session_id = self._open_session_id
        worker = self._worker
        if worker is not None:
            worker.set_recording_offer(None)
        self._hint.setText("Finalisation de l'enregistrement…")
        self._log_life("RECORDER STOPPING", session_id)
        metadata = recorder.stop(RECORDING_STOP_TIMEOUT_SECONDS)
        self._log_life("RECORDER CLOSED", session_id)
        self._recorder = None
        self._set_session_text("—")
        self._rec_banner.hide()
        if metadata is None or recorder.state == "error":
            logger.error("Recording finished without metadata")
            if announce and not self._closing:
                QMessageBox.warning(self, "FINISH", "L'enregistrement n'a pas pu être finalisé.")
        elif self._player is None and not self._stopping and not self._closing:
            self._hint.setText("Session en cours.")
        self._update_transport_buttons()

    def _confirm_stop(self) -> None:
        if self._worker is None:
            return
        if self._preview_mode:
            self._worker.stop()
            return
        label = "—" if self._open_session_id is None else f"{self._open_session_id:03d}"
        if label == "—":
            question = "Arrêter la session ?"
        else:
            question = f"Arrêter l'enregistrement de la session {label} ?"
        answer = QMessageBox.question(
            self,
            "FINISH",
            question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._request_stop()

    def _request_stop(self) -> None:
        worker = self._worker
        if worker is None:
            return
        self._log_life("STOP REQUESTED")
        self._stopping = True
        self._record_when_ready = False
        self._stop_button.setEnabled(False)
        self._end_replay_ui()
        self._finalize_recording(announce=True, reason="stop-camera")
        worker.stop()
        self._hint.setText("Arrêt de la caméra…")
        self._update_transport_buttons()

    def _refresh(self) -> None:
        worker = self._worker
        if worker is None or self._closing:
            return
        if not worker.is_alive():
            self._handle_worker_exit(worker)
            return
        if self._stopping:
            return

        snapshot = worker.snapshot()
        if snapshot.state != "running":
            return
        if self._preview_mode and time.monotonic() >= self._preview_until:
            worker.stop()
            return
        self._show_capture_status(snapshot)
        if self._record_when_ready and self._recorder is None and snapshot.width > 0:
            self._start_recording()
        if self._player is None:
            self._show_live_frame(snapshot)

    def _show_capture_status(self, snapshot: CaptureSnapshot) -> None:
        if not self._logged_camera_started:
            self._logged_camera_started = True
            self._log_life("CAMERA STARTED")
        if self._player is None:
            if self._preview_mode:
                self._set_status("TEST CAMÉRA", "live")
                rate = f"{snapshot.measured_fps:.0f} fps" if snapshot.fps_ready else "mesure…"
                self._camera_report.setText(
                    f"Caméra détectée\n{snapshot.backend}\n{snapshot.pixel_format}\n"
                    f"{snapshot.width}×{snapshot.height}\n{rate}"
                )
            elif self._recorder is not None:
                self._set_status("LIVE — ENREGISTREMENT", "live")
            elif self._record_when_ready:
                self._set_status("OUVERTURE…", "opening")
            else:
                self._set_status("LIVE", "live")
        backend = f" ({snapshot.backend})" if snapshot.backend else ""
        camera = f"index {snapshot.camera_index}{backend}"
        resolution = (
            f"{snapshot.width} x {snapshot.height}"
            if snapshot.width and snapshot.height
            else "—"
        )
        fps = f"{snapshot.measured_fps:.1f}" if snapshot.fps_ready else "mesure…"
        worker = self._worker
        buffer = "—"
        if worker is not None:
            buffer = f"{worker.buffer_stats().duration_seconds:.1f} s"
        self._set_tech(camera, resolution, fps, buffer)
        recorder = self._recorder
        if recorder is not None:
            if snapshot.fps_ready:
                recorder.note_measured_fps(snapshot.measured_fps)
            self._rec_banner.setText(f"● REC — {_format_hms(recorder.elapsed_seconds)}")
            self._rec_banner.show()
        if self._player is None and self._recorder is not None:
            self._hint.setText("Session en cours.")
        self._update_transport_buttons()

    def _show_live_frame(self, snapshot: CaptureSnapshot) -> None:
        if snapshot.frame is None or snapshot.frame_index == self._shown_index:
            return
        self._shown_index = snapshot.frame_index
        self._live.set_frame_bgr(snapshot.frame)

    def _start_replay(self, seconds: float) -> None:
        worker = self._worker
        if worker is None or not worker.is_alive() or self._stopping:
            return
        frames = worker.snapshot_last_seconds(seconds)
        replay_logger.info("Replay requested duration=%ss", int(seconds))
        replay_logger.info("Replay snapshot frames=%s", len(frames))
        if not frames:
            self._hint.setText("Le buffer ne contient pas encore d'image.")
            return
        self._player = ReplayPlayer(frames, requested_seconds=seconds)
        self._player.start(time.monotonic())
        self._replay_shown_index = -1
        self._set_status(self._player.mode_label(), "replay")
        if self._recorder is not None:
            self._hint.setText("Replay. L'enregistrement continue.")
        else:
            self._hint.setText("Replay. La capture continue.")
        self._paint_replay_view(self._player.advance(time.monotonic()))
        self._replay_timer.start()
        self._update_transport_buttons()

    def _on_replay_tick(self) -> None:
        player = self._player
        if player is None or self._closing:
            return
        view = player.advance(time.monotonic())
        if view.finished:
            replay_logger.info("Replay finished")
            self._return_to_live(automatic=True)
            return
        self._paint_replay_view(view)

    def _paint_replay_view(self, view) -> None:
        player = self._player
        if player is None:
            return
        if player.paused:
            self._set_status("REPLAY EN PAUSE", "pause")
        else:
            self._set_status(player.mode_label(), "replay")
        self._replay_value.setText(player.progress_label(view.elapsed_seconds))
        if view.jpeg_data is None or view.index == self._replay_shown_index:
            return
        frame, elapsed_ms = decode_jpeg(view.jpeg_data)
        self._decode_count += 1
        self._decode_total_ms += elapsed_ms
        if frame is None:
            replay_logger.error("JPEG decode failed")
            return
        self._replay_shown_index = view.index
        self._live.set_frame_bgr(frame)

    def _toggle_pause(self) -> None:
        player = self._player
        if player is None:
            return
        if player.paused:
            player.resume(time.monotonic())
        else:
            player.pause()
        self._replay_shown_index = -1
        self._paint_replay_view(player.advance(time.monotonic()))
        self._update_transport_buttons()

    def _step_replay(self, delta: int) -> None:
        player = self._player
        if player is None or not player.paused:
            return
        player.step(delta)
        self._replay_shown_index = -1
        self._paint_replay_view(player.advance(time.monotonic()))

    def _return_to_live(self, automatic: bool) -> None:
        if self._player is None:
            return
        started = time.perf_counter()
        self._end_replay_ui()
        worker = self._worker
        if worker is not None and worker.is_alive() and not self._stopping:
            snapshot = worker.snapshot()
            self._shown_index = -1
            self._show_live_frame(snapshot)
            self._show_capture_status(snapshot)
        self._last_return_live_ms = (time.perf_counter() - started) * 1000.0
        replay_logger.info("Returned to LIVE")
        if not automatic:
            replay_logger.info("Return LIVE delay_ms=%.1f", self._last_return_live_ms)

    def _end_replay_ui(self) -> None:
        self._replay_timer.stop()
        self._player = None
        self._replay_shown_index = -1
        self._replay_value.setText("")
        self._pause_button.setText("Pause")
        if self._worker is not None and not self._stopping and not self._closing:
            if self._recorder is not None:
                self._set_status("LIVE — ENREGISTREMENT", "live")
            else:
                self._set_status("LIVE", "live")
        self._update_transport_buttons()

    def _update_transport_buttons(self) -> None:
        live = (
            self._worker is not None
            and self._worker.is_alive()
            and not self._stopping
            and not self._closing
        )
        playing = self._player is not None
        paused = playing and self._player is not None and self._player.paused
        for button in (self._replay_10, self._replay_20, self._replay_30):
            button.setEnabled(live and not self._preview_mode)
        self._return_live.setEnabled(playing)
        self._pause_button.setEnabled(playing)
        self._pause_button.setText("Lecture" if paused else "Pause")
        self._previous_button.setEnabled(paused)
        self._next_button.setEnabled(paused)
        recording = self._recorder is not None
        watching = self._view == "archive"
        browsing = self._view == "list"
        self._new_course_button.setEnabled(not recording and not live and not self._closing)
        self._archives_button.setEnabled(not live and not self._closing)
        self._archives_nav.setEnabled(not self._closing)
        self._prepare_nav.setEnabled(not live and not self._closing)
        self._detect_button.setEnabled(not live and not self._detecting and not self._closing)
        self._test_button.setEnabled(not live and not self._closing and self._camera_available())
        self._start_button.setEnabled(not live and not watching and not browsing and not self._closing)
        self._start_session_button.setEnabled(not live and not self._closing and self._course is not None)
        self._refresh_start_label()
        self._finish_button.setEnabled(not live and not self._closing)
        self._finish_course_button.setEnabled(not live and not self._closing)
        self._stop_button.setText("Arrêter le test" if self._preview_mode and live else "Arrêter session")
        self._open_archive_button.setEnabled(browsing)
        stepped = watching and not self._archive_playing
        self._archive_play_button.setEnabled(watching and not self._archive_playing)
        self._archive_pause_button.setEnabled(watching and self._archive_playing)
        self._archive_stop_button.setEnabled(watching)
        self._archive_previous_button.setEnabled(stepped)
        self._archive_next_button.setEnabled(stepped)
        self._archive_close_button.setEnabled(watching)
        self._archive_info_button.setEnabled(watching)
        self._goto_edit.setEnabled(watching)
        self._goto_button.setEnabled(watching)
        self._archive_slider.setEnabled(watching)
        self._back_button.setEnabled(browsing)

    def _handle_worker_exit(self, worker: CameraCapture) -> None:
        self._end_replay_ui()
        snapshot = worker.snapshot()
        message = snapshot.error if snapshot.state == "error" else None
        if message:
            self._log_life("CAMERA UNAVAILABLE", detail=message)
            self._record_when_ready = False
        self._finalize_recording(announce=not self._closing, reason="camera-ended")
        self._detach_worker(worker)
        if message and not self._error_shown and not self._closing:
            self._error_shown = True
            self._hint.setText("Caméra indisponible. Les archives restent utilisables.")
            QMessageBox.warning(self, "FINISH", message)

    def _detach_worker(self, worker: CameraCapture) -> None:
        self._timer.stop()
        self._worker = None
        self._stopping = False
        self._shown_index = -1
        worker.join(timeout=CAMERA_STOP_TIMEOUT_SECONDS)
        self._log_life("CAMERA STOPPED")
        if not self._preview_mode:
            self._log_life("SESSION CLOSED")
        self._preview_mode = False
        self._open_session_id = None
        self._logged_camera_started = False
        self._live.clear_frame()
        self._show_idle()

    def _refresh_start_label(self) -> None:
        if self._course is None:
            self._start_button.setText("Démarrer la course")
            return
        self._start_button.setText("Démarrer une session")
        self._start_session_button.setText("Démarrer une session")

    def _show_idle(self) -> None:
        self._set_status("EN ATTENTE", "idle")
        self._set_tech("—", "—", "—", "—")
        self._set_meta("—", "—")
        self._set_session_text("—")
        self._replay_value.setText("")
        self._rec_banner.hide()
        self._start_button.setEnabled(True)
        self._stop_button.setEnabled(False)
        self._attach_live(self._course_video_layout, 0)
        self._refresh_start_label()
        if self._course is not None:
            self._hint.setText("Session arrêtée. Démarrez la suivante, ou terminez la course.")
            self._stack.setCurrentIndex(1)
            self._course_nav.setChecked(True)
        else:
            self._hint.setText("Renseignez la course, puis démarrez.")
            self._stack.setCurrentIndex(0)
            self._prepare_nav.setChecked(True)
        self._refresh_readiness()
        self._update_transport_buttons()

    def _on_archives_clicked(self) -> None:
        live = (
            self._worker is not None
            and self._worker.is_alive()
            and not self._stopping
        )
        if live:
            QMessageBox.information(
                self,
                "FINISH",
                "Arrêtez la session avant d'ouvrir les archives.\n"
                "La capture en cours ne sera pas interrompue.",
            )
            self._course_nav.setChecked(True)
            return
        self._show_archive_list()

    def _show_archive_list(self) -> None:
        self._pause_archive()
        self._archive_player.close()
        self._archive_session = None
        self._archive_course = None
        self._archive_playing = False
        self._view = "list"
        self._attach_live(self._course_video_layout, 0)
        self._player_page.hide()
        self._course_browser.show()
        self._library_label.show()
        sessions = scan_recordings(self._recordings_dir)
        self._course_browser.show_courses(build_courses(sessions))
        self._refresh_library_space()
        self._stack.setCurrentIndex(2)
        self._archives_nav.setChecked(True)
        self._set_status("ARCHIVES", "archive")
        self._set_session_text("—")
        self._set_meta("—", "—")
        self._replay_value.setText("")
        self._hint.setText("Choisissez une course, puis une session.")
        self._update_transport_buttons()

    def _refresh_library_space(self) -> None:
        try:
            used = library_size(self._recordings_dir)
            free = free_bytes(self._recordings_dir)
        except OSError:
            self._library_label.setText("Espace des archives indisponible.")
            return
        self._library_label.setText(
            f"Espace utilisé par Finish : {format_byte_size(used)}    "
            f"Espace libre : {format_byte_size(free)}"
        )

    def _leave_archives(self) -> None:
        self._pause_archive()
        self._archive_player.close()
        self._archive_session = None
        self._archive_course = None
        self._archive_playing = False
        self._view = "idle"
        self._player_page.hide()
        self._course_browser.show_list()
        self._attach_live(self._course_video_layout, 0)
        self._live.show()
        self._live.clear_frame()
        if self._worker is None and self._stack.currentIndex() != 0:
            self._show_idle()

    def _open_selected_archive(self) -> None:
        session = self._course_browser.selected_session()
        if session is None:
            self._hint.setText("Choisissez une session.")
            return
        self._open_recorded(session)

    def _open_recorded(self, session: RecordedSession) -> None:
        if not self._archive_player.open(session.video_path, session.file_fps):
            QMessageBox.warning(self, "FINISH", "Cette vidéo ne peut pas être lue.")
            return
        self._archive_session = session
        self._archive_course = self._course_for(session)
        self._archive_playing = False
        self._view = "archive"
        self._course_browser.hide()
        self._player_page.show()
        self._library_label.hide()
        self._attach_live(self._player_video_layout, 0)
        self._live.show()
        self._stack.setCurrentIndex(2)
        self._archives_nav.setChecked(True)
        self._archive_slider.setRange(0, max(0, self._archive_player.frame_count - 1))
        self._set_status("ARCHIVE", "archive")
        self._set_course_text(session.course_name)
        position = f"{session.session_id:03d}"
        if self._archive_course is not None:
            position = f"{session.session_id:03d} / {self._archive_course.session_count:03d}"
        self._set_session_text(position)
        self._player_heading.setText(
            f"{session.course_name}\nSession {position}\n"
            f"{session.start_time.strftime('%d/%m/%Y %H:%M:%S')}  ·  "
            f"{format_duration_minutes(session.duration_seconds)}"
        )
        has_previous = self._archive_course is not None and self._archive_course.previous_session(session) is not None
        has_next = self._archive_course is not None and self._archive_course.next_session(session) is not None
        self._prev_session_button.setEnabled(has_previous)
        self._next_session_button.setEnabled(has_next)
        self._set_meta(
            session.start_time.strftime("%d/%m/%Y %H:%M:%S"),
            format_duration_minutes(session.duration_seconds),
        )
        self._set_tech(
            "non utilisée",
            f"{session.width} x {session.height}",
            f"{session.file_fps:.2f} fichier",
            "—",
        )
        self._replay_value.setText("")
        self._goto_edit.clear()
        self._paint_archive_frame()
        self._hint.setText("Lecture d'archive. La caméra n'est pas utilisée.")
        self._update_transport_buttons()

    def _course_for(self, session: RecordedSession) -> CourseArchive | None:
        current = self._course_browser.current_course()
        if current is not None and current.course_name == session.course_name:
            return current
        courses = build_courses(scan_recordings(self._recordings_dir))
        return next((course for course in courses if course.course_name == session.course_name), None)

    def _open_previous_session(self) -> None:
        if self._archive_course is None or self._archive_session is None:
            return
        session = self._archive_course.previous_session(self._archive_session)
        if session is not None:
            self._open_recorded(session)

    def _open_next_session(self) -> None:
        if self._archive_course is None or self._archive_session is None:
            return
        session = self._archive_course.next_session(self._archive_session)
        if session is not None:
            self._open_recorded(session)

    def _export_one_session(self, session: RecordedSession) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Exporter la session")
        if not folder:
            return
        include_json = (
            QMessageBox.question(
                self,
                "FINISH",
                "Copier aussi le JSON ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            == QMessageBox.StandardButton.Yes
        )
        self._start_export(
            lambda cancel, progress: export_session(
                session.video_path,
                session.metadata_path,
                Path(folder),
                include_json=include_json,
                cancel=cancel,
                progress=progress,
            ),
            [session.video_path, session.metadata_path] if include_json else [session.video_path],
        )

    def _export_one_course(self, course: CourseArchive) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Exporter la course")
        if not folder:
            return
        sources = [path for session in course.sessions for path in (session.video_path, session.metadata_path)]
        self._start_export(
            lambda cancel, progress: export_course(course, Path(folder), cancel=cancel, progress=progress),
            sources,
        )

    def _start_export(self, operation, sources: list[Path]) -> None:
        if self._export_thread is not None and self._export_thread.is_alive():
            self._hint.setText("Un export est déjà en cours.")
            return
        self._export_sources = sources
        self._export_cancel.clear()
        self._export_result = None
        self._export_progress = (0, 1, 0, 1)
        self._export_label.show()
        self._export_cancel_button.show()
        self._export_label.setText("Export en cours")

        def worker() -> None:
            def progress(files_done: int, files_total: int, bytes_done: int, bytes_total: int) -> None:
                with self._export_lock:
                    self._export_progress = (files_done, files_total, bytes_done, bytes_total)

            try:
                result = operation(self._export_cancel, progress)
            except Exception:
                logger.exception("Export failed")
                result = ExportResult("io_error", "L'export a échoué.")
            with self._export_lock:
                self._export_result = result

        self._export_thread = threading.Thread(target=worker, name="archive-export", daemon=False)
        self._export_thread.start()

    def _poll_export(self) -> None:
        thread = self._export_thread
        if thread is None:
            return
        with self._export_lock:
            files_done, files_total, bytes_done, bytes_total = self._export_progress
            result = self._export_result
        self._export_label.setText(
            f"Export en cours\n{files_done} / {files_total} fichiers\n"
            f"{format_byte_size(bytes_done)} / {format_byte_size(bytes_total)}"
        )
        if thread.is_alive():
            return
        self._export_thread = None
        self._export_cancel_button.hide()
        if result is None:
            return
        self._export_label.setText(result.message)
        if not may_remove_sources(result):
            return
        answer = QMessageBox.question(
            self,
            "FINISH",
            "L'export est terminé.\nVoulez-vous supprimer la copie locale de cette course ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self._hint.setText("Export terminé. Les fichiers locaux sont conservés.")
            return
        freed = delete_local_files(self._export_sources)
        self._hint.setText(f"Copie locale supprimée. Espace libéré : {format_byte_size(freed)}.")
        self._show_archive_list()

    def _delete_one_session(self, session: RecordedSession) -> None:
        size = session.video_path.stat().st_size if session.video_path.is_file() else 0
        answer = QMessageBox.question(
            self,
            "FINISH",
            f"Supprimer définitivement la session {session.session_id:03d} ?\n"
            f"Taille libérée : {format_byte_size(size)}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        delete_local_files([session.video_path, session.metadata_path])
        self._show_archive_list()

    def _delete_one_course(self, course: CourseArchive) -> None:
        answer = QMessageBox.question(
            self,
            "FINISH",
            f"Supprimer définitivement {course.course_name} et ses {course.session_count} sessions ?\n"
            f"Taille libérée : {format_byte_size(course.size_total())}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        paths = [path for session in course.sessions for path in (session.video_path, session.metadata_path)]
        delete_local_files(paths)
        self._show_archive_list()

    def _play_archive(self) -> None:
        player = self._archive_player
        if not player.is_open:
            return
        if player.frame_index >= player.frame_count - 1:
            player.seek(0)
            self._paint_archive_frame()
        fps = player.file_fps if player.file_fps > 0 else 30.0
        self._archive_anchor_index = player.frame_index
        self._archive_anchor_mono = time.monotonic()
        self._archive_timer.setInterval(max(15, int(round(1000 / fps))))
        self._archive_playing = True
        self._archive_timer.start()
        self._update_transport_buttons()

    def _pause_archive(self) -> None:
        self._archive_playing = False
        self._archive_timer.stop()
        self._update_transport_buttons()

    def _stop_archive(self) -> None:
        self._pause_archive()
        if self._archive_player.is_open:
            self._archive_player.seek(0)
            self._paint_archive_frame()

    def _step_archive(self, delta: int) -> None:
        if self._view != "archive" or self._archive_playing:
            return
        if self._archive_player.step(delta):
            self._paint_archive_frame()

    def _on_archive_tick(self) -> None:
        player = self._archive_player
        if not player.is_open or not self._archive_playing or self._archive_slider_dragging:
            return
        elapsed = time.monotonic() - self._archive_anchor_mono
        fps = player.file_fps if player.file_fps > 0 else 30.0
        target = self._archive_anchor_index + int(elapsed * fps)
        if target >= player.frame_count - 1:
            player.seek(player.frame_count - 1)
            self._paint_archive_frame()
            self._pause_archive()
            return
        if target != player.frame_index and player.seek(target):
            self._paint_archive_frame()

    def _paint_archive_frame(self) -> None:
        player = self._archive_player
        if player.frame is not None:
            self._live.set_frame_bgr(player.frame)
        total = player.frame_count / player.file_fps if player.file_fps > 0 else 0.0
        current = seconds_for_frame(max(0, player.frame_index), player.file_fps)
        self._archive_time.setText(f"{_format_hms(current)} / {_format_hms(total)}")
        if not self._archive_slider_dragging:
            self._archive_slider.blockSignals(True)
            self._archive_slider.setValue(max(0, player.frame_index))
            self._archive_slider.blockSignals(False)

    def _on_archive_slider_pressed(self) -> None:
        self._archive_slider_dragging = True

    def _on_archive_slider_released(self) -> None:
        self._archive_slider_dragging = False
        if not self._archive_player.is_open:
            return
        self._archive_player.seek(self._archive_slider.value())
        if self._archive_playing:
            self._archive_anchor_index = max(0, self._archive_player.frame_index)
            self._archive_anchor_mono = time.monotonic()
        self._paint_archive_frame()

    def _go_to_archive_time(self) -> None:
        session = self._archive_session
        player = self._archive_player
        if session is None or not player.is_open or self._view != "archive":
            return
        located = locate_frame_for_clock_text(
            session.start_time,
            self._goto_edit.text(),
            player.file_fps,
            player.frame_count,
        )
        if located is None:
            self._hint.setText("Heure non reconnue. Exemple : 13:25:21")
            return
        index, place = located
        self._pause_archive()
        player.seek(index)
        self._paint_archive_frame()
        if place == "before":
            self._hint.setText("Avant le début de la session : première image.")
        elif place == "after":
            self._hint.setText("Après la fin de la session : dernière image.")
        else:
            self._hint.setText("Repérage par l'heure. Ajustez image par image si besoin.")

    def _show_archive_info(self) -> None:
        session = self._archive_session
        if session is None:
            return
        QMessageBox.information(
            self,
            "FINISH",
            "\n".join(
                [
                    f"Résolution : {session.width} x {session.height}",
                    f"FPS mesuré : {session.measured_fps:.1f}",
                    f"FPS fichier : {session.file_fps:.2f}",
                    f"Codec : {session.codec}",
                    f"Images écrites : {session.frames_written}",
                    f"Images perdues : {session.recording_dropped_frames}",
                    f"Caméra : index {session.camera_index} ({session.backend}, {session.pixel_format})",
                ]
            ),
        )

    def _finish_course(self) -> None:
        if self._session_controls_live() or self._recorder is not None:
            QMessageBox.information(
                self,
                "FINISH",
                "Arrêtez la session avant de terminer la course.\n"
                "La capture en cours ne sera pas interrompue.",
            )
            return
        name = self._course_name_edit.text().strip()
        if not name and self._course is not None:
            name = self._course.course_name
        if not name:
            QMessageBox.information(self, "FINISH", "Indiquez le nom de la course.")
            return
        self._show_archive_list()
        courses = build_courses(scan_recordings(self._recordings_dir))
        course = next((item for item in courses if item.course_name == name), None)
        if course is not None:
            self._course_browser.open_course(course)
        text = format_course_summary(course) if course is not None else format_summary(name, 0, 0, 0)
        box = QMessageBox(self)
        box.setWindowTitle("Fin de course")
        box.setText(text)
        see = box.addButton("Voir les sessions", QMessageBox.ButtonRole.AcceptRole)
        export = box.addButton("Exporter la course", QMessageBox.ButtonRole.ActionRole)
        home = box.addButton("Retour accueil", QMessageBox.ButtonRole.RejectRole)
        export.setEnabled(course is not None)
        box.exec()
        chosen = box.clickedButton()
        if chosen is export and course is not None:
            self._export_one_course(course)
        elif chosen is home:
            self._show_prepare()
        elif chosen is see and course is None:
            self._hint.setText("Cette course n'a pas encore de session.")

    def _show_about(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("À propos de Finish")
        pixmap = logo_pixmap()
        if pixmap is not None:
            box.setIconPixmap(pixmap.scaledToHeight(72, Qt.TransformationMode.SmoothTransformation))
        box.setText(f"Finish\n{VERSION}")
        box.setInformativeText(ABOUT_TEXT)
        logs = box.addButton("Ouvrir le dossier des logs", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Fermer", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is logs:
            folder = logs_dir()
            folder.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - signature Qt
        self._closing = True
        self._persist_preferences()
        if self._worker is not None or self._recorder is not None:
            self._log_life("STOP REQUESTED", detail="window-close")
        application = QApplication.instance()
        if application is not None:
            application.removeEventFilter(self)
        self._timer.stop()
        self._replay_timer.stop()
        self._archive_timer.stop()
        self._export_cancel.set()
        if self._export_thread is not None:
            self._export_thread.join(timeout=2)
        self._archive_player.close()
        self._finalize_recording(announce=False, reason="window-close")
        worker = self._worker
        if worker is not None:
            worker.stop()
            worker.join(timeout=CAMERA_STOP_TIMEOUT_SECONDS)
            if worker.is_alive():
                logger.error("Camera thread still alive on application exit")
            self._log_life("CAMERA STOPPED")
            self._log_life("SESSION CLOSED")
            self._worker = None
        event.accept()
