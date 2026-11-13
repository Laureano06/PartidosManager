"""Consulta de selecciones importadas desde un Data Pack."""
from fastapi import APIRouter

from api.runtime import (
    AsyncSession, ConvocatoriaSeleccion, Depends, ElegibilidadSeleccion,
    HTTPException, Jugador, PartidoSeleccion, Seleccion, TorneoSeleccion, VentanaInternacional, get_db, select, json,
)

router = APIRouter(tags=["Selecciones"])


@router.get("/partidas/{id_partida}/ventanas-internacionales")
async def listar_ventanas_internacionales(id_partida: int, db: AsyncSession = Depends(get_db)):
    ventanas = (await db.execute(select(VentanaInternacional).where(
        VentanaInternacional.id_partida == id_partida).order_by(VentanaInternacional.fecha_inicio)
    )).scalars().all()
    return [{"id_ventana": v.id_ventana, "nombre": v.nombre, "inicio": v.fecha_inicio.isoformat(),
             "fin": v.fecha_fin.isoformat(), "tipo": v.tipo} for v in ventanas]


@router.get("/partidas/{id_partida}/partidos-selecciones")
async def listar_partidos_selecciones(id_partida: int, db: AsyncSession = Depends(get_db)):
    partidos = (await db.execute(select(PartidoSeleccion).where(
        PartidoSeleccion.id_partida == id_partida).order_by(PartidoSeleccion.fecha)
    )).scalars().all()
    ids = {p.id_local for p in partidos} | {p.id_visitante for p in partidos}
    nombres = {s.id_seleccion: s.nombre for s in (await db.execute(select(Seleccion).where(Seleccion.id_seleccion.in_(ids)))).scalars().all()} if ids else {}
    return [{"id_partido": p.id_partido_seleccion, "fecha": p.fecha.isoformat(), "tipo": p.tipo,
             "competencia": p.competencia, "grupo": p.grupo, "jornada": p.jornada, "oficial": p.oficial,
             "local": nombres.get(p.id_local, "—"), "visitante": nombres.get(p.id_visitante, "—"),
             "jugado": p.jugado, "goles_local": p.goles_local, "goles_visitante": p.goles_visitante} for p in partidos]


@router.get("/partidas/{id_partida}/torneos-selecciones")
async def listar_torneos_selecciones(id_partida: int, db: AsyncSession = Depends(get_db)):
    torneos = (await db.execute(select(TorneoSeleccion).where(TorneoSeleccion.id_partida == id_partida))).scalars().all()
    if not torneos:
        return []
    partidos = (await db.execute(select(PartidoSeleccion).where(
        PartidoSeleccion.id_partida == id_partida, PartidoSeleccion.id_torneo.is_not(None)
    ))).scalars().all()
    ids = {p.id_local for p in partidos} | {p.id_visitante for p in partidos}
    selecciones = {s.id_seleccion: s for s in (await db.execute(select(Seleccion).where(Seleccion.id_seleccion.in_(ids)))).scalars().all()} if ids else {}
    salida = []
    for torneo in torneos:
        try:
            grupos = json.loads(torneo.grupos_json or "[]")
        except json.JSONDecodeError:
            grupos = []
        propios = [p for p in partidos if p.id_torneo == torneo.id_torneo]
        tablas = []
        for grupo in grupos:
            if not isinstance(grupo, dict):
                continue
            codigos = set(grupo.get("selecciones") or [])
            filas = {codigo: {"codigo": codigo, "nombre": next((s.nombre for s in selecciones.values() if s.codigo == codigo), codigo), "pj": 0, "pg": 0, "pe": 0, "pp": 0, "gf": 0, "gc": 0, "pts": 0} for codigo in codigos}
            for p in propios:
                if not p.jugado or p.grupo != grupo.get("nombre") or p.goles_local is None or p.goles_visitante is None:
                    continue
                local, visitante = selecciones.get(p.id_local), selecciones.get(p.id_visitante)
                if not local or not visitante or local.codigo not in filas or visitante.codigo not in filas:
                    continue
                a, b = filas[local.codigo], filas[visitante.codigo]
                a["pj"] += 1; b["pj"] += 1; a["gf"] += p.goles_local; a["gc"] += p.goles_visitante; b["gf"] += p.goles_visitante; b["gc"] += p.goles_local
                if p.goles_local > p.goles_visitante: a["pg"] += 1; b["pp"] += 1; a["pts"] += 3
                elif p.goles_local < p.goles_visitante: b["pg"] += 1; a["pp"] += 1; b["pts"] += 3
                else: a["pe"] += 1; b["pe"] += 1; a["pts"] += 1; b["pts"] += 1
            tablas.append({"nombre": grupo.get("nombre") or "Grupo", "tabla": sorted(filas.values(), key=lambda x: (x["pts"], x["gf"] - x["gc"], x["gf"]), reverse=True)})
        salida.append({"id_torneo": torneo.id_torneo, "codigo": torneo.codigo, "nombre": torneo.nombre, "tipo": torneo.tipo, "grupos": tablas})
    return salida


