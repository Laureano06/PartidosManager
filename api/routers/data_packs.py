from fastapi import APIRouter
from api.runtime import (
    AsyncSession,
    DIRECTORIO_ESCUDOS,
    Depends,
    File,
    HTTPException,
    PAQUETE_BASE_FICTICIA,
    PaqueteClubes,
    Partida,
    Path,
    PmpackInvalido,
    Response,
    UploadFile,
    _guardar_bytes_escudo,
    _pack_ids_existentes,
    _resumen_paquete,
    _validar_datos_pack,
    datetime,
    get_db,
    json,
    pack_engine,
    select
)

router = APIRouter()

@router.get("/paquetes-clubes", tags=["Data Packs"])
async def listar_paquetes_clubes(db: AsyncSession = Depends(get_db)):
    """Base Ficticia (entrada sintética, no es una fila de PaqueteClubes)
    siempre primero, después PARTIDOS Real Data (si `fixtures_prueba/`
    existía al arrancar el backend — ver sembrar_partidos_real_data) y
    cualquier pack propio, más nuevo primero."""
    paquetes = (await db.execute(select(PaqueteClubes).order_by(PaqueteClubes.fecha_creacion.desc()))).scalars().all()
    return [PAQUETE_BASE_FICTICIA] + [_resumen_paquete(p) for p in paquetes]


@router.get("/paquetes-clubes/{id_paquete}", tags=["Data Packs"])
async def obtener_paquete_clubes(id_paquete: int, db: AsyncSession = Depends(get_db)):
    paquete = await db.get(PaqueteClubes, id_paquete)
    if not paquete:
        raise HTTPException(status_code=404, detail="Paquete no encontrado")
    return {
        **_resumen_paquete(paquete),
        "nombres_clubes": json.loads(paquete.nombres_json),
        "jugadores_clubes": json.loads(paquete.jugadores_json) if paquete.jugadores_json else None,
        "competencias": json.loads(paquete.competencias_json) if paquete.competencias_json else None,
        "metadata_clubes": json.loads(paquete.metadata_clubes_json) if paquete.metadata_clubes_json else None,
        "configuracion": json.loads(paquete.configuracion_json) if paquete.configuracion_json else {},
    }


@router.post("/paquetes-clubes", tags=["Data Packs"])
async def crear_paquete_clubes(datos: dict, db: AsyncSession = Depends(get_db)):
    """Guarda una lista de nombres/jugadores de club personalizados con un
    nombre propio, para poder reusarla en otra carrera sin volver a
    armarla — separado de cualquier carrera puntual, igual que un dataset
    editado por la comunidad se guarda aparte de los datos oficiales."""
    nombre = (datos.get("nombre") or "").strip()
    nombres_clubes = datos.get("nombres_clubes")
    jugadores_clubes = datos.get("jugadores_clubes")
    competencias = datos.get("competencias")
    if not nombre or not nombres_clubes:
        raise HTTPException(status_code=400, detail="Hace falta un nombre y al menos un club")
    nombres_clubes, jugadores_clubes = _validar_datos_pack(nombres_clubes, jugadores_clubes)
    ahora = datetime.utcnow()
    paquete = PaqueteClubes(
        pack_id=pack_engine.generar_pack_id(nombre, await _pack_ids_existentes(db)),
        nombre=nombre, version=(datos.get("version") or "1.0.0").strip(),
        autor=(datos.get("autor") or "").strip(), descripcion=(datos.get("descripcion") or "").strip(),
        nombres_json=json.dumps(nombres_clubes),
        jugadores_json=json.dumps(jugadores_clubes) if jugadores_clubes else None,
        competencias_json=json.dumps(competencias) if competencias else None,
        configuracion_json=json.dumps(datos.get("configuracion") or {}),
        fecha_creacion=ahora, fecha_actualizacion=ahora,
    )
    db.add(paquete)
    await db.commit()
    await db.refresh(paquete)
    return {"id_paquete": paquete.id_paquete}


