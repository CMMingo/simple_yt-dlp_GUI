"""
yt-dlp GUI – Tkinter version
"""


# ==================================================
# IMPORTS
# ==================================================

import json  # Read/write settings to disk
import os  # File system utilities (paths, cwd)
import queue  # Thread-safe communication with GUI
import re  # Parse the download percentage out of yt-dlp output
import shutil  # Locate ffmpeg on PATH
import subprocess  # Run external programs (yt-dlp)
import threading  # Run long tasks without freezing GUI
import tkinter as tk  # Base GUI library (windows, widgets, events)
from tkinter import (
    filedialog,  # Native folder picker dialog
    messagebox,  # Popup dialogs (errors, warnings)
    ttk,  # Modern themed widgets (buttons, frames, etc.)
)

# ==================================================
# SETTINGS FILE MANAGEMENT
# ==================================================

# This script lives in deprecated/, so the project folder is one level up. The
# settings folder is shared with the Qt app: same file, same three keys
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_DIR = os.path.join(PROJECT_DIR, "settings")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "theme": "dark",
    # The project folder, not the working directory: the defaults are written
    # out on first run, so a cwd-dependent value would be baked in permanently
    "download_folder": PROJECT_DIR,
    "allow_custom_command": False,
}


# Write the given settings to disk, creating the folder if it is not there
def write_settings(data):
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


# Load settings from disk, filling in any key the file does not contain
def load_settings():
    settings = DEFAULT_SETTINGS.copy()

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings.update(json.load(f))
    except (OSError, ValueError):
        # Nothing readable yet: write the defaults so the file always exists
        write_settings(settings)

    return settings


# Save current settings to disk
def save_settings():
    write_settings(
        {
            "theme": current_theme.get(),
            "download_folder": download_path.get(),
            "allow_custom_command": allow_command_var.get(),
        }
    )


# Load settings immediately at startup
settings = load_settings()


# ==================================================
# ENSURE yt-dlp IS AVAILABLE & UPDATED
# ==================================================

yt_dlp_path = os.path.join(os.path.dirname(__file__), "yt-dlp.exe")
if not os.path.exists(yt_dlp_path):
    # This script now lives in deprecated/, so also look in the project folder,
    # and in bin/ where the Qt app keeps its executables
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for candidate in (
        os.path.join(project_dir, "bin", "yt-dlp.exe"),
        os.path.join(project_dir, "yt-dlp.exe"),
    ):
        if os.path.exists(candidate):
            yt_dlp_path = candidate
            break
if not os.path.exists(yt_dlp_path):
    # If yt-dlp is not there, show error and exit. The update itself runs later,
    # with the window already on screen (see start_update)
    messagebox.showerror("Error", "yt-dlp.exe was not found next to this script")
    raise SystemExit


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


# ==================================================
# CUSTOM COMMAND HELPER
# ==================================================


# Kill the process and its children (a shell command spawns its own tree)
def kill_process_tree(process):
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    else:
        process.terminate()


# Point a hand-written `yt-dlp ...` command at the bundled executable
def resolve_custom_command(text):
    command = text.strip()
    for name in ("yt-dlp.exe", "yt-dlp"):
        if command.lower() == name or command.lower().startswith(name + " "):
            return f'"{yt_dlp_path}"' + command[len(name) :]
    return command


# ==================================================
# MAIN APPLICATION WINDOW
# ==================================================

root = tk.Tk()  # main window
root.title("yt-dlp GUI")  # window title
root.geometry("1200x650")  # initial window size
root.minsize(700, 500)  # minimum size (prevents layout breaking)


# ==================================================
# THEME SYSTEM (LIGHT / DARK)
# ==================================================

# ttk styling engine
style = ttk.Style(root)
style.theme_use("clam")  # use a theme that allows color customization

THEMES = {
    "dark": {"bg": "#1e1e1e", "fg": "#ffffff", "entry": "#2d2d2d"},
    "light": {"bg": "#f2f2f2", "fg": "#000000", "entry": "#ffffff"},
}

