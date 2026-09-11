from models import HistorialNegociacion
import json
from fastapi import APIRouter
from api.runtime import (
    AddOnTransferencia,
    AsyncSession,
    CederJugadorIn,
    DIAS_ELEGIBLE_PRECONTRATO,
    DURACIONES_CESION_VALIDAS,
    Depends,
    Equipo,
    FicharLibreIn,
    HTTPException,
    Jugador,
    Liga,
    NegociarContratoTraspasoIn,
    OfertaFichaje,
    OfertaIn,
    OfrecerJugadorIn,
    POSICIONES_CANCHA,
    PrecontratoIn,
    RespuestaOfertaIn,
    _aplicar_cesion,
    _aplicar_fog,
    _asegurar_academia,
    _crear_mensaje,
    _efectivizar_ofertas_pendientes,
    _equipo_usuario,
    _fecha_actual,
    _margen_salarial_disponible,
    _promedios_por_posicion,
    _reportes_de,
    _texto_incorporacion,
    date,
    disposicion_fichar,
    evaluar_oferta,
    evaluar_renovacion,
    get_db,
    money,
    or_,
    random,
    salario_esperado,
    select,
    timedelta
)

router = APIRouter()

@router.get("/mercado/jugadores", tags=["Transferencias"])
async def listar_mercado(
    id_equipo: int | None = None,
    id_partida: int | None = None,
    id_liga: int | None = None,
    posicion: str | None = None,
    posicion_especifica: str | None = None,
    edad_min: int | None = None,
    edad_max: int | None = None,
    overall_min: int | None = None,
    club: str | None = None,
    nombre: str | None = None,
    categoria: str | None = None,
    solo_libres: bool = False,
    solo_transferibles: bool = False,
    solo_cedibles: bool = False,
    orden: str = "valor",
    limit: int = 200,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    if id_equipo is None:
        equipo_usuario = await _equipo_usuario(db, id_partida) if id_partida else None
        id_equipo = equipo_usuario.id_equipo if equipo_usuario else None
    else:
        equipo_ref = await db.get(Equipo, id_equipo)
        if equipo_ref:
            id_partida = equipo_ref.id_partida

    # outerjoin porque los agentes libres (id_equipo NULL) no tienen fila en
    # equipos; con un join normal desaparecían del todo del mercado.
    query = (
        select(Jugador, Equipo.nombre, Equipo.id_liga)
        .outerjoin(Equipo, Jugador.id_equipo == Equipo.id_equipo)
        .where(or_(Jugador.id_equipo.is_(None), Jugador.id_equipo != id_equipo))
    )
    # Por defecto el mercado es de jugadores "adultos": Primera y Sub-21 (ya
    # prácticamente adultos, se reclutan por este mismo flujo). Un categoria
    # explícito (SUB13/15/18) es lo que usa Academia para navegar/robar
    # juveniles de otro club — nunca se cuelan de por sí en el mercado normal.
    if categoria is not None:
        query = query.where(Jugador.categoria == categoria)
    else:
        query = query.where(Jugador.categoria.in_(["PRIMERA", "SUB21"]))
    if id_partida is not None:
        query = query.where(Jugador.id_partida == id_partida)
    if solo_libres:
        query = query.where(Jugador.id_equipo.is_(None))
    if solo_transferibles:
        query = query.where(Jugador.en_transferible.is_(True))
    if solo_cedibles:
        # Un jugador cedible pertenece aún a su club, no está prestado en
        # otro equipo y no es una pieza titular de esa plantilla.
        query = query.where(
            Jugador.id_equipo.is_not(None),
            Jugador.id_equipo_dueno.is_(None),
            Jugador.rol.in_(["SUPLENTE", "RESERVA"]),
        )
    if id_liga is not None:
        query = query.where(Equipo.id_liga == id_liga)
    if posicion:
        query = query.where(Jugador.posicion == posicion)
    if posicion_especifica:
        query = query.where(Jugador.posicion_especifica == posicion_especifica)
    if edad_min is not None:
        query = query.where(Jugador.edad >= edad_min)
    if edad_max is not None:
        query = query.where(Jugador.edad <= edad_max)
    if club:
        query = query.where(Equipo.nombre.ilike(f"%{club}%"))
    if nombre:
        query = query.where(Jugador.nombre.ilike(f"%{nombre}%"))

    # Buscando una categoría de Academia por club (así es como lo usa la
    # pantalla de Academia): la academia de ESE club puntual todavía puede no
    # haberse generado nunca (se genera perezosamente) — sin esto la
    # búsqueda vuelve vacía para cualquier club que nadie miró todavía, sea
    # de tu misma liga o de cualquier otra.
    if categoria not in (None, "PRIMERA") and club:
        query_clubes = select(Equipo).where(Equipo.nombre.ilike(f"%{club}%"))
        if id_partida is not None:
            query_clubes = query_clubes.where(Equipo.id_partida == id_partida)
        if id_liga is not None:
            query_clubes = query_clubes.where(Equipo.id_liga == id_liga)
        for eq in (await db.execute(query_clubes)).scalars().all():
            await _asegurar_academia(db, eq)

    filas = (await db.execute(query)).all()
    fecha = await _fecha_actual(db, id_partida) if id_partida else date.today()

    jugadores = []
    jugadores_orm: dict[int, Jugador] = {}
    for j, nombre_club, id_liga_row in filas:
        dias_restantes = (j.fecha_fin_contrato - fecha).days if j.fecha_fin_contrato else None
        jugadores_orm[j.id_jugador] = j
        jugadores.append({
            "id_jugador": j.id_jugador,
            "id_equipo": j.id_equipo,
            "id_liga": id_liga_row,
            "club": nombre_club or "Agente Libre",
            "nombre": j.nombre,
            "posicion": j.posicion,
            "posicion_especifica": j.posicion_especifica,
            "nacionalidad": j.nacionalidad,
            "edad": j.edad,
            "ataque": j.ataque,
            "defensa": j.defensa,
            "fisico": j.fisico,
            "valor_mercado": j.valor_mercado,
            "salario": j.salario,
            "overall": j.overall,
            "potencial": j.potencial,
            "categoria": j.categoria,
            "es_libre": j.id_equipo is None,
            "en_transferible": j.en_transferible,
            "es_cedible": j.id_equipo is not None and j.id_equipo_dueno is None and j.rol in ("SUPLENTE", "RESERVA"),
            "fecha_fin_contrato": j.fecha_fin_contrato.isoformat() if j.fecha_fin_contrato else None,
            "dias_restantes_contrato": dias_restantes,
            "elegible_precontrato": dias_restantes is not None and 0 < dias_restantes <= DIAS_ELEGIBLE_PRECONTRATO,
            "id_equipo_precontrato": j.id_equipo_precontrato,
        })

    if overall_min is not None:
        jugadores = [j for j in jugadores if j["overall"] >= overall_min]

    clave = {"valor": "valor_mercado", "overall": "overall", "edad": "edad"}.get(orden, "valor_mercado")
    jugadores.sort(key=lambda j: j[clave], reverse=(clave != "edad"))

    # Con cientos de jugadores coincidiendo, devolver TODOS de una siempre
    # es desperdiciar ancho de banda para lo que en la práctica se muestra
    # de a una pantalla — se pagina y se informa el total real aparte.
    total = len(jugadores)
    pagina = jugadores[offset:offset + limit]

    # Fog-of-war: acá adentro TODOS los jugadores son ajenos (la query ya
    # excluye al propio id_equipo más arriba), así que se aplica sin
    # branching extra — y recién sobre la página final, no sobre los cientos
    # de candidatos descartados por la paginación.
    if id_equipo is not None:
        reportes = await _reportes_de(db, id_equipo, [j["id_jugador"] for j in pagina])
        for j in pagina:
            _aplicar_fog(j, jugadores_orm[j["id_jugador"]], reportes.get(j["id_jugador"]))

    return {"jugadores": pagina, "total": total, "limit": limit, "offset": offset}


async def _resolver_oferta_fichaje(datos: OfertaIn, db: AsyncSession = Depends(get_db)):
    """Solo negocia el PRECIO con el club vendedor. Si se acuerda, todavía
    falta pactar el contrato con el jugador (POST /fichajes/negociar-contrato)
    antes de que el pase quede realmente cerrado — igual que en la vida real,
    acordar el precio con el club no significa que el jugador ya firmó."""
    jugador = await db.get(Jugador, datos.id_jugador)
    if not jugador or not jugador.id_equipo:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    comprador = await db.get(Equipo, datos.id_equipo_comprador)

    if jugador.edad < 18:
        vendedor = await db.get(Equipo, jugador.id_equipo)
        liga_vendedor = await db.get(Liga, vendedor.id_liga) if vendedor else None
        liga_comprador = await db.get(Liga, comprador.id_liga) if comprador else None
        pais_vendedor = liga_vendedor.pais if liga_vendedor else None
        pais_comprador = liga_comprador.pais if liga_comprador else None
        if pais_vendedor != pais_comprador:
            return {
                "estado": "RECHAZADA",
                "mensaje": f"La FIFA prohíbe transferencias internacionales de menores de 18 — {pais_vendedor} → {pais_comprador}.",
            }

    # Cláusula de rescisión: el club no puede negarse si se paga el monto
    # completo — se salta evaluar_oferta (rondas, demanda, intransferible)
    # por completo, sea cual sea la ronda.
    if jugador.clausula_rescision and datos.monto_oferta >= jugador.clausula_rescision:
        if comprador.presupuesto_fichajes < jugador.clausula_rescision:
            return {"estado": "RECHAZADA", "mensaje": "No tenés presupuesto suficiente."}
        return {
            "estado": "ACEPTADA_CLUB",
            "mensaje": f"Pagaste la cláusula de rescisión (${money(jugador.clausula_rescision)}) — el club no puede negarse.",
            "monto_acordado": jugador.clausula_rescision,
        }

    resultado = evaluar_oferta(datos.monto_oferta, jugador.valor_mercado, es_clave=(jugador.rol == "TITULAR"), ronda=datos.ronda)

    if resultado["estado"] == "ACEPTADA":
        if comprador.presupuesto_fichajes < datos.monto_oferta:
            return {"estado": "RECHAZADA", "mensaje": "No tenés presupuesto suficiente."}
        return {
            "estado": "ACEPTADA_CLUB",
            "mensaje": f"El club acepta ${money(datos.monto_oferta)} por {jugador.nombre}. Ahora falta acordar el contrato con el jugador.",
            "monto_acordado": datos.monto_oferta,
        }

    return resultado


async def _resolver_contrato_traspaso(datos: NegociarContratoTraspasoIn, db: AsyncSession = Depends(get_db)):
    jugador = await db.get(Jugador, datos.id_jugador)
    if not jugador or not jugador.id_equipo:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    comprador = await db.get(Equipo, datos.id_equipo_comprador)
    vendedor = await db.get(Equipo, jugador.id_equipo)
    if not comprador or not vendedor or comprador.id_partida != jugador.id_partida or comprador.id_equipo == vendedor.id_equipo:
        raise HTTPException(400, 'Los clubes deben pertenecer a la misma carrera y ser distintos')
    if datos.monto_oferta <= 0 or datos.salario_ofrecido <= 0:
        raise HTTPException(400, 'El precio y el salario deben ser positivos')
    acuerdos = (await db.scalars(select(HistorialNegociacion).where(
        HistorialNegociacion.id_jugador == jugador.id_jugador,
        HistorialNegociacion.id_equipo == comprador.id_equipo
    ).order_by(HistorialNegociacion.id.desc()).limit(50))).all()
    if not any((detalle := json.loads(a.detalle_json)).get('estado') == 'ACEPTADA_CLUB'
               and detalle.get('monto_acordado') == datos.monto_oferta
               and detalle.get('id_vendedor') == vendedor.id_equipo for a in acuerdos):
        return {'estado': 'RECHAZADA', 'mensaje': 'Primero necesitás acordar este precio con el club vendedor.'}
    if datos.clausula_rescision is not None and datos.clausula_rescision < datos.monto_oferta:
        return {'estado': 'RECHAZADA', 'mensaje': 'La cláusula de rescisión no puede ser menor que el precio del traspaso.'}

    ya_acordado = (await db.execute(
        select(OfertaFichaje.id_oferta).where(
            OfertaFichaje.id_jugador == jugador.id_jugador,
            OfertaFichaje.estado == "ACEPTADA",
            OfertaFichaje.efectivizada.is_(False),
        )
    )).first()
    if ya_acordado:
        return {"estado": "RECHAZADA", "mensaje": f"{jugador.nombre} ya acordó su pase a otro club."}

    if datos.ronda == 0:
        disposicion = disposicion_fichar(jugador.overall, jugador.edad, vendedor.reputacion, comprador.reputacion)
        if not disposicion["quiere"]:
            return {"estado": "NO_INTERESADO", "mensaje": disposicion["motivo"]}

    margen = await _margen_salarial_disponible(db, comprador)
    if datos.salario_ofrecido > margen:
        return {
            "estado": "SIN_MARGEN_SALARIAL",
            "mensaje": f"Ese sueldo supera tu tope de fair play financiero — te quedan ${money(max(0, margen))}/semana de margen.",
        }

    resultado = evaluar_renovacion(datos.salario_ofrecido, jugador.valor_mercado, jugador.edad, ronda=datos.ronda)

    if resultado["estado"] == "ACEPTADA":
        if comprador.presupuesto_fichajes < datos.monto_oferta:
            return {"estado": "RECHAZADA", "mensaje": "No tenés presupuesto suficiente para la cifra pactada con el club."}

        db.add(OfertaFichaje(
            id_jugador=jugador.id_jugador, id_equipo_comprador=comprador.id_equipo,
            id_equipo_vendedor=vendedor.id_equipo, monto_oferta=datos.monto_oferta,
            salario_pactado=datos.salario_ofrecido, estado="ACEPTADA", efectivizada=False,
            condiciones_json=json.dumps({'anios': datos.anios, 'clausula_rescision': datos.clausula_rescision}),
        ))
        # Add-ons: pagos extra que el comprador ofreció como endulzante,
        # atados a que el jugador sume partidos con su club nuevo — se
        # cobran solos, ver _calcular_efectos_fisicos.
        for addon in datos.addons:
            if addon.partidos > 0 and addon.monto > 0:
                db.add(AddOnTransferencia(
                    id_jugador=jugador.id_jugador, id_equipo_beneficiario=vendedor.id_equipo,
                    partidos_objetivo=addon.partidos, monto=addon.monto, cumplido=False,
                ))

        fecha = await _fecha_actual(db, jugador.id_partida)
        texto = _texto_incorporacion(fecha)
        mensaje = (
            f"Cerraste el fichaje de {jugador.nombre} por ${money(datos.monto_oferta)}, "
            f"contrato pactado a ${money(datos.salario_ofrecido)}/semana. Se incorporará {texto}."
        )
        await _crear_mensaje(db, comprador.id_equipo, "Secretaría Técnica", f"Acuerdo cerrado por {jugador.nombre}", mensaje, "MERCADO", fecha)

        await _efectivizar_ofertas_pendientes(db, fecha, jugador.id_partida)  # si la ventana ya está abierta, se aplica ahora mismo
        await db.commit()
        return {"estado": "ACEPTADA", "mensaje": mensaje, "jugador": jugador.nombre}

    return resultado


@router.post("/fichajes/precontrato", tags=["Transferencias"])
async def firmar_precontrato(datos: PrecontratoIn, db: AsyncSession = Depends(get_db)):
    jugador = await db.get(Jugador, datos.id_jugador)
    if not jugador or not jugador.id_equipo:
        raise HTTPException(status_code=404, detail="Jugador no encontrado o sin club")
    if jugador.id_equipo == datos.id_equipo_destino:
        raise HTTPException(status_code=400, detail="Ya juega en ese club")

    fecha = await _fecha_actual(db, jugador.id_partida)
    dias_restantes = (jugador.fecha_fin_contrato - fecha).days if jugador.fecha_fin_contrato else None
    if dias_restantes is None or dias_restantes > DIAS_ELEGIBLE_PRECONTRATO or dias_restantes <= 0:
        raise HTTPException(status_code=400, detail=f"El jugador no está a {DIAS_ELEGIBLE_PRECONTRATO} días o menos de finalizar contrato")
    if jugador.id_equipo_precontrato and jugador.id_equipo_precontrato != datos.id_equipo_destino:
        return {"estado": "RECHAZADA", "mensaje": "El jugador ya firmó un precontrato con otro club."}

    equipo_destino = await db.get(Equipo, datos.id_equipo_destino)
    equipo_actual = await db.get(Equipo, jugador.id_equipo)

    if datos.ronda == 0:
        disposicion = disposicion_fichar(jugador.overall, jugador.edad, equipo_actual.reputacion, equipo_destino.reputacion)
        if not disposicion["quiere"]:
            return {"estado": "NO_INTERESADO", "mensaje": disposicion["motivo"]}

    margen = await _margen_salarial_disponible(db, equipo_destino)
    if datos.salario_ofrecido > margen:
        return {
            "estado": "SIN_MARGEN_SALARIAL",
            "mensaje": f"Ese precontrato supera tu tope de fair play financiero — te quedan ${money(max(0, margen))}/semana de margen.",
        }

    resultado = evaluar_renovacion(datos.salario_ofrecido, jugador.valor_mercado, jugador.edad, ronda=datos.ronda)

    if resultado["estado"] == "ACEPTADA":
        jugador.id_equipo_precontrato = datos.id_equipo_destino
        jugador.salario_precontrato = datos.salario_ofrecido
        jugador.clausula_rescision = datos.clausula_rescision
        mensaje = (
            f"{jugador.nombre} firmó precontrato con {equipo_destino.nombre if equipo_destino else '?'}. "
            f"Se incorporará libre el {jugador.fecha_fin_contrato.strftime('%d/%m/%Y')}."
        )
        if equipo_destino and equipo_destino.es_usuario:
            await _crear_mensaje(db, equipo_destino.id_equipo, "Secretaría Técnica", f"Precontrato firmado: {jugador.nombre}", mensaje, "MERCADO", fecha)
        if equipo_actual and equipo_actual.es_usuario:
            await _crear_mensaje(db, equipo_actual.id_equipo, "Secretaría Técnica", f"{jugador.nombre} firmó con otro club", mensaje, "MERCADO", fecha)
        await db.commit()
        resultado["mensaje"] = mensaje

    return resultado


@router.post("/fichajes/fichar-libre", tags=["Transferencias"])
async def fichar_libre(datos: FicharLibreIn, db: AsyncSession = Depends(get_db)):
    jugador = await db.get(Jugador, datos.id_jugador)
    if not jugador or jugador.id_equipo is not None or jugador.categoria != "PRIMERA":
        raise HTTPException(status_code=404, detail="Jugador no encontrado o no es agente libre")

    equipo_destino = await db.get(Equipo, datos.id_equipo)
    if datos.ronda == 0:
        disposicion = disposicion_fichar(jugador.overall, jugador.edad, None, equipo_destino.reputacion)
        if not disposicion["quiere"]:
            return {"estado": "NO_INTERESADO", "mensaje": disposicion["motivo"]}

    margen = await _margen_salarial_disponible(db, equipo_destino)
    if datos.salario_ofrecido > margen:
        return {
            "estado": "SIN_MARGEN_SALARIAL",
            "mensaje": f"Ese sueldo supera tu tope de fair play financiero — te quedan ${money(max(0, margen))}/semana de margen.",
        }

    resultado = evaluar_renovacion(datos.salario_ofrecido, jugador.valor_mercado, jugador.edad, ronda=datos.ronda)

    if resultado["estado"] == "ACEPTADA":
        fecha = await _fecha_actual(db, jugador.id_partida)
        jugador.id_equipo = datos.id_equipo
        jugador.salario = datos.salario_ofrecido
        jugador.fecha_fin_contrato = fecha + timedelta(days=365 * 3)
        jugador.rol = "RESERVA"
        jugador.clausula_rescision = datos.clausula_rescision
        jugador.partidos_club_actual = 0
        equipo = await db.get(Equipo, datos.id_equipo)
        mensaje = f"Fichaste libre a {jugador.nombre} por ${money(datos.salario_ofrecido)}/semana."
        if equipo and equipo.es_usuario:
            await _crear_mensaje(db, datos.id_equipo, "Secretaría Técnica", f"Fichaje libre: {jugador.nombre}", mensaje, "MERCADO", fecha)
        await db.commit()
        resultado["mensaje"] = mensaje

    return resultado


@router.get("/fichajes/en-negociacion", tags=["Transferencias"])
async def en_negociacion(id_equipo: int, db: AsyncSession = Depends(get_db)):
    comprando = (await db.execute(
        select(OfertaFichaje).where(
            OfertaFichaje.id_equipo_comprador == id_equipo,
            OfertaFichaje.estado == "ACEPTADA",
            OfertaFichaje.efectivizada.is_(False),
        )
    )).scalars().all()
    vendiendo = (await db.execute(
        select(OfertaFichaje).where(
            OfertaFichaje.id_equipo_vendedor == id_equipo,
            OfertaFichaje.estado == "ACEPTADA",
            OfertaFichaje.efectivizada.is_(False),
        )
    )).scalars().all()
    recibidas = (await db.execute(
        select(OfertaFichaje).where(
            OfertaFichaje.id_equipo_vendedor == id_equipo,
            OfertaFichaje.estado == "PENDIENTE",
        )
    )).scalars().all()

    todas = comprando + vendiendo + recibidas
    ids_jugadores = {o.id_jugador for o in todas}
    ids_equipos = {o.id_equipo_comprador for o in todas} | {o.id_equipo_vendedor for o in todas}
    jugadores = {j.id_jugador: j for j in (await db.execute(select(Jugador).where(Jugador.id_jugador.in_(ids_jugadores)))).scalars().all()} if ids_jugadores else {}
    equipos = {e.id_equipo: e for e in (await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_equipos)))).scalars().all()} if ids_equipos else {}

    equipo_propio = await db.get(Equipo, id_equipo)
    fecha = await _fecha_actual(db, equipo_propio.id_partida) if equipo_propio else None
    texto_incorp = _texto_incorporacion(fecha) if fecha else None

    def _detalle(o: OfertaFichaje) -> dict | None:
        jugador = jugadores.get(o.id_jugador)
        if not jugador:
            return None
        comprador = equipos.get(o.id_equipo_comprador)
        vendedor = equipos.get(o.id_equipo_vendedor)
        return {
            "id_oferta": o.id_oferta, "id_jugador": o.id_jugador, "nombre_jugador": jugador.nombre,
            "posicion": jugador.posicion, "posicion_especifica": jugador.posicion_especifica, "overall": jugador.overall,
            "nombre_comprador": comprador.nombre if comprador else "?", "id_equipo_comprador": o.id_equipo_comprador,
            "nombre_vendedor": vendedor.nombre if vendedor else "?", "id_equipo_vendedor": o.id_equipo_vendedor,
            "monto_oferta": o.monto_oferta, "estado": o.estado,
            "texto_incorporacion": texto_incorp,
        }

    comprando_detalle = [d for d in (_detalle(o) for o in comprando) if d]
    # "Comprando" es siempre un jugador ajeno todavía no fichado — se le
    # aplica fog. "Vendiendo"/"recibidas" son plantel propio, sin fog.
    reportes = await _reportes_de(db, id_equipo, [d["id_jugador"] for d in comprando_detalle])
    for d in comprando_detalle:
        _aplicar_fog(d, jugadores[d["id_jugador"]], reportes.get(d["id_jugador"]))

    # Precontratos: no pasan por OfertaFichaje (viven en Jugador.id_equipo_precontrato/
    # salario_precontrato), así que se arman aparte — "entrantes" son ajenos
    # que van a sumarse a tu club libres cuando termine su contrato actual,
    # "salientes" son tuyos que ya firmaron para irse.
    entrantes = (await db.execute(
        select(Jugador).where(Jugador.id_equipo_precontrato == id_equipo)
    )).scalars().all()
    salientes = (await db.execute(
        select(Jugador).where(Jugador.id_equipo == id_equipo, Jugador.id_equipo_precontrato.is_not(None))
    )).scalars().all()
    ids_clubes_precontrato = {j.id_equipo for j in entrantes if j.id_equipo} | {j.id_equipo_precontrato for j in salientes}
    clubes_precontrato = {e.id_equipo: e for e in (
        await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_clubes_precontrato)))
    ).scalars().all()} if ids_clubes_precontrato else {}

    def _detalle_precontrato(j: Jugador, nombre_club: str, id_equipo_club: int | None) -> dict:
        return {
            "id_jugador": j.id_jugador, "nombre_jugador": j.nombre, "posicion": j.posicion,
            "posicion_especifica": j.posicion_especifica, "overall": j.overall, "potencial": j.potencial,
            "salario_precontrato": j.salario_precontrato,
            "fecha_fin_contrato": j.fecha_fin_contrato.isoformat() if j.fecha_fin_contrato else None,
            "nombre_club": nombre_club, "id_equipo_club": id_equipo_club,
        }

    entrantes_por_id = {j.id_jugador: j for j in entrantes}
    entrantes_detalle = [
        _detalle_precontrato(
            j,
            clubes_precontrato.get(j.id_equipo).nombre if j.id_equipo and clubes_precontrato.get(j.id_equipo) else "Agente libre",
            j.id_equipo,
        )
        for j in entrantes
    ]
    reportes_precontrato = await _reportes_de(db, id_equipo, list(entrantes_por_id))
    for d in entrantes_detalle:
        _aplicar_fog(d, entrantes_por_id[d["id_jugador"]], reportes_precontrato.get(d["id_jugador"]))
    salientes_detalle = [
        _detalle_precontrato(
            j,
            clubes_precontrato[j.id_equipo_precontrato].nombre if j.id_equipo_precontrato in clubes_precontrato else "?",
            j.id_equipo_precontrato,
        )
        for j in salientes
    ]

    return {
        "comprando": comprando_detalle,
        "vendiendo": [d for d in (_detalle(o) for o in vendiendo) if d],
        "recibidas": [d for d in (_detalle(o) for o in recibidas) if d],
        "precontratos_entrantes": entrantes_detalle,
        "precontratos_salientes": salientes_detalle,
    }


