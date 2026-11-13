"""
Generación de una carrera (partida): 9 ligas ficticias (ARG1, BRA1, ESP1,
ING1, ITA1, FRA1, ALE1, URU1, CHI1) de 20 clubes cada una repartidas en dos
confederaciones (UEFA/CONMEBOL), sus planteles (generados, sin nombres
reales, 25 jugadores clasificados en 11 titulares / 9 suplentes / 5
reservas), y el fixture round-robin de las ligas que el usuario eligió
"cargar completas" — todo aislado bajo un `id_partida` propio, para que
varias carreras convivan en la misma base sin mezclarse.

Cada confederación tiene su propio calendario real: UEFA arranca su
temporada el 1 de agosto, CONMEBOL el 1 de enero — la confederación del
club elegido por el usuario arranca su primera temporada ya mismo acá; la
otra arranca sola más adelante (ver `_procesar_arranques_diferidos` en
main.py), cuando `fecha_actual` alcance su propia fecha real de inicio.

Uso por consola (crea una carrera nueva con el club por defecto, para
desarrollo/testing rápido):
    python seed.py           # no hace nada si ya hay alguna partida
    python seed.py --reset   # borra TODO (todas las carreras) y crea una
"""
import asyncio
import json
import random
import sys
from datetime import date, timedelta

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import engine, AsyncSessionLocal, Base
from models import (
    Equipo, Jugador, Tactica, PlanEntrenamiento, PersonalTecnico, Ojeador,
    Calendario, Liga, Partida, Mensaje, CicloTemporada, AfiliacionClub,
    Seleccion, ElegibilidadSeleccion, ConvocatoriaSeleccion, VentanaInternacional, PartidoSeleccion, TorneoSeleccion,
    AUTOMATIZACIONES_DEFAULT,
)
from engine.data_gen import (
    LIGAS, CLUB_NAMES, CONFEDERACION, color_para_indice, gen_squad, gen_squad_mixto,
    gen_player_real, clasificar_plantel,
    nivel_club, factor_overall_liga, presupuesto_club, objetivo_por_nivel, reputacion_club,
    random_name, random_nation,
)
from engine.copa_engine import (
    COMPETENCIAS, OFFSET_SEMANAS_GRUPO, fecha_ronda, seleccionar_participantes,
    armar_grupos, fixtures_grupo,
)
from engine.multiclub_engine import AFILIACIONES_CURADAS, GRUPOS_MARCA_CURADOS

OJEADORES_POR_CLUB = 3
LIGAS_COMPLETAS_DEFAULT = ["ARG1", "BRA1", "ESP1", "ING1"]
DIAS_LIGA = [5, 6]  # sábado, domingo (0=lunes en date.weekday()) — al azar por jornada

ANIO_BASE = 2027
MES_INICIO_CONFEDERACION = {"UEFA": 8, "CONMEBOL": 1}
# Fecha "neutra" solo para escalonar vencimientos de contrato al generar
# planteles — no necesita alinearse con el arranque real de ninguna
# confederación en particular.
FECHA_BASE_CONTRATOS = date(ANIO_BASE, 1, 1)


def preseleccion_inicial(jugadores: list[Jugador], cupo: int = 23) -> list[Jugador]:
    """Plantel inicial de una selección para datos que solo traen elegibles.

    No pretende replicar una lista oficial: mantiene tres arqueros y una
    distribución razonable por línea, ordenando por nivel actual y edad.
    """
    cuotas = {"POR": 3, "DEF": 8, "MED": 8, "DEL": 4}
    ordenados = sorted(jugadores, key=lambda j: (j.overall, -j.edad, j.potencial), reverse=True)
    elegidos: list[Jugador] = []
    for posicion, cantidad in cuotas.items():
        candidatos = [j for j in ordenados if j.posicion == posicion]
        elegidos.extend(candidatos[:cantidad])
    vistos = {j.id_jugador for j in elegidos}
    for jugador in ordenados:
        if len(elegidos) >= cupo:
            break
        if jugador.id_jugador not in vistos:
            elegidos.append(jugador)
            vistos.add(jugador.id_jugador)
    return elegidos[:cupo]


def generar_fixture(team_ids: list[int]) -> list[list[tuple[int, int]]]:
    """Round robin simple (método del círculo)."""
    ids = team_ids[:]
    n = len(ids)
    rounds = []
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            home, away = ids[i], ids[n - 1 - i]
            pairs.append((home, away) if r % 2 == 0 else (away, home))
        rounds.append(pairs)
        ids = [ids[0]] + [ids[-1]] + ids[1:-1]
    return rounds


def fecha_inicio_confederacion(confederacion: str, temporada: int) -> date:
    return date(temporada, MES_INICIO_CONFEDERACION[confederacion], 1)


