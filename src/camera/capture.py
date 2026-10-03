"""Worker de capture. Il ne connaît pas l'interface graphique."""

from __future__ import annotations

import logging
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import cv2
import numpy as np

from camera.fourcc import fourcc_to_string
from camera.fps_meter import FpsMeter
from camera.overlay import draw_timestamp
from camera.timestamp import format_timestamp
from config import (
    CAMERA_INDEX,
    CAPTURE_BUFFER_SIZE,
    FPS_LOG_INTERVAL_SECONDS,
    FPS_WINDOW_SECONDS,
    JPEG_QUALITY,
    MAX_BUFFER_SECONDS,
    PREFER_DIRECTSHOW,
    REQUESTED_FPS,
    REQUESTED_HEIGHT,
    REQUESTED_WIDTH,
)
from video.jpeg_encode import encode_jpeg
from video.jpeg_meter import JpegEncodeMeter, JpegEncodeStats
from video.ring_buffer import BufferStats, BufferedFrame, RingBuffer

logger = logging.getLogger("finish.camera")


@dataclass(frozen=True)
class CaptureSnapshot:
    """Vue cohérente de la dernière image. L'image ne doit plus être modifiée."""

    state: str
    error: str | None
    frame: np.ndarray | None
    frame_index: int
    width: int
    height: int
    measured_fps: float
    fps_ready: bool
    camera_index: int
    backend: str
    wall_time: datetime | None
    monotonic_time: float | None
    pixel_format: str = ""


