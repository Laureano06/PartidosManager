from fastapi import APIRouter
from api.runtime import (
    AsyncSession,
    DIAS_ELEGIBLE_PRECONTRATO,
    Depends,
    Equipo,
    EquipoOut,
    HTTPException,
    HistorialTemporada,
    Jugador,
    JugadorOut,
    TransferibleIn,
    _aplicar_fog,
    _equipo_usuario,
    _fecha_actual,
    _interes_desde_probabilidad,
    _rango_fog,
    _reportes_de,
    disposicion_fichar,
    disposicion_renovar,
    frase_dialogo,
    get_db,
    select
)

router = APIRouter()

@router.get("/equipos", response_model=list[EquipoOut], tags=["Equipos"])
async def listar_equipos(id_partida: int, id_liga: int | None = None, db: AsyncSession = Depends(get_db)):
    query = select(Equipo).where(Equipo.id_partida == id_partida)
    if id_liga is not None:
        query = query.where(Equipo.id_liga == id_liga)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/equipos/{id_equipo}/jugadores", tags=["Equipos"])
async def obtener_plantilla(id_equipo: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Jugador).where(Jugador.id_equipo == id_equipo, Jugador.categoria == "PRIMERA")
    )
    jugadores = result.scalars().all()
    if not jugadores:
        raise HTTPException(status_code=404, detail="Equipo sin jugadores (¿corriste seed.py?)")

    fecha = await _fecha_actual(db, jugadores[0].id_partida)
    ids_duenos = {j.id_equipo_dueno for j in jugadores if j.id_equipo_dueno}
    duenos = {e.id_equipo: e.nombre for e in (await db.execute(
        select(Equipo).where(Equipo.id_equipo.in_(ids_duenos))
    )).scalars().all()} if ids_duenos else {}
    equipo_objetivo = await db.get(Equipo, id_equipo)
    equipo_usuario = None if (equipo_objetivo and equipo_objetivo.es_usuario) else await _equipo_usuario(db, jugadores[0].id_partida)
    reportes = (
        await _reportes_de(db, equipo_usuario.id_equipo, [j.id_jugador for j in jugadores])
        if equipo_usuario else {}
    )
    salida = []
    for j in jugadores:
        base = JugadorOut.model_validate(j).model_dump(mode="json")
        dias_restantes = (j.fecha_fin_contrato - fecha).days if j.fecha_fin_contrato else None
        base["dias_restantes_contrato"] = dias_restantes
        base["elegible_precontrato"] = dias_restantes is not None and 0 < dias_restantes <= DIAS_ELEGIBLE_PRECONTRATO
        base["id_equipo_precontrato"] = j.id_equipo_precontrato
        base["club_dueno"] = duenos.get(j.id_equipo_dueno) if j.id_equipo_dueno else None
        base["en_convocatoria"] = j.en_convocatoria
        if equipo_usuario:
            _aplicar_fog(base, j, reportes.get(j.id_jugador))
        salida.append(base)
    return salida


@router.get("/equipos/{id_equipo}/cedidos", tags=["Equipos"])
async def obtener_cedidos(id_equipo: int, db: AsyncSession = Depends(get_db)):
    """Jugadores propios que están jugando a préstamo en otro club."""
    jugadores = (await db.execute(select(Jugador).where(Jugador.id_equipo_dueno == id_equipo))).scalars().all()
    destinos = {e.id_equipo: e.nombre for e in (await db.execute(
        select(Equipo).where(Equipo.id_equipo.in_({j.id_equipo for j in jugadores if j.id_equipo}))
    )).scalars().all()} if jugadores else {}
    return [
        {
            **JugadorOut.model_validate(j).model_dump(mode="json"),
            "club_actual": destinos.get(j.id_equipo, "—"),
            "fin_cesion": j.fin_cesion.isoformat() if j.fin_cesion else None,
            "opcion_compra": j.opcion_compra,
        }
        for j in jugadores
    ]


@router.get("/jugadores/{id_jugador}", tags=["Equipos"])
async def obtener_jugador(id_jugador: int, db: AsyncSession = Depends(get_db)):
    """Ficha completa de un jugador puntual — para cuando la vista de lista
    (mercado, búsqueda) usó una versión liviana/paginada y hace falta el
    detalle completo recién al abrir su ficha."""
    jugador = await db.get(Jugador, id_jugador)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    equipo = await db.get(Equipo, jugador.id_equipo) if jugador.id_equipo else None
    fecha = await _fecha_actual(db, jugador.id_partida)
    dias_restantes = (jugador.fecha_fin_contrato - fecha).days if jugador.fecha_fin_contrato else None
    base = JugadorOut.model_validate(jugador).model_dump(mode="json")
    base["club"] = equipo.nombre if equipo else "Agente Libre"
    base["es_libre"] = jugador.id_equipo is None
    base["dias_restantes_contrato"] = dias_restantes
    base["elegible_precontrato"] = dias_restantes is not None and 0 < dias_restantes <= DIAS_ELEGIBLE_PRECONTRATO
    base["id_equipo_precontrato"] = jugador.id_equipo_precontrato
    if not (equipo and equipo.es_usuario):
        equipo_usuario = await _equipo_usuario(db, jugador.id_partida)
        if equipo_usuario:
            reporte = (await _reportes_de(db, equipo_usuario.id_equipo, [id_jugador])).get(id_jugador)
            _aplicar_fog(base, jugador, reporte)
    return base


