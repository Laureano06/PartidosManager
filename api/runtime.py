"""Dependencias y servicios compartidos de la API; sin registro de rutas."""
import json


import os


import random


import uuid


from contextlib import asynccontextmanager


from datetime import date, datetime, timedelta


from pathlib import Path


from formato import money


from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Response


from fastapi.middleware.cors import CORSMiddleware


from fastapi.staticfiles import StaticFiles


from sqlalchemy import select, or_, and_, update, delete, func, text


from sqlalchemy.ext.asyncio import AsyncSession


from database import engine, Base, get_db, AsyncSessionLocal


from models import (
    Equipo, Jugador, Tactica, PlanEntrenamiento, Calendario, OfertaFichaje, Liga, Partida, Mensaje,
    HistorialTemporada, PaqueteClubes, EventoPartido, PersonalTecnico, Ojeador, ReporteScouting,
    CicloTemporada, OfertaClubDT, AfiliacionClub, SolicitudParticipacion, AddOnTransferencia,
    Seleccion, ElegibilidadSeleccion, ConvocatoriaSeleccion, VentanaInternacional, PartidoSeleccion, TorneoSeleccion,
    automatizaciones_de_partida, AUTOMATIZACIONES_DEFAULT,
)


from schemas import (
    EquipoOut, JugadorOut, LigaOut, TacticaIn, EntrenamientoIn, EntrenamientoIndividualIn, CapitanIn, CharlaEquipoIn,
    OfertaIn, RespuestaOfertaIn, SimularJornadaIn,
    RenovarContratoIn, PrecontratoIn, FicharLibreIn, NegociarContratoTraspasoIn,
    TransferibleIn, OfrecerJugadorIn, CederJugadorIn,
    CategoriaJugadorIn, IntakeDecidirIn, ReclutarJuvenilIn, ElegirDestinoDTIn,
    OfertaParticipacionIn, MoverJugadorIn, InfluenciaIn,
)


from engine.match_engine import simulate_match


from engine.transfer_engine import evaluar_oferta


from engine.training_engine import aplicar_entrenamiento, recalcular_derivados_jugador, grupo_atributos


from engine.season_engine import aplicar_desgaste, procesar_lesiones, procesar_fin_temporada, generar_regen


from engine.ai_engine import ejecutar_ia_mercado


from engine.transfer_window import ventana_activa, proxima_apertura


from engine.contract_engine import evaluar_renovacion, salario_esperado


from engine.player_ai_engine import disposicion_renovar, disposicion_fichar, ajustar_moral, frase_dialogo


from engine.copa_engine import (
    COMPETENCIAS, NOMBRES_COMPETENCIA_DEFAULT, RONDAS_ELIMINATORIA, OFFSET_SEMANAS_ELIMINATORIA,
    fecha_ronda, posiciones_grupo, emparejar_octavos, ganador_eliminatoria,
)


from engine import academia_engine


from engine.academia_engine import (
    CATEGORIAS as CATEGORIAS_ACADEMIA, puede_mover_a_categoria, puede_reclutar,
    generar_academia_completa, calcular_n_candidatos_intake,
)


from engine import directiva_engine


from engine import multiclub_engine


from engine.data_gen import objetivo_por_nivel, nivel_desde_reputacion, tope_salarial


import pack_engine


from pack_engine import sembrar_partidos_real_data, PmpackInvalido


DIAS_ELEGIBLE_PRECONTRATO = 180


DIAS_CHECKPOINT_RENOVACION_IA = 150


PROB_RENOVACION_IA = 0.75


DIRECTORIO_STATIC = os.getenv("PARTIDOS_STATIC_DIR") or os.path.join(str(Path(__file__).resolve().parents[1]), "static")


DIRECTORIO_ESCUDOS = os.path.join(DIRECTORIO_STATIC, "escudos")


os.makedirs(DIRECTORIO_ESCUDOS, exist_ok=True)


EXTENSIONES_ESCUDO_VALIDAS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}


TAMANO_MAXIMO_ESCUDO = 2 * 1024 * 1024  # 2 MB


def _guardar_bytes_escudo(contenido: bytes, extension: str) -> str:
    """Guarda bytes de imagen ya validados en static/escudos/ con un nombre
    único y devuelve la URL local — usado tanto por /escudos/subir (subida
    manual) como por pack_engine.importar_pmpack (assets embebidos en un
    .pmpack)."""
    nombre_archivo = f"{uuid.uuid4().hex}{extension}"
    with open(os.path.join(DIRECTORIO_ESCUDOS, nombre_archivo), "wb") as f:
        f.write(contenido)
    return f"/static/escudos/{nombre_archivo}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # create_all crea tablas nuevas (como addons_transferencia) pero NO altera
    # tablas que ya existían — no hay Alembic en este proyecto, así que las
    # columnas nuevas se agregan acá a mano.
    migraciones_columna = (
        "ALTER TABLE jugadores ADD COLUMN clausula_rescision INTEGER",
        "ALTER TABLE jugadores ADD COLUMN id_club_reventa INTEGER",
        "ALTER TABLE jugadores ADD COLUMN porcentaje_reventa INTEGER",
        "ALTER TABLE jugadores ADD COLUMN partidos_club_actual INTEGER DEFAULT 0",
        "ALTER TABLE jugadores ADD COLUMN foco_individual VARCHAR(12)",
        "ALTER TABLE equipos ADD COLUMN id_capitan INTEGER",
        "ALTER TABLE equipos ADD COLUMN humor_hinchada INTEGER DEFAULT 60",
        "ALTER TABLE calendario ADD COLUMN charla_dada BOOLEAN DEFAULT FALSE",
        "ALTER TABLE ofertas_fichaje ADD COLUMN condiciones_json TEXT",
        # Sistema de Data Packs (.pmpack) — ver pack_engine.py.
        "ALTER TABLE paquetes_clubes ADD COLUMN pack_id VARCHAR(60)",
        "ALTER TABLE paquetes_clubes ADD COLUMN version VARCHAR(20) DEFAULT '1.0.0'",
        "ALTER TABLE paquetes_clubes ADD COLUMN autor VARCHAR(100) DEFAULT ''",
        "ALTER TABLE paquetes_clubes ADD COLUMN descripcion TEXT DEFAULT ''",
        "ALTER TABLE paquetes_clubes ADD COLUMN es_oficial BOOLEAN DEFAULT FALSE",
        "ALTER TABLE paquetes_clubes ADD COLUMN metadata_clubes_json TEXT",
        "ALTER TABLE paquetes_clubes ADD COLUMN configuracion_json TEXT",
        "ALTER TABLE equipos ADD COLUMN datos_pack_json TEXT",
        "ALTER TABLE jugadores ADD COLUMN datos_pack_json TEXT",
        "ALTER TABLE jugadores ADD COLUMN en_convocatoria BOOLEAN DEFAULT FALSE",
        "ALTER TABLE jugadores ADD COLUMN relacion_dt INTEGER DEFAULT 50",
        "ALTER TABLE ventanas_internacionales ADD COLUMN codigos_selecciones_json TEXT",
        "ALTER TABLE partidos_selecciones ADD COLUMN id_torneo INTEGER",
        "ALTER TABLE partidos_selecciones ADD COLUMN grupo VARCHAR(40)",
        "ALTER TABLE partidos_selecciones ADD COLUMN jornada INTEGER",
        "ALTER TABLE partidos_selecciones ADD COLUMN oficial BOOLEAN DEFAULT FALSE",
        "ALTER TABLE paquetes_clubes ADD COLUMN fecha_actualizacion TIMESTAMP",
        "ALTER TABLE paquetes_clubes ADD COLUMN id_pack_origen INTEGER",
        "ALTER TABLE partidas ADD COLUMN id_paquete_clubes INTEGER",
        "ALTER TABLE partidas ADD COLUMN automatizaciones_json TEXT",
    )
    if engine.dialect.name == "postgresql":
        # En Neon la versión anterior intentaba 30 ALTERs ya aplicados, cada
        # uno en una transacción propia. Eso hacía que cada reinicio tardara
        # minutos. Se consulta el esquema una vez y solo se migra lo faltante.
        async with engine.begin() as conn:
            existentes = {
                (fila[0], fila[1]) for fila in (await conn.execute(text(
                    "SELECT table_name, column_name FROM information_schema.columns "
                    "WHERE table_schema = current_schema()"
                ))).all()
            }
            for stmt in migraciones_columna:
                partes = stmt.split()
                tabla, columna = partes[2], partes[5]
                if (tabla, columna) not in existentes:
                    await conn.execute(text(stmt))
            largo_codigo = await conn.scalar(text(
                "SELECT character_maximum_length FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = 'selecciones' AND column_name = 'codigo'"
            ))
            if largo_codigo is not None and largo_codigo < 32:
                await conn.execute(text("ALTER TABLE selecciones ALTER COLUMN codigo TYPE VARCHAR(32)"))
    else:
        # SQLite no ofrece la misma introspección/migración de tipos; conserva
        # la estrategia tolerante para desarrollo local.
        for stmt in migraciones_columna:
            try:
                async with engine.begin() as conn:
                    await conn.execute(text(stmt))
            except Exception:
                pass

    async with AsyncSessionLocal() as session:
        await sembrar_partidos_real_data(session)

    print("Base de datos lista.")
    yield
    await engine.dispose()


async def _equipo_usuario(db: AsyncSession, id_partida: int) -> Equipo | None:
    return (await db.execute(
        select(Equipo).where(Equipo.id_partida == id_partida, Equipo.es_usuario.is_(True))
    )).scalars().first()


async def _fecha_actual(db: AsyncSession, id_partida: int) -> date:
    partida = await db.get(Partida, id_partida)
    return partida.fecha_actual if partida else date.today()


async def _bono_red_equipo(db: AsyncSession, equipo: Equipo) -> dict:
    """Bono de red combinado del club a partir de su vínculo multiclub más
    fuerte (participación accionaria o red de marca) — reemplaza el bono
    que antes salía de nivel_* (infraestructura por niveles, descartada:
    "no es real que existan niveles"). Para loops sobre muchos equipos a la
    vez, usar _bonos_red_por_equipos en vez de esto (evita N+1)."""
    relaciones = (await db.execute(
        select(AfiliacionClub).where(
            AfiliacionClub.id_partida == equipo.id_partida,
            or_(AfiliacionClub.id_equipo_inversor == equipo.id_equipo,
                AfiliacionClub.id_equipo_participado == equipo.id_equipo),
        )
    )).scalars().all()
    candidatos = []
    for r in relaciones:
        if r.id_equipo_participado == equipo.id_equipo:
            contraparte_id, rol = r.id_equipo_inversor, "PARTICIPADO"
        else:
            contraparte_id, rol = r.id_equipo_participado, "INVERSOR"
        contraparte = await db.get(Equipo, contraparte_id)
        if contraparte:
            candidatos.append((r.tipo_relacion, rol, contraparte.reputacion))
    if equipo.red_marca:
        socio = (await db.execute(
            select(Equipo).where(
                Equipo.id_partida == equipo.id_partida, Equipo.red_marca == equipo.red_marca,
                Equipo.id_equipo != equipo.id_equipo,
            )
        )).scalars().first()
        if socio:
            candidatos.append(("MARCA", "MARCA", socio.reputacion))
    if not candidatos:
        return multiclub_engine.bono_red(None, None, 0)
    mejor = max(candidatos, key=lambda c: multiclub_engine.fuerza_relacion(*c))
    return multiclub_engine.bono_red(*mejor)


async def _bonos_red_por_equipos(db: AsyncSession, id_partida: int, equipo_ids: set[int]) -> dict[int, dict]:
    """Versión batched de _bono_red_equipo: UNA consulta de AfiliacionClub
    para toda la partida (la tabla es chica, no crece con jugadores) en vez
    de 1-2 consultas por equipo dentro de un loop — mismo criterio que ya
    usa el resto del código (equipos_ojeadores_por_id, etc.)."""
    if not equipo_ids:
        return {}
    relaciones = (await db.execute(
        select(AfiliacionClub).where(AfiliacionClub.id_partida == id_partida)
    )).scalars().all()
    ids_relevantes = set(equipo_ids)
    for r in relaciones:
        ids_relevantes.add(r.id_equipo_inversor)
        ids_relevantes.add(r.id_equipo_participado)
    equipos_por_id = {e.id_equipo: e for e in (
        await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_relevantes)))
    ).scalars().all()}

    candidatos_por_equipo: dict[int, list] = {eid: [] for eid in equipo_ids}
    for r in relaciones:
        if r.id_equipo_participado in candidatos_por_equipo:
            contraparte = equipos_por_id.get(r.id_equipo_inversor)
            if contraparte:
                candidatos_por_equipo[r.id_equipo_participado].append((r.tipo_relacion, "PARTICIPADO", contraparte.reputacion))
        if r.id_equipo_inversor in candidatos_por_equipo:
            contraparte = equipos_por_id.get(r.id_equipo_participado)
            if contraparte:
                candidatos_por_equipo[r.id_equipo_inversor].append((r.tipo_relacion, "INVERSOR", contraparte.reputacion))

    marcas_por_equipo: dict[str, list[Equipo]] = {}
    for e in equipos_por_id.values():
        if e.red_marca:
            marcas_por_equipo.setdefault(e.red_marca, []).append(e)
    for eid in equipo_ids:
        equipo = equipos_por_id.get(eid)
        if equipo and equipo.red_marca:
            socios = [e for e in marcas_por_equipo.get(equipo.red_marca, []) if e.id_equipo != eid]
            if socios:
                candidatos_por_equipo[eid].append(("MARCA", "MARCA", socios[0].reputacion))

    resultado = {}
    for eid, candidatos in candidatos_por_equipo.items():
        if not candidatos:
            resultado[eid] = multiclub_engine.bono_red(None, None, 0)
        else:
            mejor = max(candidatos, key=lambda c: multiclub_engine.fuerza_relacion(*c))
            resultado[eid] = multiclub_engine.bono_red(*mejor)
    return resultado


def _bono_centro(bono: dict | None) -> float:
    return bono["bono_centro"] if bono else 0.0


def _factor_medico(bono: dict | None) -> float:
    """Multiplicador de riesgo de lesión (1.0 = sin efecto, hasta 0.4 = 60%
    menos riesgo) — ver engine/injury_engine.py::evaluar_lesion."""
    return bono["factor_medico"] if bono else 1.0


def _bono_analitica(bono: dict | None) -> int:
    return bono["bono_analitica"] if bono else 0


def _bono_instalaciones_juveniles(bono: dict | None) -> float:
    return bono["bono_instalaciones_juveniles"] if bono else 0.0


def _bono_captacion_juvenil(bono: dict | None) -> int:
    return bono["bono_captacion_juvenil"] if bono else 0


async def _asegurar_academia(db: AsyncSession, equipo: Equipo) -> None:
    """Genera la Academia completa (60 jugadores, 15 por categoría) la
    primera vez que se mira este club — nada se genera en seed.py, así los
    clubes de la IA que nadie mira nunca pagan este costo."""
    ya_existe = (await db.execute(
        select(Jugador.id_jugador)
        .where(Jugador.id_equipo == equipo.id_equipo, Jugador.categoria != "PRIMERA")
        .limit(1)
    )).first()
    if ya_existe:
        return
    liga = await db.get(Liga, equipo.id_liga)
    pais = liga.pais if liga else "Argentina"
    plantel_primera = (await db.execute(
        select(Jugador).where(Jugador.id_equipo == equipo.id_equipo, Jugador.categoria == "PRIMERA")
    )).scalars().all()
    bono_red = await _bono_red_equipo(db, equipo)
    bono_instalaciones = _bono_instalaciones_juveniles(bono_red)
    factor = academia_engine.calcular_factor_desde_plantel(plantel_primera, bono_instalaciones)
    fecha = await _fecha_actual(db, equipo.id_partida)
    for datos in generar_academia_completa(pais, factor):
        _completar_contrato_juvenil(datos, fecha)
        db.add(Jugador(id_partida=equipo.id_partida, id_equipo=equipo.id_equipo, **datos))
    await db.commit()


def _completar_contrato_juvenil(datos: dict, fecha: date) -> None:
    """generar_jugador_academia ya decidió el salario (0 = sin contrato); si
    tiene contrato le falta la fecha de vencimiento, que solo main.py puede
    poner porque necesita la fecha actual de la partida."""
    if datos["salario"] > 0:
        datos["fecha_fin_contrato"] = fecha + timedelta(days=365 * random.randint(1, 3))


