"""
Tests for ytdlp_core.

Nothing here opens a window: build_command is a pure function, so the shape of
every yt-dlp command can be checked in milliseconds. Run them with pytest, or
directly with `python tests/test_core.py` if pytest is not installed.
"""

import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import ytdlp_core as core  # noqa: E402

TOOLS = core.Tools(yt_dlp="YTDLP", ffmpeg=r"C:\tools\ffmpeg.exe", ffmpeg_bundled=True)
PATH_TOOLS = core.Tools(yt_dlp="YTDLP", ffmpeg="/usr/bin/ffmpeg", ffmpeg_bundled=False)
FOLDER = os.path.join("C:", os.sep, "out")


class frozen_as:
    """Pretend to be a PyInstaller build: a bundle folder and an .exe folder."""

    def __init__(self, bundle, app):
        self.bundle = bundle
        self.app = app

    def __enter__(self):
        sys.frozen = True
        sys._MEIPASS = self.bundle
        self.executable = sys.executable
        sys.executable = os.path.join(self.app, "app.exe")

    def __exit__(self, *exc):
        del sys.frozen
        del sys._MEIPASS
        sys.executable = self.executable


def command(tools=TOOLS, **kwargs):
    kwargs.setdefault("url", "URL")
    kwargs.setdefault("folder", FOLDER)
    return core.build_command(core.DownloadRequest(**kwargs), tools)


def value_after(command, flag):
    """The argument that follows the first `flag`."""
    return command[command.index(flag) + 1]


def last_value_after(command, flag):
    """The argument that follows the last `flag`."""
    return command[len(command) - command[::-1].index(flag)]


# ==================================================
# COMMAND BUILDING
# ==================================================


def test_audio_extracts_mp3():
    cmd = command()
    assert cmd[0] == "YTDLP"
    assert "-x" in cmd and value_after(cmd, "--audio-format") == "mp3"
    assert cmd[-1] == "URL"


def test_video_uses_the_selector_and_merges_to_mp4():
    cmd = command(kind="video", selector="bv*+ba/b")
    assert value_after(cmd, "-f") == "bv*+ba/b"
    assert value_after(cmd, "--merge-output-format") == "mp4"


def test_every_download_asks_for_line_by_line_progress():
    # Without --newline yt-dlp overwrites one line with \r and the bar cannot follow
    assert "--newline" in command()
    assert "--newline" in command(kind="video", selector="b")


def test_playlists_are_opt_in():
    assert "--no-playlist" in command()
    assert "--yes-playlist" in command(whole_playlist=True)


def test_playlist_with_a_fixed_name_numbers_the_entries():
    # Otherwise every entry would overwrite the previous one
    cmd = command(whole_playlist=True, filename="Song")
    assert value_after(cmd, "-o").endswith("%(playlist_index)s - Song.%(ext)s")


def test_single_video_keeps_the_name_as_typed():
    cmd = command(filename="Song")
    assert value_after(cmd, "-o").endswith("Song.%(ext)s")


def test_no_name_falls_back_to_the_title():
    assert value_after(command(), "-o").endswith("%(title)s.%(ext)s")


def test_splitting_by_chapters_names_the_pieces():
    cmd = command(split_chapters=True)
    assert "--split-chapters" in cmd and "--force-keyframes-at-cut" in cmd

    # two -o flags: one naming the chapter pieces, one naming the full file
    assert cmd.count("-o") == 2

    chapter = value_after(cmd, "-o")
    assert chapter.startswith("chapter:")
    assert chapter.endswith("%(section_number)s - %(section_title)s.%(ext)s")

    assert last_value_after(cmd, "-o").endswith("%(title)s.%(ext)s")


def test_a_video_with_no_selector_lists_the_formats():
    request = core.DownloadRequest(url="URL", kind="video")
    assert request.lists_formats
    cmd = core.build_command(request, TOOLS)
    assert "-F" in cmd and "-f" not in cmd


def test_audio_never_lists_formats():
    assert not core.DownloadRequest(url="U", kind="audio").lists_formats
    assert not core.DownloadRequest(url="U", kind="video", selector="b").lists_formats


def test_bundled_ffmpeg_is_passed_as_its_folder():
    # so yt-dlp finds ffprobe sitting next to it
    assert value_after(command(), "--ffmpeg-location") == os.path.dirname(TOOLS.ffmpeg)


