import os
import traceback
import logging
import glob
import subprocess
import shutil
import sys
import time
import threading
import hashlib
import yt_dlp
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap, QImage
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .paths import default_download_dir

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
    playlist_fetched = pyqtSignal(dict)
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
                # Плоский разбор: ссылки с названиями без опроса каждого
                # видео. На одиночную ссылку не влияет.
                'extract_flat': 'in_playlist',
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
                if info.get('_type') == 'playlist':
                    # entries бывает генератором — разворачиваем в потоке.
                    info = dict(info, entries=[e for e in (info.get('entries') or []) if e])
                    self.signals.playlist_fetched.emit(info)
                else:
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
        self._final_path = None

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
            speed = (d.get('_speed_str') or '').strip()
            eta = (d.get('_eta_str') or '').strip()
            if total_bytes:
                # Загрузку укладываем в 0-90%: остальное занимает обработка.
                raw_percent = d.get('downloaded_bytes', 0) / total_bytes * 100
                percent = int(raw_percent * 0.9)
                parts = [f"{int(raw_percent)}%"]
                if speed:
                    parts.append(speed)
                if eta:
                    parts.append(f"осталось {eta}")
                self.task.update_progress(percent, " | ".join(parts))
            else:
                # При обрезке по времени качается участок, и общего размера
                # yt-dlp не знает. Раньше это условие просто не выполнялось, и
                # полоса стояла на нуле без единой подписи — со стороны
                # неотличимо от зависшей программы.
                done = d.get('downloaded_bytes') or 0
                parts = [f"Скачано {done / 1048576:.1f} МБ"]
                if speed:
                    parts.append(speed)
                self.task.update_progress(self.task.progress or 1, " | ".join(parts))
        elif d['status'] == 'finished':
            self.task.set_status(self.task.Status.PROCESSING)
            self.task.update_progress(90, "Обработка файла...")
            final_path = d.get('filename')
            if final_path:
                self.task.update_current_paths(filename=final_path)

    # yt-dlp зовёт шаги обработки именами своих классов.
    POSTPROCESSOR_NAMES = {
        'Merger': 'Соединение видео и звука',
        'FFmpegMerger': 'Соединение видео и звука',
        'VideoRemuxer': 'Смена контейнера',
        'FFmpegVideoRemuxer': 'Смена контейнера',
        'VideoConvertor': 'Перекодирование видео',
        'FFmpegVideoConvertor': 'Перекодирование видео',
        'ExtractAudio': 'Извлечение звука',
        'FFmpegExtractAudio': 'Извлечение звука',
        'FFmpegVideoRemuxer': 'Смена контейнера',
        'FFmpegMetadata': 'Запись сведений о файле',
        'EmbedThumbnail': 'Встраивание обложки',
        'FFmpegEmbedSubtitle': 'Встраивание субтитров',
        'FFmpegSubtitlesConvertor': 'Подготовка субтитров',
        'MoveFiles': 'Перенос файла',
        'MoveFilesAfterDownload': 'Перенос файла',
    }

    def postprocessor_hook(self, d):
        if self.task.is_stop_requested() or self._cancel_requested:
            raise yt_dlp.utils.DownloadCancelled("Download stopped by user during processing.")
        status = d.get('status')
        pp_name = d.get('postprocessor', '')
        if status == 'started':
            # Незнакомое имя оставляем как есть: список растёт с версиями.
            readable = self.POSTPROCESSOR_NAMES.get(pp_name, pp_name)
            self.task.update_progress(92, f"{readable}...")
        elif status == 'finished':
            self.task.update_progress(98, "Завершение...")

    def _default_save_path(self):
        # Used to be a "downloads" folder beside the code, which lands inside a
        # temporary directory in a frozen build and is unwritable under
        # Program Files.
        return default_download_dir()

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

    def _require_ffmpeg(self):
        if not self.ffmpeg_path:
            raise RuntimeError(
                'This download needs FFmpeg, which was not found. Install it and '
                'put it on your PATH, or use the release build that bundles it.')

    def _strip_audio_copy(self, in_path, out_path):
        self._require_ffmpeg()
        cmd = [
            self.ffmpeg_path, '-y', '-i', in_path,
            '-map', '0:v', '-c:v', 'copy', '-an', out_path
        ]
        # Понижаем приоритет процесса на Windows для предотвращения лагов.
        # CREATE_NO_WINDOW нужен отдельно: без него в оконной сборке на каждый
        # вызов ffmpeg мигает консоль.
        creation_flags = 0
        if sys.platform == 'win32':
            creation_flags = 0x00004000 | subprocess.CREATE_NO_WINDOW  # BELOW_NORMAL_PRIORITY_CLASS
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   stdin=subprocess.DEVNULL,
                                   creationflags=creation_flags)

        # Обновляем прогресс во время обработки
        self.task.update_progress(99, "Удаление звука...")

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
        self._require_ffmpeg()
        cmd = [
            self.ffmpeg_path, '-y', '-i', in_path,
            '-map', '0:v', '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast',
            '-movflags', '+faststart', '-an', out_path
        ]
        self._run_ffmpeg_with_progress(
            cmd, 'Перекодирование видео',
            self._media_duration(in_path), base_pct=90, span_pct=9)

    def _convert_to_mp4(self, path):
        """Пережимает видео в mp4 с прогрессом. Возвращает новый путь.

        Ключи те же, что у FFmpegVideoConvertorPP из yt-dlp.
        """
        if not os.path.isfile(path):
            return path
        base, ext = os.path.splitext(path)
        if ext.lower() == '.mp4':
            return path
        out_path = base + '.converting.mp4'
        cmd = [
            self.ffmpeg_path, '-y', '-i', path,
            '-map', '0', '-dn', '-ignore_unknown', '-c:s', 'mov_text',
            '-movflags', '+faststart', out_path,
        ]
        try:
            self._run_ffmpeg_with_progress(
                cmd, 'Перекодирование видео',
                self._media_duration(path), base_pct=90, span_pct=9)
        except Exception:
            if os.path.exists(out_path):
                try:
                    os.remove(out_path)
                except Exception:
                    pass
            raise
        final_path = base + '.mp4'
        os.replace(out_path, final_path)
        # Только после успешного переименования.
        try:
            os.remove(path)
        except Exception:
            pass
        return final_path

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

    def _media_duration(self, path):
        """Длительность файла в секундах, или None если определить не вышло."""
        probe = os.path.join(os.path.dirname(self.ffmpeg_path or ''), 'ffprobe.exe')
        if not os.path.isfile(probe):
            probe = 'ffprobe'
        try:
            out = subprocess.run(
                [probe, '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'csv=p=0', path],
                capture_output=True, text=True, stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
                timeout=15)
            value = float(out.stdout.strip())
            return value if value > 0 else None
        except Exception:
            return None

    def _run_ffmpeg_with_progress(self, cmd, label, duration, base_pct, span_pct):
        """Запускает ffmpeg, переводя -progress в проценты и остаток времени."""
        self._require_ffmpeg()
        cmd = list(cmd) + ['-progress', 'pipe:1', '-nostats']
        creation_flags = 0
        if sys.platform == 'win32':
            creation_flags = 0x00004000 | subprocess.CREATE_NO_WINDOW
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL, creationflags=creation_flags,
            text=True, encoding='utf-8', errors='replace', bufsize=1)

        # stderr читаем параллельно: иначе его буфер переполнится и ffmpeg
        # встанет на записи, пока мы ждём stdout. Дедлок.
        stderr_chunks = []

        def drain_stderr():
            stderr_chunks.append(process.stderr.read())

        stderr_reader = threading.Thread(target=drain_stderr, daemon=True)
        stderr_reader.start()

        started = time.monotonic()
        self.task.update_progress(base_pct, f'{label}...')
        try:
            for line in process.stdout:
                if self.task.is_stop_requested() or self._cancel_requested:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    raise yt_dlp.utils.DownloadCancelled('FFmpeg processing cancelled by user.')
                if not line.startswith('out_time_us=') or not duration:
                    continue
                try:
                    done = int(line.split('=', 1)[1]) / 1_000_000
                except ValueError:
                    continue
                fraction = max(0.0, min(1.0, done / duration))
                elapsed = time.monotonic() - started
                # По фактической скорости: на разном железе она разная.
                if fraction > 0.01:
                    remaining = elapsed / fraction - elapsed
                    text = f'{label} — осталось {self._format_eta(remaining)}'
                else:
                    text = f'{label}...'
                # pyqtSignal(int, str) — дробное значение уронит emit.
                self.task.update_progress(int(base_pct + span_pct * fraction), text)
        finally:
            process.stdout.close()

        returncode = process.wait()
        stderr_reader.join(timeout=5)
        process.stderr.close()
        if returncode != 0:
            raise subprocess.CalledProcessError(
                returncode, cmd, None, ''.join(c for c in stderr_chunks if c))

    @staticmethod
    def _format_eta(seconds):
        seconds = int(max(0, seconds))
        if seconds < 60:
            return f'{seconds} сек'
        minutes, seconds = divmod(seconds, 60)
        if minutes < 60:
            return f'{minutes} мин {seconds:02d} сек'
        hours, minutes = divmod(minutes, 60)
        return f'{hours} ч {minutes:02d} мин'

    # Признаки того, что YouTube упёрся именно в отсутствие движка JavaScript.
    _JS_FAILURE_MARKERS = (
        'signature', 'nsig', 'javascript', 'js runtime', 'jsinterp',
        'player response', 'unable to extract',
    )

    def _explain_error(self, message):
        """Дополняет ошибку подсказкой про Deno, если она про JS.

        Сообщения yt-dlp вроде «Signature extraction failed» сами по себе
        ничего не объясняют.
        """
        lowered = message.lower()
        looks_like_js = any(marker in lowered for marker in self._JS_FAILURE_MARKERS)
        if not looks_like_js or 'youtube' not in (self.task.platform or '').lower():
            return message
        if shutil.which('deno'):
            return message
        return (f'{message}\n\n'
                'Похоже, YouTube требует движок JavaScript. Установите Deno '
                '(deno.com) и повторите загрузку — в PowerShell:\n'
                'irm https://deno.land/install.ps1 | iex')

    def _record_final_path(self, path):
        self._final_path = path
        self.task.update_current_paths(filename=path)

    def _video_postprocessors(self):
        """Что делать с контейнером скачанного видео.

        По умолчанию ремукс: FFmpegVideoConvertor внутри yt-dlp работает без
        '-c copy' и пережимает каждый webm целиком, тогда как ремуксер просто
        перекладывает дорожки. Перекодирование — осознанный выбор ради
        совместимости со старой техникой.
        """
        policy = self.settings.value('video_container_policy', 'remux', type=str)
        if policy == 'keep':
            return []
        if policy == 'convert':
            # Перекодируем сами, после загрузки: postprocessor_hook даёт
            # только «начал» и «закончил», без прогресса.
            return []
        # Контейнеры перечислены явно: простое 'mp4' утянуло бы в ремукс и
        # те, чьи кодеки mp4 не принимает. Остальное yt-dlp пропустит.
        return [{'key': 'FFmpegVideoRemuxer', 'preferedformat': 'webm>mp4/mkv>mp4/flv>mp4'}]

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
                'socket_timeout': 30,
                'retries': 10,
                'fragment_retries': 3,
                # Каждая задача — ровно одно видео. Плейлист разворачивается
                # в отдельные задачи заранее, и без этого ключа ссылка вида
                # «видео из плейлиста» утянула бы весь плейлист внутрь одной
                # карточки: с общим прогрессом и одним именем файла на всех.
                'noplaylist': True,
                # EJS support for YouTube (requires Deno runtime)
                'enable_js': True,
                'remote_components': {'ejs:github': True},
            }
            # Only pass ffmpeg_location when we actually have one: handing
            # yt-dlp a None makes it treat "None" as a path instead of falling
            # back to its own discovery.
            if self.ffmpeg_path:
                ydl_opts['ffmpeg_location'] = self.ffmpeg_path

            # Формат, выбранный вручную для этого видео, важнее качества из
            # настроек: настройка задаётся заранее и одна на всю площадку, а
            # здесь человек смотрел на список именно этого ролика.
            if self.task.format_override:
                chosen_format = self.task.format_override

            video_only_mode = chosen_format == 'video_only_stripped'
            if video_only_mode:
                ydl_opts['format'] = 'bestvideo[ext=mp4]/bestvideo/best'
                ydl_opts['postprocessors'] = self._video_postprocessors()
            elif chosen_format in ['bestaudio/best', 'bestaudio'] or str(chosen_format).startswith('bestaudio'):
                ydl_opts['format'] = chosen_format
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            else:
                ydl_opts['format'] = chosen_format
                ydl_opts['postprocessors'] = self._video_postprocessors()
            if self.task.has_clip:
                start, end = self.task.clip_start, self.task.clip_end
                # yt-dlp ждёт функцию, а не пару чисел: она вызывается для
                # каждого видео и может вернуть несколько кусков. Нам нужен
                # один, границы которого уже выбраны человеком.
                ydl_opts['download_ranges'] = lambda info, ydl: [{
                    'start_time': start if start is not None else 0,
                    'end_time': end if end is not None else (info.get('duration') or 0),
                }]
                # Без этого ключа рез идёт по ближайшему опорному кадру и
                # уезжает на несколько секунд от заданного момента.
                ydl_opts['force_keyframes_at_cuts'] = True

            if self.settings.value('subtitles_enabled', False, type=bool):
                ydl_opts['writesubtitles'] = True
                ydl_opts['subtitleslangs'] = ['en', 'ru', 'uk']
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
            # Настоящий путь к готовому файлу приходит из post_hooks: yt-dlp
            # зовёт их последними, уже после всей постобработки, и передаёт
            # info_dict['filepath']. Раньше имя предсказывалось заранее —
            # расширение просто подменялось на mp4, если были постпроцессоры.
            # Предсказание врёт при любом раскладе, кроме перекодирования:
            # при «оставить как есть» файл остаётся webm, при ремуксе mov
            # остаётся mov. Приложение отчитывалось бы о готовности файла,
            # которого нет по указанному пути.
            self._final_path = None
            ydl_opts['post_hooks'] = [self._record_final_path]

            # Между нажатием и первым байтом проходит заметное время: сведения
            # о видео запрашиваются по сети, а YouTube вдобавок режет скорость.
            # Без этой строки карточка всё это время пуста, и программа
            # выглядит зависшей.
            self.task.update_progress(1, 'Получение сведений о видео...')

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.task.url, download=False)
                predicted_filepath = ydl.prepare_filename(info)
                if self.task.is_stop_requested() or self._cancel_requested:
                    raise yt_dlp.utils.DownloadCancelled("Download stopped before start.")
                if self.task.has_clip:
                    # При загрузке отрезка yt-dlp не сообщает ни размера, ни
                    # прогресса — сказать, сколько осталось, нечем. Честнее
                    # написать, что идёт работа, чем оставить пустую полосу.
                    self.task.update_progress(
                        2, 'Скачивается выбранный отрезок, размер заранее неизвестен...')
                else:
                    self.task.update_progress(2, 'Начинается загрузка...')
                ydl.download([self.task.url])
                # Хук не срабатывает, если файл уже был скачан ранее; тогда
                # опираемся на предсказание, как и раньше.
                final_filepath = self._final_path or predicted_filepath
                if video_only_mode:
                    try:
                        self.task.update_progress(98, "Обработка видео (удаление звука)...")
                        self._force_video_only(final_filepath)
                    except Exception as e:
                        logger.error(f"Strip-audio failed for {self.task.url}: {e}")
                        raise
                elif self.settings.value('video_container_policy', 'remux', type=str) == 'convert':
                    try:
                        final_filepath = self._convert_to_mp4(final_filepath)
                    except Exception as e:
                        logger.error(f"Convert to mp4 failed for {self.task.url}: {e}")
                        raise
                if not self.task.is_stop_requested() and not self._cancel_requested:
                    self.task.set_completed(final_filepath)
        except yt_dlp.utils.DownloadCancelled:
            self.task.set_status(self.task.Status.STOPPED)
        except Exception as e:
            logger.error(f"DownloadWorker error for {self.task.url}: {traceback.format_exc()}")
            self.signals.error.emit(self._explain_error(str(e)))
        finally:
            if self.task.status != self.task.Status.COMPLETED:
                path = self.task.save_path or self._default_save_path()
                self._cleanup_incomplete(path)
            self.signals.finished.emit()
