import os
import json
import logging
from PyQt6.QtCore import QObject, pyqtSignal

from .paths import resource_path

logger = logging.getLogger(__name__)


class Translator(QObject):
    language_changed = pyqtSignal()

    def __init__(self, project_root=None, parent=None):
        super().__init__(parent)
        # project_root is kept for callers that still pass it, but resource
        # lookup now goes through resource_path so it works in a frozen build.
        self.project_root = project_root
        self.current_language = 'ru'
        self.translations = {}
        self.load_translations()

    def _read_json(self, path):
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f'Ошибка чтения файла перевода: {path} - {e}')
        else:
            logger.warning(f'Не найден файл перевода: {path}')
        return {}

    def load_translations(self):
        data = self._read_json(resource_path('assets', f'{self.current_language}.json'))
        if not data:
            data = self._read_json(resource_path('assets', 'en.json'))
        self.translations = data or {}

    def translate(self, key: str, fallback: str = None) -> str:
        if not isinstance(key, str):
            return fallback or str(key)
        if key in self.translations:
            return self.translations[key]
        lk = key.lower()
        if lk in self.translations:
            return self.translations[lk]
        return fallback or key

    def set_language(self, language_code: str):
        if self.current_language != language_code:
            self.current_language = language_code
            self.load_translations()
            self.language_changed.emit()
        else:
            self.load_translations()