@router.get("/fichajes/ofertas-recibidas", tags=["Transferencias"])
async def ofertas_recibidas(id_equipo: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(OfertaFichaje).where(
            OfertaFichaje.id_equipo_vendedor == id_equipo,
            OfertaFichaje.estado == "PENDIENTE",
        )
    )
    ofertas = result.scalars().all()
    ids_jugadores = {o.id_jugador for o in ofertas}
    ids_compradores = {o.id_equipo_comprador for o in ofertas}
    jugadores = {j.id_jugador: j for j in (await db.execute(select(Jugador).where(Jugador.id_jugador.in_(ids_jugadores)))).scalars().all()} if ids_jugadores else {}
    compradores = {e.id_equipo: e for e in (await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_compradores)))).scalars().all()} if ids_compradores else {}

    salida = []
    for o in ofertas:
        jugador = jugadores.get(o.id_jugador)
        if not jugador:
            continue
        comprador = compradores.get(o.id_equipo_comprador)
        salida.append({
            "id_oferta": o.id_oferta, "id_jugador": o.id_jugador, "nombre_jugador": jugador.nombre,
            "posicion": jugador.posicion, "posicion_especifica": jugador.posicion_especifica, "id_equipo_comprador": o.id_equipo_comprador,
            "nombre_comprador": comprador.nombre if comprador else "?",
            "monto_oferta": o.monto_oferta,
        })
    return {"ofertas": salida}


