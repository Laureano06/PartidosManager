from fastapi import APIRouter
from api.runtime import (
    AsyncSession,
    Calendario,
    CharlaEquipoIn,
    Depends,
    HTTPException,
    Jugador,
    SimularJornadaIn,
    TONOS_CHARLA,
    _aplicar_efectos_fisicos,
    _aplicar_marcaje,
    _bono_red_equipo,
    _cerrar_jornada_del_dia,
    _crear_mensaje,
    _delta_charla,
    _efectivizar_ofertas_pendientes,
    _factor_medico,
    _fecha_actual,
    _finalizar_fixture,
    _jugar_fixture,
    _preparar_lineup,
    _procesar_addons_cumplidos,
    _procesar_fin_temporada_si_corresponde,
    aplicar_desgaste,
    ejecutar_ia_mercado,
    get_db,
    procesar_lesiones,
    select,
    simulate_match
)

router = APIRouter()

@router.post("/partidos/simular", tags=["Simulación"])
async def simular_partido(datos: dict, db: AsyncSession = Depends(get_db)):
    id_local = datos.get("id_local")
    id_visitante = datos.get("id_visitante")
    fixture = (await db.execute(
        select(Calendario).where(
            Calendario.id_local == id_local,
            Calendario.id_visitante == id_visitante,
            Calendario.jugado.is_(False),
        )
    )).scalars().first()
    if not fixture:
        raise HTTPException(status_code=404, detail="No hay un partido pendiente entre esos equipos.")

    resultado = await _jugar_fixture(db, fixture, datos.get("id_jugador_marcado"))
    resultado["mercado_ia"], resultado["nueva_temporada"] = await _cerrar_jornada_del_dia(db, fixture)
    await db.commit()
    return resultado


@router.post("/partidos/simular-primer-tiempo", tags=["Simulación"])
async def simular_primer_tiempo(datos: dict, db: AsyncSession = Depends(get_db)):
    id_local = datos.get("id_local")
    id_visitante = datos.get("id_visitante")
    fixture = (await db.execute(
        select(Calendario).where(
            Calendario.id_local == id_local,
            Calendario.id_visitante == id_visitante,
            Calendario.jugado.is_(False),
        )
    )).scalars().first()
    if not fixture:
        raise HTTPException(status_code=404, detail="No hay un partido pendiente entre esos equipos.")

    local, visit, plantel_local, plantel_visit, jl, jv, dict_local, dict_visit, tac_local_dict, tac_visit_dict = await _preparar_lineup(db, fixture)
    _aplicar_marcaje(dict_local, dict_visit, datos.get("id_jugador_marcado"))

    resultado = simulate_match(
        dict_local, dict_visit, tac_local_dict, tac_visit_dict,
        ia_local=not local.es_usuario, ia_visit=not visit.es_usuario,
        minuto_inicio=1, minuto_fin=45,
        factor_medico_local=_factor_medico(await _bono_red_equipo(db, local)),
        factor_medico_visit=_factor_medico(await _bono_red_equipo(db, visit)),
    )
    # El desgaste y las lesiones del primer tiempo se aplican ya mismo — así,
    # si hay que hacer cambios en el entretiempo, reflejan la realidad del
    # partido (un lesionado del primer tiempo no puede seguir jugando).
    jugadores_por_id = {p.id_jugador: p for p in jl + jv}
    aplicar_desgaste(jugadores_por_id, resultado["energia_gastada"])
    procesar_lesiones(jugadores_por_id, resultado["lesiones"])

    await db.commit()
    return {
        "id_local": fixture.id_local, "id_visitante": fixture.id_visitante,
        "nombre_local": local.nombre, "nombre_visitante": visit.nombre,
        "goles_local": resultado["gh"], "goles_visitante": resultado["gv"],
        "eventos": resultado["events"],
    }


