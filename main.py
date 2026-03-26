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


def setup_logging():
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
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
        project_root = os.path.dirname(os.path.abspath(__file__))
        app = QApplication(sys.argv)

        settings = QSettings('Magerko', 'UniversalMediaDownloader')

        translator = Translator(project_root=project_root)
        saved_language = settings.value('language', 'en')
        translator.set_language(saved_language)

        icon_path = os.path.join(project_root, 'assets', 'icon.png')
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
        else:
            logger.warning(f'Image not found in root: {icon_path}')

        window = MainWindow(translator, settings)

        theme_manager = ThemeManager(window.settings)
        theme_manager.apply_theme()

        window.show()

        sys.exit(app.exec())
    except Exception as e:
        logger.exception('Fatal error on execution.')
        traceback.print_exc()


if __name__ == '__main__':
    main()