@router.post("/fichajes/responder", tags=["Transferencias"])
async def responder_oferta(datos: RespuestaOfertaIn, db: AsyncSession = Depends(get_db)):
    oferta = await db.get(OfertaFichaje, datos.id_oferta)
    if not oferta or oferta.estado != "PENDIENTE":
        raise HTTPException(status_code=404, detail="Oferta no encontrada o ya resuelta")

    jugador = await db.get(Jugador, oferta.id_jugador)
    fecha = await _fecha_actual(db, jugador.id_partida)

    if not datos.aceptar:
        oferta.estado = "RECHAZADA"
        await db.commit()
        return {"status": "ok", "mensaje": "Rechazaste la oferta."}

    vendedor = await db.get(Equipo, oferta.id_equipo_vendedor)
    comprador = await db.get(Equipo, oferta.id_equipo_comprador)

    vendedor_plantilla = (await db.execute(select(Jugador).where(Jugador.id_equipo == vendedor.id_equipo))).scalars().all()
    if len(vendedor_plantilla) <= 14:
        raise HTTPException(status_code=400, detail="No podés vender, tu plantilla quedaría muy corta.")

    oferta.estado = "ACEPTADA"
    # Reventa: condición que pone el vendedor al aceptar, no algo que se
    # negocie — se guarda en el jugador para que _efectivizar_ofertas_pendientes
    # la cobre recién en la venta SIGUIENTE (no en esta).
    if datos.porcentaje_reventa_solicitado and 0 < datos.porcentaje_reventa_solicitado <= 100:
        jugador.id_club_reventa = vendedor.id_equipo
        jugador.porcentaje_reventa = datos.porcentaje_reventa_solicitado
    texto = _texto_incorporacion(fecha)
    mensaje = f"Aceptaste vender a {jugador.nombre} a {comprador.nombre} por ${money(oferta.monto_oferta)}. Se hará efectivo {texto}."
    await _crear_mensaje(db, vendedor.id_equipo, "Secretaría Técnica", f"Venta acordada: {jugador.nombre}", mensaje, "MERCADO", fecha)

    # El jugador ya acordó su pase: las demás ofertas pendientes por él
    # (de otros clubes) quedan sin efecto, para que no se pueda "vender"
    # dos veces al mismo jugador.
    otras_pendientes = (await db.execute(
        select(OfertaFichaje).where(
            OfertaFichaje.id_jugador == jugador.id_jugador,
            OfertaFichaje.id_oferta != oferta.id_oferta,
            OfertaFichaje.estado == "PENDIENTE",
        )
    )).scalars().all()
    for otra in otras_pendientes:
        otra.estado = "RECHAZADA"
        otro_comprador = await db.get(Equipo, otra.id_equipo_comprador)
        if otro_comprador and otro_comprador.es_usuario:
            await _crear_mensaje(
                db, otro_comprador.id_equipo, "Secretaría Técnica", f"{jugador.nombre} eligió otro club",
                f"{jugador.nombre} acordó su pase a {comprador.nombre}. Tu oferta quedó sin efecto.",
                "MERCADO", fecha,
            )

    await _efectivizar_ofertas_pendientes(db, fecha, jugador.id_partida)
    await db.commit()
    return {"status": "ok", "mensaje": mensaje}


