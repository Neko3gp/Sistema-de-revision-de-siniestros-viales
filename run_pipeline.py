from __future__ import annotations

import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"


def main() -> None:
    subprocess.run([sys.executable, "build_outputs.py"], cwd=SRC_DIR, check=True)
    subprocess.run([sys.executable, "pipeline_map.py"], cwd=SRC_DIR, check=True)
    print(f"Mapa generado en: {BASE_DIR / 'outputs' / 'mapa_siniestralidad_chihuahua.html'}")


if __name__ == "__main__":
    main()
