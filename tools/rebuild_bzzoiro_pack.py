"""Recupera planteles actuales; no ejecuta el generador original ni imprime secretos."""
import argparse
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

BASE = "https://sports.bzzoiro.com/api/v2/"


def rebuild(source, output):
    token = dotenv_values(source / ".env").get("BZZOIRO_API_KEY", "")
    if not token:
        raise RuntimeError("Falta la clave del proveedor en la configuración local.")

    def get(endpoint, **params):
        url = BASE + endpoint + ("?" + urllib.parse.urlencode(params) if params else "")
        for attempt in range(3):
            req = urllib.request.Request(url, headers={"Authorization": "Token " + token, "User-Agent": "PARTIDOS-DataImporter/1.1"})
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    result = json.load(response)
                time.sleep(0.15)
                return result
            except urllib.error.HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise RuntimeError(f"Proveedor HTTP {exc.code}: {endpoint}") from None
                time.sleep(min(5 * (attempt + 1), 15))
        raise RuntimeError(f"No se pudo obtener {endpoint}")

    def all_rows(endpoint, key="results", **params):
        rows, offset = [], 0
        while True:
            data = get(endpoint, limit=200, offset=offset, **params)
            page = data if isinstance(data, list) else data.get(key, [])
            rows.extend(page)
            if not isinstance(data, dict) or not data.get("next"):
                return rows
            if not page:
                raise RuntimeError(f"Paginación vacía en {endpoint}")
            offset += len(page)

    with zipfile.ZipFile(source / "PARTIDOS_9Ligas_FullData.pmpack") as previous:
        leagues = json.loads(previous.read("database/ligas.json"))["leagues"]
        old_assets = {n: previous.read(n) for n in previous.namelist() if n.startswith("assets/teams/")}

    clubs, players, competitions, assets, missing_squads, missing_badges = [], [], [], {}, [], []
    player_ids = set()
    for league in leagues:
        lid = league["source_id"]
        season = get(f"leagues/{lid}/season/")
        season = season.get("season", season)
        if not season.get("id"):
            raise RuntimeError(f"No hay temporada identificable para {league['id']}")
        teams = all_rows("teams/", league_id=lid, season_id=season["id"])
        if not teams:
            raise RuntimeError(f"Liga sin equipos: {league['id']}")
        competitions.append({**league, "type": "league", "season": season})
        print(f"{league['id']}: temporada {season['id']}, {len(teams)} clubes", flush=True)
        for team in teams:
            tid = team["id"]
            detail = get(f"teams/{tid}/")
            team = {**team, **detail}
            if team.get("venue_id"):
                team["venue"] = get(f"venues/{team['venue_id']}/")
            badge = f"assets/teams/{tid}.png"
            if badge in old_assets:
                assets[badge] = old_assets[badge]
            else:
                try:
                    req = urllib.request.Request(f"https://sports.bzzoiro.com/img/team/{tid}/", headers={"User-Agent": "PARTIDOS-DataImporter/1.1"})
                    with urllib.request.urlopen(req, timeout=30) as response:
                        assets[badge] = response.read()
                except (urllib.error.URLError, TimeoutError):
                    missing_badges.append(tid)
                    badge = None
            clubs.append({**team, "league_id": league["id"], "badge": badge,
                          "source": {"provider": "Bzzoiro", "team_id": tid}})
            squad = get(f"teams/{tid}/squad/").get("players", [])
            if not squad:
                squad = all_rows("players/", team_id=tid)
            if not squad:
                missing_squads.append({"id": tid, "name": team["name"], "league": league["id"]})
            for player in squad:
                pid = player["id"]
                if pid in player_ids:
                    raise RuntimeError(f"Jugador {pid} aparece en más de un plantel actual. Revisar la fuente.")
                player_ids.add(pid)
                players.append({**player, "team_id": tid, "league_id": league["id"],
                                "image": f"https://sports.bzzoiro.com/img/player/{pid}/",
                                "source": {"provider": "Bzzoiro", "player_id": pid}})
        print(f"  Acumulado: {len(players)} jugadores", flush=True)

    for lid, code in ((7, "CAMPEONES_UEFA"), (8, "EUROPEA_UEFA"), (32, "LIBERTADORES"), (33, "SUDAMERICANA")):
        comp = get(f"leagues/{lid}/")
        competitions.append({**comp, "game_code": code, "type": "cup"})

    report = {"fetchedAt": datetime.now(timezone.utc).isoformat(), "clubs": len(clubs), "players": len(players),
              "leagues": len(leagues), "badges": len(assets), "missingLeagues": ["CHI1", "URU1"],
              "missingSquads": missing_squads, "missingBadges": missing_badges,
              "attributePolicy": "Valores de simulación estimados, no ratings reales del proveedor."}
    manifest = {"format": "pmpack", "version": "1.1.0", "name": "PARTIDOS — Datos reales Bzzoiro",
                "author": "MiPackPartidos / Bzzoiro", "createdAt": report["fetchedAt"],
                "description": "Clubes y planteles de la temporada actual del proveedor. Valoraciones estimadas para el juego.",
                "coverage": report}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in {
            "manifest.json": manifest, "database/ligas.json": {"leagues": leagues},
            "database/clubes.json": {"clubs": clubs}, "database/jugadores.json": {"players": players},
            "database/competencias.json": {"competitions": competitions},
            "database/configuracion.json": {"solo_clubes_pack": True, "rellenar_planteles": False, "coverage": report},
        }.items():
            z.writestr(name, json.dumps(data, ensure_ascii=False))
        for name, content in assets.items():
            z.writestr(name, content)
    output.write_bytes(buffer.getvalue())
    output.with_suffix(".coverage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rebuild(args.source, args.output)
