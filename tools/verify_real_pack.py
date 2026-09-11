"""Verifica el pack completo usando endpoints y SQLite en memoria, sin alterar partidas."""
import argparse
import asyncio
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
from sqlalchemy import select, func
from database import Base, engine, AsyncSessionLocal
from models import Equipo, Jugador, Liga, PaqueteClubes
from pack_engine import importar_pmpack, exportar_pmpack
from main import (confirmar_importar_pmpack, crear_partida_endpoint, obtener_paquete_clubes,
                  actualizar_jugador_paquete, actualizar_club_paquete, duplicar_paquete_clubes)


async def verify(path):
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        def save(content, ext):
            name = hashlib.sha256(content).hexdigest() + ext
            (root / name).write_bytes(content)
            return "/static/escudos/" + name
        payload = importar_pmpack(path.read_bytes(), save)
        counts = payload["conteos"]
        assert counts["numberOfClubs"] == 178 and counts["numberOfLeagues"] == 9
        assert payload["configuracion"]["rellenar_planteles"] is False
        for clubs in payload["nombres_clubes"].values():
            for club in clubs:
                assert club[2].startswith("/static/escudos/")
                content = (root / club[2].rsplit("/", 1)[-1]).read_bytes()
                assert content.startswith((b"\x89PNG", b"\xff\xd8\xff", b"RIFF", b"<svg", b"<?xml"))
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with AsyncSessionLocal() as db:
            installed = await confirmar_importar_pmpack(payload, db)
            pid = installed["id_paquete"]
            detail = await obtener_paquete_clubes(pid, db)
            assert detail["configuracion"] == payload["configuracion"]
            league = "ARG1"
            club = detail["nombres_clubes"][league][0]
            code, name = club[:2]
            player = detail["jugadores_clubes"][league][code][0]
            source = player["datos_fuente"]
            await actualizar_jugador_paquete(pid, league, code, 0, {"nombre": player["nombre"], "posicion": player["posicion"], "defensa": 0}, db)
            meta = detail["metadata_clubes"][league][code]
            await actualizar_club_paquete(pid, league, code, {"nombre": name, "escudo_url": club[2], "nombre_competencia": club[3], "ciudad": "Prueba editable"}, db)
            edited = await obtener_paquete_clubes(pid, db)
            assert edited["jugadores_clubes"][league][code][0]["datos_fuente"] == source
            assert edited["jugadores_clubes"][league][code][0]["defensa"] == 0
            assert edited["metadata_clubes"][league][code]["datos_fuente"] == meta["datos_fuente"]
            # Restaurar atributos para probar la carrera con el contenido original.
            await actualizar_jugador_paquete(pid, league, code, 0, player, db)
            duplicate = await duplicar_paquete_clubes(pid, db)
            copy = await obtener_paquete_clubes(duplicate["id_paquete"], db)
            assert copy["configuracion"] == detail["configuracion"]
            original = await db.get(PaqueteClubes, pid)
            roundtrip = importar_pmpack(exportar_pmpack(original, root), save)
            assert roundtrip["conteos"] == counts
            print("Importación, edición, duplicado y exportación: OK", flush=True)
            career = await crear_partida_endpoint({"dataset": "personalizada", "id_paquete_clubes": str(pid), "nombre_dt": "Prueba pack",
                                                    "codigo_liga": league, "nombre_club": name, "ligas_completas": [league]}, db)
            cid = career["id_partida"]
            actual_clubs = (await db.execute(select(func.count()).select_from(Equipo).where(Equipo.id_partida == cid))).scalar_one()
            actual_players = (await db.execute(select(func.count()).select_from(Jugador).where(Jugador.id_partida == cid))).scalar_one()
            actual_leagues = (await db.execute(select(func.count()).select_from(Liga).where(Liga.id_partida == cid))).scalar_one()
            assert (actual_clubs, actual_players, actual_leagues) == (counts["numberOfClubs"], counts["numberOfPlayers"], counts["numberOfLeagues"])
            without_source = (await db.execute(select(func.count()).select_from(Jugador).where(Jugador.id_partida == cid, Jugador.datos_pack_json.is_(None)))).scalar_one()
            assert without_source == 0
            teams = (await db.execute(select(Equipo).where(Equipo.id_partida == cid))).scalars().all()
            for team in teams:
                assert team.escudo_url and team.datos_pack["datos_fuente"]["id"]
            print(json.dumps({"career": "OK", "clubs": actual_clubs, "players": actual_players, "leagues": actual_leagues, "fictitious_players_added": without_source}), flush=True)
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pack", type=Path)
    args = parser.parse_args()
    asyncio.run(verify(args.pack))
