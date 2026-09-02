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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import engine, AsyncSessionLocal, Base
from models import (
    Equipo, Jugador, Tactica, PlanEntrenamiento, PersonalTecnico, Ojeador,
    Calendario, Liga, Partida, Mensaje, CicloTemporada, AfiliacionClub,
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
                session.add(Calendario(
                    id_partida=id_partida, id_liga=liga.id_liga, num_jornada=num_jornada,
                    fecha=fecha_jornada, id_local=home, id_visitante=away, tipo="LIGA",
                ))

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
                    session.add(Calendario(
                        id_partida=id_partida, id_liga=None, num_jornada=num_jornada,
                        fecha=fecha_md, id_local=local, id_visitante=visita,
                        tipo="COPA", competencia=nombre_competencia, ronda_copa=nombre_grupo,
                    ))

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
    ligas_completas = set(ligas_completas or LIGAS_COMPLETAS_DEFAULT)
    if codigo_liga_elegida:
        ligas_completas.add(codigo_liga_elegida)

    # La fecha real se termina de fijar más abajo, una vez elegido el club
    # del usuario (y con él, su confederación) — acá todavía no importa.
    partida = Partida(
        nombre_dt=nombre_dt, dataset=dataset, fecha_actual=FECHA_BASE_CONTRATOS,
        competencias_json=json.dumps(competencias_custom) if competencias_custom else None,
    )
    session.add(partida)
    await session.flush()  # asigna id_partida

    equipos_candidatos_usuario: list[Equipo] = []
    nivel_por_equipo: dict[int, float] = {}
    # Ligas ficticias (no personalizadas) de esta partida — las afiliaciones
    # multiclub curadas solo se siembran ahí, porque el código de club es
    # recuperable del prefijo de Equipo.nombre (ver más abajo).
    ligas_ficticias: set[str] = set()

    for codigo_liga in LIGAS:
        info = LIGAS[codigo_liga]
        liga = Liga(
            id_partida=partida.id_partida, codigo=codigo_liga, pais=info["pais"], nombre=info["nombre"],
            confederacion=CONFEDERACION[codigo_liga],
            modo="COMPLETA" if codigo_liga in ligas_completas else "VISTA",
        )
        session.add(liga)
        await session.flush()  # asigna id_liga

        es_custom = codigo_liga in (nombres_clubes_custom or {})
        if not es_custom:
            ligas_ficticias.add(codigo_liga)
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
            )
            session.add(eq)
            equipos.append(eq)
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
                plantel = gen_squad_mixto(jugadores_reales, factor=factor)
            else:
                plantel = gen_squad(factor=factor)
            clasificar_plantel(plantel)
            for pdata in plantel:
                # Contratos escalonados: entre 2 meses y 4 años desde el
                # arranque, para que desde el día 1 ya haya algunos
                # jugadores a <=180 días de quedar libres (precontrato).
                pdata["fecha_fin_contrato"] = FECHA_BASE_CONTRATOS + timedelta(days=random.randint(60, 4 * 365))
                session.add(Jugador(id_partida=partida.id_partida, id_equipo=eq.id_equipo, **pdata))

    # Afiliaciones multiclub curadas (ver engine/multiclub_engine.py) — recién
    # acá existen TODOS los Equipo de TODAS las ligas (los pares curados
    # cruzan liga, ej. MANC es ING1 pero GIR es ESP1), y solo tiene sentido
    # en ligas ficticias (en "datos personalizados" el código de club no es
    # recuperable del nombre, que es el nombre real tal cual lo subió el usuario).
    if ligas_ficticias:
        filas = (await session.execute(
            select(Equipo, Liga.codigo).join(Liga, Equipo.id_liga == Liga.id_liga)
            .where(Liga.id_partida == partida.id_partida, Liga.codigo.in_(ligas_ficticias))
        )).all()
        equipo_por_clave = {(codigo_liga_eq, eq.nombre.split(" - ", 1)[0]): eq for eq, codigo_liga_eq in filas}

        for rel in AFILIACIONES_CURADAS:
            inv = equipo_por_clave.get((rel["liga_inversor"], rel["codigo_inversor"]))
            part = equipo_por_clave.get((rel["liga_participado"], rel["codigo_participado"]))
            if inv and part:
                session.add(AfiliacionClub(
                    id_partida=partida.id_partida, id_equipo_inversor=inv.id_equipo, id_equipo_participado=part.id_equipo,
                    porcentaje=rel["porcentaje"], tipo_relacion=rel["tipo"], fecha_adquisicion=FECHA_BASE_CONTRATOS,
                ))

        for grupo in GRUPOS_MARCA_CURADOS:
            for liga_codigo, club_codigo in grupo["miembros"]:
                eq = equipo_por_clave.get((liga_codigo, club_codigo))
                if eq:
                    eq.red_marca = grupo["grupo_marca"]

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
