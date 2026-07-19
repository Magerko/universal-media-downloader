# -*- mode: python ; coding: utf-8 -*-
import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

# ffmpeg/ffprobe are fetched into vendor/ at build time and never committed.
# yt-dlp uses ffprobe itself, so unlike SilenceCutter both are shipped.
binaries = []
for tool in ('ffmpeg.exe', 'ffprobe.exe'):
    candidate = os.path.join('vendor', tool)
    if os.path.exists(candidate):
        binaries.append((candidate, '.'))

datas = [('assets', 'assets')]
if os.path.exists('vendor/FFMPEG-LICENSE.txt'):
    datas.append(('vendor/FFMPEG-LICENSE.txt', '.'))

hiddenimports = []

# yt-dlp loads its extractors dynamically, so PyInstaller's import graph sees
# almost none of them. Without this the app builds fine and then fails to
# download from every single site.
hiddenimports += collect_submodules('yt_dlp.extractor')

# curl_cffi ships native libraries and its own CA bundle; certifi backs
# requests. Both go missing unless collected explicitly.
for package in ('curl_cffi', 'certifi'):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'pydoc_data',
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtQml',
        'PyQt6.QtQuick',
        'PyQt6.QtQuick3D',
        'PyQt6.QtMultimedia',
        'PyQt6.QtBluetooth',
        'PyQt6.QtNfc',
        'PyQt6.QtPositioning',
        'PyQt6.QtSensors',
        'PyQt6.QtSerialPort',
        'PyQt6.QtTest',
        'PyQt6.QtCharts',
        'PyQt6.QtDataVisualization',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='UniversalMediaDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX mangles Qt DLLs and is a reliable way to get flagged by antivirus.
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='UniversalMediaDownloader',
)
