# Technical decisions

Rationale and implementation notes for `ytdlp_core.py` and `ytdlp_qt_gui.py` that don't belong in the
user-facing README. Read this before changing anything in `src/`.

## Architecture

**`ytdlp_core.py` has no GUI import and no side effects on import.** It owns settings, tool discovery,
command building, and process execution. `ytdlp_qt_gui.py` owns widgets and wiring only, and never
builds a yt-dlp command itself — it always goes through `DownloadRequest` → `build_command()`.

This split exists because the project used to have two full front-ends (Qt and Tkinter), each with
its own copy of settings handling, tool discovery, and command building. The copies drifted — a fix
would land in one and be forgotten in the other. The Tkinter app was retired rather than kept in sync;
see `deprecated/ytdlp_tkinter_gui.py`, which is intentionally *not* wired to `ytdlp_core` — it's a
frozen snapshot, dependency-free on purpose (single file, stdlib only), so it stays useful as a
zero-install fallback without needing to track the core's API.

**`build_command()` is a pure function** — `DownloadRequest` + `Tools` in, an argv list out, no I/O.
This is what makes `tests/test_core.py` fast and GUI-free: every command shape (audio, video, chapter
split, playlist, custom command, format listing) is checked without opening a window or touching the
network.

**`Runner.start()` calls `on_line`/`on_finished` from a background thread.** No GUI toolkit may be
touched from there — Qt objects aren't thread-safe. The Qt front-end's callbacks
(`on_worker_line`/`on_worker_finished`) do nothing but re-emit a `Signal`, which is what actually
crosses back to the main thread. A future front-end (web, CLI) needs to replicate that hop, not the
Qt-specific mechanism.

## Process execution

**`kill_process_tree()` uses `taskkill /F /T`, not `Popen.terminate()`.** The custom-command feature
runs with `shell=True`, so `terminate()` would only kill the shell wrapper (`cmd.exe`) and leave the
actual yt-dlp/ffmpeg child running. `/T` kills the whole tree.

**`CREATE_NO_WINDOW`** is passed to every `Popen` and to the `taskkill` call. Without it, a
`--windowed` PyInstaller build still flashes a console window for every subprocess.

**Custom command requires an explicit opt-in** (`allow_custom_command`, off by default, toggled in
Settings). It runs arbitrary shell input — gating it behind a setting means it can't be triggered by
just pasting something into a URL box that happens to look like a command.

## Command building

- `--newline` is required on every download. Without it yt-dlp overwrites the progress line with
  `\r`, which can't be parsed into discrete lines for the progress bar.
- Progress lines are intercepted and shown on the bar, not appended to the output log — otherwise the
  log fills with dozens of percentage updates per second.
- Playlists are opt-in (`--no-playlist` by default). The alternative — following `&list=` in a pasted
  URL — silently turns a single-video download into a 200-video one.
- Quality presets use `bv*[height<=N]+ba/b[height<=N]`. The `/b` fallback covers sites that only offer
  pre-muxed formats. Asking for a resolution *above* what's available degrades gracefully (asks for
  4K on a 1080p-max video → gets 1080p). Asking for a resolution *below* what's available fails loudly
  instead of silently returning a much larger file — this is deliberate, not an oversight.
- `--ffmpeg-location` is only passed when `ffmpeg_bundled` is true (i.e. we found it ourselves rather
  than relying on PATH), and it's passed the *containing folder*, not the ffmpeg path itself — yt-dlp
  needs to find `ffprobe` next to it.

## Settings and packaging layout

The repo layout and the packaged (`.exe`) layout are **deliberately different**, and this is the part
most likely to surprise someone touching `find_tools()` or `settings_path()`:

| | Source (`bin/`, `settings/`) | Packaged `.exe` |
| --- | --- | --- |
| yt-dlp / ffmpeg | `bin/yt-dlp.exe` etc. | directly beside the `.exe`, no `bin/` |
| settings | `settings/settings.json` | `settings.json` directly beside the `.exe` |

Source keeps the project root tidy by nesting things in `bin/` and `settings/`. Packaged, there's no
`src/` and no repo structure to keep tidy — everything a user might want to find sits flat next to the
executable. The PyInstaller `--add-data "bin/yt-dlp.exe;."` destination (`.`) is what does this: it
takes a file from `bin/` on disk and places it at the *root* of the bundle, so no path remapping is
needed at runtime — `app_dir()` when frozen is just "the exe's folder," full stop.

