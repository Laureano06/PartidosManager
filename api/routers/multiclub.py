from fastapi import APIRouter
from api.runtime import (
    AfiliacionClub,
    AsyncSession,
    DURACIONES_CESION_VALIDAS,
    Depends,
    Equipo,
    HTTPException,
    InfluenciaIn,
    Jugador,
    MoverJugadorIn,
    OfertaParticipacionIn,
    Partida,
    SolicitudParticipacion,
    _aplicar_cesion,
    _aplicar_transferencia_interna,
    _bono_red_equipo,
    _crear_mensaje,
    _fecha_actual,
    _presupuesto_referencia_liga,
    _valor_club_equipo,
    and_,
    directiva_engine,
    func,
    get_db,
    money,
    multiclub_engine,
    or_,
    select,
    timedelta
)

router = APIRouter()

@router.get("/equipos/{id_equipo}/multiclub", tags=["Multiclub"])
async def obtener_multiclub(id_equipo: int, db: AsyncSession = Depends(get_db)):
    equipo = await db.get(Equipo, id_equipo)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    tenencias = (await db.execute(
        select(AfiliacionClub).where(AfiliacionClub.id_partida == equipo.id_partida, AfiliacionClub.id_equipo_inversor == id_equipo)
    )).scalars().all()
    participaciones_sobre_mi = (await db.execute(
        select(AfiliacionClub).where(AfiliacionClub.id_partida == equipo.id_partida, AfiliacionClub.id_equipo_participado == id_equipo)
    )).scalars().all()
    ids_contraparte = {a.id_equipo_participado for a in tenencias} | {a.id_equipo_inversor for a in participaciones_sobre_mi}
    socios_marca = []
    if equipo.red_marca:
        socios_marca = (await db.execute(
            select(Equipo).where(Equipo.id_partida == equipo.id_partida, Equipo.red_marca == equipo.red_marca, Equipo.id_equipo != id_equipo)
        )).scalars().all()
        ids_contraparte.update(s.id_equipo for s in socios_marca)
    equipos_contraparte = {e.id_equipo: e for e in (
        await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_contraparte)))
    ).scalars().all()} if ids_contraparte else {}

    bono_red = await _bono_red_equipo(db, equipo)
    # (tipo_relacion, rol, reputacion_contraparte, nombre_contraparte) — se
    # guarda el nombre al lado para no tener que reconstruir cuál vínculo
    # ganó después de elegir el más fuerte con fuerza_relacion.
    candidatos = [
        (a.tipo_relacion, "PARTICIPADO", equipos_contraparte[a.id_equipo_inversor].reputacion, equipos_contraparte[a.id_equipo_inversor].nombre)
        for a in participaciones_sobre_mi if a.id_equipo_inversor in equipos_contraparte
    ]
    candidatos += [
        (a.tipo_relacion, "INVERSOR", equipos_contraparte[a.id_equipo_participado].reputacion, equipos_contraparte[a.id_equipo_participado].nombre)
        for a in tenencias if a.id_equipo_participado in equipos_contraparte
    ]
    candidatos += [("MARCA", "MARCA", socio.reputacion, socio.nombre) for socio in socios_marca]
    posicion = None
    if candidatos:
        tipo, rol, _, nombre_contraparte = max(candidatos, key=lambda c: multiclub_engine.fuerza_relacion(c[0], c[1], c[2]))
        posicion = {"tipo_relacion": tipo, "rol": rol, "contraparte": nombre_contraparte}

    pendientes = (await db.execute(
        select(SolicitudParticipacion).where(
            SolicitudParticipacion.id_partida == equipo.id_partida,
            SolicitudParticipacion.id_equipo_iniciador == id_equipo,
            SolicitudParticipacion.estado == "PENDIENTE",
        )
    )).scalars().all()

    return {
        "posicion": posicion,
        "bono": bono_red,
        "red_marca": equipo.red_marca,
        # socio_marca se conserva para clientes anteriores; socios_marca es
        # la lista completa que necesita una red real como City Football Group.
        "socio_marca": socios_marca[0].nombre if socios_marca else None,
        "socios_marca": [{"id_equipo": socio.id_equipo, "nombre": socio.nombre} for socio in socios_marca],
        "tus_participaciones": [
            {"id_equipo": a.id_equipo_participado, "nombre": equipos_contraparte[a.id_equipo_participado].nombre,
             "porcentaje": a.porcentaje, "tipo_relacion": a.tipo_relacion, "id_afiliacion": a.id_afiliacion,
             "influencia_habilitada": a.influencia_habilitada,
             "pipeline_habilitado": a.tipo_relacion in multiclub_engine.TIPOS_CON_PIPELINE}
            for a in tenencias if a.id_equipo_participado in equipos_contraparte
        ],
        "participaciones_sobre_tu_club": [
            {"id_equipo": a.id_equipo_inversor, "nombre": equipos_contraparte[a.id_equipo_inversor].nombre,
             "porcentaje": a.porcentaje, "tipo_relacion": a.tipo_relacion, "id_afiliacion": a.id_afiliacion,
             "influencia_habilitada": a.influencia_habilitada,
             "pipeline_habilitado": a.tipo_relacion in multiclub_engine.TIPOS_CON_PIPELINE}
            for a in participaciones_sobre_mi if a.id_equipo_inversor in equipos_contraparte
        ],
        "solicitudes_pendientes": [
            {"id_solicitud": s.id_solicitud, "id_equipo_contraparte": s.id_equipo_contraparte,
             "operacion": s.operacion, "porcentaje": s.porcentaje, "monto": s.monto,
             "fase": s.fase, "fecha_resolucion": s.fecha_resolucion.isoformat()}
            for s in pendientes
        ],
    }