async def _generar_ofertas_dt(
    db: AsyncSession, id_partida: int, reputacion_referencia: int, tipo: str, excluir_id_equipo: int | None,
) -> list[Equipo]:
    """Genera y persiste (OfertaClubDT) 3 clubes candidatos, ensanchando el
    rango de reputación si hace falta hasta encontrar 3 — algunas ligas
    tienen pocos clubes en un rango angosto."""
    await db.execute(delete(OfertaClubDT).where(OfertaClubDT.id_partida == id_partida))  # nunca acumular ofertas viejas
    low, high = directiva_engine.rango_ofertas(reputacion_referencia, tipo)
    candidatos: list[Equipo] = []
    intentos = 0
    while len(candidatos) < 3 and intentos < 6:
        query = select(Equipo).where(
            Equipo.id_partida == id_partida,
            Equipo.reputacion >= low, Equipo.reputacion <= high,
        )
        if excluir_id_equipo is not None:
            query = query.where(Equipo.id_equipo != excluir_id_equipo)
        candidatos = (await db.execute(query.order_by(func.random()).limit(10))).scalars().all()
        low = max(0, low - 10)
        high = min(100, high + 10)
        intentos += 1
    elegidos = candidatos[:3]
    for eq in elegidos:
        db.add(OfertaClubDT(id_partida=id_partida, id_equipo=eq.id_equipo))
    return elegidos


async def _evaluar_temporada_dt(db: AsyncSession, fecha: date, id_partida: int, equipos: list[Equipo]) -> None:
    """Evalúa el objetivo de temporada del DT del usuario contra la tabla
    final de SU liga (antes de que se resetee) y decide despido / fin de
    contrato / nada. `equipos` ya viene filtrado a la confederación que
    justo terminó — si el club del usuario no está ahí, no hace nada."""
    equipo_usuario = next((e for e in equipos if e.es_usuario), None)
    if not equipo_usuario:
        return
    partida = await db.get(Partida, id_partida)
    if partida.estado_dt != "NORMAL":
        return  # ya hay una decisión pendiente sin resolver, no pisarla

    liga_usuario = await db.get(Liga, equipo_usuario.id_liga)
    equipos_liga = sorted(
        (e for e in equipos if e.id_liga == equipo_usuario.id_liga),
        key=lambda e: (-e.puntos, -(e.goles_favor - e.goles_contra), -e.goles_favor),
    )
    posicion = next(i for i, e in enumerate(equipos_liga, start=1) if e.id_equipo == equipo_usuario.id_equipo)
    nivel = nivel_desde_reputacion(liga_usuario.codigo, equipo_usuario.reputacion)
    cumplido = directiva_engine.objetivo_cumplido(posicion, nivel, len(equipos_liga))

    partida.confianza_directiva = directiva_engine.actualizar_confianza(partida.confianza_directiva, cumplido)
    partida.balance_dt = directiva_engine.actualizar_balance(partida.balance_dt, cumplido)

    resultado_texto = (
        f"Terminaste la temporada {posicion}° en tu liga. "
        f"{'Cumpliste el objetivo' if cumplido else 'No cumpliste el objetivo'}: {partida.objetivo_temporada}"
    )

    if partida.confianza_directiva <= directiva_engine.UMBRAL_DESPIDO:
        partida.estado_dt = "DESPEDIDO"
        await _generar_ofertas_dt(db, id_partida, equipo_usuario.reputacion, "peor", equipo_usuario.id_equipo)
        await _crear_mensaje(
            db, equipo_usuario.id_equipo, "Directiva del Club", "Fin de ciclo",
            f"{resultado_texto} La directiva perdió la confianza en tu proyecto y decidió prescindir de tus servicios. "
            "Tenés 3 propuestas de otros clubes esperando tu decisión.",
            "SISTEMA", fecha,
        )
        return

    if partida.contrato_dt_fecha_fin and partida.contrato_dt_fecha_fin <= fecha:
        if cumplido:
            partida.estado_dt = "CONTRATO_FIN_EXITO"
            await _generar_ofertas_dt(db, id_partida, equipo_usuario.reputacion, "mejor", equipo_usuario.id_equipo)
            await _crear_mensaje(
                db, equipo_usuario.id_equipo, "Directiva del Club", "Termina tu contrato",
                f"{resultado_texto} Tu ciclo en el club llegó a su fin natural. La directiva te ofrece renovar, "
                "y además tenés 3 clubes de mayor nivel interesados en ficharte.",
                "SISTEMA", fecha,
            )
        elif random.random() < directiva_engine.probabilidad_renovacion_pese_a_incumplir(partida.confianza_directiva):
            partida.estado_dt = "CONTRATO_FIN_RENOVACION_OFRECIDA"
            await _crear_mensaje(
                db, equipo_usuario.id_equipo, "Directiva del Club", "Termina tu contrato",
                f"{resultado_texto} Pese a no cumplir el objetivo, la directiva decidió darte una nueva oportunidad "
                "y te ofrece renovar.",
                "SISTEMA", fecha,
            )
        else:
            partida.estado_dt = "CONTRATO_FIN_SIN_RENOVACION"
            await _generar_ofertas_dt(db, id_partida, equipo_usuario.reputacion, "mismo", equipo_usuario.id_equipo)
            await _crear_mensaje(
                db, equipo_usuario.id_equipo, "Directiva del Club", "Termina tu contrato",
                f"{resultado_texto} La directiva decidió no renovarte. Tenés 3 propuestas de clubes de un nivel "
                "similar esperando tu decisión.",
                "SISTEMA", fecha,
            )


INCERTIDUMBRE_BASE_SCOUTING = 18


def _rango_fog(valor_real: int, progreso: int) -> list[int]:
    ancho = round(INCERTIDUMBRE_BASE_SCOUTING * (1 - progreso / 100))
    return [max(1, valor_real - ancho), min(99, valor_real + ancho)]


def _aplicar_fog(d: dict, jugador: Jugador, reporte: ReporteScouting | None) -> None:
    """Reemplaza overall/potencial exactos por un rango con incertidumbre,
    que se va cerrando con `reporte.progreso` (0-100) hasta mostrar el valor
    exacto al llegar a 100. Solo se llama para jugadores que NO son del
    plantel propio del que pregunta."""
    progreso = reporte.progreso if reporte else 0
    d["overall"] = jugador.overall if progreso >= 100 else None
    d["overall_rango"] = None if progreso >= 100 else _rango_fog(jugador.overall, progreso)
    d["potencial"] = jugador.potencial if progreso >= 100 else None
    d["potencial_rango"] = None if progreso >= 100 else _rango_fog(jugador.potencial, progreso)
    d["scouting_progreso"] = progreso


async def _reportes_de(db: AsyncSession, id_equipo_viewer: int, ids_jugador: list[int]) -> dict[int, ReporteScouting]:
    """Batch de reportes de scouting del equipo `id_equipo_viewer` sobre una
    lista de jugadores — evita una query por fila al aplicar fog en listados."""
    if not ids_jugador:
        return {}
    filas = (await db.execute(
        select(ReporteScouting).where(
            ReporteScouting.id_equipo == id_equipo_viewer,
            ReporteScouting.id_jugador.in_(ids_jugador),
        )
    )).scalars().all()
    return {r.id_jugador: r for r in filas}


async def _crear_mensaje(db: AsyncSession, id_equipo_destino: int, remitente: str, asunto: str,
                          contenido: str, tipo: str, fecha: date, id_oferta: int | None = None) -> None:
    db.add(Mensaje(
        id_equipo_destino=id_equipo_destino, remitente=remitente, asunto=asunto,
        contenido=contenido, fecha=fecha, tipo=tipo, id_oferta=id_oferta,
    ))


def _texto_incorporacion(fecha: date) -> str:
    if ventana_activa(fecha):
        return "en los próximos días (la ventana de mercado ya está abierta)"
    return f"cuando abra la próxima ventana de mercado, el {proxima_apertura(fecha).strftime('%d/%m/%Y')}"


async def _efectivizar_ofertas_pendientes(db: AsyncSession, fecha: date, id_partida: int) -> None:
    """Si hay una ventana de mercado abierta, aplica (mueve pase + presupuesto)
    todas las ofertas ACEPTADA que todavía no se hicieron efectivas."""
    if not ventana_activa(fecha):
        return
    # OfertaFichaje no tiene id_partida propio (se llega a través del
    # jugador, que sí lo tiene) — sin este join se estarían efectivizando
    # ofertas de TODAS las carreras a la vez.
    pendientes = (await db.execute(
        select(OfertaFichaje)
        .join(Jugador, OfertaFichaje.id_jugador == Jugador.id_jugador)
        .where(
            Jugador.id_partida == id_partida,
            OfertaFichaje.estado == "ACEPTADA",
            OfertaFichaje.efectivizada.is_(False),
        )
    )).scalars().all()

    # Salvaguarda: si por algún motivo quedaron dos ofertas ACEPTADA sin
    # efectivizar por el mismo jugador (no debería pasar con las validaciones
    # de arriba, pero evita traspasos dobles si igual ocurriera), el jugador
    # decide y se queda con la mejor oferta de contrato; las demás se cancelan
    # sin mover dinero (todavía no se había efectivizado ninguna).
    por_jugador: dict[int, list[OfertaFichaje]] = {}
    for oferta in pendientes:
        por_jugador.setdefault(oferta.id_jugador, []).append(oferta)
    descartadas_ids: set[int] = set()
    for id_jugador, grupo in por_jugador.items():
        if len(grupo) <= 1:
            continue
        elegida = max(grupo, key=lambda o: o.salario_pactado or 0)
        for otra in grupo:
            if otra.id_oferta == elegida.id_oferta:
                continue
            otra.estado = "CANCELADA"
            otra.efectivizada = True
            descartadas_ids.add(otra.id_oferta)
            otro_comprador = await db.get(Equipo, otra.id_equipo_comprador)
            jugador_ref = await db.get(Jugador, otra.id_jugador)
            if otro_comprador and otro_comprador.es_usuario:
                await _crear_mensaje(
                    db, otro_comprador.id_equipo, "Secretaría Técnica",
                    f"{jugador_ref.nombre if jugador_ref else 'El jugador'} eligió otro club",
                    f"{jugador_ref.nombre if jugador_ref else 'El jugador'} prefirió la propuesta de otro club. Tu acuerdo quedó sin efecto.",
                    "MERCADO", fecha,
                )
    pendientes = [o for o in pendientes if o.id_oferta not in descartadas_ids]

    for oferta in pendientes:
        jugador = await db.get(Jugador, oferta.id_jugador)
        comprador = await db.get(Equipo, oferta.id_equipo_comprador)
        vendedor = await db.get(Equipo, oferta.id_equipo_vendedor)
        oferta.efectivizada = True
        if not jugador or not comprador or not vendedor:
            continue

        comprador.presupuesto_fichajes -= oferta.monto_oferta
        vendedor.presupuesto_fichajes += oferta.monto_oferta
        comprador.presupuesto_salarios = tope_salarial(comprador.presupuesto_fichajes)
        vendedor.presupuesto_salarios = tope_salarial(vendedor.presupuesto_fichajes)
        jugador.id_equipo = comprador.id_equipo
        jugador.rol = "RESERVA"
        jugador.partidos_club_actual = 0
        if oferta.salario_pactado:
            # Contrato nuevo pactado con el jugador como parte del traspaso.
            jugador.salario = oferta.salario_pactado
            condiciones = json.loads(oferta.condiciones_json or '{}')
            jugador.fecha_fin_contrato = fecha + timedelta(days=365 * condiciones.get('anios', 3))
            jugador.clausula_rescision = condiciones.get('clausula_rescision')

        # Reventa (sell-on): si un club anterior se había quedado con un % de
        # la PRÓXIMA venta de este jugador, se cobra acá — el guard contra
        # vendedor.id_equipo evita que se pague a sí mismo en la venta donde
        # lo pidió (recién seteado por responder_oferta, vendedor==id_club_reventa
        # en ESA venta), y a la vez hace que el campo sobreviva sin tocarlo
        # hasta que dispare de verdad en la venta siguiente.
        if jugador.id_club_reventa and jugador.id_club_reventa != vendedor.id_equipo and jugador.porcentaje_reventa:
            monto_reventa = round(oferta.monto_oferta * jugador.porcentaje_reventa / 100)
            club_reventa = await db.get(Equipo, jugador.id_club_reventa)
            if club_reventa and monto_reventa > 0:
                club_reventa.presupuesto_fichajes += monto_reventa
                vendedor.presupuesto_fichajes -= monto_reventa
                if club_reventa.es_usuario:
                    await _crear_mensaje(
                        db, club_reventa.id_equipo, "Secretaría Técnica", f"Reventa de {jugador.nombre}",
                        f"Por la cláusula de reventa que te reservaste, cobrás ${money(monto_reventa)} "
                        f"({jugador.porcentaje_reventa}%) de la venta de {jugador.nombre} a {comprador.nombre}.",
                        "MERCADO", fecha,
                    )
                if vendedor.es_usuario:
                    await _crear_mensaje(
                        db, vendedor.id_equipo, "Secretaría Técnica", f"Cláusula de reventa descontada",
                        f"De los ${money(oferta.monto_oferta)} de la venta de {jugador.nombre}, "
                        f"${money(monto_reventa)} van para {club_reventa.nombre} por la cláusula de reventa pactada.",
                        "MERCADO", fecha,
                    )
            jugador.id_club_reventa = None
            jugador.porcentaje_reventa = None

        if comprador.es_usuario:
            await _crear_mensaje(
                db, comprador.id_equipo, "Secretaría Técnica", f"{jugador.nombre} ya es parte del plantel",
                f"Se hizo efectiva la incorporación de {jugador.nombre} por ${money(oferta.monto_oferta)}.",
                "MERCADO", fecha,
            )
        if vendedor.es_usuario:
            await _crear_mensaje(
                db, vendedor.id_equipo, "Secretaría Técnica", f"Se concretó la venta de {jugador.nombre}",
                f"{comprador.nombre} pagó ${money(oferta.monto_oferta)} por {jugador.nombre}.",
                "MERCADO", fecha,
            )


async def _procesar_addons_cumplidos(db: AsyncSession, ids_jugadores_que_jugaron: set[int] | list[int], fecha: date) -> None:
    """Se corre después de aplicar los efectos físicos de cada partido (ver
    _calcular_efectos_fisicos/_aplicar_efectos_fisicos, que ya incrementaron
    partidos_club_actual): revisa si algún AddOnTransferencia pendiente de
    esos jugadores llegó a su objetivo y, si sí, paga."""
    if not ids_jugadores_que_jugaron:
        return
    pendientes = (await db.execute(
        select(AddOnTransferencia, Jugador)
        .join(Jugador, AddOnTransferencia.id_jugador == Jugador.id_jugador)
        .where(
            AddOnTransferencia.cumplido.is_(False),
            AddOnTransferencia.id_jugador.in_(ids_jugadores_que_jugaron),
        )
    )).all()
    for addon, jugador in pendientes:
        if jugador.partidos_club_actual < addon.partidos_objetivo or not jugador.id_equipo:
            continue
        addon.cumplido = True
        club_pagador = await db.get(Equipo, jugador.id_equipo)
        club_beneficiario = await db.get(Equipo, addon.id_equipo_beneficiario)
        if not club_pagador or not club_beneficiario:
            continue
        club_pagador.presupuesto_fichajes -= addon.monto
        club_beneficiario.presupuesto_fichajes += addon.monto
        if club_pagador.es_usuario:
            await _crear_mensaje(
                db, club_pagador.id_equipo, "Secretaría Técnica", f"Add-on activado: {jugador.nombre}",
                f"{jugador.nombre} llegó a los {addon.partidos_objetivo} partidos pactados — se le pagan "
                f"${money(addon.monto)} a {club_beneficiario.nombre} por el add-on de su transferencia.",
                "MERCADO", fecha,
            )
        if club_beneficiario.es_usuario:
            await _crear_mensaje(
                db, club_beneficiario.id_equipo, "Secretaría Técnica", f"Cobraste un add-on: {jugador.nombre}",
                f"{jugador.nombre} llegó a los {addon.partidos_objetivo} partidos con {club_pagador.nombre} — "
                f"cobrás ${money(addon.monto)} del add-on pactado en su transferencia.",
                "MERCADO", fecha,
            )


