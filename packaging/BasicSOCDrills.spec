# PyInstaller spec for Basic SOC Drills (Windows onefile build)
# Build with:  pyinstaller packaging/BasicSOCDrills.spec
#
# Produces dist/BasicSOCDrills.exe which the MSIX packaging step
# (packaging/build_msix.ps1) then wraps into .msix / .appx.

# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "soc_drills"), "soc_drills"),
    ],
    hiddenimports=["tkinter", "queue", "threading", "subprocess"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="BasicSOCDrills",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "packaging" / "icons" / "icon.ico")
    if (ROOT / "packaging" / "icons" / "icon.ico").exists()
    else None,
    # NOTE ON ELEVATION:
    # This intentionally does NOT set an app manifest that
    # auto-elevates (requireAdministrator) on launch. The app starts
    # at standard user privileges, shows the consent dialog
    # (soc_drills/consent.py), and only the individual subprocess
    # calls that need admin rights trigger a UAC prompt at the point
    # of use (see soc_drills/backend.py run_command()). That keeps
    # elevation scoped to the specific action the user chose to run,
    # instead of elevating the whole GUI process for its entire
    # lifetime.
    uac_admin=False,
    uac_uiaccess=False,
)
