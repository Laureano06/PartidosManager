"""Completa fichas y concilia membresías antes de convertir el pack al editor."""
import argparse
import json
import re
import time
import unicodedata
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path
from dotenv import dotenv_values


def finalize(source, output, env_file, enriched=None):
    token = dotenv_values(env_file).get("BZZOIRO_API_KEY", "") if not enriched else None
    with zipfile.ZipFile(source) as z:
        files = {n: z.read(n) for n in z.namelist()}
    clubs = json.loads(files["database/clubes.json"])["clubs"]
    previous = json.loads(files["database/jugadores.json"])["players"]
    config = json.loads(files["database/configuracion.json"])
    players = []
    if enriched:
        with zipfile.ZipFile(enriched) as z:
            players = [p for p in json.loads(z.read("database/jugadores.json"))["players"] if isinstance(p["id"], int)]
    for index, club in enumerate([] if enriched else [c for c in clubs if isinstance(c["id"], int)], 1):
        offset = 0
        while True:
            url = f"https://sports.bzzoiro.com/api/v2/players/?team_id={club['id']}&limit=200&offset={offset}"
            req = urllib.request.Request(url, headers={"Authorization": "Token " + token})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.load(response)
            rows = data["results"]
            for row in rows:
                if row.get("current_team_id") != club["id"]:
                    raise RuntimeError(f"La fuente devolvió un jugador de otro club: {row['id']}")
                players.append({**row, "team_id": club["id"], "league_id": club["league_id"],
                                "image": f"https://sports.bzzoiro.com/img/player/{row['id']}/",
                                "source": {"provider": "Bzzoiro", "player_id": row["id"]}})
            time.sleep(0.15)
            if not data.get("next"):
                break
            offset += len(rows)
        if index % 20 == 0:
            print(f"Fichas completas: {index} clubes / {len(players)} jugadores", flush=True)

    def identity(player):
        name = "".join(c for c in unicodedata.normalize("NFKD", player["name"].casefold()) if not unicodedata.combining(c))
        return name, player.get("date_of_birth")

    identities = {identity(p): p for p in players}
    excluded, conflicts = [], []
    for player in previous:
        if not str(player["id"]).startswith("ESPN"):
            continue
        ref = player.get("raw", {}).get("defaultTeam", {}).get("$ref", "")
        current = re.search(r"/teams/(\d+)", ref)
        if current and "ESPN" + current[1] != player["team_id"]:
            excluded.append({"id": player["id"], "name": player["name"], "roster": player["team_id"], "current_team": current[1]})
            continue
        duplicate = identities.get(identity(player)) if player.get("date_of_birth") else None
        if duplicate:
            conflicts.append({"name": player["name"], "date_of_birth": player["date_of_birth"],
                              "retained_source": player["source"], "retained_team": player["team_id"],
                              "other_source": duplicate["source"], "other_team": duplicate["team_id"],
                              "policy": "Plantel actual de ESPN para Chile/Uruguay; ficha biográfica de Bzzoiro. Se conserva la discrepancia de origen."})
            duplicate["membership_source"] = {"provider": "ESPN", "player_id": player["source"]["player_id"],
                                              "team_id": player["team_id"], "reference": ref}
            duplicate["team_id"] = player["team_id"]
            duplicate["league_id"] = player["league_id"]
            duplicate["jersey_number"] = player.get("shirt_number")
            continue
        identities[identity(player)] = player
        players.append(player)
    ids = [str(p["id"]) for p in players]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Persisten IDs de jugadores duplicados")
    counts = Counter(str(p["team_id"]) for p in players)
    missing = [c["name"] for c in clubs if counts[str(c["id"]) ] < 11]
    if missing:
        raise RuntimeError(f"Planteles con menos de 11 jugadores: {missing}")
    report = config["coverage"]
    report.update({"players": len(players), "excluded_stale_roster_entries": excluded,
                   "membership_conflicts": conflicts, "min_squad_size": min(counts.values()),
                   "max_squad_size": max(counts.values())})
    config["coverage"] = report
    manifest = json.loads(files["manifest.json"])
    manifest["coverage"] = report
    for name, data in {"database/jugadores.json": {"players": players}, "database/configuracion.json": config, "manifest.json": manifest}.items():
        files[name] = json.dumps(data, ensure_ascii=False).encode("utf-8")
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    output.with_suffix(".coverage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"players": len(players), "stale_excluded": len(excluded), "conflicts": conflicts}, ensure_ascii=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--enriched", type=Path, help="Reutiliza fichas ya recuperadas sin consultar la API.")
    args = parser.parse_args()
    finalize(args.source, args.output, args.env_file, args.enriched)
