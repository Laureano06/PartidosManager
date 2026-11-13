"""Convierte y verifica un pack externo mediante el mismo motor que usa el editor."""
import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
from models import PaqueteClubes
from pack_engine import importar_pmpack, exportar_pmpack


def convert(source, output):
    with tempfile.TemporaryDirectory() as tmp:
        assets = Path(tmp)
        def save(data, ext):
            name = hashlib.sha256(data).hexdigest() + ext
            (assets / name).write_bytes(data)
            return "/static/escudos/" + name
        data = importar_pmpack(source.read_bytes(), save)
        p = PaqueteClubes(pack_id="partidos-9ligas-realdata", nombre=data["manifest"]["name"],
                         version="1.1.0", autor=data["manifest"].get("author", ""),
                         descripcion=data["manifest"].get("description", ""),
                         nombres_json=json.dumps(data["nombres_clubes"]), jugadores_json=json.dumps(data["jugadores_clubes"]),
                         competencias_json=json.dumps(data["competencias"]), metadata_clubes_json=json.dumps(data["metadata_clubes"]),
                         configuracion_json=json.dumps(data["configuracion"]))
        packed = exportar_pmpack(p, assets)
        check = importar_pmpack(packed, save)
        assert check["conteos"] == data["conteos"]
        assert check["jugadores_clubes"] == data["jugadores_clubes"]
        assert check["nombres_clubes"] == data["nombres_clubes"]
        assert check["metadata_clubes"] == data["metadata_clubes"]
        assert check["configuracion"] == data["configuracion"]
        output.write_bytes(packed)
        print(json.dumps({"output": str(output), **check["conteos"], "warnings": data["avisos"],
                          "estimaciones": data["configuracion"].get("estimaciones")}, ensure_ascii=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    convert(args.source, args.output)
