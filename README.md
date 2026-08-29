# yt-dlp GUI

A simple and functional desktop GUI for **yt-dlp**: download audio or video from YouTube and other
sites without touching a command line.

> **This is the Qt (PySide6) version, and the only one maintained.** The original Tkinter app still
> lives in [`deprecated/ytdlp_tkinter_gui.py`](deprecated/ytdlp_tkinter_gui.py) as a single
> self-contained script. It works, but it is frozen — every new feature and fix lands here only. See
> [The deprecated Tkinter version](#the-deprecated-tkinter-version) at the end.

---

## What it does

- **Audio or video.** MP3 extraction, or MP4 video merged from the best streams.
- **Quality presets.** Best, 4K, 2K, 1080p, 720p, 480p or smallest, from a dropdown — no format codes.
- **Manual format codes.** An advanced box for full control when the presets are not enough.
- **Split by chapters.** Cut a download into one file per chapter using the video's own timestamps.
- **Playlist control.** Playlists are opt-in, so a link carrying `&list=` does not pull in 200 videos.
- **Real progress.** The bar follows the actual percentage, with speed and ETA.
- **Stop button.** Cancel a running download without closing the app.
- **Custom command.** Run any command as-is, for the cases the UI does not cover.
- **Light and dark themes**, and settings that persist between sessions.
- **Never freezes.** yt-dlp runs in the background while the window stays responsive.

---

## Requirements

- Python 3.8+
- **PySide6** — `pip install pyside6`
- **yt-dlp**, found in the project folder, in `src/`, or on PATH. It updates itself at startup.
- **ffmpeg** (and `ffprobe`), on PATH or in the project folder. Required for MP3 extraction, for
  merging video with audio, and for splitting chapters. Without it the app still runs and warns you
  in the output area, but those three things fail.

Optional, for building a standalone `.exe`: **PyInstaller**.

---

## Quick start

```bash
python src/ytdlp_qt_gui.py
```

It can be launched from any working directory — Python puts the script's own folder on the import
path, so its `ytdlp_core` module is found automatically.

On startup the window appears immediately with the controls disabled while yt-dlp updates itself,
then unlocks. The update cannot be interrupted, which is deliberate: an outdated yt-dlp is the most
common cause of downloads failing.

---

## Usage

1. Pick **Audio (MP3)** or **Video (MP4)**.
2. Paste the URL.
3. For video, choose a **Quality** preset.
4. Optionally set a filename, a download folder, and the chapter/playlist checkboxes.
5. Click **Download**. The bar and the output area show progress.

### Video quality

Choosing **Video (MP4)** reveals a quality row:

- **Quality** — a preset yt-dlp resolves on its own: *Best available*, *4K (2160p)*, *2K (1440p)*,
  *1080p*, *720p*, *480p* or *Smallest*. Each takes the best video and audio tracks up to that height
  and merges them, so no format codes are involved.
- **Advanced** — the box for raw format codes such as `299+140`. Anything typed here overrides the
  preset.

Presets degrade gracefully: asking for 4K on a video that tops out at 1080p simply gets you 1080p.
The reverse is not true — asking for 480p on a video whose lowest quality is 720p makes yt-dlp report
`Requested format is not available`. That is deliberate, since silently handing back a much larger
file would be worse.

While no preset and no format code are set, the button reads **List formats** instead of
**Download**, and clicking it prints the available formats for that URL rather than downloading.

### Playlists

Playlists are opt-in: by default only the video itself is downloaded, even when the link carries a
`&list=` parameter. Tick **Download the whole playlist** for every entry. If a custom filename is set
too, each entry is prefixed with its playlist number so they do not overwrite each other.

### Splitting by chapters

Tick the checkbox and the download is cut into one file per chapter, named
`<number> - <chapter title>.<ext>`, alongside the full-length file. Works for both audio and video.
If the video has no chapters, yt-dlp just performs a normal download.

### Custom command

Hidden until **Allow custom command** is ticked in the **Settings** tab. Anything written in the box
is run as-is and every other option on the Download tab is ignored. The command runs from the
download folder, and one starting with `yt-dlp` is pointed at the located executable, so it does not
need to be on PATH:

```
yt-dlp --force-keyframes-at-cut --split-chapters -x --audio-format mp3 -o "%(section_number)s - %(section_title)s.%(ext)s" "VIDEO_URL"
```

Clear the box to go back to the normal options.

### Themes

Dark by default, light optional, switched from the **Settings** tab and remembered between sessions.

### Good to know

- The button label says what the next click will do: **List formats** when no quality or format code
  is chosen for a video, **Download** otherwise.
- **Download** is disabled until there is a URL (or a custom command), and stays disabled while
  something is running. **Stop** cancels it, killing yt-dlp and any process it started.
- Every run ends with `--- Finished ---`, `--- Failed (exit code N) ---` or `--- Stopped ---`, so a
  failure is never mistaken for success.
- Progress lines go to the progress bar rather than the output area, which keeps the log readable.
  Everything else yt-dlp prints is kept.

---

## Settings

`settings.json` holds three keys — `theme`, `download_folder` and `allow_custom_command` — and lives
in a `settings/` folder at the root of the app: the project folder when running from source, next to
the executable when packaged.

Values resolve in order, each overriding the previous:

1. the built-in defaults,
2. a copy shipped inside a packaged build, if there is one,
3. the user's own `settings/settings.json`.

Only the last is ever written. From source it is created on first run, so there is always something
to hand-edit. A packaged `.exe` creates nothing until a setting is actually changed — it reads its
shipped copy straight out of the bundle. A corrupted file is ignored and falls back the same way.

There is no fallback to `%LOCALAPPDATA%` or anywhere else, which keeps the app portable: copy the
folder and your settings come with it. The trade-off is that it needs write access where it sits, so
do not install it somewhere like *Program Files*. The path is also never resolved against the working
directory, so launching from elsewhere cannot silently start you on blank settings.

`settings/` is git-ignored — your download folder is never committed.

---

## Building a standalone `.exe`

```bash
pip install pyinstaller
```

From the project folder:

```bash
pyinstaller --onefile --windowed --name "yt-dlp GUI" --paths src --add-data "yt-dlp.exe;." --add-data "settings;settings" src/ytdlp_qt_gui.py
```

That produces a single `dist/yt-dlp GUI.exe` of about 63 MB with nothing missing.

| Flag | Why |
| --- | --- |
| `--onefile` | one file to share, instead of a folder |
| `--windowed` | no console window behind the GUI |
| `--name "yt-dlp GUI"` | what the `.exe` is called |
| `--paths src` | guarantees `import ytdlp_core` resolves during analysis |
| `--add-data "yt-dlp.exe;."` | bundles yt-dlp inside the executable |
| `--add-data "settings;settings"` | ships your current settings as the starting point |

**You never list `ytdlp_core.py`.** PyInstaller follows the import graph and pulls it in
automatically; `--add-data` is only for things that are *not* imported. `--paths src` is a safeguard
rather than a requirement — PyInstaller already searches the script's own folder.

### What lands next to the `.exe`

**yt-dlp is copied out on first run.** A `--onefile` build unpacks its bundle into a temporary folder
that Windows deletes on exit. yt-dlp updates itself by replacing its own executable, so running it
from there would throw the update away every time — re-downloading it on *every launch*, and failing
outright when offline. Instead the app copies it out once, and from then on runs and updates that
copy.

**Settings are not copied**, because they never need to be written in order to be used. The app reads
the bundled copy in place, so a fresh build leaves only:

```
yt-dlp GUI.exe      what you shared
yt-dlp.exe          copied out on first run, updated from then on
```

A real `settings/settings.json` appears beside the executable only when someone changes a setting,
and overrides the shipped copy from then on. Delete it to go back to the settings you shipped;
delete `yt-dlp.exe` and the app extracts a fresh one.

An `.exe` cannot update the copy inside itself — the bundle is unpacked to a temporary folder and the
running executable is locked by Windows — so bundled settings are read-only by nature. Reading them
in place is what keeps a fresh build from littering.

> **Sharing caveat:** `download_folder` is an absolute path from *your* machine, so a recipient
> starts pointed somewhere that may not exist on theirs. For builds meant for other people, drop the
> `settings` flag or first set a neutral download folder.

### Should ffmpeg be bundled? Usually not

It can be, and it needs no copying out since it never updates itself:

```bash
pyinstaller --onefile --windowed --name "yt-dlp GUI" --paths src --add-data "yt-dlp.exe;." --add-data "settings;settings" --add-data "ffmpeg.exe;." --add-data "ffprobe.exe;." src/ytdlp_qt_gui.py
```

The problem is size. A full `ffmpeg.exe` is around 225 MB and `ffprobe.exe` another 225 MB — both are
needed. That turns a 63 MB executable into something several times larger, and since `--onefile`
unpacks everything on *every* launch, a one-second startup becomes a long one.

In order of preference:

1. **Do not bundle it.** The app finds ffmpeg on PATH and warns clearly when it is missing. Best for
   your own use.
2. **Ship it beside the `.exe`.** Put `ffmpeg.exe` and `ffprobe.exe` in the same folder and zip the
   three together. The app looks there first, and there is no unpacking cost. Best for sharing.
3. **Bundle it** only if one literal file matters more than size and startup time — and use an
   "essentials" ffmpeg build, which is a fraction of the size.

Both files must exist in the project folder or PyInstaller fails on the missing `--add-data` source.
Always include `ffprobe.exe` with ffmpeg: yt-dlp needs both, which is why the app passes the
containing *folder* to `--ffmpeg-location` rather than the ffmpeg file itself.

### Practical notes

- `--onefile` with PySide6 lands around 63 MB and pauses briefly on every launch while it unpacks.
  `--onedir` starts noticeably faster if shipping a folder is acceptable.
- The build writes a `yt-dlp GUI.spec`. Once you add an icon or more data, edit that and build with
  `pyinstaller "yt-dlp GUI.spec"` instead of retyping flags.
- `build/` is intermediate output and can be deleted; `dist/` holds the executable. Both are
  git-ignored.
- Helper processes start with `CREATE_NO_WINDOW`, so `--windowed` does not flash a console on every
  yt-dlp call.

---

## Working on the code

### Layout

```
src/
    ytdlp_core.py          all the logic; imports no GUI toolkit at all
    ytdlp_qt_gui.py        the PySide6 front-end: widgets and wiring only
tests/
    test_core.py           tests for the core; never opens a window
deprecated/
    ytdlp_tkinter_gui.py   the old Tkinter app, self-contained and frozen
settings/settings.json     written by the app; git-ignored
yt-dlp.exe                 updated by the app itself
```

Runtime files (`settings/`, `yt-dlp.exe`) sit at the root, never inside `src/`: source is what git
tracks and can replace at will, and mixing state into it means a clean checkout wipes your settings.

### Why the logic is separate

**`ytdlp_core` decides *what* to run; `ytdlp_qt_gui` only decides what it looks like.** The app used
to exist twice, each copy carrying its own settings handling, tool discovery, quality presets,
progress parsing and command building. Two copies drift apart silently — a fix lands in one file and
is forgotten in the other. That is exactly why the Tkinter version was retired rather than kept in
sync.

**The logic is testable without a GUI.** `build_command()` is a pure function: a request in, an argv
list out, no side effects. Every command shape is verified in milliseconds, with no window and no
network, which is what makes changing yt-dlp flags safe.

**The core imports only the standard library** — `json os re shutil subprocess sys threading
dataclasses typing`. Only the front-end needs PySide6, so the logic stays reusable by something that
is not a desktop app.

**One rule if you add another front-end.** `Runner` calls its `on_line` and `on_finished` callbacks
*from a background thread*. A GUI toolkit must never be touched from there, so a front-end has to
hand the value back to its own main thread first — the Qt app emits a signal. Getting this wrong
deadlocks the app instead of failing loudly. Writing that hop is essentially all a second front-end
(a local web server, a CLI) would need.

### Tests

```bash
python tests/test_core.py
```

They also run under `pytest` if it is installed. No GUI, no network. They cover command building for
every combination of options, the quality presets, progress parsing, custom-command rewriting,
settings precedence (including a simulated frozen build), and `Runner` against real short-lived
processes — exit codes, streamed output, and that **Stop** kills the whole process tree.

Add a test whenever you change a yt-dlp flag or an output template. It is the cheapest place to catch
a mistake.

---

## The deprecated Tkinter version

[`deprecated/ytdlp_tkinter_gui.py`](deprecated/ytdlp_tkinter_gui.py) is the previous app: one
self-contained script with every feature built in and no dependency beyond the standard library —
handy to copy somewhere and run.

```bash
python deprecated/ytdlp_tkinter_gui.py
```

It is **no longer maintained**. It has the same features as the Qt app today, but only the Qt app
gets new ones, so expect them to diverge. It reads and writes the same `settings/settings.json`, so
both agree on your theme and download folder.

The only change made when it was moved into `deprecated/` was widening its yt-dlp lookup to check the
project folder above it, since it previously expected the binary right beside itself.

---

## Ideas for later

- A format picker that reads the real track list from `yt-dlp -J` instead of the preset dropdown
- A local web front-end: a small server on `127.0.0.1` reusing `ytdlp_core`
- Drag-and-drop URLs
- Download history
- Cross-platform builds
