"""Оформление по дизайн-системе семейства.

Обе темы порождаются из одного шаблона: раньше светлая и тёмная были двумя
независимыми простынями стилей и неизбежно расходились при правках.

Бирюза #4ecdc4 — родовой акцент трёх приложений, коралловый #ff6b6b — опасные
действия, шкала отступов 4/8/12/16/24/32.

Ограничения Qt, из-за которых это не обычный CSS: нет переменных, вложенности,
calc(), transition и box-shadow; размеры только в пикселях.
"""
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

DARK = {
    'bg': '#141519',
    'surface': '#1b1d21',
    'surface_alt': '#1c1e23',
    'raised': '#24272e',
    'raised_alt': '#2b2f37',
    'hover': '#2d313a',
    'border': '#3a3f49',
    'border_strong': '#4c525d',
    'text': '#e9ebee',
    'text_secondary': '#aab0ba',
    'text_muted': '#868c96',
    'accent': '#4ecdc4',
    'accent_deep': '#0d7c72',
    'accent_mid': '#0f8378',
    'accent_bg': '#12302c',
    'danger': '#ff6b6b',
    'success': '#40c463',
    'disabled_text': '#565b63',
}

LIGHT = {
    'bg': '#f4f5f7',
    'surface': '#ffffff',
    'surface_alt': '#fafbfc',
    'raised': '#ffffff',
    'raised_alt': '#eef0f3',
    'hover': '#e6e9ed',
    'border': '#d5d9e0',
    'border_strong': '#b6bcc6',
    'text': '#1b1d21',
    'text_secondary': '#4c525d',
    'text_muted': '#7c828b',
    'accent': '#0f8378',
    'accent_deep': '#0d7c72',
    'accent_mid': '#4ecdc4',
    'accent_bg': '#e2f5f2',
    'danger': '#d64545',
    'success': '#2f9e51',
    'disabled_text': '#aab0ba',
}

