from fastapi import APIRouter
from api.runtime import (
    AsyncSession,
    CATEGORIAS_ACADEMIA,
    CategoriaJugadorIn,
    Depends,
    Equipo,
    HTTPException,
    IntakeDecidirIn,
    Jugador,
    JugadorOut,
    Liga,
    ReclutarJuvenilIn,
    _agrupar_por_categoria,
    _aplicar_fog,
    _asegurar_academia,
    _equipo_usuario,
    _fecha_actual,
    _jugador_desarrollo,
    _reportes_de,
    academia_engine,
    get_db,
    money,
    puede_mover_a_categoria,
    puede_reclutar,
    salario_esperado,
    select,
    timedelta,
    tope_salarial
)

router = APIRouter()

@router.get("/equipos/{id_equipo}/academia", tags=["Academia"])
async def obtener_academia(id_equipo: int, db: AsyncSession = Depends(get_db)):
    equipo = await db.get(Equipo, id_equipo)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    await _asegurar_academia(db, equipo)

    jugadores = (await db.execute(
        select(Jugador).where(Jugador.id_equipo == id_equipo, Jugador.categoria != "PRIMERA")
    )).scalars().all()

    equipo_usuario = None if equipo.es_usuario else await _equipo_usuario(db, equipo.id_partida)
    reportes = (
        await _reportes_de(db, equipo_usuario.id_equipo, [j.id_jugador for j in jugadores])
        if equipo_usuario else {}
    )

    grupos = _agrupar_por_categoria(jugadores)
    salida = {}
    for categoria, lista in grupos.items():
        filas = []
        for j in lista:
            base = JugadorOut.model_validate(j).model_dump(mode="json")
            if equipo_usuario:
                _aplicar_fog(base, j, reportes.get(j.id_jugador))
            filas.append(base)
        salida[categoria.lower()] = filas
    salida["nombre_equipo"] = equipo.nombre
    return salida


@router.post("/jugadores/{id_jugador}/categoria", tags=["Academia"])
async def mover_categoria_jugador(id_jugador: int, datos: CategoriaJugadorIn, db: AsyncSession = Depends(get_db)):
    jugador = await db.get(Jugador, id_jugador)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    if datos.categoria not in ("PRIMERA", *CATEGORIAS_ACADEMIA):
        raise HTTPException(status_code=400, detail="Categoría inválida")
    if not puede_mover_a_categoria(jugador.edad, datos.categoria):
        raise HTTPException(
            status_code=400,
            detail=f"{jugador.nombre} ({jugador.edad} años) no puede pasar a {datos.categoria}",
        )

    categoria_anterior = jugador.categoria
    jugador.categoria = datos.categoria
    if datos.categoria == "PRIMERA" and categoria_anterior != "PRIMERA" and jugador.fecha_fin_contrato is None:
        # Canterano puro ascendiendo por primera vez: nunca tuvo contrato, se le arma uno.
        fecha = await _fecha_actual(db, jugador.id_partida)
        jugador.salario = salario_esperado(jugador.valor_mercado, jugador.edad)
        jugador.fecha_fin_contrato = fecha + timedelta(days=365 * 3)
        jugador.rol = "RESERVA"

    await db.commit()
    return {"status": "ok", "id_jugador": id_jugador, "categoria": jugador.categoria}


@router.get("/equipos/{id_equipo}/academia/intake", tags=["Academia"])
async def obtener_intake_academia(id_equipo: int, db: AsyncSession = Depends(get_db)):
    candidatos = (await db.execute(
        select(Jugador).where(Jugador.id_equipo_intake == id_equipo, Jugador.id_equipo.is_(None))
    )).scalars().all()
    grupos = _agrupar_por_categoria(candidatos)
    return {c.lower(): [_jugador_desarrollo(j) for j in lista] for c, lista in grupos.items()}


@router.post("/jugadores/{id_jugador}/intake/decidir", tags=["Academia"])
async def decidir_intake_academia(id_jugador: int, datos: IntakeDecidirIn, db: AsyncSession = Depends(get_db)):
    jugador = await db.get(Jugador, id_jugador)
    if not jugador or jugador.id_equipo_intake is None or jugador.id_equipo is not None:
        raise HTTPException(status_code=404, detail="No hay ningún candidato de intake pendiente con ese id")

    if datos.aceptar:
        jugador.id_equipo = jugador.id_equipo_intake
        jugador.id_equipo_intake = None
        await db.commit()
        return {"status": "ok", "aceptado": True, "id_jugador": id_jugador}

    await db.delete(jugador)
    await db.commit()
    return {"status": "ok", "aceptado": False, "id_jugador": id_jugador}


@router.post("/jugadores/{id_jugador}/reclutar-juvenil", tags=["Academia"])
async def reclutar_juvenil(id_jugador: int, datos: ReclutarJuvenilIn, db: AsyncSession = Depends(get_db)):
    jugador = await db.get(Jugador, id_jugador)
    if not jugador or jugador.categoria == "PRIMERA" or jugador.id_equipo is None:
        raise HTTPException(status_code=404, detail="Jugador de Academia no encontrado en ningún club")

    destino = await db.get(Equipo, datos.id_equipo_destino)
    origen = await db.get(Equipo, jugador.id_equipo)
    if not destino or not origen:
        raise HTTPException(status_code=404, detail="Club no encontrado")
    if destino.id_equipo == origen.id_equipo:
        raise HTTPException(status_code=400, detail="El jugador ya es de ese club")
    if jugador.fecha_fin_contrato is not None:
        raise HTTPException(
            status_code=400,
            detail=f"{jugador.nombre} tiene contrato con {origen.nombre} — hay que negociar el fichaje, no se puede reclutar directo.",
        )

    liga_origen = await db.get(Liga, origen.id_liga)
    liga_destino = await db.get(Liga, destino.id_liga)
    pais_origen = liga_origen.pais if liga_origen else None
    pais_destino = liga_destino.pais if liga_destino else None
    if not puede_reclutar(jugador.edad, pais_origen, pais_destino):
        motivo = (
            "no se puede reclutar a un jugador menor a 15 años"
            if jugador.edad < academia_engine.EDAD_MINIMA_CONTRATO
            else f"la FIFA prohíbe transferencias internacionales de menores de 18 — {pais_origen} → {pais_destino}"
        )
        raise HTTPException(status_code=400, detail=f"No se puede reclutar a {jugador.nombre}: {motivo}")

    costo = round(jugador.valor_mercado * 0.2)
    if destino.presupuesto_fichajes < costo:
        raise HTTPException(status_code=400, detail=f"Presupuesto insuficiente (compensación por formación: ${money(costo)})")

    destino.presupuesto_fichajes -= costo
    origen.presupuesto_fichajes += costo
    destino.presupuesto_salarios = tope_salarial(destino.presupuesto_fichajes)
    origen.presupuesto_salarios = tope_salarial(origen.presupuesto_fichajes)
    jugador.id_equipo = destino.id_equipo

    await db.commit()
    return {"status": "ok", "id_jugador": id_jugador, "club": destino.nombre, "compensacion": costo}
