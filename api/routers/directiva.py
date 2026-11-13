import json

from fastapi import APIRouter
from api.runtime import (
    AsyncSession,
    Depends,
    ElegirDestinoDTIn,
    Equipo,
    HTTPException,
    Liga,
    Jugador,
    OfertaClubDT,
    Partida,
    automatizaciones_de_partida,
    AUTOMATIZACIONES_DEFAULT,
    _crear_mensaje,
    _equipo_usuario,
    _generar_ofertas_dt,
    _ofertas_dt_out,
    delete,
    directiva_engine,
    get_db,
    nivel_desde_reputacion,
    objetivo_por_nivel,
    random,
    select,
    timedelta
)

router = APIRouter()

@router.get("/partidas/{id_partida}/directiva", tags=["Directiva"])
async def obtener_directiva(id_partida: int, db: AsyncSession = Depends(get_db)):
    partida = await db.get(Partida, id_partida)
    if not partida:
        raise HTTPException(status_code=404, detail="Partida no encontrada")
    dias_restantes = (partida.contrato_dt_fecha_fin - partida.fecha_actual).days if partida.contrato_dt_fecha_fin else None
    equipo_usuario = await _equipo_usuario(db, id_partida)
    return {
        "confianza_directiva": partida.confianza_directiva,
        "balance_dt": partida.balance_dt,
        "objetivo_temporada": partida.objetivo_temporada,
        "contrato_dt_anios": partida.contrato_dt_anios,
        "contrato_dt_fecha_fin": partida.contrato_dt_fecha_fin.isoformat() if partida.contrato_dt_fecha_fin else None,
        "dias_restantes_contrato": dias_restantes,
        "estado_dt": partida.estado_dt,
        "humor_hinchada": equipo_usuario.humor_hinchada if equipo_usuario else 60,
        "automatizaciones": automatizaciones_de_partida(partida.automatizaciones_json),
        "ofertas": await _ofertas_dt_out(db, id_partida) if partida.estado_dt != "NORMAL" else [],
    }


@router.get("/partidas/{id_partida}/direccion-deportiva", tags=["Directiva"])
async def informe_direccion_deportiva(id_partida: int, db: AsyncSession = Depends(get_db)):
    """Resumen accionable del plantel, sin tomar decisiones por el usuario."""
    partida = await db.get(Partida, id_partida)
    equipo = await _equipo_usuario(db, id_partida)
    if not partida or not equipo:
        raise HTTPException(status_code=404, detail="No se encontró la carrera o su club")

    primera = (await db.execute(select(Jugador).where(
        Jugador.id_equipo == equipo.id_equipo, Jugador.categoria == "PRIMERA"
    ))).scalars().all()
    juveniles = (await db.execute(select(Jugador).where(
        Jugador.id_equipo == equipo.id_equipo, Jugador.categoria == "SUB21"
    ))).scalars().all()
    limite = partida.fecha_actual + timedelta(days=180)
    contratos = sorted(
        [j for j in primera if j.fecha_fin_contrato and partida.fecha_actual <= j.fecha_fin_contrato <= limite],
        key=lambda j: j.fecha_fin_contrato,
    )[:6]
    lineas = []
    for posicion in ("POR", "DEF", "MED", "DEL"):
        grupo = [j for j in primera if j.posicion == posicion]
        lineas.append({"posicion": posicion, "cantidad": len(grupo),
                       "overall_medio": round(sum(j.overall for j in grupo) / len(grupo)) if grupo else 0,
                       "prioridad": "ALTA" if len(grupo) < 2 else "MEDIA" if len(grupo) < 4 else "CUBIERTA"})
    promesas = sorted(juveniles, key=lambda j: (j.potencial - j.overall, j.potencial, j.overall), reverse=True)[:5]
    return {
        "fecha": partida.fecha_actual.isoformat(),
        "contratos": [{"id_jugador": j.id_jugador, "nombre": j.nombre, "posicion": j.posicion_especifica or j.posicion,
                         "overall": j.overall, "vence": j.fecha_fin_contrato.isoformat(),
                         "dias": (j.fecha_fin_contrato - partida.fecha_actual).days} for j in contratos],
        "cobertura": lineas,
        "promesas": [{"id_jugador": j.id_jugador, "nombre": j.nombre, "posicion": j.posicion_especifica or j.posicion,
                       "overall": j.overall, "potencial": j.potencial} for j in promesas],
    }


