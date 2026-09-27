# Technical decisions

Rationale and implementation notes for `ytdlp_core.py`, `ytdlp_qt_gui.py` and `translations.py` that
don't belong in the user-facing README. Read this before changing anything in `src/`.

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

**`translations.py` is a third, equally GUI-free module** — plain string tables plus a `tr(language,
key)` lookup, no Qt import. It's kept separate from `ytdlp_qt_gui.py` for the same reason
`ytdlp_core.py` is: so `tests/test_translations.py` can check that English and Spanish stay in sync
without opening a window, the same way `tests/test_core.py` checks command building.

**`build_command()` is a pure function** — `DownloadRequest` + `Tools` in, an argv list out, no I/O.
This is what makes `tests/test_core.py` fast and GUI-free: every command shape (audio, video, chapter
split, playlist, custom command, format listing) is checked without opening a window or touching the
network.

**`Runner.start()` calls `on_line`/`on_finished` from a background thread.** No GUI toolkit may be
touched from there — Qt objects aren't thread-safe. The Qt front-end's callbacks
(`on_worker_line`/`on_worker_finished`) do nothing but re-emit a `Signal`, which is what actually
crosses back to the main thread. A future front-end (web, CLI) needs to replicate that hop, not the
Qt-specific mechanism.

## Internationalization

**The GUI never hardcodes a string; every label goes through `self.tr_text(key)`**, a thin wrapper
around `translations.tr(self.language, key)`. Widgets are created empty in `create_download_tab()` /
`create_settings_tab()` and get their text from a single `retranslate_ui()` pass, called once at
startup and again whenever the language changes — there's no restart, and no widget's text is ever set
in two places.

**`translations.TRANSLATIONS` is a flat `{language: {key: text}}` dict, not a class hierarchy or a
`.po` file.** The app only ever needs two languages and plain string substitution (`str.format` for
things like the exit code in "Failed (exit code {code})"), so a proper i18n toolchain (gettext, Qt
Linguist) would be solving a problem this app doesn't have. `tests/test_translations.py` guards the one
real risk of this approach — a key added to one language and forgotten in the other — by asserting
both language dicts define exactly the same keys.

**Quality preset labels are translated through a separate mapping, `QUALITY_LABEL_KEYS`**, because
`core.QUALITY_LABELS` (the English strings used internally as dict keys into `QUALITY_SELECTORS`) must
never themselves change with the language — only what's *displayed* in the combo box does. The GUI
tracks `self.quality_label_indices`, a list mapping each visible combo row back to its real index in
`core.QUALITY_LABELS`, so `format_selector()` never has to parse translated text back into a selector.
`tests/test_translations.py` checks `QUALITY_LABEL_KEYS` covers exactly the presets `core.py` defines —
neither more (a stale entry after a preset is renamed) nor fewer (a new preset with no translation).

**Runner's closing message is translatable without `ytdlp_core.py` knowing about languages.**
`Runner.start()` takes an optional `messages` dict of templates (`{"stopped": ..., "success": ...,
"failed": "...{code}...", "error": "...{error}..."}`); the Qt front-end builds this from
`self.tr_text(...)` before every launch. Omitting `messages` falls back to English templates baked
into `ytdlp_core.py` (`DEFAULT_RUN_MESSAGES`) — this is what keeps `tests/test_core.py` (which asserts
on the literal English text) decoupled from the GUI's language setting entirely.

## Process execution

**`kill_process_tree()` uses `taskkill /F /T`, not `Popen.terminate()`.** The custom-command feature
runs with `shell=True`, so `terminate()` would only kill the shell wrapper (`cmd.exe`) and leave the
actual yt-dlp/ffmpeg child running. `/T` kills the whole tree.

**`CREATE_NO_WINDOW`** is passed to every `Popen` and to the `taskkill` call. Without it, a
`--windowed` PyInstaller build still flashes a console window for every subprocess.

## Simple vs. advanced mode

**One setting, `allow_advanced_features` (off by default, "Allow advanced features" in Settings),
gates every option that isn't needed for a plain "paste a link, pick a quality, download":**
the custom command box, chapter splitting, whole-playlist downloads, and the raw format-code box.
Turning it off doesn't just hide these — `on_advanced_toggled()` also unchecks chapter splitting and
whole-playlist so a checkbox the user can no longer see can't keep silently affecting the download, and
`format_selector()` ignores any leftover text in the (hidden) format box the same way. The custom
command box needs no equivalent guard: `start_download()` already reads it only `if
self.allow_advanced_features`.

