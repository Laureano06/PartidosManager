"""Adaptación del formato MiPackPartidos/Bzzoiro al formato nativo del editor."""
from datetime import date
import hashlib
import random
from pack_ratings import calibrar_planteles

LIGAS_PROVEEDOR = {
    "argentina": "ARG1", "brazil": "BRA1", "brasil": "BRA1", "spain": "ESP1",
    "england": "ING1", "italy": "ITA1", "germany": "ALE1", "france": "FRA1",
    "chile": "CHI1", "uruguay": "URU1",
}
POSICIONES = {"G": "POR", "D": "DEF", "M": "MED", "F": "DEL", "GK": "POR",
              "GOALKEEPER": "POR", "DEFENDER": "DEF", "MIDFIELDER": "MED", "FORWARD": "DEL",
              "POR": "POR", "DEF": "DEF", "MED": "MED", "DEL": "DEL"}
ESPECIFICAS = {"GK": "POR", "CB": "DFC", "LB": "DFI", "RB": "DFD", "CM": "MC", "DM": "MCD",
               "AM": "MCO", "LM": "MI", "RM": "MD", "ST": "DC", "LW": "EI", "RW": "ED"}


def adaptar_proveedor(manifest, clubes, jugadores, competencias, metadata, ligas, configuracion):
    if not isinstance(clubes.get("clubs"), list):
        raise ValueError("El formato del proveedor debe contener una lista clubs.")
    config = dict(configuracion or {})
    config["manifest_origen"] = manifest
    config["ligas"] = (ligas or {}).get("leagues", [])
    config["competencias"] = (competencias or {}).get("competitions", [])
    liga_por_id = {str(l["id"]): l for l in config["ligas"]}
    competencias_por_id = {str(c["id"]): c for c in config["competencias"]}
    nombres, planteles, metas, clubes_por_id = {}, {}, {}, {}
    avisos = ["Formato MiPackPartidos adaptado. Los datos originales se conservan en el pack."]
    for club in clubes["clubs"]:
        lid = str(club["league_id"])
        liga = LIGAS_PROVEEDOR.get(lid.lower(), lid.upper())
        codigo = str(club["id"])
        if codigo in clubes_por_id:
            raise ValueError(f"Club repetido en la fuente: {codigo}.")
        clubes_por_id[codigo] = (liga, codigo)
        nombre_liga = competencias_por_id.get(lid, liga_por_id.get(lid, {})).get("name", liga)
        nombres.setdefault(liga, []).append([codigo, club["name"], club.get("badge") or "", nombre_liga])
        venue = club.get("venue") or club.get("stadium") or {}
        meta = {"ciudad": club.get("city") or (venue.get("city", "") if isinstance(venue, dict) else ""),
                "estadio": venue.get("name", "") if isinstance(venue, dict) else str(venue),
                "capacidad": venue.get("capacity", "") if isinstance(venue, dict) else "",
                "manager": club.get("manager") or club.get("coach") or "", "datos_fuente": club}
        if isinstance(meta["manager"], dict):
            meta["manager"] = meta["manager"].get("name", "")
        metas.setdefault(liga, {})[codigo] = meta
    for extra in (metadata or {}).get("clubs", []):
        clave = clubes_por_id.get(str(extra.get("club_id")))
        if clave:
            metas[clave[0]][clave[1]]["metadata_fuente"] = extra

    fecha = date.fromisoformat(str(manifest.get("createdAt") or date.today())[:10])
    ids, posiciones_estimadas, edades_estimadas, atributos_estimados = set(), 0, 0, 0
    for original in (jugadores or {}).get("players", []):
        clave = clubes_por_id.get(str(original.get("team_id")))
        if not clave:
            raise ValueError(f"Jugador sin club asociado: {original.get('id')}.")
        pid = str(original["id"])
        if pid in ids:
            raise ValueError(f"Jugador duplicado: {pid}.")
        ids.add(pid)
        posicion = POSICIONES.get(str(original.get("position", "")).upper())
        campos_estimados = []
        if not posicion:
            posicion = "MED"
            posiciones_estimadas += 1
            campos_estimados.append("posicion")
        try:
            nacimiento = date.fromisoformat(str(original.get("date_of_birth")))
            edad = fecha.year - nacimiento.year - ((fecha.month, fecha.day) < (nacimiento.month, nacimiento.day))
        except ValueError:
            edad = original.get("age")
            if not isinstance(edad, int):
                edad = 24
                edades_estimadas += 1
                campos_estimados.append("edad")
        attrs = original.get("attributes") or {}
        rng = random.Random(int.from_bytes(hashlib.sha256(pid.encode()).digest()[:8], "big"))
        valores = {}
        for campo, ingles in (("ataque", "attack"), ("defensa", "defense"), ("pase", "passing"), ("fisico", "physical")):
            valores[campo] = attrs.get(ingles, rng.randint(45, 75))
        # El generador original también estima sus attributes: nunca se rotulan reales.
        atributos_estimados += 1
        campos_estimados.extend(valores)
        nacionalidad = original.get("nationality") or None
        if isinstance(nacionalidad, dict):
            nacionalidad = nacionalidad.get("name")
        jugador = {"nombre": original["name"], "posicion": posicion, "edad": edad,
                   "posicion_especifica": ESPECIFICAS.get(original.get("specific_position")),
                   "nacionalidad": nacionalidad, **valores, "datos_fuente": original,
                   "campos_estimados": campos_estimados}
        # Si la fuente incluyó la cara dentro de assets/, se preserva en el
        # jugador. pack_engine resolverá esa referencia al importar el PMPack.
        if isinstance(original.get("image"), str) and original["image"].strip():
            jugador["foto_url"] = original["image"].strip()
        planteles.setdefault(clave[0], {}).setdefault(clave[1], []).append(jugador)
    config['calibracion_ovr'] = calibrar_planteles(planteles)
    copas = {c["game_code"]: c["name"] for c in config["competencias"] if c.get("game_code")}
    for c in config["competencias"]:
        code = {7: "CAMPEONES_UEFA", 8: "EUROPEA_UEFA", 32: "LIBERTADORES", 33: "SUDAMERICANA"}.get(c.get("source_id", c.get("id")))
        if code:
            copas[code] = c["name"]
    if atributos_estimados:
        avisos.append(f"{atributos_estimados} jugadores con atributos estimados para simulación; no son valoraciones reales.")
    if edades_estimadas or posiciones_estimadas:
        avisos.append(f"Faltan datos de origen: {edades_estimadas} edades y {posiciones_estimadas} posiciones usan valores de juego señalados como estimados.")
    config["estimaciones"] = {"edades": edades_estimadas, "posiciones": posiciones_estimadas, "atributos": atributos_estimados}
    manifest = {**manifest, "name": manifest.get("name") or "MiPackPartidos — Datos reales",
                "author": manifest.get("author") or "MiPackPartidos", "databaseVersion": "1", "gameVersion": "1.0.0"}
    return manifest, nombres, planteles, copas, metas, config, avisos
