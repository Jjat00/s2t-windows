# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for S2T.
Build: uv run pyinstaller s2t.spec
Output: dist/S2T/S2T.exe  (onedir — faster startup, better for an installer)
"""
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

a = Analysis(
    ["src/main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("assets",        "assets"),      # icon.ico, etc.
        ("assets/models", "models"),      # bundled Whisper model
        (".env.example",  "."),           # default config template
        *collect_data_files("silero_vad"),# bundled ONNX model for VAD
    ],
    hiddenimports=[
        # pynput Windows backends
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        # pystray Windows backend
        "pystray._win32",
        # deepgram internals
        "deepgram",
        "websockets",
        "websockets.legacy",
        "websockets.legacy.client",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Test / dev tools
        "pytest", "unittest", "IPython", "jupyter",
        "matplotlib", "scipy", "pandas",
        # torch is no longer used (VAD uses onnxruntime directly, Whisper uses ctranslate2)
        "torch",
        "torchaudio",
        "torchvision",
        "caffe2",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="S2T",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico",
    version="version_info.txt",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=["vcruntime*.dll", "msvcp*.dll", "api-ms-*.dll"],
    name="S2T",
)
