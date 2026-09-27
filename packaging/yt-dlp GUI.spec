# -*- mode: python ; coding: utf-8 -*-
#
# Generated with:
#   pyi-makespec --onefile --windowed --name "yt-dlp GUI" --paths src \
#     --add-data "bin/yt-dlp.exe;." --add-data "settings/settings.json;." \
#     --specpath packaging src/ytdlp_qt_gui.py
#
# Build from the project root with:
#   pyinstaller "packaging/yt-dlp GUI.spec"
#
# Paths below are relative to this file's own folder (packaging/), which is
# how PyInstaller resolves a .spec regardless of the current working
# directory — hence the leading "../".

# The app only ever imports QtCore/QtGui/QtWidgets (see ytdlp_qt_gui.py), but
# PySide6's own PyInstaller hook pulls in a lot more than that by default —
# QML, Quick, the virtual keyboard, Pdf, Svg, OpenGL, Network — none of which
# this app uses. Excluding them cuts a large, unnecessary chunk out of both
# the Analysis graph (faster build) and the final .exe (faster startup, since
# a --onefile build re-extracts its payload on every launch). If a future
# change starts using one of these (e.g. QtSvg for an icon), drop it from
# this list rather than working around a mysterious missing-module error.
UNUSED_QT_MODULES = [
    'PySide6.QtNetwork',
    'PySide6.QtQml',
    'PySide6.QtQuick',
    'PySide6.QtQuickWidgets',
    'PySide6.QtVirtualKeyboard',
    'PySide6.QtPdf',
    'PySide6.QtPdfWidgets',
    'PySide6.QtSvg',
    'PySide6.QtSvgWidgets',
    'PySide6.QtOpenGL',
    'PySide6.QtOpenGLWidgets',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtPositioning',
    'PySide6.QtSensors',
    'PySide6.QtBluetooth',
    'PySide6.QtNfc',
    'PySide6.QtSerialPort',
    'PySide6.QtTest',
    'PySide6.QtDesigner',
    'PySide6.QtHelp',
]

a = Analysis(
    ['../src/ytdlp_qt_gui.py'],
    pathex=['../src'],
    binaries=[],
    datas=[('../bin/yt-dlp.exe', '.'), ('../settings/settings.json', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=UNUSED_QT_MODULES,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='yt-dlp GUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX only compresses the binary to save disk space — it doesn't skip
    # anything, so it adds time to every build (compressing) and to every
    # launch (decompressing on top of --onefile's own extraction). Not worth
    # it here: this .exe is already a copy that's meant to be discarded and
    # rebuilt often, not a release artifact optimized for download size.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
