from fastapi import APIRouter
from api.runtime import (
    AsyncSession,
    Depends,
    Equipo,
    HTTPException,
    Jugador,
    get_db,
    select
)

router = APIRouter()

@router.get("/equipos/{id_equipo}/economia", tags=["Economía"])
async def obtener_economia(id_equipo: int, db: AsyncSession = Depends(get_db)):
    equipo = await db.get(Equipo, id_equipo)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    jugadores = (await db.execute(select(Jugador).where(Jugador.id_equipo == id_equipo))).scalars().all()

    masa_salarial_semanal = sum(j.salario for j in jugadores)
    valor_plantilla = sum(j.valor_mercado for j in jugadores)
    top_sueldos = sorted(jugadores, key=lambda j: -j.salario)[:5]

    ratio = (masa_salarial_semanal / equipo.presupuesto_salarios) if equipo.presupuesto_salarios else 0
    if ratio <= 0.75:
        estado_ffp, color_ffp = "Cumple con margen", "verde"
    elif ratio <= 1.0:
        estado_ffp, color_ffp = "Al límite del presupuesto", "amarillo"
    else:
        estado_ffp, color_ffp = "Excedido — riesgo de sanciones", "rojo"

    return {
        "nombre_equipo": equipo.nombre,
        "presupuesto_fichajes": equipo.presupuesto_fichajes,
        "presupuesto_salarios": equipo.presupuesto_salarios,
        "masa_salarial_semanal": masa_salarial_semanal,
        "valor_plantilla": valor_plantilla,
        "reputacion": equipo.reputacion,
        "cantidad_jugadores": len(jugadores),
        "estado_ffp": estado_ffp,
        "color_ffp": color_ffp,
        "ratio_masa_salarial": round(ratio, 3),
        "top_sueldos": [
            {"id_jugador": j.id_jugador, "nombre": j.nombre, "posicion": j.posicion, "posicion_especifica": j.posicion_especifica, "salario": j.salario, "overall": j.overall}
            for j in top_sueldos
        ],
    }