@router.put("/paquetes-clubes/{id_paquete}", tags=["Data Packs"])
async def actualizar_paquete_clubes(id_paquete: int, datos: dict, db: AsyncSession = Depends(get_db)):
    """Reemplazo completo — usado por 'Competencias' del editor y por
    ediciones masivas. Protegido solo de BORRADO, no de edición: PARTIDOS
    Real Data se puede modificar como cualquier pack (ver es_oficial)."""
    paquete = await db.get(PaqueteClubes, id_paquete)
    if not paquete:
        raise HTTPException(status_code=404, detail="Paquete no encontrado")
    if "nombre" in datos and datos["nombre"].strip():
        paquete.nombre = datos["nombre"].strip()
    if "version" in datos:
        paquete.version = datos["version"].strip()
    if "autor" in datos:
        paquete.autor = datos["autor"].strip()
    if "descripcion" in datos:
        paquete.descripcion = datos["descripcion"].strip()
    if "nombres_clubes" in datos and datos["nombres_clubes"]:
        paquete.nombres_json = json.dumps(datos["nombres_clubes"])
    if "jugadores_clubes" in datos:
        paquete.jugadores_json = json.dumps(datos["jugadores_clubes"]) if datos["jugadores_clubes"] else None
    nombres, jugadores = _validar_datos_pack(json.loads(paquete.nombres_json), json.loads(paquete.jugadores_json) if paquete.jugadores_json else None)
    paquete.nombres_json = json.dumps(nombres)
    paquete.jugadores_json = json.dumps(jugadores) if jugadores else None
    if "competencias" in datos:
        paquete.competencias_json = json.dumps(datos["competencias"]) if datos["competencias"] else None
    if "metadata_clubes" in datos:
        paquete.metadata_clubes_json = json.dumps(datos["metadata_clubes"]) if datos["metadata_clubes"] else None
    if "configuracion" in datos:
        paquete.configuracion_json = json.dumps(datos["configuracion"] or {})
    paquete.fecha_actualizacion = datetime.utcnow()
    await db.commit()
    return {"status": "ok"}


@router.put("/paquetes-clubes/{id_paquete}/clubes/{liga}/{codigo}", tags=["Data Packs"])
async def actualizar_club_paquete(id_paquete: int, liga: str, codigo: str, datos: dict, db: AsyncSession = Depends(get_db)):
    """Upsert de un club puntual dentro del pack — usado por el formulario
    individual del Editor (buscar un club, editar sus campos, guardar)."""
    paquete = await db.get(PaqueteClubes, id_paquete)
    if not paquete:
        raise HTTPException(status_code=404, detail="Paquete no encontrado")
    nombres_clubes = json.loads(paquete.nombres_json)
    nombre = (datos.get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="El club necesita un nombre")
    escudo_url = (datos.get("escudo_url") or "").strip()
    nombre_competencia = (datos.get("nombre_competencia") or "").strip()
    fila = [codigo, nombre]
    if escudo_url or nombre_competencia:
        fila.append(escudo_url)
    if nombre_competencia:
        fila.append(nombre_competencia)

    clubes_liga = nombres_clubes.setdefault(liga, [])
    idx_existente = next((i for i, f in enumerate(clubes_liga) if f[0] == codigo), None)
    if idx_existente is not None:
        clubes_liga[idx_existente] = fila
    else:
        clubes_liga.append(fila)
    paquete.nombres_json = json.dumps(nombres_clubes)

    metadata = json.loads(paquete.metadata_clubes_json) if paquete.metadata_clubes_json else {}
    campos_meta = {k: str(datos.get(k) or "").strip() for k in ("ciudad", "estadio", "capacidad", "manager", "staff")}
    # Editar campos visibles nunca descarta los datos originales del proveedor.
    metadata.setdefault(liga, {}).setdefault(codigo, {}).update(campos_meta)
    paquete.metadata_clubes_json = json.dumps(metadata)

    paquete.fecha_actualizacion = datetime.utcnow()
    await db.commit()
    return {"status": "ok"}