def test_ffmpeg_on_the_path_is_left_to_yt_dlp():
    assert "--ffmpeg-location" not in command(tools=PATH_TOOLS)


def test_update_command():
    assert core.update_command(TOOLS) == ["YTDLP", "--update"]


# ==================================================
# QUALITY PRESETS
# ==================================================


def test_presets_and_labels_line_up():
    assert core.QUALITY_LABELS[0] == "Not selected (list formats)"
    assert core.QUALITY_SELECTORS[core.QUALITY_LABELS[0]] == ""
    assert len(core.QUALITY_LABELS) == len(core.QUALITY_PRESETS)


def test_every_preset_but_the_first_selects_something():
    for label in core.QUALITY_LABELS[1:]:
        assert core.QUALITY_SELECTORS[label]


def test_height_limited_presets_fall_back_to_a_merged_file():
    # "/b[height<=N]" covers sites that only offer pre-merged formats
    assert core.QUALITY_SELECTORS["1080p"] == "bv*[height<=1080]+ba/b[height<=1080]"


# ==================================================
# CUSTOM COMMANDS
# ==================================================


def test_a_yt_dlp_command_is_pointed_at_the_located_binary():
    assert core.resolve_custom_command("yt-dlp -x URL", "C:/y.exe") == '"C:/y.exe" -x URL'
    assert core.resolve_custom_command("yt-dlp.exe -x", "C:/y.exe") == '"C:/y.exe" -x'


def test_any_other_command_is_left_alone():
    assert core.resolve_custom_command("ffmpeg -i a b", "C:/y.exe") == "ffmpeg -i a b"


# ==================================================
# PROGRESS PARSING
# ==================================================


def test_progress_percentage_is_read():
    assert core.parse_progress("[download]   0.0% of 5.00MiB at Unknown B/s") == 0.0
    assert core.parse_progress("[download]  42.7% of ~10.00MiB at 1.00MiB/s") == 42.7
    assert core.parse_progress("[download] 100% of 5.00MiB in 00:00:01") == 100.0


def test_other_lines_are_not_progress():
    assert core.parse_progress("[download] Destination: video.mp4\n") is None
    assert core.parse_progress("[info] Downloading 1 format(s): 299+140\n") is None
    assert core.parse_progress("--- Finished ---\n") is None


def test_progress_detail_drops_the_prefix():
    line = "[download]  42.7% of 10.00MiB at 1.00MiB/s ETA 00:09"
    assert core.progress_detail(line) == "42.7% of 10.00MiB at 1.00MiB/s ETA 00:09"


# ==================================================
# RUNNING COMMANDS
# ==================================================


def run_and_wait(command, **kwargs):
    """Run something to completion and return the closing message."""
    runner = core.Runner()
    finished = []
    runner.start(command, on_line=lambda line: None, on_finished=finished.append, **kwargs)

    for _ in range(200):
        if finished:
            return finished[0]
        time.sleep(0.05)

    raise AssertionError("the runner never finished")


def test_success_and_failure_are_told_apart():
    assert "Finished" in run_and_wait(["cmd", "/c", "exit 0"])
    assert "exit code 3" in run_and_wait(["cmd", "/c", "exit 3"])


def test_a_command_that_cannot_start_is_reported():
    assert "Could not run" in run_and_wait(["definitely_not_a_real_program_xyz"])


def test_output_is_streamed_line_by_line():
    runner = core.Runner()
    lines, finished = [], []
    runner.start(["cmd", "/c", "echo one& echo two"], on_line=lines.append,
                 on_finished=finished.append)
    for _ in range(200):
        if finished:
            break
        time.sleep(0.05)
    assert [line.strip() for line in lines] == ["one", "two"]


def test_stop_kills_the_whole_tree():
    runner = core.Runner()
    finished = []
    runner.start("ping -n 30 127.0.0.1", on_line=lambda line: None,
                 on_finished=finished.append, shell=True)

    for _ in range(100):
        if runner.running:
            break
        time.sleep(0.05)
    assert runner.running

    assert runner.stop() is True

    for _ in range(200):
        if finished:
            break
        time.sleep(0.05)

    assert "Stopped" in finished[0]
    assert not runner.running

    # the shell was killed, and so was the ping it had started
    time.sleep(0.5)
    running = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq PING.EXE"], capture_output=True, text=True
    ).stdout
    assert "PING.EXE" not in running.upper()


def test_stopping_nothing_is_harmless():
    assert core.Runner().stop() is False


