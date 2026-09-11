from fastapi import APIRouter
from api.runtime import (
    AsyncSession,
    Calendario,
    Depends,
    HTTPException,
    Mensaje,
    Partida,
    _cerrar_jornada_del_dia,
    _efectivizar_ofertas_pendientes,
    _equipo_usuario,
    _jugar_fixture,
    _procesar_arranques_diferidos,
    _procesar_cesiones,
    _procesar_contratos,
    _procesar_entrenamiento_individual,
    _procesar_informe_academia,
    _procesar_informe_direccion_deportiva,
    _procesar_prensa_y_vestuario,
    _procesar_bitacora_documental,
    _procesar_partidos_ajenos_del_dia,
    _procesar_partidos_selecciones,
    _procesar_oportunidades_multiclub,
    _procesar_ventanas_internacionales,
    _procesar_progreso_scouting,
    _procesar_relaciones_plantel,
    _procesar_solicitudes_participacion,
    date,
    get_db,
    or_,
    select,
    timedelta,
    update,
    ventana_activa
)

router = APIRouter()

@router.get("/juego/estado", tags=["Panel"])
async def obtener_estado_juego(id_partida: int, db: AsyncSession = Depends(get_db)):
    partida = await db.get(Partida, id_partida)
    fecha = partida.fecha_actual if partida else date.today()
    return {
        "fecha_actual": fecha.isoformat(),
        "ventana_mercado": ventana_activa(fecha),
        "objetivo_temporada": partida.objetivo_temporada if partida else None,
        "contrato_dt_anios": partida.contrato_dt_anios if partida else None,
        "contrato_dt_fecha_fin": partida.contrato_dt_fecha_fin.isoformat() if partida and partida.contrato_dt_fecha_fin else None,
    }


@router.post("/juego/avanzar-dia", tags=["Panel"])
async def avanzar_dia(id_partida: int, db: AsyncSession = Depends(get_db)):
    estado = await db.get(Partida, id_partida)
    if not estado:
        raise HTTPException(status_code=404, detail="Carrera no encontrada")

    # Validación real (no solo del lado del frontend): si el equipo del
    # usuario tiene un partido de hoy o de una fecha ya pasada sin jugar,
    # no se puede seguir avanzando — si no, el día sigue corriendo y el
    # partido queda "perdido" sin haberse disputado nunca.
    equipo_usuario = await _equipo_usuario(db, id_partida)
    if equipo_usuario:
        pendiente_atrasado = (await db.execute(
            select(Calendario).where(
                or_(Calendario.id_local == equipo_usuario.id_equipo, Calendario.id_visitante == equipo_usuario.id_equipo),
                Calendario.jugado.is_(False),
                Calendario.fecha <= estado.fecha_actual,
            )
        )).scalars().first()
        if pendiente_atrasado:
            raise HTTPException(status_code=400, detail="Tenés un partido pendiente por jugar antes de poder continuar.")

    estado.fecha_actual += timedelta(days=1)
    await _efectivizar_ofertas_pendientes(db, estado.fecha_actual, id_partida)
    await _procesar_contratos(db, estado.fecha_actual, id_partida)
    await _procesar_cesiones(db, estado.fecha_actual, id_partida)
    await _procesar_ventanas_internacionales(db, estado.fecha_actual, id_partida)
    await _procesar_partidos_selecciones(db, estado.fecha_actual, id_partida)
    await _procesar_relaciones_plantel(db, estado.fecha_actual, id_partida)
    await _procesar_oportunidades_multiclub(db, estado.fecha_actual, id_partida)
    await _procesar_informe_academia(db, estado.fecha_actual, id_partida)
    await _procesar_informe_direccion_deportiva(db, estado.fecha_actual, id_partida)
    await _procesar_prensa_y_vestuario(db, estado.fecha_actual, id_partida)
    await _procesar_bitacora_documental(db, estado.fecha_actual, id_partida)
    await _procesar_progreso_scouting(db, estado.fecha_actual, id_partida)
    await _procesar_entrenamiento_individual(db, estado.fecha_actual, id_partida)
    await _procesar_solicitudes_participacion(db, estado.fecha_actual, id_partida)
    await _procesar_arranques_diferidos(db, estado.fecha_actual, id_partida)
    await _procesar_partidos_ajenos_del_dia(db, estado.fecha_actual, id_partida, equipo_usuario)
    await db.commit()
    return {"fecha_actual": estado.fecha_actual.isoformat(), "ventana_mercado": ventana_activa(estado.fecha_actual)}


