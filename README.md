# yt-dlp GUI

A desktop GUI for **yt-dlp**: download audio or video from YouTube and other sites without a command
line.

> This is the maintained Qt (PySide6) version. A frozen, self-contained Tkinter version lives in
> [`deprecated/ytdlp_tkinter_gui.py`](deprecated/ytdlp_tkinter_gui.py) — see
> [The deprecated Tkinter version](#the-deprecated-tkinter-version).

---

## Features

- Audio (MP3) or video (MP4) downloads
- Quality presets — Best, 4K, 2K, 1080p, 720p, 480p, Smallest — plus a manual format-code box
- Split a download into one file per chapter
- Playlist downloads are opt-in
- Real progress bar with speed and ETA
- Stop button
- Custom command box, for anything the UI doesn't cover
- Light/dark theme, settings persisted between sessions
- Runs yt-dlp in the background; the window never freezes

---

## Requirements

- Python 3.8+
- PySide6 — `pip install pyside6`
- `yt-dlp`, found in `bin/`, or on PATH. Updates itself at startup.
- `ffmpeg` + `ffprobe`, on PATH or in `bin/`. Needed for MP3 extraction, merging, and chapter
  splitting — without it the app runs but warns you when those fail.

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
3. For video, pick a **Quality** preset (or type a format code in **Advanced**).
4. Optionally set a filename, download folder, chapter split, and playlist mode.
5. Click **Download**.

Notes:

- Video with no quality/format chosen: the button reads **List formats** and lists what's available
  instead of downloading.
- **Stop** cancels the running download.
- Every run ends with `--- Finished ---`, `--- Failed (exit code N) ---`, or `--- Stopped ---`.
- **Custom command** is hidden until enabled in the **Settings** tab; when used, it replaces every
  other option and runs the typed command as-is.

---

## Settings

`settings.json` (`theme`, `download_folder`, `allow_custom_command`):

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
    ytdlp_core.py          all logic — no GUI imports
    ytdlp_qt_gui.py         PySide6 front-end
tests/
    test_core.py            tests for ytdlp_core; no window opened
deprecated/
    ytdlp_tkinter_gui.py    old Tkinter app, self-contained
bin/                        yt-dlp.exe / ffmpeg.exe (git-ignored contents)
settings/settings.json      git-ignored
```

`ytdlp_core.py` has no GUI dependency and is covered by `tests/test_core.py`:

```bash
python tests/test_core.py
```

See [`src/technical_decisions.md`](src/technical_decisions.md) for the reasoning behind the
architecture, the settings/packaging layout, and what not to bundle.

---

## Building a standalone `.exe`

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "yt-dlp GUI" --paths src --add-data "bin/yt-dlp.exe;." --add-data "settings/settings.json;." src/ytdlp_qt_gui.py
```

Produces `dist/yt-dlp GUI.exe` (~63 MB). yt-dlp and your current settings are seeded next to the
`.exe` on first run; add `--add-data "bin/ffmpeg.exe;."` and `--add-data "bin/ffprobe.exe;."` to
bundle ffmpeg too (adds ~450 MB — usually better shipped alongside the `.exe` in a zip instead).

---

## The deprecated Tkinter version

```bash
python deprecated/ytdlp_tkinter_gui.py
```

Single-file, no dependencies beyond the standard library. No longer receives new features.