async def _procesar_contratos(db: AsyncSession, fecha: date, id_partida: int) -> None:
    """Se corre en cada avance de día:
    1) A 150 días de vencer, los clubes de la IA (nunca el del usuario)
       intentan renovar automáticamente a sus jugadores sin precontrato.
    2) Los contratos que vencen HOY: si el jugador firmó un precontrato,
       pasa a ese club (pase libre); si no, queda como agente libre.
    """
    # Las dos consultas de acá abajo (candidatos a renovación IA, contratos
    # vencidos) son mutuamente excluyentes en la práctica — un contrato no
    # puede a la vez ESTAR EN el checkpoint (150 días a futuro) Y ya haber
    # vencido — así que se piden juntas en un solo viaje a la base (~200ms
    # de latencia por consulta a Neon, evitar una segunda consulta importa
    # en un salto de varias semanas) y se separan acá en Python.
    checkpoint = fecha + timedelta(days=DIAS_CHECKPOINT_RENOVACION_IA)
    cond_candidato_ia = (
        (Jugador.fecha_fin_contrato == checkpoint)
        & Jugador.id_equipo_precontrato.is_(None)
        & Jugador.id_equipo.is_not(None)
    )
    cond_vencido = Jugador.fecha_fin_contrato.is_not(None) & (Jugador.fecha_fin_contrato <= fecha)
    relevantes = (await db.execute(
        select(Jugador).where(Jugador.id_partida == id_partida, or_(cond_candidato_ia, cond_vencido))
    )).scalars().all()
    candidatos_ia = [j for j in relevantes if j.fecha_fin_contrato == checkpoint and j.id_equipo_precontrato is None and j.id_equipo is not None]
    vencidos = [j for j in relevantes if j.fecha_fin_contrato is not None and j.fecha_fin_contrato <= fecha]

    # Precarga en un solo viaje (en vez de un `db.get()` por jugador dentro
    # de los loops de abajo) — con decenas de contratos venciendo el mismo
    # día, esto era el N+1 más caro de todo el avance de día.
    ids_equipo_relevantes = {j.id_equipo for j in relevantes if j.id_equipo} | {j.id_equipo_precontrato for j in vencidos if j.id_equipo_precontrato}
    equipos_por_id: dict[int, Equipo] = {}
    if ids_equipo_relevantes:
        equipos_por_id = {e.id_equipo: e for e in (
            await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_equipo_relevantes)))
        ).scalars().all()}

    for j in candidatos_ia:
        equipo = equipos_por_id.get(j.id_equipo)
        if not equipo or equipo.es_usuario:
            continue
        if random.random() < PROB_RENOVACION_IA:
            anios = random.randint(1, 3)
            j.fecha_fin_contrato = fecha + timedelta(days=365 * anios)
            j.salario = salario_esperado(j.valor_mercado, j.edad)

    for j in vencidos:
        equipo_anterior = equipos_por_id.get(j.id_equipo) if j.id_equipo else None
        if j.id_equipo_precontrato:
            equipo_nuevo = equipos_por_id.get(j.id_equipo_precontrato)
            j.id_equipo = j.id_equipo_precontrato
            j.salario = j.salario_precontrato or j.salario
            j.fecha_fin_contrato = fecha + timedelta(days=365 * 3)
            j.id_equipo_precontrato = None
            j.salario_precontrato = None
            j.rol = "RESERVA"
            if equipo_nuevo and equipo_nuevo.es_usuario:
                await _crear_mensaje(
                    db, equipo_nuevo.id_equipo, "Secretaría Técnica", f"{j.nombre} ya es parte del plantel",
                    f"Se hizo efectivo el precontrato: {j.nombre} se incorpora libre de {equipo_anterior.nombre if equipo_anterior else '?'}.",
                    "MERCADO", fecha,
                )
            if equipo_anterior and equipo_anterior.es_usuario:
                await _crear_mensaje(
                    db, equipo_anterior.id_equipo, "Secretaría Técnica", f"{j.nombre} se fue libre",
                    f"Terminó su contrato y se incorporó a {equipo_nuevo.nombre if equipo_nuevo else '?'} por precontrato.",
                    "MERCADO", fecha,
                )
        else:
            j.id_equipo = None
            j.fecha_fin_contrato = None
            j.rol = "RESERVA"
            if equipo_anterior and equipo_anterior.es_usuario:
                await _crear_mensaje(
                    db, equipo_anterior.id_equipo, "Secretaría Técnica", f"{j.nombre} quedó libre",
                    f"Terminó su contrato sin renovar y ahora es agente libre.",
                    "MERCADO", fecha,
                )


async def _procesar_ventanas_internacionales(db: AsyncSession, fecha: date, id_partida: int) -> None:
    """Activa y libera automáticamente las convocatorias de una ventana.

    Solo usa las selecciones que el pack marcó como activas; así una base
    mundial no retira por error a todos los jugadores de sus clubes a la vez.
    """
    partida = await db.get(Partida, id_partida)
    if not partida or not automatizaciones_de_partida(partida.automatizaciones_json)["selecciones"]:
        return
    partidas = (await db.execute(select(VentanaInternacional).where(
        VentanaInternacional.id_partida == id_partida,
        or_(VentanaInternacional.fecha_inicio == fecha, VentanaInternacional.fecha_fin == fecha),
    ))).scalars().all()
    if not partidas:
        return
    equipos_usuario = (await db.execute(select(Equipo).where(Equipo.id_partida == id_partida, Equipo.es_usuario.is_(True)))).scalars().all()
    ids_usuario = {e.id_equipo for e in equipos_usuario}
    for ventana in partidas:
        try:
            activos = json.loads(ventana.codigos_selecciones_json or "[]")
        except json.JSONDecodeError:
            activos = []
        if not activos:
            continue
        filas = (await db.execute(
            select(ConvocatoriaSeleccion, Jugador, Seleccion)
            .join(Jugador, Jugador.id_jugador == ConvocatoriaSeleccion.id_jugador)
            .join(Seleccion, Seleccion.id_seleccion == ConvocatoriaSeleccion.id_seleccion)
            .where(Seleccion.codigo.in_(activos), ConvocatoriaSeleccion.estado.in_(("PRESELECCION", "CONVOCADO")))
        )).all()
        if ventana.fecha_inicio == fecha:
            por_equipo: dict[int, list[str]] = {}
            for convocatoria, jugador, _ in filas:
                convocatoria.estado = "CONVOCADO"
                convocatoria.fecha_inicio, convocatoria.fecha_fin = ventana.fecha_inicio, ventana.fecha_fin
                jugador.en_convocatoria = True
                if jugador.id_equipo in ids_usuario:
                    por_equipo.setdefault(jugador.id_equipo, []).append(jugador.nombre)
            for id_equipo, nombres in por_equipo.items():
                await _crear_mensaje(db, id_equipo, "Federación", "Convocatoria internacional",
                    f"{', '.join(nombres[:6])}{' y más' if len(nombres) > 6 else ''} se incorpora a su selección hasta el {ventana.fecha_fin.isoformat()}.",
                    "SELECCION", fecha)
        if ventana.fecha_fin == fecha:
            por_equipo: dict[int, list[str]] = {}
            for convocatoria, jugador, _ in filas:
                if convocatoria.fecha_fin != ventana.fecha_fin:
                    continue
                convocatoria.estado = "PRESELECCION"
                convocatoria.fecha_inicio = convocatoria.fecha_fin = None
                jugador.en_convocatoria = False
                jugador.energia = max(35, jugador.energia - 8)
                if jugador.id_equipo in ids_usuario:
                    por_equipo.setdefault(jugador.id_equipo, []).append(jugador.nombre)
            for id_equipo, nombres in por_equipo.items():
                await _crear_mensaje(db, id_equipo, "Cuerpo Técnico", "Regreso de selecciones",
                    f"{', '.join(nombres[:6])}{' y más' if len(nombres) > 6 else ''} regresó de la ventana internacional con una carga física moderada.",
                    "SELECCION", fecha)


async def _procesar_partidos_selecciones(db: AsyncSession, fecha: date, id_partida: int) -> None:
    """Simula automáticamente los amistosos internacionales programados."""
    partida = await db.get(Partida, id_partida)
    if not partida or not automatizaciones_de_partida(partida.automatizaciones_json)["selecciones"]:
        return
    fixtures = (await db.execute(select(PartidoSeleccion).where(
        PartidoSeleccion.id_partida == id_partida, PartidoSeleccion.jugado.is_(False), PartidoSeleccion.fecha <= fecha,
    ))).scalars().all()
    if not fixtures:
        return
    ids_seleccion = {f.id_local for f in fixtures} | {f.id_visitante for f in fixtures}
    selecciones = {s.id_seleccion: s for s in (await db.execute(select(Seleccion).where(Seleccion.id_seleccion.in_(ids_seleccion)))).scalars().all()}
    convocados: dict[int, list[Jugador]] = {}
    filas = (await db.execute(select(ConvocatoriaSeleccion, Jugador).join(
        Jugador, Jugador.id_jugador == ConvocatoriaSeleccion.id_jugador
    ).where(ConvocatoriaSeleccion.id_seleccion.in_(ids_seleccion), ConvocatoriaSeleccion.estado == "CONVOCADO"))).all()
    for convocatoria, jugador in filas:
        convocados.setdefault(convocatoria.id_seleccion, []).append(jugador)
    for fixture in fixtures:
        local = _once_titular(convocados.get(fixture.id_local, []))
        visitante = _once_titular(convocados.get(fixture.id_visitante, []))
        if not local or not visitante:
            fixture.jugado = True
            fixture.goles_local, fixture.goles_visitante = 0, 0
            continue
        datos_local = [{"id_jugador": j.id_jugador, "nombre": j.nombre, "posicion": j.posicion,
                         "ataque": j.ataque, "defensa": j.defensa, "energia": j.energia, "duty": j.duty} for j in local]
        datos_visit = [{"id_jugador": j.id_jugador, "nombre": j.nombre, "posicion": j.posicion,
                         "ataque": j.ataque, "defensa": j.defensa, "energia": j.energia, "duty": j.duty} for j in visitante]
        resultado = simulate_match(datos_local, datos_visit,
            {"formacion": "4-3-3", "mentalidad": "BALANCEADA", "presion": "MEDIA"},
            {"formacion": "4-3-3", "mentalidad": "BALANCEADA", "presion": "MEDIA"}, ia_local=True, ia_visit=True)
        aplicar_desgaste({j.id_jugador: j for j in local + visitante}, resultado["energia_gastada"])
        fixture.jugado = True
        fixture.goles_local, fixture.goles_visitante = resultado["gh"], resultado["gv"]
        if fixture.oficial:
            titulares_por_seleccion = {
                fixture.id_local: {j.id_jugador for j in local},
                fixture.id_visitante: {j.id_jugador for j in visitante},
            }
            elegibilidades = (await db.execute(select(ElegibilidadSeleccion).where(
                ElegibilidadSeleccion.id_seleccion.in_(titulares_por_seleccion)
            ))).scalars().all()
            for elegibilidad in elegibilidades:
                if elegibilidad.id_jugador in titulares_por_seleccion.get(elegibilidad.id_seleccion, set()):
                    elegibilidad.partidos_oficiales += 1


async def _procesar_relaciones_plantel(db: AsyncSession, fecha: date, id_partida: int) -> None:
    """Ajuste semanal y suave del vínculo con el DT para el club del usuario."""
    partida = await db.get(Partida, id_partida)
    if not partida or not automatizaciones_de_partida(partida.automatizaciones_json)["relaciones"] or fecha.weekday() != 0:
        return
    equipo = await _equipo_usuario(db, id_partida)
    if not equipo:
        return
    jugadores = (await db.execute(select(Jugador).where(
        Jugador.id_equipo == equipo.id_equipo, Jugador.categoria == "PRIMERA"
    ))).scalars().all()
    ajuste_rol = {"TITULAR": 8, "SUPLENTE": 1, "RESERVA": -8}
    for jugador in jugadores:
        objetivo = 50 + ajuste_rol.get(jugador.rol, 0) + round((jugador.moral - 70) * 0.25)
        objetivo = max(20, min(85, objetivo))
        if jugador.relacion_dt < objetivo:
            jugador.relacion_dt += 1
        elif jugador.relacion_dt > objetivo:
            jugador.relacion_dt -= 1


async def _procesar_oportunidades_multiclub(db: AsyncSession, fecha: date, id_partida: int) -> None:
    """Propone cesiones dentro de una red, pero nunca mueve jugadores solo."""
    partida = await db.get(Partida, id_partida)
    if not partida or not automatizaciones_de_partida(partida.automatizaciones_json)["multiclub"] or fecha.weekday() != 0:
        return
    equipo = await _equipo_usuario(db, id_partida)
    if not equipo:
        return
    relaciones = (await db.execute(select(AfiliacionClub).where(
        AfiliacionClub.id_partida == id_partida,
        AfiliacionClub.tipo_relacion.in_(multiclub_engine.TIPOS_CON_PIPELINE),
        or_(AfiliacionClub.id_equipo_inversor == equipo.id_equipo, AfiliacionClub.id_equipo_participado == equipo.id_equipo),
    ))).scalars().all()
    socios_ids = {
        (r.id_equipo_participado if r.id_equipo_inversor == equipo.id_equipo else r.id_equipo_inversor)
        for r in relaciones
    }
    if equipo.red_marca:
        socios_ids.update((await db.execute(select(Equipo.id_equipo).where(
            Equipo.id_partida == id_partida, Equipo.red_marca == equipo.red_marca, Equipo.id_equipo != equipo.id_equipo
        ))).scalars().all())
    if not socios_ids:
        return
    socios = (await db.execute(select(Equipo).where(Equipo.id_equipo.in_(socios_ids), Equipo.id_liga != equipo.id_liga))).scalars().all()
    if not socios:
        return
    jugadores_socios = (await db.execute(select(Jugador).where(
        Jugador.id_equipo.in_([s.id_equipo for s in socios]), Jugador.categoria == "PRIMERA"
    ))).scalars().all()
    promedio: dict[tuple[int, str], float] = {}
    conteos: dict[tuple[int, str], int] = {}
    for jugador in jugadores_socios:
        clave = (jugador.id_equipo, jugador.posicion)
        promedio[clave] = promedio.get(clave, 0) + jugador.overall
        conteos[clave] = conteos.get(clave, 0) + 1
    for clave, total in promedio.items():
        promedio[clave] = total / conteos[clave]
    plantel = (await db.execute(select(Jugador).where(
        Jugador.id_equipo == equipo.id_equipo, Jugador.categoria == "PRIMERA", Jugador.id_equipo_dueno.is_(None),
        Jugador.rol.in_(("SUPLENTE", "RESERVA")), Jugador.edad <= 25
    ))).scalars().all()
    propuestas: list[tuple[Jugador, Equipo, float]] = []
    for jugador in plantel:
        for socio in socios:
            brecha = jugador.overall - promedio.get((socio.id_equipo, jugador.posicion), jugador.overall)
            if brecha >= 3:
                propuestas.append((jugador, socio, brecha))
    if not propuestas:
        return
    propuestas.sort(key=lambda fila: (fila[2], fila[0].potencial, fila[0].overall), reverse=True)
    texto = "; ".join(f"{j.nombre} → {s.nombre}" for j, s, _ in propuestas[:3])
    await _crear_mensaje(
        db, equipo.id_equipo, "Dirección multiclub", "Oportunidades de cesión en la red",
        f"La revisión semanal detectó opciones para acelerar minutos: {texto}. Podés concretarlas desde Multiclub; no se moverá nadie sin tu decisión.",
        "MULTICLUB", fecha,
    )


