import os
import traceback
import logging
import glob
import subprocess
import sys
import time
import hashlib
import yt_dlp
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap, QImage
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Global HTTP session with connection pooling and retries
_http_session = None


def get_http_session():
    """Get or create a global HTTP session with connection pooling."""
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=retry_strategy
        )
        _http_session.mount("http://", adapter)
        _http_session.mount("https://", adapter)
        _http_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    return _http_session


# Thumbnail cache (in-memory LRU cache)
class ThumbnailCache:
    """Simple LRU cache for thumbnails."""
    def __init__(self, max_size=100):
        self._cache = {}
        self._order = []
        self._max_size = max_size

    def _get_key(self, url):
        return hashlib.md5(url.encode()).hexdigest()

    def get(self, url):
        key = self._get_key(url)
        if key in self._cache:
            # Move to end (most recently used)
            self._order.remove(key)
            self._order.append(key)
            return self._cache[key]
        return None

    def set(self, url, pixmap):
        key = self._get_key(url)
        if key in self._cache:
            self._order.remove(key)
        elif len(self._cache) >= self._max_size:
            # Remove oldest
            oldest = self._order.pop(0)
            del self._cache[oldest]
        self._cache[key] = pixmap
        self._order.append(key)

    def clear(self):
        self._cache.clear()
        self._order.clear()


# Global thumbnail cache
thumbnail_cache = ThumbnailCache(max_size=100)


class WorkerSignals(QObject):
    info_fetched = pyqtSignal(dict)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)
    thumbnail_loaded = pyqtSignal(QPixmap)


