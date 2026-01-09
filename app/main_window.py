import sys
import os
import subprocess
import logging
import json
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QPushButton, QProgressBar, QLabel,
                             QFileDialog, QMessageBox, QComboBox,
                             QListWidget, QListWidgetItem, QStackedWidget,
                             QToolButton, QFrame, QApplication)
from PyQt6.QtCore import Qt, QSettings, QSize, QThreadPool, QUrl
from PyQt6.QtGui import QFont, QIcon, QDropEvent, QMovie, QDesktopServices
from .settings_tab import SettingsTab
from .about_tab import AboutTab
from .history_tab import HistoryTab
from .download_item_widget import DownloadItemWidget
from .download_manager import DownloadManager
from .translation import Translator
from .theme_manager import ThemeManager
from .flow_layout import FlowLayout
from .update_checker import UpdateChecker

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, translator: Translator, settings: QSettings):
        super().__init__()
        self.translator = translator
        self.settings = settings
        self.ffmpeg_path = self.check_ffmpeg()
        self.thread_pool = QThreadPool()
        # Set higher thread count for better parallelism
        # (thumbnail loading, info fetching, and downloads run in parallel)
        parallel_downloads = int(self.settings.value('parallel_downloads', 2))
        # Allow extra threads for thumbnails and info workers
        self.thread_pool.setMaxThreadCount(max(parallel_downloads + 6, 8))
        self.download_manager = DownloadManager(self.settings, self.ffmpeg_path, self.thread_pool, self.translator)
        self.update_checker = UpdateChecker(self, self.translator, self.settings, self.thread_pool)
        self.initUI()
        self.connect_signals()
        self.setAcceptDrops(True)
        self.translator.language_changed.connect(self.update_translations)

        # Check for updates and Deno on startup (after window is shown)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1000, self._startup_checks)

    def check_ffmpeg(self):
        project_root = os.path.dirname(os.path.abspath(__file__))
        ffmpeg_folder = os.path.join(project_root, '..', 'assets', 'ffmpeg', 'bin')
        ffmpeg_executable = os.path.join(ffmpeg_folder, 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
        if not os.path.exists(ffmpeg_executable):
            QMessageBox.critical(self,
                                 self.translator.translate('error'),
                                 f"{self.translator.translate('ffmpeg_not_found')}: {ffmpeg_executable}")
            sys.exit(1)
        try:
            subprocess.run([ffmpeg_executable, '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return ffmpeg_executable
        except Exception as e:
            QMessageBox.critical(self,
                                 self.translator.translate('error'),
                                 f"{self.translator.translate('ffmpeg_run_error')}\n{str(e)}")
            sys.exit(1)

    def initUI(self):
        self.setObjectName('MainWindow')
        self.setWindowTitle(self.translator.translate('app_title'))
        self.resize(1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        top_bar = QWidget()
        top_bar.setObjectName('TopBar')
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(15, 10, 15, 10)

        self.url_input = QLineEdit()
        self.url_input.setObjectName('UrlInput')
        self.url_input.setMinimumHeight(35)
        self.url_input.setPlaceholderText(self.translator.translate('enter_link_and_press_add'))

        self.btn_add = QToolButton()
        self.btn_add.setObjectName('AddUrlButton')
        self.btn_add.setText('➕')
        self.btn_add.setFixedSize(35, 35)
        self.btn_add.setToolTip(self.translator.translate('add_link'))

        self.btn_file = QToolButton()
        self.btn_file.setObjectName('LoadFileButton')
        self.btn_file.setText('📁')
        self.btn_file.setFixedSize(35, 35)
        self.btn_file.setToolTip(self.translator.translate('load_from_file'))

        top_bar_layout.addWidget(self.url_input)
        top_bar_layout.addWidget(self.btn_add)
        top_bar_layout.addWidget(self.btn_file)
        main_layout.addWidget(top_bar)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.nav_bar = QWidget()
        self.nav_bar.setObjectName('NavBar')
        nav_layout = QVBoxLayout(self.nav_bar)
        nav_layout.setContentsMargins(10, 20, 10, 10)
        nav_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.btn_downloads = QPushButton(self.translator.translate('loader_tab_title'))
        self.btn_downloads.setObjectName('NavButton')
        self.btn_history = QPushButton(self.translator.translate('history', 'History'))
        self.btn_history.setObjectName('NavButton')
        self.btn_settings = QPushButton(self.translator.translate('settings'))
        self.btn_settings.setObjectName('NavButton')
        self.btn_about = QPushButton(self.translator.translate('about'))
        self.btn_about.setObjectName('NavButton')

        nav_layout.addWidget(self.btn_downloads)
        nav_layout.addWidget(self.btn_history)
        nav_layout.addWidget(self.btn_settings)
        nav_layout.addWidget(self.btn_about)
        nav_layout.addStretch()

        self.language_combo = QComboBox()
        self.language_combo.setObjectName('LanguageCombo')
        self.language_combo.addItems(['English', 'Русский', 'Українська', 'Français'])
        saved_language = self.settings.value('language', 'ru')
        language_map = {'en': 0, 'ru': 1, 'uk': 2, 'fr': 3}
        self.language_combo.setCurrentIndex(language_map.get(saved_language, 1))
        nav_layout.addWidget(self.language_combo)

        self.quick_theme_combo = QComboBox()
        self.quick_theme_combo.addItems(['Dark', 'Light'])
        theme = self.settings.value('theme', 'dark')
        self.quick_theme_combo.setCurrentIndex(0 if theme == 'dark' else 1)
        nav_layout.addWidget(self.quick_theme_combo)

        self.page_stack = QStackedWidget()
        self.downloads_page_stack = QStackedWidget()

        self.downloads_list = QListWidget()
        self.downloads_list.setObjectName('DownloadsList')
        self.downloads_list.setSpacing(5)

        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        empty_card = QFrame()
        empty_card.setObjectName('EmptyCard')
        card_layout = QVBoxLayout(empty_card)
        card_layout.setSpacing(10)

        title_row = QHBoxLayout()
        title_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.rocket_label = QLabel()
        self.rocket_label.setObjectName('RocketEmoji')
        rocket_gif = os.path.join(os.path.dirname(__file__), '..', 'assets', 'animations', 'rocket.gif')
        if os.path.exists(rocket_gif):
            self.rocket_movie = QMovie(rocket_gif)
            self.rocket_label.setMovie(self.rocket_movie)
            self.rocket_label.setFixedSize(24, 24)
            self.rocket_movie.start()
        else:
            self.rocket_label.setText('🚀')
        self.empty_title = QLabel(
            self.translator.translate('no_downloads_placeholder', 'Add links to start downloading'))
        self.empty_title.setObjectName('EmptyTitle')
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        title_row.addWidget(self.rocket_label)
        title_row.addSpacing(6)
        title_row.addWidget(self.empty_title)

        bullets = QWidget()
        bullets.setObjectName('BulletsBox')
        bullets_layout = QVBoxLayout(bullets)
        bullets_layout.setContentsMargins(0, 0, 0, 0)
        bullets_layout.setSpacing(4)
        self.empty_b1 = QLabel(
            '• ' + self.translator.translate('empty_tip_dragdrop', 'Drag & drop links or .txt file here'))
        self.empty_b2 = QLabel('• ' + self.translator.translate('empty_tip_paste', 'Paste from clipboard'))
        self.empty_b3 = QLabel(
            '• ' + self.translator.translate('empty_tip_support', 'Supported: YouTube, TikTok, Instagram, VK, RuTube…'))
        for l in (self.empty_b1, self.empty_b2, self.empty_b3):
            l.setObjectName('EmptyListItem')
        bullets_layout.addWidget(self.empty_b1)
        bullets_layout.addWidget(self.empty_b2)
        bullets_layout.addWidget(self.empty_b3)

        self.quick_actions = QWidget()
        self.quick_actions.setObjectName('QuickActions')
        qa_layout = QHBoxLayout(self.quick_actions)
        qa_layout.setContentsMargins(0, 10, 0, 0)
        qa_layout.setSpacing(8)
        self.btn_paste = QPushButton('📋 ' + self.translator.translate('paste_from_clipboard', 'Paste'))
        self.btn_paste.setObjectName('SecondaryButton')
        self.btn_import = QPushButton('📁 ' + self.translator.translate('load_from_file'))
        self.btn_import.setObjectName('SecondaryButton')
        self.btn_quality = QPushButton('⚙️ ' + self.translator.translate('open_quality_settings', 'Quality settings'))
        self.btn_quality.setObjectName('SecondaryButton')
        qa_layout.addWidget(self.btn_paste)
        qa_layout.addWidget(self.btn_import)
        qa_layout.addWidget(self.btn_quality)

        self.recent_container = QWidget()
        rc_layout = QVBoxLayout(self.recent_container)
        rc_layout.setContentsMargins(0, 6, 0, 0)
        rc_layout.setSpacing(6)
        recent_label_layout = QHBoxLayout()
        self.recent_label = QLabel(self.translator.translate('recent', 'Recent') + ':')

        self.btn_clear_recent = QPushButton('🗑️')
        self.btn_clear_recent.setObjectName('SecondaryButton')
        self.btn_clear_recent.setFixedSize(28, 28)
        self.btn_clear_recent.setToolTip(self.translator.translate('clear_history'))

        recent_label_layout.addWidget(self.recent_label)
        recent_label_layout.addStretch(1)
        recent_label_layout.addWidget(self.btn_clear_recent)

        rc_layout.addLayout(recent_label_layout)
        self.recent_buttons_layout = FlowLayout(h_spacing=6, v_spacing=6)
        rc_layout.addLayout(self.recent_buttons_layout)

        self.hint_label = QLabel(self.translator.translate('empty_hint', "Press Enter or ➕ to add"))
        self.hint_label.setObjectName('HintLabel')
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        card_layout.addLayout(title_row)
        card_layout.addWidget(bullets)
        card_layout.addWidget(self.quick_actions)
        card_layout.addWidget(self.recent_container)
        card_layout.addWidget(self.hint_label)

        empty_layout.addWidget(empty_card, 0, Qt.AlignmentFlag.AlignHCenter)

        self.downloads_page_stack.addWidget(self.empty_widget)
        self.downloads_page_stack.addWidget(self.downloads_list)

        self.settings_page = SettingsTab(self.translator, self)
        self.history_page = HistoryTab(self.translator, self)
        self.about_page = AboutTab(self.translator, self)

        self.page_stack.addWidget(self.downloads_page_stack)  # index 0
        self.page_stack.addWidget(self.history_page)          # index 1
        self.page_stack.addWidget(self.settings_page)         # index 2
        self.page_stack.addWidget(self.about_page)            # index 3

        self.update_placeholder_visibility()
        self._rebuild_recent_buttons()

        content_layout.addWidget(self.nav_bar)
        content_layout.addWidget(self.page_stack, 1)
        main_layout.addLayout(content_layout)

        bottom_bar = QWidget()
        bottom_bar.setObjectName('BottomBar')
        bottom_bar_layout = QHBoxLayout(bottom_bar)
        bottom_bar_layout.setContentsMargins(15, 5, 15, 5)

        icon_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'icons')
        self.download_button = QPushButton(self.translator.translate('download_all'))
        self.download_button.setIcon(QIcon(os.path.join(icon_path, 'download.svg')))
        self.download_button.setObjectName('ActionButton')

        self.threads_label = QLabel("")
        self.threads_label.setObjectName('StatusLabel')

        self.stop_button = QPushButton(self.translator.translate('stop'))
        self.stop_button.setIcon(QIcon(os.path.join(icon_path, 'stop.svg')))
        self.stop_button.setObjectName('ActionButton')
        self.stop_button.setEnabled(False)

        self.clear_button = QPushButton(self.translator.translate('clear_completed'))
        self.clear_button.setIcon(QIcon(os.path.join(icon_path, 'clear.svg')))
        self.clear_button.setObjectName('ActionButton')

        self.btn_open_save = QToolButton()
        self.btn_open_save.setObjectName('SecondaryButton')
        self.btn_open_save.setText('📂')
        self.btn_open_save.setToolTip(self.translator.translate('open_save_folder'))

        self.btn_open_logs = QToolButton()
        self.btn_open_logs.setObjectName('SecondaryButton')
        self.btn_open_logs.setText('🧾')
        self.btn_open_logs.setToolTip(self.translator.translate('open_logs'))

        self.summary_info = QLabel("")
        self.summary_info.setObjectName('StatusLabel')

        self.status_label = QLabel(self.translator.translate('waiting'))
        self.status_label.setObjectName('StatusLabel')

        bottom_bar_layout.addWidget(self.download_button)
        bottom_bar_layout.addWidget(self.stop_button)
        bottom_bar_layout.addWidget(self.clear_button)
        bottom_bar_layout.addWidget(self.threads_label)
        bottom_bar_layout.addWidget(self.btn_open_save)
        bottom_bar_layout.addWidget(self.btn_open_logs)
        bottom_bar_layout.addStretch()
        bottom_bar_layout.addWidget(self.summary_info)
        bottom_bar_layout.addSpacing(10)
        bottom_bar_layout.addWidget(self.status_label)
        main_layout.addWidget(bottom_bar)

    def connect_signals(self):
        self.btn_add.clicked.connect(self.on_add_link)
        self.url_input.returnPressed.connect(self.on_add_link)
        self.btn_file.clicked.connect(self.on_load_from_file)
        self.language_combo.currentIndexChanged.connect(self.on_language_change)
        self.quick_theme_combo.currentIndexChanged.connect(self.on_quick_theme_change)
        self.download_button.clicked.connect(self.download_manager.start_all)
        self.stop_button.clicked.connect(self.download_manager.stop_all)
        self.clear_button.clicked.connect(self.clear_completed_items)
        self.btn_paste.clicked.connect(self.on_paste_from_clipboard)
        self.btn_import.clicked.connect(self.on_load_from_file)
        self.btn_quality.clicked.connect(lambda: self.page_stack.setCurrentIndex(2))  # Settings
        self.btn_downloads.clicked.connect(lambda: self.page_stack.setCurrentIndex(0))
        self.btn_history.clicked.connect(lambda: self.page_stack.setCurrentIndex(1))
        self.btn_settings.clicked.connect(lambda: self.page_stack.setCurrentIndex(2))
        self.btn_about.clicked.connect(lambda: self.page_stack.setCurrentIndex(3))

        # History re-download signal
        self.history_page.redownload_requested.connect(self._redownload_from_history)
        self.btn_open_save.clicked.connect(self.open_save_folder)
        self.btn_open_logs.clicked.connect(self.open_logs_folder)
        self.btn_clear_recent.clicked.connect(self._clear_recent_history)

        self.download_manager.task_added.connect(self.add_download_item_widget)
        self.download_manager.download_started.connect(self.on_download_started)
        self.download_manager.all_downloads_finished.connect(self.on_all_downloads_finished)
        self.download_manager.status_updated.connect(lambda msg: self.status_label.setText(msg))
        self.download_manager.summary_updated.connect(self.on_summary_update)
        self.download_manager.active_threads_changed.connect(self.on_threads_update)

    def update_translations(self):
        self.setWindowTitle(self.translator.translate('app_title'))
        self.url_input.setPlaceholderText(self.translator.translate('enter_link_and_press_add'))
        self.download_button.setText(self.translator.translate('download_all'))
        self.stop_button.setText(self.translator.translate('stop'))
        self.clear_button.setText(self.translator.translate('clear_completed'))
        self.status_label.setText(self.translator.translate('waiting'))
        self.btn_downloads.setText(self.translator.translate('loader_tab_title'))
        self.btn_settings.setText(self.translator.translate('settings'))
        self.btn_history.setText(self.translator.translate('history', 'History'))
        self.btn_about.setText(self.translator.translate('about'))
        self.btn_add.setToolTip(self.translator.translate('add_link'))
        self.btn_file.setToolTip(self.translator.translate('load_from_file'))
        self.empty_title.setText(
            self.translator.translate('no_downloads_placeholder', 'Add links to start downloading'))
        self.empty_b1.setText(
            '• ' + self.translator.translate('empty_tip_dragdrop', 'Drag & drop links or .txt file here'))
        self.empty_b2.setText('• ' + self.translator.translate('empty_tip_paste', 'Paste from clipboard'))
        self.empty_b3.setText(
            '• ' + self.translator.translate('empty_tip_support', 'Supported: YouTube, TikTok, Instagram, VK, RuTube…'))
        self.btn_paste.setText('📋 ' + self.translator.translate('paste_from_clipboard', 'Paste'))
        self.btn_import.setText('📁 ' + self.translator.translate('load_from_file'))
        self.btn_quality.setText('⚙️ ' + self.translator.translate('open_quality_settings', 'Quality settings'))
        self.hint_label.setText(self.translator.translate('empty_hint', "Press Enter or ➕ to add"))
        self.btn_open_save.setToolTip(self.translator.translate('open_save_folder'))
        self.btn_open_logs.setToolTip(self.translator.translate('open_logs'))
        self.recent_label.setText(self.translator.translate('recent', 'Recent') + ':')
        self.btn_clear_recent.setToolTip(self.translator.translate('clear_history'))

        self.language_combo.blockSignals(True)
        self.language_combo.setItemText(0, 'English')
        self.language_combo.setItemText(1, 'Русский')
        self.language_combo.setItemText(2, 'Українська')
        self.language_combo.setItemText(3, 'Français')
        self.language_combo.blockSignals(False)
        self.settings_page.update_translations()
        self.history_page.update_translations()
        self.about_page.update_translations()

    def on_language_change(self, index):
        language_map = {0: 'en', 1: 'ru', 2: 'uk', 3: 'fr'}
        selected_lang = language_map.get(index, 'ru')
        self.translator.set_language(selected_lang)
        self.settings.setValue('language', selected_lang)
        self.settings.sync()
        self._rebuild_recent_buttons()

    def on_quick_theme_change(self, idx):
        theme = 'dark' if idx == 0 else 'light'
        self.settings.setValue('theme', theme)
        self.settings.sync()
        ThemeManager(self.settings).apply_theme()

    def on_add_link(self):
        url = self.url_input.text().strip()
        if url:
            self.download_manager.add_urls([url])
            self._add_recent(url)
            self.url_input.clear()
            self._rebuild_recent_buttons()
        else:
            QMessageBox.warning(self, self.translator.translate('warning'), self.translator.translate('enter_link'))

    def on_paste_from_clipboard(self):
        text = QApplication.clipboard().text()
        if not text:
            return
        parts = [p.strip() for p in text.replace('\r', '\n').split('\n')]
        urls = [p for p in parts if p]
        if urls:
            self.download_manager.add_urls(urls)
            for u in urls:
                self._add_recent(u)
            self._rebuild_recent_buttons()

    def on_load_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, self.translator.translate('load_from_file'), '',
                                                   'Text Files (*.txt);;All Files (*)')
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    urls = [line.strip() for line in f if line.strip()]
                if not urls:
                    QMessageBox.warning(self, self.translator.translate('warning'),
                                        self.translator.translate('file_empty_or_invalid'))
                    return
                self.download_manager.add_urls(urls)
                for u in urls:
                    self._add_recent(u)
                self._rebuild_recent_buttons()
            except Exception as e:
                logger.error(f'Error reading file {file_path}: {e}')
                QMessageBox.critical(self, self.translator.translate('error'),
                                     f"{self.translator.translate('error_reading_file')}: {e}")

    def update_placeholder_visibility(self):
        if self.downloads_list.count() > 0:
            self.downloads_page_stack.setCurrentWidget(self.downloads_list)
        else:
            self.downloads_page_stack.setCurrentWidget(self.empty_widget)

    def add_download_item_widget(self, task):
        item_widget = DownloadItemWidget(task, self.translator)
        list_item = QListWidgetItem(self.downloads_list)
        list_item.setSizeHint(item_widget.sizeHint())
        self.downloads_list.addItem(list_item)
        self.downloads_list.setItemWidget(list_item, item_widget)
        task.list_item = list_item
        item_widget.remove_requested.connect(lambda: self.remove_download_item(task))
        item_widget.open_folder_requested.connect(self.open_save_folder)
        item_widget.copy_link_requested.connect(lambda: QApplication.clipboard().setText(task.url))
        item_widget.start_or_retry_requested.connect(lambda: self.download_manager.start_or_retry_task(task))

        # Connect to save history when download completes/fails/stops
        task.status_changed.connect(lambda status, t=task: self._on_task_status_changed(t, status))
        self.update_placeholder_visibility()

    def remove_download_item(self, task):
        self.download_manager.remove_task(task)
        if task.list_item:
            row = self.downloads_list.row(task.list_item)
            self.downloads_list.takeItem(row)
        self.update_placeholder_visibility()

    def clear_completed_items(self):
        tasks_to_remove = self.download_manager.get_completed_tasks()
        for task in tasks_to_remove:
            self.remove_download_item(task)
        self.status_label.setText(self.translator.translate('completed_cleared'))
        self.update_placeholder_visibility()

    def on_download_started(self):
        self.download_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.clear_button.setEnabled(False)

    def on_all_downloads_finished(self):
        self.download_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.clear_button.setEnabled(True)
        self.status_label.setText(self.translator.translate('downloads_completed'))

    def on_summary_update(self, text):
        self.summary_info.setText(text)

    def on_threads_update(self, active, maxc):
        if maxc <= 0:
            self.threads_label.setText("")
        else:
            self.threads_label.setText(f"{active}/{maxc}")

    def open_save_folder(self):
        folder = self.settings.value('save_path', '')
        if not folder or not os.path.isdir(folder):
            folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self._open_path(folder)

    def open_logs_folder(self):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        folder = os.path.join(project_root, 'logs')
        if not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)
        self._open_path(folder)

    def _open_path(self, path):
        if sys.platform.startswith('win'):
            os.startfile(path)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', path])
        else:
            subprocess.Popen(['xdg-open', path])

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls_to_add = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                file_path = url.toLocalFile()
                if file_path.lower().endswith('.txt'):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            urls_to_add.extend([line.strip() for line in f if line.strip()])
                    except Exception as e:
                        logger.error(f'Error reading dropped file {file_path}: {e}')
            else:
                urls_to_add.append(url.toString())
        if urls_to_add:
            self.download_manager.add_urls(urls_to_add)
            for u in urls_to_add:
                self._add_recent(u)
            self._rebuild_recent_buttons()

    def closeEvent(self, event):
        self.download_manager.stop_all()
        self.thread_pool.waitForDone()
        self.settings.sync()
        event.accept()

    def _get_recent(self):
        raw = self.settings.value('recent_urls', '')
        items = []
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, str) and raw:
            try:
                if raw.strip().startswith('['):
                    items = json.loads(raw)
                else:
                    items = [p for p in raw.split('|') if p]
            except Exception:
                items = []
        return items[:5]

    def _add_recent(self, url):
        items = [u for u in self._get_recent() if u != url]
        items.insert(0, url)
        items = items[:5]
        self.settings.setValue('recent_urls', '|'.join(items))
        self.settings.sync()

    def _rebuild_recent_buttons(self):
        while self.recent_buttons_layout.count():
            item = self.recent_buttons_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        recent = self._get_recent()
        if not recent:
            self.recent_container.setVisible(False)
            return
        self.recent_container.setVisible(True)
        for url in recent:
            max_len = 60
            text = url if len(url) <= max_len else f"{url[:max_len - 3]}..."
            b = QPushButton(text)
            b.setObjectName('SecondaryButton')
            b.setToolTip(url)
            b.clicked.connect(lambda _, u=url: self._add_recent_and_queue(u))
            self.recent_buttons_layout.addWidget(b)

    def _add_recent_and_queue(self, url):
        self.download_manager.add_urls([url])
        self._add_recent(url)
        self._rebuild_recent_buttons()

    def _clear_recent_history(self):
        self.settings.remove('recent_urls')
        self.settings.sync()
        self._rebuild_recent_buttons()

    def _startup_checks(self):
        """Perform startup checks for Deno and yt-dlp updates."""
        # Check if Deno is installed (for YouTube support)
        if not self.update_checker.check_deno_installed():
            self.update_checker.show_deno_warning()

        # Check for yt-dlp updates (silent mode - only notify if update available)
        self.update_checker.check_for_updates(silent=True)

    def _redownload_from_history(self, url):
        """Re-download a URL from history."""
        self.download_manager.add_urls([url])
        self._add_recent(url)
        self._rebuild_recent_buttons()
        self.page_stack.setCurrentIndex(0)  # Switch to downloads tab

    def _save_to_history(self, task):
        """Save completed task to history."""
        self.history_page.add_to_history(
            url=task.url,
            title=task.title,
            platform=task.platform,
            status=task.status.value,
            file_path=task.final_filepath
        )

    def _on_task_status_changed(self, task, status):
        """Handle task status changes - save to history when finished."""
        from .download_task import DownloadTask
        final_statuses = [DownloadTask.Status.COMPLETED, DownloadTask.Status.ERROR, DownloadTask.Status.STOPPED]
        if status in final_statuses:
            self._save_to_history(task)
