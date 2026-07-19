from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QFormLayout)
from PyQt6.QtCore import Qt

from .timecode import parse_timecode, format_timecode, validate_range


class TrimDialog(QDialog):
    """Выбор куска видео. Пустое поле — «с начала» или «до конца»."""

    def __init__(self, translator, duration=None, start=None, end=None, parent=None):
        super().__init__(parent)
        self.translator = translator
        self.duration = duration
        self.result_start = None
        self.result_end = None

        self.setWindowTitle(self.translator.translate('trim_title'))
        self.setModal(True)

        layout = QVBoxLayout(self)

        hint = QLabel(self.translator.translate('trim_hint'))
        hint.setObjectName('HintLabel')
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        self.start_input = QLineEdit(format_timecode(start))
        self.start_input.setPlaceholderText(self.translator.translate('trim_from_start'))
        self.end_input = QLineEdit(format_timecode(end))
        self.end_input.setPlaceholderText(self.translator.translate('trim_to_end'))
        form.addRow(self.translator.translate('trim_from'), self.start_input)
        form.addRow(self.translator.translate('trim_to'), self.end_input)
        layout.addLayout(form)

        if duration:
            total = QLabel(self.translator.translate('trim_duration').format(
                duration=format_timecode(duration)))
            total.setObjectName('HintLabel')
            layout.addWidget(total)

        self.error_label = QLabel()
        self.error_label.setObjectName('ErrorLabel')
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.clear_button = QPushButton(self.translator.translate('trim_clear'))
        self.clear_button.setObjectName('SecondaryButton')
        self.ok_button = QPushButton(self.translator.translate('trim_apply'))
        self.ok_button.setObjectName('ActionButton')
        self.cancel_button = QPushButton(self.translator.translate('cancel'))
        self.cancel_button.setObjectName('SecondaryButton')
        buttons.addWidget(self.clear_button)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.ok_button)
        layout.addLayout(buttons)

        self.ok_button.setDefault(True)
        self.ok_button.clicked.connect(self.on_accept)
        self.cancel_button.clicked.connect(self.reject)
        self.clear_button.clicked.connect(self.on_clear)

    def on_clear(self):
        """Снимает обрезку — видео снова качается целиком."""
        self.result_start = None
        self.result_end = None
        self.accept()

    def on_accept(self):
        try:
            start = parse_timecode(self.start_input.text())
        except ValueError:
            return self._show_error('trim_bad_start')
        try:
            end = parse_timecode(self.end_input.text())
        except ValueError:
            return self._show_error('trim_bad_end')

        problem = validate_range(start, end, self.duration)
        if problem:
            return self._show_error(problem)

        self.result_start = start
        self.result_end = end
        self.accept()

    def _show_error(self, key):
        # В самом окне, а не сообщением поверх: видно, что исправлять.
        self.error_label.setText(self.translator.translate(key))
        self.error_label.show()
