from fastapi import APIRouter
from api.runtime import (
    AsyncSession,
    COMPETENCIAS,
    Calendario,
    Depends,
    Equipo,
    get_db,
    select
)

router = APIRouter()

@router.get("/torneos", tags=["Torneos"])
async def obtener_torneos(id_partida: int, db: AsyncSession = Depends(get_db)):
    filas = (await db.execute(
        select(Calendario).where(Calendario.id_partida == id_partida, Calendario.tipo == "COPA")
    )).scalars().all()
    ids_equipos = {id_eq for f in filas for id_eq in (f.id_local, f.id_visitante)}
    nombres = {e.id_equipo: e.nombre for e in (
        await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_equipos)))
    ).scalars().all()} if ids_equipos else {}

    torneos = {}
    for confederacion, nombres_comp in COMPETENCIAS.items():
        for nivel, competencia in nombres_comp.items():
            fixtures_comp = [f for f in filas if f.competencia == competencia]
            if not fixtures_comp:
                continue
            torneos[competencia] = {
                "confederacion": confederacion, "nivel": nivel,
                "partidos": [
                    {
                        "id_fixture": f.id_fixture, "ronda_copa": f.ronda_copa, "num_jornada": f.num_jornada,
                        "fecha": f.fecha.isoformat(), "id_local": f.id_local, "id_visitante": f.id_visitante,
                        "nombre_local": nombres.get(f.id_local, "?"), "nombre_visitante": nombres.get(f.id_visitante, "?"),
                        "jugado": f.jugado, "goles_local": f.goles_local, "goles_visitante": f.goles_visitante,
                        "desempate_id_equipo": f.desempate_id_equipo,
                    }
                    for f in sorted(fixtures_comp, key=lambda x: (x.fecha, x.id_fixture))
                ],
            }
    return {"torneos": torneos}
