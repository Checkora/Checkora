"""Prepare Checkora assets for Vercel builds."""

from pathlib import Path
import os
import shutil
import subprocess


def main():
    public_dir = Path("public")
    public_dir.mkdir(exist_ok=True)
    (public_dir / "placeholder.html").write_text("", encoding="utf-8")

    compiler = shutil.which("g++")
    if not compiler:
        print("No g++, using Python engine")
        return

    output_path = Path("game/engine/main")
    try:
        subprocess.check_call(
            [
                compiler,
                "-O2",
                "-std=c++17",
                "game/engine/main.cpp",
                "-o",
                str(output_path),
            ]
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"C++ engine build failed, using Python engine: {exc}")
        return

    if os.name != "nt":
        output_path.chmod(0o755)


if __name__ == "__main__":
    main()