# ==================================================
# SETTINGS
# ==================================================


def test_missing_keys_are_filled_in():
    settings = core.load_settings()
    for key in core.DEFAULT_SETTINGS:
        assert key in settings


def test_settings_live_in_a_settings_folder_at_the_app_root():
    assert core.settings_dir() == os.path.join(core.app_dir(), "settings")
    assert core.settings_path() == os.path.join(core.settings_dir(), "settings.json")


def test_the_app_root_is_the_project_folder_not_src():
    source_folder = os.path.dirname(os.path.abspath(core.__file__))
    assert core.app_dir() == os.path.dirname(source_folder)
    assert core.settings_dir() != os.path.join(source_folder, "settings")


def test_asking_for_the_settings_folder_does_not_create_it():
    # A packaged app nobody has customised must not litter the folder it sits in
    import shutil as _shutil, tempfile

    scratch = tempfile.mkdtemp()
    try:
        with frozen_as(scratch, scratch):
            folder = core.settings_dir()
            assert not os.path.exists(folder)
            core.load_settings()
            assert not os.path.exists(folder), "loading settings created the folder"

            core.save_settings({"theme": "light"})
            assert os.path.isdir(folder), "saving should create it"
    finally:
        _shutil.rmtree(scratch, ignore_errors=True)


def test_a_frozen_build_reads_settings_out_of_the_bundle():
    import json as _json, shutil as _shutil, tempfile

    bundle = tempfile.mkdtemp()
    app = tempfile.mkdtemp()
    os.makedirs(os.path.join(bundle, "settings"))
    with open(os.path.join(bundle, "settings", "settings.json"), "w") as f:
        _json.dump({"theme": "light", "download_folder": r"D:\Shipped"}, f)

    try:
        with frozen_as(bundle, app):
            settings = core.load_settings()
            # the bundled values are used...
            assert settings["theme"] == "light"
            assert settings["download_folder"] == r"D:\Shipped"
            # ...a key the bundle omits still falls back to the built-in default
            assert settings["allow_custom_command"] is False
            # ...and nothing was written beside the executable
            assert not os.path.exists(os.path.join(app, "settings"))
    finally:
        _shutil.rmtree(bundle, ignore_errors=True)
        _shutil.rmtree(app, ignore_errors=True)


def test_a_saved_setting_overrides_the_bundled_one():
    import json as _json, shutil as _shutil, tempfile

    bundle = tempfile.mkdtemp()
    app = tempfile.mkdtemp()
    os.makedirs(os.path.join(bundle, "settings"))
    with open(os.path.join(bundle, "settings", "settings.json"), "w") as f:
        _json.dump({"theme": "light"}, f)

    try:
        with frozen_as(bundle, app):
            core.save_settings(dict(core.load_settings(), theme="dark"))
            assert core.load_settings()["theme"] == "dark"
    finally:
        _shutil.rmtree(bundle, ignore_errors=True)
        _shutil.rmtree(app, ignore_errors=True)


def test_loading_with_no_file_writes_the_defaults():
    saved = None
    if os.path.exists(core.settings_path()):
        with open(core.settings_path(), encoding="utf-8") as f:
            saved = f.read()
        os.remove(core.settings_path())

    try:
        settings = core.load_settings()
        # the file now exists instead of appearing only on the first change
        assert os.path.isfile(core.settings_path())
        assert settings == core.DEFAULT_SETTINGS
    finally:
        if saved is not None:
            with open(core.settings_path(), "w", encoding="utf-8") as f:
                f.write(saved)


def test_the_default_download_folder_ignores_the_working_directory():
    # It is persisted on first run, so it must not depend on where you launched
    assert core.DEFAULT_SETTINGS["download_folder"] == core.app_dir()


def test_settings_are_not_resolved_against_the_working_directory():
    # Otherwise launching the app from elsewhere would start from blank settings
    assert os.path.isabs(core.settings_path())


# ==================================================
# RUNNING WITHOUT PYTEST
# ==================================================

if __name__ == "__main__":
    failures = 0
    for name, test in sorted(globals().items()):
        if name.startswith("test_") and callable(test):
            try:
                test()
                print(f"  ok   {name}")
            except AssertionError as error:
                failures += 1
                print(f"  FAIL {name}: {error}")

    print(f"\n{'all tests passed' if not failures else f'{failures} failed'}")
    sys.exit(1 if failures else 0)
