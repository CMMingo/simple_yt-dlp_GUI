# yt-dlp GUI

A desktop GUI for **yt-dlp**: download audio or video from YouTube and other sites without a command
line.

> This is the maintained Qt (PySide6) version. A frozen, self-contained Tkinter version lives in
> [`deprecated/ytdlp_tkinter_gui.py`](deprecated/ytdlp_tkinter_gui.py) — see
> [The deprecated Tkinter version](#the-deprecated-tkinter-version).

---

## Features

- Audio (MP3) or video (MP4) downloads
- Quality presets — Best, 4K, 2K, 1080p, 720p, 480p, Smallest
- Real-time progress bar with speed and ETA, and a Stop button
- English and Spanish interface, switchable at any time from Settings
- Warns on startup if ffmpeg/ffprobe aren't installed, instead of failing silently mid-download
- Automatically cleans up leftover files from an interrupted or failed download
- Light/dark theme; every setting is remembered between sessions
- Runs yt-dlp in the background — the window never freezes

### Simple by default, advanced when you need it

The app opens in a simple mode with only the essentials on screen. Turning on **Allow advanced
features** in Settings additionally unlocks:

- A manual format-code box, for picking an exact stream combination yt-dlp offers
- Splitting a download into one file per chapter
- Whole-playlist downloads (off by default — a pasted playlist link only downloads the one video)
- A custom command box, for anything the UI doesn't cover, run as typed

---

## Requirements

- Python 3.12+
- PySide6 — `pip install pyside6` (or `uv sync`, if you use [uv](https://docs.astral.sh/uv/))
- `yt-dlp`, found in `bin/`, or on PATH. Updates itself at startup.
- `ffmpeg` + `ffprobe`, on PATH or in `bin/`. Needed for MP3 extraction, merging, and chapter
  splitting.

Optional, for building a standalone `.exe`: PyInstaller.

---

## Running

```bash
python src/ytdlp_qt_gui.py
```

---

## Usage

1. Pick **Audio** or **Video**.
2. Paste the URL.
3. For video, pick a **Quality** preset.
4. Optionally set a filename and download folder.
5. Click **Download**.

Notes:

- **Stop** cancels the running download.
- Every run ends with a translated **Finished**, **Failed**, or **Stopped** line in the output log.
- If ffmpeg and/or ffprobe can't be found, a banner appears above the tabs explaining what won't work
  until they're installed.

---

## Settings

| Setting | What it does |
| --- | --- |
| Language | English or Español — applies immediately, no restart |
| Theme | Light or dark |
| Allow advanced features | Shows the format-code box, chapter splitting, whole-playlist downloads, and the custom command box described above |

Stored in `settings.json`:

| Running | Path |
| --- | --- |
| from source | `settings/settings.json` |
| packaged `.exe` | `settings.json`, next to the executable |

No `%LOCALAPPDATA%` fallback — settings always sit with the app, so the folder (or `.exe`) is
portable. `settings/` is git-ignored.

---

## Project layout

```
src/
    ytdlp_core.py           all logic — no GUI imports
    ytdlp_qt_gui.py          PySide6 front-end
    translations.py          UI text, English and Spanish
tests/
    test_core.py             tests for ytdlp_core; no window opened
    test_translations.py     tests for translations.py; no window opened
deprecated/
    ytdlp_tkinter_gui.py     old Tkinter app, self-contained
packaging/
    yt-dlp GUI.spec          PyInstaller build spec
bin/                         yt-dlp.exe / ffmpeg.exe (git-ignored contents)
settings/settings.json       git-ignored
```

`ytdlp_core.py` and `translations.py` have no GUI dependency and are covered by their own test files:

```bash
python tests/test_core.py
python tests/test_translations.py
```

See [`src/technical_decisions.md`](src/technical_decisions.md) for the reasoning behind the
architecture, the settings/packaging layout, and what not to bundle.

---

## Building a standalone `.exe`

```bash
pip install pyinstaller
pyinstaller "packaging/yt-dlp GUI.spec"
```

Run from the project root. Produces `dist/yt-dlp GUI.exe` (~60 MB). yt-dlp and your current settings
are seeded next to the `.exe` on first run. To bundle ffmpeg too (adds ~450 MB — usually better
shipped alongside the `.exe` in a zip instead), add its `datas` entries to
[`packaging/yt-dlp GUI.spec`](packaging/yt-dlp%20GUI.spec).

---

## The deprecated Tkinter version

```bash
python deprecated/ytdlp_tkinter_gui.py
```

Old. Single-file, no dependencies beyond the standard library. No longer receives new features.