async def generar_temporada_confederacion(
    session: AsyncSession, id_partida: int, confederacion: str, temporada: int, fecha_inicio: date,
) -> None:
    """Arma el fixture doméstico (solo ligas `modo="COMPLETA"`) y los 2
    torneos internacionales de UNA confederación para una temporada dada, y
    graba/actualiza su fila de `CicloTemporada`. Se usa tanto al crear la
    carrera (para la confederación del club elegido) como cada vez que esa
    confederación arranca/rearma su temporada (ver main.py)."""
    ligas = (await session.execute(
        select(Liga).where(Liga.id_partida == id_partida, Liga.confederacion == confederacion)
    )).scalars().all()
    ids_liga = [l.id_liga for l in ligas]
    equipos = (await session.execute(select(Equipo).where(Equipo.id_liga.in_(ids_liga)))).scalars().all() if ids_liga else []
    ids_equipo = [e.id_equipo for e in equipos]
    jugadores = (await session.execute(select(Jugador).where(Jugador.id_equipo.in_(ids_equipo)))).scalars().all() if ids_equipo else []

    # Un día random (viernes o sábado) por número de jornada, sorteado UNA
    # sola vez y reusado para todas las ligas de la confederación — así
    # todas siguen jugando la misma jornada el mismo día, como ya asume el
    # resto del motor (_cerrar_jornada_del_dia resuelve por fecha exacta).
    # Lazy (no un rango fijo precalculado): con datos personalizados una
    # liga puede tener más o menos de 20 clubes (ej. Argentina real, 30),
    # lo que cambia cuántas jornadas necesita un round-robin simple.
    lunes_inicio = fecha_inicio - timedelta(days=fecha_inicio.weekday())
    dia_por_jornada: dict[int, int] = {}
    calendario_a_insertar: list[dict] = []

    def _dia_de(num_jornada: int) -> int:
        if num_jornada not in dia_por_jornada:
            dia_por_jornada[num_jornada] = random.choice(DIAS_LIGA)
        return dia_por_jornada[num_jornada]

    for liga in ligas:
        if liga.modo != "COMPLETA":
            continue
        team_ids = [e.id_equipo for e in equipos if e.id_liga == liga.id_liga]
        if len(team_ids) < 2:
            continue
        fixture = generar_fixture(team_ids)
        for num_jornada, pairs in enumerate(fixture, start=1):
            fecha_jornada = lunes_inicio + timedelta(weeks=num_jornada - 1, days=_dia_de(num_jornada))
            for home, away in pairs:
                calendario_a_insertar.append({
                    "id_partida": id_partida, "id_liga": liga.id_liga, "num_jornada": num_jornada,
                    "fecha": fecha_jornada, "id_local": home, "id_visitante": away, "tipo": "LIGA",
                })

    jugadores_por_equipo: dict[int, list[Jugador]] = {}
    for j in jugadores:
        jugadores_por_equipo.setdefault(j.id_equipo, []).append(j)
    overall_por_club = [
        (id_eq, sum(j.overall for j in js) / len(js))
        for id_eq, js in jugadores_por_equipo.items() if js
    ]
    top, segundo = seleccionar_participantes(overall_por_club, cupo=32)
    nombres_competencia = COMPETENCIAS[confederacion]
    for participantes, nombre_competencia in ((top, nombres_competencia["top"]), (segundo, nombres_competencia["segundo"])):
        if len(participantes) < 8:
            continue
        for nombre_grupo, equipos_grupo in armar_grupos(participantes).items():
            for num_jornada, pares in enumerate(fixtures_grupo(equipos_grupo), start=1):
                fecha_md = fecha_ronda(fecha_inicio, OFFSET_SEMANAS_GRUPO[num_jornada - 1])
                for local, visita in pares:
                    calendario_a_insertar.append({
                        "id_partida": id_partida, "id_liga": None, "num_jornada": num_jornada,
                        "fecha": fecha_md, "id_local": local, "id_visitante": visita,
                        "tipo": "COPA", "competencia": nombre_competencia, "ronda_copa": nombre_grupo,
                    })

    if calendario_a_insertar:
        await session.execute(insert(Calendario), calendario_a_insertar)

    ciclo = await session.get(CicloTemporada, (id_partida, confederacion))
    if ciclo:
        ciclo.temporada = temporada
        ciclo.fecha_inicio = fecha_inicio
    else:
        session.add(CicloTemporada(id_partida=id_partida, confederacion=confederacion, temporada=temporada, fecha_inicio=fecha_inicio))