@router.get("/fichajes/recomendaciones", tags=["Transferencias"])
async def recomendaciones_fichaje(id_equipo: int | None = None, id_partida: int | None = None, db: AsyncSession = Depends(get_db)):
    if id_equipo is None:
        equipo_usuario = await _equipo_usuario(db, id_partida) if id_partida else None
        id_equipo = equipo_usuario.id_equipo if equipo_usuario else None
    equipo = await db.get(Equipo, id_equipo)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    plantel = (await db.execute(
        select(Jugador).where(Jugador.id_equipo == id_equipo, Jugador.categoria == "PRIMERA")
    )).scalars().all()
    promedios = _promedios_por_posicion(plantel)
    posiciones_ordenadas = sorted(POSICIONES_CANCHA, key=lambda p: promedios[p])
    posiciones_prioritarias = posiciones_ordenadas[:2]

    filas = (await db.execute(
        select(Jugador, Equipo.nombre)
        .outerjoin(Equipo, Jugador.id_equipo == Equipo.id_equipo)
        .where(
            Jugador.id_partida == equipo.id_partida,
            Jugador.categoria.in_(["PRIMERA", "SUB21"]),
            or_(Jugador.id_equipo.is_(None), Jugador.id_equipo != id_equipo),
            Jugador.posicion.in_(posiciones_prioritarias),
        )
    )).all()

    # Nivel general de cada club (overall promedio de toda su plantilla), para
    # no recomendar fichajes poco realistas: un jugador de un club bastante
    # mejor que el nuestro difícilmente se venga a jugar a un equipo peor.
    # `overall` es una @property calculada en Python (no una columna), así
    # que hace falta traer los objetos completos en vez de seleccionar la
    # columna directo.
    niveles_por_club: dict[int, list[int]] = {}
    jugadores_para_nivel = (await db.execute(
        select(Jugador).where(
            Jugador.id_partida == equipo.id_partida,
            Jugador.id_equipo.is_not(None),
            Jugador.categoria == "PRIMERA",
        )
    )).scalars().all()
    for jn in jugadores_para_nivel:
        niveles_por_club.setdefault(jn.id_equipo, []).append(jn.overall)
    nivel_club = {id_eq: sum(ovs) / len(ovs) for id_eq, ovs in niveles_por_club.items()}
    nivel_propio = nivel_club.get(id_equipo, 0)

    # Umbral de realismo: si el club actual del candidato promedia más de
    # esto por encima de nuestro nivel, ni se lo considera — un jugador de
    # un club claramente mejor no vendría a jugar peor (un agente libre no
    # tiene club, así que no se lo penaliza ni excluye por esto).
    DIFERENCIA_NIVEL_MAXIMA = 20.0

    fecha = await _fecha_actual(db, equipo.id_partida)
    candidatos = []
    candidatos_orm: dict[int, Jugador] = {}
    for j, nombre_club in filas:
        promedio_pos = promedios[j.posicion]
        margen = j.overall - promedio_pos
        if margen <= 0:
            continue
        # Si el club actual del candidato es mejor que el nuestro, cuanto
        # mayor la diferencia menos realista el fichaje.
        diferencia_nivel = max(0.0, nivel_club.get(j.id_equipo, nivel_propio) - nivel_propio) if j.id_equipo else 0.0
        if diferencia_nivel > DIFERENCIA_NIVEL_MAXIMA:
            continue
        rank = posiciones_ordenadas.index(j.posicion)  # 0 = la posición más floja del equipo
        asequible = equipo.presupuesto_fichajes >= j.valor_mercado

        # Puntaje crudo para ORDENAR candidatos entre sí y elegir el lote a
        # mostrar (favorece necesidad/edad/potencial/realismo, igual que
        # antes) — la prioridad que se muestra al usuario, en cambio, es una
        # escala ABSOLUTA (ver más abajo), no depende de quién más aparezca
        # en este lote.
        puntaje_crudo = (
            margen * 2
            + (2 - rank) * 5
            + (8 if asequible else -15)
            + (3 if j.edad <= 23 else 1 if j.edad <= 27 else 0)
            + (j.potencial - j.overall) * 0.3
            - diferencia_nivel * 1.5
        )

        # Prioridad 1-10 ABSOLUTA, proporcional al nivel del propio equipo:
        # ya pasó el filtro de "es mejor que el promedio de tu plantel en esa
        # posición" y de realismo de nivel, así que como recomendación que es
        # el piso es 6 (nunca un número bajo que dé a entender que no vale la
        # pena) — de ahí escala hasta 10 según qué tan grande es la mejora,
        # qué tan urgente es la posición, edad/potencial, y si es realista y
        # accesible.
        calidad = (
            min(1.0, margen / 20) * 0.30
            + (1.0 if rank == 0 else 0.6 if rank == 1 else 0.3) * 0.15
            + (1.0 if j.edad <= 23 else 0.6 if j.edad <= 27 else 0.3) * 0.10
            + min(1.0, max(0.0, (j.potencial - j.overall) / 15)) * 0.15
            + max(0.0, 1 - diferencia_nivel / DIFERENCIA_NIVEL_MAXIMA) * 0.20
            + (1.0 if asequible else 0.3) * 0.10
        )

        dias_restantes = (j.fecha_fin_contrato - fecha).days if j.fecha_fin_contrato else None
        candidatos_orm[j.id_jugador] = j
        candidatos.append({
            "id_jugador": j.id_jugador, "nombre": j.nombre, "posicion": j.posicion, "posicion_especifica": j.posicion_especifica,
            "edad": j.edad, "overall": j.overall, "potencial": j.potencial,
            "club": nombre_club or "Agente Libre", "id_equipo": j.id_equipo, "es_libre": j.id_equipo is None,
            "valor_mercado": j.valor_mercado, "salario": j.salario, "asequible": asequible,
            "fecha_fin_contrato": j.fecha_fin_contrato.isoformat() if j.fecha_fin_contrato else None,
            "dias_restantes_contrato": dias_restantes,
            "elegible_precontrato": dias_restantes is not None and 0 < dias_restantes <= DIAS_ELEGIBLE_PRECONTRATO,
            "id_equipo_precontrato": j.id_equipo_precontrato,
            "prioridad": max(6, min(10, round(6 + calidad * 4))),
            "_puntaje_crudo": puntaje_crudo,
        })
    candidatos.sort(key=lambda c: -c["_puntaje_crudo"])
    candidatos = candidatos[:15]

    recomendaciones = []
    for c in candidatos:
        del c["_puntaje_crudo"]
        recomendaciones.append(c)

    # Estos candidatos son siempre ajenos (la query los excluye explícitamente
    # del plantel propio más arriba) — se les aplica fog de scouting.
    reportes = await _reportes_de(db, id_equipo, [c["id_jugador"] for c in recomendaciones])
    for c in recomendaciones:
        _aplicar_fog(c, candidatos_orm[c["id_jugador"]], reportes.get(c["id_jugador"]))

    oportunidades_salida = []
    for j in plantel:
        if j.rol not in ("SUPLENTE", "RESERVA"):
            continue
        promedio_pos = promedios.get(j.posicion, 0)
        if not (j.overall <= promedio_pos or j.edad >= 30 or j.rol == "RESERVA"):
            continue
        oportunidades_salida.append({
            "id_jugador": j.id_jugador, "nombre": j.nombre, "posicion": j.posicion, "posicion_especifica": j.posicion_especifica,
            "edad": j.edad, "overall": j.overall, "valor_mercado": j.valor_mercado, "rol": j.rol,
        })
    oportunidades_salida.sort(key=lambda c: c["overall"])

    return {
        "promedios_por_posicion": promedios,
        "posicion_prioritaria": posiciones_ordenadas[0] if posiciones_ordenadas else None,
        "recomendaciones": recomendaciones,
        "oportunidades_salida": oportunidades_salida[:10],
    }