**The quality combo drops "Not selected (list formats)" in simple mode and defaults to 1080p.**
Listing formats is only useful together with the raw format box (so the user has somewhere to type one
of the codes it lists), and that box is exactly what's hidden in simple mode — so the combo excludes
that entry entirely rather than leaving a dead end reachable. `update_quality_options()` rebuilds the
combo from `core.QUALITY_LABELS` filtered by `self.allow_advanced_features`, and preserves whatever was
already selected across the toggle when it's still a valid choice (e.g. going advanced → simple → advanced
keeps 1080p instead of resetting).

Originally this same setting only gated the custom command box (hence its old name,
`allow_custom_command`); it was renamed and its scope widened in place rather than adding a second
setting, since from the user's point of view it's one question — "show me the advanced stuff or not" —
not several independent ones.

## Dependency warning banner

**`Tools` also resolves `ffprobe`, not just `ffmpeg`**, even though nothing in `build_command()` passes
an `ffprobe` path anywhere (yt-dlp finds it next to `ffmpeg` on its own via `--ffmpeg-location`). The
only reason `find_tools()` looks for it is so the GUI can tell the user it's missing *before* a
download fails partway through needing it — a `QLabel` above the tabs (`self.warning_banner`),
checked once at startup against whichever of `tools.ffmpeg` / `tools.ffprobe` is `None`, with a
dedicated message for "just ffmpeg", "just ffprobe", or "both".

This check happens once, at import time (`tools = core.find_tools()` runs before any window exists) —
it's a startup diagnostic, not a live poll. If someone installs ffmpeg while the app is already open,
the banner won't clear until the app is restarted; that trade-off is deliberate, since polling the
filesystem or PATH on every download for a scenario this rare isn't worth the complexity.

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

**`cleanup_leftovers()` removes intermediate files by diffing the folder, not by predicting a
filename.** When video and audio must be downloaded separately before merging, yt-dlp names the
pieces with the format id ahead of the extension (`Song.f399.mp4`, `Song.f251.webm`) and deletes them
itself right after a successful merge. If the merge never happens — ffmpeg missing, the merge
failing, or the download being stopped midway — they're left behind. The actual final filename isn't
known ahead of time (`%(title)s` is resolved by yt-dlp, not by us), so the GUI snapshots the folder
(`core.snapshot_folder()`) right before launching a download and diffs it against the folder
afterwards in `on_process_finished()`; only files that are both new and match yt-dlp's own naming for
unmerged pieces or partial downloads (`.f<id>.<ext>`, `.part`, `.ytdl`) are removed. This is why it's a
snapshot-diff and not a glob on the expected output name — it never touches a file the user already
had sitting in that folder, and it runs after every attempt (success, failure, or Stop), not only on
success, since a stopped or failed merge is precisely when leftovers occur.

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
`settings.json` still gets sane defaults for anything it omits. The current `.spec` doesn't bundle a
`settings.json` at all — there's no customized default worth shipping — so that middle layer is
currently a no-op (`bundled_settings_path()` just doesn't exist, `_read_json` catches the `OSError` and
returns `{}`); the mechanism stays in place for whenever there is one worth shipping again.

**No `%LOCALAPPDATA%` fallback, ever.** Settings always live with the app (project root or exe folder).
This is what makes "copy the folder" or "copy the exe" a complete backup/move — nothing is left behind
in the user profile. The cost: the app needs write access wherever it's placed, so it shouldn't be
installed into `Program Files` or similar.

**`DEFAULT_SETTINGS["download_folder"]` is `app_dir()`, not `os.getcwd()`.** Since `load_settings()`
now persists the defaults to disk on first run (see above), a `cwd`-dependent default would get baked
in permanently based on wherever the script happened to be launched from that first time.

## Should ffmpeg be bundled?

Generally no. A full `ffmpeg.exe` + `ffprobe.exe` pair is roughly 450 MB combined, which:

