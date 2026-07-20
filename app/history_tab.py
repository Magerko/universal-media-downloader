import os
import json
import logging
import shutil
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QLabel, QHeaderView, QAbstractItemView,
    QMessageBox, QMenu, QApplication, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QDesktopServices
from PyQt6.QtCore import QUrl

from . import paths

logger = logging.getLogger(__name__)


class HistoryManager:
    """Manages download history storage in JSON file."""

    def __init__(self, data_dir):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.history_file = os.path.join(data_dir, 'history.json')
        self._history = []
        self._migrate_legacy_history()
        self._load()

    def _migrate_legacy_history(self):
        """Carry over history from the old location beside the code."""
        if os.path.exists(self.history_file):
            return
        legacy = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'history.json')
        if not os.path.isfile(legacy):
            return
        try:
            shutil.copy2(legacy, self.history_file)
            logger.info(f'Migrated download history from {legacy}')
        except Exception as e:
            logger.warning(f'Could not migrate history from {legacy}: {e}')

    def _load(self):
        """Load history from file."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self._history = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
            self._history = []

    def _save(self):
        """Save history to file."""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self._history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def add_entry(self, url, title, platform, status, file_path=None):
        """Add a new history entry."""
        entry = {
            'id': len(self._history) + 1,
            'url': url,
            'title': title,
            'platform': platform,
            'status': status,
            'file_path': file_path,
            'date': datetime.now().isoformat()
        }
        self._history.insert(0, entry)  # Add to beginning (newest first)

        # Keep only last 500 entries
        if len(self._history) > 500:
            self._history = self._history[:500]

        self._save()
        return entry

    def get_all(self):
        """Get all history entries."""
        return self._history.copy()

    def search(self, query):
        """Search history by title or URL."""
        query = query.lower()
        return [
            entry for entry in self._history
            if query in entry.get('title', '').lower() or query in entry.get('url', '').lower()
        ]

    def clear(self):
        """Clear all history."""
        self._history = []
        self._save()

    def remove_entry(self, entry_id):
        """Remove a specific entry by ID."""
        self._history = [e for e in self._history if e.get('id') != entry_id]
        self._save()


class HistoryTab(QWidget):
    """Tab for displaying download history."""

    redownload_requested = pyqtSignal(str)  # URL to re-download

    def __init__(self, translator, parent=None):
        super().__init__(parent)
        self.translator = translator
        self.parent_window = parent

        # Initialize history manager
        self.history_manager = HistoryManager(paths.data_dir())

        self.initUI()
        self.load_history()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        header = QLabel(self.translator.translate('history_title', 'Download History'))
        header.setObjectName('SectionTitle')
        header.setStyleSheet('font-size: 18px; font-weight: bold;')
        layout.addWidget(header)

        # Search and actions bar
        search_bar = QHBoxLayout()
        search_bar.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            self.translator.translate('search_history', 'Search by title or URL...')
        )
        self.search_input.setMinimumHeight(35)
        self.search_input.textChanged.connect(self.on_search)
        search_bar.addWidget(self.search_input)

        self.btn_refresh = QPushButton(self.translator.translate('refresh', 'Refresh'))
        self.btn_refresh.setObjectName('SecondaryButton')
        self.btn_refresh.clicked.connect(self.load_history)
        search_bar.addWidget(self.btn_refresh)

        self.btn_clear_all = QPushButton(self.translator.translate('clear_all_history', 'Clear All'))
        self.btn_clear_all.setObjectName('SecondaryButton')
        self.btn_clear_all.clicked.connect(self.clear_history)
        search_bar.addWidget(self.btn_clear_all)

        layout.addLayout(search_bar)

        # History table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            self.translator.translate('history_date', 'Date'),
            self.translator.translate('history_title', 'Title'),
            self.translator.translate('history_platform', 'Platform'),
            self.translator.translate('history_status', 'Status')
        ])

        # Table settings
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # Несколько строк выделяются мышью с Shift или Ctrl, действие из меню
        # применяется сразу ко всем выделенным.
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        # Column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.table)

        # Stats bar
        stats_frame = QFrame()
        stats_frame.setObjectName('StatsFrame')
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setContentsMargins(10, 5, 10, 5)

        self.stats_label = QLabel()
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch()

        layout.addWidget(stats_frame)

    def load_history(self):
        """Load and display history."""
        entries = self.history_manager.get_all()
        self._populate_table(entries)
        self._update_stats(entries)

    def _populate_table(self, entries):
        """Populate table with entries."""
        self.table.setRowCount(len(entries))

        for row, entry in enumerate(entries):
            # Date
            date_str = entry.get('date', '')
            try:
                dt = datetime.fromisoformat(date_str)
                date_display = dt.strftime('%Y-%m-%d %H:%M')
            except:
                date_display = date_str[:16] if len(date_str) > 16 else date_str

            date_item = QTableWidgetItem(date_display)
            date_item.setData(Qt.ItemDataRole.UserRole, entry)
            self.table.setItem(row, 0, date_item)

            # Title
            title = entry.get('title', 'Unknown')
            if len(title) > 60:
                title = title[:57] + '...'
            title_item = QTableWidgetItem(title)
            title_item.setToolTip(entry.get('title', ''))
            self.table.setItem(row, 1, title_item)

            # Platform
            platform_item = QTableWidgetItem(entry.get('platform', 'Unknown'))
            self.table.setItem(row, 2, platform_item)

            # Status
            status = entry.get('status', 'unknown')
            status_display = self.translator.translate(f'status_{status}', status.capitalize())
            status_item = QTableWidgetItem(status_display)

            # Color code status
            if status == 'completed':
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            elif status == 'error':
                status_item.setForeground(Qt.GlobalColor.red)
            elif status == 'stopped':
                status_item.setForeground(Qt.GlobalColor.darkYellow)

            self.table.setItem(row, 3, status_item)

    def _update_stats(self, entries):
        """Update statistics label."""
        total = len(entries)
        completed = len([e for e in entries if e.get('status') == 'completed'])
        errors = len([e for e in entries if e.get('status') == 'error'])

        self.stats_label.setText(
            self.translator.translate(
                'history_stats',
                f'Total: {total} | Completed: {completed} | Errors: {errors}'
            ).format(total=total, completed=completed, errors=errors)
            if '{total}' in self.translator.translate('history_stats', '')
            else f'Total: {total} | Completed: {completed} | Errors: {errors}'
        )

    def on_search(self, text):
        """Handle search input."""
        if text.strip():
            entries = self.history_manager.search(text)
        else:
            entries = self.history_manager.get_all()
        self._populate_table(entries)

    def selected_entries(self):
        """Записи всех выделенных строк, в порядке таблицы."""
        rows = sorted({index.row() for index in self.table.selectedIndexes()})
        entries = []
        for row in rows:
            item = self.table.item(row, 0)
            if item is not None:
                entry = item.data(Qt.ItemDataRole.UserRole)
                if entry:
                    entries.append(entry)
        return entries

    def show_context_menu(self, position):
        """Меню для выделенных строк."""
        row = self.table.rowAt(position.y())
        if row < 0:
            return
        if not self.table.item(row, 0).isSelected():
            self.table.selectRow(row)

        entries = self.selected_entries()
        if not entries:
            return
        count = len(entries)
        suffix = f' ({count})' if count > 1 else ''

        menu = QMenu(self)

        redownload_action = QAction(
            self.translator.translate('redownload', 'Re-download') + suffix, self)
        redownload_action.triggered.connect(lambda: self.redownload_many(entries))
        menu.addAction(redownload_action)

        copy_action = QAction(
            self.translator.translate('copy_link', 'Copy link') + suffix, self)
        copy_action.triggered.connect(lambda: self.copy_links(entries))
        menu.addAction(copy_action)

        # «Открыть файл» — действие для одной записи: открывать десяток видео
        # разом никто не просит.
        if count == 1:
            entry = entries[0]
            if entry.get('file_path') and os.path.exists(entry.get('file_path', '')):
                open_action = QAction(
                    self.translator.translate('open_file', 'Open file'), self)
                open_action.triggered.connect(lambda: self.open_file(entry))
                menu.addAction(open_action)

        menu.addSeparator()

        remove_action = QAction(
            self.translator.translate('remove_from_history', 'Remove from history') + suffix, self)
        remove_action.triggered.connect(lambda: self.remove_many(entries))
        menu.addAction(remove_action)

        menu.exec(self.table.viewport().mapToGlobal(position))

    def redownload_many(self, entries):
        for entry in entries:
            self.redownload(entry)

    def copy_links(self, entries):
        links = [e.get('url', '') for e in entries if e.get('url')]
        if links:
            QApplication.clipboard().setText('\n'.join(links))

    def remove_many(self, entries):
        for entry in entries:
            self.remove_entry(entry)

    def redownload(self, entry):
        """Re-download the entry."""
        url = entry.get('url')
        if url:
            self.redownload_requested.emit(url)

    def copy_link(self, entry):
        """Copy link to clipboard."""
        url = entry.get('url', '')
        QApplication.clipboard().setText(url)

    def open_file(self, entry):
        """Open the downloaded file."""
        file_path = entry.get('file_path', '')
        if file_path and os.path.exists(file_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))

    def remove_entry(self, entry):
        """Remove entry from history."""
        entry_id = entry.get('id')
        if entry_id:
            self.history_manager.remove_entry(entry_id)
            self.load_history()

    def clear_history(self):
        """Clear all history."""
        reply = QMessageBox.question(
            self,
            self.translator.translate('confirm', 'Confirm'),
            self.translator.translate('clear_history_confirm', 'Are you sure you want to clear all history?'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.history_manager.clear()
            self.load_history()

    def add_to_history(self, url, title, platform, status, file_path=None):
        """Add new entry to history (called from download manager)."""
        self.history_manager.add_entry(url, title, platform, status, file_path)
        # Refresh if tab is visible
        self.load_history()

    def update_translations(self):
        """Update UI translations."""
        self.search_input.setPlaceholderText(
            self.translator.translate('search_history', 'Search by title or URL...')
        )
        self.btn_refresh.setText(self.translator.translate('refresh', 'Refresh'))
        self.btn_clear_all.setText(self.translator.translate('clear_all_history', 'Clear All'))

        self.table.setHorizontalHeaderLabels([
            self.translator.translate('history_date', 'Date'),
            self.translator.translate('history_title', 'Title'),
            self.translator.translate('history_platform', 'Platform'),
            self.translator.translate('history_status', 'Status')
        ])

        self.load_history()
