from fastapi import APIRouter
from api.runtime import (
    AsyncSession,
    CATEGORIAS_ACADEMIA,
    Depends,
    Equipo,
    HTTPException,
    Jugador,
    _asegurar_academia,
    _jugador_desarrollo,
    _resumen_cantera,
    get_db,
    select
)

router = APIRouter()

@router.get("/equipos/{id_equipo}/desarrollo", tags=["Desarrollo"])
async def obtener_desarrollo(id_equipo: int, db: AsyncSession = Depends(get_db)):
    equipo = await db.get(Equipo, id_equipo)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    await _asegurar_academia(db, equipo)

    jugadores = (await db.execute(
        select(Jugador).where(Jugador.id_equipo == id_equipo, Jugador.categoria == "PRIMERA")
    )).scalars().all()
    cedidos = (await db.execute(select(Jugador).where(Jugador.id_equipo_dueno == id_equipo))).scalars().all()
    cedidos_recibidos = [j for j in jugadores if j.id_equipo_dueno]
    nombres_prestamistas = {}
    if cedidos:
        ids_prestamistas = {j.id_equipo for j in cedidos if j.id_equipo}
        equipos_prestamistas = (await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_prestamistas)))).scalars().all()
        nombres_prestamistas = {e.id_equipo: e.nombre for e in equipos_prestamistas}
    nombres_duenos = {}
    if cedidos_recibidos:
        ids_duenos = {j.id_equipo_dueno for j in cedidos_recibidos if j.id_equipo_dueno}
        equipos_duenos = (await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_duenos)))).scalars().all()
        nombres_duenos = {e.id_equipo: e.nombre for e in equipos_duenos}

    # Las 4 categorías son los jugadores REALES de la Academia (no un filtro
    # por edad sobre Primera como antes) — Centro de Desarrollo es donde el
    # DT ve de un vistazo lo importante de toda la cantera, no solo Primera.
    academia = (await db.execute(
        select(Jugador).where(Jugador.id_equipo == id_equipo, Jugador.categoria != "PRIMERA")
    )).scalars().all()
    por_categoria = {c: sorted((j for j in academia if j.categoria == c), key=lambda j: -j.potencial) for c in CATEGORIAS_ACADEMIA}

    # Destacados: los mejores prospectos de TODA la Academia (cualquier
    # categoría), la información más importante para el DT de un vistazo —
    # quién está más cerca de ser un golazo, sin importar en qué división esté.
    destacados = sorted(academia, key=lambda j: -j.potencial)[:8]

    candidatos = sorted(
        (j for j in jugadores if j.edad <= 21 and j.rol in ("TITULAR", "SUPLENTE")),
        key=lambda j: -j.overall,
    )

    en_desarrollo = sorted(
        (j for j in jugadores if j.edad <= 23 and (j.potencial - j.overall) > 0),
        key=lambda j: -(j.potencial - j.overall),
    )
    necesita_atencion = [j for j in en_desarrollo if j.rol == "RESERVA"][:5]
    a_vigilar = ([j for j in en_desarrollo if j.rol != "RESERVA"] or en_desarrollo)[:5]

    return {
        "nombre_equipo": equipo.nombre,
        "destacados_academia": [_jugador_desarrollo(j) for j in destacados],
        "sub13": {"jugadores": [_jugador_desarrollo(j) for j in por_categoria["SUB13"]], "resumen": _resumen_cantera(por_categoria["SUB13"], "Sub-13")},
        "sub15": {"jugadores": [_jugador_desarrollo(j) for j in por_categoria["SUB15"]], "resumen": _resumen_cantera(por_categoria["SUB15"], "Sub-15")},
        "sub18": {"jugadores": [_jugador_desarrollo(j) for j in por_categoria["SUB18"]], "resumen": _resumen_cantera(por_categoria["SUB18"], "Sub-18")},
        "sub21": {"jugadores": [_jugador_desarrollo(j) for j in por_categoria["SUB21"]], "resumen": _resumen_cantera(por_categoria["SUB21"], "Sub-21")},
        "candidatos_primer_equipo": [_jugador_desarrollo(j) for j in candidatos],
        "necesita_atencion": [_jugador_desarrollo(j) for j in necesita_atencion],
        "jugadores_a_vigilar": [_jugador_desarrollo(j) for j in a_vigilar],
        "cedidos": [
            {
                **_jugador_desarrollo(j),
                "club_prestamista": nombres_prestamistas.get(j.id_equipo, "?"),
                "fin_cesion": j.fin_cesion.isoformat() if j.fin_cesion else None,
                "opcion_compra": j.opcion_compra,
            }
            for j in cedidos
        ],
        "cedidos_recibidos": [
            {
                **_jugador_desarrollo(j),
                "club_dueno": nombres_duenos.get(j.id_equipo_dueno, "?"),
                "fin_cesion": j.fin_cesion.isoformat() if j.fin_cesion else None,
                "opcion_compra": j.opcion_compra,
            }
            for j in cedidos_recibidos
        ],
    }