@router.delete("/paquetes-clubes/{id_paquete}/clubes/{liga}/{codigo}", tags=["Data Packs"])
async def borrar_club_paquete(id_paquete: int, liga: str, codigo: str, db: AsyncSession = Depends(get_db)):
    paquete = await db.get(PaqueteClubes, id_paquete)
    if not paquete:
        raise HTTPException(status_code=404, detail="Paquete no encontrado")
    nombres_clubes = json.loads(paquete.nombres_json)
    if liga in nombres_clubes:
        nombres_clubes[liga] = [f for f in nombres_clubes[liga] if f[0] != codigo]
        paquete.nombres_json = json.dumps(nombres_clubes)
    paquete.fecha_actualizacion = datetime.utcnow()
    await db.commit()
    return {"status": "ok"}


@router.put("/paquetes-clubes/{id_paquete}/jugadores/{liga}/{codigo_club}/{indice}", tags=["Data Packs"])
async def actualizar_jugador_paquete(id_paquete: int, liga: str, codigo_club: str, indice: int, datos: dict, db: AsyncSession = Depends(get_db)):
    """Upsert de un jugador real puntual — `indice` nuevo (ej. el largo
    actual de la lista) agrega uno; uno existente lo reemplaza."""
    paquete = await db.get(PaqueteClubes, id_paquete)
    if not paquete:
        raise HTTPException(status_code=404, detail="Paquete no encontrado")
    nombre = (datos.get("nombre") or "").strip()
    posicion = (datos.get("posicion") or "").strip()
    if not nombre or not posicion:
        raise HTTPException(status_code=400, detail="El jugador necesita nombre y posición")

    jugadores_clubes = json.loads(paquete.jugadores_json) if paquete.jugadores_json else {}
    lista = jugadores_clubes.setdefault(liga, {}).setdefault(codigo_club, [])
    fila = {
        **(lista[indice] if 0 <= indice < len(lista) else {}),
        "nombre": nombre, "posicion": posicion,
        "posicion_especifica": (datos.get("posicion_especifica") or "").strip() or None,
        "nacionalidad": (datos.get("nacionalidad") or "").strip() or None,
        "edad": datos.get("edad", 24),
        "ataque": datos.get("ataque", 50), "defensa": datos.get("defensa", 50),
        "pase": datos.get("pase", 50), "fisico": datos.get("fisico", 50),
    }
    if 'foto_url' in datos:
        foto = datos.get('foto_url') or ''
        if not isinstance(foto, str) or (foto and not foto.startswith(('/static/', 'https://', 'http://'))):
            raise HTTPException(400, 'La cara debe ser una imagen subida o una URL HTTP(S).')
        fila['foto_url'] = foto
    if 0 <= indice < len(lista):
        lista[indice] = fila
    else:
        lista.append(fila)
    _, jugadores_clubes = _validar_datos_pack(json.loads(paquete.nombres_json), jugadores_clubes)
    paquete.jugadores_json = json.dumps(jugadores_clubes)
    paquete.fecha_actualizacion = datetime.utcnow()
    await db.commit()
    return {"status": "ok"}


@router.delete("/paquetes-clubes/{id_paquete}/jugadores/{liga}/{codigo_club}/{indice}", tags=["Data Packs"])
async def borrar_jugador_paquete(id_paquete: int, liga: str, codigo_club: str, indice: int, db: AsyncSession = Depends(get_db)):
    paquete = await db.get(PaqueteClubes, id_paquete)
    if not paquete:
        raise HTTPException(status_code=404, detail="Paquete no encontrado")
    jugadores_clubes = json.loads(paquete.jugadores_json) if paquete.jugadores_json else {}
    lista = jugadores_clubes.get(liga, {}).get(codigo_club, [])
    if 0 <= indice < len(lista):
        lista.pop(indice)
    paquete.jugadores_json = json.dumps(jugadores_clubes)
    paquete.fecha_actualizacion = datetime.utcnow()
    await db.commit()
    return {"status": "ok"}


