"""Single source of truth for every path the application touches.

Read-only assets live next to the code (or inside the bundle when frozen);
anything the app writes goes to the per-user data directory. Writing next to
the executable breaks both in a frozen build, where that folder is temporary,
and under Program Files, where it is not writable.
"""
import os
import shutil
import subprocess
import sys
from functools import lru_cache
from typing import Optional

APP_NAME = 'UniversalMediaDownloader'


def _bundle_roots() -> list:
    if getattr(sys, 'frozen', False):
        roots = [os.path.dirname(os.path.abspath(sys.executable))]
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            roots.append(meipass)
        return roots
    return [os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]


def resource_path(*parts: str) -> str:
    """Absolute path to a bundled, read-only resource."""
    relative = os.path.join(*parts)
    roots = _bundle_roots()
    for root in roots:
        candidate = os.path.join(root, relative)
        if os.path.exists(candidate):
            return candidate
    return os.path.join(roots[0], relative)


def user_data_dir() -> str:
    if os.name == 'nt':
        base = os.environ.get('APPDATA') or os.path.expanduser('~')
    elif sys.platform == 'darwin':
        base = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support')
    else:
        base = os.environ.get('XDG_DATA_HOME') or os.path.join(
            os.path.expanduser('~'), '.local', 'share')
    return os.path.join(base, APP_NAME)


def logs_dir() -> str:
    path = os.path.join(user_data_dir(), 'logs')
    os.makedirs(path, exist_ok=True)
    return path


def data_dir() -> str:
    path = os.path.join(user_data_dir(), 'data')
    os.makedirs(path, exist_ok=True)
    return path


def default_download_dir() -> str:
    path = os.path.join(os.path.expanduser('~'), 'Downloads', 'UMD')
    os.makedirs(path, exist_ok=True)
    return path


@lru_cache(maxsize=None)
def ffmpeg_path() -> Optional[str]:
    """Bundled ffmpeg if present, otherwise whatever is on PATH, else None."""
    exe = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
    subfolders = ('', 'ffmpeg', os.path.join('ffmpeg', 'bin'),
                  os.path.join('assets', 'ffmpeg', 'bin'))
    for root in _bundle_roots():
        for sub in subfolders:
            candidate = os.path.join(root, sub, exe)
            if os.path.isfile(candidate):
                return candidate
    return shutil.which('ffmpeg')


def has_ffmpeg() -> bool:
    return ffmpeg_path() is not None


def subprocess_kwargs() -> dict:
    """Keeps console windows from flashing in a windowed build and stops the
    child inheriting an invalid stdin handle."""
    kwargs = {'stdin': subprocess.DEVNULL}
    if os.name == 'nt':
        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
    return kwargs