@router.post("/fichajes/ofrecer", tags=["Transferencias"])
async def ofrecer_jugador(datos: OfrecerJugadorIn, db: AsyncSession = Depends(get_db)):
    """El usuario sale a ofrecer un jugador propio. Cada club destinatario
    evalúa por su cuenta (necesidad de esa posición + presupuesto + un
    poco de azar) si le hace una oferta o no — la IA puede decir que no."""
    jugador = await db.get(Jugador, datos.id_jugador)
    if not jugador or not jugador.id_equipo:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    vendedor = await db.get(Equipo, jugador.id_equipo)

    if datos.id_equipos:
        destinatarios = (await db.execute(
            select(Equipo).where(Equipo.id_equipo.in_(datos.id_equipos), Equipo.id_partida == jugador.id_partida)
        )).scalars().all()
    else:
        destinatarios = (await db.execute(
            select(Equipo).where(Equipo.id_partida == jugador.id_partida, Equipo.es_usuario.is_(False))
        )).scalars().all()
    destinatarios = [c for c in destinatarios if c.id_equipo != vendedor.id_equipo]

    MAX_OFERTAS_POR_INTENTO = 5  # aunque "interesen" varios clubes, no todos se mueven el mismo día

    fecha = await _fecha_actual(db, jugador.id_partida)

    # Todo lo que hace falta se trae de una sola vez, en vez de ida-y-vuelta
    # por cada club (con 80 equipos eso eran ~160 consultas y varios segundos).
    ids_destinatarios = [c.id_equipo for c in destinatarios]
    todos_jugadores = (await db.execute(
        select(Jugador).where(Jugador.id_equipo.in_(ids_destinatarios), Jugador.categoria == "PRIMERA")
    )).scalars().all() if ids_destinatarios else []
    plantel_por_equipo: dict[int, list[Jugador]] = {}
    for j in todos_jugadores:
        plantel_por_equipo.setdefault(j.id_equipo, []).append(j)

    compradores_con_pendiente = set((await db.execute(
        select(OfertaFichaje.id_equipo_comprador).where(
            OfertaFichaje.id_jugador == jugador.id_jugador,
            OfertaFichaje.estado == "PENDIENTE",
        )
    )).scalars().all())

    interesados = []
    sin_interes = []

    for club in destinatarios:
        plantel_club = plantel_por_equipo.get(club.id_equipo, [])
        promedios_club = _promedios_por_posicion(plantel_club)
        promedio_pos = promedios_club.get(jugador.posicion, 0)
        encaja = jugador.overall > promedio_pos

        if jugador.valor_mercado > club.presupuesto_fichajes * 1.1:
            sin_interes.append({"id_equipo": club.id_equipo, "nombre": club.nombre, "motivo": "Presupuesto insuficiente"})
            continue

        # Probabilidad de que la IA se interese: más alta si el jugador
        # mejora esa posición, más baja si ya están cubiertos ahí.
        prob = 0.35 if encaja else 0.06
        if random.random() > prob:
            sin_interes.append({"id_equipo": club.id_equipo, "nombre": club.nombre, "motivo": "No le interesó por ahora"})
            continue

        if club.id_equipo in compradores_con_pendiente:
            continue

        oferta_monto = round(jugador.valor_mercado * random.randint(80, 105) / 100 / 10_000) * 10_000
        oferta_monto = min(oferta_monto, club.presupuesto_fichajes)
        if oferta_monto <= 0:
            sin_interes.append({"id_equipo": club.id_equipo, "nombre": club.nombre, "motivo": "Presupuesto insuficiente"})
            continue

        interesados.append({"club": club, "monto": oferta_monto})

    # De los interesados, solo una manija concreta llega a ofertar en firme
    # el mismo día — el resto queda "con la duda" para otro momento.
    random.shuffle(interesados)
    a_ofertar, resto = interesados[:MAX_OFERTAS_POR_INTENTO], interesados[MAX_OFERTAS_POR_INTENTO:]
    for r in resto:
        sin_interes.append({"id_equipo": r["club"].id_equipo, "nombre": r["club"].nombre, "motivo": "Le interesa pero no se decidió a ofertar todavía"})

    ofertas_recibidas = []
    for item in a_ofertar:
        club, oferta_monto = item["club"], item["monto"]
        oferta = OfertaFichaje(
            id_jugador=jugador.id_jugador, id_equipo_comprador=club.id_equipo,
            id_equipo_vendedor=vendedor.id_equipo, monto_oferta=oferta_monto,
            salario_pactado=salario_esperado(jugador.valor_mercado, jugador.edad),
            estado="PENDIENTE",
        )
        db.add(oferta)
        await db.flush()
        await _crear_mensaje(
            db, vendedor.id_equipo, "Mercado de Pases", f"Oferta recibida por {jugador.nombre}",
            f"Ofreciste a {jugador.nombre} y {club.nombre} respondió con ${money(oferta_monto)}. Podés aceptarla o rechazarla desde tu bandeja.",
            "MERCADO", fecha, id_oferta=oferta.id_oferta,
        )
        ofertas_recibidas.append({"id_equipo": club.id_equipo, "nombre": club.nombre, "monto_oferta": oferta_monto})

    await db.commit()
    return {
        "jugador": jugador.nombre,
        "ofertas_recibidas": ofertas_recibidas,
        "sin_interes": sin_interes,
        "mensaje": (
            f"{len(ofertas_recibidas)} club(es) hicieron una oferta por {jugador.nombre}."
            if ofertas_recibidas else f"Ningún club mostró interés por {jugador.nombre} en este intento."
        ),
    }