@router.get("/partidas/{id_partida}/selecciones")
async def listar_selecciones(id_partida: int, db: AsyncSession = Depends(get_db)):
    filas = (await db.execute(
        select(Seleccion).where(Seleccion.id_partida == id_partida).order_by(Seleccion.categoria, Seleccion.ranking, Seleccion.nombre)
    )).scalars().all()
    return [{"id_seleccion": s.id_seleccion, "codigo": s.codigo, "nombre": s.nombre,
             "pais": s.pais, "confederacion": s.confederacion, "categoria": s.categoria,
             "ranking": s.ranking, "seleccionador": s.seleccionador} for s in filas]


@router.get("/selecciones/{id_seleccion}")
async def obtener_seleccion(id_seleccion: int, db: AsyncSession = Depends(get_db)):
    seleccion = await db.get(Seleccion, id_seleccion)
    if not seleccion:
        raise HTTPException(status_code=404, detail="Selección no encontrada")
    # La consulta es deliberadamente de solo lectura. Las selecciones no
    # activas conservan el dato real importado por el PMPack y no disparan una
    # carga masiva de jugadores por nacionalidad solo por abrir su ficha.
    convocados = (await db.execute(
        select(ConvocatoriaSeleccion, Jugador)
        .join(Jugador, Jugador.id_jugador == ConvocatoriaSeleccion.id_jugador)
        .where(ConvocatoriaSeleccion.id_seleccion == id_seleccion)
    )).all()
    elegibles = (await db.execute(
        select(ElegibilidadSeleccion, Jugador)
        .join(Jugador, Jugador.id_jugador == ElegibilidadSeleccion.id_jugador)
        .where(ElegibilidadSeleccion.id_seleccion == id_seleccion)
    )).all()
    convocado_ids = {j.id_jugador for _, j in convocados}
    def jugador_out(e, j):
        return {"id_jugador": j.id_jugador, "nombre": j.nombre, "posicion": j.posicion,
                "posicion_especifica": j.posicion_especifica, "edad": j.edad, "overall": j.overall,
                "estado_elegibilidad": e.estado, "partidos_oficiales": e.partidos_oficiales}
    return {
        "id_seleccion": seleccion.id_seleccion, "codigo": seleccion.codigo, "nombre": seleccion.nombre,
        "pais": seleccion.pais, "confederacion": seleccion.confederacion, "categoria": seleccion.categoria,
        "ranking": seleccion.ranking, "seleccionador": seleccion.seleccionador,
        "convocados": [{"id_jugador": j.id_jugador, "nombre": j.nombre, "posicion": j.posicion,
                         "posicion_especifica": j.posicion_especifica, "edad": j.edad, "overall": j.overall,
                         "estado_elegibilidad": "CONVOCADO", "partidos_oficiales": 0,
                         "estado_convocatoria": c.estado} for c, j in convocados],
        "elegibles": [jugador_out(e, j) for e, j in elegibles if j.id_jugador not in convocado_ids],
    }