async def _procesar_informe_academia(db: AsyncSession, fecha: date, id_partida: int) -> None:
    """Resume la academia existente cada semana sin generar jugadores ocultos."""
    partida = await db.get(Partida, id_partida)
    if not partida or not automatizaciones_de_partida(partida.automatizaciones_json)["academia"] or fecha.weekday() != 2:
        return
    equipo = await _equipo_usuario(db, id_partida)
    if not equipo:
        return
    juveniles = (await db.execute(select(Jugador).where(
        Jugador.id_equipo == equipo.id_equipo, Jugador.categoria != "PRIMERA"
    ))).scalars().all()
    if not juveniles:
        return
    sub21 = [j for j in juveniles if j.categoria == "SUB21" and j.edad >= 18]
    destacados = sorted(sub21, key=lambda j: (j.potencial - j.overall, j.potencial), reverse=True)[:3]
    cantidades = {categoria: sum(1 for j in juveniles if j.categoria == categoria) for categoria in CATEGORIAS_ACADEMIA}
    faltantes = [categoria.replace("SUB", "Sub-") for categoria, cantidad in cantidades.items() if cantidad < academia_engine.TAMANIO_MINIMO_CATEGORIA]
    if not destacados and not faltantes:
        return
    partes = []
    if destacados:
        partes.append("listos para seguimiento: " + ", ".join(
            f"{j.nombre} (OVR {j.overall} · POT {j.potencial})" for j in destacados
        ))
    if faltantes:
        partes.append("plantel incompleto en " + ", ".join(faltantes))
    await _crear_mensaje(
        db, equipo.id_equipo, "Responsable de Academia", "Informe semanal de cantera",
        " · ".join(partes) + ". Revisalos en Academia antes de promoverlos o buscarles una cesión.",
        "ACADEMIA", fecha,
    )


async def _procesar_prensa_y_vestuario(db: AsyncSession, fecha: date, id_partida: int) -> None:
    """Resume cada semana el pulso del grupo y la lectura pública, sin alterar decisiones del usuario."""
    partida = await db.get(Partida, id_partida)
    if (
        not partida
        or not automatizaciones_de_partida(partida.automatizaciones_json)["prensa_vestuario"]
        or fecha.weekday() != 1
    ):
        return
    equipo = await _equipo_usuario(db, id_partida)
    if not equipo:
        return
    plantel = (await db.execute(select(Jugador).where(
        Jugador.id_equipo == equipo.id_equipo, Jugador.categoria == "PRIMERA",
    ))).scalars().all()
    if not plantel:
        return
    puntaje = _puntaje_vestuario(plantel, equipo.id_capitan)
    media_moral = sum(jugador.moral for jugador in plantel) / len(plantel)
    inquietos = sorted(plantel, key=lambda jugador: (jugador.moral, jugador.relacion_dt))[:3]
    if puntaje < 50:
        lectura = "La prensa percibe tensión en el grupo y espera una reacción deportiva."
    elif puntaje < 70:
        lectura = "El grupo se mantiene estable, aunque la prensa pide continuidad en los resultados."
    else:
        lectura = "El vestuario transmite confianza y la prensa valora la estabilidad del proyecto."
    contenido = (
        f"{lectura} Vestuario: {puntaje:.0f}/100 · moral media: {media_moral:.0f}/100. "
        f"Jugadores a acompañar: {', '.join(jugador.nombre for jugador in inquietos)}. "
        "Podés intervenir desde Plantel mediante una charla individual."
    )
    await _crear_mensaje(
        db, equipo.id_equipo, "Prensa y Vestuario", "Pulso semanal del vestuario",
        contenido, "PRENSA", fecha,
    )


async def _procesar_bitacora_documental(db: AsyncSession, fecha: date, id_partida: int) -> None:
    """Guarda una crónica mensual de carrera en el buzón sin inventar hechos deportivos."""
    partida = await db.get(Partida, id_partida)
    if (
        not partida
        or not automatizaciones_de_partida(partida.automatizaciones_json)["documental"]
        or fecha.day != 1
    ):
        return
    equipo = await _equipo_usuario(db, id_partida)
    if not equipo:
        return
    plantel = (await db.execute(select(Jugador).where(
        Jugador.id_equipo == equipo.id_equipo, Jugador.categoria == "PRIMERA",
    ))).scalars().all()
    moral_media = round(sum(jugador.moral for jugador in plantel) / len(plantel)) if plantel else 0
    contratos = sum(1 for jugador in plantel if jugador.fecha_fin_contrato and 0 <= (jugador.fecha_fin_contrato - fecha).days <= 180)
    await _crear_mensaje(
        db, equipo.id_equipo, "Bitácora de carrera", f"Crónica de {fecha.strftime('%B de %Y')}",
        f"{equipo.nombre} inicia el mes con hinchada en {equipo.humor_hinchada}/100, moral de plantilla en {moral_media}/100 y {contratos} contratos por revisar. Esta entrada conserva el estado de la carrera para seguir su evolución.",
        "DOCUMENTAL", fecha,
    )


async def _procesar_informe_direccion_deportiva(db: AsyncSession, fecha: date, id_partida: int) -> None:
    """Entrega una revisión semanal del plantel sin fichar ni renovar por cuenta propia."""
    partida = await db.get(Partida, id_partida)
    if (
        not partida
        or not automatizaciones_de_partida(partida.automatizaciones_json)["direccion_deportiva"]
        or fecha.weekday() != 4
    ):
        return
    equipo = await _equipo_usuario(db, id_partida)
    if not equipo:
        return

    plantel = (await db.execute(select(Jugador).where(
        Jugador.id_equipo == equipo.id_equipo,
        Jugador.categoria == "PRIMERA",
    ))).scalars().all()
    disponibles = [j for j in plantel if j.rol in ("TITULAR", "SUPLENTE")]
    if not disponibles:
        return

    proximos = sorted(
        (j for j in plantel if j.fecha_fin_contrato and 0 <= (j.fecha_fin_contrato - fecha).days <= 180),
        key=lambda jugador: jugador.fecha_fin_contrato,
    )[:3]
    minimos = {"POR": 2, "DEF": 6, "MED": 6, "DEL": 4}
    nombres_posicion = {"POR": "arco", "DEF": "defensa", "MED": "mediocampo", "DEL": "ataque"}
    cobertura_corta = [
        f"{nombres_posicion[pos]} ({sum(1 for jugador in disponibles if jugador.posicion == pos)}/{minimo})"
        for pos, minimo in minimos.items()
        if sum(1 for jugador in disponibles if jugador.posicion == pos) < minimo
    ]
    promedios = _promedios_por_posicion(disponibles)
    posiciones_debiles = sorted(promedios, key=promedios.get)[:1]

    partes = []
    if proximos:
        partes.append("contratos a revisar: " + ", ".join(
            f"{jugador.nombre} ({jugador.fecha_fin_contrato.strftime('%d/%m/%Y')})"
            for jugador in proximos
        ))
    if cobertura_corta:
        partes.append("cobertura corta en " + ", ".join(cobertura_corta))
    if posiciones_debiles and promedios[posiciones_debiles[0]]:
        pos = posiciones_debiles[0]
        partes.append(f"nivel medio más bajo: {nombres_posicion[pos]} (OVR {promedios[pos]:.1f})")
    if not partes:
        return

    await _crear_mensaje(
        db, equipo.id_equipo, "Dirección Deportiva", "Informe de planificación de plantilla",
        " · ".join(partes) + ". Revisá Plantel, Contratos y Transferencias para decidir los próximos pasos.",
        "DIRECCION", fecha,
    )


async def _procesar_cesiones(db: AsyncSession, fecha: date, id_partida: int) -> None:
    """Se corre en cada avance de día: si una cesión llega a su fecha de
    devolución, el club que tiene al jugador a préstamo decide si ejerce
    la opción de compra pactada (si la había) o lo devuelve al dueño."""
    vencidas = (await db.execute(
        select(Jugador).where(
            Jugador.id_partida == id_partida,
            Jugador.fin_cesion.is_not(None),
            Jugador.fin_cesion <= fecha,
        )
    )).scalars().all()
    ids_equipo_cesion = {j.id_equipo for j in vencidas if j.id_equipo} | {j.id_equipo_dueno for j in vencidas if j.id_equipo_dueno}
    equipos_cesion_por_id: dict[int, Equipo] = {}
    if ids_equipo_cesion:
        equipos_cesion_por_id = {e.id_equipo: e for e in (
            await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_equipo_cesion)))
        ).scalars().all()}
    for j in vencidas:
        prestamista = equipos_cesion_por_id.get(j.id_equipo)  # quien lo tiene ahora mismo
        dueno = equipos_cesion_por_id.get(j.id_equipo_dueno) if j.id_equipo_dueno else None

        ejercida = False
        if j.opcion_compra and prestamista and dueno and not prestamista.es_usuario:
            plantel_prestamista = (await db.execute(
                select(Jugador).where(Jugador.id_equipo == prestamista.id_equipo)
            )).scalars().all()
            promedio_pos = _promedios_por_posicion(plantel_prestamista).get(j.posicion, 0)
            encaja = j.overall > promedio_pos
            puede_pagar = prestamista.presupuesto_fichajes >= j.opcion_compra
            prob = 0.55 if (encaja and puede_pagar) else 0.1
            ejercida = puede_pagar and random.random() < prob

        if ejercida:
            monto = j.opcion_compra
            prestamista.presupuesto_fichajes -= monto
            dueno.presupuesto_fichajes += monto
            prestamista.presupuesto_salarios = tope_salarial(prestamista.presupuesto_fichajes)
            dueno.presupuesto_salarios = tope_salarial(dueno.presupuesto_fichajes)
            j.salario = salario_esperado(j.valor_mercado, j.edad)
            j.fecha_fin_contrato = fecha + timedelta(days=365 * 3)
            j.id_equipo_dueno = None
            j.fin_cesion = None
            j.opcion_compra = None
            if prestamista.es_usuario:
                await _crear_mensaje(
                    db, prestamista.id_equipo, "Secretaría Técnica", f"Compra ejercida: {j.nombre}",
                    f"Ejerciste la opción de compra: {j.nombre} ya es tuyo de forma permanente por ${money(monto)}.",
                    "MERCADO", fecha,
                )
            if dueno.es_usuario:
                await _crear_mensaje(
                    db, dueno.id_equipo, "Secretaría Técnica", f"Se vendió {j.nombre}",
                    f"{prestamista.nombre} ejerció la opción de compra por {j.nombre} y te pagó ${money(monto)}.",
                    "MERCADO", fecha,
                )
        else:
            nombre_prestamista = prestamista.nombre if prestamista else "?"
            nombre_dueno = dueno.nombre if dueno else "?"
            j.id_equipo = j.id_equipo_dueno
            j.id_equipo_dueno = None
            j.fin_cesion = None
            j.opcion_compra = None
            j.rol = "RESERVA"
            if dueno and dueno.es_usuario:
                await _crear_mensaje(
                    db, dueno.id_equipo, "Secretaría Técnica", f"{j.nombre} volvió de la cesión",
                    f"Terminó su préstamo en {nombre_prestamista} y volvió al plantel.",
                    "MERCADO", fecha,
                )
            if prestamista and prestamista.es_usuario:
                await _crear_mensaje(
                    db, prestamista.id_equipo, "Secretaría Técnica", f"{j.nombre} vuelve a su club",
                    f"Terminó la cesión y {j.nombre} regresó a {nombre_dueno}.",
                    "MERCADO", fecha,
                )


async def _upsert_afiliacion(db: AsyncSession, id_partida: int, id_inversor: int, id_participado: int, delta_porcentaje: int, fecha: date) -> None:
    """Aplica delta_porcentaje (positivo=COMPRAR, negativo=VENDER) a la
    AfiliacionClub del par (inversor, participado) — la crea si no existía,
    la borra si el porcentaje llega a 0, y recalcula tipo_relacion según el
    nuevo % (ver engine/multiclub_engine.py::tipo_relacion_por_porcentaje)."""
    fila = (await db.execute(
        select(AfiliacionClub).where(
            AfiliacionClub.id_partida == id_partida,
            AfiliacionClub.id_equipo_inversor == id_inversor,
            AfiliacionClub.id_equipo_participado == id_participado,
        )
    )).scalars().first()
    porcentaje_actual = fila.porcentaje if fila else 0
    nuevo_porcentaje = max(0, min(100, porcentaje_actual + delta_porcentaje))
    if nuevo_porcentaje <= 0:
        if fila:
            await db.delete(fila)
        return
    tipo = multiclub_engine.tipo_relacion_por_porcentaje(nuevo_porcentaje)
    if fila:
        fila.porcentaje = nuevo_porcentaje
        fila.tipo_relacion = tipo
    else:
        db.add(AfiliacionClub(
            id_partida=id_partida, id_equipo_inversor=id_inversor, id_equipo_participado=id_participado,
            porcentaje=nuevo_porcentaje, tipo_relacion=tipo, fecha_adquisicion=fecha,
        ))


async def _procesar_solicitudes_participacion(db: AsyncSession, fecha: date, id_partida: int) -> None:
    """Se corre en cada avance de día: resuelve SolicitudParticipacion
    PENDIENTE cuya fecha_resolucion ya llegó, en DOS fases secuenciales.
    FASE 1 (DIRECTIVA_PROPIA): tu propia directiva evalúa gastar/cobrar —
    si aprueba, pasa a fase 2 con una nueva fecha_resolucion; si rechaza,
    termina ahí (nunca molesta al club contraparte). FASE 2
    (DIRECTIVA_CONTRAPARTE): la directiva del club objetivo (IA) evalúa si
    acepta ceder/recomprar — si acepta, se mueve la plata y se actualiza
    AfiliacionClub."""
    pendientes = (await db.execute(
        select(SolicitudParticipacion).where(
            SolicitudParticipacion.id_partida == id_partida,
            SolicitudParticipacion.estado == "PENDIENTE",
            SolicitudParticipacion.fecha_resolucion <= fecha,
        )
    )).scalars().all()
    if not pendientes:
        return

    ids_equipo = {s.id_equipo_iniciador for s in pendientes} | {s.id_equipo_contraparte for s in pendientes}
    equipos_por_id: dict[int, Equipo] = {e.id_equipo: e for e in (
        await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_equipo)))
    ).scalars().all()}
    partida = await db.get(Partida, id_partida)
    confianza = partida.confianza_directiva if partida else directiva_engine.CONFIANZA_INICIAL

    for s in pendientes:
        iniciador = equipos_por_id.get(s.id_equipo_iniciador)
        contraparte = equipos_por_id.get(s.id_equipo_contraparte)
        if not iniciador or not contraparte:
            continue
        nombre_op = "compra" if s.operacion == "COMPRAR" else "venta"

        if s.fase == "DIRECTIVA_PROPIA":
            veredicto = multiclub_engine.evaluar_directiva_propia(confianza, s.monto, iniciador.presupuesto_fichajes, s.operacion)
            if veredicto["estado"] == "RECHAZADA":
                s.estado = "RECHAZADA_PROPIA"
                if iniciador.es_usuario:
                    await _crear_mensaje(
                        db, iniciador.id_equipo, "Directiva del Club", f"Operación rechazada: {contraparte.nombre}",
                        f"Tu directiva rechazó la {nombre_op} de participación en {contraparte.nombre}. {veredicto['motivo']}",
                        "SISTEMA", fecha,
                    )
                continue
            s.fase = "DIRECTIVA_CONTRAPARTE"
            s.fecha_resolucion = fecha + timedelta(days=multiclub_engine.dias_espera_directiva_contraparte(s.porcentaje))
            if iniciador.es_usuario:
                await _crear_mensaje(
                    db, iniciador.id_equipo, "Directiva del Club", f"Operación en curso: {contraparte.nombre}",
                    f"Tu directiva autorizó la {nombre_op} — ahora queda en manos de la directiva de {contraparte.nombre}, "
                    f"respuesta estimada el {s.fecha_resolucion.strftime('%d/%m/%Y')}.",
                    "SISTEMA", fecha,
                )
            continue

        # FASE 2: DIRECTIVA_CONTRAPARTE
        presupuesto_referencia_liga = await _presupuesto_referencia_liga(db, contraparte)
        afiliacion_actual = (await db.execute(
            select(AfiliacionClub).where(
                AfiliacionClub.id_partida == id_partida,
                AfiliacionClub.id_equipo_inversor == s.id_equipo_iniciador,
                AfiliacionClub.id_equipo_participado == s.id_equipo_contraparte,
            )
        )).scalars().first()
        porcentaje_actual = afiliacion_actual.porcentaje if afiliacion_actual else 0
        delta = s.porcentaje if s.operacion == "COMPRAR" else -s.porcentaje
        tipo_relevante = multiclub_engine.tipo_relacion_por_porcentaje(porcentaje_actual + delta) or "MINORITARIO"
        veredicto = multiclub_engine.evaluar_directiva_contraparte(
            contraparte.reputacion, contraparte.presupuesto_fichajes, presupuesto_referencia_liga, tipo_relevante, s.operacion,
        )
        if veredicto["estado"] == "RECHAZADA":
            s.estado = "RECHAZADA_CONTRAPARTE"
            if iniciador.es_usuario:
                await _crear_mensaje(
                    db, iniciador.id_equipo, "Directiva del Club", f"Operación rechazada: {contraparte.nombre}",
                    f"La directiva de {contraparte.nombre} rechazó la {nombre_op}. {veredicto['motivo']}",
                    "SISTEMA", fecha,
                )
            continue

        if s.operacion == "COMPRAR":
            iniciador.presupuesto_fichajes -= s.monto
            contraparte.presupuesto_fichajes += s.monto
        else:
            contraparte.presupuesto_fichajes -= s.monto
            iniciador.presupuesto_fichajes += s.monto
        iniciador.presupuesto_salarios = tope_salarial(iniciador.presupuesto_fichajes)
        contraparte.presupuesto_salarios = tope_salarial(contraparte.presupuesto_fichajes)
        await _upsert_afiliacion(db, id_partida, s.id_equipo_iniciador, s.id_equipo_contraparte, delta, fecha)
        s.estado = "CONCRETADA"
        if iniciador.es_usuario:
            await _crear_mensaje(
                db, iniciador.id_equipo, "Directiva del Club", f"Operación concretada: {contraparte.nombre}",
                f"Se concretó la {nombre_op} de {s.porcentaje}% de {contraparte.nombre} por ${money(s.monto)}.",
                "SISTEMA", fecha,
            )