current_theme = tk.StringVar(value=settings["theme"])  # loaded from settings


# Apply theme colors to all widgets
def apply_theme():
    t = THEMES[current_theme.get()]

    # Window background
    root.configure(bg=t["bg"])
    # ttk widget styles
    style.configure("TFrame", background=t["bg"])
    style.configure("TLabel", background=t["bg"], foreground=t["fg"])
    style.configure("TRadiobutton", background=t["bg"], foreground=t["fg"])
    style.configure("TButton", background="#4a4a4a", foreground=t["fg"])
    style.configure("TEntry", fieldbackground=t["entry"], foreground=t["fg"])
    style.configure(
        "TCombobox", fieldbackground=t["entry"], background=t["entry"], foreground=t["fg"]
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", t["entry"])],
        foreground=[("readonly", t["fg"])],
    )
    # The dropdown list is a plain Tk listbox, styled through the option database
    root.option_add("*TCombobox*Listbox.background", t["entry"])
    root.option_add("*TCombobox*Listbox.foreground", t["fg"])
    root.option_add("*TCombobox*Listbox.selectBackground", "#5c9ded")
    style.configure("Horizontal.TProgressbar", background="#5c9ded")
    # Text widget must be styled manually
    output.configure(bg=t["entry"], fg=t["fg"], insertbackground=t["fg"])

    save_settings()


# ==================================================
# APPLICATION STATE VARIABLES
# ==================================================

download_type = tk.StringVar(value="audio")  # download type (default = audio)
url_var = tk.StringVar()  # URL entered by the user
format_var = tk.StringVar()  # video format selection (advanced)
quality_var = tk.StringVar(value=QUALITY_LABELS[0])  # video quality preset
filename_var = tk.StringVar()  # optional output filename
split_chapters_var = tk.BooleanVar(value=False)  # split the download by chapters
playlist_var = tk.BooleanVar(value=False)  # download every entry of a playlist
command_var = tk.StringVar()  # arbitrary command typed by the user
allow_command_var = tk.BooleanVar(
    value=settings["allow_custom_command"]
)  # whether the custom command box is shown at all
download_path = tk.StringVar(
    value=settings["download_folder"]
)  # download folder (loaded from settings)

process_running = tk.BooleanVar(
    value=False
)  # indicates whether yt-dlp is currently running

current_process = None  # handle of the running process, so it can be stopped
stop_requested = False  # True when the user pressed Stop
updating = False  # True while yt-dlp is updating itself at startup

output_queue = (
    queue.Queue()
)  # queue used to safely move text from background threads to GUI

PROCESS_DONE = object()  # sentinel queued when a process ends


# ==================================================
# NOTEBOOK (TABS)
# ==================================================

# Create tab container
notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)  # make it fill the entire window

# Create individual tabs
main_tab = ttk.Frame(notebook)
settings_tab = ttk.Frame(notebook)

# Add tabs to notebook
notebook.add(main_tab, text="Download")
notebook.add(settings_tab, text="Settings")


# ==================================================
# DOWNLOAD TAB UI
# ==================================================

# Main layout frame
main = ttk.Frame(main_tab, padding=15)
main.pack(fill="both", expand=True)

# ---- Download type ----

ttk.Label(main, text="Download type").pack(anchor="w")

type_frame = ttk.Frame(main)
type_frame.pack(anchor="w", pady=5)

radio_audio = ttk.Radiobutton(
    type_frame, text="Audio (MP3)", variable=download_type, value="audio"
)
radio_video = ttk.Radiobutton(
    type_frame, text="Video (MP4)", variable=download_type, value="video"
)

radio_audio.grid(row=0, column=0, sticky="w")
radio_video.grid(row=0, column=1, sticky="w", padx=(20, 5))

# ---- Video options (shown only for video, packed by validate) ----

video_options = ttk.Frame(main)

ttk.Label(video_options, text="Quality").grid(row=0, column=0, sticky="w")

