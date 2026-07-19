import logging
import subprocess
import sys
import shutil
from packaging import version
from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool
from PyQt6.QtWidgets import QMessageBox, QPushButton

from . import paths

logger = logging.getLogger(__name__)


class UpdateSignals(QObject):
    update_available = pyqtSignal(str, str)  # current_version, latest_version
    update_completed = pyqtSignal(bool, str)  # success, message
    no_update_needed = pyqtSignal()
    check_failed = pyqtSignal(str)  # error message


class UpdateCheckWorker(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = UpdateSignals()

    def run(self):
        try:
            import yt_dlp
            current_version = yt_dlp.version.__version__

            # Get latest version from PyPI
            import requests
            response = requests.get(
                'https://pypi.org/pypi/yt-dlp/json',
                timeout=10,
                headers={'User-Agent': 'UniversalMediaDownloader/1.1'}
            )
            response.raise_for_status()
            data = response.json()
            latest_version = data['info']['version']

            logger.info(f"yt-dlp version check: current={current_version}, latest={latest_version}")

            # Compare versions
            if version.parse(latest_version) > version.parse(current_version):
                self.signals.update_available.emit(current_version, latest_version)
            else:
                self.signals.no_update_needed.emit()

        except Exception as e:
            logger.error(f"Failed to check for yt-dlp updates: {e}")
            self.signals.check_failed.emit(str(e))


class UpdateWorker(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = UpdateSignals()

    def run(self):
        try:
            # In a frozen build sys.executable is this application, not a Python
            # interpreter: running it with "-m pip" would launch a second copy of
            # the GUI. There is also nowhere useful to install to, since yt-dlp
            # lives inside the bundle.
            if getattr(sys, 'frozen', False):
                logger.info('Skipping pip update: running from a frozen build')
                self.signals.update_completed.emit(
                    False,
                    'This build ships with its own yt-dlp. Install the latest '
                    'release of the app to update it.')
                return

            python_exe = sys.executable
            result = subprocess.run(
                [python_exe, '-m', 'pip', 'install', '-U', 'yt-dlp[curl-cffi]'],
                capture_output=True,
                text=True,
                timeout=120,
                **paths.subprocess_kwargs()
            )

            if result.returncode == 0:
                logger.info("yt-dlp updated successfully")
                self.signals.update_completed.emit(True, "yt-dlp updated successfully!")
            else:
                error_msg = result.stderr or result.stdout
                logger.error(f"yt-dlp update failed: {error_msg}")
                self.signals.update_completed.emit(False, f"Update failed: {error_msg[:200]}")

        except subprocess.TimeoutExpired:
            self.signals.update_completed.emit(False, "Update timed out")
        except Exception as e:
            logger.error(f"Failed to update yt-dlp: {e}")
            self.signals.update_completed.emit(False, str(e))


class UpdateChecker(QObject):
    def __init__(self, parent, translator, settings, thread_pool):
        super().__init__(parent)
        self.parent = parent
        self.translator = translator
        self.settings = settings
        self.thread_pool = thread_pool
        self._current_version = None
        self._latest_version = None

    def check_for_updates(self, silent=False):
        """Check for yt-dlp updates. If silent=True, don't show dialog if no update."""
        self._silent = silent
        worker = UpdateCheckWorker()
        worker.signals.update_available.connect(self._on_update_available)
        worker.signals.no_update_needed.connect(self._on_no_update)
        worker.signals.check_failed.connect(self._on_check_failed)
        self.thread_pool.start(worker)

    def _on_update_available(self, current_version, latest_version):
        self._current_version = current_version
        self._latest_version = latest_version

        msg = QMessageBox(self.parent)
        msg.setWindowTitle(self.translator.translate('update_available', 'Update Available'))
        msg.setText(
            self.translator.translate(
                'ytdlp_update_message',
                f'A new version of yt-dlp is available!\n\n'
                f'Current: {current_version}\n'
                f'Latest: {latest_version}\n\n'
                f'Updating is recommended for YouTube support.'
            ).format(current=current_version, latest=latest_version)
            if '{current}' in self.translator.translate('ytdlp_update_message', '')
            else f'A new version of yt-dlp is available!\n\n'
                 f'Current: {current_version}\n'
                 f'Latest: {latest_version}\n\n'
                 f'Updating is recommended for YouTube support.'
        )
        msg.setIcon(QMessageBox.Icon.Information)

        update_btn = msg.addButton(
            self.translator.translate('update_now', 'Update Now'),
            QMessageBox.ButtonRole.AcceptRole
        )
        later_btn = msg.addButton(
            self.translator.translate('remind_later', 'Remind Later'),
            QMessageBox.ButtonRole.RejectRole
        )
        skip_btn = msg.addButton(
            self.translator.translate('skip_version', 'Skip This Version'),
            QMessageBox.ButtonRole.DestructiveRole
        )

        msg.exec()

        if msg.clickedButton() == update_btn:
            self._perform_update()
        elif msg.clickedButton() == skip_btn:
            self.settings.setValue('skipped_ytdlp_version', latest_version)
            self.settings.sync()

    def _on_no_update(self):
        if not self._silent:
            QMessageBox.information(
                self.parent,
                self.translator.translate('no_updates', 'No Updates'),
                self.translator.translate('ytdlp_up_to_date', 'yt-dlp is up to date!')
            )

    def _on_check_failed(self, error):
        if not self._silent:
            logger.warning(f"Update check failed: {error}")

    def _perform_update(self):
        # Show progress dialog
        from PyQt6.QtWidgets import QProgressDialog
        progress = QProgressDialog(
            self.translator.translate('updating_ytdlp', 'Updating yt-dlp...'),
            None, 0, 0, self.parent
        )
        progress.setWindowTitle(self.translator.translate('updating', 'Updating'))
        progress.setModal(True)
        progress.show()

        worker = UpdateWorker()
        worker.signals.update_completed.connect(
            lambda success, msg: self._on_update_completed(success, msg, progress)
        )
        self.thread_pool.start(worker)

    def _on_update_completed(self, success, message, progress_dialog):
        progress_dialog.close()

        if success:
            msg = QMessageBox(self.parent)
            msg.setWindowTitle(self.translator.translate('update_complete', 'Update Complete'))
            msg.setText(
                self.translator.translate(
                    'restart_required',
                    'yt-dlp has been updated successfully!\n\n'
                    'Please restart the application for changes to take effect.'
                )
            )
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
        else:
            QMessageBox.warning(
                self.parent,
                self.translator.translate('update_failed', 'Update Failed'),
                message
            )

    def check_deno_installed(self):
        """Check if Deno is installed and return version or None."""
        try:
            deno_path = shutil.which('deno')
            if deno_path:
                result = subprocess.run(
                    [deno_path, '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    **paths.subprocess_kwargs()
                )
                if result.returncode == 0:
                    # Parse version from output like "deno 2.1.0"
                    for line in result.stdout.split('\n'):
                        if line.startswith('deno'):
                            return line.split()[1]
            return None
        except Exception as e:
            logger.debug(f"Deno check failed: {e}")
            return None

    def show_deno_warning(self):
        """Show warning if Deno is not installed."""
        deno_version = self.check_deno_installed()
        if deno_version is None:
            msg = QMessageBox(self.parent)
            msg.setWindowTitle(self.translator.translate('deno_required', 'Deno Required'))
            msg.setText(
                self.translator.translate(
                    'deno_not_found_message',
                    'Deno JavaScript runtime is not installed.\n\n'
                    'YouTube downloads may not work properly without Deno.\n\n'
                    'Install Deno from: https://deno.com\n\n'
                    'Windows (PowerShell):\n'
                    'irm https://deno.land/install.ps1 | iex'
                )
            )
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return False
        return True
