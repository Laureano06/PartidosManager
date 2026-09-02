import json
import random
from contextlib import asynccontextmanager
from datetime import date, timedelta

from formato import money

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, or_, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import engine, Base, get_db
from models import (
    Equipo, Jugador, Tactica, PlanEntrenamiento, Calendario, OfertaFichaje, Liga, Partida, Mensaje,
    HistorialTemporada, PaqueteClubes, EventoPartido, PersonalTecnico, Ojeador, ReporteScouting,
    CicloTemporada, OfertaClubDT, SolicitudObra,
)
from schemas import (
    EquipoOut, JugadorOut, LigaOut, TacticaIn, EntrenamientoIn,
    OfertaIn, RespuestaOfertaIn, SimularJornadaIn,
    RenovarContratoIn, PrecontratoIn, FicharLibreIn, NegociarContratoTraspasoIn,
    TransferibleIn, OfrecerJugadorIn, CederJugadorIn,
    CategoriaJugadorIn, IntakeDecidirIn, ReclutarJuvenilIn, ElegirDestinoDTIn,
    SolicitarObraIn,
)
from engine.match_engine import simulate_match
from engine.transfer_engine import evaluar_oferta
from engine.training_engine import aplicar_entrenamiento
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
from engine.data_gen import (
    objetivo_por_nivel, nivel_desde_reputacion, tope_salarial,
    COSTO_BASE_INSTALACION, costo_mejora_instalacion, mantenimiento_mensual_instalacion,
)

DIAS_ELEGIBLE_PRECONTRATO = 180
DIAS_CHECKPOINT_RENOVACION_IA = 150
PROB_RENOVACION_IA = 0.75

# Tipos de instalación válidos (clave usada en SolicitudObra.tipo_instalacion
# y en la columna nivel_<tipo> de Equipo) con su nombre para mostrar.
NOMBRE_INSTALACION = {
    "centro_entrenamiento": "Centro de Entrenamiento",
    "centro_medico": "Centro Médico",
    "analitica": "Departamento de Analítica",
    "captacion_juvenil": "Captación Juvenil",
    "instalaciones_juveniles": "Instalaciones Juveniles",
    "entrenadores_juveniles": "Entrenadores Juveniles",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Base de datos lista.")
    yield
    await engine.dispose()


app = FastAPI(title="Partidos Soccer Manager API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- HELPERS COMPARTIDOS ----------
async def _equipo_usuario(db: AsyncSession, id_partida: int) -> Equipo | None:
    return (await db.execute(
        select(Equipo).where(Equipo.id_partida == id_partida, Equipo.es_usuario.is_(True))
    )).scalars().first()


async def _fecha_actual(db: AsyncSession, id_partida: int) -> date:
    partida = await db.get(Partida, id_partida)
    return partida.fecha_actual if partida else date.today()


# ---------- ACADEMIA (plantel juvenil) ----------
def _bono_instalaciones_juveniles(equipo: Equipo) -> float:
    """Bono combinado de Instalaciones Juveniles + Entrenadores Juveniles
    (0.0-0.3) para academia_engine.calcular_factor_desde_plantel."""
    return min(0.3, (equipo.nivel_instalaciones_juveniles + equipo.nivel_entrenadores_juveniles) * 0.0075)


def _bono_captacion_juvenil(equipo: Equipo) -> int:
    """Candidatos extra (0-5) en el intake anual según Captación Juvenil."""
    return equipo.nivel_captacion_juvenil // 4


def _factor_medico(equipo: Equipo | None) -> float:
    """Multiplicador de riesgo de lesión según el Centro Médico del club
    (1.0 = sin efecto, hasta 0.4 = 60% menos riesgo en nivel 20) — ver
    engine/injury_engine.py::evaluar_lesion."""
    if not equipo:
        return 1.0
    return max(0.4, 1 - equipo.nivel_centro_medico * 0.03)


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
    bono_instalaciones = _bono_instalaciones_juveniles(equipo)
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


# ---------- DIRECTIVA: mercado de ofertas de club para el DT ----------
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


# ---------- SCOUTING: fog-of-war sobre overall/potencial ajenos ----------
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
        if oferta.salario_pactado:
            # Contrato nuevo pactado con el jugador como parte del traspaso.
            jugador.salario = oferta.salario_pactado
            jugador.fecha_fin_contrato = fecha + timedelta(days=365 * 3)

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


async def _procesar_solicitudes_obra(db: AsyncSession, fecha: date, id_partida: int) -> None:
    """Se corre en cada avance de día: resuelve las solicitudes de obra de
    infraestructura PENDIENTE cuya fecha_resolucion ya llegó — el veredicto
    (aprobada/rechazada) se decide RECIÉN ACÁ, con la confianza/presupuesto
    del día de la resolución, no del día que se pidió. Si se aprueba, cobra
    el costo y sube el nivel de la instalación; en cualquier caso, avisa
    por mensaje."""
    pendientes = (await db.execute(
        select(SolicitudObra).where(
            SolicitudObra.id_partida == id_partida,
            SolicitudObra.estado == "PENDIENTE",
            SolicitudObra.fecha_resolucion <= fecha,
        )
    )).scalars().all()
    if not pendientes:
        return
    ids_equipo = {s.id_equipo for s in pendientes}
    equipos_por_id: dict[int, Equipo] = {e.id_equipo: e for e in (
        await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_equipo)))
    ).scalars().all()}
    partida = await db.get(Partida, id_partida)
    confianza = partida.confianza_directiva if partida else directiva_engine.CONFIANZA_INICIAL

    for s in pendientes:
        equipo = equipos_por_id.get(s.id_equipo)
        if not equipo:
            continue
        nombre_instalacion = NOMBRE_INSTALACION.get(s.tipo_instalacion, s.tipo_instalacion)
        veredicto = directiva_engine.evaluar_solicitud_obra(confianza, s.costo, equipo.presupuesto_fichajes)
        s.estado = veredicto["estado"]
        if veredicto["estado"] == "APROBADA":
            setattr(equipo, f"nivel_{s.tipo_instalacion}", s.nivel_objetivo)
            equipo.presupuesto_fichajes -= s.costo
            equipo.presupuesto_salarios = tope_salarial(equipo.presupuesto_fichajes)
            if equipo.es_usuario:
                await _crear_mensaje(
                    db, equipo.id_equipo, "Directiva del Club", f"Obra aprobada: {nombre_instalacion}",
                    f"La directiva aprobó la mejora de {nombre_instalacion} a nivel {s.nivel_objetivo} "
                    f"por ${money(s.costo)}. Ya está operativa.",
                    "SISTEMA", fecha,
                )
        else:
            if equipo.es_usuario:
                await _crear_mensaje(
                    db, equipo.id_equipo, "Directiva del Club", f"Obra rechazada: {nombre_instalacion}",
                    f"La directiva rechazó la mejora de {nombre_instalacion}. {veredicto['motivo']}",
                    "SISTEMA", fecha,
                )


async def _procesar_mantenimiento_infraestructura(db: AsyncSession, id_partida: int) -> None:
    """Se corre en cada avance de día: cobra a cada club el mantenimiento
    mensual de sus instalaciones, PRORRATEADO POR DÍA (no hay ciclo mensual
    en el juego, ver mantenimiento_mensual_instalacion en data_gen.py)."""
    equipos = (await db.execute(select(Equipo).where(Equipo.id_partida == id_partida))).scalars().all()
    for equipo in equipos:
        total_mensual = sum(
            mantenimiento_mensual_instalacion(tipo, getattr(equipo, f"nivel_{tipo}"))
            for tipo in COSTO_BASE_INSTALACION
        )
        if total_mensual:
            equipo.presupuesto_fichajes -= round(total_mensual / 30)
            equipo.presupuesto_salarios = tope_salarial(equipo.presupuesto_fichajes)


