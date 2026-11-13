"""Incorpora caras de jugadores del proveedor al interior de un PMPack."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_IMAGEN = "https://sports.bzzoiro.com/img/player/{}/?sor=true&bg=transparent"
EXTENSIONES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


def _id_jugador(jugador: dict) -> str | None:
    fuente = jugador.get("datos_fuente")
    if not isinstance(fuente, dict):
        return None
    valor = fuente.get("id") or fuente.get("player_id")
    return str(valor).strip() if valor is not None and str(valor).strip() else None


def _descargar(identificador: str, timeout: int) -> tuple[str, bytes, str] | None:
    try:
        solicitud = Request(BASE_IMAGEN.format(identificador), headers={"User-Agent": "PARTIDOS-PMPack/1.0"})
        with urlopen(solicitud, timeout=timeout) as respuesta:
            tipo = respuesta.headers.get_content_type().lower()
            contenido = respuesta.read()
        extension = EXTENSIONES.get(tipo)
        if not extension or not contenido:
            return None
        return identificador, contenido, extension
    except (HTTPError, URLError, TimeoutError):
        return None


def enriquecer_caras(origen: Path, destino: Path, trabajadores: int = 3, limite: int | None = None, timeout: int = 8) -> tuple[int, int]:
    with zipfile.ZipFile(origen, "r") as entrada:
        nombres = [info.filename for info in entrada.infolist() if not info.is_dir()]
        jugadores = json.loads(entrada.read("database/jugadores.json"))
        por_id: dict[str, list[dict]] = {}
        for liga in jugadores.values():
            for plantel in liga.values():
                for jugador in plantel:
                    identificador = _id_jugador(jugador)
                    if identificador and not jugador.get("foto_url"):
                        por_id.setdefault(identificador, []).append(jugador)
        ids = list(por_id)
        if limite is not None:
            ids = ids[:limite]
        destino.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(delete=False, dir=destino.parent, suffix=".pmpack") as temporal:
            ruta_temporal = Path(temporal.name)
        try:
            with zipfile.ZipFile(ruta_temporal, "w", compression=zipfile.ZIP_DEFLATED) as salida:
                for nombre in nombres:
                    if nombre != "database/jugadores.json":
                        salida.writestr(nombre, entrada.read(nombre))
                cargadas = 0
                with ThreadPoolExecutor(max_workers=max(1, trabajadores)) as executor:
                    futuros = [executor.submit(_descargar, identificador, timeout) for identificador in ids]
                    procesadas = 0
                    for futuro in as_completed(futuros):
                        procesadas += 1
                        if procesadas % 100 == 0:
                            print(f"Progreso caras: {procesadas}/{len(ids)}", flush=True)
                        resultado = futuro.result()
                        if not resultado:
                            continue
                        identificador, contenido, extension = resultado
                        ruta = f"assets/players/{identificador}{extension}"
                        salida.writestr(ruta, contenido)
                        for jugador in por_id[identificador]:
                            jugador["foto_url"] = ruta
                        cargadas += 1
                salida.writestr("database/jugadores.json", json.dumps(jugadores, ensure_ascii=False))
            os.replace(ruta_temporal, destino)
            return cargadas, len(ids)
        except Exception:
            ruta_temporal.unlink(missing_ok=True)
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("origen", type=Path)
    parser.add_argument("destino", type=Path)
    parser.add_argument("--trabajadores", type=int, default=3)
    parser.add_argument("--limite", type=int)
    parser.add_argument("--timeout", type=int, default=8)
    args = parser.parse_args()
    cargadas, intentadas = enriquecer_caras(args.origen, args.destino, args.trabajadores, args.limite, args.timeout)
    print(f"Caras incorporadas: {cargadas}/{intentadas}")
