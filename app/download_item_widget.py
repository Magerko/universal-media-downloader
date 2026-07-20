import os
import logging
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel,
                             QProgressBar, QPushButton, QMenu, QFrame)
from PyQt6.QtGui import QPixmap, QIcon, QAction
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from .download_task import DownloadTask
from .timecode import format_timecode
from . import paths


def _current_theme() -> str:
    """Тема из настроек: карточка создаётся вне окна и его настроек не видит."""
    from PyQt6.QtCore import QSettings
    return QSettings('Magerko', 'UniversalMediaDownloader').value('theme', 'dark')

logger = logging.getLogger(__name__)


class DownloadItemWidget(QWidget):
    remove_requested = pyqtSignal()
    open_folder_requested = pyqtSignal()
    copy_link_requested = pyqtSignal()
    start_or_retry_requested = pyqtSignal()
    trim_requested = pyqtSignal()
    format_requested = pyqtSignal()
    selection_requested = pyqtSignal(object)

    def __init__(self, task: DownloadTask, translator):
        super().__init__()
        self.task = task
        self.translator = translator
        self.setObjectName('DownloadItem')
        self.initUI()
        self.connect_signals()
        self.update_ui()

    def initUI(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 10, 10, 10)
        main_layout.setSpacing(15)

        # Состояние несут три признака сразу: цвет рельса, иконка и вид
        # полосы — список читается взглядом.
        self.rail = QFrame()
        self.rail.setFixedWidth(4)
        self.rail.setObjectName('StateRail')
        main_layout.addWidget(self.rail)

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(128, 72)
        self.thumbnail_label.setObjectName('Thumbnail')
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setText("...")
        main_layout.addWidget(self.thumbnail_label)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)

        self.title_label = QLabel(self.task.title)
        self.title_label.setObjectName('TitleLabel')
        self.title_label.setWordWrap(True)

        self.url_label = QLabel(self.task.url)
        self.url_label.setObjectName('UrlLabel')
        self.url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setObjectName('ItemProgressBar')

        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self.state_icon = QLabel()
        self.state_icon.setFixedSize(16, 16)
        status_row.addWidget(self.state_icon)

        self.status_label = QLabel()
        self.status_label.setObjectName('StatusLabelItem')
        status_row.addWidget(self.status_label, 1)

        # На виду, а не только в меню по правой кнопке: по карточке в
        # загрузчике правой кнопкой почти никто не жмёт.
        self.quality_button = QPushButton(self.translator.translate('card_quality'))
        self.quality_button.setObjectName('CardButton')
        self.quality_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.trim_button = QPushButton(self.translator.translate('card_trim'))
        self.trim_button.setObjectName('CardButton')
        self.trim_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_button = QPushButton(self.translator.translate('card_open'))
        self.open_button.setObjectName('CardButton')
        self.open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        for button in (self.quality_button, self.trim_button, self.open_button):
            status_row.addWidget(button)

        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.url_label)
        info_layout.addWidget(self.progress_bar)
        info_layout.addLayout(status_row)

        main_layout.addLayout(info_layout, 1)

        self.remove_button = QPushButton()
        self.remove_button.setFixedSize(24, 24)
        self.remove_button.setIconSize(QSize(14, 14))
        self.remove_button.setObjectName('RemoveButton')
        self.remove_button.setToolTip(self.translator.translate('status_stopped'))

        close_icon_path = paths.icon_path('close', _current_theme())
        if os.path.exists(close_icon_path):
            icon = QIcon(close_icon_path)
            if not icon.isNull():
                self.remove_button.setIcon(icon)
            else:
                logger.warning(f"Не удалось загрузить иконку, хотя файл существует: {close_icon_path}")
                self.remove_button.setText('X')
        else:
            logger.warning(f"Файл иконки не найден: {close_icon_path}")
            self.remove_button.setText('X')

        main_layout.addWidget(self.remove_button)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def mousePressEvent(self, event):
        """Передаёт клик списку, чтобы работало выделение с Shift и Ctrl.

        Карточка закрывает собой элемент списка и забирает все нажатия себе,
        поэтому без этого выделить несколько загрузок было нельзя.
        """
        self.selection_requested.emit(event.modifiers())
        super().mousePressEvent(event)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        act_open = QAction(self.translator.translate('open_save_folder'), self)
        act_copy = QAction(self.translator.translate('copy_link'), self)
        act_start = QAction(self.translator.translate('download_this_video'), self)
        act_trim = QAction(self.translator.translate('trim_menu'), self)
        act_format = QAction(self.translator.translate('format_menu'), self)
        act_remove = QAction(self.translator.translate('remove_from_list'), self)

        act_open.triggered.connect(self.open_folder_requested.emit)
        act_copy.triggered.connect(self.copy_link_requested.emit)
        act_start.triggered.connect(self.start_or_retry_requested.emit)
        act_trim.triggered.connect(self.trim_requested.emit)
        act_format.triggered.connect(self.format_requested.emit)
        act_remove.triggered.connect(self.remove_requested.emit)

        is_startable = self.task.status in (
            DownloadTask.Status.PENDING, DownloadTask.Status.ERROR, DownloadTask.Status.STOPPED)
        act_start.setEnabled(is_startable)
        # Качающееся видео уже режется по прежним меткам.
        act_trim.setEnabled(is_startable)
        # Форматы приходят вместе со сведениями о видео.
        act_format.setEnabled(is_startable and bool(self.task.formats))

        is_completed = self.task.status == DownloadTask.Status.COMPLETED
        act_open.setEnabled(is_completed)

        menu.addAction(act_start)
        menu.addAction(act_format)
        menu.addAction(act_trim)
        menu.addAction(act_open)
        menu.addAction(act_copy)
        menu.addSeparator()
        menu.addAction(act_remove)
        menu.exec(self.mapToGlobal(pos))

    def connect_signals(self):
        self.task.info_updated.connect(self.update_ui)
        self.task.status_changed.connect(self.update_ui)
        self.task.progress_updated.connect(self.on_progress_update)
        self.task.thumbnail_loaded.connect(self.set_thumbnail)
        self.remove_button.clicked.connect(self.remove_requested.emit)
        self.quality_button.clicked.connect(self.format_requested.emit)
        self.trim_button.clicked.connect(self.trim_requested.emit)
        self.open_button.clicked.connect(self.open_folder_requested.emit)

    def on_progress_update(self, percent, text):
        self.progress_bar.setValue(percent)
        self.status_label.setText(text)

    def set_thumbnail(self, pixmap):
        scaled_pixmap = pixmap.scaled(self.thumbnail_label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
        self.thumbnail_label.setPixmap(scaled_pixmap)

    # Три семьи цветов, чтобы список сортировался взглядом: идёт работа —
    # бирюза, ждёт очереди — синий, закончилось — зелёный, красный или
    # приглушённый. Иконка и вид полосы подтверждают то же самое.
    STATE_LOOK = {
        DownloadTask.Status.FETCHING_INFO: ('#5aa9ff', 'link', 'busy'),
        DownloadTask.Status.PENDING: ('#5aa9ff', 'history', 'idle'),
        DownloadTask.Status.DOWNLOADING: ('#4ecdc4', 'download', 'progress'),
        # У обработки есть настоящий счёт — бегущая полоса противоречила бы
        # подписи «осталось 1 мин 20 сек».
        DownloadTask.Status.PROCESSING: ('#4ecdc4', 'settings', 'progress'),
        DownloadTask.Status.COMPLETED: ('#40c463', 'check-circle', 'full'),
        DownloadTask.Status.ERROR: ('#ff6b6b', 'error', 'hidden'),
        DownloadTask.Status.STOPPED: ('#565b63', 'pause', 'frozen'),
    }

    def _apply_state_look(self, status):
        colour, icon_name, bar = self.STATE_LOOK.get(
            status, ('#565b63', 'file', 'hidden'))

        self.rail.setStyleSheet(
            f'background-color: {colour}; border-radius: 2px;')
        self.state_icon.setPixmap(
            QIcon(paths.icon_path(icon_name, _current_theme())).pixmap(QSize(16, 16)))

        if bar == 'hidden':
            self.progress_bar.setVisible(False)
            return

        self.progress_bar.setVisible(True)
        if bar == 'busy':
            # Бегунок без конкретного значения: работа идёт, но доля неизвестна.
            self.progress_bar.setRange(0, 0)
        elif bar == 'full':
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
        elif bar == 'idle':
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
        else:
            # progress и frozen: значение приходит извне, у frozen оно замирает.
            self.progress_bar.setRange(0, 100)

        self.progress_bar.setStyleSheet(
            f'QProgressBar::chunk {{ background-color: {colour}; border-radius: 3px; }}')

    def _clip_badge(self):
        """Подпись о выбранном куске, чтобы обрезка не была невидимой."""
        if not self.task.has_clip:
            return ''
        start = (format_timecode(self.task.clip_start) if self.task.clip_start is not None
                 else self.translator.translate('trim_from_start'))
        end = (format_timecode(self.task.clip_end) if self.task.clip_end is not None
               else self.translator.translate('trim_to_end'))
        return self.translator.translate('trim_badge').format(start=start, end=end)

    def _subtitle(self):
        """Строка под названием: площадка и длительность, пока не известны —
        ссылка."""
        parts = []
        if self.task.platform and self.task.platform != 'Unknown':
            parts.append(self.task.platform)
        if self.task.duration:
            parts.append(format_timecode(self.task.duration))
        return '  ·  '.join(parts) if parts else self.task.url

    def update_ui(self):
        self.url_label.setText(self._subtitle())
        self.url_label.setToolTip(self.task.url)
        marks = [m for m in (self.task.format_label, self._clip_badge()) if m]
        suffix = '  ·  '.join(marks)
        self.title_label.setText(f'{self.task.title}  ·  {suffix}' if suffix else self.task.title)
        status = self.task.status
        self._apply_state_look(status)

        # Прячем, а не гасим: неактивная кнопка заставляет гадать, почему
        # она не нажимается.
        before_start = status in (DownloadTask.Status.PENDING,
                                  DownloadTask.Status.ERROR,
                                  DownloadTask.Status.STOPPED)
        self.quality_button.setVisible(before_start and bool(self.task.formats))
        self.trim_button.setVisible(before_start)
        self.open_button.setVisible(status == DownloadTask.Status.COMPLETED)

        status_text_map = {
            DownloadTask.Status.PENDING: self.translator.translate('status_pending'),
            DownloadTask.Status.FETCHING_INFO: self.translator.translate('status_fetching_info'),
            DownloadTask.Status.DOWNLOADING: self.translator.translate('status_downloading'),
            DownloadTask.Status.PROCESSING: self.translator.translate('status_processing'),
            DownloadTask.Status.COMPLETED: f"{self.translator.translate('status_completed')} ✓",
            DownloadTask.Status.ERROR: f"{self.translator.translate('status_error')}: {self.task.error_message}",
            DownloadTask.Status.STOPPED: self.translator.translate('status_stopped'),
        }
        self.status_label.setText(status_text_map.get(status, ""))

        self.setProperty('status', status.value)
        self.style().polish(self)