async def _procesar_progreso_scouting(db: AsyncSession, fecha: date, id_partida: int) -> None:
    """Se corre en cada avance de día: todo ojeador con un objetivo asignado
    suma progreso a su reporte, más rápido cuanto mejor sea su `calidad`."""
    ojeadores = (await db.execute(
        select(Ojeador).where(Ojeador.id_partida == id_partida, Ojeador.id_jugador_asignado.is_not(None))
    )).scalars().all()
    if not ojeadores:
        return
    ids_equipo_ojeadores = {o.id_equipo for o in ojeadores}
    equipos_ojeadores_por_id: dict[int, Equipo] = {e.id_equipo: e for e in (
        await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_equipo_ojeadores)))
    ).scalars().all()}
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
        equipo_ojeador = equipos_ojeadores_por_id.get(o.id_equipo)
        # Bono del Departamento de Analítica del club: acelera el progreso
        # de cualquier reporte en curso, sin importar quién sea el ojeador.
        bono_analitica = round((equipo_ojeador.nivel_analitica if equipo_ojeador else 0) * 0.4)
        reporte.progreso = min(100, reporte.progreso + max(1, o.calidad // 15) + bono_analitica)
        reporte.fecha_ultimo_reporte = fecha


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

    for equipo_academia in equipos:
        academia_club = jugadores_academia_por_club.get(equipo_academia.id_equipo)
        if not academia_club:
            continue
        liga_club = next((l for l in ligas if l.id_liga == equipo_academia.id_liga), None)
        pais_club = liga_club.pais if liga_club else "Argentina"
        factor_club = academia_engine.calcular_factor_desde_plantel(
            jugadores_primera_por_club.get(equipo_academia.id_equipo, []), _bono_instalaciones_juveniles(equipo_academia),
        )
        bono_captacion = _bono_captacion_juvenil(equipo_academia)
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
            disposicion = disposicion_renovar(j.overall, j.edad, j.rol, j.moral, equipo_usuario.reputacion)
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
        tac_local_dict = {"formacion": tac_local.formacion, "mentalidad": tac_local.mentalidad, "presion": tac_local.presion}
        tac_visit_dict = {"formacion": tac_visit.formacion, "mentalidad": tac_visit.mentalidad, "presion": tac_visit.presion}
        resultado = simulate_match(
            dict_local, dict_visit, tac_local_dict, tac_visit_dict, ia_local=True, ia_visit=True,
            factor_medico_local=_factor_medico(local), factor_medico_visit=_factor_medico(visit),
        )
        _aplicar_efectos_fisicos(jl, jv, plantel_local, plantel_visit, resultado, _factor_medico(local), _factor_medico(visit))
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


# ---------- ESTADO DEL JUEGO (fecha) ----------
@app.get("/juego/estado", tags=["Panel"])
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


@app.post("/juego/avanzar-dia", tags=["Panel"])
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
    await _procesar_progreso_scouting(db, estado.fecha_actual, id_partida)
    await _procesar_solicitudes_obra(db, estado.fecha_actual, id_partida)
    await _procesar_mantenimiento_infraestructura(db, id_partida)
    await _procesar_arranques_diferidos(db, estado.fecha_actual, id_partida)
    await _procesar_partidos_ajenos_del_dia(db, estado.fecha_actual, id_partida, equipo_usuario)
    await db.commit()
    return {"fecha_actual": estado.fecha_actual.isoformat(), "ventana_mercado": ventana_activa(estado.fecha_actual)}


# ---------- AVANZAR VARIOS DÍAS DE UNA (hasta una fecha elegida) ----------
@app.post("/juego/simular-hasta", tags=["Panel"])
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
        await _procesar_progreso_scouting(db, estado.fecha_actual, id_partida)
        await _procesar_solicitudes_obra(db, estado.fecha_actual, id_partida)
        await _procesar_mantenimiento_infraestructura(db, id_partida)
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


# ---------- INBOX ----------
@app.get("/inbox", tags=["Panel"])
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


@app.post("/inbox/{id_mensaje}/leido", tags=["Panel"])
async def marcar_leido(id_mensaje: int, db: AsyncSession = Depends(get_db)):
    mensaje = await db.get(Mensaje, id_mensaje)
    if not mensaje:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    mensaje.leido = True
    await db.commit()
    return {"status": "ok"}


@app.post("/inbox/marcar-todo-leido", tags=["Panel"])
async def marcar_todo_leido(id_equipo: int, db: AsyncSession = Depends(get_db)):
    await db.execute(
        update(Mensaje).where(Mensaje.id_equipo_destino == id_equipo, Mensaje.leido.is_(False)).values(leido=True)
    )
    await db.commit()
    return {"status": "ok"}


# ---------- LIGAS ----------
@app.get("/ligas", response_model=list[LigaOut], tags=["Liga"])
async def listar_ligas(id_partida: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Liga).where(Liga.id_partida == id_partida))
    return result.scalars().all()


# ---------- EQUIPOS ----------
@app.get("/equipos", response_model=list[EquipoOut], tags=["Equipos"])
async def listar_equipos(id_partida: int, id_liga: int | None = None, db: AsyncSession = Depends(get_db)):
    query = select(Equipo).where(Equipo.id_partida == id_partida)
    if id_liga is not None:
        query = query.where(Equipo.id_liga == id_liga)
    result = await db.execute(query)
    return result.scalars().all()


@app.get("/equipos/{id_equipo}/jugadores", tags=["Equipos"])
async def obtener_plantilla(id_equipo: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Jugador).where(Jugador.id_equipo == id_equipo, Jugador.categoria == "PRIMERA")
    )
    jugadores = result.scalars().all()
    if not jugadores:
        raise HTTPException(status_code=404, detail="Equipo sin jugadores (¿corriste seed.py?)")

    fecha = await _fecha_actual(db, jugadores[0].id_partida)
    equipo_objetivo = await db.get(Equipo, id_equipo)
    equipo_usuario = None if (equipo_objetivo and equipo_objetivo.es_usuario) else await _equipo_usuario(db, jugadores[0].id_partida)
    reportes = (
        await _reportes_de(db, equipo_usuario.id_equipo, [j.id_jugador for j in jugadores])
        if equipo_usuario else {}
    )
    salida = []
    for j in jugadores:
        base = JugadorOut.model_validate(j).model_dump(mode="json")
        dias_restantes = (j.fecha_fin_contrato - fecha).days if j.fecha_fin_contrato else None
        base["dias_restantes_contrato"] = dias_restantes
        base["elegible_precontrato"] = dias_restantes is not None and 0 < dias_restantes <= DIAS_ELEGIBLE_PRECONTRATO
        base["id_equipo_precontrato"] = j.id_equipo_precontrato
        if equipo_usuario:
            _aplicar_fog(base, j, reportes.get(j.id_jugador))
        salida.append(base)
    return salida


@app.get("/jugadores/{id_jugador}", tags=["Equipos"])
async def obtener_jugador(id_jugador: int, db: AsyncSession = Depends(get_db)):
    """Ficha completa de un jugador puntual — para cuando la vista de lista
    (mercado, búsqueda) usó una versión liviana/paginada y hace falta el
    detalle completo recién al abrir su ficha."""
    jugador = await db.get(Jugador, id_jugador)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    equipo = await db.get(Equipo, jugador.id_equipo) if jugador.id_equipo else None
    fecha = await _fecha_actual(db, jugador.id_partida)
    dias_restantes = (jugador.fecha_fin_contrato - fecha).days if jugador.fecha_fin_contrato else None
    base = JugadorOut.model_validate(jugador).model_dump(mode="json")
    base["club"] = equipo.nombre if equipo else "Agente Libre"
    base["es_libre"] = jugador.id_equipo is None
    base["dias_restantes_contrato"] = dias_restantes
    base["elegible_precontrato"] = dias_restantes is not None and 0 < dias_restantes <= DIAS_ELEGIBLE_PRECONTRATO
    base["id_equipo_precontrato"] = jugador.id_equipo_precontrato
    if not (equipo and equipo.es_usuario):
        equipo_usuario = await _equipo_usuario(db, jugador.id_partida)
        if equipo_usuario:
            reporte = (await _reportes_de(db, equipo_usuario.id_equipo, [id_jugador])).get(id_jugador)
            _aplicar_fog(base, jugador, reporte)
    return base


def _interes_desde_probabilidad(probabilidad: float) -> str:
    if probabilidad >= 0.6:
        return "alto"
    if probabilidad >= 0.35:
        return "medio"
    return "bajo"