@router.post("/fichajes/ceder", tags=["Transferencias"])
async def ceder_jugador(datos: CederJugadorIn, db: AsyncSession = Depends(get_db)):
    """El usuario ofrece un jugador propio a préstamo (6 o 12 meses, con
    opción de compra negociable y opcional). Un préstamo solo puede tener
    un destino, así que se consulta a los candidatos hasta que uno acepta
    (o ninguno lo hace) — la IA puede rechazarlo si no lo necesita."""
    if datos.duracion_meses not in DURACIONES_CESION_VALIDAS:
        raise HTTPException(status_code=400, detail="La duración de la cesión debe ser 6 o 12 meses")

    jugador = await db.get(Jugador, datos.id_jugador)
    if not jugador or not jugador.id_equipo:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    if jugador.id_equipo_dueno is not None:
        raise HTTPException(status_code=400, detail="Ese jugador ya está cedido a préstamo en otro club")
    dueno = await db.get(Equipo, jugador.id_equipo)

    if datos.id_equipos:
        destinatarios = (await db.execute(
            select(Equipo).where(Equipo.id_equipo.in_(datos.id_equipos), Equipo.id_partida == jugador.id_partida)
        )).scalars().all()
    else:
        destinatarios = (await db.execute(
            select(Equipo).where(Equipo.id_partida == jugador.id_partida, Equipo.es_usuario.is_(False))
        )).scalars().all()
    destinatarios = [c for c in destinatarios if c.id_equipo != dueno.id_equipo]
    random.shuffle(destinatarios)

    ids_destinatarios = [c.id_equipo for c in destinatarios]
    todos_jugadores = (await db.execute(
        select(Jugador).where(Jugador.id_equipo.in_(ids_destinatarios), Jugador.categoria == "PRIMERA")
    )).scalars().all() if ids_destinatarios else []
    plantel_por_equipo: dict[int, list[Jugador]] = {}
    for j in todos_jugadores:
        plantel_por_equipo.setdefault(j.id_equipo, []).append(j)

    fecha = await _fecha_actual(db, jugador.id_partida)
    sin_interes = []
    club_aceptante = None

    for club in destinatarios:
        plantel_club = plantel_por_equipo.get(club.id_equipo, [])
        promedios_club = _promedios_por_posicion(plantel_club)
        promedio_pos = promedios_club.get(jugador.posicion, 0)
        encaja = jugador.overall > promedio_pos

        margen_salario = club.presupuesto_salarios - sum(j.salario for j in plantel_club)
        if margen_salario < jugador.salario:
            sin_interes.append({"id_equipo": club.id_equipo, "nombre": club.nombre, "motivo": "No le entra en la masa salarial"})
            continue

        # Un préstamo compromete menos que una compra: la IA es bastante
        # más receptiva que ante una venta definitiva.
        prob = 0.45 if encaja else 0.08
        if random.random() > prob:
            sin_interes.append({"id_equipo": club.id_equipo, "nombre": club.nombre, "motivo": "No le interesó por ahora"})
            continue

        club_aceptante = club
        break

    if not club_aceptante:
        return {
            "jugador": jugador.nombre,
            "aceptado": False,
            "sin_interes": sin_interes,
            "mensaje": f"Ningún club se mostró interesado en llevarse a {jugador.nombre} a préstamo por ahora.",
        }

    _aplicar_cesion(jugador, dueno, club_aceptante, datos.duracion_meses, datos.opcion_compra, fecha)

    texto_opcion = f" con opción de compra por ${money(datos.opcion_compra)}" if datos.opcion_compra else ""
    await _crear_mensaje(
        db, dueno.id_equipo, "Secretaría Técnica", f"Cesión acordada: {jugador.nombre}",
        f"{club_aceptante.nombre} se lleva a {jugador.nombre} a préstamo por {datos.duracion_meses} meses{texto_opcion}. "
        f"Vuelve el {jugador.fin_cesion.strftime('%d/%m/%Y')} si no ejercen la compra.",
        "MERCADO", fecha,
    )

    await db.commit()
    return {
        "jugador": jugador.nombre,
        "aceptado": True,
        "club": club_aceptante.nombre,
        "fin_cesion": jugador.fin_cesion.isoformat(),
        "sin_interes": sin_interes,
        "mensaje": f"{club_aceptante.nombre} se lleva a {jugador.nombre} a préstamo por {datos.duracion_meses} meses{texto_opcion}.",
    }