@router.post("/paquetes-clubes/{id_paquete}/duplicar", tags=["Data Packs"])
async def duplicar_paquete_clubes(id_paquete: int, db: AsyncSession = Depends(get_db)):
    """Copia profunda e independiente — el original (incluido uno oficial
    como PARTIDOS Real Data) queda intacto; el duplicado nunca es oficial,
    así que se puede editar/borrar libremente."""
    original = await db.get(PaqueteClubes, id_paquete)
    if not original:
        raise HTTPException(status_code=404, detail="Paquete no encontrado")
    ahora = datetime.utcnow()
    nombre_copia = f"{original.nombre} (copia)"
    copia = PaqueteClubes(
        pack_id=pack_engine.generar_pack_id(nombre_copia, await _pack_ids_existentes(db)),
        nombre=nombre_copia, version=original.version, autor=original.autor, descripcion=original.descripcion,
        es_oficial=False, id_pack_origen=original.id_paquete,
        nombres_json=original.nombres_json, jugadores_json=original.jugadores_json,
        competencias_json=original.competencias_json, metadata_clubes_json=original.metadata_clubes_json,
        configuracion_json=original.configuracion_json,
        fecha_creacion=ahora, fecha_actualizacion=ahora,
    )
    db.add(copia)
    await db.commit()
    await db.refresh(copia)
    return {"id_paquete": copia.id_paquete}


@router.get("/paquetes-clubes/{id_paquete}/exportar", tags=["Data Packs"])
async def exportar_paquete_clubes(id_paquete: int, db: AsyncSession = Depends(get_db)):
    paquete = await db.get(PaqueteClubes, id_paquete)
    if not paquete:
        raise HTTPException(status_code=404, detail="Paquete no encontrado")
    contenido = pack_engine.exportar_pmpack(paquete, Path(DIRECTORIO_ESCUDOS))
    return Response(
        content=contenido, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{paquete.pack_id or "pack"}.pmpack"'},
    )


@router.post("/paquetes-clubes/importar", tags=["Data Packs"])
async def previsualizar_importar_pmpack(archivo: UploadFile = File(...)):
    """Valida el .pmpack y devuelve una vista previa (manifest + conteos +
    avisos de compatibilidad) SIN instalar nada todavía — el frontend
    reenvía este mismo payload a /importar/confirmar si el usuario confirma."""
    contenido = await archivo.read()
    try:
        resultado = pack_engine.importar_pmpack(contenido, _guardar_bytes_escudo)
    except PmpackInvalido as e:
        raise HTTPException(status_code=400, detail=str(e))
    return resultado


@router.post("/paquetes-clubes/importar/confirmar", tags=["Data Packs"])
async def confirmar_importar_pmpack(datos: dict, db: AsyncSession = Depends(get_db)):
    """Recibe el mismo payload que devolvió /importar (el frontend no lo
    modifica, solo lo reenvía tras la confirmación del usuario) y crea el
    pack — los assets ya se guardaron durante la previsualización."""
    manifest = datos.get("manifest") or {}
    nombres_clubes = datos.get("nombres_clubes")
    if not nombres_clubes:
        raise HTTPException(status_code=400, detail="Falta la base de clubes a importar")
    if not isinstance(manifest, dict):
        raise HTTPException(status_code=400, detail="Manifest inválido")
    nombres_clubes, jugadores_clubes = _validar_datos_pack(nombres_clubes, datos.get("jugadores_clubes"))
    nombre = (manifest.get("name") or "Pack importado").strip()
    ahora = datetime.utcnow()
    paquete = PaqueteClubes(
        pack_id=pack_engine.generar_pack_id(manifest.get("packId") or nombre, await _pack_ids_existentes(db)),
        nombre=nombre, version=manifest.get("version") or "1.0.0",
        autor=manifest.get("author") or "", descripcion=manifest.get("description") or "",
        nombres_json=json.dumps(nombres_clubes),
        jugadores_json=json.dumps(jugadores_clubes) if jugadores_clubes else None,
        competencias_json=json.dumps(datos.get("competencias")) if datos.get("competencias") else None,
        metadata_clubes_json=json.dumps(datos.get("metadata_clubes")) if datos.get("metadata_clubes") else None,
        configuracion_json=json.dumps(datos.get("configuracion") or {}),
        fecha_creacion=ahora, fecha_actualizacion=ahora,
    )
    db.add(paquete)
    await db.commit()
    await db.refresh(paquete)
    return {"id_paquete": paquete.id_paquete}