# Picks the best format up to that height, or the closest quality below it
quality_combo = ttk.Combobox(
    video_options,
    textvariable=quality_var,
    values=QUALITY_LABELS,
    state="readonly",
    width=26,
)
quality_combo.grid(row=0, column=1, padx=(5, 20))

ttk.Label(video_options, text="Advanced").grid(row=0, column=2, sticky="w")

# Overrides the quality preset when filled in
format_entry = ttk.Entry(video_options, textvariable=format_var, width=24)
format_entry.grid(row=0, column=3, padx=(5, 0))

# ---- Split by chapters ----

# yt-dlp downloads the video normally when it has no chapters
split_check = ttk.Checkbutton(
    main,
    text="Split into tracks using the chapters/timestamps of the video",
    variable=split_chapters_var,
)
split_check.pack(anchor="w", pady=(5, 0))

# ---- Playlists ----

# Off: only the video itself, even if the link points into a playlist
ttk.Checkbutton(
    main,
    text="Download the whole playlist",
    variable=playlist_var,
).pack(anchor="w")

# ---- URL ----

ttk.Label(main, text="URL").pack(anchor="w", pady=(10, 0))
ttk.Entry(main, textvariable=url_var).pack(fill="x")

# ---- Filename ----

ttk.Label(main, text="Output filename (optional)").pack(anchor="w", pady=(10, 0))
ttk.Entry(main, textvariable=filename_var, width=40).pack(anchor="w")

# ---- Download folder ----


def choose_folder():
    folder = filedialog.askdirectory()
    if folder:
        download_path.set(folder)
        save_settings()


folder_frame = ttk.Frame(main)
folder_frame.pack(anchor="w", pady=10)

ttk.Label(folder_frame, text="Download folder").pack(side="left")
folder_entry = ttk.Entry(folder_frame, textvariable=download_path, width=45)
folder_entry.pack(side="left", padx=5)
# Persist a hand-typed folder once the user is done editing it
folder_entry.bind("<FocusOut>", lambda _: save_settings())
folder_entry.bind("<Return>", lambda _: save_settings())
ttk.Button(folder_frame, text="Browse", command=choose_folder).pack(side="left")

# ---- Custom command ----

command_frame = ttk.Frame(main)
command_frame.pack(fill="x")

ttk.Label(command_frame, text="Custom command (optional)").pack(anchor="w")
ttk.Entry(command_frame, textvariable=command_var).pack(fill="x")

# ---- Progress bar ----

progress = ttk.Progressbar(main, mode="indeterminate")
progress.pack(fill="x", pady=(10, 0))

# ttk progress bars cannot show text, so keep a label under it
progress_label = ttk.Label(main, text="")
progress_label.pack(anchor="w", pady=(0, 10))

# ---- Output area (VERTICAL SCROLL ONLY) ----

ttk.Label(main, text="Output").pack(anchor="w")

output_frame = ttk.Frame(main)
output_frame.pack(fill="both", expand=True)

scrollbar = ttk.Scrollbar(output_frame, orient="vertical")
scrollbar.pack(side="right", fill="y")

output = tk.Text(
    output_frame,
    wrap="word",  # prevent horizontal scrolling
    yscrollcommand=scrollbar.set,
    height=10,
    state="disabled",
)
output.pack(fill="both", expand=True)
scrollbar.config(command=output.yview)

# ---- DOWNLOAD BUTTON ----

button_frame = ttk.Frame(main)
button_frame.pack(fill="x", pady=10)

download_btn = ttk.Button(button_frame, text="Download")
download_btn.pack(side="left", fill="x", expand=True)

stop_btn = ttk.Button(button_frame, text="Stop", state="disabled")
stop_btn.pack(side="left", padx=(5, 0))


# ==================================================
# SETTINGS TAB UI
# ==================================================

settings_ui = ttk.Frame(settings_tab, padding=20)
settings_ui.pack(fill="both", expand=True)

