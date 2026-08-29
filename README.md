# yt-dlp GUI

A simple and functional Python GUI for **yt-dlp**, allowing audio and video downloads from YouTube.
There are 2 versions, using Tkinter or Qt (PySide) for different styles. Both have the exact same functionalities.

---

## Features

- **Audio or Video downloads:** Select between MP3 audio extraction or MP4 video downloads.
- **Manual format selection:** For video downloads, enter your desired format (no automatic parsing).
- **Split by chapters:** Optionally cut the download into one file per chapter, using the timestamps of the video.
- **Custom command:** Type any command and run it as-is instead of the built-in options (enabled from the Settings tab).
- **Stop button:** Cancel a running download without closing the app.
- **Real progress:** The bar follows the actual download percentage, with speed and ETA.
- **Playlist control:** Playlists are opt-in, so a link with `&list=` does not pull in the whole list.
- **Optional filename:** Specify a custom output filename.
- **Download folder selection:** Choose where to save downloaded files.
- **Persistent settings:** Download folder and theme saved to disk via JSON.
- **Thread-safe execution:** Runs yt-dlp without freezing the GUI.
- **Light and Dark modes:** Switch between themes.

---

## Requirements

- Python 3.8+
- `yt-dlp.exe` next to the script (it is updated automatically on startup)
- `ffmpeg` on PATH, or `ffmpeg.exe` next to the script — required to extract audio, merge
  video and audio, and split chapters. The app warns in the output area when it is missing.
- Standard Python libraries (tkinter, PySide6, threading, subprocess, os, json, re, queue, typing)

Optional for creating standalone `.exe`:
- `PyInstaller` (pip install pyinstaller)

---

## Installation

1. Clone or download this repository.
2. Ensure `yt-dlp.exe` sits in the same folder as the script, and that `ffmpeg` is available.
3. Run the GUI:
```bash
python ytdlp_qt_gui.py
or
python ytdlp_tkinter_gui.py
```

---

## Usage

1. Open the GUI.
2. Select the download type: **Audio (MP3)** or **Video (MP4)**.
3. Paste the video URL in the URL box.
4. Optionally, enter a filename.
5. Select the download folder (default is current working directory).
6. For video, enter the desired format.
7. Optionally, tick **Split into tracks using the chapters/timestamps of the video** and
   **Download the whole playlist**.
8. Click **Download** to start.
9. The progress bar and output area show the download status.

### Playlists

Playlists are opt-in: by default only the video itself is downloaded, even when the link carries a
`&list=` parameter. Tick **Download the whole playlist** to get every entry; if a custom filename is
also set, each entry is prefixed with its playlist number so they do not overwrite each other.

### Splitting by chapters

When the checkbox is ticked, the download is cut into one file per chapter, named
`<number> - <chapter title>.<ext>`, next to the full-length file. It works for both audio and
video. If the video has no chapters, yt-dlp simply performs a normal download.

### Custom command

The box is hidden until **Allow custom command** is ticked in the **Settings** tab; the choice is
remembered between sessions. Anything written in it is run as-is, and every other option on the
Download tab is ignored. The command runs from the download folder, and a command starting with `yt-dlp` is pointed
at the bundled `yt-dlp.exe`, so it does not need to be in PATH:

```
yt-dlp --force-keyframes-at-cut --split-chapters -x --audio-format mp3 -o "%(section_number)s - %(section_title)s.%(ext)s" "VIDEO_URL"
```

Clear the box to go back to the normal download options.

### Notes
- The download button is disabled until a URL or a custom command is provided, and stays disabled
  while a download runs. **Stop** cancels it, killing yt-dlp and anything it started.
- The output area ends every run with `--- Finished ---`, `--- Failed (exit code N) ---` or
  `--- Stopped ---`, so a failed download is not mistaken for a finished one.
- Progress lines are shown on the progress bar rather than in the output area, which keeps the log
  readable. Everything else yt-dlp prints is kept.
- On startup the window opens immediately and updates yt-dlp with the controls disabled; the update
  cannot be interrupted, and the app becomes usable as soon as it finishes.
- For video downloads, the format must be entered manually.
- Themes and download folder are persisted between sessions.

---

## Theme System

- **Dark mode:** Default, uses dark backgrounds and light text.
- **Light mode:** Optional, uses light backgrounds and dark text.
- Change themes from the **Settings tab**.

---

## Saving Settings

- Stored in `settings.json` in the same folder as the script.
- Stores:
  - `theme` ("dark" or "light")
  - `download_folder` (string)
  - `allow_custom_command` (true or false)

---

## Packaging as Executable (.exe)

1. Install PyInstaller:
```bash
pip install pyinstaller
```
2. Create a single-file, windowed executable:
```bash
pyinstaller --onefile --windowed ytdlp_qt_gui.py
or
pyinstaller --onefile --windowed ytdlp_tkinter_gui.py
```
3. The `.exe` will appear in the `dist/` folder.

### Important
- The `.exe` **does not bundle `yt-dlp`**. Users must have it installed separately or include a relative path.
- If one wants to bundle the yt-dlp executable too:
  ```bash
  pyinstaller --onefile --windowed ytdlp_qt_gui.py --add-data "yt-dlp.exe;."
  or
  pyinstaller --onefile --windowed ytdlp_tkinter_gui.py --add-data "yt-dlp.exe;."
  ```

---

## Future Extensions (Optional)

- Better listing of specific formats for video download
- Drag-and-drop URLs
- Download history
- Cross-platform builds