@router.get("/equipos/{id_equipo}/multiclub/mercado", tags=["Multiclub"])
async def mercado_multiclub(id_equipo: int, db: AsyncSession = Depends(get_db)):
    equipo = await db.get(Equipo, id_equipo)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    # Clubes de tu MISMA liga quedan afuera del mercado: en la realidad las
    # reglas de multipropiedad prohíben tener participación en dos clubes
    # que compiten en la misma competición (conflicto de interés deportivo).
    otros = (await db.execute(
        select(Equipo).where(
            Equipo.id_partida == equipo.id_partida, Equipo.id_equipo != id_equipo, Equipo.id_liga != equipo.id_liga,
        )
    )).scalars().all()
    tenencias = {a.id_equipo_participado: a for a in (await db.execute(
        select(AfiliacionClub).where(AfiliacionClub.id_partida == equipo.id_partida, AfiliacionClub.id_equipo_inversor == id_equipo)
    )).scalars().all()}
    # valor_club de TODOS los clubes en 2 consultas (una agregada de plantel,
    # nada de N+1) — con ~180 clubes por partida, una consulta por club era
    # la diferencia entre milisegundos y minutos con la latencia de Neon.
    valores_plantel = dict((await db.execute(
        select(Jugador.id_equipo, func.coalesce(func.sum(Jugador.valor_mercado), 0))
        .where(Jugador.id_equipo.in_([o.id_equipo for o in otros]), Jugador.categoria == "PRIMERA")
        .group_by(Jugador.id_equipo)
    )).all())

    salida = [
        {
            "id_equipo": otro.id_equipo, "nombre": otro.nombre, "id_liga": otro.id_liga, "reputacion": otro.reputacion,
            "valor_club": multiclub_engine.valor_club(otro.reputacion, otro.presupuesto_fichajes, valores_plantel.get(otro.id_equipo, 0)),
            "tu_porcentaje": tenencias[otro.id_equipo].porcentaje if otro.id_equipo in tenencias else 0,
        }
        for otro in otros
    ]
    return {"clubes": salida}