- turns a ~60 MB `.exe` into a 500+ MB one,
- and, because `--onefile` re-extracts its payload on *every* launch, turns a near-instant startup
  into a multi-second one, every time.

If ffmpeg needs to travel with the app, prefer shipping `ffmpeg.exe`/`ffprobe.exe` in the same folder
as the built `.exe` (zipped together) over baking them into the PyInstaller bundle — same result for
the end user, none of the startup cost. Only reach for `--add-data` if a single-file deliverable is a
hard requirement, and consider a stripped "essentials" ffmpeg build instead of the full one.

## The PyInstaller `.spec` file

`packaging/yt-dlp GUI.spec` is checked into git (a `!packaging/*.spec` exception carves it out of the
blanket `*.spec` ignore rule) so the exact build configuration — the `--add-data` entries, the Qt
module excludes, the UPX setting — isn't just documented prose that can drift from what a real build
uses.

Its paths (`../src/ytdlp_qt_gui.py`, `../bin/yt-dlp.exe`) are relative to
**the `.spec` file's own folder**, not to the working directory `pyinstaller` is invoked from — that's
how PyInstaller resolves relative paths inside a spec. Build from the project root
(`pyinstaller "packaging/yt-dlp GUI.spec"`); `dist/` and `build/` still land in the project root
regardless, since `--distpath`/`--workpath` default relative to the invocation `cwd`, not `SPECPATH`.

**`Analysis(excludes=UNUSED_QT_MODULES)` trims a long list of PySide6 submodules the app never
imports** (QtNetwork, QtQml, QtQuick, QtSvg, QtOpenGL, QtVirtualKeyboard, QtPdf, QtMultimedia,
QtWebEngine, and a handful more) — `ytdlp_qt_gui.py` only ever imports QtCore, QtGui and QtWidgets, but
PySide6's own PyInstaller hook is written to pull in far more than that by default. Excluding them
measurably shrinks the module-analysis phase (fewer hooks to process on every build, since PyInstaller
re-analyzes the full graph whenever any source file's mtime changes — there's no finer-grained
incremental mode to lean on here), which is the dominant cost of a `--onefile` rebuild during
iteration. It does *not* shrink the underlying Qt DLLs actually bundled (`Qt6Qml.dll`, `Qt6Quick.dll`,
etc. are still pulled in by PySide6's hook through the compiled `.pyd`s' own binary dependencies,
independent of which Python submodules `Analysis` is told to skip) — so treat this as a build-time
optimization, not a size one, and don't be surprised the `.exe` doesn't shrink to match the shorter
import list.

**`upx=False`.** UPX only compresses the already-built binary to save disk space; it doesn't skip any
work, so turning it on adds time to *every* build (compressing) and to *every launch* of a `--onefile`
build (decompressing, on top of the one-time extraction `--onefile` already does). That trade — smaller
download, slower everything else — makes sense for a binary handed to end users, not for a build that
gets thrown away and regenerated on every test iteration during development.

To regenerate the `.spec` from scratch after changing the build flags:

```bash
pyi-makespec --onefile --windowed --name "yt-dlp GUI" --paths src --add-data "bin/yt-dlp.exe;." --specpath packaging src/ytdlp_qt_gui.py
```

`pyi-makespec` rewrites the script's own path to be relative to `--specpath`, but leaves `pathex` and
`--add-data` sources exactly as typed — those need the `../` prefix added by hand afterwards, or the
next build will fail looking for `packaging/bin/yt-dlp.exe`. It also has no flag for `excludes` or
`upx=False`, so regenerating from scratch silently drops both — re-add `UNUSED_QT_MODULES` and flip
`upx` back to `False` in the fresh file rather than assuming the command above reproduces the checked-in
spec exactly.

## Testing

`tests/test_core.py` and `tests/test_translations.py` never import a GUI toolkit and never open a
network connection. Frozen-build behavior (seeding, settings precedence, path resolution) is tested via
a `frozen_as` context manager that fakes `sys.frozen` / `sys._MEIPASS` / `sys.executable` rather than
actually invoking PyInstaller — keeps the suite fast enough to run on every change instead of only
before a release. `ytdlp_qt_gui.py` itself has no automated tests — it's kept deliberately thin
(widgets and wiring only, per Architecture above) precisely so that everything worth asserting on
already lives in one of the two GUI-free modules instead.
