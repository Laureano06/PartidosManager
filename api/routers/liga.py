from fastapi import APIRouter
from api.runtime import (
    AsyncSession,
    Calendario,
    Depends,
    Equipo,
    Liga,
    LigaOut,
    _equipo_usuario,
    _nombres_competencia,
    get_db,
    or_,
    select
)

router = APIRouter()

@router.get("/ligas", response_model=list[LigaOut], tags=["Liga"])
async def listar_ligas(id_partida: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Liga).where(Liga.id_partida == id_partida))
    return result.scalars().all()


@router.get("/tabla", tags=["Liga"])
async def obtener_tabla(id_liga: int | None = None, id_partida: int | None = None, db: AsyncSession = Depends(get_db)):
    if id_liga is None:
        equipo_usuario = await _equipo_usuario(db, id_partida) if id_partida else None
        id_liga = equipo_usuario.id_liga if equipo_usuario else None

    result = await db.execute(select(Equipo).where(Equipo.id_liga == id_liga))
    equipos = result.scalars().all()
    ordenados = sorted(
        equipos,
        key=lambda e: (-e.puntos, -(e.goles_favor - e.goles_contra), -e.goles_favor),
    )
    return {
        "id_liga": id_liga,
        "tabla": [
            {
                "id_equipo": e.id_equipo, "nombre": e.nombre, "es_usuario": e.es_usuario, "puntos": e.puntos,
                "jugados": e.jugados, "ganados": e.ganados, "empatados": e.empatados,
                "perdidos": e.perdidos, "goles_favor": e.goles_favor,
                "goles_contra": e.goles_contra,
                "diferencia_goles": e.goles_favor - e.goles_contra,
            }
            for e in ordenados
        ]
    }


@router.get("/calendario/{num_jornada}", tags=["Liga"])
async def ver_jornada(num_jornada: int, id_liga: int | None = None, id_partida: int | None = None, db: AsyncSession = Depends(get_db)):
    if id_liga is None:
        equipo_usuario = await _equipo_usuario(db, id_partida) if id_partida else None
        id_liga = equipo_usuario.id_liga if equipo_usuario else None

    result = await db.execute(
        select(Calendario).where(Calendario.num_jornada == num_jornada, Calendario.id_liga == id_liga)
    )
    fixtures = result.scalars().all()

    ids_equipos = {id_eq for f in fixtures for id_eq in (f.id_local, f.id_visitante)}
    equipos = (await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_equipos)))).scalars().all()
    nombres = {e.id_equipo: e.nombre for e in equipos}

    return {"jornada": num_jornada, "id_liga": id_liga, "partidos": [
        {"id_fixture": f.id_fixture, "id_local": f.id_local, "id_visitante": f.id_visitante,
         "nombre_local": nombres.get(f.id_local, "?"), "nombre_visitante": nombres.get(f.id_visitante, "?"),
         "fecha": f.fecha.isoformat(), "jugado": f.jugado,
         "goles_local": f.goles_local, "goles_visitante": f.goles_visitante}
        for f in fixtures
    ]}


@router.get("/calendario/equipo/{id_equipo}", tags=["Liga"])
async def calendario_equipo(id_equipo: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Calendario)
        .where(or_(Calendario.id_local == id_equipo, Calendario.id_visitante == id_equipo))
        .order_by(Calendario.fecha)
    )
    fixtures = result.scalars().all()

    ids_equipos = {id_eq for f in fixtures for id_eq in (f.id_local, f.id_visitante)}
    equipos = (await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_equipos)))).scalars().all()
    nombres = {e.id_equipo: e.nombre for e in equipos}
    nombres_competencia = await _nombres_competencia(db, fixtures[0].id_partida) if fixtures else {}

    return {"partidos": [
        {"id_fixture": f.id_fixture, "num_jornada": f.num_jornada, "fecha": f.fecha.isoformat(),
         "id_local": f.id_local, "id_visitante": f.id_visitante,
         "nombre_local": nombres.get(f.id_local, "?"), "nombre_visitante": nombres.get(f.id_visitante, "?"),
         "jugado": f.jugado, "goles_local": f.goles_local, "goles_visitante": f.goles_visitante,
         "tipo": f.tipo, "competencia": f.competencia, "ronda_copa": f.ronda_copa,
         "nombre_competencia": nombres_competencia.get(f.competencia) if f.competencia else None}
        for f in fixtures
    ]}