@router.get("/multiclub/cotizar", tags=["Multiclub"])
async def cotizar_participacion(id_equipo_iniciador: int, id_equipo_contraparte: int, operacion: str, porcentaje: int, db: AsyncSession = Depends(get_db)):
    contraparte = await db.get(Equipo, id_equipo_contraparte)
    if not contraparte:
        raise HTTPException(status_code=404, detail="Club objetivo no encontrado")
    if operacion == "COMPRAR":
        iniciador = await db.get(Equipo, id_equipo_iniciador)
        if iniciador and iniciador.id_liga == contraparte.id_liga:
            raise HTTPException(status_code=400, detail="No podés comprar participación en un club de tu misma liga (conflicto de interés deportivo).")
    valor = await _valor_club_equipo(db, contraparte)
    afiliacion = (await db.execute(
        select(AfiliacionClub).where(
            AfiliacionClub.id_partida == contraparte.id_partida,
            AfiliacionClub.id_equipo_inversor == id_equipo_iniciador,
            AfiliacionClub.id_equipo_participado == id_equipo_contraparte,
        )
    )).scalars().first()
    porcentaje_actual = afiliacion.porcentaje if afiliacion else 0
    if operacion == "VENDER":
        if porcentaje > porcentaje_actual:
            raise HTTPException(status_code=400, detail="No podés vender más de lo que tenés")
        monto = multiclub_engine.ingreso_venta(valor, porcentaje_actual, porcentaje_actual - porcentaje)
        tipo_relevante = multiclub_engine.tipo_relacion_por_porcentaje(porcentaje_actual) or "MINORITARIO"
    else:
        if porcentaje_actual + porcentaje > 100:
            raise HTTPException(status_code=400, detail=f"No podés superar el 100% (ya tenés {porcentaje_actual}%)")
        monto = multiclub_engine.costo_participacion(valor, porcentaje_actual, porcentaje_actual + porcentaje)
        tipo_relevante = multiclub_engine.tipo_relacion_por_porcentaje(porcentaje_actual + porcentaje) or "MINORITARIO"

    presupuesto_referencia_liga = await _presupuesto_referencia_liga(db, contraparte)
    interes = multiclub_engine.interes_directiva_contraparte(
        contraparte.reputacion, contraparte.presupuesto_fichajes, presupuesto_referencia_liga, tipo_relevante, operacion,
    )
    return {
        "valor_club": valor, "porcentaje_actual": porcentaje_actual, "monto": monto,
        "tipo_relacion_resultante": tipo_relevante, "interes_directiva_contraparte": interes,
    }


