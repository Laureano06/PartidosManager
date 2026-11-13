"""Ejecuta el código corregido con la configuración de una instalación existente."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import uvicorn

if __name__ == "__main__":
    project = Path(sys.argv[1]).resolve()
    os.chdir(project)
    load_dotenv(project / ".env")
    os.environ.setdefault("PARTIDOS_STATIC_DIR", str(project / "static"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    uvicorn.run("main:app", host="127.0.0.1", port=8000)
