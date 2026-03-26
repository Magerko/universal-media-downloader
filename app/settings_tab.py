import os
import logging
import subprocess
import platform
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout,
                             QPushButton, QFileDialog, QCheckBox, QComboBox,
                             QGridLayout, QFormLayout, QGroupBox, QSpinBox, QRadioButton, QWidget as QtWidget,
                             QAbstractSpinBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from .translation import Translator
from .theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class SettingsTab(QWidget):
    def __init__(self, translator: Translator, parent=None):
        super().__init__(parent)
        self.translator = translator
        self.parent_window = parent
        self.settings = parent.settings
        self.available_browsers = []
        self.detect_available_browsers()
        self.initUI()
        self.translator.language_changed.connect(self.update_translations)

    def detect_available_browsers(self):
        browsers_to_check = {
            'chrome': ['Google Chrome', 'Chrome', 'google-chrome', 'chrome'],
            'firefox': ['Firefox', 'firefox'],
            'brave': ['Brave Browser', 'Brave', 'brave-browser', 'brave'],
            'edge': ['Microsoft Edge', 'msedge', 'microsoft-edge'],
            'opera': ['Opera', 'opera'],
            'vivaldi': ['Vivaldi', 'vivaldi'],
            'safari': ['Safari', 'safari'],
            'chromium': ['Chromium', 'chromium-browser', 'chromium']
        }

        self.available_browsers = ['none']
        system = platform.system()

        for browser_key, names in browsers_to_check.items():
            if system == 'Windows':
                if self._check_browser_windows(names):
                    self.available_browsers.append(browser_key)
            elif system == 'Darwin':
                if self._check_browser_macos(names):
                    self.available_browsers.append(browser_key)
            else:
                if self._check_browser_linux(names):
                    self.available_browsers.append(browser_key)

    def _check_browser_windows(self, names):
        import winreg
        paths_to_check = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths",
        ]

        for path in paths_to_check:
            for name in names:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{path}\\{name}.exe"):
                        return True
                except:
                    pass

        common_paths = [
            os.environ.get('PROGRAMFILES', ''),
            os.environ.get('PROGRAMFILES(X86)', ''),
            os.environ.get('LOCALAPPDATA', ''),
        ]

        for base_path in common_paths:
            if not base_path:
                continue
            for name in names:
                if os.path.exists(os.path.join(base_path, name)):
                    return True
                if os.path.exists(os.path.join(base_path, f"{name}.exe")):
                    return True

        return False

    def _check_browser_macos(self, names):
        for name in names:
            if os.path.exists(f"/Applications/{name}.app"):
                return True
            try:
                result = subprocess.run(['mdfind', f'kMDItemDisplayName == "{name}.app"'],
                                        capture_output=True, text=True, timeout=2)
                if result.returncode == 0 and result.stdout.strip():
                    return True
            except:
                pass
        return False

    def _check_browser_linux(self, names):
        for name in names:
            try:
                result = subprocess.run(['which', name], capture_output=True, text=True, timeout=2)
                if result.returncode == 0 and result.stdout.strip():
                    return True
            except:
                pass
        return False

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.create_general_settings(main_layout)
        self.create_download_settings(main_layout)
        self.create_quality_settings(main_layout)

        self.update_translations()
        self.connect_signals()
        self.load_settings()

    def create_general_settings(self, layout):
        group_box = QGroupBox()
        group_box.setProperty("title_key", "general_settings")
        group_box.setObjectName('SettingsGroup')
        form_layout = QFormLayout(group_box)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem(self.translator.translate('theme_dark', 'Dark'), 'dark')
        self.theme_combo.addItem(self.translator.translate('theme_light', 'Light'), 'light')
        theme = self.settings.value('theme', 'dark')
        self.theme_combo.setCurrentIndex(0 if theme == 'dark' else 1)
        self.theme_label = QLabel()
        self.theme_label.setProperty("text_key", "select_theme")
        form_layout.addRow(self.theme_label, self.theme_combo)

        self.parallel_downloads_spin = QSpinBox()
        self.parallel_downloads_spin.setRange(1, 10)
        self.parallel_downloads_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        self.parallel_label = QLabel()
        self.parallel_label.setProperty("text_key", "parallel_downloads")
        form_layout.addRow(self.parallel_label, self.parallel_downloads_spin)

        layout.addWidget(group_box)

    def create_download_settings(self, layout):
        group_box = QGroupBox()
        group_box.setProperty("title_key", "download_settings")
        group_box.setObjectName('SettingsGroup')
        v_layout = QVBoxLayout(group_box)

        save_path_layout = QHBoxLayout()
        self.save_path_btn = QPushButton()
        self.save_path_btn.setObjectName('SecondaryButton')
        self.save_path_btn.setProperty("text_key", "select_save_folder")
        self.save_path_lbl = QLabel()
        self.save_path_lbl.setOpenExternalLinks(True)
        self.save_path_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.save_path_lbl.setWordWrap(True)
        save_path_layout.addWidget(self.save_path_btn)
        save_path_layout.addWidget(self.save_path_lbl, 1)
        v_layout.addLayout(save_path_layout)

        self.subtitles_checkbox = QCheckBox()
        self.subtitles_checkbox.setProperty("text_key", "download_subtitles")
        v_layout.addWidget(self.subtitles_checkbox)

        self.cookies_checkbox = QCheckBox()
        self.cookies_checkbox.setProperty("text_key", "use_cookies")
        v_layout.addWidget(self.cookies_checkbox)

        self.cookies_options_widget = QWidget()
        cookies_layout = QVBoxLayout(self.cookies_options_widget)
        cookies_layout.setContentsMargins(20, 0, 0, 0)
        self.rb_cookie_file = QRadioButton()
        self.rb_cookie_file.setProperty("text_key", "cookie_file")
        self.rb_cookie_browser = QRadioButton()
        self.rb_cookie_browser.setProperty("text_key", "cookie_browser")

        self.cookie_file_widget = QWidget()
        file_layout = QHBoxLayout(self.cookie_file_widget)
        file_layout.setContentsMargins(0, 0, 0, 0)
        self.cookies_btn = QPushButton()
        self.cookies_btn.setObjectName('SecondaryButton')
        self.cookies_btn.setProperty("text_key", "select_cookies_file")
        self.cookies_lbl = QLabel()
        self.cookies_lbl.setOpenExternalLinks(True)
        self.cookies_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        file_layout.addWidget(self.cookies_btn)
        file_layout.addWidget(self.cookies_lbl, 1)

        self.cookie_browser_combo = QComboBox()
        for browser in self.available_browsers:
            display_name = browser.capitalize() if browser != 'none' else 'None'
            self.cookie_browser_combo.addItem(display_name, browser)

        cookies_layout.addWidget(self.rb_cookie_file)
        cookies_layout.addWidget(self.cookie_file_widget)
        cookies_layout.addWidget(self.rb_cookie_browser)
        cookies_layout.addWidget(self.cookie_browser_combo)
        v_layout.addWidget(self.cookies_options_widget)

        layout.addWidget(group_box)

    def create_quality_settings(self, layout):
        group_box = QGroupBox()
        group_box.setProperty("title_key", "quality_settings")
        group_box.setObjectName('SettingsGroup')
        grid_layout = QGridLayout(group_box)
        grid_layout.setSpacing(10)

        platforms = ['YouTube', 'RuTube', 'TikTok', 'Instagram', 'VK', 'PornHub', 'Facebook', 'X (Twitter)',
                     'Kinopoisk', 'Twitch', 'Kick']
        self.quality_combos = {}

        row, col = 0, 0
        for platform in platforms:
            platform_label = self._platform_label(platform)
            combo = QComboBox()
            self.quality_combos[platform] = combo

            grid_layout.addWidget(platform_label, row, col * 2)
            grid_layout.addWidget(combo, row, col * 2 + 1)

            col += 1
            if col > 2:
                col = 0
                row += 1

        layout.addWidget(group_box)

    def _platform_label(self, name):
        w = QtWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        pic = QLabel()
        logos_dir = os.path.join(os.path.dirname(__file__), '..', 'assets', 'logos')
        fname_map = {
            'YouTube': 'youtube.png',
            'RuTube': 'rutube.png',
            'TikTok': 'tiktok.png',
            'Instagram': 'instagram.png',
            'VK': 'vk.png',
            'PornHub': 'pornhub.png',
            'Facebook': 'facebook.png',
            'X (Twitter)': 'x.png',
            'Kinopoisk': 'kinopoisk.png',
            'Twitch': 'twitch.png',
            'Kick': 'kick.png'
        }
        fpath = os.path.join(logos_dir, fname_map.get(name, ''))
        if os.path.exists(fpath):
            pm = QPixmap(fpath)
            if not pm.isNull():
                pic.setPixmap(pm.scaled(
                    16, 16,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
        lbl = QLabel(f"{name}:")
        h.addWidget(pic)
        h.addWidget(lbl)
        h.addStretch(1)
        return w

    def connect_signals(self):
        self.theme_combo.currentIndexChanged.connect(self.on_setting_changed)
        self.parallel_downloads_spin.valueChanged.connect(self.on_setting_changed)
        self.save_path_btn.clicked.connect(self.on_select_save_path)
        self.subtitles_checkbox.stateChanged.connect(self.on_setting_changed)
        self.cookies_checkbox.stateChanged.connect(self.on_setting_changed)
        self.rb_cookie_file.toggled.connect(self.on_setting_changed)
        self.cookies_btn.clicked.connect(self.on_select_cookies_file)
        self.cookie_browser_combo.currentIndexChanged.connect(self.on_setting_changed)
        for combo in self.quality_combos.values():
            combo.currentIndexChanged.connect(self.on_setting_changed)

    def disconnect_signals(self):
        self.theme_combo.currentIndexChanged.disconnect()
        self.parallel_downloads_spin.valueChanged.disconnect()
        self.save_path_btn.clicked.disconnect()
        self.subtitles_checkbox.stateChanged.disconnect()
        self.cookies_checkbox.stateChanged.disconnect()
        self.rb_cookie_file.toggled.disconnect()
        self.cookies_btn.clicked.disconnect()
        self.cookie_browser_combo.currentIndexChanged.disconnect()
        for combo in self.quality_combos.values():
            combo.currentIndexChanged.disconnect()

    def populate_youtube_qualities(self, cbox):
        cbox.addItem(self.translator.translate('video_best_quality'), 'bestvideo+bestaudio/best')
        cbox.addItem(self.translator.translate('audio_only'), 'bestaudio/best')
        cbox.addItem('144p', 'bestvideo[height<=144]+bestaudio/best')
        cbox.addItem('240p', 'bestvideo[height<=240]+bestaudio/best')
        cbox.addItem('360p', 'bestvideo[height<=360]+bestaudio/best')
        cbox.addItem('480p', 'bestvideo[height<=480]+bestaudio/best')
        cbox.addItem('720p (HD)', 'bestvideo[height<=720]+bestaudio/best')
        cbox.addItem('1080p (Full HD)', 'bestvideo[height<=1080]+bestaudio/best')
        cbox.addItem('1440p (2K)', 'bestvideo[height<=1440]+bestaudio/best')
        cbox.addItem('2160p (4K)', 'bestvideo[height<=2160]+bestaudio/best')

    def populate_generic_qualities(self, cbox):
        cbox.addItem(self.translator.translate('best_quality'), 'best')
        cbox.addItem(self.translator.translate('audio_only'), 'bestaudio/best')
        cbox.addItem(self.translator.translate('video_only'), 'video_only_stripped')
        cbox.addItem(self.translator.translate('worst_quality'), 'worst')

    def update_translations(self):
        widgets_with_keys = self.findChildren(QWidget)
        for widget in widgets_with_keys:
            key = widget.property("text_key")
            if key:
                if isinstance(widget, (QPushButton, QCheckBox, QRadioButton, QLabel)):
                    widget.setText(self.translator.translate(key))

            title_key = widget.property("title_key")
            if title_key:
                if isinstance(widget, QGroupBox):
                    widget.setTitle(self.translator.translate(title_key))

        for platform, combo in self.quality_combos.items():
            current_data = combo.currentData()
            combo.clear()
            if platform == 'YouTube':
                self.populate_youtube_qualities(combo)
            else:
                self.populate_generic_qualities(combo)
            self.set_combo_by_data(combo, current_data)

        save_path = self.settings.value('save_path', '')
        if save_path:
            self.save_path_lbl.setText(f'<a href="file:///{save_path}">{save_path}</a>')
        else:
            self.save_path_lbl.setText(self.translator.translate('folder_not_selected'))
        cookies_path = self.settings.value('cookies_path', '')
        if cookies_path:
            self.cookies_lbl.setText(f'<a href="file:///{cookies_path}">{cookies_path}</a>')
        else:
            self.cookies_lbl.setText(self.translator.translate('file_not_selected'))

    def load_settings(self):
        self.disconnect_signals()

        theme = self.settings.value('theme', 'dark')
        self.set_combo_by_data(self.theme_combo, theme)

        self.parallel_downloads_spin.setValue(int(self.settings.value('parallel_downloads', 2)))

        save_path = self.settings.value('save_path', '')
        if save_path:
            self.save_path_lbl.setText(f'<a href="file:///{save_path}">{save_path}</a>')
        else:
            self.save_path_lbl.setText(self.translator.translate('folder_not_selected'))

        self.subtitles_checkbox.setChecked(self.settings.value('subtitles_enabled', False, type=bool))
        self.cookies_checkbox.setChecked(self.settings.value('use_cookies', False, type=bool))

        cookie_source_type = self.settings.value('cookie_source_type', 'file')
        self.rb_cookie_file.setChecked(cookie_source_type == 'file')
        self.rb_cookie_browser.setChecked(cookie_source_type == 'browser')

        cookies_path = self.settings.value('cookies_path', '')
        if cookies_path:
            self.cookies_lbl.setText(f'<a href="file:///{cookies_path}">{cookies_path}</a>')
        else:
            self.cookies_lbl.setText(self.translator.translate('file_not_selected'))

        cookie_browser = self.settings.value('cookie_browser', 'none')
        idx = self.cookie_browser_combo.findData(cookie_browser)
        if idx >= 0:
            self.cookie_browser_combo.setCurrentIndex(idx)
        else:
            self.cookie_browser_combo.setCurrentIndex(0)

        self.update_cookie_widgets_state()

        for platform, combo in self.quality_combos.items():
            key = f"quality_{platform.lower().replace(' ', '_').replace('(', '').replace(')', '')}"
            default_quality = 'bestvideo+bestaudio/best' if platform == 'YouTube' else 'best'
            quality = self.settings.value(key, default_quality)
            self.set_combo_by_data(combo, quality)

        self.connect_signals()

    def on_setting_changed(self):
        self.settings.setValue('theme', self.theme_combo.currentData())
        self.settings.setValue('parallel_downloads', self.parallel_downloads_spin.value())
        self.parent_window.thread_pool.setMaxThreadCount(self.parallel_downloads_spin.value())

        self.settings.setValue('subtitles_enabled', self.subtitles_checkbox.isChecked())
        self.settings.setValue('use_cookies', self.cookies_checkbox.isChecked())

        if self.rb_cookie_file.isChecked():
            self.settings.setValue('cookie_source_type', 'file')
            self.settings.setValue('cookie_source', 'file')
        else:
            self.settings.setValue('cookie_source_type', 'browser')
            browser_value = self.cookie_browser_combo.currentData()
            self.settings.setValue('cookie_source', browser_value)
            self.settings.setValue('cookie_browser', browser_value)

        for platform, combo in self.quality_combos.items():
            key = f"quality_{platform.lower().replace(' ', '_').replace('(', '').replace(')', '')}"
            self.settings.setValue(key, combo.currentData())

        self.settings.sync()
        self.update_cookie_widgets_state()

        if self.sender() == self.theme_combo:
            ThemeManager(self.settings).apply_theme()
            idx = self.theme_combo.currentIndex()
            self.parent_window.quick_theme_combo.blockSignals(True)
            self.parent_window.quick_theme_combo.setCurrentIndex(idx)
            self.parent_window.quick_theme_combo.blockSignals(False)

    def update_cookie_widgets_state(self):
        use_cookies = self.cookies_checkbox.isChecked()
        self.cookies_options_widget.setEnabled(use_cookies)
        if use_cookies:
            is_file = self.rb_cookie_file.isChecked()
            self.cookie_file_widget.setEnabled(is_file)
            self.cookie_browser_combo.setEnabled(not is_file)

    def on_select_save_path(self):
        folder = QFileDialog.getExistingDirectory(self, self.translator.translate('select_save_folder'))
        if folder:
            self.save_path_lbl.setText(f'<a href="file:///{folder}">{folder}</a>')
            self.settings.setValue('save_path', folder)
            self.settings.sync()

    def on_select_cookies_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, self.translator.translate('select_cookies_file'), '',
                                                   'Text Files (*.txt *.cookies);;All Files (*)')
        if file_path:
            self.cookies_lbl.setText(f'<a href="file:///{file_path}">{file_path}</a>')
            self.settings.setValue('cookies_path', file_path)
            self.settings.sync()

    def set_combo_by_data(self, combo, data):
        index = combo.findData(data)
        if index != -1:
            combo.setCurrentIndex(index)