import logging
import re
from PyQt6.QtCore import QObject, pyqtSignal
from .threads import InfoWorker, DownloadWorker, ThumbnailWorker
from .download_task import DownloadTask

logger = logging.getLogger(__name__)


class DownloadManager(QObject):
    task_added = pyqtSignal(DownloadTask)
    playlist_found = pyqtSignal(DownloadTask, str, list)
    download_started = pyqtSignal()
    all_downloads_finished = pyqtSignal()
    status_updated = pyqtSignal(str)
    summary_updated = pyqtSignal(str)
    active_threads_changed = pyqtSignal(int, int)

    def __init__(self, settings, ffmpeg_path, thread_pool, translator):
        super().__init__()
        self.settings = settings
        self.ffmpeg_path = ffmpeg_path
        self.thread_pool = thread_pool
        self.translator = translator
        self.tasks = []
        self.active_downloads = 0
        self.is_downloading_active = False
        self._workers = {}
        self.max_thumbnail_workers = 5  # Increased for better parallelism
        self.active_thumbnail_workers = 0
        self.thumbnail_queue = []

    def _update_summary(self):
        total = len(self.tasks)
        done = len([t for t in self.tasks if t.status == DownloadTask.Status.COMPLETED])
        errs = len([t for t in self.tasks if t.status == DownloadTask.Status.ERROR])
        self.summary_updated.emit(f"{done}/{total} ✓ • {errs} ⚠")
        self.active_threads_changed.emit(self.active_downloads, int(self.settings.value('parallel_downloads', 2)))

    def _normalize_url(self, url: str) -> str:
        u = url.strip()
        m = re.search(r"https?://(?:www\.)?kick\.com/[^/]+/videos/([0-9a-fA-F-]{6,})", u)
        if m:
            return f"https://kick.com/video/{m.group(1)}"
        return u

    def add_urls(self, urls):
        for url in urls:
            url = self._normalize_url(url)
            task = DownloadTask(url)
            task.thumbnail_load_requested.connect(self.queue_thumbnail_load)
            self.tasks.append(task)
            self.task_added.emit(task)
            self.fetch_video_info(task)
        self._update_summary()

    def queue_thumbnail_load(self, url, task):
        self.thumbnail_queue.append((url, task))
        self.process_thumbnail_queue()

    def process_thumbnail_queue(self):
        while self.thumbnail_queue and self.active_thumbnail_workers < self.max_thumbnail_workers:
            url, task = self.thumbnail_queue.pop(0)
            self.load_thumbnail(url, task)

    def load_thumbnail(self, url, task):
        self.active_thumbnail_workers += 1
        worker = ThumbnailWorker(url, task)
        worker.signals.thumbnail_loaded.connect(lambda pixmap: self.on_thumbnail_loaded(task, pixmap))
        self.thread_pool.start(worker)

    def on_thumbnail_loaded(self, task, pixmap):
        task.set_thumbnail(pixmap)
        self.active_thumbnail_workers -= 1
        self.process_thumbnail_queue()

    def fetch_video_info(self, task):
        worker = InfoWorker(task.url, self.settings)
        worker.signals.info_fetched.connect(lambda info, t=task: self.on_info_fetched(t, info))
        worker.signals.playlist_fetched.connect(lambda info, t=task: self.on_playlist_fetched(t, info))
        worker.signals.error.connect(lambda error, t=task: self.on_info_error(t, error))
        self.thread_pool.start(worker)

    def on_info_fetched(self, task, info):
        task.update_info(info)
        self._update_summary()

    def on_playlist_fetched(self, task, info):
        """Заменяет задачу-заглушку отдельной задачей на каждое видео.

        Одной задачей плейлист качать нельзя: был бы общий прогресс и одно
        имя файла на всех.
        """
        entries = info.get('entries') or []
        urls = []
        for entry in entries:
            url = entry.get('url') or entry.get('webpage_url')
            if url:
                urls.append(url)

        if not urls:
            self.on_info_error(task, 'playlist has no entries')
            return

        # Спрашиваем до того, как очередь вырастет на несколько сотен.
        self.playlist_found.emit(task, info.get('title') or '', urls)

    def on_info_error(self, task, error):
        task.set_error(self.translator.translate('error_getting_info'))
        logger.error(f"Error fetching info for {task.url}: {error}")
        self._update_summary()

    def start_all(self):
        if self.is_downloading_active:
            return

        tasks_to_start = [t for t in self.tasks if t.status == DownloadTask.Status.PENDING]
        if not tasks_to_start:
            self.status_updated.emit(self.translator.translate('no_links_to_download'))
            return

        self.is_downloading_active = True
        self.download_started.emit()
        self.status_updated.emit(self.translator.translate('starting_download'))

        for task in tasks_to_start:
            self.start_task(task)
        self._update_summary()

    def start_task(self, task):
        max_concurrent = int(self.settings.value('parallel_downloads', 2))
        if self.active_downloads >= max_concurrent:
            return

        self.active_downloads += 1
        task.set_status(DownloadTask.Status.DOWNLOADING)

        worker = DownloadWorker(
            task,
            self.settings,
            self.ffmpeg_path,
            self.translator
        )
        self._workers[task] = worker
        worker.signals.finished.connect(lambda t=task: self.on_task_finished(t))
        worker.signals.error.connect(lambda error, t=task: self.on_task_error(t, error))

        self.thread_pool.start(worker)
        self._update_summary()

    def on_task_finished(self, task):
        if self.active_downloads > 0:
            self.active_downloads -= 1
        if task in self._workers:
            self._workers.pop(task, None)

        pending_tasks = [t for t in self.tasks if t.status == DownloadTask.Status.PENDING]
        if pending_tasks:
            self.start_task(pending_tasks[0])
        elif self.active_downloads == 0:
            self.is_downloading_active = False
            self.all_downloads_finished.emit()
        self._update_summary()

    def on_task_error(self, task, error_msg):
        task.set_error(error_msg)
        self.on_task_finished(task)

    def stop_all(self):
        if not self.is_downloading_active and self.active_downloads == 0:
            return

        for task in self.tasks:
            if task.status in (DownloadTask.Status.FETCHING_INFO, DownloadTask.Status.DOWNLOADING,
                               DownloadTask.Status.PENDING, DownloadTask.Status.PROCESSING):
                task.request_stop()
                worker = self._workers.get(task)
                if worker:
                    worker.cancel()

        self.status_updated.emit(self.translator.translate('stopping_downloads'))
        self.is_downloading_active = False
        self._update_summary()

    def remove_task(self, task):
        if task in self.tasks:
            task.request_stop()
            worker = self._workers.get(task)
            if worker:
                worker.cancel()
            try:
                self.tasks.remove(task)
            except ValueError:
                pass
            self._update_summary()

    def start_or_retry_task(self, task):
        if task.status in (DownloadTask.Status.ERROR, DownloadTask.Status.STOPPED, DownloadTask.Status.PENDING):
            task.set_status(DownloadTask.Status.PENDING)
            if not self.is_downloading_active:
                self.start_all()
            else:
                self.start_task(task)

    def get_completed_tasks(self):
        return [t for t in self.tasks if
                t.status in (DownloadTask.Status.COMPLETED, DownloadTask.Status.ERROR, DownloadTask.Status.STOPPED)]
