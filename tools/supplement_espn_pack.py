"""Agrega los planteles publicados por ESPN para Chile y Uruguay al pack recuperado."""
import argparse
import json
import time
import urllib.request
import zipfile
from pathlib import Path


def supplement(source, output):
    with zipfile.ZipFile(source) as z:
        files = {n: z.read(n) for n in z.namelist()}
    manifest = json.loads(files["manifest.json"])
    clubs = json.loads(files["database/clubes.json"])["clubs"]
    players = json.loads(files["database/jugadores.json"])["players"]
    leagues = json.loads(files["database/ligas.json"])["leagues"]
    competitions = json.loads(files["database/competencias.json"])["competitions"]
    config = json.loads(files["database/configuracion.json"])

    def get(url):
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.load(response)
        time.sleep(0.15)
        return data

    for code, lid, country in (("chi.1", "chile", "Chile"), ("uru.1", "uruguay", "Uruguay")):
        base = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code}"
        data = get(base + "/teams?limit=100")
        league_data = data["sports"][0]["leagues"][0]
        league = {"id": lid, "name": league_data["name"], "country": country, "source": {"provider": "ESPN", "league": code}}
        leagues.append(league)
        competitions.append({**league, "type": "league"})
        for row in league_data["teams"]:
            team = row["team"]
            tid = "ESPN" + team["id"]
            roster = get(base + f"/teams/{team['id']}/roster")
            if len(roster.get("athletes", [])) < 11:
                raise RuntimeError(f"Plantel insuficiente publicado para {team['displayName']}")
            badge = f"assets/teams/{tid}.png"
            with urllib.request.urlopen(team["logos"][0]["href"], timeout=30) as response:
                files[badge] = response.read()
            clubs.append({"id": tid, "name": team["displayName"], "league_id": lid, "country": country, "badge": badge,
                          "color": team.get("color"), "source": {"provider": "ESPN", "team_id": team["id"]}, "raw": team})
            for player in roster["athletes"]:
                players.append({"id": "ESPN" + player["id"], "name": player["displayName"], "team_id": tid, "league_id": lid,
                                "position": (player.get("position") or {}).get("abbreviation", ""),
                                "date_of_birth": (player.get("dateOfBirth") or "")[:10], "age": player.get("age"),
                                "nationality": player.get("citizenship"), "shirt_number": player.get("jersey"),
                                "image": (player.get("headshot") or {}).get("href"),
                                "source": {"provider": "ESPN", "player_id": player["id"]}, "raw": player})
            print(f"{country}: {team['displayName']} — {len(roster['athletes'])} jugadores", flush=True)
    report = config["coverage"]
    report.update({"clubs": len(clubs), "players": len(players), "leagues": len(leagues),
                   "badges": len([n for n in files if n.startswith('assets/teams/')]), "missingLeagues": [],
                   "sources": ["Bzzoiro", "ESPN"]})
    manifest.update({"name": "PARTIDOS — 9 ligas, datos reales", "author": "MiPackPartidos / Bzzoiro / ESPN", "coverage": report})
    for name, data in {"manifest.json": manifest, "database/clubes.json": {"clubs": clubs},
                       "database/jugadores.json": {"players": players}, "database/ligas.json": {"leagues": leagues},
                       "database/competencias.json": {"competitions": competitions}, "database/configuracion.json": config}.items():
        files[name] = json.dumps(data, ensure_ascii=False).encode("utf-8")
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    output.with_suffix(".coverage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    supplement(args.source, args.output)
