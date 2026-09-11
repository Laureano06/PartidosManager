from fastapi import APIRouter
from api.runtime import (
    AsyncSession,
    Depends,
    Equipo,
    HTTPException,
    Tactica,
    TacticaIn,
    _crear_mensaje,
    _fecha_actual,
    get_db
)

router = APIRouter()

@router.get("/tacticas/{id_equipo}", tags=["Tácticas"])
async def obtener_tactica(id_equipo: int, db: AsyncSession = Depends(get_db)):
    tac = await db.get(Tactica, id_equipo)
    if not tac:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return {
        "id_equipo": tac.id_equipo, "formacion": tac.formacion,
        "mentalidad": tac.mentalidad, "presion": tac.presion, "estilo_pase": tac.estilo_pase,
    }


@router.post("/tacticas/configurar", tags=["Tácticas"])
async def configurar_tactica(datos: TacticaIn, db: AsyncSession = Depends(get_db)):
    tac = await db.get(Tactica, datos.id_equipo)
    if not tac:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    tac.formacion = datos.formacion
    tac.mentalidad = datos.mentalidad
    tac.presion = datos.presion
    tac.estilo_pase = datos.estilo_pase

    equipo = await db.get(Equipo, datos.id_equipo)
    fecha = await _fecha_actual(db, equipo.id_partida)
    await _crear_mensaje(
        db, datos.id_equipo, "Cuerpo Técnico", "Táctica actualizada",
        f"Se actualizó la táctica del equipo: formación {datos.formacion}, mentalidad {datos.mentalidad}, presión {datos.presion}.",
        "TACTICA", fecha,
    )

    await db.commit()
    return {"status": "ok", "mensaje": "Táctica actualizada"}
