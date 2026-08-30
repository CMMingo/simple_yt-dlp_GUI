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

a = Analysis(
    ['../src/ytdlp_qt_gui.py'],
    pathex=['../src'],
    binaries=[],
    datas=[('../bin/yt-dlp.exe', '.'), ('../settings/settings.json', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