@app.get("/jugadores/{id_jugador}/dialogo", tags=["Equipos"])
async def dialogo_jugador(id_jugador: int, id_equipo_interesado: int, tema: str = "continuidad", db: AsyncSession = Depends(get_db)):
    """'Hablar con el jugador' — consulta de solo lectura, no gasta ninguna
    ronda de negociación real. Si id_equipo_interesado es el club actual del
    jugador, se lee su disposición a RENOVAR; si es otro club (scouting/
    mercado), su disposición a SUMARSE ahí. `tema`: club | continuidad | futuro."""
    jugador = await db.get(Jugador, id_jugador)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    equipo_interesado = await db.get(Equipo, id_equipo_interesado)
    if not equipo_interesado:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    if jugador.id_equipo == id_equipo_interesado:
        disposicion = disposicion_renovar(jugador.overall, jugador.edad, jugador.rol, jugador.moral, equipo_interesado.reputacion)
    else:
        equipo_actual = await db.get(Equipo, jugador.id_equipo) if jugador.id_equipo else None
        reputacion_actual = equipo_actual.reputacion if equipo_actual else None
        disposicion = disposicion_fichar(jugador.overall, jugador.edad, reputacion_actual, equipo_interesado.reputacion)

    frase = frase_dialogo(
        tema, moral=jugador.moral, disposicion=disposicion,
        overall=jugador.overall, potencial=jugador.potencial, edad=jugador.edad,
    )
    return {"tema": tema, "frase": frase, "interes": _interes_desde_probabilidad(disposicion["probabilidad"])}


@app.get("/jugadores/{id_jugador}/historial", tags=["Equipos"])
async def historial_jugador(id_jugador: int, db: AsyncSession = Depends(get_db)):
    """Evolución de carrera del jugador, temporada a temporada (overall,
    potencial, valor de mercado) — una fila por cada cierre de temporada
    que le tocó vivir."""
    filas = (await db.execute(
        select(HistorialTemporada).where(HistorialTemporada.id_jugador == id_jugador).order_by(HistorialTemporada.temporada)
    )).scalars().all()

    # Mismo criterio de fog que en la ficha actual del jugador — se aplica
    # parejo a todo el historial (no granular por el club de cada temporada
    # pasada), usando el progreso de scouting que se tenga HOY sobre él.
    progreso = 100
    jugador = await db.get(Jugador, id_jugador)
    if jugador:
        equipo = await db.get(Equipo, jugador.id_equipo) if jugador.id_equipo else None
        if not (equipo and equipo.es_usuario):
            equipo_usuario = await _equipo_usuario(db, jugador.id_partida)
            progreso = 0
            if equipo_usuario:
                reporte = (await _reportes_de(db, equipo_usuario.id_equipo, [id_jugador])).get(id_jugador)
                progreso = reporte.progreso if reporte else 0

    historial = []
    for h in filas:
        fila = {
            "temporada": h.temporada, "nombre_jugador": h.nombre_jugador, "nombre_equipo": h.nombre_equipo, "edad": h.edad,
            "valor_mercado": h.valor_mercado, "salario": h.salario, "rol": h.rol,
        }
        fila["overall"] = h.overall if progreso >= 100 else None
        fila["overall_rango"] = None if progreso >= 100 else _rango_fog(h.overall, progreso)
        fila["potencial"] = h.potencial if progreso >= 100 else None
        fila["potencial_rango"] = None if progreso >= 100 else _rango_fog(h.potencial, progreso)
        historial.append(fila)
    return {"historial": historial}


@app.post("/jugadores/{id_jugador}/rol", tags=["Equipos"])
async def cambiar_rol_jugador(id_jugador: int, datos: dict, db: AsyncSession = Depends(get_db)):
    rol = datos.get("rol")
    if rol not in ("TITULAR", "SUPLENTE", "RESERVA"):
        raise HTTPException(status_code=400, detail="rol inválido")
    jugador = await db.get(Jugador, id_jugador)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    if jugador.categoria != "PRIMERA":
        raise HTTPException(status_code=400, detail="Un jugador de la Academia no tiene rol de convocatoria")
    jugador.rol = rol
    await db.commit()
    return {"status": "ok", "id_jugador": id_jugador, "rol": rol}


@app.post("/jugadores/{id_jugador}/duty", tags=["Equipos"])
async def cambiar_duty_jugador(id_jugador: int, datos: dict, db: AsyncSession = Depends(get_db)):
    """Instrucción individual del jugador dentro de la táctica (independiente
    del rol titular/suplente/reserva) — ver `team_power` en match_engine.py."""
    duty = datos.get("duty")
    if duty not in ("DEFENSIVO", "EQUILIBRADO", "OFENSIVO"):
        raise HTTPException(status_code=400, detail="duty inválido")
    jugador = await db.get(Jugador, id_jugador)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    jugador.duty = duty
    await db.commit()
    return {"status": "ok", "id_jugador": id_jugador, "duty": duty}


@app.post("/jugadores/{id_jugador}/transferible", tags=["Equipos"])
async def marcar_transferible(id_jugador: int, datos: TransferibleIn, db: AsyncSession = Depends(get_db)):
    jugador = await db.get(Jugador, id_jugador)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    jugador.en_transferible = datos.en_transferible
    await db.commit()
    return {"status": "ok", "id_jugador": id_jugador, "en_transferible": jugador.en_transferible}


# ---------- TABLA DE POSICIONES ----------
@app.get("/tabla", tags=["Liga"])
async def obtener_tabla(id_liga: int | None = None, id_partida: int | None = None, db: AsyncSession = Depends(get_db)):
    if id_liga is None:
        equipo_usuario = await _equipo_usuario(db, id_partida) if id_partida else None
        id_liga = equipo_usuario.id_liga if equipo_usuario else None

    result = await db.execute(select(Equipo).where(Equipo.id_liga == id_liga))
    equipos = result.scalars().all()
    ordenados = sorted(
        equipos,
        key=lambda e: (-e.puntos, -(e.goles_favor - e.goles_contra), -e.goles_favor),
    )
    return {
        "id_liga": id_liga,
        "tabla": [
            {
                "id_equipo": e.id_equipo, "nombre": e.nombre, "es_usuario": e.es_usuario, "puntos": e.puntos,
                "jugados": e.jugados, "ganados": e.ganados, "empatados": e.empatados,
                "perdidos": e.perdidos, "goles_favor": e.goles_favor,
                "goles_contra": e.goles_contra,
                "diferencia_goles": e.goles_favor - e.goles_contra,
            }
            for e in ordenados
        ]
    }


# ---------- CALENDARIO ----------
@app.get("/calendario/{num_jornada}", tags=["Liga"])
async def ver_jornada(num_jornada: int, id_liga: int | None = None, id_partida: int | None = None, db: AsyncSession = Depends(get_db)):
    if id_liga is None:
        equipo_usuario = await _equipo_usuario(db, id_partida) if id_partida else None
        id_liga = equipo_usuario.id_liga if equipo_usuario else None

    result = await db.execute(
        select(Calendario).where(Calendario.num_jornada == num_jornada, Calendario.id_liga == id_liga)
    )
    fixtures = result.scalars().all()

    ids_equipos = {id_eq for f in fixtures for id_eq in (f.id_local, f.id_visitante)}
    equipos = (await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_equipos)))).scalars().all()
    nombres = {e.id_equipo: e.nombre for e in equipos}

    return {"jornada": num_jornada, "id_liga": id_liga, "partidos": [
        {"id_fixture": f.id_fixture, "id_local": f.id_local, "id_visitante": f.id_visitante,
         "nombre_local": nombres.get(f.id_local, "?"), "nombre_visitante": nombres.get(f.id_visitante, "?"),
         "fecha": f.fecha.isoformat(), "jugado": f.jugado,
         "goles_local": f.goles_local, "goles_visitante": f.goles_visitante}
        for f in fixtures
    ]}


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


@app.get("/calendario/equipo/{id_equipo}", tags=["Liga"])
async def calendario_equipo(id_equipo: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Calendario)
        .where(or_(Calendario.id_local == id_equipo, Calendario.id_visitante == id_equipo))
        .order_by(Calendario.fecha)
    )
    fixtures = result.scalars().all()

    ids_equipos = {id_eq for f in fixtures for id_eq in (f.id_local, f.id_visitante)}
    equipos = (await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_equipos)))).scalars().all()
    nombres = {e.id_equipo: e.nombre for e in equipos}
    nombres_competencia = await _nombres_competencia(db, fixtures[0].id_partida) if fixtures else {}

    return {"partidos": [
        {"id_fixture": f.id_fixture, "num_jornada": f.num_jornada, "fecha": f.fecha.isoformat(),
         "id_local": f.id_local, "id_visitante": f.id_visitante,
         "nombre_local": nombres.get(f.id_local, "?"), "nombre_visitante": nombres.get(f.id_visitante, "?"),
         "jugado": f.jugado, "goles_local": f.goles_local, "goles_visitante": f.goles_visitante,
         "tipo": f.tipo, "competencia": f.competencia, "ronda_copa": f.ronda_copa,
         "nombre_competencia": nombres_competencia.get(f.competencia) if f.competencia else None}
        for f in fixtures
    ]}