# Theme selection
ttk.Label(settings_ui, text="Theme").pack(anchor="w")
ttk.Radiobutton(
    settings_ui, text="Dark", variable=current_theme, value="dark", command=apply_theme
).pack(anchor="w")
ttk.Radiobutton(
    settings_ui,
    text="Light",
    variable=current_theme,
    value="light",
    command=apply_theme,
).pack(anchor="w")


# Custom command
def on_allow_command_toggled():
    if allow_command_var.get():
        command_frame.pack(fill="x", before=progress)
    else:
        command_frame.pack_forget()

    save_settings()
    validate()


ttk.Label(settings_ui, text="Custom command").pack(anchor="w", pady=(20, 0))
ttk.Checkbutton(
    settings_ui,
    text="Allow custom command",
    variable=allow_command_var,
    command=on_allow_command_toggled,
).pack(anchor="w")


# ==================================================
# HELPER FUNCTIONS
# ==================================================


# Back to the indeterminate bar, until yt-dlp reports a percentage
def reset_progress():
    progress.stop()
    progress.config(mode="indeterminate", value=0)
    progress_label.config(text="Working...")
    progress.start()


# Feed a yt-dlp output line to the bar. Returns the percentage, if any
def update_progress(line):
    match = PROGRESS_RE.match(line)
    if not match:
        return None

    percent = float(match.group(1))

    if str(progress["mode"]) != "determinate":
        progress.stop()
        progress.config(mode="determinate", maximum=100)

    progress.config(value=percent)
    progress_label.config(text=line.split("]", 1)[1].strip())
    return percent


# Safely append text to output widget
def append_output(text):
    # Progress lines go to the bar instead of flooding the log
    percent = update_progress(text)
    if percent is not None and percent < 100:
        return

    output.configure(state="normal")
    output.insert("end", text)
    output.see("end")
    output.configure(state="disabled")


# The -f value for a video download, or "" when nothing is chosen yet
def format_selector():
    return format_var.get().strip() or QUALITY_SELECTORS.get(quality_var.get(), "")


# Validate UI state and enable/disable button
def validate():
    # Show the quality row only for video
    if download_type.get() == "video":
        video_options.pack(anchor="w", pady=(5, 0), before=split_check)
    else:
        video_options.pack_forget()

    # Without a quality or a format code, the button lists the formats instead
    listing = download_type.get() == "video" and not format_selector()
    download_btn.config(text="List formats" if listing else "Download")

    can_stop = process_running.get() and not updating
    stop_btn.config(state="normal" if can_stop else "disabled")

    # Disable button while process is running
    if process_running.get():
        download_btn.config(state="disabled")
        return

    # Enable button if there is a URL to download or a command to run
    has_command = allow_command_var.get() and command_var.get().strip()
    valid = (download_type.get() and url_var.get().strip()) or has_command
    download_btn.config(state="normal" if valid else "disabled")


# Start a process in the background and lock the UI while it runs
def launch(command, shell=False):
    global stop_requested

    stop_requested = False
    process_running.set(True)
    reset_progress()
    validate()

    # Read the folder here: the worker thread must not touch Tk variables
    cwd = download_path.get() if shell else None

    threading.Thread(
        target=run_process,
        args=(command,),
        kwargs={"shell": shell, "cwd": cwd},
        daemon=True,
    ).start()


# Run yt-dlp without freezing GUI
def run_process(command, shell=False, cwd=None):
    global current_process

    try:
        current_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=shell,
            cwd=cwd,
        )

        for line in current_process.stdout:
            output_queue.put(line)

        code = current_process.wait()

        if stop_requested:
            output_queue.put("\n--- Stopped ---\n")
        elif code == 0:
            output_queue.put("\n--- Finished ---\n")
        else:
            output_queue.put(f"\n--- Failed (exit code {code}) ---\n")

    except OSError as error:
        output_queue.put(f"\n--- Could not run: {error} ---\n")

    finally:
        current_process = None
        # Tkinter is not thread-safe: let the main thread unlock the UI
        output_queue.put(PROCESS_DONE)


# Unlock the UI once the process is gone (runs on the main thread)
def on_process_finished():
    global updating

    updating = False
    process_running.set(False)
    progress.stop()
    progress_label.config(text="")
    validate()