`app_dir()`, `bundle_dir()` and `settings_dir()`/`settings_path()` all branch on `sys.frozen`. Don't
assume `app_dir() == HERE` or that settings live in a `settings/` folder — check `sys.frozen`.

**Why yt-dlp is "seeded" rather than run from the bundle:** a `--onefile` build unpacks into a
temporary folder that Windows deletes when the process exits. yt-dlp updates itself by *replacing its
own executable*. If it ran from the temp folder, every update would be thrown away on exit and
re-downloaded on the next launch — a full re-download every single time, and a hard failure offline.
So the bundled copy is copied out once (`_seed_from_bundle`) and becomes the copy that's actually used
and updated from then on.

**Why settings are read in place instead of also being seeded out immediately:** unlike yt-dlp,
settings never *need* to be written to be used — they can be read straight out of the temp bundle on
every launch. A `.exe` genuinely can't rewrite the copy inside itself (the bundle is unpacked to a
temp folder, and the running executable is locked), so a real, writable `settings.json` only appears
the first time a user actually changes something, via `save_settings()`. A fresh, uncustomized build
therefore drops zero files next to itself until it's used.

**Precedence** in `load_settings()`: built-in `DEFAULT_SETTINGS` → bundled `settings.json` (if frozen)
→ the user's own file. Each layer only overrides the keys it defines, so a bundle that ships a partial
`settings.json` still gets sane defaults for anything it omits.

**No `%LOCALAPPDATA%` fallback, ever.** Settings always live with the app (project root or exe folder).
This is what makes "copy the folder" or "copy the exe" a complete backup/move — nothing is left behind
in the user profile. The cost: the app needs write access wherever it's placed, so it shouldn't be
installed into `Program Files` or similar.

**`DEFAULT_SETTINGS["download_folder"]` is `app_dir()`, not `os.getcwd()`.** Since `load_settings()`
now persists the defaults to disk on first run (see above), a `cwd`-dependent default would get baked
in permanently based on wherever the script happened to be launched from that first time.

## Should ffmpeg be bundled?

Generally no. A full `ffmpeg.exe` + `ffprobe.exe` pair is roughly 450 MB combined, which:

- turns a ~63 MB `.exe` into a 500+ MB one,
- and, because `--onefile` re-extracts its payload on *every* launch, turns a near-instant startup
  into a multi-second one, every time.

If ffmpeg needs to travel with the app, prefer shipping `ffmpeg.exe`/`ffprobe.exe` in the same folder
as the built `.exe` (zipped together) over baking them into the PyInstaller bundle — same result for
the end user, none of the startup cost. Only reach for `--add-data` if a single-file deliverable is a
hard requirement, and consider a stripped "essentials" ffmpeg build instead of the full one.

## The PyInstaller `.spec` file

`packaging/yt-dlp GUI.spec` is checked into git (a `!packaging/*.spec` exception carves it out of the
blanket `*.spec` ignore rule) so the exact build configuration — the `--add-data` entries in
particular — isn't just documented prose that can drift from what a real build uses.

Its paths (`../src/ytdlp_qt_gui.py`, `../bin/yt-dlp.exe`, `../settings/settings.json`) are relative to
**the `.spec` file's own folder**, not to the working directory `pyinstaller` is invoked from — that's
how PyInstaller resolves relative paths inside a spec. Build from the project root
(`pyinstaller "packaging/yt-dlp GUI.spec"`); `dist/` and `build/` still land in the project root
regardless, since `--distpath`/`--workpath` default relative to the invocation `cwd`, not `SPECPATH`.

To regenerate it after changing the build flags:

```bash
pyi-makespec --onefile --windowed --name "yt-dlp GUI" --paths src --add-data "bin/yt-dlp.exe;." --add-data "settings/settings.json;." --specpath packaging src/ytdlp_qt_gui.py
```

`pyi-makespec` rewrites the script's own path to be relative to `--specpath`, but leaves `pathex` and
`--add-data` sources exactly as typed — those need the `../` prefix added by hand afterwards, or the
next build will fail looking for `packaging/bin/yt-dlp.exe`.

## Testing

`tests/test_core.py` never imports a GUI toolkit and never opens a network connection. Frozen-build
behavior (seeding, settings precedence, path resolution) is tested via a `frozen_as` context manager
that fakes `sys.frozen` / `sys._MEIPASS` / `sys.executable` rather than actually invoking PyInstaller
— keeps the suite fast enough to run on every change instead of only before a release.
