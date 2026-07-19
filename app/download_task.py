import os
import threading
from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal, QUrl
from PyQt6.QtGui import QPixmap, QImage


class DownloadTask(QObject):
    class Status(Enum):
        PENDING = "pending"
        FETCHING_INFO = "fetching_info"
        DOWNLOADING = "downloading"
        PROCESSING = "processing"
        COMPLETED = "completed"
        ERROR = "error"
        STOPPED = "stopped"

    info_updated = pyqtSignal()
    status_changed = pyqtSignal(Status)
    progress_updated = pyqtSignal(int, str)
    thumbnail_loaded = pyqtSignal(QPixmap)
    thumbnail_load_requested = pyqtSignal(str, object)

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.title = "..."
        self.thumbnail_url = None
        self.thumbnail = None
        self.platform = "Unknown"
        self._status = self.Status.FETCHING_INFO
        self.progress = 0
        self.progress_text = ""
        self.error_message = ""
        self.list_item = None
        self._stop_event = threading.Event()
        self.output_path = ""
        self.temp_path = ""
        self.video_id = None
        self.current_tmpfilename = None
        self.current_filename = None
        self.final_filepath = None
        self.thumbnail_loading = False
        self.duration = None
        # Границы обрезки в секундах. None означает «от начала» и «до конца»
        # соответственно, поэтому отличать их от нуля обязательно.
        self.clip_start = None
        self.clip_end = None
        # Список доступных форматов в сокращённом виде и выбранный вручную.
        # Полный ответ yt-dlp хранить нельзя: это десятки килобайт на видео,
        # а в очереди их могут быть сотни.
        self.formats = []
        self.format_override = None
        self.format_label = ''

    @property
    def has_clip(self):
        return self.clip_start is not None or self.clip_end is not None

    @property
    def status(self):
        return self._status

    def set_status(self, new_status):
        if self._status != new_status:
            self._status = new_status
            self.status_changed.emit(new_status)

    def update_info(self, info):
        self.title = info.get('title', 'Unknown Title')
        self.thumbnail_url = info.get('thumbnail')
        self.platform = info.get('extractor_key', 'Unknown')
        self.video_id = info.get('id')
        self.duration = info.get('duration')
        self.formats = self._compact_formats(info.get('formats'))
        self.info_updated.emit()
        self.set_status(self.Status.PENDING)
        if self.thumbnail_url and not self.thumbnail_loading:
            self.thumbnail_loading = True
            self.thumbnail_load_requested.emit(self.thumbnail_url, self)

    @staticmethod
    def _compact_formats(formats):
        """Оставляет от списка форматов только то, что показываем человеку.

        Форматы без картинки отбрасываем: отдельные звуковые дорожки уже
        доступны через пункт «только звук», а в списке качества они лишь
        мешали бы выбирать.
        """
        compact = []
        for fmt in formats or []:
            if fmt.get('vcodec') in (None, 'none'):
                continue
            height = fmt.get('height')
            if not height:
                continue
            compact.append({
                'format_id': fmt.get('format_id'),
                'ext': fmt.get('ext'),
                'height': height,
                'fps': fmt.get('fps'),
                'vcodec': fmt.get('vcodec') or '',
                'has_audio': fmt.get('acodec') not in (None, 'none'),
                'filesize': fmt.get('filesize') or fmt.get('filesize_approx'),
            })
        compact.sort(key=lambda f: (f['height'], f['fps'] or 0, f['filesize'] or 0), reverse=True)
        return compact

    def update_current_paths(self, tmpfilename=None, filename=None):
        if tmpfilename:
            self.current_tmpfilename = tmpfilename
        if filename:
            self.current_filename = filename

    def set_thumbnail(self, pixmap):
        self.thumbnail = pixmap
        self.thumbnail_loaded.emit(pixmap)
        self.thumbnail_loading = False

    def update_progress(self, percent, text):
        self.progress = percent
        self.progress_text = text
        self.progress_updated.emit(percent, text)

    def set_error(self, message):
        self.error_message = message
        self.set_status(self.Status.ERROR)

    def set_completed(self, filepath):
        self.final_filepath = filepath
        self.set_status(self.Status.COMPLETED)
        self.update_progress(100, "")

    def request_stop(self):
        self._stop_event.set()
        if self.status in (self.Status.PENDING, self.Status.DOWNLOADING, self.Status.PROCESSING):
            self.set_status(self.Status.STOPPED)

    def is_stop_requested(self):
        return self._stop_event.is_set()
