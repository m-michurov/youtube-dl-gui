import sys
from pathlib import Path
from typing import Sequence, Any, Callable
import random
import subprocess

from PyQt6.QtCore import (
    Qt,
    QRegularExpression,
    QRunnable,
    pyqtSignal as Signal,
    QThreadPool,
    pyqtSlot as Slot, QObject
)
from PyQt6.QtGui import QIcon, QRegularExpressionValidator
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QLabel,
    QLineEdit,
    QFormLayout,
    QWidget,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QVBoxLayout,
    QErrorMessage
)
import qt_material

from core import VIDEO_URL_REGEX_STR, get_video_id, download
from preferences import Preferences


def show_file_in_explorer(path: Path) -> None:
    subprocess.Popen(rf'explorer /select,"{path}"')


class BackgroundWorkProgress(QObject):
    finished = Signal([], [Exception])


class BackgroundWorker(QRunnable):
    def __init__(self, target: Callable[[], Any | None]) -> None:
        super().__init__()
        self._target = target

        self.progress = BackgroundWorkProgress()

    def run(self) -> None:
        try:
            self._target()
            self.progress.finished.emit()
        except Exception as e:
            self.progress.finished[Exception].emit(e)


class MainWindow(QMainWindow):
    status_changed = Signal(str)

    def __init__(self, preferences: Preferences) -> None:
        super().__init__()

        self._setup_ui()
        self.reset_status()

        self.video_id: str | None = None

        key_download_folder = 'download_folder'
        self.download_folder_input.setText(preferences.get(key_download_folder, str(Path.cwd())))
        self.download_folder_input.textChanged[str].connect(lambda value: preferences.set(key_download_folder, value))

    def _setup_ui(self) -> None:
        self.setWindowIcon(QIcon('icon.ico'))
        self.setWindowTitle('YouTube DL')

        root = QWidget(self)
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)

        input_form = QFormLayout()

        self.url_input = QLineEdit()
        self.url_input.setValidator(QRegularExpressionValidator(QRegularExpression(VIDEO_URL_REGEX_STR)))
        self.url_input.textChanged[str].connect(self.url_text_changed)
        input_form.addRow('URL', self.url_input)

        folder_input_widget = QWidget()
        folder_input_layout = QHBoxLayout(folder_input_widget)
        folder_input_layout.setContentsMargins(0, 0, 0, 0)

        self.download_folder_input = QLineEdit()
        folder_input_layout.addWidget(self.download_folder_input)

        self.browse_button = QPushButton('Browse')
        self.browse_button.clicked.connect(self.browse_button_pressed)
        folder_input_layout.addWidget(self.browse_button)

        input_form.addRow('Save to', folder_input_widget)

        root_layout.addLayout(input_form)

        self.status_label = QLabel('Status')
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.status_changed[str].connect(self.status_label.setText)
        root_layout.addWidget(self.status_label)

        self.download_button = QPushButton('Download')
        self.download_button.clicked.connect(self.download_button_pressed)
        root_layout.addWidget(self.download_button)

        self.input_controls = (
            self.url_input,
            self.download_folder_input,
            self.browse_button,
            self.download_button
        )

    def _set_input_enabled(self, enabled: bool) -> None:
        for control in self.input_controls:
            control.setEnabled(enabled)

    @Slot()
    def reset_status(self) -> None:
        self.url_text_changed(self.url_input.text())

    @Slot(str)
    def url_text_changed(self, url: str) -> None:
        self.video_id = get_video_id(url)
        can_download = self.video_id is not None

        self.download_button.setEnabled(can_download)

        status = f'Can download' if can_download \
            else 'No URL' if not url or url.isspace() \
            else 'Invalid URL'
        self.status_label.setText(status)

    @Slot()
    def browse_button_pressed(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            parent=self,
            caption='Select directory',
            directory=self.download_folder_input.text()
        )

        if not folder:
            return

        self.download_folder_input.setText(folder)

    @Slot()
    def download_button_pressed(self) -> None:
        self._set_input_enabled(enabled=False)

        def download_and_show_file() -> None:
            mp3_path = download(
                video_id=self.video_id,
                download_folder=Path(self.download_folder_input.text()),
                status_changed=lambda new_status: self.status_changed[str].emit(new_status)
            )
            show_file_in_explorer(mp3_path)

        worker = BackgroundWorker(target=download_and_show_file)

        worker.progress.finished[Exception].connect(self.download_failed)
        worker.progress.finished[Exception].connect(self.reset_status)
        worker.progress.finished[Exception].connect(self.enable_input)

        worker.progress.finished.connect(self.enable_input)

        QThreadPool.globalInstance().start(worker)

    @Slot(Exception)
    def download_failed(self, e: Exception) -> None:
        error_dialog = QErrorMessage(parent=self)
        error_dialog.setWindowTitle('Error occurred')
        error_dialog.showMessage(str(e))

    @Slot()
    def enable_input(self) -> None:
        self._set_input_enabled(enabled=True)


def apply_random_theme(app: QApplication) -> None:
    themes = [
        'light_teal.xml',
        'light_red.xml',
        'light_purple_500.xml',
        'light_lightgreen.xml',
        'light_cyan_500.xml',
        'light_blue.xml',
    ]
    theme_name = random.choice(list(set(themes).intersection(set(qt_material.list_themes()))))
    qt_material.apply_stylesheet(
        app=app,
        theme=theme_name,
        invert_secondary='light' in theme_name
    )


def main(args: Sequence[str]) -> int:
    app = QApplication(args)

    apply_random_theme(app)

    window = MainWindow(Preferences(Path('preferences.json')))
    window.show()
    window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
    window.activateWindow()

    return app.exec()


if __name__ == '__main__':
    sys.exit(main(sys.argv))