async def _procesar_progreso_scouting(db: AsyncSession, fecha: date, id_partida: int) -> None:
    """Se corre en cada avance de día: todo ojeador con un objetivo asignado
    suma progreso a su reporte, más rápido cuanto mejor sea su `calidad`."""
    ojeadores = (await db.execute(
        select(Ojeador).where(Ojeador.id_partida == id_partida, Ojeador.id_jugador_asignado.is_not(None))
    )).scalars().all()
    if not ojeadores:
        return
    ids_equipo_ojeadores = {o.id_equipo for o in ojeadores}
    bonos_red_ojeadores = await _bonos_red_por_equipos(db, id_partida, ids_equipo_ojeadores)
    claves = {(o.id_equipo, o.id_jugador_asignado) for o in ojeadores}
    existentes = (await db.execute(
        select(ReporteScouting).where(
            ReporteScouting.id_partida == id_partida,
            or_(*[
                (ReporteScouting.id_equipo == id_eq) & (ReporteScouting.id_jugador == id_jug)
                for id_eq, id_jug in claves
            ])
        )
    )).scalars().all()
    reportes = {(r.id_equipo, r.id_jugador): r for r in existentes}
    for o in ojeadores:
        clave = (o.id_equipo, o.id_jugador_asignado)
        reporte = reportes.get(clave)
        if not reporte:
            reporte = ReporteScouting(id_equipo=o.id_equipo, id_jugador=o.id_jugador_asignado, id_partida=id_partida, progreso=0)
            db.add(reporte)
            reportes[clave] = reporte
        # Bono de red multiclub: acelera el progreso de cualquier reporte en
        # curso, sin importar quién sea el ojeador.
        bono_analitica = _bono_analitica(bonos_red_ojeadores.get(o.id_equipo))
        reporte.progreso = min(100, reporte.progreso + max(1, o.calidad // 15) + bono_analitica)
        reporte.fecha_ultimo_reporte = fecha


PROB_MEJORA_INDIVIDUAL = 0.06


COSTO_ENERGIA_INDIVIDUAL = 5


async def _procesar_entrenamiento_individual(db: AsyncSession, fecha: date, id_partida: int) -> None:
    """Se corre una vez por semana de juego (los lunes): todo jugador con un
    `foco_individual` fijado tiene chance de mejorar algún atributo de ese
    grupo, además de (e independiente de) lo que le toque por el plan de
    entrenamiento grupal del equipo — ver aplicar_entrenamiento."""
    if fecha.weekday() != 0:
        return
    jugadores = (await db.execute(
        select(Jugador).where(
            Jugador.id_partida == id_partida,
            Jugador.foco_individual.is_not(None),
            Jugador.categoria == "PRIMERA",
            Jugador.edad < 29,
            Jugador.id_equipo.is_not(None),
        )
    )).scalars().all()
    if not jugadores:
        return
    bonos_red = await _bonos_red_por_equipos(db, id_partida, {j.id_equipo for j in jugadores})
    for j in jugadores:
        grupo = grupo_atributos(j.foco_individual)
        if not grupo:
            continue
        prob = PROB_MEJORA_INDIVIDUAL + _bono_centro(bonos_red.get(j.id_equipo))
        cambio = False
        for atributo in grupo:
            if random.random() < prob and getattr(j, atributo) < j.potencial:
                setattr(j, atributo, min(j.potencial, getattr(j, atributo) + 1))
                cambio = True
        if cambio:
            recalcular_derivados_jugador(j)
        j.energia = max(0, j.energia - COSTO_ENERGIA_INDIVIDUAL)


CONFEDERACIONES = ["UEFA", "CONMEBOL"]


async def _procesar_fin_temporada_confederacion(db: AsyncSession, fecha: date, id_partida: int, confederacion: str) -> bool:
    """Igual que la versión vieja (única) de esta función, pero acotada a
    UNA confederación — UEFA y CONMEBOL corren temporadas independientes
    (arrancan/cierran en fechas reales distintas), así que cada una
    envejece a SUS jugadores y rearma SU fixture (ligas + torneos
    internacionales) cuando termina, sin tocar a la otra."""
    ligas = (await db.execute(
        select(Liga).where(Liga.id_partida == id_partida, Liga.confederacion == confederacion)
    )).scalars().all()
    if not ligas:
        return False
    # Si esta confederación todavía no arrancó su primera temporada (la
    # otra, la que no eligió el usuario, arranca diferida — ver
    # _procesar_arranques_diferidos), no hay "fin de temporada" que
    # detectar: sin CicloTemporada no hay fixtures propios, y sin fixtures
    # el chequeo de abajo daría falso positivo (0 pendientes = "terminó").
    ciclo_actual = await db.get(CicloTemporada, (id_partida, confederacion))
    if not ciclo_actual:
        return False
    ids_liga = [l.id_liga for l in ligas]

    competencias_confed = list(COMPETENCIAS[confederacion].values())
    queda_pendiente_liga = (await db.execute(
        select(Calendario.id_fixture).where(
            Calendario.id_partida == id_partida, Calendario.tipo == "LIGA",
            Calendario.id_liga.in_(ids_liga), Calendario.jugado.is_(False),
        ).limit(1)
    )).first()
    queda_pendiente_copa = (await db.execute(
        select(Calendario.id_fixture).where(
            Calendario.id_partida == id_partida, Calendario.tipo == "COPA",
            Calendario.competencia.in_(competencias_confed), Calendario.jugado.is_(False),
        ).limit(1)
    )).first()
    if queda_pendiente_liga or queda_pendiente_copa:
        return False

    from seed import generar_temporada_confederacion, fecha_inicio_confederacion  # import local: evita import circular

    equipos = (await db.execute(select(Equipo).where(Equipo.id_liga.in_(ids_liga)))).scalars().all()
    ids_equipo = [e.id_equipo for e in equipos]
    todos_jugadores = (await db.execute(select(Jugador).where(Jugador.id_equipo.in_(ids_equipo)))).scalars().all() if ids_equipo else []
    equipo_usuario = next((e for e in equipos if e.es_usuario), None)
    nombres_equipo = {e.id_equipo: e.nombre for e in equipos}

    # Foto de cada jugador ANTES de envejecer/desarrollar — así "Historial"
    # muestra cómo termina cada temporada, no el arranque de la siguiente.
    for j in todos_jugadores:
        db.add(HistorialTemporada(
            id_partida=id_partida, id_jugador=j.id_jugador, nombre_jugador=j.nombre, temporada=fecha.year,
            id_equipo=j.id_equipo, nombre_equipo=nombres_equipo.get(j.id_equipo, "Sin club"),
            edad=j.edad, overall=j.overall, potencial=j.potencial,
            valor_mercado=j.valor_mercado, salario=j.salario, rol=j.rol,
        ))

    retirados = procesar_fin_temporada(todos_jugadores)
    for j in retirados:
        id_equipo_original = j.id_equipo
        posicion_original = j.posicion
        nombre_retirado = j.nombre
        await db.delete(j)
        if id_equipo_original is not None:
            # El regen es un juvenil de 17-19 años: entra directo como
            # reserva del plantel de Primera (no hay reacomodo automático de
            # titular — si el club se queda con un hueco, lo resuelve el
            # usuario en Tácticas, o a un club de la IA simplemente no le
            # importa jugar con ese hueco).
            regen_data = generar_regen(posicion_original)
            regen_data["fecha_fin_contrato"] = fecha + timedelta(days=365 * random.randint(2, 4))
            db.add(Jugador(id_partida=id_partida, id_equipo=id_equipo_original, **regen_data))
            if equipo_usuario and id_equipo_original == equipo_usuario.id_equipo:
                await _crear_mensaje(
                    db, equipo_usuario.id_equipo, "Secretaría Técnica", f"{nombre_retirado} se retira",
                    f"{nombre_retirado} colgó los botines después de esta temporada. Un juvenil se suma al plantel para ocupar su lugar.",
                    "SISTEMA", fecha,
                )

    # Intake anual de la Academia: una vez por temporada, solo para clubes
    # que YA tienen Academia generada (los que nadie miró nunca no generan
    # nada acá — nacen completos en 15 recién la primera vez que se miran).
    jugadores_academia_por_club: dict[int, list[Jugador]] = {}
    jugadores_primera_por_club: dict[int, list[Jugador]] = {}
    for j in todos_jugadores:
        if j.categoria != "PRIMERA":
            jugadores_academia_por_club.setdefault(j.id_equipo, []).append(j)
        else:
            jugadores_primera_por_club.setdefault(j.id_equipo, []).append(j)

    bonos_red = await _bonos_red_por_equipos(db, id_partida, set(ids_equipo))
    for equipo_academia in equipos:
        academia_club = jugadores_academia_por_club.get(equipo_academia.id_equipo)
        if not academia_club:
            continue
        liga_club = next((l for l in ligas if l.id_liga == equipo_academia.id_liga), None)
        pais_club = liga_club.pais if liga_club else "Argentina"
        bono_red_club = bonos_red.get(equipo_academia.id_equipo)
        factor_club = academia_engine.calcular_factor_desde_plantel(
            jugadores_primera_por_club.get(equipo_academia.id_equipo, []), _bono_instalaciones_juveniles(bono_red_club),
        )
        bono_captacion = _bono_captacion_juvenil(bono_red_club)
        for categoria_intake in ("SUB13", "SUB15", "SUB18"):
            cantidad_actual = sum(1 for j in academia_club if j.categoria == categoria_intake)
            n_candidatos = calcular_n_candidatos_intake(cantidad_actual, bono_captacion)
            faltaban = cantidad_actual < academia_engine.TAMANIO_MINIMO_CATEGORIA
            for _ in range(n_candidatos):
                pos = random.choice(["POR", "DEF", "MED", "DEL"])
                datos_candidato = academia_engine.generar_jugador_academia(categoria_intake, pais_club, pos, factor_club)
                _completar_contrato_juvenil(datos_candidato, fecha)
                if equipo_academia.es_usuario:
                    # Queda pendiente de revisión — el usuario decide en la Academia.
                    db.add(Jugador(
                        id_partida=id_partida, id_equipo=None,
                        id_equipo_intake=equipo_academia.id_equipo, **datos_candidato,
                    ))
                else:
                    # Clubes de la IA: se resuelve en el momento, sin dejar
                    # ninguna fila pendiente — acepta lo que hace falta para
                    # llegar a 15, o algún golpe de suerte si ya estaba completo.
                    aceptar = faltaban or (random.random() < 0.3 and datos_candidato["potencial"] >= 70)
                    if aceptar:
                        db.add(Jugador(id_partida=id_partida, id_equipo=equipo_academia.id_equipo, **datos_candidato))

    # Evaluación de objetivo/despido/fin de contrato del DT — tiene que
    # correr ANTES del reset de puntos de abajo, porque necesita la tabla
    # real de la temporada que recién termina.
    await _evaluar_temporada_dt(db, fecha, id_partida, equipos)

    for e in equipos:
        e.puntos = 0
        e.jugados = 0
        e.ganados = 0
        e.empatados = 0
        e.perdidos = 0
        e.goles_favor = 0
        e.goles_contra = 0
        # El tope de sueldos (fair play financiero) también se recalcula acá
        # como red de seguridad — en la práctica ya se mantiene al día
        # durante toda la temporada, cada vez que presupuesto_fichajes
        # cambia (ver tope_salarial en engine/data_gen.py).
        e.presupuesto_salarios = tope_salarial(e.presupuesto_fichajes)

    temporada_nueva = ciclo_actual.temporada + 1
    fecha_inicio_nueva = fecha_inicio_confederacion(confederacion, temporada_nueva)
    await generar_temporada_confederacion(db, id_partida, confederacion, temporada_nueva, fecha_inicio_nueva)

    if equipo_usuario:
        # Aviso proactivo de continuidad: solo para TU club (calcularlo para
        # las ~180 plantillas de toda la partida no tiene sentido ni es
        # barato), y solo jugadores con contrato por vencer pronto — así el
        # usuario se entera ANTES de intentar renovar a ciegas.
        ids_retirados = {r.id_jugador for r in retirados}
        plantel_usuario = [
            j for j in jugadores_primera_por_club.get(equipo_usuario.id_equipo, [])
            if j.id_jugador not in ids_retirados
        ]
        for j in plantel_usuario:
            dias_restantes = (j.fecha_fin_contrato - fecha).days if j.fecha_fin_contrato else None
            if dias_restantes is None or dias_restantes > 365:
                continue
            disposicion = disposicion_renovar(j.overall, j.edad, j.rol, j.moral, equipo_usuario.reputacion, j.relacion_dt)
            if disposicion["probabilidad"] < 0.4:
                await _crear_mensaje(
                    db, equipo_usuario.id_equipo, "Secretaría Técnica", f"{j.nombre}: dudas sobre su continuidad",
                    f"El entorno de {j.nombre} hace saber que no está del todo conforme con su continuidad: \"{disposicion['motivo']}\"",
                    "JUGADOR", fecha,
                )

        await _crear_mensaje(
            db, equipo_usuario.id_equipo, "Directiva del Club", "Arranca una nueva temporada",
            "Terminó la temporada: se armó el fixture nuevo y varios jugadores envejecieron, mejoraron o "
            "declinaron según su edad. Revisá cómo quedó tu plantel y su valor de mercado.",
            "SISTEMA", fecha,
        )
    return True


async def _procesar_fin_temporada_si_corresponde(db: AsyncSession, fecha: date, id_partida: int) -> bool:
    """Corre el chequeo de fin de temporada de las dos confederaciones —
    cada una es independiente, así que puede terminar una sin la otra."""
    resultados = [
        await _procesar_fin_temporada_confederacion(db, fecha, id_partida, confederacion)
        for confederacion in CONFEDERACIONES
    ]
    return any(resultados)


async def _procesar_arranques_diferidos(db: AsyncSession, fecha: date, id_partida: int) -> None:
    """La confederación que NO eligió el usuario al crear la carrera no
    arranca su primera temporada hasta que `fecha_actual` llegue a su fecha
    real de inicio (1 de agosto para UEFA, 1 de enero para CONMEBOL) — acá
    se detecta ese momento (una sola vez, el día que se cumple) y se arma su
    primera temporada (ligas "completas" + sus 2 torneos internacionales)."""
    if fecha.day != 1:
        return
    from seed import MES_INICIO_CONFEDERACION, generar_temporada_confederacion

    for confederacion, mes_inicio in MES_INICIO_CONFEDERACION.items():
        if fecha.month != mes_inicio:
            continue
        ya_existe = await db.get(CicloTemporada, (id_partida, confederacion))
        if ya_existe:
            continue
        await generar_temporada_confederacion(db, id_partida, confederacion, fecha.year, fecha)


SIGUIENTE_RONDA_ELIMINATORIA = {"OCTAVOS": "CUARTOS", "CUARTOS": "SEMIS", "SEMIS": "FINAL"}


async def _crear_eliminatoria(
    db: AsyncSession, id_partida: int, competencia: str, ronda: str,
    cruces: list[tuple[int, int]], fecha_inicio_confed: date,
) -> None:
    """Crea las filas IDA+VUELTA de una eliminatoria (o, si `ronda` es
    "FINAL", el único partido a partido único)."""
    if ronda == "FINAL":
        if len(cruces) != 1:
            return
        local, visita = cruces[0]
        db.add(Calendario(
            id_partida=id_partida, id_liga=None, num_jornada=1,
            fecha=fecha_ronda(fecha_inicio_confed, OFFSET_SEMANAS_ELIMINATORIA["FINAL"]),
            id_local=local, id_visitante=visita, tipo="COPA", competencia=competencia, ronda_copa="FINAL",
        ))
        return
    fecha_ida = fecha_ronda(fecha_inicio_confed, OFFSET_SEMANAS_ELIMINATORIA[f"{ronda}_IDA"])
    fecha_vuelta = fecha_ronda(fecha_inicio_confed, OFFSET_SEMANAS_ELIMINATORIA[f"{ronda}_VUELTA"])
    for local, visita in cruces:
        db.add(Calendario(
            id_partida=id_partida, id_liga=None, num_jornada=1, fecha=fecha_ida,
            id_local=local, id_visitante=visita, tipo="COPA", competencia=competencia, ronda_copa=f"{ronda}_IDA",
        ))
        db.add(Calendario(
            id_partida=id_partida, id_liga=None, num_jornada=1, fecha=fecha_vuelta,
            id_local=visita, id_visitante=local, tipo="COPA", competencia=competencia, ronda_copa=f"{ronda}_VUELTA",
        ))


async def _avanzar_una_competencia_si_corresponde(db: AsyncSession, id_partida: int, competencia: str, confederacion: str) -> None:
    filas = (await db.execute(
        select(Calendario).where(Calendario.id_partida == id_partida, Calendario.tipo == "COPA", Calendario.competencia == competencia)
    )).scalars().all()
    if not filas:
        return
    ciclo = await db.get(CicloTemporada, (id_partida, confederacion))
    if not ciclo:
        return
    por_ronda: dict[str, list[Calendario]] = {}
    for f in filas:
        por_ronda.setdefault(f.ronda_copa, []).append(f)

    # Fase de grupos -> octavos: los 2 primeros de cada grupo. Orden
    # alfabético (GRUPO_A, GRUPO_B, ...) para que el cruce A-B/C-D/... de
    # emparejar_octavos sea determinístico, sin depender del orden en que
    # la consulta devolvió las filas.
    rondas_grupo = sorted(r for r in por_ronda if r.startswith("GRUPO_"))
    if rondas_grupo and "OCTAVOS_IDA" not in por_ronda and all(f.jugado for r in rondas_grupo for f in por_ronda[r]):
        clasificados_por_grupo: dict[str, list[int]] = {}
        for r in rondas_grupo:
            ids_equipo_grupo = sorted({f.id_local for f in por_ronda[r]} | {f.id_visitante for f in por_ronda[r]})
            jugados = [
                {"id_local": f.id_local, "id_visitante": f.id_visitante, "goles_local": f.goles_local, "goles_visitante": f.goles_visitante}
                for f in por_ronda[r]
            ]
            clasificados_por_grupo[r] = posiciones_grupo(ids_equipo_grupo, jugados)[:2]
        cruces = emparejar_octavos(clasificados_por_grupo)
        await _crear_eliminatoria(db, id_partida, competencia, "OCTAVOS", cruces, ciclo.fecha_inicio)
        return

    # Eliminatorias: octavos -> cuartos -> semis -> final.
    for ronda in ("OCTAVOS", "CUARTOS", "SEMIS"):
        clave_ida, clave_vuelta = f"{ronda}_IDA", f"{ronda}_VUELTA"
        if clave_ida not in por_ronda or clave_vuelta not in por_ronda:
            continue
        siguiente = SIGUIENTE_RONDA_ELIMINATORIA[ronda]
        ya_avanzada = "FINAL" in por_ronda if siguiente == "FINAL" else f"{siguiente}_IDA" in por_ronda
        if ya_avanzada:
            continue
        if not (all(f.jugado for f in por_ronda[clave_ida]) and all(f.jugado for f in por_ronda[clave_vuelta])):
            continue

        idas_por_par = {frozenset((f.id_local, f.id_visitante)): f for f in por_ronda[clave_ida]}
        ganadores = []
        for vuelta_f in por_ronda[clave_vuelta]:
            ida_f = idas_por_par.get(frozenset((vuelta_f.id_local, vuelta_f.id_visitante)))
            if not ida_f:
                continue
            ida_dict = {"id_local": ida_f.id_local, "id_visitante": ida_f.id_visitante, "goles_local": ida_f.goles_local, "goles_visitante": ida_f.goles_visitante}
            vuelta_dict = {"id_local": vuelta_f.id_local, "id_visitante": vuelta_f.id_visitante, "goles_local": vuelta_f.goles_local, "goles_visitante": vuelta_f.goles_visitante}
            ganador, empate = ganador_eliminatoria(ida_dict, vuelta_dict)
            if empate:
                ganador = random.choice([vuelta_f.id_local, vuelta_f.id_visitante])
                vuelta_f.desempate_id_equipo = ganador
            ganadores.append(ganador)

        await _crear_eliminatoria(
            db, id_partida, competencia, siguiente,
            [(ganadores[i], ganadores[i + 1]) for i in range(0, len(ganadores) - 1, 2)],
            ciclo.fecha_inicio,
        )
        return

    # Final jugada: si terminó empatada se define por penales al azar.
    if "FINAL" in por_ronda:
        final = por_ronda["FINAL"][0]
        if final.jugado and final.goles_local == final.goles_visitante and not final.desempate_id_equipo:
            final.desempate_id_equipo = random.choice([final.id_local, final.id_visitante])


async def _avanzar_torneos_internacionales_si_corresponde(db: AsyncSession, id_partida: int, fecha_actual: date) -> None:
    """Se llama cada vez que se resuelve algún partido de copa (propio o
    ajeno): si una fase quedó completa, arma la siguiente."""
    for confederacion, nombres in COMPETENCIAS.items():
        for competencia in nombres.values():
            await _avanzar_una_competencia_si_corresponde(db, id_partida, competencia, confederacion)


async def _procesar_partidos_ajenos_del_dia(db: AsyncSession, fecha: date, id_partida: int, equipo_usuario: Equipo | None = None) -> None:
    """Se corre en cada avance de día: resuelve partidos (de liga o de copa)
    de OTROS equipos en fechas donde el usuario no tiene nada ese día.
    Antes, con un solo calendario compartido por todas las ligas, esto nunca
    hacía falta — el usuario siempre tenía partido en cada jornada y
    `_cerrar_jornada_del_dia` se encargaba de todo lo demás de esa fecha.
    Ahora hay fechas de liga/copa de OTRA confederación (o de una liga
    "completa" que no es la del usuario) donde puede no tener nada.

    `equipo_usuario` se puede pasar ya resuelto (el/los llamadores de este
    avance de día ya lo tienen) para ahorrarse un viaje a la base por cada
    día simulado — cada consulta a Neon tarda ~200ms, así que evitar
    reconsultarlo suma rápido en un salto de varias semanas."""
    if equipo_usuario is None:
        equipo_usuario = await _equipo_usuario(db, id_partida)
    pendientes = (await db.execute(
        select(Calendario).where(Calendario.id_partida == id_partida, Calendario.jugado.is_(False), Calendario.fecha <= fecha)
    )).scalars().all()
    if equipo_usuario:
        pendientes = [f for f in pendientes if equipo_usuario.id_equipo not in (f.id_local, f.id_visitante)]
    if not pendientes:
        return

    ids_equipos = {id_eq for f in pendientes for id_eq in (f.id_local, f.id_visitante)}
    equipos_por_id = {e.id_equipo: e for e in (await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_equipos)))).scalars().all()}
    tacticas_por_id = {t.id_equipo: t for t in (await db.execute(select(Tactica).where(Tactica.id_equipo.in_(ids_equipos)))).scalars().all()}
    jugadores_por_equipo: dict[int, list[Jugador]] = {}
    for j in (await db.execute(select(Jugador).where(Jugador.id_equipo.in_(ids_equipos)))).scalars().all():
        jugadores_por_equipo.setdefault(j.id_equipo, []).append(j)
    bonos_red = await _bonos_red_por_equipos(db, id_partida, ids_equipos)

    for f in pendientes:
        local = equipos_por_id.get(f.id_local)
        visit = equipos_por_id.get(f.id_visitante)
        tac_local = tacticas_por_id.get(f.id_local)
        tac_visit = tacticas_por_id.get(f.id_visitante)
        if not local or not visit or not tac_local or not tac_visit:
            continue
        plantel_local = jugadores_por_equipo.get(f.id_local, [])
        plantel_visit = jugadores_por_equipo.get(f.id_visitante, [])
        jl = _once_titular(plantel_local)
        jv = _once_titular(plantel_visit)
        dict_local = [{"id_jugador": p.id_jugador, "nombre": p.nombre, "posicion": p.posicion,
                        "ataque": p.ataque, "defensa": p.defensa, "energia": p.energia, "duty": p.duty} for p in jl]
        dict_visit = [{"id_jugador": p.id_jugador, "nombre": p.nombre, "posicion": p.posicion,
                        "ataque": p.ataque, "defensa": p.defensa, "energia": p.energia, "duty": p.duty} for p in jv]
        _aplicar_vestuario(dict_local, plantel_local, local.id_capitan)
        _aplicar_vestuario(dict_visit, plantel_visit, visit.id_capitan)
        tac_local_dict = {"formacion": tac_local.formacion, "mentalidad": tac_local.mentalidad, "presion": tac_local.presion}
        tac_visit_dict = {"formacion": tac_visit.formacion, "mentalidad": tac_visit.mentalidad, "presion": tac_visit.presion}
        fm_local = _factor_medico(bonos_red.get(f.id_local))
        fm_visit = _factor_medico(bonos_red.get(f.id_visitante))
        resultado = simulate_match(
            dict_local, dict_visit, tac_local_dict, tac_visit_dict, ia_local=True, ia_visit=True,
            factor_medico_local=fm_local, factor_medico_visit=fm_visit,
        )
        _aplicar_efectos_fisicos(jl, jv, plantel_local, plantel_visit, resultado, fm_local, fm_visit)
        await _procesar_addons_cumplidos(db, {p.id_jugador for p in jl + jv}, fecha)
        f.jugado = True
        f.goles_local = resultado["gh"]
        f.goles_visitante = resultado["gv"]
        if f.tipo == "LIGA":
            local.jugados += 1
            visit.jugados += 1
            local.goles_favor += resultado["gh"]
            local.goles_contra += resultado["gv"]
            visit.goles_favor += resultado["gv"]
            visit.goles_contra += resultado["gh"]
            if resultado["gh"] > resultado["gv"]:
                local.ganados += 1
                local.puntos += 3
                visit.perdidos += 1
            elif resultado["gv"] > resultado["gh"]:
                visit.ganados += 1
                visit.puntos += 3
                local.perdidos += 1
            else:
                local.empatados += 1
                local.puntos += 1
                visit.empatados += 1
                visit.puntos += 1

    await _avanzar_torneos_internacionales_si_corresponde(db, id_partida, fecha)
    await _procesar_fin_temporada_si_corresponde(db, fecha, id_partida)