@router.post("/multiclub/ofertar", tags=["Multiclub"])
async def ofertar_participacion(datos: OfertaParticipacionIn, db: AsyncSession = Depends(get_db)):
    if datos.operacion not in ("COMPRAR", "VENDER"):
        raise HTTPException(status_code=400, detail="Operación inválida")
    if datos.id_equipo_iniciador == datos.id_equipo_contraparte:
        raise HTTPException(status_code=400, detail="No podés operar sobre tu propio club")
    iniciador = await db.get(Equipo, datos.id_equipo_iniciador)
    contraparte = await db.get(Equipo, datos.id_equipo_contraparte)
    if not iniciador or not contraparte:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    if datos.operacion == "COMPRAR" and iniciador.id_liga == contraparte.id_liga:
        raise HTTPException(status_code=400, detail="No podés comprar participación en un club de tu misma liga (conflicto de interés deportivo).")

    ya_pendiente = (await db.execute(
        select(SolicitudParticipacion).where(
            SolicitudParticipacion.id_equipo_iniciador == datos.id_equipo_iniciador,
            SolicitudParticipacion.id_equipo_contraparte == datos.id_equipo_contraparte,
            SolicitudParticipacion.estado == "PENDIENTE",
        )
    )).scalars().first()
    if ya_pendiente:
        raise HTTPException(status_code=400, detail="Ya hay una operación pendiente con ese club")

    valor = await _valor_club_equipo(db, contraparte)
    afiliacion = (await db.execute(
        select(AfiliacionClub).where(
            AfiliacionClub.id_partida == iniciador.id_partida,
            AfiliacionClub.id_equipo_inversor == datos.id_equipo_iniciador,
            AfiliacionClub.id_equipo_participado == datos.id_equipo_contraparte,
        )
    )).scalars().first()
    porcentaje_actual = afiliacion.porcentaje if afiliacion else 0
    if datos.operacion == "VENDER":
        if datos.porcentaje > porcentaje_actual:
            raise HTTPException(status_code=400, detail="No podés vender más de lo que tenés")
        monto = multiclub_engine.ingreso_venta(valor, porcentaje_actual, porcentaje_actual - datos.porcentaje)
    else:
        if porcentaje_actual + datos.porcentaje > 100:
            raise HTTPException(status_code=400, detail=f"No podés superar el 100% (ya tenés {porcentaje_actual}%)")
        monto = multiclub_engine.costo_participacion(valor, porcentaje_actual, porcentaje_actual + datos.porcentaje)

    fecha = await _fecha_actual(db, iniciador.id_partida)
    partida = await db.get(Partida, iniciador.id_partida)
    confianza = partida.confianza_directiva if partida else directiva_engine.CONFIANZA_INICIAL
    dias = multiclub_engine.dias_espera_directiva_propia(confianza, monto, iniciador.presupuesto_fichajes)
    fecha_resolucion = fecha + timedelta(days=dias)

    solicitud = SolicitudParticipacion(
        id_partida=iniciador.id_partida, id_equipo_iniciador=datos.id_equipo_iniciador,
        id_equipo_contraparte=datos.id_equipo_contraparte, operacion=datos.operacion, porcentaje=datos.porcentaje,
        monto=monto, fecha_solicitud=fecha, fecha_resolucion=fecha_resolucion,
    )
    db.add(solicitud)
    nombre_op = "compra" if datos.operacion == "COMPRAR" else "venta"
    await _crear_mensaje(
        db, datos.id_equipo_iniciador, "Directiva del Club", f"Solicitud enviada: {contraparte.nombre}",
        f"Se elevó a la directiva la {nombre_op} de {datos.porcentaje}% de {contraparte.nombre} por ${money(monto)}. "
        f"Primero se evalúa internamente, respuesta estimada el {fecha_resolucion.strftime('%d/%m/%Y')}.",
        "SISTEMA", fecha,
    )
    await db.commit()
    return {
        "status": "ok", "monto": monto,
        "mensaje": f"Solicitud enviada, primera respuesta estimada el {fecha_resolucion.strftime('%d/%m/%Y')}",
        "fecha_resolucion": fecha_resolucion.isoformat(),
    }


@router.post("/multiclub/solicitud/{id_solicitud}/retirar", tags=["Multiclub"])
async def retirar_solicitud_participacion(id_solicitud: int, id_equipo: int, db: AsyncSession = Depends(get_db)):
    """Permite al equipo iniciador retirar una SolicitudParticipacion propia
    mientras siga PENDIENTE — antes no había forma de deshacer un envío por
    error antes de que la directiva la resolviera."""
    solicitud = await db.get(SolicitudParticipacion, id_solicitud)
    if not solicitud or solicitud.id_equipo_iniciador != id_equipo:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if solicitud.estado != "PENDIENTE":
        raise HTTPException(status_code=400, detail="Esa solicitud ya no está pendiente")
    solicitud.estado = "CANCELADA"
    await db.commit()
    return {"status": "ok"}


