from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QAbstractItemView)
from PyQt6.QtCore import Qt

# Кодек в ответе сайта записан как avc1.64002a или av01.0.09M.08 — читать
# такое человеку незачем, поэтому приводим к привычным названиям.
_CODEC_NAMES = (
    ('avc1', 'H.264'),
    ('h264', 'H.264'),
    ('hev1', 'H.265'),
    ('hvc1', 'H.265'),
    ('av01', 'AV1'),
    ('vp09', 'VP9'),
    ('vp9', 'VP9'),
    ('vp8', 'VP8'),
)


def codec_name(vcodec):
    value = (vcodec or '').lower()
    for prefix, name in _CODEC_NAMES:
        if value.startswith(prefix):
            return name
    return (vcodec or '').split('.')[0] or '—'


def format_size(size):
    if not size:
        return '—'
    if size >= 1024 ** 3:
        return f'{size / 1024 ** 3:.2f} ГБ'
    return f'{size / 1024 ** 2:.0f} МБ'


class FormatDialog(QDialog):
    """Выбор конкретного формата для одного видео.

    Настройки задают качество заранее и одинаково для всей платформы. Здесь
    же видно, что сайт предлагает именно для этого ролика: одно и то же
    разрешение бывает доступно в трёх кодеках с двукратной разницей в
    размере, и вслепую такой выбор не сделать.
    """

    AUTO = object()

    def __init__(self, translator, task, parent=None):
        super().__init__(parent)
        self.translator = translator
        self.task = task
        self.selected_format = None
        self.selected_label = ''

        self.setWindowTitle(self.translator.translate('format_title'))
        self.setModal(True)
        self.resize(620, 460)

        layout = QVBoxLayout(self)

        hint = QLabel(self.translator.translate('format_hint'))
        hint.setObjectName('HintLabel')
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            self.translator.translate('format_resolution'),
            self.translator.translate('format_fps'),
            self.translator.translate('format_codec'),
            self.translator.translate('format_container'),
            self.translator.translate('format_size'),
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        self.auto_button = QPushButton(self.translator.translate('format_auto'))
        self.auto_button.setObjectName('SecondaryButton')
        buttons.addWidget(self.auto_button)
        buttons.addStretch(1)
        self.cancel_button = QPushButton(self.translator.translate('cancel'))
        self.cancel_button.setObjectName('SecondaryButton')
        self.ok_button = QPushButton(self.translator.translate('format_apply'))
        self.ok_button.setObjectName('ActionButton')
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.ok_button)
        layout.addLayout(buttons)

        self.ok_button.setDefault(True)
        self.ok_button.clicked.connect(self.on_accept)
        self.cancel_button.clicked.connect(self.reject)
        self.auto_button.clicked.connect(self.on_auto)
        self.table.doubleClicked.connect(self.on_accept)

        # Только теперь: заполнение трогает кнопку «Выбрать», а она создаётся
        # ниже разметки таблицы.
        self._fill_table()

    def _fill_table(self):
        formats = self.task.formats or []
        self.table.setRowCount(len(formats))
        current = self.task.format_override
        for row, fmt in enumerate(formats):
            label = f"{fmt['height']}p"
            cells = [
                label,
                str(int(fmt['fps'])) if fmt.get('fps') else '—',
                codec_name(fmt.get('vcodec')),
                (fmt.get('ext') or '—').upper(),
                format_size(fmt.get('filesize')),
            ]
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if column:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, item)
            if current and current.startswith(str(fmt['format_id'])):
                self.table.selectRow(row)

        self.ok_button.setEnabled(bool(formats))
        if formats and not self.table.selectedItems():
            self.table.selectRow(0)

    def on_auto(self):
        """Возврат к качеству из настроек."""
        self.selected_format = None
        self.selected_label = ''
        self.accept()

    def on_accept(self):
        row = self.table.currentRow()
        formats = self.task.formats or []
        if row < 0 or row >= len(formats):
            return
        fmt = formats[row]
        selector = str(fmt['format_id'])
        if not fmt.get('has_audio'):
            # Дорожка без звука: просим yt-dlp доложить лучший звук и
            # соединить. Без этого получилось бы немое видео.
            selector = f'{selector}+bestaudio/{selector}'
        self.selected_format = selector
        self.selected_label = (f"{fmt['height']}p"
                               + (f"{int(fmt['fps'])}" if fmt.get('fps') and fmt['fps'] >= 50 else '')
                               + f" {codec_name(fmt.get('vcodec'))}")
        self.accept()
