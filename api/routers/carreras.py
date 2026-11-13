from fastapi import APIRouter
from api.runtime import (
    AddOnTransferencia,
    AfiliacionClub,
    AsyncSession,
    Calendario,
    CicloTemporada,
    ConvocatoriaSeleccion,
    Depends,
    EXTENSIONES_ESCUDO_VALIDAS,
    Equipo,
    ElegibilidadSeleccion,
    EventoPartido,
    File,
    HTTPException,
    HistorialTemporada,
    Jugador,
    Liga,
    Mensaje,
    OfertaClubDT,
    OfertaFichaje,
    Ojeador,
    PaqueteClubes,
    Partida,
    PersonalTecnico,
    PartidoSeleccion,
    PlanEntrenamiento,
    ReporteScouting,
    SolicitudParticipacion,
    Seleccion,
    TAMANO_MAXIMO_ESCUDO,
    Tactica,
    TorneoSeleccion,
    UploadFile,
    VentanaInternacional,
    _equipo_usuario,
    _guardar_bytes_escudo,
    _validar_datos_pack,
    delete,
    func,
    get_db,
    json,
    os,
    select
)

router = APIRouter()

@router.post("/escudos/subir", tags=["Carreras"])
async def subir_escudo(archivo: UploadFile = File(...)):
    """Sube una imagen de escudo elegida por el propio usuario y devuelve una
    URL servida por este backend — mismo rol que ESCUDO_URL en el CSV de
    paquetes (ver Editor), pero sin depender de que tenga hosting externo.
    Nunca acepta ni reutiliza datos de otro juego con licencia."""
    extension = os.path.splitext(archivo.filename or "")[1].lower()
    if extension not in EXTENSIONES_ESCUDO_VALIDAS:
        raise HTTPException(status_code=400, detail=f"Formato no soportado ({extension or 'sin extensión'}). Usá PNG, JPG, WEBP o SVG.")
    contenido = await archivo.read()
    if len(contenido) > TAMANO_MAXIMO_ESCUDO:
        raise HTTPException(status_code=400, detail="La imagen no puede pesar más de 2 MB.")
    return {"url": _guardar_bytes_escudo(contenido, extension)}


@router.get("/catalogo/clubes", tags=["Carreras"])
async def catalogo_clubes(dataset: str = "ficticia"):
    from engine.data_gen import LIGAS, CLUB_NAMES, CONFEDERACION
    return {
        "ligas": [
            {
                "codigo": codigo, "pais": info["pais"], "nombre": info["nombre"],
                "confederacion": CONFEDERACION[codigo],
                "clubes": [f"{cc} - {nc}" for cc, nc in CLUB_NAMES[codigo]],
            }
            for codigo, info in LIGAS.items()
        ]
    }