@router.post("/juego/simular-hasta", tags=["Panel"])
async def simular_hasta(id_partida: int, datos: dict, db: AsyncSession = Depends(get_db)):
    """Como avanzar-dia, pero repetido hasta llegar a `fecha_objetivo`. Si en
    el camino aparece un partido del usuario, se resuelve con simulación
    rápida automáticamente (para no quedar trabado) y se informa en la
    respuesta — así se puede saltar, por ejemplo, hasta que abra la próxima
    ventana de mercado sin tener que ir tocando "Continuar" un día a la vez."""
    fecha_objetivo = date.fromisoformat(datos["fecha_objetivo"])
    estado = await db.get(Partida, id_partida)
    if not estado:
        raise HTTPException(status_code=400, detail="Todavía no arrancó la partida.")
    if fecha_objetivo <= estado.fecha_actual:
        raise HTTPException(status_code=400, detail="Elegí una fecha posterior a la actual.")

    equipo_usuario = await _equipo_usuario(db, id_partida)
    partidos_jugados: list[dict] = []
    mercado_ia_total: list[str] = []
    nueva_temporada_alguna = False

    MAX_ITERACIONES = 1500  # salvaguarda: no debería hacer falta ni para varias temporadas
    for _ in range(MAX_ITERACIONES):
        if estado.fecha_actual >= fecha_objetivo:
            break

        pendiente = None
        if equipo_usuario:
            pendiente = (await db.execute(
                select(Calendario).where(
                    or_(Calendario.id_local == equipo_usuario.id_equipo, Calendario.id_visitante == equipo_usuario.id_equipo),
                    Calendario.jugado.is_(False),
                    Calendario.fecha <= estado.fecha_actual,
                )
            )).scalars().first()

        if pendiente:
            resultado = await _jugar_fixture(db, pendiente)
            mercado_ia, nueva_temporada = await _cerrar_jornada_del_dia(db, pendiente)
            mercado_ia_total.extend(mercado_ia)
            nueva_temporada_alguna = nueva_temporada_alguna or nueva_temporada
            partidos_jugados.append({
                "fecha": pendiente.fecha.isoformat(),
                "nombre_local": resultado["nombre_local"], "nombre_visitante": resultado["nombre_visitante"],
                "goles_local": resultado["goles_local"], "goles_visitante": resultado["goles_visitante"],
            })
            continue

        estado.fecha_actual += timedelta(days=1)
        await _efectivizar_ofertas_pendientes(db, estado.fecha_actual, id_partida)
        await _procesar_contratos(db, estado.fecha_actual, id_partida)
        await _procesar_cesiones(db, estado.fecha_actual, id_partida)
        await _procesar_ventanas_internacionales(db, estado.fecha_actual, id_partida)
        await _procesar_partidos_selecciones(db, estado.fecha_actual, id_partida)
        await _procesar_relaciones_plantel(db, estado.fecha_actual, id_partida)
        await _procesar_oportunidades_multiclub(db, estado.fecha_actual, id_partida)
        await _procesar_informe_academia(db, estado.fecha_actual, id_partida)
        await _procesar_informe_direccion_deportiva(db, estado.fecha_actual, id_partida)
        await _procesar_prensa_y_vestuario(db, estado.fecha_actual, id_partida)
        await _procesar_bitacora_documental(db, estado.fecha_actual, id_partida)
        await _procesar_progreso_scouting(db, estado.fecha_actual, id_partida)
        await _procesar_entrenamiento_individual(db, estado.fecha_actual, id_partida)
        await _procesar_solicitudes_participacion(db, estado.fecha_actual, id_partida)
        await _procesar_arranques_diferidos(db, estado.fecha_actual, id_partida)
        await _procesar_partidos_ajenos_del_dia(db, estado.fecha_actual, id_partida, equipo_usuario)
    else:
        raise HTTPException(status_code=500, detail="Se alcanzó el límite de días simulando de una — probá con una fecha más cercana.")

    await db.commit()
    return {
        "fecha_actual": estado.fecha_actual.isoformat(),
        "ventana_mercado": ventana_activa(estado.fecha_actual),
        "partidos_jugados": partidos_jugados,
        "mercado_ia": mercado_ia_total,
        "nueva_temporada": nueva_temporada_alguna,
    }


@router.get("/inbox", tags=["Panel"])
async def get_inbox(id_equipo: int | None = None, id_partida: int | None = None, db: AsyncSession = Depends(get_db)):
    if id_equipo is None:
        equipo = await _equipo_usuario(db, id_partida) if id_partida else None
        id_equipo = equipo.id_equipo if equipo else None

    result = await db.execute(
        select(Mensaje).where(Mensaje.id_equipo_destino == id_equipo).order_by(Mensaje.id_mensaje.desc())
    )
    mensajes = result.scalars().all()
    return {
        "emails": [
            {
                "id": m.id_mensaje, "remitente": m.remitente, "asunto": m.asunto,
                "contenido": m.contenido, "fecha": m.fecha.isoformat(), "leido": m.leido,
                "tipo": m.tipo, "id_oferta": m.id_oferta,
            }
            for m in mensajes
        ]
    }


@router.post("/inbox/{id_mensaje}/leido", tags=["Panel"])
async def marcar_leido(id_mensaje: int, db: AsyncSession = Depends(get_db)):
    mensaje = await db.get(Mensaje, id_mensaje)
    if not mensaje:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    mensaje.leido = True
    await db.commit()
    return {"status": "ok"}


@router.post("/inbox/marcar-todo-leido", tags=["Panel"])
async def marcar_todo_leido(id_equipo: int, db: AsyncSession = Depends(get_db)):
    await db.execute(
        update(Mensaje).where(Mensaje.id_equipo_destino == id_equipo, Mensaje.leido.is_(False)).values(leido=True)
    )
    await db.commit()
    return {"status": "ok"}