_TEMPLATE = """
QWidget {{
    background-color: {bg};
    color: {text};
    font-family: "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
}}
QWidget:disabled {{
    color: {disabled_text};
}}
QLabel {{
    background: transparent;
    color: {text};
}}
#MainWindow {{
    background-color: {bg};
}}

/* --- каркас окна --- */
#TopBar, #BottomBar {{
    background-color: {surface};
    border: none;
}}
#TopBar {{
    border-bottom: 1px solid {border};
}}
#BottomBar {{
    border-top: 1px solid {border};
}}
#NavBar {{
    background-color: {surface};
    border-right: 1px solid {border};
}}
#NavButton {{
    background: transparent;
    color: {text_secondary};
    border: none;
    border-radius: 8px;
    padding: 9px 14px;
    text-align: left;
    font-weight: 500;
}}
#NavButton:hover {{
    background-color: {hover};
    color: {text};
}}
#NavButton:checked {{
    background-color: {accent_bg};
    color: {accent};
    font-weight: 600;
}}
#QuickActions {{
    background: transparent;
}}

/* --- заголовки и подписи --- */
#TitleLabel {{
    font-size: 18px;
    font-weight: 600;
    color: {text};
}}
#SectionTitle {{
    font-size: 14px;
    font-weight: 600;
    color: {text};
}}
#ErrorLabel {{
    color: #ff6b6b;
}}
#UrlLabel, #StatusLabelItem, #PlaceholderLabel, #HintLabel {{
    color: {text_secondary};
    background: transparent;
}}
#StatusLabel {{
    color: {text_muted};
    background: transparent;
}}

/* --- ввод ссылки --- */
#UrlInput {{
    background-color: {surface_alt};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 9px 12px;
    selection-background-color: {accent_deep};
    selection-color: #ffffff;
}}
#UrlInput:hover {{
    border-color: {border_strong};
}}
#UrlInput:focus {{
    border-color: {accent};
}}

/* --- кнопки --- */
QPushButton {{
    background-color: {raised};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 7px 14px;
}}
QPushButton:hover {{
    background-color: {hover};
    border-color: {border_strong};
}}
QPushButton:pressed {{
    background-color: {raised_alt};
}}
#ActionButton, #AboutButton {{
    background-color: {accent_deep};
    border: 1px solid {accent_mid};
    color: #ffffff;
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: 600;
}}
#ActionButton:hover, #AboutButton:hover {{
    background-color: {accent_mid};
}}
#ActionButton:disabled {{
    background-color: {surface_alt};
    border-color: {border};
    color: {disabled_text};
}}
#SecondaryButton {{
    background-color: {raised};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 8px 16px;
}}
/* Кнопки «добавить ссылку» и «загрузить из файла» состоят из одной иконки и
   жёстко заданы как 35x35. Отступ 8px 16px оставлял внутри один пиксель
   ширины, иконка сжималась в точку, и кнопки выглядели пустыми. */
#AddUrlButton, #LoadFileButton {{
    background-color: {raised};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 0px;
}}
#AddUrlButton:hover, #LoadFileButton:hover, #SecondaryButton:hover {{
    background-color: {hover};
    border-color: {border_strong};
}}
#RemoveButton {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 3px;
    color: {text_muted};
}}
#RemoveButton:hover {{
    background-color: {danger};
    color: #ffffff;
}}

/* --- список загрузок --- */
#DownloadsList {{
    background-color: {bg};
    border: none;
    outline: none;
}}
#DownloadItem {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 10px;
}}
#EmptyListItem {{
    background: transparent;
    border: none;
}}
#EmptyCard {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 12px;
}}
#EmptyCard QWidget {{
    background: transparent;
}}
#EmptyTitle {{
    font-size: 15px;
    font-weight: 600;
    color: {text};
    background: transparent;
}}
#BulletsBox {{
    background: transparent;
}}
#RocketEmoji {{
    background: transparent;
}}
#Thumbnail {{
    background-color: {raised};
    border: 1px solid {border};
    border-radius: 6px;
}}
#StatsFrame {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 10px;
}}

/* --- прогресс --- */
#ItemProgressBar, QProgressBar {{
    background-color: {surface_alt};
    border: 1px solid {border};
    border-radius: 6px;
    height: 12px;
    text-align: center;
    color: {text_secondary};
    font-size: 11px;
}}
#ItemProgressBar::chunk, QProgressBar::chunk {{
    background-color: {accent_deep};
    border-radius: 5px;
}}

/* --- поля и списки --- */
QLineEdit, QComboBox, QSpinBox {{
    background-color: {surface_alt};
    color: {text};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: {accent_deep};
    selection-color: #ffffff;
}}
QComboBox:hover, QSpinBox:hover, QLineEdit:hover {{
    border-color: {border_strong};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border-color: {accent};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: {raised};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    selection-background-color: {accent_bg};
    selection-color: {text};
    outline: none;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background-color: {raised};
    border: none;
    width: 16px;
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled,
QPushButton:disabled, QCheckBox:disabled, QRadioButton:disabled {{
    color: {disabled_text};
    background-color: {surface};
    border-color: {border};
}}

QCheckBox, QRadioButton {{
    background: transparent;
    spacing: 8px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {border_strong};
    background-color: {surface_alt};
}}
QCheckBox::indicator {{
    border-radius: 4px;
}}
QRadioButton::indicator {{
    border-radius: 8px;
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {accent};
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {accent_deep};
    border-color: {accent};
}}

/* --- настройки --- */
QGroupBox#SettingsGroup {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 10px;
    margin-top: 14px;
    padding: 16px 12px 12px;
    font-weight: 600;
}}
QGroupBox#SettingsGroup::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {accent};
}}
QGroupBox#SettingsGroup QWidget {{
    background: transparent;
}}

/* --- история --- */
QTableWidget {{
    background-color: {surface};
    alternate-background-color: {surface_alt};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    gridline-color: {border};
    outline: none;
}}
QTableWidget::item {{
    padding: 7px 8px;
    border: none;
}}
QTableWidget::item:selected {{
    background-color: {accent_bg};
    color: {text};
}}
QHeaderView::section {{
    background-color: {raised};
    color: {text_secondary};
    border: none;
    border-bottom: 1px solid {border};
    padding: 8px;
    font-weight: 600;
}}
QHeaderView::section:hover {{
    background-color: {hover};
    color: {text};
}}

/* --- о программе --- */
#AboutTitleLabel {{
    font-size: 20px;
    font-weight: 600;
    color: {text};
}}
#AboutVersionLabel {{
    color: {accent};
    font-weight: 600;
}}
#AboutDescriptionLabel {{
    color: {text_secondary};
}}
#AboutAuthorLabel {{
    color: {text_muted};
}}

/* --- прокрутка, меню, подсказки --- */
QScrollBar:vertical {{
    background: transparent;
    width: 11px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background-color: {border};
    border-radius: 5px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {border_strong};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 11px;
}}
QScrollBar::handle:horizontal {{
    background-color: {border};
    border-radius: 5px;
    min-width: 28px;
}}
QMenu {{
    background-color: {raised};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 7px 18px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background-color: {accent_bg};
}}
QToolTip {{
    background-color: {raised};
    color: {text};
    border: 1px solid {border_strong};
    border-radius: 6px;
    padding: 6px 8px;
}}
"""


class ThemeManager:
    def __init__(self, settings: QSettings):
        self.settings = settings

    def apply_theme(self):
        app = QApplication.instance()
        if app is None:
            return
        theme = self.settings.value('theme', 'dark')
        stylesheet = self.get_dark_theme() if theme == 'dark' else self.get_light_theme()
        app.setStyleSheet(stylesheet)

    def get_dark_theme(self):
        return _TEMPLATE.format(**DARK)

    def get_light_theme(self):
        return _TEMPLATE.format(**LIGHT)