def _interes_desde_probabilidad(probabilidad: float) -> str:
    if probabilidad >= 0.6:
        return "alto"
    if probabilidad >= 0.35:
        return "medio"
    return "bajo"


async def _nombres_competencia(db: AsyncSession, id_partida: int) -> dict:
    """Nombre a mostrar de cada código de copa internacional para una
    partida: el fijo por defecto, salvo que la partida tenga nombres
    personalizados guardados en Partida.competencias_json (dataset editor
    de datos reales, ver seed.py::crear_partida)."""
    partida = await db.get(Partida, id_partida)
    nombres = dict(NOMBRES_COMPETENCIA_DEFAULT)
    if partida and partida.competencias_json:
        nombres.update(json.loads(partida.competencias_json))
    return nombres


def _once_titular(plantel: list[Jugador]) -> list[Jugador]:
    """Los 11 que realmente juegan: TITULAR primero; si por lesiones u otra
    razón no llegan a 11, se completa con SUPLENTE (mejor overall primero).
    La RESERVA nunca viaja con el plantel del partido, ni siquiera si faltan
    jugadores — en ese caso el equipo sale a la cancha con menos de 11."""
    disponibles = [p for p in plantel if not p.lesionado and not p.en_convocatoria]
    titulares = [p for p in disponibles if p.rol == "TITULAR"]
    if len(titulares) >= 11:
        return titulares[:11]

    suplentes = sorted(
        (p for p in disponibles if p.rol == "SUPLENTE"),
        key=lambda p: p.overall, reverse=True,
    )
    return titulares + suplentes[:11 - len(titulares)]


MULTIPLICADOR_VESTUARIO_MIN = 0.95


MULTIPLICADOR_VESTUARIO_RANGO = 0.10


ATENUACION_LIDERAZGO_CAPITAN = 0.4


def _puntaje_vestuario(plantel: list[Jugador], id_capitan: int | None) -> float:
    """Dinámica de vestuario (0-100): moral promedio del plantel PRIMERA,
    penalizada si el plantel está muy dividido de ánimo (desviación
    estándar alta) — un capitán con buen liderazgo atenúa ese castigo."""
    morales = [j.moral for j in plantel if j.categoria == "PRIMERA"]
    if not morales:
        return 75.0
    promedio = sum(morales) / len(morales)
    varianza = sum((m - promedio) ** 2 for m in morales) / len(morales)
    desviacion = varianza ** 0.5
    capitan = next((j for j in plantel if j.id_jugador == id_capitan), None) if id_capitan else None
    atenuacion = 1 - (capitan.liderazgo / 100 * ATENUACION_LIDERAZGO_CAPITAN) if capitan else 1.0
    return max(0.0, min(100.0, promedio - desviacion * atenuacion))


def _aplicar_vestuario(dict_equipo: list[dict], plantel: list[Jugador], id_capitan: int | None) -> None:
    """Traduce el puntaje de vestuario en un multiplicador chico y parejo
    de ataque/defensa para todo el equipo — a diferencia del marcaje
    (ver _aplicar_marcaje), esto es una condición estructural del club:
    corre en TODOS sus partidos, no solo en los que mira el usuario."""
    mult = MULTIPLICADOR_VESTUARIO_MIN + (_puntaje_vestuario(plantel, id_capitan) / 100) * MULTIPLICADOR_VESTUARIO_RANGO
    for p in dict_equipo:
        p["ataque"] = round(p["ataque"] * mult)
        p["defensa"] = round(p["defensa"] * mult)


async def _preparar_lineup(db: AsyncSession, fixture: Calendario):
    local = await db.get(Equipo, fixture.id_local)
    visit = await db.get(Equipo, fixture.id_visitante)
    tac_local = await db.get(Tactica, fixture.id_local)
    tac_visit = await db.get(Tactica, fixture.id_visitante)

    plantel_local = (await db.execute(select(Jugador).where(Jugador.id_equipo == fixture.id_local))).scalars().all()
    plantel_visit = (await db.execute(select(Jugador).where(Jugador.id_equipo == fixture.id_visitante))).scalars().all()

    jl = _once_titular(plantel_local)
    jv = _once_titular(plantel_visit)

    dict_local = [{"id_jugador": p.id_jugador, "nombre": p.nombre, "posicion": p.posicion,
                    "ataque": p.ataque, "defensa": p.defensa, "energia": p.energia, "duty": p.duty} for p in jl]
    dict_visit = [{"id_jugador": p.id_jugador, "nombre": p.nombre, "posicion": p.posicion,
                    "ataque": p.ataque, "defensa": p.defensa, "energia": p.energia, "duty": p.duty} for p in jv]
    _aplicar_vestuario(dict_local, plantel_local, local.id_capitan)
    _aplicar_vestuario(dict_visit, plantel_visit, visit.id_capitan)

    tac_local_dict = {"formacion": tac_local.formacion, "mentalidad": tac_local.mentalidad, "presion": tac_local.presion}
    tac_visit_dict = {"formacion": tac_visit.formacion, "mentalidad": tac_visit.mentalidad, "presion": tac_visit.presion}

    return local, visit, plantel_local, plantel_visit, jl, jv, dict_local, dict_visit, tac_local_dict, tac_visit_dict


