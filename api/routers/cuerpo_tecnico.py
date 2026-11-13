from fastapi import APIRouter
from api.runtime import (
    AsyncSession,
    CapitanIn,
    Depends,
    Equipo,
    HTTPException,
    Jugador,
    Ojeador,
    PersonalTecnico,
    PlanEntrenamiento,
    ReporteScouting,
    Tactica,
    _consejo_entrenamiento,
    _consejo_vestuario,
    _opinion_tactica,
    _promedios_por_posicion,
    _puntaje_vestuario,
    _rango_fog,
    _reportes_de,
    get_db,
    select
)

router = APIRouter()

@router.post("/equipos/{id_equipo}/capitan", tags=["Cuerpo Técnico"])
async def asignar_capitan(id_equipo: int, datos: CapitanIn, db: AsyncSession = Depends(get_db)):
    """Capitán del plantel PRIMERA — su liderazgo atenúa el castigo de
    vestuario cuando el ánimo del plantel está dividido, ver
    _puntaje_vestuario. `id_jugador=None` quita el capitán."""
    equipo = await db.get(Equipo, id_equipo)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    if datos.id_jugador is not None:
        jugador = await db.get(Jugador, datos.id_jugador)
        if not jugador or jugador.id_equipo != id_equipo or jugador.categoria != "PRIMERA":
            raise HTTPException(status_code=400, detail="El capitán tiene que ser un jugador del plantel PRIMERA de este equipo.")
    equipo.id_capitan = datos.id_jugador
    await db.commit()
    return {"status": "ok", "id_capitan": equipo.id_capitan}


@router.get("/equipos/{id_equipo}/cuerpo-tecnico", tags=["Cuerpo Técnico"])
async def obtener_cuerpo_tecnico(id_equipo: int, db: AsyncSession = Depends(get_db)):
    equipo = await db.get(Equipo, id_equipo)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    personal = await db.get(PersonalTecnico, id_equipo)
    tactica = await db.get(Tactica, id_equipo)

    plantel = (await db.execute(select(Jugador).where(Jugador.id_equipo == id_equipo))).scalars().all()
    promedios = _promedios_por_posicion(plantel)
    opinion = (
        _opinion_tactica(tactica, promedios, plantel) if tactica and plantel
        else "Todavía no tengo plantel suficiente para darte una opinión formada."
    )

    ojeadores = (await db.execute(select(Ojeador).where(Ojeador.id_equipo == id_equipo))).scalars().all()
    ids_asignados = [o.id_jugador_asignado for o in ojeadores if o.id_jugador_asignado]
    objetivos = {j.id_jugador: j for j in (
        (await db.execute(select(Jugador).where(Jugador.id_jugador.in_(ids_asignados)))).scalars().all()
        if ids_asignados else []
    )}
    reportes = await _reportes_de(db, id_equipo, ids_asignados)

    ojeadores_out = []
    for o in ojeadores:
        asignado = None
        objetivo = objetivos.get(o.id_jugador_asignado) if o.id_jugador_asignado else None
        if objetivo:
            reporte = reportes.get(objetivo.id_jugador)
            progreso = reporte.progreso if reporte else 0
            asignado = {
                "id_jugador": objetivo.id_jugador, "nombre": objetivo.nombre,
                "posicion": objetivo.posicion, "posicion_especifica": objetivo.posicion_especifica,
                "progreso": progreso,
                "overall_rango": None if progreso >= 100 else _rango_fog(objetivo.overall, progreso),
                "overall": objetivo.overall if progreso >= 100 else None,
                "potencial_rango": None if progreso >= 100 else _rango_fog(objetivo.potencial, progreso),
                "potencial": objetivo.potencial if progreso >= 100 else None,
            }
        ojeadores_out.append({
            "id_ojeador": o.id_ojeador, "nombre": o.nombre, "calidad": o.calidad, "asignado": asignado,
        })

    plan = await db.get(PlanEntrenamiento, id_equipo)
    capitan = next((j for j in plantel if j.id_jugador == equipo.id_capitan), None) if equipo.id_capitan else None
    return {
        "asistente": {"nombre": personal.nombre_asistente if personal else "?", "opinion": opinion},
        "entrenamiento": {
            "foco": plan.foco if plan else "EQUILIBRADO",
            "intensidad": plan.intensidad if plan else "MEDIA",
            "consejo": _consejo_entrenamiento(plantel),
        },
        "vestuario": {
            "puntaje": round(_puntaje_vestuario(plantel, equipo.id_capitan)),
            "consejo": _consejo_vestuario(plantel, capitan),
            "capitan": {"id_jugador": capitan.id_jugador, "nombre": capitan.nombre} if capitan else None,
            "jugadores_a_acompanar": [
                {"id_jugador": j.id_jugador, "nombre": j.nombre, "moral": j.moral, "relacion_dt": j.relacion_dt}
                for j in sorted((j for j in plantel if j.categoria == "PRIMERA"), key=lambda j: (j.moral, j.relacion_dt))[:3]
            ],
            "plantel_primera": [
                {"id_jugador": j.id_jugador, "nombre": j.nombre, "posicion": j.posicion, "moral": j.moral, "relacion_dt": j.relacion_dt}
                for j in plantel if j.categoria == "PRIMERA"
            ],
        },
        "ojeadores": ojeadores_out,
    }


@router.post("/scouting/asignar", tags=["Cuerpo Técnico"])
async def asignar_scouting(datos: dict, db: AsyncSession = Depends(get_db)):
    ojeador = await db.get(Ojeador, datos.get("id_ojeador"))
    if not ojeador:
        raise HTTPException(status_code=404, detail="Ojeador no encontrado")
    id_jugador = datos.get("id_jugador")
    jugador = await db.get(Jugador, id_jugador)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    ojeador.id_jugador_asignado = id_jugador
    reporte = await db.get(ReporteScouting, (ojeador.id_equipo, id_jugador))
    if not reporte:
        db.add(ReporteScouting(id_equipo=ojeador.id_equipo, id_jugador=id_jugador, id_partida=ojeador.id_partida, progreso=0))
    await db.commit()
    return {"status": "ok"}


@router.post("/scouting/quitar", tags=["Cuerpo Técnico"])
async def quitar_scouting(datos: dict, db: AsyncSession = Depends(get_db)):
    ojeador = await db.get(Ojeador, datos.get("id_ojeador"))
    if not ojeador:
        raise HTTPException(status_code=404, detail="Ojeador no encontrado")
    ojeador.id_jugador_asignado = None
    await db.commit()
    return {"status": "ok"}
