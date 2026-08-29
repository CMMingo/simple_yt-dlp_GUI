"""
yt-dlp GUI — PySide6 front-end.

Only widgets and wiring live here. Settings, locating yt-dlp and ffmpeg,
building the commands and running them all live in ytdlp_core, so the same
logic can drive a different front-end without being copied.
"""

# ==================================================
# IMPORTS
# ==================================================

import sys
from typing import cast

import ytdlp_core as core

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# ==================================================
# SETTINGS AND EXTERNAL TOOLS (both provided by ytdlp_core)
# ==================================================

settings = core.load_settings()
tools = core.find_tools()

if tools.yt_dlp is None:
    app = QApplication(sys.argv)
    QMessageBox.critical(
        None, "Error", "yt-dlp was not found next to this script or on PATH"
    )
    sys.exit(1)


# ==================================================
# SIGNAL HANDLER (for thread-safe GUI updates)
# ==================================================


class SignalHandler(QObject):
    output_signal = Signal(str)
    process_finished = Signal()


signal_handler = SignalHandler()


# ==================================================
# MAIN APPLICATION WINDOW
# ==================================================


class YtDlpGUI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.current_theme = settings["theme"]
        self.download_folder = settings["download_folder"]
        self.allow_custom_command = settings["allow_custom_command"]
        self.process_running = False
        self.updating = False
        self.runner = core.Runner()

        self.init_ui()
        self.apply_theme()
        self.validate()

        # Connect signals
        signal_handler.output_signal.connect(self.append_output)
        signal_handler.process_finished.connect(self.on_process_finished)

    def init_ui(self):
        self.setWindowTitle("yt-dlp GUI")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(700, 500)

        # Central widget with tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Create tabs
        self.create_download_tab()
        self.create_settings_tab()

    def create_download_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)

        # Download type
        type_label = QLabel("Download type")
        layout.addWidget(type_label)

        type_layout = QHBoxLayout()
        self.radio_audio = QRadioButton("Audio (MP3)")
        self.radio_video = QRadioButton("Video (MP4)")
        self.radio_audio.setChecked(True)

        self.type_group = QButtonGroup()
        self.type_group.addButton(self.radio_audio)
        self.type_group.addButton(self.radio_video)

        type_layout.addWidget(self.radio_audio)
        type_layout.addWidget(self.radio_video)
        type_layout.addStretch()

        layout.addLayout(type_layout)

        # Video options: a quality preset, and the raw format box for advanced use
        self.video_options = QWidget()
        video_layout = QHBoxLayout()
        video_layout.setContentsMargins(0, 5, 0, 0)

        video_layout.addWidget(QLabel("Quality"))

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(core.QUALITY_LABELS)
        self.quality_combo.setMinimumWidth(200)
        self.quality_combo.setToolTip(
            "Picks the best format up to that height. A video that does not "
            "reach it is downloaded at the closest quality below."
        )
        self.quality_combo.currentIndexChanged.connect(self.validate)
        video_layout.addWidget(self.quality_combo)

        video_layout.addSpacing(20)
        video_layout.addWidget(QLabel("Advanced"))

        self.format_entry = QLineEdit()
        self.format_entry.setPlaceholderText("Format codes, e.g. 299+140")
        self.format_entry.setMaximumWidth(220)
        self.format_entry.setToolTip("Overrides the quality preset when filled in.")
        self.format_entry.textChanged.connect(self.validate)
        video_layout.addWidget(self.format_entry)
        video_layout.addStretch()

        self.video_options.setLayout(video_layout)
        self.video_options.setVisible(False)
        layout.addWidget(self.video_options)

        # Split by chapters
        self.split_chapters_check = QCheckBox(
            "Split into tracks using the chapters/timestamps of the video"
        )
        self.split_chapters_check.setToolTip(
            "If the video has no chapters, it is downloaded normally."
        )
        layout.addWidget(self.split_chapters_check)

        # Playlists
        self.playlist_check = QCheckBox("Download the whole playlist")
        self.playlist_check.setToolTip(
            "Off: only the video itself, even if the link points into a playlist."
        )
        layout.addWidget(self.playlist_check)

        # URL
        layout.addSpacing(10)
        url_label = QLabel("URL")
        layout.addWidget(url_label)

        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText("Enter video URL")
        layout.addWidget(self.url_entry)

        # Filename
        layout.addSpacing(10)
        filename_label = QLabel("Output filename (optional)")
        layout.addWidget(filename_label)

        self.filename_entry = QLineEdit()
        self.filename_entry.setPlaceholderText(
            "Leave empty to keep the video title name"
        )
        layout.addWidget(self.filename_entry)

        # Download folder
        layout.addSpacing(10)
        folder_layout = QHBoxLayout()
        folder_label = QLabel("Download folder")
        folder_layout.addWidget(folder_label)

        self.folder_entry = QLineEdit(self.download_folder)
        self.folder_entry.textChanged.connect(self.on_folder_edited)
        self.folder_entry.editingFinished.connect(
            lambda: self.save_settings()
        )
        folder_layout.addWidget(self.folder_entry)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.choose_folder)
        browse_btn.setMaximumWidth(100)
        folder_layout.addWidget(browse_btn)

        layout.addLayout(folder_layout)

        # Custom command
        layout.addSpacing(10)
        command_label = QLabel("Custom command (optional)")
        layout.addWidget(command_label)

        self.command_entry = QLineEdit()
        self.command_entry.setPlaceholderText(
            "Write a full command to run it as-is, ignoring the options above"
        )
        layout.addWidget(self.command_entry)

        self.command_label = command_label
        self.command_label.setVisible(self.allow_custom_command)
        self.command_entry.setVisible(self.allow_custom_command)

        # Progress bar
        layout.addSpacing(10)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        layout.addWidget(self.progress)
        self.reset_progress()

        # Output
        layout.addSpacing(10)
        output_label = QLabel("Output")
        layout.addWidget(output_label)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

        # Download / Stop buttons
        buttons_layout = QHBoxLayout()

        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.start_download)
        buttons_layout.addWidget(self.download_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_download)
        self.stop_btn.setMaximumWidth(100)
        buttons_layout.addWidget(self.stop_btn)

        layout.addLayout(buttons_layout)

        tab.setLayout(layout)
        self.tabs.addTab(tab, "Download")

        # Connect signals for validation
        self.radio_audio.toggled.connect(self.on_type_changed)
        self.radio_video.toggled.connect(self.on_type_changed)
        self.url_entry.textChanged.connect(self.validate)
        self.command_entry.textChanged.connect(self.validate)

    def create_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)

        theme_label = QLabel("Theme")
        layout.addWidget(theme_label)

        self.radio_dark = QRadioButton("Dark")
        self.radio_light = QRadioButton("Light")

        if self.current_theme == "dark":
            self.radio_dark.setChecked(True)
        else:
            self.radio_light.setChecked(True)

        self.radio_dark.toggled.connect(lambda: self.change_theme("dark"))
        self.radio_light.toggled.connect(lambda: self.change_theme("light"))

        layout.addWidget(self.radio_dark)
        layout.addWidget(self.radio_light)

        layout.addSpacing(20)
        command_label = QLabel("Custom command")
        layout.addWidget(command_label)

        self.allow_command_check = QCheckBox("Allow custom command")
        self.allow_command_check.setToolTip(
            "Shows a box in the Download tab that runs any command as-is."
        )
        self.allow_command_check.setChecked(self.allow_custom_command)
        self.allow_command_check.toggled.connect(self.on_allow_command_toggled)
        layout.addWidget(self.allow_command_check)

        layout.addStretch()

        tab.setLayout(layout)
        self.tabs.addTab(tab, "Settings")

    def on_allow_command_toggled(self, allowed):
        self.allow_custom_command = allowed
        self.command_label.setVisible(allowed)
        self.command_entry.setVisible(allowed)
        self.save_settings()
        self.validate()

    def on_type_changed(self):
        self.video_options.setVisible(self.radio_video.isChecked())
        self.validate()

    def save_settings(self):
        core.save_settings(
            {
                "theme": self.current_theme,
                "download_folder": self.download_folder,
                "allow_custom_command": self.allow_custom_command,
            }
        )

    def on_folder_edited(self, folder):
        self.download_folder = folder

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Download Folder", self.download_folder
        )
        if folder:
            self.download_folder = folder
            self.folder_entry.setText(folder)
            self.save_settings()

    def format_selector(self):
        """The -f value for a video download, or "" when nothing is chosen yet."""
        return (
            self.format_entry.text().strip()
            or core.QUALITY_SELECTORS[self.quality_combo.currentText()]
        )

    def validate(self):
        # Without a quality or a format code, the button lists the formats instead
        listing = self.radio_video.isChecked() and not self.format_selector()
        self.download_btn.setText("List formats" if listing else "Download")

        self.stop_btn.setEnabled(self.process_running and not self.updating)

        if self.process_running:
            self.download_btn.setEnabled(False)
            return

        has_url = bool(self.url_entry.text().strip())
        has_command = self.allow_custom_command and bool(
            self.command_entry.text().strip()
        )
        self.download_btn.setEnabled(has_url or has_command)

    def reset_progress(self):
        """Back to the indeterminate bar, until yt-dlp reports a percentage."""
        self.progress.setMaximum(0)
        self.progress.setValue(0)
        self.progress.setFormat("Working...")

    def update_progress(self, line):
        """Feed a yt-dlp output line to the bar. Returns the percentage, if any."""
        percent = core.parse_progress(line)
        if percent is None:
            return None

        self.progress.setMaximum(100)
        self.progress.setValue(int(percent))
        self.progress.setFormat(core.progress_detail(line))
        return percent

    def append_output(self, text):
        # Progress lines go to the bar instead of flooding the log
        percent = self.update_progress(text)
        if percent is not None and percent < 100:
            return

        self.output.moveCursor(self.output.textCursor().MoveOperation.End)
        self.output.insertPlainText(text)
        self.output.moveCursor(self.output.textCursor().MoveOperation.End)

    def launch(self, command, shell=False):
        """Start a process in the background and lock the UI while it runs."""
        self.process_running = True
        self.reset_progress()
        self.progress.setVisible(True)
        self.validate()

        self.runner.start(
            command,
            on_line=self.on_worker_line,
            on_finished=self.on_worker_finished,
            shell=shell,
            cwd=self.download_folder if shell else None,
        )

    # The two callbacks below run on the worker thread, so they do nothing but
    # emit signals: that is how Qt hands the values back to the GUI thread.
    def on_worker_line(self, line):
        signal_handler.output_signal.emit(line)

    def on_worker_finished(self, message):
        if message:
            signal_handler.output_signal.emit(message)
        signal_handler.process_finished.emit()

    def stop_download(self):
        if self.runner.stop():
            self.stop_btn.setEnabled(False)
            self.append_output("\n--- Stopping ---\n")

    def on_process_finished(self):
        self.process_running = False
        self.updating = False
        self.progress.setVisible(False)
        self.validate()

    def start_update(self):
        """Update yt-dlp with the window already visible, but everything locked."""
        self.append_output("--- Updating yt-dlp ---\n")
        self.updating = True
        self.launch(core.update_command(tools))

    def build_request(self):
        """Turn the state of the widgets into a plain download request."""
        return core.DownloadRequest(
            url=self.url_entry.text(),
            kind="video" if self.radio_video.isChecked() else "audio",
            selector=self.format_selector(),
            filename=self.filename_entry.text(),
            folder=self.download_folder,
            split_chapters=self.split_chapters_check.isChecked(),
            whole_playlist=self.playlist_check.isChecked(),
        )

    def start_download(self):
        # Custom command: run it verbatim and ignore every other option
        custom_command = (
            self.command_entry.text().strip() if self.allow_custom_command else ""
        )
        if custom_command:
            self.append_output("\n--- Running custom command ---\n")
            self.launch(
                core.resolve_custom_command(custom_command, tools.yt_dlp), shell=True
            )
            return

        request = self.build_request()

        if request.lists_formats:
            self.append_output("\nListing formats...\n")
        else:
            self.append_output("\n--- Download started ---\n")

            if request.split_chapters:
                self.append_output(
                    "Splitting by chapters (plain download if the video has none)...\n"
                )

            if tools.ffmpeg is None:
                self.append_output(
                    "Warning: ffmpeg was not found. Audio extraction, merging and "
                    "chapter splitting need it and will fail.\n"
                )

        self.launch(core.build_command(request, tools))

    def change_theme(self, theme):
        self.current_theme = theme
        self.apply_theme()
        self.save_settings()

    def apply_theme(self):
        if self.current_theme == "dark":
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.Base, QColor(45, 45, 45))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(30, 30, 30))
            palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.Button, QColor(74, 74, 74))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(92, 157, 237))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))

            app = cast(QApplication, QApplication.instance())
            app.setPalette(palette)

            # Additional styling for specific widgets
            self.setStyleSheet("""
                QWidget {
                    background-color: #1e1e1e;
                    color: #ffffff;
                }
                QLineEdit {
                    background-color: #2d2d2d;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 5px;
                    border-radius: 3px;
                }
                QPushButton {
                    background-color: #4a4a4a;
                    color: #ffffff;
                    border: none;
                    padding: 8px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #5a5a5a;
                }
                QPushButton:disabled {
                    background-color: #333333;
                    color: #666666;
                }
                QComboBox {
                    background-color: #2d2d2d;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 4px;
                    border-radius: 3px;
                }
                QComboBox QAbstractItemView {
                    background-color: #2d2d2d;
                    color: #ffffff;
                    selection-background-color: #5c9ded;
                    selection-color: #000000;
                }
                QTextEdit {
                    background-color: #2d2d2d;
                    color: #ffffff;
                    border: 1px solid #555555;
                }
                QProgressBar {
                    border: 1px solid #555555;
                    border-radius: 3px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #5c9ded;
                }
                QLabel {
                    color: #ffffff;
                }
                QRadioButton {
                    color: #ffffff;
                }
                QTabWidget::pane {
                    background-color: #2d2d2d;
                    border: none;
                }
                QTabBar::tab {
                    background-color: #4a4a4a;
                    color: #ffffff;
                }
                QTabBar::tab:selected {
                    background-color: #5c9ded;
                }
            """)
        else:
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(242, 242, 242))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
            palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(242, 242, 242))
            palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
            palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(92, 157, 237))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))

            app = cast(QApplication, QApplication.instance())
            app.setPalette(palette)

            self.setStyleSheet("""
                QWidget {
                    background-color: #f2f2f2;
                    color: #000000;
                }
                QLineEdit {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #cccccc;
                    padding: 5px;
                    border-radius: 3px;
                }
                QPushButton {
                    background-color: #e0e0e0;
                    color: #000000;
                    border: 1px solid #cccccc;
                    padding: 8px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #d0d0d0;
                }
                QPushButton:disabled {
                    background-color: #f0f0f0;
                    color: #999999;
                }
                QComboBox {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #cccccc;
                    padding: 4px;
                    border-radius: 3px;
                }
                QComboBox QAbstractItemView {
                    background-color: #ffffff;
                    color: #000000;
                    selection-background-color: #5c9ded;
                    selection-color: #ffffff;
                }
                QTextEdit {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #cccccc;
                }
                QProgressBar {
                    border: 1px solid #cccccc;
                    border-radius: 3px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #5c9ded;
                }
                QLabel {
                    color: #000000;
                }
                QRadioButton {
                    color: #000000;
                }
                QTabWidget::pane {
                    border: none;
                }
                QTabBar::tab {
                    background-color: #e0e0e0;
                    color: #000000;
                }
                QTabBar::tab:selected {
                    background-color: #5c9ded;
                }
            """)

# ==================================================
# APPLICATION ENTRY POINT
# ==================================================


def main():
    app = QApplication(sys.argv)
    window = YtDlpGUI()
    window.show()
    window.start_update()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