# ---------- TORNEOS INTERNACIONALES ----------
@app.get("/torneos", tags=["Torneos"])
async def obtener_torneos(id_partida: int, db: AsyncSession = Depends(get_db)):
    filas = (await db.execute(
        select(Calendario).where(Calendario.id_partida == id_partida, Calendario.tipo == "COPA")
    )).scalars().all()
    ids_equipos = {id_eq for f in filas for id_eq in (f.id_local, f.id_visitante)}
    nombres = {e.id_equipo: e.nombre for e in (
        await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_equipos)))
    ).scalars().all()} if ids_equipos else {}

    torneos = {}
    for confederacion, nombres_comp in COMPETENCIAS.items():
        for nivel, competencia in nombres_comp.items():
            fixtures_comp = [f for f in filas if f.competencia == competencia]
            if not fixtures_comp:
                continue
            torneos[competencia] = {
                "confederacion": confederacion, "nivel": nivel,
                "partidos": [
                    {
                        "id_fixture": f.id_fixture, "ronda_copa": f.ronda_copa, "num_jornada": f.num_jornada,
                        "fecha": f.fecha.isoformat(), "id_local": f.id_local, "id_visitante": f.id_visitante,
                        "nombre_local": nombres.get(f.id_local, "?"), "nombre_visitante": nombres.get(f.id_visitante, "?"),
                        "jugado": f.jugado, "goles_local": f.goles_local, "goles_visitante": f.goles_visitante,
                        "desempate_id_equipo": f.desempate_id_equipo,
                    }
                    for f in sorted(fixtures_comp, key=lambda x: (x.fecha, x.id_fixture))
                ],
            }
    return {"torneos": torneos}


def _once_titular(plantel: list[Jugador]) -> list[Jugador]:
    """Los 11 que realmente juegan: TITULAR primero; si por lesiones u otra
    razón no llegan a 11, se completa con SUPLENTE (mejor overall primero).
    La RESERVA nunca viaja con el plantel del partido, ni siquiera si faltan
    jugadores — en ese caso el equipo sale a la cancha con menos de 11."""
    disponibles = [p for p in plantel if not p.lesionado]
    titulares = [p for p in disponibles if p.rol == "TITULAR"]
    if len(titulares) >= 11:
        return titulares[:11]

    suplentes = sorted(
        (p for p in disponibles if p.rol == "SUPLENTE"),
        key=lambda p: p.overall, reverse=True,
    )
    return titulares + suplentes[:11 - len(titulares)]


# ---------- HELPER: ARMAR ALINEACIÓN Y DATOS PARA SIMULAR ----------
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

    tac_local_dict = {"formacion": tac_local.formacion, "mentalidad": tac_local.mentalidad, "presion": tac_local.presion}
    tac_visit_dict = {"formacion": tac_visit.formacion, "mentalidad": tac_visit.mentalidad, "presion": tac_visit.presion}

    return local, visit, plantel_local, plantel_visit, jl, jv, dict_local, dict_visit, tac_local_dict, tac_visit_dict


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
        await _crear_mensaje(
            db, id_equipo_usuario, "Cuerpo Técnico", f"Resultado: {local.nombre} {gh} - {gv} {visit.nombre}",
            f"Terminó el partido entre {local.nombre} y {visit.nombre}: {gh} a {gv}.",
            "PARTIDO", fecha,
        )


# ---------- HELPER: JUGAR UN FIXTURE COMPLETO (simulación rápida) ----------
async def _jugar_fixture(db: AsyncSession, fixture: Calendario) -> dict:
    local, visit, plantel_local, plantel_visit, jl, jv, dict_local, dict_visit, tac_local_dict, tac_visit_dict = await _preparar_lineup(db, fixture)
    return await _simular_y_finalizar(db, fixture, local, visit, plantel_local, plantel_visit, jl, jv, dict_local, dict_visit, tac_local_dict, tac_visit_dict)


async def _simular_y_finalizar(
    db: AsyncSession, fixture: Calendario, local: Equipo, visit: Equipo,
    plantel_local: list, plantel_visit: list, jl: list, jv: list, dict_local: list, dict_visit: list,
    tac_local_dict: dict, tac_visit_dict: dict,
) -> dict:
    """Núcleo de simular-un-fixture sin leer nada de la base — se usa tanto
    para el partido puntual del usuario (una consulta más arriba) como para
    resolver en lote el resto de la jornada (datos ya precargados)."""
    resultado = simulate_match(
        dict_local, dict_visit, tac_local_dict, tac_visit_dict,
        ia_local=not local.es_usuario,
        ia_visit=not visit.es_usuario,
        factor_medico_local=_factor_medico(local), factor_medico_visit=_factor_medico(visit),
    )

    _aplicar_efectos_fisicos(jl, jv, plantel_local, plantel_visit, resultado, _factor_medico(local), _factor_medico(visit))
    await _finalizar_fixture(db, fixture, local, visit, resultado["gh"], resultado["gv"])

    return {
        "id_local": fixture.id_local, "id_visitante": fixture.id_visitante,
        "nombre_local": local.nombre, "nombre_visitante": visit.nombre,
        "goles_local": resultado["gh"], "goles_visitante": resultado["gv"],
        "eventos": resultado["events"],
    }


# ---------- SIMULAR UN PARTIDO PUNTUAL (día de partido del usuario) ----------
@app.post("/partidos/simular", tags=["Simulación"])
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

    resultado = await _jugar_fixture(db, fixture)
    resultado["mercado_ia"], resultado["nueva_temporada"] = await _cerrar_jornada_del_dia(db, fixture)
    await db.commit()
    return resultado


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

        # Se calcula todo en memoria (nada de mutar objetos ORM acá) y se
        # manda como 3 UPDATE masivos al final — mutar ~2000 objetos uno por
        # uno hace que SQLAlchemy pierda el lote (executemany) apenas dos
        # jugadores no cambian exactamente las mismas columnas al mismo
        # valor, y eso son minutos de diferencia con la latencia de Neon.
        updates_jugador: list[dict] = []
        updates_equipo: list[dict] = []
        updates_fixture: list[dict] = []

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
            tac_local_dict = {"formacion": tac_local.formacion, "mentalidad": tac_local.mentalidad, "presion": tac_local.presion}
            tac_visit_dict = {"formacion": tac_visit.formacion, "mentalidad": tac_visit.mentalidad, "presion": tac_visit.presion}

            resultado = simulate_match(
                dict_local, dict_visit, tac_local_dict, tac_visit_dict,
                ia_local=not local.es_usuario, ia_visit=not visit.es_usuario,
                factor_medico_local=_factor_medico(local), factor_medico_visit=_factor_medico(visit),
            )
            updates_jugador.extend(_calcular_efectos_fisicos(
                plantel_local, plantel_visit, resultado, _factor_medico(local), _factor_medico(visit),
            ))
            if otro.tipo == "LIGA":
                updates_equipo.append(_calcular_update_equipo(local, resultado["gh"], resultado["gv"]))
                updates_equipo.append(_calcular_update_equipo(visit, resultado["gv"], resultado["gh"]))
            updates_fixture.append({
                "id_fixture": otro.id_fixture, "jugado": True,
                "goles_local": resultado["gh"], "goles_visitante": resultado["gv"],
            })

        if updates_jugador:
            await db.execute(update(Jugador), updates_jugador)
        if updates_equipo:
            await db.execute(update(Equipo), updates_equipo)
        if updates_fixture:
            await db.execute(update(Calendario), updates_fixture)

    fecha = await _fecha_actual(db, id_partida)
    log_ia: list[str] = []
    await ejecutar_ia_mercado(db, log_ia, fecha, id_partida)
    await _efectivizar_ofertas_pendientes(db, fecha, id_partida)
    await _avanzar_torneos_internacionales_si_corresponde(db, id_partida, fecha)
    nueva_temporada = await _procesar_fin_temporada_si_corresponde(db, fecha, id_partida)
    return log_ia, nueva_temporada