@router.delete("/paquetes-clubes/{id_paquete}", tags=["Data Packs"])
async def borrar_paquete_clubes(id_paquete: int, db: AsyncSession = Depends(get_db)):
    paquete = await db.get(PaqueteClubes, id_paquete)
    if not paquete:
        raise HTTPException(status_code=404, detail="Paquete no encontrado")
    if paquete.es_oficial:
        raise HTTPException(status_code=400, detail="Este pack viene incluido con el juego y no se puede borrar — podés duplicarlo y borrar la copia.")
    # Las carreras son snapshots independientes: pueden seguir jugándose aun
    # si se elimina el archivo fuente que las originó. Se desvinculan antes
    # de borrar el pack para que la clave foránea no bloquee la acción.
    carreras = (await db.execute(select(Partida).where(Partida.id_paquete_clubes == id_paquete))).scalars().all()
    for carrera in carreras:
        carrera.id_paquete_clubes = None
    await db.flush()
    await db.delete(paquete)
    await db.commit()
    return {"status": "ok", "carreras_conservadas": len(carreras)}


@router.post('/paquetes-clubes/{id_paquete}/caras', tags=['Data Packs'])
async def cargar_caras_paquete(id_paquete: int, archivos: list[UploadFile] = File(...), db: AsyncSession = Depends(get_db)):
    paquete = await db.get(PaqueteClubes, id_paquete)
    if not paquete:
        raise HTTPException(404, 'Paquete no encontrado')
    if len(archivos) > 200:
        raise HTTPException(400, 'Subí hasta 200 caras por tanda')
    from pathlib import Path
    jugadores = json.loads(paquete.jugadores_json or '{}')
    index = {}
    for liga, clubes in jugadores.items():
        for codigo, squad in clubes.items():
            for i, player in enumerate(squad):
                for key in {f'{liga}_{codigo}_{i}', str(player.get('datos_fuente', {}).get('id') or '')} - {''}:
                    index.setdefault(key.casefold(), []).append(player)
    preparados, sin_coincidencia, total = [], [], 0
    for file in archivos:
        name = Path(file.filename or '')
        matches = index.get(name.stem.casefold(), [])
        if len(matches) != 1:
            sin_coincidencia.append(file.filename)
            continue
        ext = name.suffix.lower()
        if ext not in ('.png', '.jpg', '.jpeg', '.webp'):
            raise HTTPException(400, f'Formato de cara no soportado: {file.filename}')
        content = await file.read(2 * 1024 * 1024 + 1)
        total += len(content)
        if not content or len(content) > 2 * 1024 * 1024 or total > 50 * 1024 * 1024:
            raise HTTPException(400, 'Máximo 2 MB por cara y 50 MB por tanda')
        preparados.append((matches[0], content, ext))
    for player, content, ext in preparados:
        player['foto_url'] = _guardar_bytes_escudo(content, ext)
    paquete.jugadores_json = json.dumps(jugadores, ensure_ascii=False)
    await db.commit()
    return {'cargadas': len(preparados), 'sin_coincidencia': sin_coincidencia}
