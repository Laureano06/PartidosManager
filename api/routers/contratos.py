from fastapi import APIRouter
from api.runtime import (
    AsyncSession,
    DIAS_ELEGIBLE_PRECONTRATO,
    Depends,
    Equipo,
    HTTPException,
    Jugador,
    RenovarContratoIn,
    _crear_mensaje,
    _fecha_actual,
    _margen_salarial_disponible,
    disposicion_renovar,
    evaluar_renovacion,
    get_db,
    money,
    timedelta
)

router = APIRouter()

@router.get("/contratos/{id_jugador}", tags=["Contratos"])
async def obtener_contrato(id_jugador: int, db: AsyncSession = Depends(get_db)):
    jugador = await db.get(Jugador, id_jugador)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    fecha = await _fecha_actual(db, jugador.id_partida)
    dias_restantes = (jugador.fecha_fin_contrato - fecha).days if jugador.fecha_fin_contrato else None
    equipo_precontrato = await db.get(Equipo, jugador.id_equipo_precontrato) if jugador.id_equipo_precontrato else None
    return {
        "id_jugador": jugador.id_jugador,
        "fecha_fin_contrato": jugador.fecha_fin_contrato.isoformat() if jugador.fecha_fin_contrato else None,
        "dias_restantes": dias_restantes,
        "salario": jugador.salario,
        "es_libre": jugador.id_equipo is None,
        "elegible_precontrato": dias_restantes is not None and 0 < dias_restantes <= DIAS_ELEGIBLE_PRECONTRATO,
        "id_equipo_precontrato": jugador.id_equipo_precontrato,
        "nombre_equipo_precontrato": equipo_precontrato.nombre if equipo_precontrato else None,
    }


@router.post("/contratos/renovar", tags=["Contratos"])
async def renovar_contrato(datos: RenovarContratoIn, db: AsyncSession = Depends(get_db)):
    jugador = await db.get(Jugador, datos.id_jugador)
    if not jugador or not jugador.id_equipo:
        raise HTTPException(status_code=404, detail="Jugador no encontrado o sin club")

    equipo = await db.get(Equipo, jugador.id_equipo)
    if datos.ronda == 0:
        disposicion = disposicion_renovar(jugador.overall, jugador.edad, jugador.rol, jugador.moral, equipo.reputacion, jugador.relacion_dt)
        if not disposicion["quiere"]:
            return {"estado": "QUIERE_IRSE", "mensaje": disposicion["motivo"]}

    margen = await _margen_salarial_disponible(db, equipo, excluir_jugador=jugador)
    if datos.salario_propuesto > margen:
        return {
            "estado": "SIN_MARGEN_SALARIAL",
            "mensaje": f"Esa renovación supera tu tope de fair play financiero — te quedan ${money(max(0, margen))}/semana de margen.",
        }

    resultado = evaluar_renovacion(datos.salario_propuesto, jugador.valor_mercado, jugador.edad, ronda=datos.ronda)

    if resultado["estado"] == "ACEPTADA":
        fecha = await _fecha_actual(db, jugador.id_partida)
        jugador.salario = datos.salario_propuesto
        jugador.fecha_fin_contrato = fecha + timedelta(days=365 * datos.anios)
        jugador.clausula_rescision = datos.clausula_rescision
        mensaje = f"{jugador.nombre} renovó contrato hasta el {jugador.fecha_fin_contrato.strftime('%d/%m/%Y')} por ${money(datos.salario_propuesto)}/semana."
        await _crear_mensaje(db, jugador.id_equipo, "Secretaría Técnica", f"Renovación: {jugador.nombre}", mensaje, "CONTRATO", fecha)
        await db.commit()
        resultado["mensaje"] = mensaje

    return resultado
