"""
yt-dlp GUI — shared logic.

Everything here is free of any GUI toolkit: settings, locating the external
binaries, building yt-dlp commands and running them. A front-end (the PySide6
window next to this file, or a local web server, or a CLI) only has to turn its
own state into a DownloadRequest and display what Runner reports back.
"""

# ==================================================
# IMPORTS
# ==================================================

import json
import os
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Callable, Optional

HERE = os.path.dirname(os.path.abspath(__file__))

# Windows only: keep helper processes from flashing a console window
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# ==================================================
# WHERE THINGS LIVE
# ==================================================

# Frozen with PyInstaller, the code does not run from the folder the user sees:
# `__file__` points inside a temporary extraction folder that is wiped on exit.
# So "where the code is", "where the user's files go" and "where bundled
# resources were unpacked" are three different places and must not be confused.


# Running from source the code sits in src/, so the project folder is one level up
PROJECT_DIR = os.path.dirname(HERE)


def app_dir():
    """The root of the app: the folder holding the .exe, or the project folder.

    Everything the app writes or reads at runtime hangs off this: settings/ and
    the yt-dlp binary. It is never src/, which holds source files only.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return PROJECT_DIR


def bundle_dir():
    """Where PyInstaller unpacked the bundled files. Temporary: never write here."""
    return getattr(sys, "_MEIPASS", HERE)


def settings_dir():
    """The settings/ folder in the repo. Source layout only — see settings_path().

    Only a path: it is created when something is actually saved, so a run from
    source that nobody has customised does not litter the project root.
    """
    return os.path.join(app_dir(), "settings")


# ==================================================
# SETTINGS FILE MANAGEMENT
# ==================================================


def settings_path():
    """The settings the user owns and the app writes to.

    Deliberately not the same layout as the repo: from source it is
    settings/settings.json, keeping the project root tidy. Packaged, there is
    no settings/ at all — `--add-data "settings/settings.json;."` (see the
    packaging docs) places the shipped copy at the bundle's root, so the
    file the user's own changes get written to sits directly beside the
    executable instead, matching where the seeded yt-dlp binary ends up.
    """
    if getattr(sys, "frozen", False):
        return os.path.join(app_dir(), "settings.json")
    return os.path.join(settings_dir(), "settings.json")


def bundled_settings_path():
    """Settings shipped inside a frozen build: read-only defaults, never written."""
    return os.path.join(bundle_dir(), "settings.json")


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):  # missing or corrupted
        return {}

    return data if isinstance(data, dict) else {}


DEFAULT_SETTINGS = {
    "theme": "dark",
    # The app root rather than the working directory: the defaults are written
    # out on first run, so a cwd-dependent value would be baked in permanently
    "download_folder": app_dir(),
    "allow_custom_command": False,
}


def load_settings():
    """The settings, in order of precedence: built-in, bundled, then the user's.

    A frozen build can carry a settings.json inside it. That copy is read
    straight out of the bundle and never written to — an .exe cannot modify
    itself — so a build nobody has customised creates no files at all. The
    moment a setting is changed, save_settings writes a real file next to the
    executable, and from then on that file wins.
    """
    settings = DEFAULT_SETTINGS.copy()

    if bundle_dir() != app_dir():  # frozen: defaults shipped inside the .exe
        settings.update(_read_json(bundled_settings_path()))

    settings.update(_read_json(settings_path()))

    # Running from source there is no bundle to fall back on, so keep a file on
    # disk to edit by hand. A distributed .exe is left clean instead.
    if not getattr(sys, "frozen", False) and not os.path.isfile(settings_path()):
        save_settings(settings)

    return settings


def save_settings(settings):
    """Write the settings, creating settings/ the first time it is needed.

    Only relevant from source: packaged, settings_path() already sits directly
    in app_dir(), which exists as soon as the .exe does.
    """
    os.makedirs(os.path.dirname(settings_path()), exist_ok=True)

    with open(settings_path(), "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)


# ==================================================
# EXTERNAL TOOLS (yt-dlp and ffmpeg)
# ==================================================


@dataclass
class Tools:
    """Where the external programs live."""

    yt_dlp: Optional[str] = None
    ffmpeg: Optional[str] = None
    # True when ffmpeg is a file we found ourselves rather than one on PATH;
    # only then does yt-dlp need to be told where it is
    ffmpeg_bundled: bool = False


def _find_binary(name, folders):
    """Look for `name` in the given folders, then fall back to PATH."""
    for folder in folders:
        for filename in (name + ".exe", name):
            candidate = os.path.join(folder, filename)
            if os.path.isfile(candidate):
                return candidate, True

    return shutil.which(name), False


def _seed_from_bundle(relative_path):
    """Copy a bundled tool out of the archive once, so it can be written to.

    yt-dlp replaces its own executable when it updates. Inside a PyInstaller
    bundle that executable sits in a temporary folder that disappears when the
    app closes, so the update would be thrown away and downloaded again on every
    launch. The bundled copy is therefore only a seed: it is copied next to the
    app the first time, and from then on that copy is the one that runs and
    updates itself.
    """
    if bundle_dir() == app_dir():  # not frozen, or a --onedir build
        return

    source = os.path.join(bundle_dir(), relative_path)
    target = os.path.join(app_dir(), relative_path)

    if os.path.isfile(source) and not os.path.isfile(target):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(source, target)


def find_tools(folder=None):
    """Locate yt-dlp and ffmpeg, unpacking bundled copies on the first run.

    The two layouts are deliberately different. In the repo, executables sit
    in bin/ so the project root stays tidy. Packaged, they sit directly beside
    the .exe instead: `--add-data "bin/yt-dlp.exe;."` places the file at the
    bundle's root regardless of where it came from on disk, so no path
    remapping is needed here — seeding is a plain root-to-root copy.
    """
    if folder:
        folders = [folder]
    else:
        for name in ("yt-dlp", "ffmpeg", "ffprobe"):
            filename = name + ".exe" if os.name == "nt" else name
            _seed_from_bundle(filename)

        if getattr(sys, "frozen", False):
            folders = [app_dir()]  # the seeded copy lands directly beside the .exe
        else:
            folders = [
                os.path.join(PROJECT_DIR, "bin"),
                os.path.join(HERE, "bin"),
            ]

    yt_dlp, _ = _find_binary("yt-dlp", folders)
    ffmpeg, ffmpeg_bundled = _find_binary("ffmpeg", folders)

    return Tools(yt_dlp=yt_dlp, ffmpeg=ffmpeg, ffmpeg_bundled=ffmpeg_bundled)


# ==================================================
# VIDEO QUALITY PRESETS
# ==================================================

# "bv*+ba" takes the best video and audio tracks separately and merges them;
# the "/b" fallback covers sites that only offer pre-merged files. A height
# limit picks the closest quality below it when the video does not reach it.
QUALITY_PRESETS = [
    ("Not selected (list formats)", ""),
    ("Best available", "bv*+ba/b"),
    ("4K (2160p)", "bv*[height<=2160]+ba/b[height<=2160]"),
    ("2K (1440p)", "bv*[height<=1440]+ba/b[height<=1440]"),
    ("1080p", "bv*[height<=1080]+ba/b[height<=1080]"),
    ("720p", "bv*[height<=720]+ba/b[height<=720]"),
    ("480p", "bv*[height<=480]+ba/b[height<=480]"),
    ("Smallest", "wv*+wa/w"),
]

QUALITY_LABELS = [label for label, _ in QUALITY_PRESETS]
QUALITY_SELECTORS = dict(QUALITY_PRESETS)


# ==================================================
# DOWNLOAD PROGRESS
# ==================================================

# Matches the percentage of "[download]  12.3% of 10.00MiB at 1.00MiB/s ETA 00:09"
PROGRESS_RE = re.compile(r"^\[download\]\s+(\d{1,3}(?:\.\d+)?)%")


def parse_progress(line):
    """The percentage reported by a yt-dlp output line, or None."""
    match = PROGRESS_RE.match(line)
    return float(match.group(1)) if match else None


def progress_detail(line):
    """The readable part of a progress line, without the "[download]" prefix."""
    return line.split("]", 1)[1].strip()


# ==================================================
# BUILDING COMMANDS
# ==================================================


@dataclass
class DownloadRequest:
    """What the user asked for, with no widgets involved."""

    url: str
    kind: str = "audio"  # "audio" or "video"
    selector: str = ""  # the -f value; empty for video means "list formats"
    filename: str = ""
    folder: str = "."
    split_chapters: bool = False
    whole_playlist: bool = False

    @property
    def lists_formats(self):
        """A video with no quality and no format code: show what is available."""
        return self.kind == "video" and not self.selector.strip()


def build_command(request, tools):
    """The yt-dlp command line for a request. A pure function."""
    common_args = [
        "--newline",  # one progress line at a time, so a bar can be updated
        "--yes-playlist" if request.whole_playlist else "--no-playlist",
    ]
    if tools.ffmpeg and tools.ffmpeg_bundled:
        # The containing folder, so yt-dlp finds ffprobe next to ffmpeg
        common_args += ["--ffmpeg-location", os.path.dirname(tools.ffmpeg)]

    if request.lists_formats:
        return [tools.yt_dlp, *common_args, "-F", request.url]

    base = request.filename.strip() or "%(title)s"
    # A fixed name would make every playlist entry overwrite the previous one
    if request.whole_playlist and request.filename.strip():
        base = "%(playlist_index)s - " + base
    output_template = os.path.join(request.folder, base + ".%(ext)s")

    # Chapter splitting: yt-dlp keeps the full file and simply downloads it
    # normally when the video has no chapters
    split_args = []
    if request.split_chapters:
        chapter_template = os.path.join(
            request.folder, "%(section_number)s - %(section_title)s.%(ext)s"
        )
        split_args = [
            "--force-keyframes-at-cut",
            "--split-chapters",
            "-o",
            "chapter:" + chapter_template,
        ]

    if request.kind == "audio":
        return [
            tools.yt_dlp,
            *common_args,
            *split_args,
            "-x",
            "--audio-format",
            "mp3",
            "-o",
            output_template,
            request.url,
        ]

    return [
        tools.yt_dlp,
        *common_args,
        *split_args,
        "-f",
        request.selector,
        "--merge-output-format",
        "mp4",
        "-o",
        output_template,
        request.url,
    ]


def update_command(tools):
    """The command that updates yt-dlp itself."""
    return [tools.yt_dlp, "--update"]


def resolve_custom_command(text, yt_dlp_path):
    """Point a hand-written `yt-dlp ...` command at the located executable."""
    command = text.strip()
    for name in ("yt-dlp.exe", "yt-dlp"):
        if command.lower() == name or command.lower().startswith(name + " "):
            return f'"{yt_dlp_path}"' + command[len(name) :]
    return command


# ==================================================
# RUNNING COMMANDS
# ==================================================


def kill_process_tree(process):
    """Kill the process and its children (a shell command spawns its own tree)."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )
    else:
        process.terminate()