class InfoWorker(QRunnable):
    def __init__(self, url, settings):
        super().__init__()
        self.url = url
        self.settings = settings
        self.signals = WorkerSignals()

    def run(self):
        try:
            ydl_opts = {
                'quiet': True,
                'skip_download': True,
                'nocheckcertificate': True,
                # EJS support for YouTube (requires Deno runtime)
                'enable_js': True,
                'remote_components': {'ejs:github': True},
            }
            use_cookies = self.settings.value('use_cookies', False, type=bool)
            if use_cookies:
                source_type = self.settings.value('cookie_source_type', 'file')
                if source_type == 'file':
                    cookie_file = self.settings.value('cookies_path', '')
                    if cookie_file and os.path.exists(cookie_file):
                        ydl_opts['cookiefile'] = cookie_file
                else:
                    browser = self.settings.value('cookie_browser', self.settings.value('cookie_source', 'none'))
                    if browser and browser != 'none':
                        try:
                            ydl_opts['cookiesfrombrowser'] = (browser,)
                        except Exception as e:
                            logger.warning(f"Browser {browser} not available for cookies: {e}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                self.signals.info_fetched.emit(info)
        except Exception as e:
            logger.error(f"InfoWorker error for {self.url}: {e}")
            self.signals.error.emit(str(e))


class ThumbnailWorker(QRunnable):
    def __init__(self, url, task):
        super().__init__()
        self.url = url
        self.task = task
        self.signals = WorkerSignals()

    def run(self):
        try:
            # Check cache first
            cached = thumbnail_cache.get(self.url)
            if cached is not None:
                self.signals.thumbnail_loaded.emit(cached)
                return

            # Use connection-pooled session
            session = get_http_session()
            response = session.get(self.url, timeout=10)
            response.raise_for_status()
            image = QImage()
            image.loadFromData(response.content)
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                # Cache the result
                thumbnail_cache.set(self.url, pixmap)
                self.signals.thumbnail_loaded.emit(pixmap)
        except Exception as e:
            logger.debug(f"Failed to load thumbnail from {self.url}: {e}")


class DownloadWorker(QRunnable):
    def __init__(self, task, settings, ffmpeg_path, translator):
        super().__init__()
        self.task = task
        self.settings = settings
        self.ffmpeg_path = ffmpeg_path
        self.translator = translator
        self.signals = WorkerSignals()
        self._cancel_requested = False

    def cancel(self):
        self._cancel_requested = True
        self.task.request_stop()

    def progress_hook(self, d):
        if self.task.is_stop_requested() or self._cancel_requested:
            raise yt_dlp.utils.DownloadCancelled("Download stopped by user.")
        fn = d.get('filename')
        tmp = d.get('tmpfilename')
        if tmp or fn:
            self.task.update_current_paths(tmpfilename=tmp, filename=fn)
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            if total_bytes:
                # Scale download to 0-90%
                raw_percent = d.get('downloaded_bytes', 0) / total_bytes * 100
                percent = int(raw_percent * 0.9)
                speed = d.get('_speed_str', 'N/A').strip()
                eta = d.get('_eta_str', 'N/A').strip()
                progress_text = f"{int(raw_percent)}% | {speed} | ETA: {eta}"
                self.task.update_progress(percent, progress_text)
        elif d['status'] == 'finished':
            self.task.set_status(self.task.Status.PROCESSING)
            self.task.update_progress(90, "Processing...")
            final_path = d.get('filename')
            if final_path:
                self.task.update_current_paths(filename=final_path)

    def postprocessor_hook(self, d):
        if self.task.is_stop_requested() or self._cancel_requested:
            raise yt_dlp.utils.DownloadCancelled("Download stopped by user during processing.")
        status = d.get('status')
        pp_name = d.get('postprocessor', '')
        if status == 'started':
            self.task.update_progress(92, f"Processing: {pp_name}...")
        elif status == 'finished':
            self.task.update_progress(98, "Finalizing...")

    def _default_save_path(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        dl_dir = os.path.join(root, 'downloads')
        os.makedirs(dl_dir, exist_ok=True)
        return dl_dir

    def _cleanup_incomplete(self, save_path):
        try:
            paths = set()
            if self.task.current_tmpfilename:
                paths.add(self.task.current_tmpfilename)
            if self.task.current_filename and os.path.exists(self.task.current_filename):
                paths.add(self.task.current_filename)
            if self.task.video_id:
                marker = f"[{self.task.video_id}]"
                for name in os.listdir(save_path):
                    if marker in name:
                        paths.add(os.path.join(save_path, name))
            for pattern in ("*.part", "*.ytdl", "*.temp", "*.aria2", "*.fragment", "*.frag", "*.downloading"):
                for p in glob.glob(os.path.join(save_path, pattern)):
                    if self.task.video_id and f"[{self.task.video_id}]" not in os.path.basename(p):
                        continue
                    paths.add(p)
            for p in list(paths):
                try:
                    if os.path.isfile(p):
                        os.remove(p)
                except Exception:
                    pass
        except Exception:
            pass

    def _strip_audio_copy(self, in_path, out_path):
        cmd = [
            self.ffmpeg_path, '-y', '-i', in_path,
            '-map', '0:v', '-c:v', 'copy', '-an', out_path
        ]
        # Понижаем приоритет процесса на Windows для предотвращения лагов
        creation_flags = 0x00004000 if sys.platform == 'win32' else 0  # BELOW_NORMAL_PRIORITY_CLASS
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   creationflags=creation_flags)

        # Обновляем прогресс во время обработки
        self.task.update_progress(99, "Removing audio (copy mode)...")

        # Ждем завершения с периодической проверкой отмены
        while process.poll() is None:
            if self.task.is_stop_requested() or self._cancel_requested:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                raise yt_dlp.utils.DownloadCancelled("FFmpeg processing cancelled by user.")
            time.sleep(0.1)

        stdout, stderr = process.communicate()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd, stdout, stderr)

    def _strip_audio_reencode(self, in_path, out_path):
        cmd = [
            self.ffmpeg_path, '-y', '-i', in_path,
            '-map', '0:v', '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast',
            '-movflags', '+faststart', '-an', out_path
        ]
        # Понижаем приоритет процесса на Windows для предотвращения лагов
        creation_flags = 0x00004000 if sys.platform == 'win32' else 0  # BELOW_NORMAL_PRIORITY_CLASS
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   creationflags=creation_flags)

        # Обновляем прогресс во время обработки
        self.task.update_progress(99, "Re-encoding video...")

        # Ждем завершения с периодической проверкой отмены
        while process.poll() is None:
            if self.task.is_stop_requested() or self._cancel_requested:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                raise yt_dlp.utils.DownloadCancelled("FFmpeg processing cancelled by user.")
            time.sleep(0.1)

        stdout, stderr = process.communicate()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd, stdout, stderr)

    def _force_video_only(self, path):
        if not os.path.isfile(path):
            return
        base, ext = os.path.splitext(path)
        tmp_out = base + '.mute' + ext
        try:
            self._strip_audio_copy(path, tmp_out)
        except Exception:
            # Проверяем отмену перед повторной попыткой с перекодировкой
            if self.task.is_stop_requested() or self._cancel_requested:
                raise yt_dlp.utils.DownloadCancelled("FFmpeg processing cancelled by user.")
            try:
                self._strip_audio_reencode(path, tmp_out)
            except Exception as e:
                if os.path.exists(tmp_out):
                    try:
                        os.remove(tmp_out)
                    except Exception:
                        pass
                raise e
        os.replace(tmp_out, path)

    def run(self):
        try:
            platform = self.task.platform.lower().replace(' ', '_').replace('(', '').replace(')', '')
            quality_key = f'quality_{platform}'
            chosen_format = self.settings.value(quality_key, 'bestvideo+bestaudio/best')
            save_path = self.settings.value('save_path', '')
            if not save_path or not os.path.isdir(save_path):
                save_path = self._default_save_path()
            self.task.save_path = save_path
            ydl_opts = {
                'outtmpl': os.path.join(save_path, '%(title)s [%(id)s].%(ext)s'),
                'progress_hooks': [self.progress_hook],
                'postprocessor_hooks': [self.postprocessor_hook],
                'quiet': True,
                'noprogress': False,
                'ignoreerrors': False,
                'nocheckcertificate': True,
                'ffmpeg_location': self.ffmpeg_path,
                'socket_timeout': 30,
                'retries': 10,
                'fragment_retries': 3,
                # EJS support for YouTube (requires Deno runtime)
                'enable_js': True,
                'remote_components': {'ejs:github': True},
            }
            video_only_mode = chosen_format == 'video_only_stripped'
            if video_only_mode:
                ydl_opts['format'] = 'bestvideo[ext=mp4]/bestvideo/best'
                ydl_opts['postprocessors'] = [
                    {'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}
                ]
            elif chosen_format in ['bestaudio/best', 'bestaudio'] or str(chosen_format).startswith('bestaudio'):
                ydl_opts['format'] = chosen_format
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            else:
                ydl_opts['format'] = chosen_format
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }]
            if self.settings.value('subtitles_enabled', False, type=bool):
                ydl_opts['writesubtitles'] = True
                ydl_opts['subtitleslangs'] = ['en', 'ru', 'uk', 'fr']
            use_cookies = self.settings.value('use_cookies', False, type=bool)
            if use_cookies:
                source_type = self.settings.value('cookie_source_type', 'file')
                if source_type == 'file':
                    cookie_file = self.settings.value('cookies_path', '')
                    if cookie_file and os.path.exists(cookie_file):
                        ydl_opts['cookiefile'] = cookie_file
                else:
                    browser = self.settings.value('cookie_browser', self.settings.value('cookie_source', 'none'))
                    if browser and browser != 'none':
                        try:
                            ydl_opts['cookiesfrombrowser'] = (browser,)
                        except Exception as e:
                            logger.warning(f"Browser {browser} not available for cookies: {e}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.task.url, download=False)
                info_copy = info.copy()
                if 'postprocessors' in ydl_opts:
                    info_copy['ext'] = 'mp4'
                final_filepath = ydl.prepare_filename(info_copy)
                if self.task.is_stop_requested() or self._cancel_requested:
                    raise yt_dlp.utils.DownloadCancelled("Download stopped before start.")
                ydl.download([self.task.url])
                if video_only_mode:
                    try:
                        self.task.update_progress(98, "Processing video (removing audio)...")
                        self._force_video_only(final_filepath)
                    except Exception as e:
                        logger.error(f"Strip-audio failed for {self.task.url}: {e}")
                        raise
                if not self.task.is_stop_requested() and not self._cancel_requested:
                    self.task.set_completed(final_filepath)
        except yt_dlp.utils.DownloadCancelled:
            self.task.set_status(self.task.Status.STOPPED)
        except Exception as e:
            logger.error(f"DownloadWorker error for {self.task.url}: {traceback.format_exc()}")
            self.signals.error.emit(str(e))
        finally:
            if self.task.status != self.task.Status.COMPLETED:
                path = self.task.save_path or self._default_save_path()
                self._cleanup_incomplete(path)
            self.signals.finished.emit()