# ---------- JUGAR EL PARTIDO EN VIVO: PRIMER TIEMPO ----------
@app.post("/partidos/simular-primer-tiempo", tags=["Simulación"])
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

    resultado = simulate_match(
        dict_local, dict_visit, tac_local_dict, tac_visit_dict,
        ia_local=not local.es_usuario, ia_visit=not visit.es_usuario,
        minuto_inicio=1, minuto_fin=45,
        factor_medico_local=_factor_medico(local), factor_medico_visit=_factor_medico(visit),
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


# ---------- JUGAR EL PARTIDO EN VIVO: SEGUNDO TIEMPO (con cambios ya aplicados) ----------
@app.post("/partidos/simular-segundo-tiempo", tags=["Simulación"])
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

    resultado = simulate_match(
        dict_local, dict_visit, tac_local_dict, tac_visit_dict,
        ia_local=not local.es_usuario, ia_visit=not visit.es_usuario,
        minuto_inicio=46, minuto_fin=90, gh_inicial=gh_medio, gv_inicial=gv_medio,
        factor_medico_local=_factor_medico(local), factor_medico_visit=_factor_medico(visit),
    )

    _aplicar_efectos_fisicos(jl, jv, plantel_local, plantel_visit, resultado, _factor_medico(local), _factor_medico(visit))
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


# ---------- SIMULAR JORNADA COMPLETA ----------
@app.post("/jornada/simular", tags=["Simulación"])
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


# ---------- TÁCTICAS ----------
@app.get("/tacticas/{id_equipo}", tags=["Tácticas"])
async def obtener_tactica(id_equipo: int, db: AsyncSession = Depends(get_db)):
    tac = await db.get(Tactica, id_equipo)
    if not tac:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return {
        "id_equipo": tac.id_equipo, "formacion": tac.formacion,
        "mentalidad": tac.mentalidad, "presion": tac.presion, "estilo_pase": tac.estilo_pase,
    }


@app.post("/tacticas/configurar", tags=["Tácticas"])
async def configurar_tactica(datos: TacticaIn, db: AsyncSession = Depends(get_db)):
    tac = await db.get(Tactica, datos.id_equipo)
    if not tac:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    tac.formacion = datos.formacion
    tac.mentalidad = datos.mentalidad
    tac.presion = datos.presion
    tac.estilo_pase = datos.estilo_pase

    equipo = await db.get(Equipo, datos.id_equipo)
    fecha = await _fecha_actual(db, equipo.id_partida)
    await _crear_mensaje(
        db, datos.id_equipo, "Cuerpo Técnico", "Táctica actualizada",
        f"Se actualizó la táctica del equipo: formación {datos.formacion}, mentalidad {datos.mentalidad}, presión {datos.presion}.",
        "TACTICA", fecha,
    )

    await db.commit()
    return {"status": "ok", "mensaje": "Táctica actualizada"}


# ---------- ENTRENAMIENTO ----------
@app.post("/entrenamiento/configurar", tags=["Entrenamiento"])
async def configurar_entrenamiento(datos: EntrenamientoIn, db: AsyncSession = Depends(get_db)):
    plan = await db.get(PlanEntrenamiento, datos.id_equipo)
    if not plan:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    plan.foco = datos.foco
    plan.intensidad = datos.intensidad

    jugadores = (await db.execute(
        select(Jugador).where(Jugador.id_equipo == datos.id_equipo, Jugador.categoria == "PRIMERA")
    )).scalars().all()
    equipo = await db.get(Equipo, datos.id_equipo)
    # +1% de probabilidad de mejora por nivel de Centro de Entrenamiento (tope 20).
    bono_centro = (equipo.nivel_centro_entrenamiento if equipo else 0) * 0.01
    aplicar_entrenamiento(jugadores, datos.foco, datos.intensidad, bono_centro)

    fecha = await _fecha_actual(db, equipo.id_partida)
    await _crear_mensaje(
        db, datos.id_equipo, "Cuerpo Técnico", "Plan de entrenamiento actualizado",
        f"Se configuró el entrenamiento en modo {datos.foco}/{datos.intensidad}.",
        "ENTRENAMIENTO", fecha,
    )

    await db.commit()
    return {"status": "ok", "mensaje": f"Entrenamiento configurado en modo {datos.foco}/{datos.intensidad}"}


# ---------- MERCADO: LISTAR JUGADORES DISPONIBLES (de otros equipos, todas las ligas, + libres) ----------
@app.get("/mercado/jugadores", tags=["Transferencias"])
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


# ---------- MERCADO: OFERTAR POR UN JUGADOR (paso 1 — acordar precio con el club) ----------
@app.post("/fichajes/ofertar", tags=["Transferencias"])
async def ofertar_fichaje(datos: OfertaIn, db: AsyncSession = Depends(get_db)):
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


# ---------- MERCADO: OFERTAR POR UN JUGADOR (paso 2 — pactar contrato con el jugador) ----------
@app.post("/fichajes/negociar-contrato", tags=["Transferencias"])
async def negociar_contrato_traspaso(datos: NegociarContratoTraspasoIn, db: AsyncSession = Depends(get_db)):
    jugador = await db.get(Jugador, datos.id_jugador)
    if not jugador or not jugador.id_equipo:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    comprador = await db.get(Equipo, datos.id_equipo_comprador)
    vendedor = await db.get(Equipo, jugador.id_equipo)

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


# ---------- CONTRATOS ----------
@app.get("/contratos/{id_jugador}", tags=["Contratos"])
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


@app.post("/contratos/renovar", tags=["Contratos"])
async def renovar_contrato(datos: RenovarContratoIn, db: AsyncSession = Depends(get_db)):
    jugador = await db.get(Jugador, datos.id_jugador)
    if not jugador or not jugador.id_equipo:
        raise HTTPException(status_code=404, detail="Jugador no encontrado o sin club")

    equipo = await db.get(Equipo, jugador.id_equipo)
    if datos.ronda == 0:
        disposicion = disposicion_renovar(jugador.overall, jugador.edad, jugador.rol, jugador.moral, equipo.reputacion)
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
        mensaje = f"{jugador.nombre} renovó contrato hasta el {jugador.fecha_fin_contrato.strftime('%d/%m/%Y')} por ${money(datos.salario_propuesto)}/semana."
        await _crear_mensaje(db, jugador.id_equipo, "Secretaría Técnica", f"Renovación: {jugador.nombre}", mensaje, "CONTRATO", fecha)
        await db.commit()
        resultado["mensaje"] = mensaje

    return resultado


@app.post("/fichajes/precontrato", tags=["Transferencias"])
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


@app.post("/fichajes/fichar-libre", tags=["Transferencias"])
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
        equipo = await db.get(Equipo, datos.id_equipo)
        mensaje = f"Fichaste libre a {jugador.nombre} por ${money(datos.salario_ofrecido)}/semana."
        if equipo and equipo.es_usuario:
            await _crear_mensaje(db, datos.id_equipo, "Secretaría Técnica", f"Fichaje libre: {jugador.nombre}", mensaje, "MERCADO", fecha)
        await db.commit()
        resultado["mensaje"] = mensaje

    return resultado


# ---------- MERCADO: TODO LO QUE ESTÁ "EN NEGOCIACIÓN" PARA UN EQUIPO ----------
@app.get("/fichajes/en-negociacion", tags=["Transferencias"])
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
            "nombre_comprador": comprador.nombre if comprador else "?",
            "nombre_vendedor": vendedor.nombre if vendedor else "?",
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

    def _detalle_precontrato(j: Jugador, nombre_club: str) -> dict:
        return {
            "id_jugador": j.id_jugador, "nombre_jugador": j.nombre, "posicion": j.posicion,
            "posicion_especifica": j.posicion_especifica, "overall": j.overall, "potencial": j.potencial,
            "salario_precontrato": j.salario_precontrato,
            "fecha_fin_contrato": j.fecha_fin_contrato.isoformat() if j.fecha_fin_contrato else None,
            "nombre_club": nombre_club,
        }

    entrantes_por_id = {j.id_jugador: j for j in entrantes}
    entrantes_detalle = [_detalle_precontrato(j, clubes_precontrato.get(j.id_equipo).nombre if j.id_equipo and clubes_precontrato.get(j.id_equipo) else "Agente libre") for j in entrantes]
    reportes_precontrato = await _reportes_de(db, id_equipo, list(entrantes_por_id))
    for d in entrantes_detalle:
        _aplicar_fog(d, entrantes_por_id[d["id_jugador"]], reportes_precontrato.get(d["id_jugador"]))
    salientes_detalle = [_detalle_precontrato(j, clubes_precontrato[j.id_equipo_precontrato].nombre if j.id_equipo_precontrato in clubes_precontrato else "?") for j in salientes]

    return {
        "comprando": comprando_detalle,
        "vendiendo": [d for d in (_detalle(o) for o in vendiendo) if d],
        "recibidas": [d for d in (_detalle(o) for o in recibidas) if d],
        "precontratos_entrantes": entrantes_detalle,
        "precontratos_salientes": salientes_detalle,
    }


# ---------- MERCADO: OFERTAS QUE LA IA LE HIZO AL USUARIO ----------
@app.get("/fichajes/ofertas-recibidas", tags=["Transferencias"])
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


@app.post("/fichajes/responder", tags=["Transferencias"])
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


# ---------- CENTRO DE DESARROLLO (cantera propia) ----------
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


@app.get("/equipos/{id_equipo}/desarrollo", tags=["Desarrollo"])
async def obtener_desarrollo(id_equipo: int, db: AsyncSession = Depends(get_db)):
    equipo = await db.get(Equipo, id_equipo)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    await _asegurar_academia(db, equipo)

    jugadores = (await db.execute(
        select(Jugador).where(Jugador.id_equipo == id_equipo, Jugador.categoria == "PRIMERA")
    )).scalars().all()
    cedidos = (await db.execute(select(Jugador).where(Jugador.id_equipo_dueno == id_equipo))).scalars().all()
    nombres_prestamistas = {}
    if cedidos:
        ids_prestamistas = {j.id_equipo for j in cedidos if j.id_equipo}
        equipos_prestamistas = (await db.execute(select(Equipo).where(Equipo.id_equipo.in_(ids_prestamistas)))).scalars().all()
        nombres_prestamistas = {e.id_equipo: e.nombre for e in equipos_prestamistas}

    # Las 4 categorías son los jugadores REALES de la Academia (no un filtro
    # por edad sobre Primera como antes) — Centro de Desarrollo es donde el
    # DT ve de un vistazo lo importante de toda la cantera, no solo Primera.
    academia = (await db.execute(
        select(Jugador).where(Jugador.id_equipo == id_equipo, Jugador.categoria != "PRIMERA")
    )).scalars().all()
    por_categoria = {c: sorted((j for j in academia if j.categoria == c), key=lambda j: -j.potencial) for c in CATEGORIAS_ACADEMIA}

    # Destacados: los mejores prospectos de TODA la Academia (cualquier
    # categoría), la información más importante para el DT de un vistazo —
    # quién está más cerca de ser un golazo, sin importar en qué división esté.
    destacados = sorted(academia, key=lambda j: -j.potencial)[:8]

    candidatos = sorted(
        (j for j in jugadores if j.edad <= 21 and j.rol in ("TITULAR", "SUPLENTE")),
        key=lambda j: -j.overall,
    )

    en_desarrollo = sorted(
        (j for j in jugadores if j.edad <= 23 and (j.potencial - j.overall) > 0),
        key=lambda j: -(j.potencial - j.overall),
    )
    necesita_atencion = [j for j in en_desarrollo if j.rol == "RESERVA"][:5]
    a_vigilar = ([j for j in en_desarrollo if j.rol != "RESERVA"] or en_desarrollo)[:5]

    return {
        "nombre_equipo": equipo.nombre,
        "destacados_academia": [_jugador_desarrollo(j) for j in destacados],
        "sub13": {"jugadores": [_jugador_desarrollo(j) for j in por_categoria["SUB13"]], "resumen": _resumen_cantera(por_categoria["SUB13"], "Sub-13")},
        "sub15": {"jugadores": [_jugador_desarrollo(j) for j in por_categoria["SUB15"]], "resumen": _resumen_cantera(por_categoria["SUB15"], "Sub-15")},
        "sub18": {"jugadores": [_jugador_desarrollo(j) for j in por_categoria["SUB18"]], "resumen": _resumen_cantera(por_categoria["SUB18"], "Sub-18")},
        "sub21": {"jugadores": [_jugador_desarrollo(j) for j in por_categoria["SUB21"]], "resumen": _resumen_cantera(por_categoria["SUB21"], "Sub-21")},
        "candidatos_primer_equipo": [_jugador_desarrollo(j) for j in candidatos],
        "necesita_atencion": [_jugador_desarrollo(j) for j in necesita_atencion],
        "jugadores_a_vigilar": [_jugador_desarrollo(j) for j in a_vigilar],
        "cedidos": [
            {
                **_jugador_desarrollo(j),
                "club_prestamista": nombres_prestamistas.get(j.id_equipo, "?"),
                "fin_cesion": j.fin_cesion.isoformat() if j.fin_cesion else None,
                "opcion_compra": j.opcion_compra,
            }
            for j in cedidos
        ],
    }


# ---------- ACADEMIA: ver, mover de categoría, intake anual, reclutar ----------
def _agrupar_por_categoria(jugadores: list[Jugador]) -> dict:
    grupos = {c: [] for c in CATEGORIAS_ACADEMIA}
    for j in jugadores:
        if j.categoria in grupos:
            grupos[j.categoria].append(j)
    for c in grupos:
        grupos[c].sort(key=lambda j: -j.potencial)
    return grupos


@app.get("/equipos/{id_equipo}/academia", tags=["Academia"])
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


@app.post("/jugadores/{id_jugador}/categoria", tags=["Academia"])
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


@app.get("/equipos/{id_equipo}/academia/intake", tags=["Academia"])
async def obtener_intake_academia(id_equipo: int, db: AsyncSession = Depends(get_db)):
    candidatos = (await db.execute(
        select(Jugador).where(Jugador.id_equipo_intake == id_equipo, Jugador.id_equipo.is_(None))
    )).scalars().all()
    grupos = _agrupar_por_categoria(candidatos)
    return {c.lower(): [_jugador_desarrollo(j) for j in lista] for c, lista in grupos.items()}


@app.post("/jugadores/{id_jugador}/intake/decidir", tags=["Academia"])
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


@app.post("/jugadores/{id_jugador}/reclutar-juvenil", tags=["Academia"])
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


# ---------- ECONOMÍA DEL CLUB ----------
@app.get("/equipos/{id_equipo}/economia", tags=["Economía"])
async def obtener_economia(id_equipo: int, db: AsyncSession = Depends(get_db)):
    equipo = await db.get(Equipo, id_equipo)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    jugadores = (await db.execute(select(Jugador).where(Jugador.id_equipo == id_equipo))).scalars().all()

    masa_salarial_semanal = sum(j.salario for j in jugadores)
    valor_plantilla = sum(j.valor_mercado for j in jugadores)
    top_sueldos = sorted(jugadores, key=lambda j: -j.salario)[:5]

    ratio = (masa_salarial_semanal / equipo.presupuesto_salarios) if equipo.presupuesto_salarios else 0
    if ratio <= 0.75:
        estado_ffp, color_ffp = "Cumple con margen", "verde"
    elif ratio <= 1.0:
        estado_ffp, color_ffp = "Al límite del presupuesto", "amarillo"
    else:
        estado_ffp, color_ffp = "Excedido — riesgo de sanciones", "rojo"

    return {
        "nombre_equipo": equipo.nombre,
        "presupuesto_fichajes": equipo.presupuesto_fichajes,
        "presupuesto_salarios": equipo.presupuesto_salarios,
        "masa_salarial_semanal": masa_salarial_semanal,
        "valor_plantilla": valor_plantilla,
        "reputacion": equipo.reputacion,
        "cantidad_jugadores": len(jugadores),
        "estado_ffp": estado_ffp,
        "color_ffp": color_ffp,
        "ratio_masa_salarial": round(ratio, 3),
        "top_sueldos": [
            {"id_jugador": j.id_jugador, "nombre": j.nombre, "posicion": j.posicion, "posicion_especifica": j.posicion_especifica, "salario": j.salario, "overall": j.overall}
            for j in top_sueldos
        ],
    }


# ---------- INFRAESTRUCTURA ----------
@app.get("/equipos/{id_equipo}/infraestructura", tags=["Infraestructura"])
async def obtener_infraestructura(id_equipo: int, db: AsyncSession = Depends(get_db)):
    equipo = await db.get(Equipo, id_equipo)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    pendientes = (await db.execute(
        select(SolicitudObra).where(SolicitudObra.id_equipo == id_equipo, SolicitudObra.estado == "PENDIENTE")
    )).scalars().all()
    pendientes_por_tipo = {s.tipo_instalacion: s for s in pendientes}

    instalaciones = []
    for tipo in COSTO_BASE_INSTALACION:
        nivel_actual = getattr(equipo, f"nivel_{tipo}")
        solicitud = pendientes_por_tipo.get(tipo)
        instalaciones.append({
            "tipo": tipo,
            "nombre": NOMBRE_INSTALACION[tipo],
            "nivel_actual": nivel_actual,
            "costo_proximo_nivel": costo_mejora_instalacion(tipo, nivel_actual) if nivel_actual < 20 else None,
            "mantenimiento_mensual_actual": mantenimiento_mensual_instalacion(tipo, nivel_actual),
            "solicitud_pendiente": {
                "id_solicitud": solicitud.id_solicitud,
                "nivel_objetivo": solicitud.nivel_objetivo,
                "costo": solicitud.costo,
                "fecha_solicitud": solicitud.fecha_solicitud.isoformat(),
                "fecha_resolucion": solicitud.fecha_resolucion.isoformat(),
            } if solicitud else None,
        })

    return {
        "presupuesto_fichajes": equipo.presupuesto_fichajes,
        "instalaciones": instalaciones,
    }


@app.post("/infraestructura/solicitar", tags=["Infraestructura"])
async def solicitar_obra(datos: SolicitarObraIn, db: AsyncSession = Depends(get_db)):
    equipo = await db.get(Equipo, datos.id_equipo)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    if datos.tipo_instalacion not in COSTO_BASE_INSTALACION:
        raise HTTPException(status_code=400, detail="Tipo de instalación inválido")

    nivel_actual = getattr(equipo, f"nivel_{datos.tipo_instalacion}")
    if nivel_actual >= 20:
        raise HTTPException(status_code=400, detail="Esta instalación ya está en su nivel máximo")

    ya_pendiente = (await db.execute(
        select(SolicitudObra).where(
            SolicitudObra.id_equipo == datos.id_equipo,
            SolicitudObra.tipo_instalacion == datos.tipo_instalacion,
            SolicitudObra.estado == "PENDIENTE",
        )
    )).scalars().first()
    if ya_pendiente:
        raise HTTPException(status_code=400, detail="Ya hay una solicitud pendiente para esta instalación")

    costo = costo_mejora_instalacion(datos.tipo_instalacion, nivel_actual)
    partida = await db.get(Partida, equipo.id_partida)
    confianza = partida.confianza_directiva if partida else directiva_engine.CONFIANZA_INICIAL
    dias = directiva_engine.dias_espera_obra(confianza, costo, equipo.presupuesto_fichajes)
    fecha = await _fecha_actual(db, equipo.id_partida)
    fecha_resolucion = fecha + timedelta(days=dias)

    solicitud = SolicitudObra(
        id_partida=equipo.id_partida, id_equipo=datos.id_equipo, tipo_instalacion=datos.tipo_instalacion,
        nivel_objetivo=nivel_actual + 1, costo=costo, fecha_solicitud=fecha, fecha_resolucion=fecha_resolucion,
    )
    db.add(solicitud)

    nombre_instalacion = NOMBRE_INSTALACION[datos.tipo_instalacion]
    await _crear_mensaje(
        db, datos.id_equipo, "Directiva del Club", f"Solicitud enviada: {nombre_instalacion}",
        f"Se elevó a la directiva el pedido de mejorar {nombre_instalacion} a nivel {nivel_actual + 1} "
        f"(costo ${money(costo)}). Estimamos una respuesta para el {fecha_resolucion.strftime('%d/%m/%Y')}.",
        "SISTEMA", fecha,
    )

    await db.commit()
    return {
        "status": "ok", "mensaje": f"Solicitud enviada a la directiva, respuesta estimada el {fecha_resolucion.strftime('%d/%m/%Y')}",
        "fecha_resolucion": fecha_resolucion.isoformat(),
    }


# ---------- MERCADO: RECOMENDACIONES ESTILO SCOUTING ----------
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


@app.get("/fichajes/recomendaciones", tags=["Transferencias"])
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
            "club": nombre_club or "Agente Libre", "es_libre": j.id_equipo is None,
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


# ---------- CUERPO TÉCNICO + SCOUTING ----------
@app.get("/equipos/{id_equipo}/cuerpo-tecnico", tags=["Cuerpo Técnico"])
async def obtener_cuerpo_tecnico(id_equipo: int, db: AsyncSession = Depends(get_db)):
    equipo = await db.get(Equipo, id_equipo)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    personal = await db.get(PersonalTecnico, id_equipo)
    tactica = await db.get(Tactica, id_equipo)

    plantel = (await db.execute(select(Jugador).where(Jugador.id_equipo == id_equipo))).scalars().all()
    promedios = _promedios_por_posicion(plantel)
    opinion = (
        _opinion_tactica(tactica, promedios, plantel) if tactica and plantel
        else "Todavía no tengo plantel suficiente para darte una opinión formada."
    )

    ojeadores = (await db.execute(select(Ojeador).where(Ojeador.id_equipo == id_equipo))).scalars().all()
    ids_asignados = [o.id_jugador_asignado for o in ojeadores if o.id_jugador_asignado]
    objetivos = {j.id_jugador: j for j in (
        (await db.execute(select(Jugador).where(Jugador.id_jugador.in_(ids_asignados)))).scalars().all()
        if ids_asignados else []
    )}
    reportes = await _reportes_de(db, id_equipo, ids_asignados)

    ojeadores_out = []
    for o in ojeadores:
        asignado = None
        objetivo = objetivos.get(o.id_jugador_asignado) if o.id_jugador_asignado else None
        if objetivo:
            reporte = reportes.get(objetivo.id_jugador)
            progreso = reporte.progreso if reporte else 0
            asignado = {
                "id_jugador": objetivo.id_jugador, "nombre": objetivo.nombre,
                "posicion": objetivo.posicion, "posicion_especifica": objetivo.posicion_especifica,
                "progreso": progreso,
                "overall_rango": None if progreso >= 100 else _rango_fog(objetivo.overall, progreso),
                "overall": objetivo.overall if progreso >= 100 else None,
                "potencial_rango": None if progreso >= 100 else _rango_fog(objetivo.potencial, progreso),
                "potencial": objetivo.potencial if progreso >= 100 else None,
            }
        ojeadores_out.append({
            "id_ojeador": o.id_ojeador, "nombre": o.nombre, "calidad": o.calidad, "asignado": asignado,
        })

    plan = await db.get(PlanEntrenamiento, id_equipo)
    return {
        "asistente": {"nombre": personal.nombre_asistente if personal else "?", "opinion": opinion},
        "entrenamiento": {
            "foco": plan.foco if plan else "EQUILIBRADO",
            "intensidad": plan.intensidad if plan else "MEDIA",
            "consejo": _consejo_entrenamiento(plantel),
        },
        "ojeadores": ojeadores_out,
    }


@app.post("/scouting/asignar", tags=["Cuerpo Técnico"])
async def asignar_scouting(datos: dict, db: AsyncSession = Depends(get_db)):
    ojeador = await db.get(Ojeador, datos.get("id_ojeador"))
    if not ojeador:
        raise HTTPException(status_code=404, detail="Ojeador no encontrado")
    id_jugador = datos.get("id_jugador")
    jugador = await db.get(Jugador, id_jugador)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    ojeador.id_jugador_asignado = id_jugador
    reporte = await db.get(ReporteScouting, (ojeador.id_equipo, id_jugador))
    if not reporte:
        db.add(ReporteScouting(id_equipo=ojeador.id_equipo, id_jugador=id_jugador, id_partida=ojeador.id_partida, progreso=0))
    await db.commit()
    return {"status": "ok"}


@app.post("/scouting/quitar", tags=["Cuerpo Técnico"])
async def quitar_scouting(datos: dict, db: AsyncSession = Depends(get_db)):
    ojeador = await db.get(Ojeador, datos.get("id_ojeador"))
    if not ojeador:
        raise HTTPException(status_code=404, detail="Ojeador no encontrado")
    ojeador.id_jugador_asignado = None
    await db.commit()
    return {"status": "ok"}


# ---------- MERCADO: OFRECER UN JUGADOR PROPIO A LA IA ----------
@app.post("/fichajes/ofrecer", tags=["Transferencias"])
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


# ---------- MERCADO: CEDER UN JUGADOR A PRÉSTAMO ----------
DURACIONES_CESION_VALIDAS = {6: 182, 12: 365}


@app.post("/fichajes/ceder", tags=["Transferencias"])
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

    jugador.id_equipo_dueno = dueno.id_equipo
    jugador.id_equipo = club_aceptante.id_equipo
    jugador.fin_cesion = fecha + timedelta(days=DURACIONES_CESION_VALIDAS[datos.duracion_meses])
    jugador.opcion_compra = datos.opcion_compra
    jugador.rol = "RESERVA"

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


# ---------- CATÁLOGO DE CLUBES (estático, para elegir equipo al crear carrera) ----------
@app.get("/catalogo/clubes", tags=["Carreras"])
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


# ---------- CARRERAS (guardados independientes) ----------
@app.get("/partidas", tags=["Carreras"])
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


@app.delete("/partidas/{id_partida}", tags=["Carreras"])
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

    if fixture_ids:
        await db.execute(delete(EventoPartido).where(EventoPartido.id_fixture.in_(fixture_ids)))
    if equipo_ids:
        await db.execute(delete(Mensaje).where(Mensaje.id_equipo_destino.in_(equipo_ids)))
    if jugador_ids:
        await db.execute(delete(OfertaFichaje).where(OfertaFichaje.id_jugador.in_(jugador_ids)))
    await db.execute(delete(HistorialTemporada).where(HistorialTemporada.id_partida == id_partida))
    if equipo_ids:
        await db.execute(delete(Tactica).where(Tactica.id_equipo.in_(equipo_ids)))
        await db.execute(delete(PlanEntrenamiento).where(PlanEntrenamiento.id_equipo.in_(equipo_ids)))
        await db.execute(delete(PersonalTecnico).where(PersonalTecnico.id_equipo.in_(equipo_ids)))
        await db.execute(delete(ReporteScouting).where(ReporteScouting.id_equipo.in_(equipo_ids)))
        await db.execute(delete(Ojeador).where(Ojeador.id_equipo.in_(equipo_ids)))
    await db.execute(delete(Jugador).where(Jugador.id_partida == id_partida))
    await db.execute(delete(Calendario).where(Calendario.id_partida == id_partida))
    await db.execute(delete(Equipo).where(Equipo.id_partida == id_partida))
    await db.execute(delete(Liga).where(Liga.id_partida == id_partida))
    await db.execute(delete(CicloTemporada).where(CicloTemporada.id_partida == id_partida))
    await db.delete(partida)
    await db.commit()
    return {"status": "ok"}


@app.post("/partidas", tags=["Carreras"])
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
    id_paquete = datos.get("id_paquete_clubes")
    if id_paquete:
        paquete = await db.get(PaqueteClubes, id_paquete)
        if paquete:
            if not nombres_custom:
                nombres_custom = json.loads(paquete.nombres_json)
            if not jugadores_custom and paquete.jugadores_json:
                jugadores_custom = json.loads(paquete.jugadores_json)
            if not competencias_custom and paquete.competencias_json:
                competencias_custom = json.loads(paquete.competencias_json)

    id_partida = await crear_partida(
        db, nombre_dt=nombre_dt, dataset=dataset,
        codigo_liga_elegida=datos.get("codigo_liga"),
        nombre_club_elegido=datos.get("nombre_club"),
        nombres_clubes_custom=nombres_custom,
        jugadores_clubes_custom=jugadores_custom,
        competencias_custom=competencias_custom,
        ligas_completas=datos.get("ligas_completas"),
    )
    partida = await db.get(Partida, id_partida)
    equipo_usuario = await _equipo_usuario(db, id_partida)
    return {
        "id_partida": id_partida,
        "nombre_club": equipo_usuario.nombre if equipo_usuario else None,
        "objetivo_temporada": partida.objetivo_temporada,
        "contrato_dt_anios": partida.contrato_dt_anios,
        "contrato_dt_fecha_fin": partida.contrato_dt_fecha_fin.isoformat() if partida.contrato_dt_fecha_fin else None,
    }


# ---------- DIRECTIVA: objetivo, confianza, despido, fin de contrato, renuncia ----------
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


@app.get("/partidas/{id_partida}/directiva", tags=["Directiva"])
async def obtener_directiva(id_partida: int, db: AsyncSession = Depends(get_db)):
    partida = await db.get(Partida, id_partida)
    if not partida:
        raise HTTPException(status_code=404, detail="Partida no encontrada")
    dias_restantes = (partida.contrato_dt_fecha_fin - partida.fecha_actual).days if partida.contrato_dt_fecha_fin else None
    return {
        "confianza_directiva": partida.confianza_directiva,
        "balance_dt": partida.balance_dt,
        "objetivo_temporada": partida.objetivo_temporada,
        "contrato_dt_anios": partida.contrato_dt_anios,
        "contrato_dt_fecha_fin": partida.contrato_dt_fecha_fin.isoformat() if partida.contrato_dt_fecha_fin else None,
        "dias_restantes_contrato": dias_restantes,
        "estado_dt": partida.estado_dt,
        "ofertas": await _ofertas_dt_out(db, id_partida) if partida.estado_dt != "NORMAL" else [],
    }


@app.post("/partidas/{id_partida}/renunciar", tags=["Directiva"])
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


@app.post("/partidas/{id_partida}/elegir-destino", tags=["Directiva"])
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


# ---------- PAQUETES DE CLUBES PERSONALIZADOS (reusables entre carreras) ----------
@app.get("/paquetes-clubes", tags=["Carreras"])
async def listar_paquetes_clubes(db: AsyncSession = Depends(get_db)):
    paquetes = (await db.execute(select(PaqueteClubes).order_by(PaqueteClubes.fecha_creacion.desc()))).scalars().all()
    salida = []
    for p in paquetes:
        nombres = json.loads(p.nombres_json)
        salida.append({
            "id_paquete": p.id_paquete, "nombre": p.nombre,
            "fecha_creacion": p.fecha_creacion.isoformat(),
            "cantidad_ligas": len(nombres), "cantidad_clubes": sum(len(v) for v in nombres.values()),
        })
    return salida


@app.get("/paquetes-clubes/{id_paquete}", tags=["Carreras"])
async def obtener_paquete_clubes(id_paquete: int, db: AsyncSession = Depends(get_db)):
    paquete = await db.get(PaqueteClubes, id_paquete)
    if not paquete:
        raise HTTPException(status_code=404, detail="Paquete no encontrado")
    return {
        "id_paquete": paquete.id_paquete, "nombre": paquete.nombre,
        "nombres_clubes": json.loads(paquete.nombres_json),
        "jugadores_clubes": json.loads(paquete.jugadores_json) if paquete.jugadores_json else None,
        "competencias": json.loads(paquete.competencias_json) if paquete.competencias_json else None,
    }


@app.post("/paquetes-clubes", tags=["Carreras"])
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
    paquete = PaqueteClubes(
        nombre=nombre, nombres_json=json.dumps(nombres_clubes),
        jugadores_json=json.dumps(jugadores_clubes) if jugadores_clubes else None,
        competencias_json=json.dumps(competencias) if competencias else None,
    )
    db.add(paquete)
    await db.commit()
    await db.refresh(paquete)
    return {"id_paquete": paquete.id_paquete}


@app.delete("/paquetes-clubes/{id_paquete}", tags=["Carreras"])
async def borrar_paquete_clubes(id_paquete: int, db: AsyncSession = Depends(get_db)):
    paquete = await db.get(PaqueteClubes, id_paquete)
    if not paquete:
        raise HTTPException(status_code=404, detail="Paquete no encontrado")
    await db.delete(paquete)
    await db.commit()
    return {"status": "ok"}


# ---------- ADMIN: POBLAR LA LIGA ----------
@app.post("/admin/seed", tags=["Admin"])
async def seed_endpoint(reset: bool = False):
    from seed import seed
    await seed(reset=reset)
    return {"status": "ok"}