async def _registrar_negociacion(datos, fase, resolver, db):
    jugador = await db.get(Jugador, datos.id_jugador)
    equipo = await db.get(Equipo, datos.id_equipo_comprador)
    if not jugador or not equipo or jugador.id_partida != equipo.id_partida:
        raise HTTPException(400, 'Jugador y club deben pertenecer a la misma carrera')
    resultado = await resolver(datos, db)
    detalle = {'fase': fase, 'monto': datos.monto_oferta if fase == 'precio' else datos.salario_ofrecido,
               'monto_acordado': resultado.get('monto_acordado'), 'id_vendedor': jugador.id_equipo,
               'estado': resultado.get('estado'), 'mensaje': resultado.get('mensaje', 'El club acepta el precio.'),
               'condiciones': datos.model_dump()}
    db.add(HistorialNegociacion(id_jugador=datos.id_jugador, id_equipo=datos.id_equipo_comprador,
                               detalle_json=json.dumps(detalle, ensure_ascii=False)))
    await db.commit()
    return resultado


@router.post('/fichajes/ofertar', tags=['Transferencias'])
async def ofertar_fichaje(datos: OfertaIn, db: AsyncSession = Depends(get_db)):
    return await _registrar_negociacion(datos, 'precio', _resolver_oferta_fichaje, db)


@router.post('/fichajes/negociar-contrato', tags=['Transferencias'])
async def negociar_contrato_traspaso(datos: NegociarContratoTraspasoIn, db: AsyncSession = Depends(get_db)):
    return await _registrar_negociacion(datos, 'contrato', _resolver_contrato_traspaso, db)


@router.get('/fichajes/historial/{id_jugador}', tags=['Transferencias'])
async def historial_negociacion(id_jugador: int, id_equipo: int, db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(HistorialNegociacion).where(
        HistorialNegociacion.id_jugador == id_jugador, HistorialNegociacion.id_equipo == id_equipo
    ).order_by(HistorialNegociacion.id.desc()).limit(50))).all()
    return [json.loads(row.detalle_json) for row in reversed(rows)]
