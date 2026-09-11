from fastapi import APIRouter
from api.runtime import (
    AsyncSession,
    Depends,
    EntrenamientoIn,
    EntrenamientoIndividualIn,
    Equipo,
    FOCOS_INDIVIDUALES_VALIDOS,
    HTTPException,
    Jugador,
    PlanEntrenamiento,
    _bono_centro,
    _bono_red_equipo,
    _crear_mensaje,
    _fecha_actual,
    aplicar_entrenamiento,
    get_db,
    select
)

router = APIRouter()

@router.post("/entrenamiento/configurar", tags=["Entrenamiento"])
async def configurar_entrenamiento(datos: EntrenamientoIn, db: AsyncSession = Depends(get_db)):
    plan = await db.get(PlanEntrenamiento, datos.id_equipo)
    if not plan:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    plan.foco = datos.foco
    plan.intensidad = datos.intensidad

    jugadores = (await db.execute(
        select(Jugador).where(Jugador.id_equipo == datos.id_equipo, Jugador.categoria == "PRIMERA")
    )).scalars().all()
    equipo = await db.get(Equipo, datos.id_equipo)
    bono_centro = _bono_centro(await _bono_red_equipo(db, equipo)) if equipo else 0.0
    aplicar_entrenamiento(jugadores, datos.foco, datos.intensidad, bono_centro)

    fecha = await _fecha_actual(db, equipo.id_partida)
    await _crear_mensaje(
        db, datos.id_equipo, "Cuerpo Técnico", "Plan de entrenamiento actualizado",
        f"Se configuró el entrenamiento en modo {datos.foco}/{datos.intensidad}.",
        "ENTRENAMIENTO", fecha,
    )

    await db.commit()
    return {"status": "ok", "mensaje": f"Entrenamiento configurado en modo {datos.foco}/{datos.intensidad}"}


@router.post("/entrenamiento/individual", tags=["Entrenamiento"])
async def configurar_entrenamiento_individual(datos: EntrenamientoIndividualIn, db: AsyncSession = Depends(get_db)):
    """Foco extra propio de UN jugador, además del plan grupal de su equipo
    — progresa solo cada semana, ver _procesar_entrenamiento_individual."""
    if datos.foco is not None and datos.foco not in FOCOS_INDIVIDUALES_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Foco inválido, debe ser uno de {sorted(FOCOS_INDIVIDUALES_VALIDOS)} o null.")
    jugador = await db.get(Jugador, datos.id_jugador)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    jugador.foco_individual = datos.foco

    if jugador.id_equipo:
        fecha = await _fecha_actual(db, jugador.id_partida)
        mensaje = (
            f"Se asignó a {jugador.nombre} un foco de entrenamiento individual en {datos.foco}."
            if datos.foco else f"Se quitó el foco de entrenamiento individual de {jugador.nombre}."
        )
        await _crear_mensaje(db, jugador.id_equipo, "Cuerpo Técnico", "Entrenamiento individual actualizado", mensaje, "ENTRENAMIENTO", fecha)

    await db.commit()
    return {"status": "ok", "foco_individual": jugador.foco_individual}