async def crear_partida(
    session: AsyncSession,
    nombre_dt: str,
    dataset: str = "ficticia",
    codigo_liga_elegida: str | None = None,
    nombre_club_elegido: str | None = None,
    nombres_clubes_custom: dict[str, list[tuple[str, str]]] | None = None,
    jugadores_clubes_custom: dict[str, dict[str, list[dict]]] | None = None,
    competencias_custom: dict[str, str] | None = None,
    ligas_completas: list[str] | None = None,
    metadata_clubes_custom: dict | None = None,
    configuracion_pack: dict | None = None,
) -> int:
    """Genera una carrera nueva completa (9 ligas, ~180 clubes, planteles) y
    devuelve su `id_partida`. El club que pasa a ser del usuario se elige
    por (codigo_liga_elegida, nombre_club_elegido) — si no coincide ninguno
    (o no se pasó), se randomiza entre todos los generados.

    `ligas_completas`: códigos de liga a cargar "completas" (con fixture y
    tabla propia) — el resto queda "de vista" (clubes y jugadores generados
    igual, elegibles para scouting/transferencias/torneos internacionales,
    pero sin liga doméstica propia). La liga del club elegido se fuerza a
    completa. Default: las 4 ligas originales.

    `nombres_clubes_custom`, si se pasa (dataset "personalizada"), reemplaza
    `CLUB_NAMES` para esa liga — así el usuario puede poner los nombres de
    club que quiera (bajo su propia responsabilidad, el juego no genera ni
    valida esos nombres), y con LA CANTIDAD que quiera (no tiene que ser
    20 clubes; ej. la liga argentina real tiene 30). Cada club es una lista
    de 2 a 4 elementos: (codigo, nombre[, escudo_url[, nombre_competencia]])
    — escudo_url se guarda en Equipo.escudo_url; nombre_competencia
    reemplaza Liga.nombre para toda esa liga (si se repite en varias filas,
    gana la última no vacía). A diferencia de una liga ficticia (que se
    muestra como "CODIGO - Nombre" para distinguir clubes de "aire"
    parecido), acá `Equipo.nombre` es el nombre real solo, sin el código
    antepuesto — el código sigue usándose puertas adentro para vincular
    jugadores reales (`jugadores_clubes_custom`), solo no se muestra.

    `jugadores_clubes_custom`, si se pasa, agrega jugadores reales puntuales
    a los clubes indicados, anidado por liga y código de club —
    {"ARG1": {"BOC": [...]}, ...} (ver PaqueteClubes.jugadores_json). Anidar
    por liga es necesario porque el código de club NO es único entre ligas
    (ej. "BOC" existe en ARG1 y en ALE1). El resto del plantel de esos
    clubes, y los clubes no listados, se generan ficticios como siempre.

    `competencias_custom`, si se pasa, reemplaza el nombre por defecto de las
    copas internacionales para esta partida (ver
    engine/copa_engine.py COMPETENCIAS/NOMBRES_COMPETENCIA_DEFAULT) — se
    guarda en Partida.competencias_json."""
    configuracion_pack = configuracion_pack or {}
    ligas_completas = set(ligas_completas or LIGAS_COMPLETAS_DEFAULT)
    if codigo_liga_elegida:
        ligas_completas.add(codigo_liga_elegida)

    # La fecha real se termina de fijar más abajo, una vez elegido el club
    # del usuario (y con él, su confederación) — acá todavía no importa.
    partida = Partida(
        nombre_dt=nombre_dt, dataset=dataset, fecha_actual=FECHA_BASE_CONTRATOS,
        competencias_json=json.dumps(competencias_custom) if competencias_custom else None,
        automatizaciones_json=json.dumps(AUTOMATIZACIONES_DEFAULT),
    )
    session.add(partida)
    await session.flush()  # asigna id_partida

    equipos_candidatos_usuario: list[Equipo] = []
    nivel_por_equipo: dict[int, float] = {}
    # Referencias estables del pack: los nombres personalizados no conservan
    # el prefijo de código en Equipo.nombre.
    equipo_por_clave: dict[tuple[str, str], Equipo] = {}
    cesiones_pendientes: list[tuple[str, dict, str]] = []
    jugador_por_referencia: dict[str, Jugador] = {}
    jugadores_a_insertar: list[dict] = []
    from pack_contracts import contrato_importado
    from pack_market import valor_importado
    confederacion_referencia = CONFEDERACION.get(codigo_liga_elegida or "", "UEFA")
    fecha_referencia_importacion = fecha_inicio_confederacion(confederacion_referencia, ANIO_BASE) - timedelta(days=31)

    for codigo_liga in LIGAS:
        if configuracion_pack.get("solo_clubes_pack") and codigo_liga not in (nombres_clubes_custom or {}):
            continue
        info = LIGAS[codigo_liga]
        liga = Liga(
            id_partida=partida.id_partida, codigo=codigo_liga, pais=info["pais"], nombre=info["nombre"],
            confederacion=CONFEDERACION[codigo_liga],
            modo="COMPLETA" if codigo_liga in ligas_completas else "VISTA",
        )
        session.add(liga)
        await session.flush()  # asigna id_liga

        es_custom = codigo_liga in (nombres_clubes_custom or {})
        clubes = (nombres_clubes_custom or {}).get(codigo_liga) or CLUB_NAMES[codigo_liga]
        niveles = [nivel_club(i, len(clubes)) for i in range(len(clubes))]

        # Filas de 2 a 4 elementos: (codigo, nombre[, escudo_url[,
        # nombre_competencia]]) — si alguna fila trae nombre_competencia, la
        # última no vacía reemplaza el nombre ficticio de la liga entera.
        for fila in clubes:
            if len(fila) >= 4 and fila[3]:
                liga.nombre = fila[3]

        equipos = []
        for i, fila in enumerate(clubes):
            codigo_club, nombre_club = fila[0], fila[1]
            escudo_url = fila[2] if len(fila) >= 3 and fila[2] else None
            presupuesto = presupuesto_club(codigo_liga, niveles[i])
            reputacion_eq = reputacion_club(codigo_liga, niveles[i])
            eq = Equipo(
                id_partida=partida.id_partida,
                id_liga=liga.id_liga,
                # Datos personalizados: el nombre real se muestra solo, sin
                # el código interno de club antepuesto (ese código sigue
                # existiendo para vincular jugadores reales, pero no tiene
                # sentido mostrarlo junto a un nombre real como sí lo tiene
                # con los nombres ficticios, que lo llevan para distinguir
                # clubes con "aire" parecido dentro de la misma liga).
                nombre=nombre_club if es_custom else f"{codigo_club} - {nombre_club}",
                color=color_para_indice(i),
                es_usuario=False,
                presupuesto_fichajes=presupuesto,
                presupuesto_salarios=round(presupuesto * 0.3 / 10_000) * 10_000,
                reputacion=reputacion_eq,
                escudo_url=escudo_url,
                datos_pack_json=json.dumps((metadata_clubes_custom or {}).get(codigo_liga, {}).get(codigo_club, {}), ensure_ascii=False),
            )
            session.add(eq)
            equipos.append(eq)
            equipo_por_clave[(codigo_liga, codigo_club)] = eq
        codigos_club = [fila[0] for fila in clubes]
        await session.flush()  # asigna ids
        for i, eq in enumerate(equipos):
            nivel_por_equipo[eq.id_equipo] = niveles[i]

        if codigo_liga == codigo_liga_elegida:
            equipos_candidatos_usuario = equipos
        elif not codigo_liga_elegida:
            equipos_candidatos_usuario.extend(equipos)

        for i, eq in enumerate(equipos):
            session.add(Tactica(id_equipo=eq.id_equipo))
            session.add(PlanEntrenamiento(id_equipo=eq.id_equipo))
            session.add(PersonalTecnico(id_equipo=eq.id_equipo, nombre_asistente=random_name(random_nation())))
            for _ in range(OJEADORES_POR_CLUB):
                session.add(Ojeador(
                    id_partida=partida.id_partida, id_equipo=eq.id_equipo,
                    nombre=random_name(random_nation()), calidad=random.randint(30, 90),
                ))
            factor = factor_overall_liga(codigo_liga, niveles[i])
            datos_reales = (jugadores_clubes_custom or {}).get(codigo_liga, {}).get(codigos_club[i])
            if datos_reales:
                jugadores_reales = [gen_player_real(d) for d in datos_reales]
                for pdata, origen in zip(jugadores_reales, datos_reales):
                    pdata["datos_pack_json"] = json.dumps(origen, ensure_ascii=False)
                plantel = jugadores_reales if configuracion_pack.get("rellenar_planteles") is False else gen_squad_mixto(jugadores_reales, factor=factor)
            elif configuracion_pack.get("rellenar_planteles") is False:
                raise ValueError(f"El pack no contiene jugadores para {codigo_liga}/{codigos_club[i]}")
            else:
                plantel = gen_squad(factor=factor)
            clasificar_plantel(plantel)
            for pdata in plantel:
                # Contratos escalonados: entre 2 meses y 4 años desde el
                # arranque, para que desde el día 1 ya haya algunos
                # jugadores a <=180 días de quedar libres (precontrato).
                # Un pack puede aportar fecha de contrato real. La fecha
                # escalonada se reserva para jugadores sin ese dato.
                fecha_contrato = pdata.get("fecha_fin_contrato")
                if isinstance(fecha_contrato, str):
                    try:
                        fecha_contrato = date.fromisoformat(fecha_contrato)
                    except ValueError:
                        fecha_contrato = None
                pdata["fecha_fin_contrato"] = fecha_contrato or (FECHA_BASE_CONTRATOS + timedelta(days=random.randint(60, 4 * 365)))
                try:
                    origen = json.loads(pdata.get("datos_pack_json") or "{}")
                except (TypeError, json.JSONDecodeError):
                    origen = {}
                if origen:
                    # La calibración se hace antes de insertar. Así se evita
                    # una segunda pasada de miles de UPDATEs al terminar la
                    # creación de una carrera con el PMPack.
                    contrato, detalle_contrato = contrato_importado(origen, fecha_referencia_importacion)
                    pdata.update(contrato)
                    valor_inicial = pdata.get("valor_mercado", 50_000)
                    valor_mercado, calibracion = valor_importado(origen, valor_inicial)
                    calibracion.update(version=1, valor_inicial_usd=valor_inicial)
                    origen["contrato_importado"] = detalle_contrato
                    origen["calibracion_valor"] = calibracion
                    pdata["valor_mercado"] = valor_mercado
                    pdata["datos_pack_json"] = json.dumps(origen, ensure_ascii=False)
                cesion = origen.get("cesion") if isinstance(origen.get("cesion"), dict) else {}
                referencia = origen.get("codigo") or origen.get("id") or (origen.get("datos_fuente") or {}).get("id")
                if referencia is not None:
                    if cesion.get("club_dueno_codigo"):
                        cesiones_pendientes.append((str(referencia), cesion, codigo_liga))
                jugadores_a_insertar.append({
                    "id_partida": partida.id_partida,
                    "id_equipo": eq.id_equipo,
                    **pdata,
                })

    # Afiliaciones multiclub curadas (ver engine/multiclub_engine.py) — recién
    # acá existen TODOS los Equipo de TODAS las ligas (los pares curados
    # cruzan liga, ej. MANC es ING1 pero GIR es ESP1). Se busca por el
    # prefijo "CODIGO - " de Equipo.nombre en TODAS las ligas, no solo las
    # ficticias: en "datos personalizados" el código no lo antepone el
    # juego, pero si el propio nombre subido por el usuario ya lo trae
    # (ej. "MANC - Manchester City"), el match funciona igual. Si no lo
    # trae, este club simplemente no matchea ninguna clave curada — no
    # rompe nada, solo no se siembra ahí.
    # Los planteles reales se insertan en bloque. Antes se agregaban miles de
    # instancias ORM y el viaje a PostgreSQL podía dejar la creación de carrera
    # esperando varios minutos.
    if jugadores_a_insertar:
        await session.execute(insert(Jugador), jugadores_a_insertar)
    jugadores_partida = (await session.execute(
        select(Jugador).where(Jugador.id_partida == partida.id_partida)
    )).scalars().all()
    for jugador in jugadores_partida:
        try:
            origen = json.loads(jugador.datos_pack_json or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        referencia = origen.get("codigo") or origen.get("id") or (origen.get("datos_fuente") or {}).get("id")
        if referencia is not None:
            jugador_por_referencia[str(referencia)] = jugador

    # La ficha se agrupa bajo el club donde juega. El bloque `cesion` del
    # pack conserva el dueño y condiciones para que el jugador aparezca en
    # Plantel del destino y en Centro de Desarrollo del club dueño.
    for referencia, cesion, liga_destino in cesiones_pendientes:
        jugador = jugador_por_referencia.get(referencia)
        if not jugador:
            continue
        liga_dueno = cesion.get("liga_dueno") or liga_destino
        dueno = equipo_por_clave.get((liga_dueno, str(cesion["club_dueno_codigo"])))
        if not dueno or dueno.id_equipo == jugador.id_equipo:
            continue
        jugador.id_equipo_dueno = dueno.id_equipo
        fecha_fin = cesion.get("fin")
        if fecha_fin:
            try:
                jugador.fin_cesion = date.fromisoformat(fecha_fin)
            except ValueError:
                pass
        jugador.opcion_compra = cesion.get("opcion_compra") or None

    # Un pmpack puede describir la red real con sus propios códigos; las
    # afiliaciones curadas siguen siendo el fallback de la base ficticia.
    multiclub_pack = configuracion_pack.get("multiclub") if isinstance(configuracion_pack.get("multiclub"), dict) else {}
    relaciones_multiclub = list(AFILIACIONES_CURADAS) + list(multiclub_pack.get("afiliaciones") or [])
    relaciones_vistas: set[tuple[int, int]] = set()
    for rel in relaciones_multiclub:
        inv = equipo_por_clave.get((rel["liga_inversor"], rel["codigo_inversor"]))
        part = equipo_por_clave.get((rel["liga_participado"], rel["codigo_participado"]))
        if inv and part and inv.id_equipo != part.id_equipo and (inv.id_equipo, part.id_equipo) not in relaciones_vistas:
            relaciones_vistas.add((inv.id_equipo, part.id_equipo))
            session.add(AfiliacionClub(
                id_partida=partida.id_partida, id_equipo_inversor=inv.id_equipo, id_equipo_participado=part.id_equipo,
                porcentaje=int(rel.get("porcentaje", 20)), tipo_relacion=rel.get("tipo", "SATELITE"), fecha_adquisicion=FECHA_BASE_CONTRATOS,
            ))

    for grupo in list(GRUPOS_MARCA_CURADOS) + list(multiclub_pack.get("redes_marca") or []):
        for liga_codigo, club_codigo in grupo["miembros"]:
            eq = equipo_por_clave.get((liga_codigo, club_codigo))
            if eq:
                eq.red_marca = grupo["grupo_marca"]

    # Selecciones: el archivo selecciones.json del pack queda disponible en
    # configuracion_pack["selecciones"]. Cada jugador con misma nacionalidad
    # queda elegible de entrada; el pack puede sumar doble nacionalidad o
    # bloquear casos mediante elegibilidades explícitas.
    selecciones_pack = configuracion_pack.get("selecciones") if isinstance(configuracion_pack.get("selecciones"), dict) else {}
    selecciones_por_codigo: dict[str, Seleccion] = {}
    for datos in selecciones_pack.get("equipos", []):
        if not isinstance(datos, dict) or not datos.get("codigo") or not datos.get("nombre"):
            continue
        seleccion = Seleccion(
            id_partida=partida.id_partida, codigo=str(datos["codigo"]), nombre=datos["nombre"],
            pais=datos.get("pais") or datos["nombre"], confederacion=datos.get("confederacion") or "",
            categoria=datos.get("categoria") or "MAYOR", ranking=datos.get("ranking"),
            seleccionador=datos.get("seleccionador"), datos_pack_json=json.dumps(datos, ensure_ascii=False),
        )
        session.add(seleccion)
        selecciones_por_codigo[seleccion.codigo] = seleccion
    await session.flush()
    # Índice de nacionalidad: evita comparar cada jugador contra todas las
    # selecciones del PMPack al crear una carrera grande.
    jugadores_por_nacionalidad: dict[str, list[Jugador]] = {}
    for jugador in jugadores_partida:
        jugadores_por_nacionalidad.setdefault(jugador.nacionalidad.strip().casefold(), []).append(jugador)
    # Solo las selecciones que jugarán su primera ventana necesitan plantel
    # inmediatamente. Las demás se materializan al abrirlas: el PMPack y sus
    # jugadores ya están disponibles desde el inicio, sin demorar la carrera
    # creando miles de filas que todavía no se van a consultar.
    convocatorias_pack = [d for d in selecciones_pack.get("convocatorias", []) if isinstance(d, dict)]
    codigos_iniciales = set(selecciones_pack.get("activas") or [])
    codigos_iniciales.update(str(d.get("seleccion_codigo", "")) for d in selecciones_pack.get("elegibilidades", []) if isinstance(d, dict))
    codigos_iniciales.update(str(d.get("seleccion_codigo", "")) for d in convocatorias_pack)
    # Se insertan por lote: con miles de jugadores, agregar una instancia ORM
    # por elegibilidad hacía que una carrera con el PMPack pareciera detenida.
    elegibilidades_por_clave: dict[tuple[int, int], dict] = {}
    elegibles_por_seleccion: dict[int, list[Jugador]] = {}
    for codigo, seleccion in selecciones_por_codigo.items():
        if codigo not in codigos_iniciales:
            continue
        elegibles = jugadores_por_nacionalidad.get(seleccion.pais.strip().casefold(), [])
        elegibles_por_seleccion[seleccion.id_seleccion] = list(elegibles)
        for jugador in elegibles:
            clave = (seleccion.id_seleccion, jugador.id_jugador)
            elegibilidades_por_clave[clave] = {
                "id_seleccion": seleccion.id_seleccion,
                "id_jugador": jugador.id_jugador,
                "estado": "ELEGIBLE",
                "partidos_oficiales": 0,
            }
    for datos in selecciones_pack.get("elegibilidades", []):
        if not isinstance(datos, dict):
            continue
        seleccion = selecciones_por_codigo.get(str(datos.get("seleccion_codigo", "")))
        jugador = jugador_por_referencia.get(str(datos.get("jugador_codigo", "")))
        if seleccion and jugador:
            clave = (seleccion.id_seleccion, jugador.id_jugador)
            existente = elegibilidades_por_clave.get(clave)
            if existente:
                existente["estado"] = datos.get("estado") or existente["estado"]
                existente["partidos_oficiales"] = int(datos.get("partidos_oficiales") or existente["partidos_oficiales"] or 0)
                existente["datos_pack_json"] = json.dumps(datos, ensure_ascii=False)
            else:
                elegibilidades_por_clave[clave] = {
                    "id_seleccion": seleccion.id_seleccion,
                    "id_jugador": jugador.id_jugador,
                    "estado": datos.get("estado") or "ELEGIBLE",
                    "partidos_oficiales": int(datos.get("partidos_oficiales") or 0),
                    "datos_pack_json": json.dumps(datos, ensure_ascii=False),
                }
    if elegibilidades_por_clave:
        await session.execute(insert(ElegibilidadSeleccion), list(elegibilidades_por_clave.values()))
    for datos in convocatorias_pack:
        seleccion = selecciones_por_codigo.get(str(datos.get("seleccion_codigo", "")))
        jugador = jugador_por_referencia.get(str(datos.get("jugador_codigo", "")))
        if seleccion and jugador:
            session.add(ConvocatoriaSeleccion(id_seleccion=seleccion.id_seleccion, id_jugador=jugador.id_jugador,
                        estado=datos.get("estado") or "CONVOCADO"))

    # Si la fuente no aportó una convocatoria vigente, cada selección mayor
    # comienza con una preselección de juego. No se usa para afirmar que sea
    # una nómina oficial; permite que la pantalla internacional y futuras
    # ventanas FIFA tengan un plantel desde el primer día.
    convocatorias_explicitas = {(str(d.get("seleccion_codigo", "")), str(d.get("jugador_codigo", "")))
                                for d in convocatorias_pack}
    jugadores_por_id = {jugador.id_jugador: jugador for jugador in jugadores_partida}
    for codigo, seleccion in selecciones_por_codigo.items():
        if seleccion.categoria != "MAYOR" or codigo not in codigos_iniciales:
            continue
        elegibles = elegibles_por_seleccion.get(seleccion.id_seleccion, [])
        if any(sel_codigo == codigo for sel_codigo, _ in convocatorias_explicitas):
            continue
        for jugador in preseleccion_inicial(elegibles):
            session.add(ConvocatoriaSeleccion(id_seleccion=seleccion.id_seleccion, id_jugador=jugador.id_jugador,
                        estado="PRESELECCION"))

    # Elegir el club del usuario: por nombre exacto si se pasó, si no al azar
    # entre los candidatos (los de la liga elegida, o todos si no se eligió).
    equipo_usuario = None
    if nombre_club_elegido:
        equipo_usuario = next((e for e in equipos_candidatos_usuario if e.nombre == nombre_club_elegido), None)
    if not equipo_usuario and equipos_candidatos_usuario:
        equipo_usuario = random.choice(equipos_candidatos_usuario)

    # La confederación del club elegido arranca su primera temporada YA
    # (con la partida arrancando un mes antes, a modo de pretemporada); la
    # otra confederación arranca sola más adelante, el día que `fecha_actual`
    # llegue a su propia fecha real de inicio (ver main.py).
    confederacion_usuario = "UEFA"
    if equipo_usuario:
        liga_usuario = await session.get(Liga, equipo_usuario.id_liga)
        confederacion_usuario = liga_usuario.confederacion
        liga_usuario.modo = "COMPLETA"  # por si el club salió de un sorteo total y su liga había quedado "de vista"

    fecha_inicio_confed = fecha_inicio_confederacion(confederacion_usuario, ANIO_BASE)
    partida.fecha_actual = fecha_inicio_confed - timedelta(days=31)
    # Fechas internacionales configurables por pack. Si no trae calendario,
    # el juego usa cinco ventanas anuales de simulación; no representan un
    # calendario oficial ni fuerzan una convocatoria manual del usuario.
    ventanas_pack = selecciones_pack.get("ventanas") if isinstance(selecciones_pack.get("ventanas"), list) else []
    if not ventanas_pack and selecciones_por_codigo:
        ventanas_pack = [
            {"nombre": "Ventana internacional de marzo", "inicio": f"{ANIO_BASE}-03-22", "fin": f"{ANIO_BASE}-03-30"},
            {"nombre": "Ventana internacional de junio", "inicio": f"{ANIO_BASE}-06-01", "fin": f"{ANIO_BASE}-06-09"},
            {"nombre": "Ventana internacional de septiembre", "inicio": f"{ANIO_BASE}-09-06", "fin": f"{ANIO_BASE}-09-14"},
            {"nombre": "Ventana internacional de octubre", "inicio": f"{ANIO_BASE}-10-04", "fin": f"{ANIO_BASE}-10-12"},
            {"nombre": "Ventana internacional de noviembre", "inicio": f"{ANIO_BASE}-11-08", "fin": f"{ANIO_BASE}-11-16"},
        ]
    ventanas_creadas: list[VentanaInternacional] = []
    for ventana in ventanas_pack:
        try:
            inicio, fin = date.fromisoformat(ventana["inicio"]), date.fromisoformat(ventana["fin"])
        except (KeyError, TypeError, ValueError):
            continue
        if fin >= inicio:
            ventana_creada = VentanaInternacional(id_partida=partida.id_partida, nombre=ventana.get("nombre") or "Ventana internacional",
                        fecha_inicio=inicio, fecha_fin=fin, tipo=ventana.get("tipo") or "FECHA_FIFA",
                        codigos_selecciones_json=json.dumps(selecciones_pack.get("activas") or []))
            session.add(ventana_creada)
            ventanas_creadas.append(ventana_creada)
    # Torneos y clasificaciones: el pack aporta grupos y fixture explícito.
    # No se generan competiciones ni fechas "reales" de forma inventada.
    await session.flush()
    activas = [selecciones_por_codigo[codigo] for codigo in selecciones_pack.get("activas", []) if codigo in selecciones_por_codigo]
    torneos_pack = selecciones_pack.get("torneos") if isinstance(selecciones_pack.get("torneos"), list) else []
    ventanas_con_torneo: set[int] = set()
    for datos_torneo in torneos_pack:
        if not isinstance(datos_torneo, dict) or not datos_torneo.get("codigo") or not datos_torneo.get("nombre"):
            continue
        torneo = TorneoSeleccion(
            id_partida=partida.id_partida, codigo=str(datos_torneo["codigo"]), nombre=str(datos_torneo["nombre"]),
            tipo=str(datos_torneo.get("tipo") or "CLASIFICACION"),
            grupos_json=json.dumps(datos_torneo.get("grupos") or [], ensure_ascii=False),
            datos_pack_json=json.dumps(datos_torneo, ensure_ascii=False),
        )
        session.add(torneo)
        await session.flush()
        participantes = {codigo for grupo in datos_torneo.get("grupos", []) if isinstance(grupo, dict)
                         for codigo in grupo.get("selecciones", []) if codigo in selecciones_por_codigo}
        for fixture in datos_torneo.get("partidos", []):
            if not isinstance(fixture, dict):
                continue
            local = selecciones_por_codigo.get(str(fixture.get("local", "")))
            visitante = selecciones_por_codigo.get(str(fixture.get("visitante", "")))
            try:
                fecha_fixture = date.fromisoformat(str(fixture["fecha"]))
            except (KeyError, TypeError, ValueError):
                continue
            if not local or not visitante:
                continue
            participantes.update((local.codigo, visitante.codigo))
            ventana = next((v for v in ventanas_creadas if v.fecha_inicio <= fecha_fixture <= v.fecha_fin), None)
            if ventana is None:
                ventana = VentanaInternacional(
                    id_partida=partida.id_partida, nombre=f"{torneo.nombre} · fecha internacional",
                    fecha_inicio=fecha_fixture - timedelta(days=2), fecha_fin=fecha_fixture + timedelta(days=2),
                    tipo="TORNEO", codigos_selecciones_json=json.dumps(sorted(participantes)),
                )
                session.add(ventana)
                await session.flush()
                ventanas_creadas.append(ventana)
            ventanas_con_torneo.add(ventana.id_ventana)
            session.add(PartidoSeleccion(
                id_partida=partida.id_partida, id_torneo=torneo.id_torneo, id_ventana=ventana.id_ventana,
                id_local=local.id_seleccion, id_visitante=visitante.id_seleccion, fecha=fecha_fixture,
                tipo=str(fixture.get("tipo") or "CLASIFICACION"), competencia=torneo.nombre,
                grupo=fixture.get("grupo"), jornada=fixture.get("jornada"), oficial=True,
            ))
    # Amistosos automáticos solo en ventanas que el pack no ocupó con un torneo.
    for indice, ventana in enumerate(ventanas_creadas):
        if ventana.id_ventana in ventanas_con_torneo:
            continue
        rotadas = activas[indice:] + activas[:indice]
        for local, visitante in zip(rotadas[::2], rotadas[1::2]):
            session.add(PartidoSeleccion(id_partida=partida.id_partida, id_ventana=ventana.id_ventana,
                        id_local=local.id_seleccion, id_visitante=visitante.id_seleccion,
                        fecha=min(ventana.fecha_fin, ventana.fecha_inicio + timedelta(days=3)), tipo="AMISTOSO",
                        competencia="Fecha internacional"))
    await generar_temporada_confederacion(session, partida.id_partida, confederacion_usuario, ANIO_BASE, fecha_inicio_confed)

    if equipo_usuario:
        equipo_usuario.es_usuario = True
        nivel_usuario = nivel_por_equipo.get(equipo_usuario.id_equipo, 0.5)
        partida.objetivo_temporada = objetivo_por_nivel(nivel_usuario)
        partida.contrato_dt_anios = random.randint(1, 3)
        partida.contrato_dt_fecha_fin = partida.fecha_actual + timedelta(days=365 * partida.contrato_dt_anios)
        session.add(Mensaje(
            id_equipo_destino=equipo_usuario.id_equipo,
            remitente="Directiva del Club",
            asunto="Bienvenido y objetivos de la temporada",
            contenido=(
                f"Le damos la bienvenida a {equipo_usuario.nombre}. Objetivo de la temporada: {partida.objetivo_temporada} "
                f"Contrato inicial firmado por {partida.contrato_dt_anios} año(s)."
            ),
            fecha=partida.fecha_actual,
            tipo="SISTEMA",
        ))

    await session.commit()
    return partida.id_partida


async def seed(reset: bool = False):
    """Solo para desarrollo/testing por consola: crea una carrera de prueba
    con el club por defecto (primero de ARG1) si no hay ninguna partida."""
    async with engine.begin() as conn:
        if reset:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:  # type: AsyncSession
        existing = (await session.execute(select(Partida))).scalars().first()
        if existing and not reset:
            print("Ya hay al menos una partida cargada. Usá --reset para borrar todo y regenerar.")
            return

        primer_club = CLUB_NAMES["ARG1"][0]
        nombre_club_default = f"{primer_club[0]} - {primer_club[1]}"
        id_partida = await crear_partida(
            session, nombre_dt="DT", dataset="ficticia",
            codigo_liga_elegida="ARG1", nombre_club_elegido=nombre_club_default,
        )
        print(f"Partida creada (id_partida={id_partida}).")

        equipo_usuario = (await session.execute(
            select(Equipo).where(Equipo.id_partida == id_partida, Equipo.es_usuario.is_(True))
        )).scalars().first()
        if equipo_usuario:
            print(f"Tu club (es_usuario=True): {equipo_usuario.nombre} (id={equipo_usuario.id_equipo})")


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    asyncio.run(seed(reset=reset))
