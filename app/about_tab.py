import logging
import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QFont, QDesktopServices, QPixmap
from .translation import Translator
from . import paths

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

        buttons_layout.addWidget(self.btn_telegram)
        buttons_layout.addWidget(self.btn_support)

        layout.addLayout(buttons_layout)
        layout.addStretch(1)

    def update_translations(self):
        self.lbl_title.setText(self.translator.translate('app_title'))
        self.lbl_version.setText(self.translator.translate('version'))
        self.lbl_author.setText(self.translator.translate('author'))
        self.lbl_desc.setText(self.translator.translate('description'))
        self.btn_telegram.setText(self.translator.translate('Telegram'))
        self.btn_support.setText(self.translator.translate('support_author'))

    def on_telegram_clicked(self):
        QDesktopServices.openUrl(QUrl('https://t.me/mcodeg'))

    def on_support_clicked(self):
        QDesktopServices.openUrl(QUrl('https://donatepay.eu/don/34347'))