# Stop button action
def stop_download():
    global stop_requested

    process = current_process
    if process is None or process.poll() is not None:
        return

    stop_requested = True
    stop_btn.config(state="disabled")
    append_output("\n--- Stopping ---\n")
    kill_process_tree(process)


# Update yt-dlp with the window already visible, but everything locked
def start_update():
    global updating

    append_output("--- Updating yt-dlp ---\n")
    updating = True
    launch([yt_dlp_path, "--update"])


# Download button action
def start_download():
    # CUSTOM COMMAND: run it verbatim and ignore every other option
    custom_command = command_var.get().strip() if allow_command_var.get() else ""
    if custom_command:
        append_output("\n--- Running custom command ---\n")
        launch(resolve_custom_command(custom_command), shell=True)
        return

    append_output("\n--- Download started ---\n")

    whole_playlist = playlist_var.get()

    base = filename_var.get().strip() or "%(title)s"
    # A fixed name would make every playlist entry overwrite the previous one
    if whole_playlist and filename_var.get().strip():
        base = "%(playlist_index)s - " + base
    output_template = os.path.join(download_path.get(), base + ".%(ext)s")

    common_args = [
        "--newline",  # one progress line at a time, so the bar can be updated
        "--yes-playlist" if whole_playlist else "--no-playlist",
    ]
    if bundled_ffmpeg:
        common_args += ["--ffmpeg-location", bundled_ffmpeg]

    # CHAPTER SPLITTING: yt-dlp keeps the full file and simply downloads it
    # normally when the video has no chapters
    split_args = []
    if split_chapters_var.get():
        chapter_template = os.path.join(
            download_path.get(), "%(section_number)s - %(section_title)s.%(ext)s"
        )
        split_args = [
            "--force-keyframes-at-cut",
            "--split-chapters",
            "-o",
            "chapter:" + chapter_template,
        ]
        append_output("Splitting by chapters (plain download if the video has none)...\n")

    if ffmpeg_path is None:
        append_output(
            "Warning: ffmpeg was not found. Audio extraction, merging and "
            "chapter splitting need it and will fail.\n"
        )

    # AUDIO DOWNLOAD
    if download_type.get() == "audio":
        cmd = [
            yt_dlp_path,
            *common_args,
            *split_args,
            "-x",
            "--audio-format",
            "mp3",
            "-o",
            output_template,
            url_var.get(),
        ]
        launch(cmd)
        return

    # VIDEO: with no quality and no format code, show what is available
    selector = format_selector()
    if not selector:
        append_output("\nListing formats...\n")
        cmd = [yt_dlp_path, *common_args, "-F", url_var.get()]
        launch(cmd)
        return

    # VIDEO: actual download
    cmd = [
        yt_dlp_path,
        *common_args,
        *split_args,
        "-f",
        selector,
        "--merge-output-format",
        "mp4",
        "-o",
        output_template,
        url_var.get(),
    ]

    launch(cmd)


# ==================================================
# INITIALIZATION & EVENT LOOP
# ==================================================

# React to state changes
download_type.trace_add("write", lambda *_: validate())
url_var.trace_add("write", lambda *_: validate())
command_var.trace_add("write", lambda *_: validate())
format_var.trace_add("write", lambda *_: validate())
quality_var.trace_add("write", lambda *_: validate())

# Apply theme once widgets exist
apply_theme()

# Show or hide the custom command box according to the saved setting
on_allow_command_toggled()

# Attach button actions
download_btn.config(command=start_download)
stop_btn.config(command=stop_download)


# Periodically flush output queue
def process_queue():
    while not output_queue.empty():
        item = output_queue.get()
        if item is PROCESS_DONE:
            on_process_finished()
        else:
            append_output(item)
    root.after(100, process_queue)


process_queue()

# Update yt-dlp once the window is on screen, with the UI locked meanwhile
root.after(100, start_update)

# Start Tkinter event loop
root.mainloop()