@router.put("/partidas/{id_partida}/automatizaciones", tags=["Directiva"])
async def actualizar_automatizaciones(id_partida: int, datos: dict, db: AsyncSession = Depends(get_db)):
    """Activa o pausa módulos automáticos de una carrera, sin alterar datos."""
    partida = await db.get(Partida, id_partida)
    if not partida:
        raise HTTPException(status_code=404, detail="Partida no encontrada")
    recibidas = datos.get("automatizaciones")
    if not isinstance(recibidas, dict):
        raise HTTPException(status_code=400, detail="Se esperaba el objeto automatizaciones")
    actuales = automatizaciones_de_partida(partida.automatizaciones_json)
    for clave in AUTOMATIZACIONES_DEFAULT:
        if clave in recibidas:
            actuales[clave] = bool(recibidas[clave])
    partida.automatizaciones_json = json.dumps(actuales)
    await db.commit()
    return {"automatizaciones": actuales}


@router.post("/partidas/{id_partida}/renunciar", tags=["Directiva"])
async def renunciar_dt(id_partida: int, db: AsyncSession = Depends(get_db)):
    partida = await db.get(Partida, id_partida)
    if not partida:
        raise HTTPException(status_code=404, detail="Partida no encontrada")
    if partida.estado_dt != "NORMAL":
        raise HTTPException(status_code=400, detail="Ya tenés una decisión pendiente — resolvela antes de renunciar")
    equipo_usuario = await _equipo_usuario(db, id_partida)
    if not equipo_usuario:
        raise HTTPException(status_code=404, detail="No se encontró tu club")

    await _generar_ofertas_dt(db, id_partida, partida.balance_dt, "mismo", equipo_usuario.id_equipo)
    partida.estado_dt = "RENUNCIO"
    await _crear_mensaje(
        db, equipo_usuario.id_equipo, "Directiva del Club", "Renunciaste al cargo",
        "Presentaste tu renuncia. Tenés 3 propuestas de otros clubes, acordes a tu trayectoria, esperando tu decisión.",
        "SISTEMA", partida.fecha_actual,
    )
    await db.commit()
    return {"status": "ok", "estado_dt": partida.estado_dt, "ofertas": await _ofertas_dt_out(db, id_partida)}


@router.post("/partidas/{id_partida}/elegir-destino", tags=["Directiva"])
async def elegir_destino_dt(id_partida: int, datos: ElegirDestinoDTIn, db: AsyncSession = Depends(get_db)):
    partida = await db.get(Partida, id_partida)
    if not partida:
        raise HTTPException(status_code=404, detail="Partida no encontrada")
    if partida.estado_dt == "NORMAL":
        raise HTTPException(status_code=400, detail="No tenés ninguna decisión pendiente")

    if datos.opcion == "renovar":
        if partida.estado_dt not in ("CONTRATO_FIN_EXITO", "CONTRATO_FIN_RENOVACION_OFRECIDA"):
            raise HTTPException(status_code=400, detail="La renovación no está disponible en esta situación")
        partida.contrato_dt_anios = random.randint(1, 3)
        partida.contrato_dt_fecha_fin = partida.fecha_actual + timedelta(days=365 * partida.contrato_dt_anios)
        # Mismo club, sigue la misma relación — la confianza no se resetea.
    else:
        if not datos.opcion.startswith("id_equipo:"):
            raise HTTPException(status_code=400, detail="Opción inválida")
        id_equipo_nuevo = int(datos.opcion.split(":", 1)[1])
        oferta_valida = (await db.execute(
            select(OfertaClubDT).where(OfertaClubDT.id_partida == id_partida, OfertaClubDT.id_equipo == id_equipo_nuevo)
        )).scalars().first()
        if not oferta_valida:
            raise HTTPException(status_code=400, detail="Esa oferta no está entre las disponibles")
        equipo_nuevo = await db.get(Equipo, id_equipo_nuevo)
        equipo_anterior = await _equipo_usuario(db, id_partida)
        if equipo_anterior:
            equipo_anterior.es_usuario = False
        equipo_nuevo.es_usuario = True
        liga_nueva = await db.get(Liga, equipo_nuevo.id_liga)
        partida.confianza_directiva = directiva_engine.CONFIANZA_INICIAL
        partida.contrato_dt_anios = random.randint(1, 3)
        partida.contrato_dt_fecha_fin = partida.fecha_actual + timedelta(days=365 * partida.contrato_dt_anios)
        nivel_nuevo = nivel_desde_reputacion(liga_nueva.codigo, equipo_nuevo.reputacion) if liga_nueva else 0.5
        partida.objetivo_temporada = objetivo_por_nivel(nivel_nuevo)

    partida.estado_dt = "NORMAL"
    await db.execute(delete(OfertaClubDT).where(OfertaClubDT.id_partida == id_partida))
    await db.commit()
    return {"status": "ok"}