class CameraCapture(threading.Thread):
    """Ouvre la webcam et publie la dernière image horodatée.

    L'interface appelle snapshot() depuis son timer. Elle ne bloque pas ce thread.
    """

    def __init__(
        self,
        camera_index: int | None = None,
        *,
        store_ring_buffer: bool = True,
        width: int | None = None,
        height: int | None = None,
        fps: int | None = None,
        buffer_seconds: int | None = None,
        jpeg_quality: int | None = None,
    ) -> None:
        super().__init__(name="camera-capture", daemon=False)
        self._index = CAMERA_INDEX if camera_index is None else camera_index
        self._store_ring_buffer = store_ring_buffer
        self._requested_width = REQUESTED_WIDTH if width is None else width
        self._requested_height = REQUESTED_HEIGHT if height is None else height
        self._requested_fps = REQUESTED_FPS if fps is None else fps
        self._jpeg_quality = JPEG_QUALITY if jpeg_quality is None else jpeg_quality
        self._buffer_seconds = MAX_BUFFER_SECONDS if buffer_seconds is None else buffer_seconds
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._fps = FpsMeter(FPS_WINDOW_SECONDS)
        self._buffer = RingBuffer(self._buffer_seconds)
        self._jpeg_meter = JpegEncodeMeter()
        self._jpeg_failure_logged = False
        self._state = "starting"
        self._error: str | None = None
        self._frame: np.ndarray | None = None
        self._frame_index = 0
        self._width = 0
        self._height = 0
        self._measured_fps = 0.0
        self._fps_ready = False
        self._backend = ""
        self._pixel_format = ""
        self._recording_offer: Callable[[np.ndarray], None] | None = None
        self._recorder_lock = threading.Lock()
        self._recording_fault_logged = False
        self._wall_time: datetime | None = None
        self._monotonic_time: float | None = None
        self._logged_resolution = False
        self._last_fps_log_mono: float | None = None

    def stop(self) -> None:
        self._stop.set()

    def set_recording_offer(self, offer: Callable[[np.ndarray], None] | None) -> None:
        """Dépose chaque image BGR déjà horodatée. L'appel ne doit pas bloquer."""
        with self._recorder_lock:
            self._recording_offer = offer
            self._recording_fault_logged = False

    def buffer_stats(self) -> BufferStats:
        return self._buffer.stats()

    def jpeg_stats(self) -> JpegEncodeStats:
        return self._jpeg_meter.snapshot()

    def snapshot_last_seconds(self, seconds: float) -> list[BufferedFrame]:
        return self._buffer.snapshot_last_seconds(seconds)

    def snapshot(self) -> CaptureSnapshot:
        with self._lock:
            return CaptureSnapshot(
                state=self._state,
                error=self._error,
                frame=self._frame,
                frame_index=self._frame_index,
                width=self._width,
                height=self._height,
                measured_fps=self._measured_fps,
                fps_ready=self._fps_ready,
                camera_index=self._index,
                backend=self._backend,
                wall_time=self._wall_time,
                monotonic_time=self._monotonic_time,
                pixel_format=self._pixel_format,
            )

    def run(self) -> None:
        try:
            self._capture_loop()
        except Exception:
            logger.exception("Camera worker failed")
            self._set_error("Erreur inattendue pendant la capture.")
        finally:
            with self._lock:
                if self._state == "running" or self._state == "starting":
                    self._state = "stopped"
                self._frame = None
            self._buffer.clear()
            logger.info("Camera worker finished")

    def _capture_loop(self) -> None:
        if self._stop.is_set():
            return

        capture = self._open_camera()
        if capture is None:
            return
        if self._stop.is_set():
            capture.release()
            logger.info("Camera released")
            logger.info("CAMERA STOPPED index=%s", self._index)
            return

        self._configure_camera(capture)
        if self._store_ring_buffer:
            logger.info("Ring buffer started")
            logger.info("Buffer duration=%.1fs", self._buffer_seconds)
            logger.info("JPEG quality=%s", self._jpeg_quality)
        try:
            while not self._stop.is_set():
                ok, frame = capture.read()
                if not ok or frame is None:
                    logger.error("Camera read failed index=%s", self._index)
                    self._set_error("La caméra a cessé de fournir des images.")
                    break
                # read() fournit un tableau neuf : on peut le publier tel quel
                # après le dessin, sans copie supplémentaire.
                self._publish_frame(frame)
        finally:
            capture.release()
            logger.info("Camera released")
            logger.info("CAMERA STOPPED index=%s", self._index)

    def _open_camera(self) -> cv2.VideoCapture | None:
        logger.info("Camera open requested index=%s", self._index)
        attempts: list[tuple[int, str]] = []
        if sys.platform == "win32" and PREFER_DIRECTSHOW:
            attempts.append((cv2.CAP_DSHOW, "DSHOW"))
        attempts.append((cv2.CAP_ANY, "ANY"))

        for api, api_name in attempts:
            capture = cv2.VideoCapture(self._index, api)
            if capture.isOpened():
                backend = api_name
                get_backend_name = getattr(capture, "getBackendName", None)
                if callable(get_backend_name):
                    try:
                        reported = str(get_backend_name())
                    except cv2.error:
                        reported = ""
                    if reported:
                        backend = reported
                with self._lock:
                    self._backend = backend
                logger.info("Camera opened index=%s backend=%s", self._index, backend)
                logger.info("CAMERA STARTED index=%s backend=%s", self._index, backend)
                return capture
            capture.release()
            logger.info("Camera backend %s failed index=%s", api_name, self._index)

        logger.error("Camera open failed index=%s", self._index)
        self._set_error("Caméra introuvable ou déjà utilisée.")
        return None

    def _configure_camera(self, capture: cv2.VideoCapture) -> None:
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._requested_width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._requested_height)
        capture.set(cv2.CAP_PROP_FPS, self._requested_fps)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, CAPTURE_BUFFER_SIZE)
        reported_fps = capture.get(cv2.CAP_PROP_FPS)
        pixel_format = fourcc_to_string(capture.get(cv2.CAP_PROP_FOURCC))
        with self._lock:
            self._pixel_format = pixel_format
        logger.info("Requested FPS=%s", self._requested_fps)
        logger.info("Driver reported FPS=%.1f", reported_fps)
        logger.info("Capture fourcc=%s", pixel_format)

    def _publish_frame(self, frame: np.ndarray) -> None:
        wall_time = datetime.now()
        monotonic_time = time.monotonic()
        draw_timestamp(frame, format_timestamp(wall_time))
        measured_fps = self._fps.tick(monotonic_time)
        fps_ready = self._fps.ready
        if self._store_ring_buffer:
            self._store_jpeg(frame, wall_time, monotonic_time)
        height, width = frame.shape[:2]

        if not self._logged_resolution:
            self._log_resolution(width, height)
            self._logged_resolution = True

        if fps_ready and (
            self._last_fps_log_mono is None
            or monotonic_time - self._last_fps_log_mono >= FPS_LOG_INTERVAL_SECONDS
        ):
            logger.info("Measured FPS=%.1f", measured_fps)
            if self._store_ring_buffer:
                self._log_buffer_summary()
            self._last_fps_log_mono = monotonic_time

        with self._lock:
            self._frame = frame
            self._frame_index += 1
            self._width = width
            self._height = height
            self._measured_fps = measured_fps
            self._fps_ready = fps_ready
            self._wall_time = wall_time
            self._monotonic_time = monotonic_time
            self._state = "running"
        self._forward_recording(frame)

    def _forward_recording(self, frame: np.ndarray) -> None:
        with self._recorder_lock:
            offer = self._recording_offer
        if offer is None:
            return
        try:
            offer(frame)
        except Exception:
            if not self._recording_fault_logged:
                logger.exception("Recording offer failed")
                self._recording_fault_logged = True

    def _log_resolution(self, width: int, height: int) -> None:
        logger.info("Requested resolution=%sx%s", self._requested_width, self._requested_height)
        logger.info("Actual resolution=%sx%s", width, height)
        if (width, height) != (self._requested_width, self._requested_height):
            logger.warning(
                "Actual resolution differs from requested (%sx%s != %sx%s)",
                width,
                height,
                self._requested_width,
                self._requested_height,
            )

    def _store_jpeg(self, frame: np.ndarray, wall_time: datetime, monotonic_time: float) -> None:
        jpeg, elapsed_ms = encode_jpeg(frame, self._jpeg_quality)
        if jpeg is None:
            self._jpeg_meter.add_failure()
            if not self._jpeg_failure_logged:
                logger.error("JPEG encode failed")
                self._jpeg_failure_logged = True
            return
        self._jpeg_meter.add_success(len(jpeg), elapsed_ms)
        self._buffer.append(
            BufferedFrame(
                monotonic_timestamp=monotonic_time,
                wall_clock_timestamp=wall_time,
                jpeg_data=jpeg,
            )
        )

    def _log_buffer_summary(self) -> None:
        stats = self._buffer.stats()
        jpeg = self._jpeg_meter.snapshot()
        logger.info("Buffer duration=%.1fs", stats.duration_seconds)
        logger.info("Buffer frames=%s", stats.frame_count)
        logger.info("Buffer memory=%s", stats.memory_bytes)
        logger.info("Average JPEG size=%s", jpeg.average_bytes)
        logger.info("JPEG encode average=%.1f ms", jpeg.average_ms)

    def _set_error(self, user_message: str) -> None:
        with self._lock:
            self._state = "error"
            self._error = user_message
            self._frame = None
