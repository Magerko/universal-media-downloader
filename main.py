import sys
import logging
import traceback
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSettings
from app.main_window import MainWindow
from app.translation import Translator
from app.theme_manager import ThemeManager
from app import paths


def setup_logging():
    # Must not write beside the executable: in a frozen build that is a
    # temporary folder, and under Program Files it raises PermissionError -
    # here, before QApplication exists, so the user would see nothing at all.
    log_dir = paths.logs_dir()
    log_file = os.path.join(log_dir, 'app.log')
    logging.basicConfig(
        filename=log_file,
        filemode='a',
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        level=logging.DEBUG,
        encoding='utf-8'
    )


def excepthook(exc_type, exc_value, exc_tb):
    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logging.critical(f"Unhandled exception:\n{tb_text}")
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def main():
    setup_logging()
    sys.excepthook = excepthook
    logger = logging.getLogger(__name__)

    try:
        app = QApplication(sys.argv)

        settings = QSettings('Magerko', 'UniversalMediaDownloader')

        translator = Translator()
        saved_language = settings.value('language', 'ru')
        translator.set_language(saved_language)

        icon_path = paths.resource_path('assets', 'icon.png')
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
        else:
            logger.warning(f'Иконка не найдена по пути: {icon_path}')

        window = MainWindow(translator, settings)

        theme_manager = ThemeManager(window.settings)
        theme_manager.apply_theme()

        window.show()

        sys.exit(app.exec())

    except Exception:
        logger.exception('Произошла фатальная ошибка при запуске приложения.')
        traceback.print_exc()
        # Without this the process reported success after failing to start,
        # which hides the crash from anything that checks the exit code.
        sys.exit(1)


if __name__ == '__main__':
    main()