class Runner:
    """Runs one command at a time in a background thread.

    IMPORTANT: `on_line` and `on_finished` are called FROM THAT THREAD. A GUI
    toolkit must never be touched from there, so a front-end has to hand the
    value back to its own main thread first: the Qt front-end emits a signal, a
    web front-end would push an event to the client.
    """

    def __init__(self):
        self._process = None
        self._stop_requested = False

    @property
    def running(self):
        return self._process is not None

    def start(
        self,
        command,
        on_line: Callable[[str], None],
        on_finished: Callable[[str], None],
        shell=False,
        cwd=None,
    ):
        self._stop_requested = False

        threading.Thread(
            target=self._run,
            args=(command, on_line, on_finished, shell, cwd),
            daemon=True,
        ).start()

    def _run(self, command, on_line, on_finished, shell, cwd):
        message = ""

        try:
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=shell,
                cwd=cwd,
                creationflags=CREATE_NO_WINDOW,
            )

            for line in self._process.stdout:
                on_line(line)

            code = self._process.wait()

            if self._stop_requested:
                message = "\n--- Stopped ---\n"
            elif code == 0:
                message = "\n--- Finished ---\n"
            else:
                message = f"\n--- Failed (exit code {code}) ---\n"

        except OSError as error:
            message = f"\n--- Could not run: {error} ---\n"

        finally:
            self._process = None
            on_finished(message)

    def stop(self):
        """Kill whatever is running. Returns False when there was nothing to kill."""
        process = self._process
        if process is None or process.poll() is not None:
            return False

        self._stop_requested = True
        kill_process_tree(process)
        return True
