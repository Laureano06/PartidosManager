"""Agrega selecciones y grupos multiclub a un pmpack nativo de PARTIDOS.

No consulta internet ni modifica el archivo de origen. Las selecciones se
derivan de nacionalidades y referencias nacionales ya incluidas por el pack.
Las redes multiclub se limitan a clubes que realmente están en sus 9 ligas.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def codigo_pais(nombre: str) -> str:
    limpio = "".join(c for c in nombre.upper() if c.isalnum())[:8] or "PAIS"
    return f"NAT-{limpio}-{hashlib.sha1(nombre.encode()).hexdigest()[:4]}"


def categoria(nombre: str) -> str:
    texto = nombre.upper().replace(" ", "")
    for edad in ("U23", "U21", "U20", "U19", "U18", "U17"):
        if edad in texto:
            return f"SUB{edad[1:]}"
    return "MAYOR"


def grupos_multiclub(clubes: dict) -> dict:
    disponibles = {(liga, fila[0]) for liga, filas in clubes.items() for fila in filas}
    def tiene(liga: str, codigo: str) -> bool:
        return (liga, codigo) in disponibles
    redes = [
        ("CITY_FOOTBALL_GROUP", [("ING1", "12"), ("FRA1", "1303"), ("BRA1", "166"), ("URU1", "ESPN19002")]),
        ("BLUECO", [("ING1", "13"), ("FRA1", "112")]),
        ("EAGLE_FOOTBALL", [("FRA1", "100"), ("BRA1", "163")]),
        ("INEOS_FOOTBALL", [("ING1", "17"), ("FRA1", "103")]),
        ("RED_BULL", [("ALE1", "80"), ("BRA1", "168")]),
    ]
    return {
        "redes_marca": [{"grupo_marca": nombre, "miembros": [list(x) for x in miembros if tiene(*x)]}
                        for nombre, miembros in redes if sum(tiene(*x) for x in miembros) > 1],
        # Estas tenencias habilitan el pipeline de juego. Los grupos que usan
        # holdings y no un club matriz se representan solo como red de marca.
        "afiliaciones": [
            {"liga_inversor": "ING1", "codigo_inversor": "12", "liga_participado": "FRA1", "codigo_participado": "1303", "porcentaje": 100, "tipo": "PROPIETARIO"},
            {"liga_inversor": "ING1", "codigo_inversor": "12", "liga_participado": "BRA1", "codigo_participado": "166", "porcentaje": 100, "tipo": "PROPIETARIO"},
            {"liga_inversor": "ING1", "codigo_inversor": "12", "liga_participado": "URU1", "codigo_participado": "ESPN19002", "porcentaje": 100, "tipo": "PROPIETARIO"},
            {"liga_inversor": "ING1", "codigo_inversor": "13", "liga_participado": "FRA1", "codigo_participado": "112", "porcentaje": 100, "tipo": "PROPIETARIO"},
        ],
    }


def construir_selecciones(jugadores: dict, existentes: dict | None = None) -> dict:
    todos = [j for clubes in jugadores.values() for plantel in clubes.values() for j in plantel]
    paises = sorted({j.get("nacionalidad", "").strip() for j in todos if j.get("nacionalidad")})
    equipos = [{"codigo": codigo_pais(pais), "nombre": pais, "pais": pais, "categoria": "MAYOR"} for pais in paises]
    extras: dict[str, dict] = {}
    elegibilidades = []
    for jugador in todos:
        fuente = jugador.get("datos_fuente") or {}
        nacional = fuente.get("national_team") or {}
        if not isinstance(nacional, dict) or not nacional.get("id") or not nacional.get("name"):
            continue
        codigo = f"NT-{nacional['id']}"
        if codigo not in extras:
            extras[codigo] = {"codigo": codigo, "nombre": nacional["name"], "pais": jugador.get("nacionalidad") or nacional["name"],
                              "categoria": categoria(nacional["name"]), "datos_fuente": nacional}
        referencia = fuente.get("id")
        if referencia is not None:
            elegibilidades.append({"jugador_codigo": str(referencia), "seleccion_codigo": codigo, "estado": "ELEGIBLE"})
    equipos.extend(extras.values())
    paises_activos = {"Argentina", "Brazil", "Brasil", "Spain", "England", "Italy", "Germany", "France", "Chile", "Uruguay"}
    activos = [codigo_pais(pais) for pais in paises if pais in paises_activos]
    ventanas = [
        {"nombre": "Ventana internacional de septiembre", "inicio": "2027-09-06", "fin": "2027-09-14"},
        {"nombre": "Ventana internacional de octubre", "inicio": "2027-10-04", "fin": "2027-10-12"},
        {"nombre": "Ventana internacional de noviembre", "inicio": "2027-11-08", "fin": "2027-11-16"},
    ]
    # El enriquecedor agrega cobertura al pack, pero nunca borra un calendario
    # de selecciones que su autor ya verificó. Así un proveedor puede incluir
    # grupos/partidos reales en database/selecciones.json y regenerar el pack
    # sin perderlos.
    existentes = existentes if isinstance(existentes, dict) else {}

    def filas(nombre: str) -> list[dict]:
        valor = existentes.get(nombre)
        return [fila for fila in valor if isinstance(fila, dict)] if isinstance(valor, list) else []

    equipos_por_codigo = {str(equipo["codigo"]): equipo for equipo in equipos if equipo.get("codigo")}
    for equipo in filas("equipos"):
        codigo = str(equipo.get("codigo") or "")
        if codigo:
            equipos_por_codigo[codigo] = equipo
    elegibilidades_existentes = filas("elegibilidades")
    claves_elegibilidad = {(str(fila.get("jugador_codigo")), str(fila.get("seleccion_codigo"))) for fila in elegibilidades}
    for fila in elegibilidades_existentes:
        clave = (str(fila.get("jugador_codigo")), str(fila.get("seleccion_codigo")))
        if all(clave) and clave not in claves_elegibilidad:
            elegibilidades.append(fila)
            claves_elegibilidad.add(clave)
    activos = list(dict.fromkeys(activos + [str(codigo) for codigo in existentes.get("activas", []) if isinstance(codigo, str)]))
    ventanas = filas("ventanas") or ventanas
    return {
        "equipos": list(equipos_por_codigo.values()),
        "elegibilidades": elegibilidades,
        "convocatorias": filas("convocatorias"),
        "activas": activos,
        "ventanas": ventanas,
        "torneos": filas("torneos"),
        "nota": "Elegibilidad derivada de la nacionalidad y de la referencia nacional disponible en la fuente del pack; los torneos y fixtures son conservados solo si ya estaban verificados por su proveedor.",
    }


def enriquecer(origen: Path, destino: Path) -> None:
    with zipfile.ZipFile(origen, "r") as entrada:
        archivos = {info.filename: entrada.read(info.filename) for info in entrada.infolist() if not info.is_dir()}
    clubes = json.loads(archivos["database/clubes.json"])
    jugadores = json.loads(archivos["database/jugadores.json"])
    config = json.loads(archivos.get("database/configuracion.json", b"{}"))
    selecciones_existentes = json.loads(archivos.get("database/selecciones.json", b"{}"))
    if not isinstance(selecciones_existentes, dict):
        selecciones_existentes = config.get("selecciones") if isinstance(config.get("selecciones"), dict) else {}
    config["selecciones"] = construir_selecciones(jugadores, selecciones_existentes)
    # Las relaciones reales pertenecen al PMPack. Solo se completa el mapa
    # curado cuando la fuente aún no trae multiclub; nunca se pisa lo que el
    # proveedor ya verificó y guardó dentro de database/configuracion.json.
    multiclub_existente = config.get("multiclub")
    config["multiclub"] = multiclub_existente if isinstance(multiclub_existente, dict) and multiclub_existente else grupos_multiclub(clubes)
    archivos["database/configuracion.json"] = json.dumps(config, ensure_ascii=False).encode()
    archivos["database/selecciones.json"] = json.dumps(config["selecciones"], ensure_ascii=False).encode()
    manifest = json.loads(archivos["manifest.json"])
    manifest["version"] = "1.2.0"
    manifest["description"] = (manifest.get("description") or "") + " Incluye selecciones y redes multiclub."
    archivos["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
    with zipfile.ZipFile(destino, "w", compression=zipfile.ZIP_DEFLATED) as salida:
        for nombre, contenido in archivos.items():
            salida.writestr(nombre, contenido)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("origen", type=Path)
    parser.add_argument("destino", type=Path)
    args = parser.parse_args()
    enriquecer(args.origen, args.destino)
    print(f"Pack enriquecido: {args.destino}")