PENALIDAD_ATAQUE_MARCADO = 0.65


PENALIDAD_DEFENSA_MARCADOR = 0.98


def _aplicar_marcaje(dict_local: list[dict], dict_visit: list[dict], id_jugador_marcado: int | None) -> None:
    """Instrucción de rival: marcar de cerca a UN jugador rival (DEL/MED)
    para el próximo partido — reduce su aporte de ataque (y por lo tanto
    su chance de ser goleador, ver _pick_scorer) a costa de un poco de
    solidez defensiva pareja en todo el equipo que lo marca, por
    reacomodarse para seguirlo. No persiste nada: es una elección efímera
    del usuario para su próximo partido, mandada como parámetro al armar
    la simulación. Si el jugador marcado no está en ninguna de las dos
    listas (se transfirió, no es titular, etc.), no hace nada."""
    if not id_jugador_marcado:
        return
    for equipo_marcado, equipo_marcador in ((dict_visit, dict_local), (dict_local, dict_visit)):
        objetivo = next((p for p in equipo_marcado if p["id_jugador"] == id_jugador_marcado), None)
        if objetivo:
            objetivo["ataque"] = round(objetivo["ataque"] * PENALIDAD_ATAQUE_MARCADO)
            for p in equipo_marcador:
                p["defensa"] = round(p["defensa"] * PENALIDAD_DEFENSA_MARCADOR)
            return


TONOS_CHARLA = {"EFUSIVA": 0, "CALMA": 1, "EXIGENTE": 2}


INDICE_CORRECTO_CHARLA = {"PERDIO": 0, "EMPATO": 1, "GANO": 2}


DELTA_POR_DISTANCIA_CHARLA = {0: 4, 1: 1, 2: -3}


def _delta_charla(tono: str, resultado: str) -> int:
    """Charla post-partido: EFUSIVA es lo que corresponde si se perdió,
    CALMA si empató, EXIGENTE si ganó — cuanto más lejos el tono elegido
    del que corresponde, peor el efecto (puede hasta bajar la moral)."""
    distancia = abs(TONOS_CHARLA[tono] - INDICE_CORRECTO_CHARLA[resultado])
    return DELTA_POR_DISTANCIA_CHARLA[distancia]


def _calcular_efectos_fisicos(
    plantel_local: list[Jugador], plantel_visit: list[Jugador], resultado: dict,
    factor_medico_local: float = 1.0, factor_medico_visit: float = 1.0,
) -> list[dict]:
    """Calcula desgaste + lesiones nuevas + recuperación de lesiones previas
    + ajuste de moral para los planteles de ambos equipos, SIN tocar los
    objetos ORM — devuelve una lista de dicts listos para un UPDATE masivo
    (ver _cerrar_jornada_del_dia). Usar esto (en vez de mutar atributos uno
    por uno) es lo que evita que resolver una jornada entera (30-40
    partidos, ~2000 jugadores) tarde minutos: si se mutan los objetos ORM
    directamente, SQLAlchemy solo agrupa las actualizaciones en un solo
    lote (executemany) cuando el VALOR realmente cambia igual en todas las
    filas — apenas un jugador difiere (por ejemplo, el único campo que
    cambió fue `semanas_lesion` y no `energia`), el lote se rompe y termina
    mandando un UPDATE individual por jugador. El UPDATE masivo por
    diccionarios no tiene ese problema porque no depende del tracking de
    "qué cambió" del ORM.
    """
    energia_gastada = resultado["energia_gastada"]
    lesionados_ahora = {les["id_jugador"]: les for les in resultado["lesiones"]}
    ids_local = {j.id_jugador for j in plantel_local}
    gh, gv = resultado["gh"], resultado["gv"]
    resultado_local = "GANO" if gh > gv else "PERDIO" if gh < gv else "EMPATO"
    resultado_visit = "GANO" if gv > gh else "PERDIO" if gv < gh else "EMPATO"

    updates = []
    for j in plantel_local + plantel_visit:
        delta = energia_gastada.get(j.id_jugador)
        nueva_energia = max(0, round(j.energia - delta)) if delta else j.energia
        nuevo_lesionado, nuevo_tipo, nuevas_semanas = j.lesionado, j.tipo_lesion, j.semanas_lesion
        if j.id_jugador in lesionados_ahora:
            les = lesionados_ahora[j.id_jugador]
            nuevo_lesionado, nuevo_tipo, nuevas_semanas = True, les["tipo"], les["semanas"]
        elif j.lesionado:
            # El Centro Médico acelera la recuperación: hasta ~3x más rápido
            # en nivel 20 (factor_medico llega a 0.4, ver _factor_medico).
            factor_medico = factor_medico_local if j.id_jugador in ids_local else factor_medico_visit
            paso_recuperacion = max(1, round(1 + (1 - factor_medico) * 3))
            nuevas_semanas = j.semanas_lesion - paso_recuperacion
            if nuevas_semanas <= 0:
                nuevo_lesionado, nuevo_tipo, nuevas_semanas = False, None, 0
        jugo = j.id_jugador in energia_gastada
        resultado_partido = (resultado_local if j.id_jugador in ids_local else resultado_visit) if jugo else None
        nueva_moral = ajustar_moral(j.moral, jugo, resultado_partido, j.rol)
        updates.append({
            "id_jugador": j.id_jugador, "energia": nueva_energia,
            "lesionado": nuevo_lesionado, "tipo_lesion": nuevo_tipo, "semanas_lesion": nuevas_semanas,
            "moral": nueva_moral,
            "partidos_club_actual": (j.partidos_club_actual + 1) if jugo else j.partidos_club_actual,
        })
    return updates


def _calcular_update_equipo(equipo: Equipo, goles_favor: int, goles_contra: int) -> dict:
    ganados, empatados, perdidos, puntos = equipo.ganados, equipo.empatados, equipo.perdidos, equipo.puntos
    if goles_favor > goles_contra:
        ganados += 1
        puntos += 3
    elif goles_favor < goles_contra:
        perdidos += 1
    else:
        empatados += 1
        puntos += 1
    return {
        "id_equipo": equipo.id_equipo,
        "jugados": equipo.jugados + 1,
        "goles_favor": equipo.goles_favor + goles_favor,
        "goles_contra": equipo.goles_contra + goles_contra,
        "ganados": ganados, "empatados": empatados, "perdidos": perdidos, "puntos": puntos,
    }


def _aplicar_efectos_fisicos(
    jl, jv, plantel_local, plantel_visit, resultado, factor_medico_local: float = 1.0, factor_medico_visit: float = 1.0,
) -> None:
    """Igual que _calcular_efectos_fisicos pero mutando los objetos ORM
    directamente — se usa para UN solo partido (el del usuario, o el modo
    "jugar en vivo"), donde la cantidad de filas es chica y no vale la pena
    la complejidad del camino de UPDATE masivo."""
    updates = _calcular_efectos_fisicos(plantel_local, plantel_visit, resultado, factor_medico_local, factor_medico_visit)
    updates_por_id = {u["id_jugador"]: u for u in updates}
    for j in plantel_local + plantel_visit:
        u = updates_por_id[j.id_jugador]
        j.energia, j.lesionado, j.tipo_lesion, j.semanas_lesion = u["energia"], u["lesionado"], u["tipo_lesion"], u["semanas_lesion"]
        j.moral = u["moral"]
        j.partidos_club_actual = u["partidos_club_actual"]


async def _finalizar_fixture(db: AsyncSession, fixture: Calendario, local: Equipo, visit: Equipo, gh: int, gv: int) -> None:
    """Cierra el resultado del partido: marca el fixture jugado, actualiza
    la tabla de posiciones y avisa al usuario. Se usa tanto para la
    simulación rápida (de una sola vez) como para el modo "jugar el
    partido" (una vez que terminaron los dos tiempos)."""
    fixture.jugado = True
    fixture.goles_local = gh
    fixture.goles_visitante = gv

    # Un partido de copa NUNCA toca la tabla doméstica — su resultado se
    # procesa aparte (grupos/eliminatorias) en _avanzar_ronda_copa_si_corresponde.
    if fixture.tipo == "LIGA":
        # Siempre se tocan las mismas columnas en ambos equipos (ganados/
        # perdidos/empatados/puntos), aunque el incremento sea 0 — así todas las
        # filas de Equipo quedan con la misma "forma" de UPDATE y SQLAlchemy las
        # manda en un solo lote en vez de partirlas en 3 grupos (ganó/perdió/
        # empató) al resolver una jornada entera.
        local.jugados += 1
        visit.jugados += 1
        local.goles_favor += gh
        local.goles_contra += gv
        visit.goles_favor += gv
        visit.goles_contra += gh
        if gh > gv:
            local.ganados, local.empatados, local.perdidos, local.puntos = local.ganados + 1, local.empatados, local.perdidos, local.puntos + 3
            visit.ganados, visit.empatados, visit.perdidos, visit.puntos = visit.ganados, visit.empatados, visit.perdidos + 1, visit.puntos
        elif gh < gv:
            visit.ganados, visit.empatados, visit.perdidos, visit.puntos = visit.ganados + 1, visit.empatados, visit.perdidos, visit.puntos + 3
            local.ganados, local.empatados, local.perdidos, local.puntos = local.ganados, local.empatados, local.perdidos + 1, local.puntos
        else:
            local.ganados, local.empatados, local.perdidos, local.puntos = local.ganados, local.empatados + 1, local.perdidos, local.puntos + 1
            visit.ganados, visit.empatados, visit.perdidos, visit.puntos = visit.ganados, visit.empatados + 1, visit.perdidos, visit.puntos + 1

    if local.es_usuario or visit.es_usuario:
        fecha = await _fecha_actual(db, local.id_partida)
        id_equipo_usuario = local.id_equipo if local.es_usuario else visit.id_equipo
        equipo_usuario = local if local.es_usuario else visit
        goles_propios, goles_rivales = (gh, gv) if local.es_usuario else (gv, gh)
        variacion_hinchada = 4 if goles_propios > goles_rivales else (1 if goles_propios == goles_rivales else -4)
        partida = await db.get(Partida, local.id_partida)
        if partida and automatizaciones_de_partida(partida.automatizaciones_json)["club_ciudad"]:
            equipo_usuario.humor_hinchada = max(0, min(100, equipo_usuario.humor_hinchada + variacion_hinchada))
        await _crear_mensaje(
            db, id_equipo_usuario, "Cuerpo Técnico", f"Resultado: {local.nombre} {gh} - {gv} {visit.nombre}",
            f"Terminó el partido entre {local.nombre} y {visit.nombre}: {gh} a {gv}.",
            "PARTIDO", fecha,
        )


async def _jugar_fixture(db: AsyncSession, fixture: Calendario, id_jugador_marcado: int | None = None) -> dict:
    local, visit, plantel_local, plantel_visit, jl, jv, dict_local, dict_visit, tac_local_dict, tac_visit_dict = await _preparar_lineup(db, fixture)
    _aplicar_marcaje(dict_local, dict_visit, id_jugador_marcado)
    return await _simular_y_finalizar(db, fixture, local, visit, plantel_local, plantel_visit, jl, jv, dict_local, dict_visit, tac_local_dict, tac_visit_dict)


async def _simular_y_finalizar(
    db: AsyncSession, fixture: Calendario, local: Equipo, visit: Equipo,
    plantel_local: list, plantel_visit: list, jl: list, jv: list, dict_local: list, dict_visit: list,
    tac_local_dict: dict, tac_visit_dict: dict,
) -> dict:
    """Núcleo de simular-un-fixture sin leer nada de la base — se usa tanto
    para el partido puntual del usuario (una consulta más arriba) como para
    resolver en lote el resto de la jornada (datos ya precargados)."""
    fm_local = _factor_medico(await _bono_red_equipo(db, local))
    fm_visit = _factor_medico(await _bono_red_equipo(db, visit))
    resultado = simulate_match(
        dict_local, dict_visit, tac_local_dict, tac_visit_dict,
        ia_local=not local.es_usuario,
        ia_visit=not visit.es_usuario,
        factor_medico_local=fm_local, factor_medico_visit=fm_visit,
    )

    _aplicar_efectos_fisicos(jl, jv, plantel_local, plantel_visit, resultado, fm_local, fm_visit)
    await _procesar_addons_cumplidos(db, {p.id_jugador for p in jl + jv}, fixture.fecha)
    await _finalizar_fixture(db, fixture, local, visit, resultado["gh"], resultado["gv"])

    return {
        "id_local": fixture.id_local, "id_visitante": fixture.id_visitante,
        "nombre_local": local.nombre, "nombre_visitante": visit.nombre,
        "goles_local": resultado["gh"], "goles_visitante": resultado["gv"],
        "eventos": resultado["events"],
    }


async def _cerrar_jornada_del_dia(db: AsyncSession, fixture: Calendario) -> tuple[list[str], bool]:
    """Se corre después de que el partido del usuario terminó (ya sea por
    simulación rápida o al completar el segundo tiempo del modo en vivo):
    resuelve el resto de los partidos de la misma fecha (todas las ligas
    comparten fechas de jornada), corre la IA de mercado, efectiviza
    ofertas pendientes y chequea fin de temporada."""
    id_partida = fixture.id_partida
    otros_pendientes = (await db.execute(
        select(Calendario).where(
            Calendario.id_partida == id_partida,
            Calendario.fecha == fixture.fecha,
            Calendario.jugado.is_(False),
        )
    )).scalars().all()

    if otros_pendientes:
        # Con varias ligas jugando la misma fecha, esto puede ser 30-40+
        # partidos: precargar todo en un puñado de consultas (en vez de
        # ~6 consultas POR partido, una por una) es la diferencia entre
        # segundos y varios minutos con la latencia de Neon.
        ids_equipos = {id_eq for f in otros_pendientes for id_eq in (f.id_local, f.id_visitante)}
        equipos_por_id = {e.id_equipo: e for e in (
            await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_equipos)))
        ).scalars().all()}
        tacticas_por_id = {t.id_equipo: t for t in (
            await db.execute(select(Tactica).where(Tactica.id_equipo.in_(ids_equipos)))
        ).scalars().all()}
        jugadores_por_equipo: dict[int, list[Jugador]] = {}
        for j in (await db.execute(select(Jugador).where(Jugador.id_equipo.in_(ids_equipos)))).scalars().all():
            jugadores_por_equipo.setdefault(j.id_equipo, []).append(j)
        bonos_red = await _bonos_red_por_equipos(db, id_partida, ids_equipos)

        # Se calcula todo en memoria (nada de mutar objetos ORM acá) y se
        # manda como 3 UPDATE masivos al final — mutar ~2000 objetos uno por
        # uno hace que SQLAlchemy pierda el lote (executemany) apenas dos
        # jugadores no cambian exactamente las mismas columnas al mismo
        # valor, y eso son minutos de diferencia con la latencia de Neon.
        updates_jugador: list[dict] = []
        updates_equipo: list[dict] = []
        updates_fixture: list[dict] = []
        ids_jugaron_lote: set[int] = set()

        for otro in otros_pendientes:
            local = equipos_por_id.get(otro.id_local)
            visit = equipos_por_id.get(otro.id_visitante)
            tac_local = tacticas_por_id.get(otro.id_local)
            tac_visit = tacticas_por_id.get(otro.id_visitante)
            if not local or not visit or not tac_local or not tac_visit:
                continue
            plantel_local = jugadores_por_equipo.get(otro.id_local, [])
            plantel_visit = jugadores_por_equipo.get(otro.id_visitante, [])
            jl = _once_titular(plantel_local)
            jv = _once_titular(plantel_visit)
            dict_local = [{"id_jugador": p.id_jugador, "nombre": p.nombre, "posicion": p.posicion,
                            "ataque": p.ataque, "defensa": p.defensa, "energia": p.energia, "duty": p.duty} for p in jl]
            dict_visit = [{"id_jugador": p.id_jugador, "nombre": p.nombre, "posicion": p.posicion,
                            "ataque": p.ataque, "defensa": p.defensa, "energia": p.energia, "duty": p.duty} for p in jv]
            _aplicar_vestuario(dict_local, plantel_local, local.id_capitan)
            _aplicar_vestuario(dict_visit, plantel_visit, visit.id_capitan)
            tac_local_dict = {"formacion": tac_local.formacion, "mentalidad": tac_local.mentalidad, "presion": tac_local.presion}
            tac_visit_dict = {"formacion": tac_visit.formacion, "mentalidad": tac_visit.mentalidad, "presion": tac_visit.presion}

            fm_local = _factor_medico(bonos_red.get(otro.id_local))
            fm_visit = _factor_medico(bonos_red.get(otro.id_visitante))
            resultado = simulate_match(
                dict_local, dict_visit, tac_local_dict, tac_visit_dict,
                ia_local=not local.es_usuario, ia_visit=not visit.es_usuario,
                factor_medico_local=fm_local, factor_medico_visit=fm_visit,
            )
            updates_jugador.extend(_calcular_efectos_fisicos(
                plantel_local, plantel_visit, resultado, fm_local, fm_visit,
            ))
            ids_jugaron_lote.update(p.id_jugador for p in jl + jv)
            if otro.tipo == "LIGA":
                updates_equipo.append(_calcular_update_equipo(local, resultado["gh"], resultado["gv"]))
                updates_equipo.append(_calcular_update_equipo(visit, resultado["gv"], resultado["gh"]))
            updates_fixture.append({
                "id_fixture": otro.id_fixture, "jugado": True,
                "goles_local": resultado["gh"], "goles_visitante": resultado["gv"],
            })

        if updates_jugador:
            await db.execute(update(Jugador), updates_jugador)
            await _procesar_addons_cumplidos(db, ids_jugaron_lote, fixture.fecha)
        if updates_equipo:
            await db.execute(update(Equipo), updates_equipo)
        if updates_fixture:
            await db.execute(update(Calendario), updates_fixture)

    fecha = await _fecha_actual(db, id_partida)
    log_ia: list[str] = []
    partida = await db.get(Partida, id_partida)
    if partida and automatizaciones_de_partida(partida.automatizaciones_json)["mercado"]:
        await ejecutar_ia_mercado(db, log_ia, fecha, id_partida)
    await _efectivizar_ofertas_pendientes(db, fecha, id_partida)
    await _avanzar_torneos_internacionales_si_corresponde(db, id_partida, fecha)
    nueva_temporada = await _procesar_fin_temporada_si_corresponde(db, fecha, id_partida)
    return log_ia, nueva_temporada


