"""Sistema de Data Packs (.pmpack) — bases de datos de clubes/jugadores
reales instalables, editables y exportables, al estilo de un mod de FM pero
adaptado a este juego. Un `.pmpack` es un ZIP con un manifest, el contenido
de la base (equivalente a los *_json de PaqueteClubes) y los escudos que
vivan en nuestro propio static/escudos/ (nunca se descargan URLs de
terceros, y nunca se embebe contenido con marca de otro producto — ver
fixtures_prueba/README.md).

Funciones planas (no clases) siguiendo la convención de engine/*_engine.py.
"""
import csv
import io
import json
import random
import re
import string
import zipfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import PaqueteClubes

GAME_VERSION = "1.0.0"
DATABASE_VERSION = "1"

RUTA_PROYECTO = Path(__file__).parent
RUTA_FIXTURES_REAL_DATA = RUTA_PROYECTO / "fixtures_prueba"
PACK_ID_REAL_DATA = "partidos-real-data"


def _slugify(nombre: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", nombre.lower()).strip("-") or "pack"
    return base


def generar_pack_id(nombre: str, ids_existentes: set[str]) -> str:
    """Slug estable a partir del nombre — si colisiona con uno existente
    (dos packs con el mismo nombre, o el mismo nombre reusado tras borrar
    uno), se le agrega un sufijo random corto."""
    base = _slugify(nombre)
    if base not in ids_existentes:
        return base
    sufijo = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"{base}-{sufijo}"


def contar_entidades(nombres_clubes: dict, jugadores_clubes: dict | None) -> dict:
    numero_de_ligas = len(nombres_clubes)
    numero_de_clubes = sum(len(v) for v in nombres_clubes.values())
    numero_de_jugadores = 0
    if jugadores_clubes:
        for clubes in jugadores_clubes.values():
            for jugadores in clubes.values():
                numero_de_jugadores += len(jugadores)
    return {
        "numberOfLeagues": numero_de_ligas,
        "numberOfClubs": numero_de_clubes,
        "numberOfPlayers": numero_de_jugadores,
    }


def construir_manifest(paquete: PaqueteClubes, nombres_clubes: dict, jugadores_clubes: dict | None, assets_incluidos: bool) -> dict:
    conteos = contar_entidades(nombres_clubes, jugadores_clubes)
    return {
        "packId": paquete.pack_id,
        "name": paquete.nombre,
        "version": paquete.version,
        "author": paquete.autor,
        "description": paquete.descripcion,
        "gameVersion": GAME_VERSION,
        "databaseVersion": DATABASE_VERSION,
        "createdAt": paquete.fecha_creacion.isoformat() if paquete.fecha_creacion else None,
        "updatedAt": paquete.fecha_actualizacion.isoformat() if paquete.fecha_actualizacion else None,
        "assetsIncluded": assets_incluidos,
        **conteos,
    }


def advertencias_compatibilidad(manifest: dict) -> list[str]:
    """Warnings, no bloqueos — este proyecto no tiene todavía historial de
    cambios de esquema que rompan packs viejos, así que un pack de otra
    versión se avisa pero se deja instalar igual (el usuario decide)."""
    avisos = []
    version_pack = manifest.get("gameVersion")
    if version_pack and version_pack != GAME_VERSION:
        avisos.append(
            f"Este pack se creó para la versión {version_pack} del juego y puede no ser 100% compatible con tu versión {GAME_VERSION}."
        )
    version_db = manifest.get("databaseVersion")
    if version_db and version_db != DATABASE_VERSION:
        avisos.append(f"La versión de base de datos del pack ({version_db}) no coincide con la actual ({DATABASE_VERSION}).")
    return avisos


def exportar_pmpack(paquete: PaqueteClubes, directorio_escudos: Path) -> bytes:
    """Arma el .pmpack en memoria. Los escudos que sean una URL propia
    (/static/escudos/...) se embeben como bytes reales; una URL externa
    queda tal cual en clubes.json (no se descarga contenido de terceros)."""
    nombres_clubes = json.loads(paquete.nombres_json)
    jugadores_clubes = json.loads(paquete.jugadores_json) if paquete.jugadores_json else None
    competencias = json.loads(paquete.competencias_json) if paquete.competencias_json else None
    metadata_clubes = json.loads(paquete.metadata_clubes_json) if paquete.metadata_clubes_json else None
    configuracion = json.loads(paquete.configuracion_json) if paquete.configuracion_json else None

    assets_a_incluir: dict[str, Path] = {}  # nombre dentro del zip -> path en disco
    for liga, clubes in nombres_clubes.items():
        for fila in clubes:
            codigo, escudo_url = fila[0], (fila[2] if len(fila) >= 3 else None)
            if escudo_url and escudo_url.startswith("/static/escudos/"):
                nombre_archivo = escudo_url.rsplit("/", 1)[-1]
                ruta_local = directorio_escudos / nombre_archivo
                if ruta_local.is_file():
                    extension = ruta_local.suffix
                    nombre_asset = f"assets/{liga}/{codigo}{extension}"
                    assets_a_incluir[nombre_asset] = ruta_local
                    fila[2] = nombre_asset

    def incluir_referencias(valor):
        if isinstance(valor, dict):
            return {k: incluir_referencias(v) for k, v in valor.items()}
        if isinstance(valor, list):
            return [incluir_referencias(v) for v in valor]
        if isinstance(valor, str) and valor.startswith("/static/escudos/"):
            ruta = directorio_escudos / valor.rsplit("/", 1)[-1]
            if ruta.is_file():
                existente = next((nombre for nombre, local in assets_a_incluir.items() if local == ruta), None)
                if existente:
                    return existente
                nombre = f"assets/extra/{ruta.name}"
                assets_a_incluir[nombre] = ruta
                return nombre
        return valor

    jugadores_clubes = incluir_referencias(jugadores_clubes)
    metadata_clubes = incluir_referencias(metadata_clubes)
    configuracion = incluir_referencias(configuracion)

    manifest = construir_manifest(paquete, nombres_clubes, jugadores_clubes, assets_incluidos=bool(assets_a_incluir))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr("database/clubes.json", json.dumps(nombres_clubes, ensure_ascii=False))
        if jugadores_clubes:
            zf.writestr("database/jugadores.json", json.dumps(jugadores_clubes, ensure_ascii=False))
        if competencias:
            zf.writestr("database/competencias.json", json.dumps(competencias, ensure_ascii=False))
        if metadata_clubes:
            zf.writestr("database/metadata_clubes.json", json.dumps(metadata_clubes, ensure_ascii=False))
        if configuracion:
            zf.writestr("database/configuracion.json", json.dumps(configuracion, ensure_ascii=False))
        if isinstance(configuracion, dict) and configuracion.get("selecciones"):
            zf.writestr("database/selecciones.json", json.dumps(configuracion["selecciones"], ensure_ascii=False))
        for nombre_en_zip, ruta_local in assets_a_incluir.items():
            zf.write(ruta_local, nombre_en_zip)
    return buffer.getvalue()


class PmpackInvalido(Exception):
    pass


def validar_datos_pack(nombres_clubes, jugadores_clubes):
    """Normaliza claves y rechaza jugadores que la creación de carrera perdería."""
    from engine.data_gen import LIGAS

    if not isinstance(nombres_clubes, dict) or not nombres_clubes:
        raise PmpackInvalido("Hace falta al menos un club.")
    clubes = {}
    for liga, filas in nombres_clubes.items():
        liga = liga.strip().upper()
        if liga not in LIGAS or not isinstance(filas, list) or not filas:
            raise PmpackInvalido(f"Liga inválida o sin clubes: {liga}.")
        destino = clubes.setdefault(liga, [])
        for fila in filas:
            if not isinstance(fila, (list, tuple)) or not 2 <= len(fila) <= 4 or not all(isinstance(v, str) or v is None for v in fila):
                raise PmpackInvalido(f"Club inválido en {liga}.")
            codigo, nombre = (fila[0] or "").strip().upper(), (fila[1] or "").strip()
            if not codigo or not nombre or any(c[0] == codigo for c in destino):
                raise PmpackInvalido(f"Código vacío o repetido / nombre vacío en {liga}: {codigo}.")
            destino.append([codigo, nombre, *fila[2:]])
    if jugadores_clubes is None:
        return clubes, None
    if not isinstance(jugadores_clubes, dict):
        raise PmpackInvalido("Los jugadores deben estar agrupados por liga y código de club.")
    jugadores = {}
    for liga, por_club in jugadores_clubes.items():
        liga = liga.strip().upper()
        if not isinstance(por_club, dict):
            raise PmpackInvalido(f"Jugadores mal agrupados en {liga}.")
        for codigo, plantel in por_club.items():
            codigo = codigo.strip().upper()
            if not any(c[0] == codigo for c in clubes.get(liga, [])):
                raise PmpackInvalido(f"Los jugadores de {liga}/{codigo} no tienen un club en el pack.")
            if not isinstance(plantel, list):
                raise PmpackInvalido(f"El plantel de {liga}/{codigo} debe ser una lista.")
            destino = jugadores.setdefault(liga, {}).setdefault(codigo, [])
            for dato in plantel:
                if not isinstance(dato, dict) or not isinstance(dato.get("nombre"), str) or not dato["nombre"].strip():
                    raise PmpackInvalido(f"Jugador sin nombre en {liga}/{codigo}.")
                jugador = dict(dato)
                jugador["posicion"] = str(dato.get("posicion", "")).strip().upper()
                if jugador["posicion"] not in {"POR", "DEF", "MED", "DEL"}:
                    raise PmpackInvalido(f"Posición inválida para {dato['nombre']}: usá POR, DEF, MED o DEL.")
                for campo, default in (("edad", 24), ("ataque", 50), ("defensa", 50), ("pase", 50), ("fisico", 50)):
                    try:
                        valor = dato.get(campo)
                        jugador[campo] = default if valor is None or valor == "" else int(valor)
                    except (ValueError, TypeError):
                        raise PmpackInvalido(f"{campo} inválido para {dato['nombre']}.") from None
                cesion = jugador.get("cesion")
                if cesion is not None:
                    if not isinstance(cesion, dict):
                        raise PmpackInvalido(f"Cesión inválida para {dato['nombre']}.")
                    codigo_dueno = str(cesion.get("club_dueno_codigo") or "").strip().upper()
                    liga_dueno = str(cesion.get("liga_dueno") or liga).strip().upper()
                    if not codigo_dueno or not any(club[0] == codigo_dueno for club in clubes.get(liga_dueno, [])):
                        raise PmpackInvalido(f"La cesión de {dato['nombre']} no tiene un club dueño válido en el PMPack.")
                    try:
                        datetime.strptime(str(cesion.get("fin") or ""), "%Y-%m-%d")
                    except ValueError:
                        raise PmpackInvalido(f"La cesión de {dato['nombre']} necesita una fecha de fin válida (AAAA-MM-DD).") from None
                    try:
                        opcion_compra = cesion.get("opcion_compra")
                        if opcion_compra not in (None, "") and int(opcion_compra) < 0:
                            raise ValueError
                        if opcion_compra not in (None, ""):
                            cesion["opcion_compra"] = int(opcion_compra)
                    except (TypeError, ValueError):
                        raise PmpackInvalido(f"La opción de compra de {dato['nombre']} es inválida.") from None
                    cesion["club_dueno_codigo"] = codigo_dueno
                    cesion["liga_dueno"] = liga_dueno
                    jugador["cesion"] = cesion
                destino.append(jugador)
    return clubes, jugadores


def importar_pmpack(contenido: bytes, guardar_asset: "callable[[bytes, str], str]") -> dict:
    """Abre y valida un .pmpack. `guardar_asset(bytes, extension) -> url` es
    inyectado desde main.py (misma función que usa la subida manual de
    escudos) para no duplicar el manejo de static/escudos/ acá.

    Devuelve un dict listo para previsualizar o para crear un PaqueteClubes:
    {manifest, nombres_clubes, jugadores_clubes, competencias, metadata_clubes, avisos}.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(contenido))
    except zipfile.BadZipFile:
        raise PmpackInvalido("El archivo no es un .pmpack válido (no es un ZIP).")

    nombres_zip = set(zf.namelist())
    if "manifest.json" not in nombres_zip:
        raise PmpackInvalido("Falta manifest.json — no es un .pmpack válido.")
    if "database/clubes.json" not in nombres_zip:
        raise PmpackInvalido("Falta database/clubes.json — no es un .pmpack válido.")

    try:
        manifest = json.loads(zf.read("manifest.json"))
        nombres_clubes = json.loads(zf.read("database/clubes.json"))
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as e:
        raise PmpackInvalido(f"El contenido del pack está corrupto: {e}")

    if not isinstance(nombres_clubes, dict) or not nombres_clubes:
        raise PmpackInvalido("database/clubes.json no tiene ningún club.")

    try:
        jugadores_clubes = json.loads(zf.read("database/jugadores.json")) if "database/jugadores.json" in nombres_zip else None
        competencias = json.loads(zf.read("database/competencias.json")) if "database/competencias.json" in nombres_zip else None
        metadata_clubes = json.loads(zf.read("database/metadata_clubes.json")) if "database/metadata_clubes.json" in nombres_zip else None
        ligas = json.loads(zf.read("database/ligas.json")) if "database/ligas.json" in nombres_zip else None
        configuracion = json.loads(zf.read("database/configuracion.json")) if "database/configuracion.json" in nombres_zip else {}
        selecciones = json.loads(zf.read("database/selecciones.json")) if "database/selecciones.json" in nombres_zip else None
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise PmpackInvalido(f"El contenido del pack está corrupto: {e}") from e
    if not isinstance(manifest, dict):
        raise PmpackInvalido("manifest.json debe ser un objeto.")
    avisos_formato = []
    if "clubs" in nombres_clubes:
        from pack_formats import adaptar_proveedor
        try:
            manifest, nombres_clubes, jugadores_clubes, competencias, metadata_clubes, configuracion, avisos_formato = adaptar_proveedor(
                manifest, nombres_clubes, jugadores_clubes, competencias, metadata_clubes, ligas, configuracion)
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            raise PmpackInvalido(f"Datos del proveedor inválidos: {e}") from e
    if not isinstance(configuracion, dict):
        raise PmpackInvalido("La configuración del pack debe ser un objeto.")
    if selecciones is not None:
        if not isinstance(selecciones, dict):
            raise PmpackInvalido("database/selecciones.json debe ser un objeto.")
        configuracion["selecciones"] = selecciones
    nombres_clubes, jugadores_clubes = validar_datos_pack(nombres_clubes, jugadores_clubes)

    # La referencia exacta evita colisiones; liga/código y código solo
    # permiten leer también packs anteriores.
    assets_por_ruta: dict[str, str] = {}
    for nombre_en_zip in sorted(nombres_zip):
        if nombre_en_zip.startswith("assets/") and nombre_en_zip != "assets/":
            extension = Path(nombre_en_zip).suffix.lower()
            if extension not in {".png", ".jpg", ".jpeg", ".webp", ".svg"}:
                continue
            assets_por_ruta[nombre_en_zip] = guardar_asset(zf.read(nombre_en_zip), extension)

    for liga, clubes in nombres_clubes.items():
        for fila in clubes:
            codigo = fila[0]
            referencia = fila[2] if len(fila) >= 3 else ""
            nueva_url = assets_por_ruta.get(referencia)
            if not nueva_url:
                # Compatibilidad con packs anteriores: assets/CODIGO.ext.
                for prefijo in (f"assets/{liga}/{codigo}", f"assets/{codigo}"):
                    nueva_url = next((url for ruta, url in assets_por_ruta.items() if ruta.rsplit(".", 1)[0].upper() == prefijo.upper()), None)
                    if nueva_url:
                        break
            if nueva_url:
                if len(fila) >= 4:
                    fila[2] = nueva_url
                elif len(fila) == 3:
                    fila[2] = nueva_url
                else:
                    fila.append(nueva_url)

    def resolver_referencias(valor):
        if isinstance(valor, dict):
            return {k: resolver_referencias(v) for k, v in valor.items()}
        if isinstance(valor, list):
            return [resolver_referencias(v) for v in valor]
        return assets_por_ruta.get(valor, valor) if isinstance(valor, str) else valor

    jugadores_clubes = resolver_referencias(jugadores_clubes)
    metadata_clubes = resolver_referencias(metadata_clubes)
    configuracion = resolver_referencias(configuracion)
    avisos = advertencias_compatibilidad(manifest) + avisos_formato
    estimaciones = configuracion.get("estimaciones") or {}
    if estimaciones and not avisos_formato:
        avisos.append(f"Atributos de simulación estimados: {estimaciones.get('atributos', 0)} jugadores. Edades sin dato: {estimaciones.get('edades', 0)}; posiciones sin dato: {estimaciones.get('posiciones', 0)}.")
    discrepancias = (configuracion.get("coverage") or {}).get("membership_conflicts") or []
    if discrepancias:
        avisos.append(f"{len(discrepancias)} asociaciones jugador/club reconciliadas entre fuentes. El detalle se conserva en el pack.")
    conteos = contar_entidades(nombres_clubes, jugadores_clubes)
    if not conteos["numberOfPlayers"]:
        avisos.append("Este archivo no contiene jugadores. No puede crear planteles reales.")
    faltantes = [f"{liga}/{fila[0]}" for liga, filas in nombres_clubes.items() for fila in filas
                 if not (jugadores_clubes or {}).get(liga, {}).get(fila[0])]
    if faltantes:
        avisos.append(f"{len(faltantes)} clubes sin jugadores en el archivo.")
    manifest["assetsIncluded"] = bool(assets_por_ruta)

    return {
        "manifest": manifest,
        "nombres_clubes": nombres_clubes,
        "jugadores_clubes": jugadores_clubes,
        "competencias": competencias,
        "metadata_clubes": metadata_clubes,
        "configuracion": configuracion,
        "avisos": avisos,
        "conteos": conteos,
    }


# ---------- CSV → estructura de pack (para sembrar PARTIDOS Real Data) ----------
def _parsear_csv_clubes(texto: str) -> dict:
    """Puerto a Python de parsearCsvClubes en soccer-frontend/src/utils/csvClubes.js
    — mismo formato: LIGA,CODIGO,NOMBRE[,ESCUDO_URL[,NOMBRE_COMPETENCIA]]."""
    por_liga: dict[str, list[list[str]]] = {}
    for partes in csv.reader(io.StringIO(texto.lstrip("\ufeff")), skipinitialspace=True):
        partes = [p.strip() for p in partes]
        if not partes or partes[0].startswith("#"):
            continue
        if len(partes) < 3:
            continue
        liga, codigo, nombre = partes[0].upper(), partes[1].upper(), partes[2]
        if liga == "LIGA" and codigo == "CODIGO":
            continue
        escudo_url = partes[3] if len(partes) > 3 else ""
        nombre_competencia = partes[4] if len(partes) > 4 else ""
        if not liga or not codigo or not nombre:
            continue
        fila = [codigo, nombre]
        if escudo_url or nombre_competencia:
            fila.append(escudo_url)
        if nombre_competencia:
            fila.append(nombre_competencia)
        por_liga.setdefault(liga, []).append(fila)
    return por_liga


def _parsear_csv_jugadores(texto: str) -> dict:
    """Puerto a Python de parsearCsvJugadores — LIGA,CODIGO_CLUB,NOMBRE,
    POSICION,POSICION_ESPECIFICA,NACIONALIDAD,EDAD,ATAQUE,DEFENSA,PASE,FISICO."""
    por_liga: dict[str, dict[str, list[dict]]] = {}
    for partes in csv.reader(io.StringIO(texto.lstrip("\ufeff")), skipinitialspace=True):
        partes = [p.strip() for p in partes]
        if not partes or partes[0].startswith("#"):
            continue
        if len(partes) < 11:
            continue
        liga, codigo_club, nombre, posicion, posicion_especifica, nacionalidad, edad, ataque, defensa, pase, fisico = partes[:11]
        liga, codigo_club, posicion = liga.upper(), codigo_club.upper(), posicion.upper()
        if liga == "LIGA" and codigo_club == "CODIGO_CLUB":
            continue
        if not liga or not codigo_club or not nombre or not posicion:
            continue

        def _num(v, default):
            try:
                return int(v)
            except ValueError:
                return default

        por_liga.setdefault(liga, {}).setdefault(codigo_club, []).append({
            "nombre": nombre, "posicion": posicion, "posicion_especifica": posicion_especifica or None,
            "nacionalidad": nacionalidad or None, "edad": _num(edad, 24),
            "ataque": _num(ataque, 50), "defensa": _num(defensa, 50),
            "pase": _num(pase, 50), "fisico": _num(fisico, 50),
        })
    return por_liga


DESCRIPCION_REAL_DATA = (
    "Clubes reales (178, en la cantidad real de cada liga) y jugadores reales puntuales "
    "(~85, cobertura enfocada en los clubes más conocidos de cada liga). Atributos "
    "estimados a ojo por reputación pública general, NO copiados de ninguna base de datos "
    "puntual ni garantizados como plantel vigente. Sin escudos con marca — cada club trae un "
    "placeholder autogenerado (iniciales + color); si querés un escudo real puntual, "
    "subilo vos desde el Editor (con derecho a usarlo)."
)


async def sembrar_partidos_real_data(session: AsyncSession) -> None:
    """Si fixtures_prueba/ existe en este proyecto Y todavía no hay un pack
    'partidos-real-data', lo crea a partir de esos CSV. Si el archivo no
    existe (ej. en otra máquina que clonó el repo sin esa carpeta, que está
    en .gitignore a propósito), no se crea nada — nunca se inventan datos
    reales que no estén ya provistos."""
    ruta_clubes = RUTA_FIXTURES_REAL_DATA / "clubes_prueba.csv"
    if not ruta_clubes.is_file():
        return

    ya_existe = (await session.execute(
        select(PaqueteClubes.id_paquete).where(PaqueteClubes.pack_id == PACK_ID_REAL_DATA)
    )).first()
    if ya_existe:
        return

    nombres_clubes = _parsear_csv_clubes(ruta_clubes.read_text(encoding="utf-8"))
    ruta_jugadores = RUTA_FIXTURES_REAL_DATA / "jugadores_prueba.csv"
    jugadores_clubes = _parsear_csv_jugadores(ruta_jugadores.read_text(encoding="utf-8")) if ruta_jugadores.is_file() else None

    ahora = datetime.utcnow()
    session.add(PaqueteClubes(
        pack_id=PACK_ID_REAL_DATA, nombre="PARTIDOS Real Data", version="1.0.0",
        autor="PARTIDOS Manager", descripcion=DESCRIPCION_REAL_DATA, es_oficial=True,
        nombres_json=json.dumps(nombres_clubes), jugadores_json=json.dumps(jugadores_clubes) if jugadores_clubes else None,
        fecha_creacion=ahora, fecha_actualizacion=ahora,
    ))
    await session.commit()
    print(f"PARTIDOS Real Data sembrado desde fixtures_prueba/ ({sum(len(v) for v in nombres_clubes.values())} clubes).")
