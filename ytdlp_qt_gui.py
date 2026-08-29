"""
yt-dlp GUI — PySide6 Version
"""

# ==================================================
# IMPORTS
# ==================================================

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
from typing import cast

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
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
# SETTINGS FILE MANAGEMENT
# ==================================================

SETTINGS_FILE = "settings.json"
DEFAULT_SETTINGS = {
    "theme": "dark",
    "download_folder": os.getcwd(),
    "allow_custom_command": False,
}


def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return DEFAULT_SETTINGS.copy()

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_SETTINGS.copy()


def save_settings(theme, download_folder, allow_custom_command):
    data = {
        "theme": theme,
        "download_folder": download_folder,
        "allow_custom_command": allow_custom_command,
    }
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


settings = load_settings()


# ==================================================
# ENSURE yt-dlp IS AVAILABLE & UPDATED
# ==================================================

yt_dlp_path = os.path.join(os.path.dirname(__file__), "yt-dlp.exe")
if not os.path.exists(yt_dlp_path):
    app = QApplication(sys.argv)
    QMessageBox.critical(
        None, "Error", "yt-dlp.exe was not found next to this script"
    )
    sys.exit(1)


# ==================================================
# FFMPEG (needed to extract audio, merge video and split chapters)
# ==================================================

bundled_ffmpeg = os.path.join(os.path.dirname(__file__), "ffmpeg.exe")
if os.path.exists(bundled_ffmpeg):
    ffmpeg_path = bundled_ffmpeg
else:
    ffmpeg_path = shutil.which("ffmpeg")
    bundled_ffmpeg = None


# ==================================================
# DOWNLOAD PROGRESS
# ==================================================

# Matches the percentage of "[download]  12.3% of 10.00MiB at 1.00MiB/s ETA 00:09"
PROGRESS_RE = re.compile(r"^\[download\]\s+(\d{1,3}(?:\.\d+)?)%")


# ==================================================
# CUSTOM COMMAND HELPER
# ==================================================