@router.get("/partidas", tags=["Carreras"])
async def listar_partidas(dataset: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(Partida).order_by(Partida.fecha_creacion.desc())
    if dataset:
        query = query.where(Partida.dataset == dataset)
    partidas = (await db.execute(query)).scalars().all()

    ids = [p.id_partida for p in partidas]
    equipos_usuario = {}
    cant_clubes: dict[int, int] = {}
    cant_jugadores: dict[int, int] = {}
    if ids:
        equipos = (await db.execute(
            select(Equipo).where(Equipo.id_partida.in_(ids), Equipo.es_usuario.is_(True))
        )).scalars().all()
        equipos_usuario = {e.id_partida: e.nombre for e in equipos}

        # Manifiesto liviano de cada carrera (cuántos clubes/jugadores tiene)
        # para poder mostrarlo en la hoja de ruta sin traer toda la carrera.
        for id_p, cant in (await db.execute(
            select(Equipo.id_partida, func.count(Equipo.id_equipo)).where(Equipo.id_partida.in_(ids)).group_by(Equipo.id_partida)
        )).all():
            cant_clubes[id_p] = cant
        for id_p, cant in (await db.execute(
            select(Jugador.id_partida, func.count(Jugador.id_jugador)).where(Jugador.id_partida.in_(ids)).group_by(Jugador.id_partida)
        )).all():
            cant_jugadores[id_p] = cant

    return [
        {
            "id_partida": p.id_partida, "nombre_dt": p.nombre_dt, "dataset": p.dataset,
            "nombre_equipo": equipos_usuario.get(p.id_partida, "?"),
            "fecha_actual": p.fecha_actual.isoformat(),
            "fecha_creacion": p.fecha_creacion.isoformat(),
            "cantidad_clubes": cant_clubes.get(p.id_partida, 0),
            "cantidad_jugadores": cant_jugadores.get(p.id_partida, 0),
        }
        for p in partidas
    ]


@router.delete("/partidas/{id_partida}", tags=["Carreras"])
async def borrar_partida(id_partida: int, db: AsyncSession = Depends(get_db)):
    """Borra una carrera completa y todo lo que cuelga de ella. Se hace a
    mano (no con cascade de SQLAlchemy) porque la mayoría de las tablas se
    relacionan por `id_partida`/`id_equipo` sueltos, sin `relationship()`
    hasta Partida — hay que ir de las hojas hacia la raíz para no pisar
    ninguna FK."""
    partida = await db.get(Partida, id_partida)
    if not partida:
        raise HTTPException(status_code=404, detail="Carrera no encontrada")

    equipo_ids = (await db.execute(select(Equipo.id_equipo).where(Equipo.id_partida == id_partida))).scalars().all()
    jugador_ids = (await db.execute(select(Jugador.id_jugador).where(Jugador.id_partida == id_partida))).scalars().all()
    fixture_ids = (await db.execute(select(Calendario.id_fixture).where(Calendario.id_partida == id_partida))).scalars().all()
    seleccion_ids = (await db.execute(select(Seleccion.id_seleccion).where(Seleccion.id_partida == id_partida))).scalars().all()

    if fixture_ids:
        await db.execute(delete(EventoPartido).where(EventoPartido.id_fixture.in_(fixture_ids)))
    if equipo_ids:
        await db.execute(delete(Mensaje).where(Mensaje.id_equipo_destino.in_(equipo_ids)))
    if jugador_ids:
        await db.execute(delete(OfertaFichaje).where(OfertaFichaje.id_jugador.in_(jugador_ids)))
        await db.execute(delete(AddOnTransferencia).where(AddOnTransferencia.id_jugador.in_(jugador_ids)))
    # Selecciones y sus cruces tienen FK hacia jugadores, ventanas y torneos.
    # Se borran antes de planteles para que una carrera con PMPack pueda
    # eliminarse igual que una carrera ficticia.
    await db.execute(delete(PartidoSeleccion).where(PartidoSeleccion.id_partida == id_partida))
    if seleccion_ids:
        await db.execute(delete(ConvocatoriaSeleccion).where(ConvocatoriaSeleccion.id_seleccion.in_(seleccion_ids)))
        await db.execute(delete(ElegibilidadSeleccion).where(ElegibilidadSeleccion.id_seleccion.in_(seleccion_ids)))
        await db.execute(delete(Seleccion).where(Seleccion.id_seleccion.in_(seleccion_ids)))
    await db.execute(delete(TorneoSeleccion).where(TorneoSeleccion.id_partida == id_partida))
    await db.execute(delete(VentanaInternacional).where(VentanaInternacional.id_partida == id_partida))
    await db.execute(delete(HistorialTemporada).where(HistorialTemporada.id_partida == id_partida))
    if equipo_ids:
        await db.execute(delete(Tactica).where(Tactica.id_equipo.in_(equipo_ids)))
        await db.execute(delete(PlanEntrenamiento).where(PlanEntrenamiento.id_equipo.in_(equipo_ids)))
        await db.execute(delete(PersonalTecnico).where(PersonalTecnico.id_equipo.in_(equipo_ids)))
        await db.execute(delete(ReporteScouting).where(ReporteScouting.id_equipo.in_(equipo_ids)))
        await db.execute(delete(Ojeador).where(Ojeador.id_equipo.in_(equipo_ids)))
    await db.execute(delete(OfertaClubDT).where(OfertaClubDT.id_partida == id_partida))
    await db.execute(delete(AfiliacionClub).where(AfiliacionClub.id_partida == id_partida))
    await db.execute(delete(SolicitudParticipacion).where(SolicitudParticipacion.id_partida == id_partida))
    await db.execute(delete(Jugador).where(Jugador.id_partida == id_partida))
    await db.execute(delete(Calendario).where(Calendario.id_partida == id_partida))
    await db.execute(delete(Equipo).where(Equipo.id_partida == id_partida))
    await db.execute(delete(Liga).where(Liga.id_partida == id_partida))
    await db.execute(delete(CicloTemporada).where(CicloTemporada.id_partida == id_partida))
    await db.delete(partida)
    await db.commit()
    return {"status": "ok"}


@router.post("/partidas", tags=["Carreras"])
async def crear_partida_endpoint(datos: dict, db: AsyncSession = Depends(get_db)):
    """Crea una carrera nueva completa (4 ligas, 80 clubes, planteles,
    calendario). `datos`: {nombre_dt, dataset, codigo_liga (opcional),
    nombre_club (opcional, si no se pasa se randomiza), nombres_clubes_custom/
    jugadores_clubes_custom/competencias_custom (opcionales, dict) o
    id_paquete_clubes (opcional, reusa uno ya guardado)}."""
    from seed import crear_partida

    nombre_dt = (datos.get("nombre_dt") or "").strip() or "DT"
    dataset = datos.get("dataset") or "ficticia"

    nombres_custom = datos.get("nombres_clubes_custom")
    jugadores_custom = datos.get("jugadores_clubes_custom")
    competencias_custom = datos.get("competencias_custom")
    metadata_custom = datos.get("metadata_clubes_custom")
    configuracion_pack = datos.get("configuracion_pack") or {}
    id_paquete = datos.get("id_paquete_clubes")
    if id_paquete:
        try:
            id_paquete = int(id_paquete)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="ID de paquete inválido")
        paquete = await db.get(PaqueteClubes, id_paquete)
        if not paquete:
            raise HTTPException(status_code=404, detail="Paquete no encontrado")
        if paquete:
            if not nombres_custom:
                nombres_custom = json.loads(paquete.nombres_json)
            if not jugadores_custom and paquete.jugadores_json:
                jugadores_custom = json.loads(paquete.jugadores_json)
            if not competencias_custom and paquete.competencias_json:
                competencias_custom = json.loads(paquete.competencias_json)
            metadata_custom = json.loads(paquete.metadata_clubes_json) if paquete.metadata_clubes_json else None
            configuracion_pack = json.loads(paquete.configuracion_json) if paquete.configuracion_json else {}

    if nombres_custom:
        nombres_custom, jugadores_custom = _validar_datos_pack(nombres_custom, jugadores_custom)
    if not isinstance(configuracion_pack, dict):
        raise HTTPException(status_code=400, detail="Configuración de pack inválida")
    if configuracion_pack.get("solo_clubes_pack") and not nombres_custom:
        raise HTTPException(status_code=400, detail="El modo de datos reales requiere clubes en el pack")
    if configuracion_pack.get("solo_clubes_pack") and datos.get("codigo_liga") and datos["codigo_liga"] not in nombres_custom:
        raise HTTPException(status_code=400, detail="La liga elegida no está incluida en el pack")
    if configuracion_pack.get("rellenar_planteles") is False:
        incompletos = [fila[1] for liga, filas in (nombres_custom or {}).items() for fila in filas
                      if len((jugadores_custom or {}).get(liga, {}).get(fila[0], [])) < 11]
        if incompletos:
            raise HTTPException(status_code=400, detail=f"No se pueden crear planteles reales: {len(incompletos)} clubes tienen menos de 11 jugadores. Completá el pack; no se agregarán jugadores ficticios.")

    try:
        id_partida = await crear_partida(
            db, nombre_dt=nombre_dt, dataset=dataset,
            codigo_liga_elegida=datos.get("codigo_liga"),
            nombre_club_elegido=datos.get("nombre_club"),
            nombres_clubes_custom=nombres_custom,
            jugadores_clubes_custom=jugadores_custom,
            competencias_custom=competencias_custom,
            metadata_clubes_custom=metadata_custom,
            configuracion_pack=configuracion_pack,
            ligas_completas=datos.get("ligas_completas"),
        )
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="No se pudo crear la carrera. El servidor revirtió los cambios; probá de nuevo.",
        ) from exc
    partida = await db.get(Partida, id_partida)
    if id_paquete:
        partida.id_paquete_clubes = id_paquete
        await db.commit()
    equipo_usuario = await _equipo_usuario(db, id_partida)
    return {
        "id_partida": id_partida,
        "nombre_club": equipo_usuario.nombre if equipo_usuario else None,
        "objetivo_temporada": partida.objetivo_temporada,
        "contrato_dt_anios": partida.contrato_dt_anios,
        "contrato_dt_fecha_fin": partida.contrato_dt_fecha_fin.isoformat() if partida.contrato_dt_fecha_fin else None,
    }