@router.get("/jugadores/{id_jugador}/dialogo", tags=["Equipos"])
async def dialogo_jugador(id_jugador: int, id_equipo_interesado: int, tema: str = "continuidad", db: AsyncSession = Depends(get_db)):
    """'Hablar con el jugador' — consulta de solo lectura, no gasta ninguna
    ronda de negociación real. Si id_equipo_interesado es el club actual del
    jugador, se lee su disposición a RENOVAR; si es otro club (scouting/
    mercado), su disposición a SUMARSE ahí. `tema`: club | continuidad | futuro."""
    jugador = await db.get(Jugador, id_jugador)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    equipo_interesado = await db.get(Equipo, id_equipo_interesado)
    if not equipo_interesado:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    if jugador.id_equipo == id_equipo_interesado:
        disposicion = disposicion_renovar(jugador.overall, jugador.edad, jugador.rol, jugador.moral, equipo_interesado.reputacion, jugador.relacion_dt)
    else:
        equipo_actual = await db.get(Equipo, jugador.id_equipo) if jugador.id_equipo else None
        reputacion_actual = equipo_actual.reputacion if equipo_actual else None
        disposicion = disposicion_fichar(jugador.overall, jugador.edad, reputacion_actual, equipo_interesado.reputacion)

    frase = frase_dialogo(
        tema, moral=jugador.moral, disposicion=disposicion,
        overall=jugador.overall, potencial=jugador.potencial, edad=jugador.edad,
    )
    return {"tema": tema, "frase": frase, "interes": _interes_desde_probabilidad(disposicion["probabilidad"]),
            "relacion_dt": jugador.relacion_dt}


@router.get("/jugadores/{id_jugador}/historial", tags=["Equipos"])
async def historial_jugador(id_jugador: int, db: AsyncSession = Depends(get_db)):
    """Evolución de carrera del jugador, temporada a temporada (overall,
    potencial, valor de mercado) — una fila por cada cierre de temporada
    que le tocó vivir."""
    filas = (await db.execute(
        select(HistorialTemporada).where(HistorialTemporada.id_jugador == id_jugador).order_by(HistorialTemporada.temporada)
    )).scalars().all()

    # Mismo criterio de fog que en la ficha actual del jugador — se aplica
    # parejo a todo el historial (no granular por el club de cada temporada
    # pasada), usando el progreso de scouting que se tenga HOY sobre él.
    progreso = 100
    jugador = await db.get(Jugador, id_jugador)
    if jugador:
        equipo = await db.get(Equipo, jugador.id_equipo) if jugador.id_equipo else None
        if not (equipo and equipo.es_usuario):
            equipo_usuario = await _equipo_usuario(db, jugador.id_partida)
            progreso = 0
            if equipo_usuario:
                reporte = (await _reportes_de(db, equipo_usuario.id_equipo, [id_jugador])).get(id_jugador)
                progreso = reporte.progreso if reporte else 0

    historial = []
    for h in filas:
        fila = {
            "temporada": h.temporada, "nombre_jugador": h.nombre_jugador, "nombre_equipo": h.nombre_equipo, "edad": h.edad,
            "valor_mercado": h.valor_mercado, "salario": h.salario, "rol": h.rol,
        }
        fila["overall"] = h.overall if progreso >= 100 else None
        fila["overall_rango"] = None if progreso >= 100 else _rango_fog(h.overall, progreso)
        fila["potencial"] = h.potencial if progreso >= 100 else None
        fila["potencial_rango"] = None if progreso >= 100 else _rango_fog(h.potencial, progreso)
        historial.append(fila)
    return {"historial": historial}


@router.post("/jugadores/{id_jugador}/rol", tags=["Equipos"])
async def cambiar_rol_jugador(id_jugador: int, datos: dict, db: AsyncSession = Depends(get_db)):
    rol = datos.get("rol")
    if rol not in ("TITULAR", "SUPLENTE", "RESERVA"):
        raise HTTPException(status_code=400, detail="rol inválido")
    jugador = await db.get(Jugador, id_jugador)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    if jugador.categoria != "PRIMERA":
        raise HTTPException(status_code=400, detail="Un jugador de la Academia no tiene rol de convocatoria")
    jugador.rol = rol
    await db.commit()
    return {"status": "ok", "id_jugador": id_jugador, "rol": rol}


@router.post("/jugadores/{id_jugador}/duty", tags=["Equipos"])
async def cambiar_duty_jugador(id_jugador: int, datos: dict, db: AsyncSession = Depends(get_db)):
    """Instrucción individual del jugador dentro de la táctica (independiente
    del rol titular/suplente/reserva) — ver `team_power` en match_engine.py."""
    duty = datos.get("duty")
    if duty not in ("DEFENSIVO", "EQUILIBRADO", "OFENSIVO"):
        raise HTTPException(status_code=400, detail="duty inválido")
    jugador = await db.get(Jugador, id_jugador)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    jugador.duty = duty
    await db.commit()
    return {"status": "ok", "id_jugador": id_jugador, "duty": duty}


@router.post("/jugadores/{id_jugador}/transferible", tags=["Equipos"])
async def marcar_transferible(id_jugador: int, datos: TransferibleIn, db: AsyncSession = Depends(get_db)):
    jugador = await db.get(Jugador, id_jugador)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    jugador.en_transferible = datos.en_transferible
    await db.commit()
    return {"status": "ok", "id_jugador": id_jugador, "en_transferible": jugador.en_transferible}
