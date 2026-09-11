import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

# No lifespan, .env ni bases persistentes: todas las pruebas usan SQLite en memoria.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

import pack_engine as packs
from database import Base, engine, AsyncSessionLocal
from models import PaqueteClubes, Equipo, Jugador
from sqlalchemy import select


def jugador(nombre="Jugador de prueba"):
    return dict(nombre=nombre, posicion="DEL", edad=24, ataque=80, defensa=0, pase=65, fisico=78)


def archivo(clubes, jugadores=None, assets=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("manifest.json", json.dumps({"name": "Prueba", "version": "1.0.0"}))
        z.writestr("database/clubes.json", json.dumps(clubes))
        if jugadores is not None:
            z.writestr("database/jugadores.json", jugadores if isinstance(jugadores, str) else json.dumps(jugadores))
        for ruta, contenido in (assets or {}).items():
            z.writestr(ruta, contenido)
    return buffer.getvalue()


class PackTests(unittest.TestCase):
    def test_roundtrip_selecciones_file(self):
        with tempfile.TemporaryDirectory() as temp:
            paquete = PaqueteClubes(
                nombre="Internacional", nombres_json=json.dumps({"ARG1": [["BOC", "Club"]]}),
                configuracion_json=json.dumps({"selecciones": {"equipos": [
                    {"codigo": "ARG", "nombre": "Argentina", "pais": "Argentina", "categoria": "MAYOR"}
                ]}}),
            )
            contenido = packs.exportar_pmpack(paquete, Path(temp))
            with zipfile.ZipFile(io.BytesIO(contenido)) as archivo_zip:
                self.assertIn("database/selecciones.json", archivo_zip.namelist())
            resultado = packs.importar_pmpack(contenido, lambda *_: "/static/escudos/a.svg")
            self.assertEqual(resultado["configuracion"]["selecciones"]["equipos"][0]["codigo"], "ARG")

    def test_csv_quotes_headers_and_keys(self):
        clubes = packs._parsear_csv_clubes('\ufeffLIGA,CODIGO,NOMBRE\narg1,boc,"Club, Prueba"')
        jugadores = packs._parsear_csv_jugadores('LIGA,CODIGO_CLUB,NOMBRE,POSICION,POSICION_ESPECIFICA,NACIONALIDAD,EDAD,ATAQUE,DEFENSA,PASE,FISICO\nARG1,BOC,"Apellido, Nombre",del,DC,,24,80,0,65,78')
        clubes, jugadores = packs.validar_datos_pack(clubes, jugadores)
        self.assertEqual(clubes, {"ARG1": [["BOC", "Club, Prueba"]]})
        self.assertEqual(jugadores["ARG1"]["BOC"][0]["nombre"], "Apellido, Nombre")
        self.assertEqual(jugadores["ARG1"]["BOC"][0]["defensa"], 0)

    def test_roundtrip_badges_do_not_collide_between_leagues(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "one.svg").write_text('<svg id="one"/>')
            (root / "two.svg").write_text('<svg id="two"/>')
            clubes = {"ARG1": [["ABC", "Uno", "/static/escudos/one.svg"]], "BRA1": [["ABC", "Dos", "/static/escudos/two.svg"]]}
            jugadores = {"ARG1": {"ABC": [jugador()]}}
            paquete = PaqueteClubes(nombre="Prueba", nombres_json=json.dumps(clubes), jugadores_json=json.dumps(jugadores))
            contenido = packs.exportar_pmpack(paquete, root)
            saved = []
            def guardar(data, ext):
                saved.append(data)
                return f"/static/escudos/{len(saved)}{ext}"
            resultado = packs.importar_pmpack(contenido, guardar)
            self.assertEqual(saved, [b'<svg id="one"/>', b'<svg id="two"/>'])
            self.assertNotEqual(resultado["nombres_clubes"]["ARG1"][0][2], resultado["nombres_clubes"]["BRA1"][0][2])
            self.assertEqual(resultado["jugadores_clubes"], jugadores)
            self.assertEqual(json.loads(paquete.nombres_json), clubes)

    def test_legacy_asset(self):
        result = packs.importar_pmpack(archivo({"ARG1": [["BOC", "Club"]]}, assets={"assets/BOC.svg": b"<svg/>"}), lambda *_: "/static/escudos/imported.svg")
        self.assertEqual(result["nombres_clubes"]["ARG1"][0][2], "/static/escudos/imported.svg")

    def test_bad_players_json_is_pack_error(self):
        with self.assertRaises(packs.PmpackInvalido):
            packs.importar_pmpack(archivo({"ARG1": [["BOC", "Club"]]}, "{broken"), lambda *_: self.fail("No debe guardar assets"))

    def test_orphan_players_are_rejected_before_assets(self):
        with self.assertRaisesRegex(packs.PmpackInvalido, "no tienen un club"):
            packs.importar_pmpack(archivo({"ARG1": [["BOC", "Club"]]}, {"ARG1": {"OTRO": [jugador()]}}, {"assets/BOC.svg": b"<svg/>"}), lambda *_: self.fail("No debe guardar assets"))

    def test_bundled_csv_coverage(self):
        root = Path(__file__).resolve().parents[1] / "fixtures_prueba"
        clubes = packs._parsear_csv_clubes((root / "clubes_prueba.csv").read_text(encoding="utf-8"))
        jugadores = packs._parsear_csv_jugadores((root / "jugadores_prueba.csv").read_text(encoding="utf-8"))
        clubes, jugadores = packs.validar_datos_pack(clubes, jugadores)
        self.assertEqual(packs.contar_entidades(clubes, jugadores)["numberOfPlayers"], 81)

    def test_invalid_position_is_rejected(self):
        data = jugador()
        data["posicion"] = "invalid"
        with self.assertRaisesRegex(packs.PmpackInvalido, "Posición inválida"):
            packs.validar_datos_pack({"ARG1": [["BOC", "Club"]]}, {"ARG1": {"BOC": [data]}})


class CareerTests(unittest.IsolatedAsyncioTestCase):
    async def test_api_rejects_orphan_players_before_saving(self):
        from main import crear_paquete_clubes, confirmar_importar_pmpack
        from fastapi import HTTPException
        payload = {"nombre": "Prueba", "nombres_clubes": {"ARG1": [["BOC", "Club"]]}, "jugadores_clubes": {"ARG1": {"OTRO": [jugador()]}}}
        for endpoint in (crear_paquete_clubes, confirmar_importar_pmpack):
            with self.assertRaises(HTTPException) as raised:
                await endpoint(payload, None)
            self.assertEqual(raised.exception.status_code, 400)

    async def test_import_confirm_and_career_preserve_player_and_badge(self):
        from main import confirmar_importar_pmpack, crear_partida_endpoint
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        payload = packs.importar_pmpack(archivo(
            {"arg1": [["boc", "Club de prueba"], ["riv", "Rival de prueba"]]},
            {"ARG1": {"BOC": [jugador()]}}, {"assets/BOC.svg": b"<svg/>"},
        ), lambda *_: "/static/escudos/prueba.svg")
        async with AsyncSessionLocal() as db:
            creado = await confirmar_importar_pmpack(payload, db)
            carrera = await crear_partida_endpoint({"dataset": "personalizada", "id_paquete_clubes": str(creado["id_paquete"]), "codigo_liga": "ARG1", "nombre_club": "Club de prueba", "ligas_completas": ["ARG1"]}, db)
            equipo = (await db.execute(select(Equipo).where(Equipo.id_partida == carrera["id_partida"], Equipo.nombre == "Club de prueba"))).scalar_one()
            self.assertEqual(equipo.escudo_url, "/static/escudos/prueba.svg")
            real = (await db.execute(select(Jugador).where(Jugador.id_equipo == equipo.id_equipo, Jugador.nombre == "Jugador de prueba"))).scalar_one()
            self.assertEqual(real.posicion, "DEL")
            self.assertEqual(real.edad, 24)
        await engine.dispose()