def kill_process_tree(process):
    """Kill the process and its children (a shell command spawns its own tree)."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    else:
        process.terminate()


def resolve_custom_command(text):
    """Point a hand-written `yt-dlp ...` command at the bundled executable."""
    command = text.strip()
    for name in ("yt-dlp.exe", "yt-dlp"):
        if command.lower() == name or command.lower().startswith(name + " "):
            return f'"{yt_dlp_path}"' + command[len(name) :]
    return command


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
        self.allow_custom_command = settings.get("allow_custom_command", False)
        self.process_running = False
        self.updating = False
        self.process = None
        self.stop_requested = False
        self.output_queue = queue.Queue()

        self.init_ui()
        self.apply_theme()
        self.validate()

        # Connect signals
        signal_handler.output_signal.connect(self.append_output)
        signal_handler.process_finished.connect(self.on_process_finished)

        # Start queue processor
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.process_queue)
        self.queue_timer.start(100)

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

        self.format_entry = QLineEdit()
        self.format_entry.setPlaceholderText(
            "Enter format code (e.g.: 'video_code+audio_code')"
        )
        self.format_entry.setMaximumWidth(300)
        self.format_entry.setVisible(False)
        type_layout.addWidget(self.format_entry)
        type_layout.addStretch()

        layout.addLayout(type_layout)

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
            lambda: save_settings(
                self.current_theme, self.download_folder, self.allow_custom_command
            )
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
        save_settings(
            self.current_theme, self.download_folder, self.allow_custom_command
        )
        self.validate()

    def on_type_changed(self):
        is_video = self.radio_video.isChecked()
        self.format_entry.setVisible(is_video)
        self.validate()

    def on_folder_edited(self, folder):
        self.download_folder = folder

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Download Folder", self.download_folder
        )
        if folder:
            self.download_folder = folder
            self.folder_entry.setText(folder)
            save_settings(
                self.current_theme, self.download_folder, self.allow_custom_command
            )

    def validate(self):
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
        match = PROGRESS_RE.match(line)
        if not match:
            return None

        percent = float(match.group(1))
        self.progress.setMaximum(100)
        self.progress.setValue(int(percent))
        self.progress.setFormat(line.split("]", 1)[1].strip())
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
        self.stop_requested = False
        self.reset_progress()
        self.progress.setVisible(True)
        self.validate()

        threading.Thread(
            target=self.run_process,
            args=(command,),
            kwargs={"shell": shell},
            daemon=True,
        ).start()

    def run_process(self, command, shell=False):
        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=shell,
                cwd=self.download_folder if shell else None,
            )

            for line in self.process.stdout:
                signal_handler.output_signal.emit(line)

            code = self.process.wait()

            if self.stop_requested:
                signal_handler.output_signal.emit("\n--- Stopped ---\n")
            elif code == 0:
                signal_handler.output_signal.emit("\n--- Finished ---\n")
            else:
                signal_handler.output_signal.emit(
                    f"\n--- Failed (exit code {code}) ---\n"
                )

        except OSError as error:
            signal_handler.output_signal.emit(f"\n--- Could not run: {error} ---\n")

        finally:
            self.process = None
            signal_handler.process_finished.emit()

    def stop_download(self):
        process = self.process
        if process is None or process.poll() is not None:
            return

        self.stop_requested = True
        self.stop_btn.setEnabled(False)
        self.append_output("\n--- Stopping ---\n")
        kill_process_tree(process)

    def on_process_finished(self):
        self.process_running = False
        self.updating = False
        self.progress.setVisible(False)
        self.validate()

    def start_update(self):
        """Update yt-dlp with the window already visible, but everything locked."""
        self.append_output("--- Updating yt-dlp ---\n")
        self.updating = True
        self.launch([yt_dlp_path, "--update"])

    def start_download(self):
        # Custom command: run it verbatim and ignore every other option
        custom_command = (
            self.command_entry.text().strip() if self.allow_custom_command else ""
        )
        if custom_command:
            self.append_output("\n--- Running custom command ---\n")
            self.launch(resolve_custom_command(custom_command), shell=True)
            return

        self.append_output("\n--- Download started ---\n")

        whole_playlist = self.playlist_check.isChecked()

        base = self.filename_entry.text().strip() or "%(title)s"
        # A fixed name would make every playlist entry overwrite the previous one
        if whole_playlist and self.filename_entry.text().strip():
            base = "%(playlist_index)s - " + base
        output_template = os.path.join(self.download_folder, base + ".%(ext)s")

        common_args = [
            "--newline",  # one progress line at a time, so the bar can be updated
            "--yes-playlist" if whole_playlist else "--no-playlist",
        ]
        if bundled_ffmpeg:
            common_args += ["--ffmpeg-location", bundled_ffmpeg]

        # Chapter splitting: yt-dlp keeps the full file and simply downloads it
        # normally when the video has no chapters
        split_args = []
        if self.split_chapters_check.isChecked():
            chapter_template = os.path.join(
                self.download_folder,
                "%(section_number)s - %(section_title)s.%(ext)s",
            )
            split_args = [
                "--force-keyframes-at-cut",
                "--split-chapters",
                "-o",
                "chapter:" + chapter_template,
            ]
            self.append_output(
                "Splitting by chapters (plain download if the video has none)...\n"
            )

        if ffmpeg_path is None:
            self.append_output(
                "Warning: ffmpeg was not found. Audio extraction, merging and "
                "chapter splitting need it and will fail.\n"
            )

        # Audio download
        if self.radio_audio.isChecked():
            cmd = [
                yt_dlp_path,
                *common_args,
                *split_args,
                "-x",
                "--audio-format",
                "mp3",
                "-o",
                output_template,
                self.url_entry.text(),
            ]
            self.launch(cmd)
            return

        # Video: list formats first if no format specified
        if not self.format_entry.text().strip():
            self.append_output("\nListing formats...\n")
            cmd = [yt_dlp_path, *common_args, "-F", self.url_entry.text()]
            self.launch(cmd)
            return

        # Video: actual download
        cmd = [
            yt_dlp_path,
            *common_args,
            *split_args,
            "-f",
            self.format_entry.text(),
            "--merge-output-format",
            "mp4",
            "-o",
            output_template,
            self.url_entry.text(),
        ]

        self.launch(cmd)

    def change_theme(self, theme):
        self.current_theme = theme
        self.apply_theme()
        save_settings(
            self.current_theme, self.download_folder, self.allow_custom_command
        )

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

    def process_queue(self):
        while not self.output_queue.empty():
            self.append_output(self.output_queue.get())


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