@router.post("/partidos/simular-segundo-tiempo", tags=["Simulación"])
async def simular_segundo_tiempo(datos: dict, db: AsyncSession = Depends(get_db)):
    id_local = datos.get("id_local")
    id_visitante = datos.get("id_visitante")
    gh_medio = datos.get("goles_local", 0)
    gv_medio = datos.get("goles_visitante", 0)
    fixture = (await db.execute(
        select(Calendario).where(
            Calendario.id_local == id_local,
            Calendario.id_visitante == id_visitante,
            Calendario.jugado.is_(False),
        )
    )).scalars().first()
    if not fixture:
        raise HTTPException(status_code=404, detail="No hay un partido pendiente entre esos equipos.")

    # Se vuelve a armar la alineación acá — si el usuario hizo cambios en el
    # entretiempo (tácticas, titulares), el segundo tiempo ya sale con eso.
    local, visit, plantel_local, plantel_visit, jl, jv, dict_local, dict_visit, tac_local_dict, tac_visit_dict = await _preparar_lineup(db, fixture)
    _aplicar_marcaje(dict_local, dict_visit, datos.get("id_jugador_marcado"))

    fm_local = _factor_medico(await _bono_red_equipo(db, local))
    fm_visit = _factor_medico(await _bono_red_equipo(db, visit))
    resultado = simulate_match(
        dict_local, dict_visit, tac_local_dict, tac_visit_dict,
        ia_local=not local.es_usuario, ia_visit=not visit.es_usuario,
        minuto_inicio=46, minuto_fin=90, gh_inicial=gh_medio, gv_inicial=gv_medio,
        factor_medico_local=fm_local, factor_medico_visit=fm_visit,
    )

    _aplicar_efectos_fisicos(jl, jv, plantel_local, plantel_visit, resultado, fm_local, fm_visit)
    await _procesar_addons_cumplidos(db, {p.id_jugador for p in jl + jv}, fixture.fecha)
    await _finalizar_fixture(db, fixture, local, visit, resultado["gh"], resultado["gv"])
    log_ia, nueva_temporada = await _cerrar_jornada_del_dia(db, fixture)

    await db.commit()
    return {
        "id_local": fixture.id_local, "id_visitante": fixture.id_visitante,
        "nombre_local": local.nombre, "nombre_visitante": visit.nombre,
        "goles_local": resultado["gh"], "goles_visitante": resultado["gv"],
        "eventos": resultado["events"],
        "mercado_ia": log_ia,
        "nueva_temporada": nueva_temporada,
    }


@router.post("/partidos/charla", tags=["Simulación"])
async def charla_equipo(datos: CharlaEquipoIn, db: AsyncSession = Depends(get_db)):
    if datos.tono not in TONOS_CHARLA:
        raise HTTPException(status_code=400, detail=f"Tono inválido, debe ser uno de {sorted(TONOS_CHARLA)}.")
    fixture = await db.get(Calendario, datos.id_fixture)
    if not fixture:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    if not fixture.jugado:
        raise HTTPException(status_code=400, detail="Todavía no se jugó este partido.")
    if fixture.charla_dada:
        raise HTTPException(status_code=400, detail="Ya se le dio la charla post-partido a este equipo.")

    if fixture.id_local == datos.id_equipo:
        goles_propios, goles_rivales = fixture.goles_local, fixture.goles_visitante
    elif fixture.id_visitante == datos.id_equipo:
        goles_propios, goles_rivales = fixture.goles_visitante, fixture.goles_local
    else:
        raise HTTPException(status_code=400, detail="Ese equipo no jugó este partido.")

    resultado = "GANO" if goles_propios > goles_rivales else "PERDIO" if goles_propios < goles_rivales else "EMPATO"
    delta = _delta_charla(datos.tono, resultado)

    jugadores = (await db.execute(
        select(Jugador).where(Jugador.id_equipo == datos.id_equipo, Jugador.categoria == "PRIMERA")
    )).scalars().all()
    for j in jugadores:
        j.moral = max(0, min(100, j.moral + delta))

    fixture.charla_dada = True
    fecha = await _fecha_actual(db, fixture.id_partida)
    tono_texto = {"EFUSIVA": "efusiva", "CALMA": "calma", "EXIGENTE": "exigente"}[datos.tono]
    signo = "+" if delta >= 0 else ""
    await _crear_mensaje(
        db, datos.id_equipo, "Cuerpo Técnico", "Charla post-partido",
        f"Le diste una charla {tono_texto} al plantel — el efecto en la moral fue de {signo}{delta}.",
        "ENTRENAMIENTO", fecha,
    )
    await db.commit()
    return {"status": "ok", "delta": delta, "resultado": resultado}


@router.post("/jornada/simular", tags=["Simulación"])
async def simular_jornada(datos: SimularJornadaIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Calendario).where(
            Calendario.id_liga == datos.id_liga,
            Calendario.num_jornada == datos.num_jornada,
            Calendario.jugado.is_(False),
        )
    )
    fixtures = result.scalars().all()
    if not fixtures:
        return {"mensaje": "Esa jornada ya fue jugada o no existe."}

    id_partida = fixtures[0].id_partida
    resultados = [await _jugar_fixture(db, f) for f in fixtures]

    fecha = await _fecha_actual(db, id_partida)
    log_ia: list[str] = []
    await ejecutar_ia_mercado(db, log_ia, fecha, id_partida)
    await _efectivizar_ofertas_pendientes(db, fecha, id_partida)
    nueva_temporada = await _procesar_fin_temporada_si_corresponde(db, fecha, id_partida)

    await db.commit()
    return {"jornada": datos.num_jornada, "resultados": resultados, "mercado_ia": log_ia, "nueva_temporada": nueva_temporada}