@router.post("/multiclub/mover-jugador", tags=["Multiclub"])
async def mover_jugador_afiliado(datos: MoverJugadorIn, db: AsyncSession = Depends(get_db)):
    """Pipeline de préstamos/transferencias facilitado entre dos clubes con
    una AfiliacionClub Satélite o Propietario — sin negociación, sin tirada
    de interés, instantáneo (a diferencia de /fichajes/ceder o una
    transferencia normal)."""
    if datos.operacion not in ("PRESTAMO", "TRANSFERENCIA"):
        raise HTTPException(status_code=400, detail="Operación inválida")
    jugador = await db.get(Jugador, datos.id_jugador)
    if not jugador or not jugador.id_equipo:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    if jugador.id_equipo_dueno is not None:
        raise HTTPException(status_code=400, detail="Ese jugador ya está cedido a préstamo en otro club")
    origen = await db.get(Equipo, jugador.id_equipo)
    destino = await db.get(Equipo, datos.id_equipo_destino)
    if not destino:
        raise HTTPException(status_code=404, detail="Club destino no encontrado")
    if origen.id_equipo == destino.id_equipo:
        raise HTTPException(status_code=400, detail="El jugador ya está en ese club")

    afiliacion = (await db.execute(
        select(AfiliacionClub).where(
            AfiliacionClub.id_partida == origen.id_partida,
            AfiliacionClub.tipo_relacion.in_(multiclub_engine.TIPOS_CON_PIPELINE),
            or_(
                and_(AfiliacionClub.id_equipo_inversor == origen.id_equipo, AfiliacionClub.id_equipo_participado == destino.id_equipo),
                and_(AfiliacionClub.id_equipo_inversor == destino.id_equipo, AfiliacionClub.id_equipo_participado == origen.id_equipo),
            ),
        )
    )).scalars().first()
    if not afiliacion:
        raise HTTPException(status_code=400, detail="Estos clubes no tienen una afiliación (Satélite o Propietario) que habilite el pipeline")

    fecha = await _fecha_actual(db, origen.id_partida)

    if datos.operacion == "PRESTAMO":
        if datos.duracion_meses not in DURACIONES_CESION_VALIDAS:
            raise HTTPException(status_code=400, detail="La duración de la cesión debe ser 6 o 12 meses")
        _aplicar_cesion(jugador, origen, destino, datos.duracion_meses, datos.opcion_compra, fecha)
        monto = 0
        mensaje = f"{destino.nombre} se lleva a {jugador.nombre} a préstamo por el pipeline de tu red multiclub."
    else:
        monto = multiclub_engine.costo_transferencia_interna(jugador.valor_mercado)
        _aplicar_transferencia_interna(jugador, origen, destino, fecha, monto)
        mensaje = f"{destino.nombre} se queda con {jugador.nombre} por transferencia interna (precio de familia: ${money(monto)})."

    if origen.es_usuario:
        await _crear_mensaje(db, origen.id_equipo, "Secretaría Técnica", f"Movimiento interno: {jugador.nombre}", mensaje, "MERCADO", fecha)
    if destino.es_usuario:
        await _crear_mensaje(db, destino.id_equipo, "Secretaría Técnica", f"Movimiento interno: {jugador.nombre}", mensaje, "MERCADO", fecha)

    await db.commit()
    return {"status": "ok", "mensaje": mensaje, "monto": monto}


@router.post("/multiclub/influencia", tags=["Multiclub"])
async def togglear_influencia(datos: InfluenciaIn, db: AsyncSession = Depends(get_db)):
    """Habilita/deshabilita que el equipo inversor gestione táctica,
    entrenamiento y fichajes del club participado (ver clubActivo en el
    frontend) — solo para afiliaciones Satélite o Propietario."""
    afiliacion = await db.get(AfiliacionClub, datos.id_afiliacion)
    if not afiliacion:
        raise HTTPException(status_code=404, detail="Afiliación no encontrada")
    if afiliacion.tipo_relacion not in multiclub_engine.TIPOS_CON_PIPELINE:
        raise HTTPException(status_code=400, detail="Esta afiliación no permite influencia (solo Satélite o Propietario)")
    afiliacion.influencia_habilitada = datos.habilitada
    await db.commit()
    return {"status": "ok", "influencia_habilitada": afiliacion.influencia_habilitada}
