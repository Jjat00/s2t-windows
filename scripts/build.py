"""
Build script — genera el instalador de Windows para S2T.

Pasos:
  1. Genera el ícono actualizado
  2. Corre PyInstaller  →  dist/S2T/
  3. Corre Inno Setup   →  dist/installer/S2T-Setup-x.x.x.exe

Uso:
    uv run python scripts/build.py            # PyInstaller + Inno Setup
    uv run python scripts/build.py --no-inno  # solo PyInstaller

Requisito para el instalador:
    Inno Setup 6 instalado en su ubicación por defecto
    https://jrsoftware.org/isdl.php
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
INNO_DEFAULT_PATHS = [
    Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
]


def run(cmd: list, **kwargs):
    print(f"\n>>> {' '.join(str(c) for c in cmd)}\n")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"ERROR: command exited with code {result.returncode}")
        sys.exit(result.returncode)


def find_inno() -> Path | None:
    for p in INNO_DEFAULT_PATHS:
        if p.exists():
            return p
    return None


def main():
    parser = argparse.ArgumentParser(description="Build S2T installer")
    parser.add_argument("--no-inno", action="store_true", help="Skip Inno Setup step")
    args = parser.parse_args()

    # 1. Regenerate icon
    print("=== Step 1: Generate icon ===")
    run([sys.executable, ROOT / "scripts" / "generate_icon.py"])

    # 2. Download Whisper model into assets/models/ (bundled in installer)
    print("=== Step 2: Download Whisper model ===")
    run([sys.executable, ROOT / "scripts" / "download_models.py"])

    # 3. PyInstaller
    print("=== Step 3: PyInstaller ===")
    run(
        [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "s2t.spec"],
        cwd=ROOT,
    )
    dist_dir = ROOT / "dist" / "S2T"
    if not dist_dir.exists():
        print(f"ERROR: expected PyInstaller output at {dist_dir}")
        sys.exit(1)
    print(f"PyInstaller output: {dist_dir}")

    if args.no_inno:
        print("\nBuild complete (no installer). Run the app with:")
        print(f"  {dist_dir / 'S2T.exe'}")
        return

    # 4. Inno Setup
    print("=== Step 4: Inno Setup ===")
    iscc = find_inno()
    if not iscc:
        print("Inno Setup not found. Install it from https://jrsoftware.org/isdl.php")
        print("Or run with --no-inno to skip this step.")
        sys.exit(1)

    installer_out = ROOT / "dist" / "installer"
    installer_out.mkdir(parents=True, exist_ok=True)

    run([iscc, ROOT / "installer" / "setup.iss"])

    installers = list(installer_out.glob("S2T-Setup-*.exe"))
    if installers:
        print(f"\nInstaller ready: {installers[-1]}")
    else:
        print("\nInstaller built (check dist/installer/)")


if __name__ == "__main__":
    main()
