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
from translations import LANGUAGES, QUALITY_LABEL_KEYS, tr

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
    _lang = settings.get("language", "en")
    QMessageBox.critical(
        None, tr(_lang, "error_title"), tr(_lang, "error_ytdlp_not_found")
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
        self.allow_advanced_features = settings["allow_advanced_features"]
        self.language = settings.get("language", "en")
        self.process_running = False
        self.updating = False
        self.runner = core.Runner()
        self.cleanup_folder = None
        self.cleanup_before = None
        self._quality_mode_is_advanced = None  # tracked by update_quality_options()

        self.init_ui()
        self.apply_advanced_mode()
        self.apply_theme()
        self.retranslate_ui()
        self.validate()

        # Connect signals
        signal_handler.output_signal.connect(self.append_output)
        signal_handler.process_finished.connect(self.on_process_finished)

    def tr_text(self, key, **kwargs):
        return tr(self.language, key, **kwargs)

    def init_ui(self):
        self.setWindowTitle("yt-dlp GUI")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(700, 500)

        # Missing-dependency banner, shown above the tabs when needed
        self.warning_banner = QLabel()
        self.warning_banner.setObjectName("warningBanner")
        self.warning_banner.setWordWrap(True)
        self.warning_banner.setVisible(False)

        self.tabs = QTabWidget()

        central = QWidget()
        central_layout = QVBoxLayout()
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.warning_banner)
        central_layout.addWidget(self.tabs)
        central.setLayout(central_layout)
        self.setCentralWidget(central)

        # Create tabs
        self.create_download_tab()
        self.create_settings_tab()

    def create_download_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)

        # Download type
        self.type_label = QLabel()
        layout.addWidget(self.type_label)

        type_layout = QHBoxLayout()
        self.radio_audio = QRadioButton()
        self.radio_video = QRadioButton()
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

        self.quality_label = QLabel()
        video_layout.addWidget(self.quality_label)

        self.quality_combo = QComboBox()
        self.quality_label_indices = []  # filled in by update_quality_options()
        self.quality_combo.setMinimumWidth(200)
        self.quality_combo.currentIndexChanged.connect(self.validate)
        video_layout.addWidget(self.quality_combo)

        video_layout.addSpacing(20)
        self.advanced_label = QLabel()
        video_layout.addWidget(self.advanced_label)

        self.format_entry = QLineEdit()
        self.format_entry.setMaximumWidth(220)
        self.format_entry.textChanged.connect(self.validate)
        video_layout.addWidget(self.format_entry)
        video_layout.addStretch()

        self.video_options.setLayout(video_layout)
        self.video_options.setVisible(False)
        layout.addWidget(self.video_options)

        # Split by chapters
        self.split_chapters_check = QCheckBox()
        layout.addWidget(self.split_chapters_check)

        # Playlists
        self.playlist_check = QCheckBox()
        layout.addWidget(self.playlist_check)

        # URL
        layout.addSpacing(10)
        self.url_label = QLabel()
        layout.addWidget(self.url_label)

        self.url_entry = QLineEdit()
        layout.addWidget(self.url_entry)

        # Filename
        layout.addSpacing(10)
        self.filename_label = QLabel()
        layout.addWidget(self.filename_label)

        self.filename_entry = QLineEdit()
        layout.addWidget(self.filename_entry)

        # Download folder
        layout.addSpacing(10)
        self.folder_label = QLabel()
        layout.addWidget(self.folder_label)

        folder_layout = QHBoxLayout()
        self.folder_entry = QLineEdit(self.download_folder)
        self.folder_entry.textChanged.connect(self.on_folder_edited)
        self.folder_entry.editingFinished.connect(
            lambda: self.save_settings()
        )
        folder_layout.addWidget(self.folder_entry)

        self.browse_btn = QPushButton()
        self.browse_btn.clicked.connect(self.choose_folder)
        self.browse_btn.setMaximumWidth(100)
        folder_layout.addWidget(self.browse_btn)

        layout.addLayout(folder_layout)

        # Custom command
        layout.addSpacing(10)
        self.command_label = QLabel()
        layout.addWidget(self.command_label)

        self.command_entry = QLineEdit()
        layout.addWidget(self.command_entry)

        # Progress bar
        layout.addSpacing(10)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        layout.addWidget(self.progress)
        self.reset_progress()

        # Output
        layout.addSpacing(10)
        self.output_label = QLabel()
        layout.addWidget(self.output_label)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

        # Download / Stop buttons
        buttons_layout = QHBoxLayout()

        self.download_btn = QPushButton()
        self.download_btn.clicked.connect(self.start_download)
        buttons_layout.addWidget(self.download_btn)

        self.stop_btn = QPushButton()
        self.stop_btn.clicked.connect(self.stop_download)
        self.stop_btn.setMaximumWidth(100)
        buttons_layout.addWidget(self.stop_btn)

        layout.addLayout(buttons_layout)

        tab.setLayout(layout)
        self.tabs.addTab(tab, "")

        # Connect signals for validation
        self.radio_audio.toggled.connect(self.on_type_changed)
        self.radio_video.toggled.connect(self.on_type_changed)
        self.url_entry.textChanged.connect(self.validate)
        self.command_entry.textChanged.connect(self.validate)

    def create_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)

        self.language_label = QLabel()
        layout.addWidget(self.language_label)

        self.language_combo = QComboBox()
        self.language_codes = list(LANGUAGES.keys())
        self.language_combo.addItems(LANGUAGES.values())
        self.language_combo.setCurrentIndex(self.language_codes.index(self.language))
        self.language_combo.setMinimumWidth(150)
        self.language_combo.currentIndexChanged.connect(self.on_language_changed)
        layout.addWidget(self.language_combo)

        layout.addSpacing(20)
        self.theme_label = QLabel()
        layout.addWidget(self.theme_label)

        self.radio_dark = QRadioButton()
        self.radio_light = QRadioButton()

        if self.current_theme == "dark":
            self.radio_dark.setChecked(True)
        else:
            self.radio_light.setChecked(True)

        self.radio_dark.toggled.connect(lambda: self.change_theme("dark"))
        self.radio_light.toggled.connect(lambda: self.change_theme("light"))

        layout.addWidget(self.radio_dark)
        layout.addWidget(self.radio_light)

        layout.addSpacing(20)
        self.advanced_features_label = QLabel()
        layout.addWidget(self.advanced_features_label)

        self.allow_advanced_check = QCheckBox()
        self.allow_advanced_check.setChecked(self.allow_advanced_features)
        self.allow_advanced_check.toggled.connect(self.on_advanced_toggled)
        layout.addWidget(self.allow_advanced_check)

        layout.addStretch()

        tab.setLayout(layout)
        self.tabs.addTab(tab, "")

    def apply_advanced_mode(self):
        """Show or hide every widget gated behind "Allow advanced features"."""
        enabled = self.allow_advanced_features
        self.command_label.setVisible(enabled)
        self.command_entry.setVisible(enabled)
        self.split_chapters_check.setVisible(enabled)
        self.playlist_check.setVisible(enabled)
        self.advanced_label.setVisible(enabled)
        self.format_entry.setVisible(enabled)
        self.update_quality_options()

    def on_advanced_toggled(self, allowed):
        self.allow_advanced_features = allowed
        if not allowed:
            # Hidden controls must not keep silently affecting the download
            self.split_chapters_check.setChecked(False)
            self.playlist_check.setChecked(False)
        self.apply_advanced_mode()
        self.save_settings()
        self.validate()

    def on_language_changed(self, index):
        self.language = self.language_codes[index]
        self.retranslate_ui()
        self.save_settings()

    def on_type_changed(self):
        self.video_options.setVisible(self.radio_video.isChecked())
        self.validate()

    def update_quality_options(self):
        """Rebuild the quality combo for the current language and mode.

        In simple mode "Not selected (list formats)" is dropped — listing
        formats is only useful together with the raw format box, which is
        hidden then too — and the default becomes 1080p instead. In advanced
        mode the default reverts to "Not selected (list formats)", matching
        what the app has always defaulted to for power users.

        Turning advanced features ON always resets to that default, even if a
        quality was already picked in simple mode — 1080p carrying over as
        "the" advanced quality would be surprising. Turning them back OFF, or
        just switching language, still preserves whatever was picked.
        """
        previous_actual_index = None
        if self.quality_label_indices and self.quality_combo.count():
            previous_actual_index = self.quality_label_indices[
                self.quality_combo.currentIndex()
            ]

        just_turned_advanced_on = (
            self.allow_advanced_features and self._quality_mode_is_advanced is False
        )
        self._quality_mode_is_advanced = self.allow_advanced_features

        if self.allow_advanced_features:
            indices = list(range(len(core.QUALITY_LABELS)))
            default_actual_index = 0  # "Not selected (list formats)"
        else:
            indices = list(range(1, len(core.QUALITY_LABELS)))  # skip "Not selected"
            default_actual_index = core.QUALITY_LABELS.index("1080p")

        if just_turned_advanced_on or previous_actual_index not in indices:
            target_actual_index = default_actual_index
        else:
            target_actual_index = previous_actual_index

        self.quality_combo.blockSignals(True)
        self.quality_combo.clear()
        self.quality_combo.addItems(
            [self.tr_text(QUALITY_LABEL_KEYS[core.QUALITY_LABELS[i]]) for i in indices]
        )
        self.quality_label_indices = indices
        self.quality_combo.setCurrentIndex(indices.index(target_actual_index))
        self.quality_combo.blockSignals(False)

    def save_settings(self):
        core.save_settings(
            {
                "theme": self.current_theme,
                "download_folder": self.download_folder,
                "allow_advanced_features": self.allow_advanced_features,
                "language": self.language,
            }
        )

    def retranslate_ui(self):
        t = self.tr_text

        self.setWindowTitle(t("window_title"))
        self.tabs.setTabText(0, t("tab_download"))
        self.tabs.setTabText(1, t("tab_settings"))

        self.type_label.setText(t("download_type_label"))
        self.radio_audio.setText(t("radio_audio"))
        self.radio_video.setText(t("radio_video"))

        self.quality_label.setText(t("quality_label"))
        self.quality_combo.setToolTip(t("quality_tooltip"))
        self.update_quality_options()

        self.advanced_label.setText(t("advanced_label"))
        self.format_entry.setPlaceholderText(t("format_placeholder"))
        self.format_entry.setToolTip(t("format_tooltip"))

        self.split_chapters_check.setText(t("split_chapters_label"))
        self.split_chapters_check.setToolTip(t("split_chapters_tooltip"))

        self.playlist_check.setText(t("playlist_label"))
        self.playlist_check.setToolTip(t("playlist_tooltip"))

        self.url_label.setText(t("url_label"))
        self.url_entry.setPlaceholderText(t("url_placeholder"))

        self.filename_label.setText(t("filename_label"))
        self.filename_entry.setPlaceholderText(t("filename_placeholder"))

        self.folder_label.setText(t("folder_label"))
        self.browse_btn.setText(t("browse_button"))

        self.command_label.setText(t("command_label"))
        self.command_entry.setPlaceholderText(t("command_placeholder"))

        self.output_label.setText(t("output_label"))
        self.stop_btn.setText(t("stop_button"))

        if self.progress.maximum() == 0:
            self.reset_progress()

        self.theme_label.setText(t("theme_label"))
        self.radio_dark.setText(t("theme_dark"))
        self.radio_light.setText(t("theme_light"))

        self.language_label.setText(t("language_label"))

        self.advanced_features_label.setText(t("advanced_features_label"))
        self.allow_advanced_check.setText(t("allow_advanced_features_label"))
        self.allow_advanced_check.setToolTip(t("allow_advanced_features_tooltip"))

        self.update_dependency_warning()
        self.validate()

    def update_dependency_warning(self):
        """Show a banner above the tabs when ffmpeg and/or ffprobe are missing."""
        if tools.ffmpeg is None and tools.ffprobe is None:
            key = "warning_ffmpeg_ffprobe_missing"
        elif tools.ffmpeg is None:
            key = "warning_ffmpeg_missing"
        elif tools.ffprobe is None:
            key = "warning_ffprobe_missing"
        else:
            self.warning_banner.setVisible(False)
            return

        self.warning_banner.setText(self.tr_text(key))
        self.warning_banner.setVisible(True)

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
        actual_index = self.quality_label_indices[self.quality_combo.currentIndex()]
        quality_label = core.QUALITY_LABELS[actual_index]
        # The raw format box is hidden in simple mode, so a leftover value in
        # it (from before advanced features were turned off) must not apply
        format_text = self.format_entry.text().strip() if self.allow_advanced_features else ""
        return format_text or core.QUALITY_SELECTORS[quality_label]

    def validate(self):
        # Without a quality or a format code, the button lists the formats instead
        listing = self.radio_video.isChecked() and not self.format_selector()
        self.download_btn.setText(
            self.tr_text("list_formats_button" if listing else "download_button")
        )

        self.stop_btn.setEnabled(self.process_running and not self.updating)

        if self.process_running:
            self.download_btn.setEnabled(False)
            return

        has_url = bool(self.url_entry.text().strip())
        has_command = self.allow_advanced_features and bool(
            self.command_entry.text().strip()
        )
        self.download_btn.setEnabled(has_url or has_command)

    def reset_progress(self):
        """Back to the indeterminate bar, until yt-dlp reports a percentage."""
        self.progress.setMaximum(0)
        self.progress.setValue(0)
        self.progress.setFormat(self.tr_text("working"))

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

        run_messages = {
            "stopped": self.tr_text("status_stopped"),
            "success": self.tr_text("status_success"),
            "failed": self.tr_text("status_failed", code="{code}"),
            "error": self.tr_text("status_error", error="{error}"),
        }
        self.runner.start(
            command,
            on_line=self.on_worker_line,
            on_finished=self.on_worker_finished,
            shell=shell,
            cwd=self.download_folder if shell else None,
            messages=run_messages,
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
            self.append_output(self.tr_text("log_stopping"))

    def on_process_finished(self):
        self.process_running = False
        self.updating = False
        self.progress.setVisible(False)

        if self.cleanup_folder is not None:
            core.cleanup_leftovers(self.cleanup_folder, self.cleanup_before)
            self.cleanup_folder = None

        self.validate()

    def start_update(self):
        """Update yt-dlp with the window already visible, but everything locked."""
        self.cleanup_folder = None
        self.append_output(self.tr_text("log_updating"))
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
            self.command_entry.text().strip() if self.allow_advanced_features else ""
        )
        if custom_command:
            self.cleanup_folder = self.download_folder
            self.cleanup_before = core.snapshot_folder(self.download_folder)
            self.append_output(self.tr_text("log_custom_command"))
            self.launch(
                core.resolve_custom_command(custom_command, tools.yt_dlp), shell=True
            )
            return

        request = self.build_request()

        if request.lists_formats:
            self.cleanup_folder = None
            self.append_output(self.tr_text("log_listing_formats"))
        else:
            self.cleanup_folder = request.folder
            self.cleanup_before = core.snapshot_folder(request.folder)
            self.append_output(self.tr_text("log_download_started"))

            if request.split_chapters:
                self.append_output(self.tr_text("log_split_chapters"))

            if tools.ffmpeg is None:
                self.append_output(self.tr_text("log_ffmpeg_missing"))

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
                QLabel#warningBanner {
                    background-color: #5c4400;
                    color: #ffe9b3;
                    padding: 8px 12px;
                    border-bottom: 1px solid #806000;
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
                QLabel#warningBanner {
                    background-color: #fff3cd;
                    color: #664d03;
                    padding: 8px 12px;
                    border-bottom: 1px solid #ffe69c;
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
