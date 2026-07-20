import logging
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
                             QFrame, QGroupBox, QLineEdit, QApplication)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QFont, QDesktopServices, QPixmap
from .translation import Translator
from . import paths, links

logger = logging.getLogger(__name__)


class AboutTab(QWidget):
    def __init__(self, translator: Translator, parent=None):
        super().__init__(parent)
        self.translator = translator
        self.initUI()
        self.translator.language_changed.connect(self.update_translations)

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        top = QHBoxLayout()
        top.setSpacing(20)

        logo_box = QVBoxLayout()
        logo_box.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.logo = QLabel()
        logos_dir = paths.resource_path('assets', 'logos', 'app.png')
        if os.path.exists(logos_dir):
            pm = QPixmap(logos_dir)
            self.logo.setPixmap(
                pm.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        logo_box.addWidget(self.logo)

        info_box = QVBoxLayout()
        info_box.setSpacing(6)

        self.lbl_title = QLabel(self.translator.translate('app_title'))
        self.lbl_title.setObjectName('AboutTitleLabel')
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.lbl_version = QLabel(self.translator.translate('version'))
        self.lbl_version.setObjectName('AboutVersionLabel')
        self.lbl_version.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.lbl_author = QLabel(self.translator.translate('author'))
        self.lbl_author.setObjectName('AboutAuthorLabel')
        self.lbl_author.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.lbl_desc = QLabel(self.translator.translate('description'))
        self.lbl_desc.setObjectName('AboutDescriptionLabel')
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setAlignment(Qt.AlignmentFlag.AlignLeft)

        info_box.addWidget(self.lbl_title)
        info_box.addWidget(self.lbl_version)
        info_box.addWidget(self.lbl_author)
        info_box.addSpacing(8)
        info_box.addWidget(self.lbl_desc)

        top.addLayout(logo_box, 0)
        top.addLayout(info_box, 1)
        layout.addLayout(top)

        line = QFrame(self)
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(16)
        buttons_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_telegram = QPushButton(self.translator.translate('Telegram'))
        self.btn_telegram.setObjectName('AboutButton')
        self.btn_telegram.clicked.connect(self.on_telegram_clicked)

        self.btn_support = QPushButton(self.translator.translate('support_author'))
        self.btn_support.setObjectName('AboutButton')
        self.btn_support.clicked.connect(self.on_support_clicked)

        # Отдельная кнопка для гривны: карты многих украинских банков не
        # проходят на международном сервисе, и без этого пути поддержать
        # программу они просто не могут.
        self.btn_support_uah = QPushButton(
            self.translator.translate('support_author_uah', 'Поддержать (₴)'))
        self.btn_support_uah.setObjectName('AboutButton')
        self.btn_support_uah.clicked.connect(self.on_support_uah_clicked)

        buttons_layout.addWidget(self.btn_telegram)
        buttons_layout.addWidget(self.btn_support)
        buttons_layout.addWidget(self.btn_support_uah)

        layout.addLayout(buttons_layout)

        # Deno нужен не для скорости, а для полноты списка качеств: без него
        # yt-dlp не может разобрать часть форматов YouTube, и высоких качеств
        # в списке может не оказаться.
        self.deno_group = QGroupBox(
            self.translator.translate('deno_title', 'Полный список качеств YouTube'))
        deno_layout = QVBoxLayout(self.deno_group)

        self.deno_text = QLabel(self.translator.translate(
            'deno_text',
            'YouTube выдаёт часть форматов только тем программам, которые умеют '
            'выполнять его JavaScript. Загрузка работает и без этого, но в списке '
            'качеств может не хватать высоких разрешений.\n\n'
            'Чтобы они появились, установите Deno — небольшую бесплатную программу. '
            'Откройте PowerShell и вставьте строку ниже, затем перезапустите загрузчик.'))
        self.deno_text.setWordWrap(True)
        self.deno_text.setObjectName('HintLabel')
        deno_layout.addWidget(self.deno_text)

        command_row = QHBoxLayout()
        self.deno_command = QLineEdit('irm https://deno.land/install.ps1 | iex')
        self.deno_command.setReadOnly(True)
        command_row.addWidget(self.deno_command, 1)

        self.btn_copy_deno = QPushButton(
            self.translator.translate('copy_command', 'Скопировать'))
        self.btn_copy_deno.setObjectName('SecondaryButton')
        self.btn_copy_deno.clicked.connect(self.on_copy_deno)
        command_row.addWidget(self.btn_copy_deno)
        deno_layout.addLayout(command_row)

        self.deno_status = QLabel()
        self.deno_status.setObjectName('HintLabel')
        deno_layout.addWidget(self.deno_status)
        self.refresh_deno_status()

        layout.addWidget(self.deno_group)
        layout.addStretch(1)

    def refresh_deno_status(self):
        import shutil
        if shutil.which('deno'):
            self.deno_status.setText(self.translator.translate(
                'deno_found', 'Deno установлен — доступны все качества.'))
        else:
            self.deno_status.setText(self.translator.translate(
                'deno_missing', 'Deno не найден. Загрузка работает, список качеств может быть короче.'))

    def on_copy_deno(self):
        QApplication.clipboard().setText(self.deno_command.text())
        self.deno_status.setText(self.translator.translate(
            'command_copied', 'Строка скопирована — вставьте её в PowerShell.'))

    def update_translations(self):
        self.lbl_title.setText(self.translator.translate('app_title'))
        self.lbl_version.setText(self.translator.translate('version'))
        self.lbl_author.setText(self.translator.translate('author'))
        self.lbl_desc.setText(self.translator.translate('description'))
        self.btn_telegram.setText(self.translator.translate('Telegram'))
        self.btn_support.setText(self.translator.translate('support_author'))

    def on_telegram_clicked(self):
        QDesktopServices.openUrl(QUrl(links.TELEGRAM))

    def on_support_clicked(self):
        QDesktopServices.openUrl(QUrl(links.DONATE))

    def on_support_uah_clicked(self):
        QDesktopServices.openUrl(QUrl(links.DONATE_UAH))
