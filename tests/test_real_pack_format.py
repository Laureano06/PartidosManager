import io
import json
import os
import unittest
import zipfile

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
from pack_engine import importar_pmpack, PmpackInvalido
from pack_formats import adaptar_proveedor


def provider_pack():
    return {
        "manifest.json": {"name": "Datos reales", "createdAt": "2026-09-05T12:00:00Z"},
        "database/ligas.json": {"leagues": [{"id": "argentina", "name": "Liga real"}]},
        "database/clubes.json": {"clubs": [{"id": 10, "league_id": "argentina", "name": "Club real", "badge": "assets/teams/10.svg", "city": "Ciudad"}]},
        "database/jugadores.json": {"players": [{"id": 20, "team_id": 10, "name": "Jugador real", "position": "D", "specific_position": "RB", "date_of_birth": "2000-09-06", "nationality": "Argentina", "image": "assets/players/20.svg", "height_cm": 180, "preferred_foot": "R"}]},
        "database/competencias.json": {"competitions": [{"id": "argentina", "name": "Liga real"}, {"id": 7, "name": "Champions League"}]},
        "database/configuracion.json": {"solo_clubes_pack": True, "rellenar_planteles": False},
    }


def zip_data(data):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, value in data.items():
            z.writestr(name, json.dumps(value))
        z.writestr("assets/teams/10.svg", b"<svg/>")
        z.writestr("assets/players/20.svg", b'<svg id="player"/>')
    return buffer.getvalue()


class ProviderTests(unittest.TestCase):
    def test_import_provider_and_preserve_extra_fields(self):
        saved = []
        def save(content, ext):
            saved.append(content)
            return f"/static/escudos/{len(saved)}{ext}"
        result = importar_pmpack(zip_data(provider_pack()), save)
        self.assertEqual(result["nombres_clubes"]["ARG1"][0][0], "10")
        self.assertEqual(result["nombres_clubes"]["ARG1"][0][3], "Liga real")
        p = result["jugadores_clubes"]["ARG1"]["10"][0]
        self.assertEqual((p["edad"], p["posicion"], p["posicion_especifica"]), (25, "DEF", "DFD"))
        self.assertEqual(p["datos_fuente"]["height_cm"], 180)
        self.assertTrue(p["datos_fuente"]["image"].startswith("/static/escudos/"))
        self.assertEqual(result["competencias"]["CAMPEONES_UEFA"], "Champions League")
        self.assertFalse(result["configuracion"]["rellenar_planteles"])
        self.assertEqual(result["metadata_clubes"]["ARG1"]["10"]["ciudad"], "Ciudad")

    def test_missing_players_warn_instead_of_inventing(self):
        data = provider_pack()
        data["database/jugadores.json"]["players"] = []
        result = importar_pmpack(zip_data(data), lambda *_: "/static/escudos/a.svg")
        self.assertEqual(result["conteos"]["numberOfPlayers"], 0)
        self.assertTrue(any("no contiene jugadores" in a for a in result["avisos"]))

    def test_bad_membership_and_duplicates_rejected(self):
        for issue in ("orphan", "duplicate"):
            data = provider_pack()
            p = data["database/jugadores.json"]["players"][0]
            if issue == "orphan": p["team_id"] = 999
            else: data["database/jugadores.json"]["players"].append(dict(p))
            with self.assertRaises(PmpackInvalido):
                importar_pmpack(zip_data(data), lambda *_: self.fail("No debe guardar assets inválidos"))

    def test_missing_age_and_position_are_marked(self):
        data = provider_pack()
        p = data["database/jugadores.json"]["players"][0]
        p["date_of_birth"], p["position"] = None, ""
        result = importar_pmpack(zip_data(data), lambda *_: "/static/escudos/a.svg")
        estimate = result["configuracion"]["estimaciones"]
        self.assertEqual((estimate["edades"], estimate["posiciones"]), (1, 1))


class StrictCareerTests(unittest.IsolatedAsyncioTestCase):
    async def test_incomplete_real_roster_is_rejected_without_filling(self):
        from main import crear_partida_endpoint
        from fastapi import HTTPException
        data = importar_pmpack(zip_data(provider_pack()), lambda *_: "/static/escudos/a.svg")
        with self.assertRaises(HTTPException) as raised:
            await crear_partida_endpoint({"dataset": "personalizada", "nombres_clubes_custom": data["nombres_clubes"],
                                          "jugadores_clubes_custom": data["jugadores_clubes"],
                                          "configuracion_pack": data["configuracion"]}, None)
        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("menos de 11", raised.exception.detail)