FOCOS_INDIVIDUALES_VALIDOS = {"OFENSIVO", "DEFENSIVO", "PASE", "FISICO"}


async def _margen_salarial_disponible(db: AsyncSession, equipo: Equipo, excluir_jugador: Jugador | None = None) -> int:
    """Cuánto sueldo semanal más puede comprometer `equipo` sin superar su
    tope de fair play financiero — descuenta la masa salarial actual del
    plantel Y lo que ya se acordó pagarle a jugadores entrantes que todavía
    no se hicieron efectivos (si no, se podría pactar varios contratos que
    juntos superan el tope, y recién enterarse cuando lleguen todos a la
    vez). `excluir_jugador`: al renovar a alguien ya del plantel, su sueldo
    VIEJO no cuenta contra sí mismo — se está reemplazando, no sumando."""
    plantel = (await db.execute(
        select(Jugador).where(Jugador.id_equipo == equipo.id_equipo, Jugador.categoria == "PRIMERA")
    )).scalars().all()
    masa_actual = sum(j.salario for j in plantel if not excluir_jugador or j.id_jugador != excluir_jugador.id_jugador)

    pendientes = (await db.execute(
        select(OfertaFichaje).where(
            OfertaFichaje.id_equipo_comprador == equipo.id_equipo,
            OfertaFichaje.estado == "ACEPTADA",
            OfertaFichaje.efectivizada.is_(False),
        )
    )).scalars().all()
    masa_pendiente = sum(o.salario_pactado or 0 for o in pendientes)

    # Precontratos firmados con jugadores ajenos (se incorporan libres cuando
    # termine SU contrato actual, no pasan por OfertaFichaje) también
    # comprometen sueldo futuro — cuentan igual.
    precontratos = (await db.execute(
        select(Jugador.salario_precontrato).where(Jugador.id_equipo_precontrato == equipo.id_equipo)
    )).scalars().all()
    masa_precontratos = sum(s or 0 for s in precontratos)

    return equipo.presupuesto_salarios - masa_actual - masa_pendiente - masa_precontratos


def _jugador_desarrollo(j: Jugador) -> dict:
    return {
        "id_jugador": j.id_jugador, "nombre": j.nombre, "posicion": j.posicion, "posicion_especifica": j.posicion_especifica,
        "edad": j.edad, "overall": j.overall, "potencial": j.potencial,
        "rol": j.rol, "valor_mercado": j.valor_mercado, "categoria": j.categoria,
        "margen_desarrollo": j.potencial - j.overall,
    }


def _resumen_cantera(lista: list[Jugador], etiqueta: str) -> str:
    if not lista:
        return f"No hay jugadores en la categoría {etiqueta}."
    prom_potencial = sum(j.potencial for j in lista) / len(lista)
    if prom_potencial >= 75:
        return "Buena plantilla, con varios jugadores de mucho potencial."
    if prom_potencial >= 60:
        return "Tenemos unos cuantos jugadores mostrando un potencial decente."
    return "Desafortunadamente, esta plantilla es de un nivel bastante mediocre en general."


def _agrupar_por_categoria(jugadores: list[Jugador]) -> dict:
    grupos = {c: [] for c in CATEGORIAS_ACADEMIA}
    for j in jugadores:
        if j.categoria in grupos:
            grupos[j.categoria].append(j)
    for c in grupos:
        grupos[c].sort(key=lambda j: -j.potencial)
    return grupos


async def _presupuesto_referencia_liga(db: AsyncSession, equipo: Equipo) -> float:
    return float((await db.execute(
        select(func.avg(Equipo.presupuesto_fichajes)).where(Equipo.id_liga == equipo.id_liga)
    )).scalar() or equipo.presupuesto_fichajes)


async def _valor_club_equipo(db: AsyncSession, equipo: Equipo) -> int:
    valor_plantel = (await db.execute(
        select(func.coalesce(func.sum(Jugador.valor_mercado), 0)).where(
            Jugador.id_equipo == equipo.id_equipo, Jugador.categoria == "PRIMERA",
        )
    )).scalar()
    return multiclub_engine.valor_club(equipo.reputacion, equipo.presupuesto_fichajes, valor_plantel)


def _aplicar_transferencia_interna(jugador: Jugador, vendedor: Equipo, comprador: Equipo, fecha: date, monto: int) -> None:
    """Pase definitivo a precio de familia entre clubes afiliados — mismo
    criterio de contrato nuevo que cualquier transferencia normal, sin
    negociación (ver /multiclub/mover-jugador)."""
    jugador.id_equipo = comprador.id_equipo
    jugador.salario = salario_esperado(jugador.valor_mercado, jugador.edad)
    jugador.fecha_fin_contrato = fecha + timedelta(days=365 * 3)
    jugador.rol = "RESERVA"
    jugador.id_equipo_dueno = None
    jugador.fin_cesion = None
    jugador.opcion_compra = None
    vendedor.presupuesto_fichajes += monto
    comprador.presupuesto_fichajes -= monto
    vendedor.presupuesto_salarios = tope_salarial(vendedor.presupuesto_fichajes)
    comprador.presupuesto_salarios = tope_salarial(comprador.presupuesto_fichajes)


POSICIONES_CANCHA = ["POR", "DEF", "MED", "DEL"]


def _promedios_por_posicion(jugadores: list[Jugador]) -> dict[str, float]:
    promedios = {}
    for pos in POSICIONES_CANCHA:
        del_pos = [j for j in jugadores if j.posicion == pos and j.rol in ("TITULAR", "SUPLENTE")]
        promedios[pos] = round(sum(j.overall for j in del_pos) / len(del_pos), 1) if del_pos else 0.0
    return promedios


def _opinion_tactica(tactica: Tactica, promedios: dict[str, float], plantel: list[Jugador]) -> str:
    """Comentario del asistente sobre el esquema actual — no repite las
    recomendaciones de fichajes (eso ya lo cubre Transferencias): mira si el
    plantel alcanza para la formación elegida y si mentalidad/presión están
    en línea con el nivel real de ataque/defensa/mediocampo."""
    partes = tactica.formacion.split("-")
    necesarios = {"DEF": int(partes[0]), "DEL": int(partes[-1]), "MED": sum(int(p) for p in partes[1:-1])}
    disponibles = {
        pos: len([j for j in plantel if j.posicion == pos and j.rol in ("TITULAR", "SUPLENTE")])
        for pos in necesarios
    }
    faltantes = {pos: necesarios[pos] - disponibles[pos] for pos in necesarios if necesarios[pos] > disponibles[pos]}
    if faltantes:
        pos_critica = max(faltantes, key=faltantes.get)
        return (
            f"Con la formación {tactica.formacion} necesitamos {necesarios[pos_critica]} jugadores de nivel en {pos_critica} "
            f"entre titulares y suplentes, y ahí solo contamos con {disponibles[pos_critica]} — es donde más flaqueamos tácticamente."
        )

    brecha = promedios["DEL"] - promedios["DEF"]
    if tactica.mentalidad in ("OFENSIVA", "PRESION_ALTA") and brecha < -6:
        return (
            f"Jugamos con mentalidad {tactica.mentalidad.lower().replace('_', ' ')} pero la defensa (promedio {promedios['DEF']}) "
            f"está bastante por debajo del ataque (promedio {promedios['DEL']}) — nos van a castigar de contragolpe."
        )
    if tactica.mentalidad in ("DEFENSIVA", "ULTRA_DEFENSIVA") and brecha > 6:
        return (
            f"Con un ataque de nivel {promedios['DEL']} bastante por encima de la defensa ({promedios['DEF']}), jugar tan "
            f"replegados desaprovecha lo que tenemos arriba. Yo probaría subir un poco la mentalidad."
        )
    if tactica.presion == "ALTA" and promedios["MED"] < 55:
        return "Presionamos alto, pero el mediocampo (promedio {:.1f}) no tiene el nivel para sostenerlo noventa minutos — vamos a sufrir en el último tramo del partido.".format(promedios["MED"])
    return f"El esquema {tactica.formacion} con mentalidad {tactica.mentalidad.lower().replace('_', ' ')} está bien equilibrado para el plantel que tenemos."


def _consejo_entrenamiento(plantel: list[Jugador]) -> str:
    """Sugerencia del asistente de entrenamiento sobre qué `foco`/intensidad
    conviene ahora — mira energía y qué atributo está más flojo en promedio."""
    if not plantel:
        return "Todavía no hay plantel para armar un plan de entrenamiento."
    energia_prom = sum(j.energia for j in plantel) / len(plantel)
    if energia_prom < 60:
        return f"El plantel llega cansado (energía promedio {energia_prom:.0f}%) — bajaría la intensidad, o directamente un ciclo de descanso antes del próximo partido."
    promedios_attr = {
        "OFENSIVO": sum(j.ataque for j in plantel) / len(plantel),
        "DEFENSIVO": sum(j.defensa for j in plantel) / len(plantel),
        "PASE": sum(j.pase for j in plantel) / len(plantel),
        "FISICO": sum(j.fisico for j in plantel) / len(plantel),
    }
    foco_sugerido, valor = min(promedios_attr.items(), key=lambda par: par[1])
    etiqueta = {"OFENSIVO": "el ataque", "DEFENSIVO": "la defensa", "PASE": "el pase", "FISICO": "lo físico"}[foco_sugerido]
    return f"Con la energía en buen nivel ({energia_prom:.0f}%), yo enfocaría el entrenamiento en {etiqueta} (promedio {valor:.0f}), que es lo más flojo del plantel ahora mismo."


def _consejo_vestuario(plantel: list[Jugador], capitan: Jugador | None) -> str:
    """Comentario del asistente sobre el estado del vestuario — puntaje,
    qué tan dividido está el ánimo, y si conviene nombrar/cambiar capitán."""
    primera = [j for j in plantel if j.categoria == "PRIMERA"]
    if not primera:
        return "Todavía no hay plantel para hablar del vestuario."
    promedio = sum(j.moral for j in primera) / len(primera)
    varianza = sum((j.moral - promedio) ** 2 for j in primera) / len(primera)
    desviacion = varianza ** 0.5
    if desviacion >= 15 and not capitan:
        return f"El vestuario está bastante dividido de ánimo (moral entre {min(j.moral for j in primera)} y {max(j.moral for j in primera)}) — un capitán con buen liderazgo ayudaría a unificarlo."
    if desviacion >= 15 and capitan:
        return f"El plantel sigue algo dividido de ánimo, pero {capitan.nombre} (liderazgo {capitan.liderazgo}) está ayudando a sostener el vestuario."
    if promedio < 55:
        return f"La moral promedio del plantel está baja ({promedio:.0f}) — cuidado, un vestuario apagado rinde peor en la cancha."
    return f"El vestuario está en buen estado (moral promedio {promedio:.0f}, ánimo parejo)."


DURACIONES_CESION_VALIDAS = {6: 182, 12: 365}


def _aplicar_cesion(jugador: Jugador, dueno: Equipo, destino: Equipo, duracion_meses: int, opcion_compra: int | None, fecha: date) -> None:
    """Setea los campos de una cesión aceptada — usado tanto por el camino
    normal (/fichajes/ceder, después de ganar la tirada de interés) como
    por el pipeline facilitado entre clubes afiliados (sin tirada, ver
    /multiclub/mover-jugador)."""
    jugador.id_equipo_dueno = dueno.id_equipo
    jugador.id_equipo = destino.id_equipo
    jugador.fin_cesion = fecha + timedelta(days=DURACIONES_CESION_VALIDAS[duracion_meses])
    jugador.opcion_compra = opcion_compra
    jugador.rol = "RESERVA"


async def _ofertas_dt_out(db: AsyncSession, id_partida: int) -> list[dict]:
    filas = (await db.execute(select(OfertaClubDT).where(OfertaClubDT.id_partida == id_partida))).scalars().all()
    salida = []
    for o in filas:
        eq = await db.get(Equipo, o.id_equipo)
        if not eq:
            continue
        liga = await db.get(Liga, eq.id_liga)
        salida.append({
            "id_oferta": o.id_oferta, "id_equipo": eq.id_equipo, "nombre": eq.nombre,
            "reputacion": eq.reputacion, "pais": liga.pais if liga else None,
        })
    return salida


PAQUETE_BASE_FICTICIA = {
    "id_paquete": None, "pack_id": "base-ficticia", "tipo": "PROCEDURAL", "es_oficial": True,
    "nombre": "Base Ficticia", "version": pack_engine.GAME_VERSION, "autor": "PARTIDOS Manager",
    "descripcion": "Ligas, clubes y jugadores generados automáticamente en cada partida nueva. Sin nombres reales.",
    "fecha_creacion": None, "fecha_actualizacion": None,
    "numberOfLeagues": None, "numberOfClubs": None, "numberOfPlayers": None,
}


def _resumen_paquete(p: PaqueteClubes) -> dict:
    nombres = json.loads(p.nombres_json)
    jugadores = json.loads(p.jugadores_json) if p.jugadores_json else None
    conteos = pack_engine.contar_entidades(nombres, jugadores)
    return {
        "id_paquete": p.id_paquete, "pack_id": p.pack_id, "tipo": "ESTATICO", "es_oficial": p.es_oficial,
        "nombre": p.nombre, "version": p.version, "autor": p.autor, "descripcion": p.descripcion,
        "fecha_creacion": p.fecha_creacion.isoformat() if p.fecha_creacion else None,
        "fecha_actualizacion": p.fecha_actualizacion.isoformat() if p.fecha_actualizacion else None,
        "numberOfLeagues": conteos["numberOfLeagues"], "numberOfClubs": conteos["numberOfClubs"], "numberOfPlayers": conteos["numberOfPlayers"],
        # Alias en español para el frontend existente (CrearCarreraPage ya usa estos nombres).
        "cantidad_ligas": conteos["numberOfLeagues"], "cantidad_clubes": conteos["numberOfClubs"],
    }


async def _pack_ids_existentes(db: AsyncSession) -> set[str]:
    filas = (await db.execute(select(PaqueteClubes.pack_id))).scalars().all()
    return {p for p in filas if p} | {"base-ficticia"}


def _validar_datos_pack(nombres, jugadores):
    try:
        return pack_engine.validar_datos_pack(nombres, jugadores)
    except PmpackInvalido as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
