from datetime import datetime, date

from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, DateTime, Date, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Partida(Base):
    """Una carrera/guardado independiente: su propio DT, su propio mundo de
    ligas/equipos/jugadores/calendario (todo lo demás se filtra por
    `id_partida`) y su propia fecha actual (reemplaza al viejo singleton
    `EstadoJuego`)."""
    __tablename__ = "partidas"

    id_partida: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre_dt: Mapped[str] = mapped_column(String(100), nullable=False)
    dataset: Mapped[str] = mapped_column(String(20), default="ficticia")  # ficticia, personalizada
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    fecha_actual: Mapped[date] = mapped_column(Date, nullable=False)

    # Contrato del DT con la directiva, ofrecido al crear la carrera — la
    # base para medir objetivo cumplido / confianza / riesgo de despido en
    # la pantalla de Directiva.
    objetivo_temporada: Mapped[str] = mapped_column(String(255), default="")
    contrato_dt_anios: Mapped[int] = mapped_column(Integer, default=1)
    contrato_dt_fecha_fin: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Paciencia del club ACTUAL con el DT — sube/baja en cada fin de
    # temporada de SU liga según si cumplió el objetivo. Si toca el piso,
    # despido inmediato sin esperar a que termine el contrato. Se resetea a
    # 60 cada vez que arranca en un club nuevo (propio o ajeno).
    confianza_directiva: Mapped[int] = mapped_column(Integer, default=60)
    # Trayectoria de TODA la carrera del DT (no se resetea al cambiar de
    # club) — es lo que un club rival mira si el usuario renuncia por su cuenta.
    balance_dt: Mapped[int] = mapped_column(Integer, default=50)
    # NORMAL | DESPEDIDO | CONTRATO_FIN_EXITO | CONTRATO_FIN_RENOVACION_OFRECIDA
    # | CONTRATO_FIN_SIN_RENOVACION | RENUNCIO — mientras no sea NORMAL, el
    # frontend bloquea el juego y muestra la pantalla de elegir destino.
    estado_dt: Mapped[str] = mapped_column(String(30), default="NORMAL")

    # Nombres personalizados de las copas internacionales para ESTA partida
    # (dataset personalizada), fijados al crearla a partir de
    # PaqueteClubes.competencias_json — {"CAMPEONES_UEFA": "...", ...}. NULL
    # o clave ausente = se usa el nombre ficticio por defecto (ver
    # engine/copa_engine.py NOMBRES_COMPETENCIA_DEFAULT).
    competencias_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class Liga(Base):
    __tablename__ = "ligas"

    id_liga: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_partida: Mapped[int] = mapped_column(ForeignKey("partidas.id_partida"))
    codigo: Mapped[str] = mapped_column(String(10), nullable=False)  # ARG1, BRA1, ESP1, ING1... (único POR partida, no global)
    pais: Mapped[str] = mapped_column(String(60), nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    confederacion: Mapped[str] = mapped_column(String(10), default="UEFA")  # UEFA | CONMEBOL
    # COMPLETA: tiene fixture y tabla propia. VISTA: existe con clubes y
    # jugadores generados (scouteables, transferibles, elegibles para
    # torneos internacionales) pero sin liga doméstica jugándose.
    modo: Mapped[str] = mapped_column(String(10), default="COMPLETA")

    equipos: Mapped[list["Equipo"]] = relationship(back_populates="liga")


class CicloTemporada(Base):
    """Reloj de temporada de UNA confederación dentro de una partida. UEFA y
    CONMEBOL corren temporadas independientes (arrancan/cierran en fechas
    reales distintas) aunque comparten el mismo contador de día
    (`Partida.fecha_actual`) — ver `_procesar_fin_temporada_confederacion`
    en main.py."""
    __tablename__ = "ciclo_temporada"

    id_partida: Mapped[int] = mapped_column(ForeignKey("partidas.id_partida"), primary_key=True)
    confederacion: Mapped[str] = mapped_column(String(10), primary_key=True)
    temporada: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)


class OfertaClubDT(Base):
    """Una de las 3 ofertas de club vigentes mientras `Partida.estado_dt` no
    es NORMAL (despido, fin de contrato sin renovar, o renuncia) — ver
    engine/directiva_engine.py."""
    __tablename__ = "ofertas_club_dt"

    id_oferta: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_partida: Mapped[int] = mapped_column(ForeignKey("partidas.id_partida"))
    id_equipo: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"))


class Mensaje(Base):
    __tablename__ = "mensajes"

    id_mensaje: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_equipo_destino: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"))
    remitente: Mapped[str] = mapped_column(String(100), nullable=False)
    asunto: Mapped[str] = mapped_column(String(200), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, default="")
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    leido: Mapped[bool] = mapped_column(Boolean, default=False)
    tipo: Mapped[str] = mapped_column(String(20), default="SISTEMA")  # SISTEMA, MERCADO, PARTIDO, TACTICA, ENTRENAMIENTO
    id_oferta: Mapped[int | None] = mapped_column(ForeignKey("ofertas_fichaje.id_oferta"), nullable=True)


class Equipo(Base):
    __tablename__ = "equipos"

    id_equipo: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_partida: Mapped[int] = mapped_column(ForeignKey("partidas.id_partida"))
    id_liga: Mapped[int] = mapped_column(ForeignKey("ligas.id_liga"))
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(String(10), default="#173C2E")
    es_usuario: Mapped[bool] = mapped_column(Boolean, default=False)
    reputacion: Mapped[int] = mapped_column(Integer, default=50)
    # Capitán del plantel PRIMERA (opcional): su liderazgo atenúa el
    # castigo de vestuario cuando el ánimo del plantel está dividido —
    # ver _puntaje_vestuario en main.py.
    id_capitan: Mapped[int | None] = mapped_column(ForeignKey("jugadores.id_jugador"), nullable=True)
    # URL de escudo provista por un tercero (su propio hosting) al crear la
    # partida con datos personalizados — el juego solo la muestra con
    # <img>, nunca la descarga ni la aloja. NULL = sin escudo, se muestra
    # el color/inicial del club como antes.
    escudo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    liga: Mapped["Liga"] = relationship(back_populates="equipos")

    presupuesto_fichajes: Mapped[int] = mapped_column(Integer, default=800_000)
    presupuesto_salarios: Mapped[int] = mapped_column(Integer, default=200_000)

    # Estadísticas de liga
    puntos: Mapped[int] = mapped_column(Integer, default=0)
    jugados: Mapped[int] = mapped_column(Integer, default=0)
    ganados: Mapped[int] = mapped_column(Integer, default=0)
    empatados: Mapped[int] = mapped_column(Integer, default=0)
    perdidos: Mapped[int] = mapped_column(Integer, default=0)
    goles_favor: Mapped[int] = mapped_column(Integer, default=0)
    goles_contra: Mapped[int] = mapped_column(Integer, default=0)

    # Red de marca (estilo Red Bull: RB Leipzig / RB Bragantino) — clubes con
    # el mismo tag comparten identidad/metodología. NULL = sin red de marca.
    # No es una relación de accionista (ver AfiliacionClub para eso) y no es
    # comprable/vendible: se fija una sola vez al generar el mundo.
    red_marca: Mapped[str | None] = mapped_column(String(30), nullable=True)

    jugadores: Mapped[list["Jugador"]] = relationship(
        back_populates="equipo", foreign_keys="Jugador.id_equipo", cascade="all, delete-orphan"
    )
    tactica: Mapped["Tactica"] = relationship(back_populates="equipo", uselist=False, cascade="all, delete-orphan")
    plan_entrenamiento: Mapped["PlanEntrenamiento"] = relationship(back_populates="equipo", uselist=False, cascade="all, delete-orphan")
    personal_tecnico: Mapped["PersonalTecnico"] = relationship(back_populates="equipo", uselist=False, cascade="all, delete-orphan")


class AfiliacionClub(Base):
    """Participación accionaria de un club en otro — cubre los 3 modelos
    multiclub comprables/vendibles (PROPIETARIO/SATELITE/MINORITARIO, ver
    engine/multiclub_engine.py::tipo_relacion_por_porcentaje). Una fila por
    par (inversor, participado); comprar más actualiza el porcentaje en la
    misma fila en vez de insertar otra."""
    __tablename__ = "afiliaciones_club"

    id_afiliacion: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_partida: Mapped[int] = mapped_column(ForeignKey("partidas.id_partida"))
    id_equipo_inversor: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"))
    id_equipo_participado: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"))
    porcentaje: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo_relacion: Mapped[str] = mapped_column(String(15), nullable=False)  # PROPIETARIO, SATELITE, MINORITARIO
    fecha_adquisicion: Mapped[date] = mapped_column(Date, nullable=False)
    # Solo togglable por el inversor cuando tipo_relacion es SATELITE o
    # PROPIETARIO — habilita el pipeline de préstamos/transferencias y
    # gestionar táctica/entrenamiento/fichajes del participado (ver
    # clubActivo en el frontend y ejecutar_ia_mercado, que lo excluye del
    # mercado autónomo de la IA mientras esté habilitado).
    influencia_habilitada: Mapped[bool] = mapped_column(Boolean, default=False)


class SolicitudParticipacion(Base):
    """Pedido de compra o venta de participación en otro club, con DOS
    aprobaciones secuenciales: primero tu propia directiva (gastar/aceptar
    cobrar), después la directiva del club contraparte (ceder/recomprar la
    participación) — ver engine/multiclub_engine.py::evaluar_directiva_propia
    / evaluar_directiva_contraparte y _procesar_solicitudes_participacion en
    main.py (llamado desde avanzar_dia)."""
    __tablename__ = "solicitudes_participacion"

    id_solicitud: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_partida: Mapped[int] = mapped_column(ForeignKey("partidas.id_partida"))
    id_equipo_iniciador: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"))
    id_equipo_contraparte: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"))
    operacion: Mapped[str] = mapped_column(String(10), nullable=False)  # COMPRAR, VENDER
    porcentaje: Mapped[int] = mapped_column(Integer, nullable=False)
    monto: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_solicitud: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_resolucion: Mapped[date] = mapped_column(Date, nullable=False)
    fase: Mapped[str] = mapped_column(String(25), default="DIRECTIVA_PROPIA")  # DIRECTIVA_PROPIA, DIRECTIVA_CONTRAPARTE
    estado: Mapped[str] = mapped_column(String(25), default="PENDIENTE")
    # PENDIENTE, RECHAZADA_PROPIA, RECHAZADA_CONTRAPARTE, CONCRETADA


class Jugador(Base):
    __tablename__ = "jugadores"

    id_jugador: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_partida: Mapped[int] = mapped_column(ForeignKey("partidas.id_partida"))
    id_equipo: Mapped[int | None] = mapped_column(ForeignKey("equipos.id_equipo"), nullable=True)

    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    posicion: Mapped[str] = mapped_column(String(10), default="MED")  # POR, DEF, MED, DEL
    # Posición específica dentro de la amplia (DFC/DFI/DFD, MCD/MC/MCO/MI/MD,
    # EI/ED/DC/MP) — solo para tácticas/formación, ver data_gen.py.
    posicion_especifica: Mapped[str | None] = mapped_column(String(5), nullable=True)
    nacionalidad: Mapped[str] = mapped_column(String(40), default="Argentina")
    edad: Mapped[int] = mapped_column(Integer, default=20)

    # Estos 4 son PROMEDIOS DERIVADOS de los atributos de abajo (se recalculan
    # cada vez que cambia alguno de sus componentes, ver
    # engine/data_gen.py::recalcular_derivados) — se mantienen como columnas
    # propias porque overall/el motor de partido/las negociaciones/la IA de
    # jugadores siguen leyendo estos 4 nomás, sin tocarse por esta ampliación.
    ataque: Mapped[int] = mapped_column(Integer, default=50)
    defensa: Mapped[int] = mapped_column(Integer, default=50)
    pase: Mapped[int] = mapped_column(Integer, default=50)
    fisico: Mapped[int] = mapped_column(Integer, default=50)
    potencial: Mapped[int] = mapped_column(Integer, default=65)

    # Atributos detallados estilo FM, TODOS en escala 1-99 (no 1-20) para ser
    # consistentes con el resto del juego. Técnico (alimentan ataque/defensa/
    # pase derivados — ver fórmulas en data_gen.py):
    finalizacion: Mapped[int] = mapped_column(Integer, default=50)
    regate: Mapped[int] = mapped_column(Integer, default=50)
    primer_toque: Mapped[int] = mapped_column(Integer, default=50)
    centros: Mapped[int] = mapped_column(Integer, default=50)
    cabeceo: Mapped[int] = mapped_column(Integer, default=50)
    marcaje: Mapped[int] = mapped_column(Integer, default=50)
    entradas: Mapped[int] = mapped_column(Integer, default=50)
    tiros_lejanos: Mapped[int] = mapped_column(Integer, default=50)
    # Mental — hoy son "de sabor" (se muestran en la ficha, no alimentan
    # ningún cálculo todavía; salvo valentía y visión/decisiones, que sí
    # entran en defensa/pase derivados).
    agresividad: Mapped[int] = mapped_column(Integer, default=50)
    valentia: Mapped[int] = mapped_column(Integer, default=50)
    decisiones: Mapped[int] = mapped_column(Integer, default=50)
    concentracion: Mapped[int] = mapped_column(Integer, default=50)
    anticipacion: Mapped[int] = mapped_column(Integer, default=50)
    compostura: Mapped[int] = mapped_column(Integer, default=50)
    vision: Mapped[int] = mapped_column(Integer, default=50)
    liderazgo: Mapped[int] = mapped_column(Integer, default=50)
    # Físico (alimentan fisico derivado).
    ritmo: Mapped[int] = mapped_column(Integer, default=50)
    aceleracion: Mapped[int] = mapped_column(Integer, default=50)
    resistencia: Mapped[int] = mapped_column(Integer, default=50)
    fuerza: Mapped[int] = mapped_column(Integer, default=50)
    agilidad: Mapped[int] = mapped_column(Integer, default=50)
    # Portería: un solo atributo compuesto (no se desglosa en reflejos/juego
    # de pies/colocación por separado) — solo relevante para POR.
    porteria: Mapped[int] = mapped_column(Integer, default=50)

    energia: Mapped[int] = mapped_column(Integer, default=100)
    moral: Mapped[int] = mapped_column(Integer, default=75)

    valor_mercado: Mapped[int] = mapped_column(Integer, default=50_000)
    salario: Mapped[int] = mapped_column(Integer, default=2_000)

    lesionado: Mapped[bool] = mapped_column(Boolean, default=False)
    semanas_lesion: Mapped[int] = mapped_column(Integer, default=0)
    tipo_lesion: Mapped[str | None] = mapped_column(String(50), nullable=True)

    rol: Mapped[str] = mapped_column(String(10), default="RESERVA")  # TITULAR, SUPLENTE, RESERVA
    en_transferible: Mapped[bool] = mapped_column(Boolean, default=False)

    # Plantel al que pertenece dentro del club: PRIMERA (todo lo que existía
    # antes de esto) o una categoría de la Academia. Ver engine/academia_engine.py.
    categoria: Mapped[str] = mapped_column(String(10), default="PRIMERA")  # PRIMERA, SUB13, SUB15, SUB18, SUB21
    # Club al que se le está OFRECIENDO este jugador en el intake anual de la
    # Academia (id_equipo sigue None hasta que el club lo acepta). Mismo
    # estilo que id_equipo_precontrato/id_equipo_dueno de más abajo.
    id_equipo_intake: Mapped[int | None] = mapped_column(ForeignKey("equipos.id_equipo"), nullable=True)

    # Instrucción individual dentro de la táctica (independiente del rol):
    # cuánto pesa este jugador en ataque vs. en defensa a la hora de simular
    # el partido — ver `team_power` en engine/match_engine.py.
    duty: Mapped[str] = mapped_column(String(15), default="EQUILIBRADO")  # DEFENSIVO, EQUILIBRADO, OFENSIVO

    # Contrato: null = agente libre. Si a <=180 días de vencer, otro club
    # puede pactar un precontrato (id_equipo_precontrato/salario_precontrato)
    # que se hace efectivo automáticamente el día que el contrato actual termina.
    fecha_fin_contrato: Mapped[date | None] = mapped_column(Date, nullable=True)
    id_equipo_precontrato: Mapped[int | None] = mapped_column(ForeignKey("equipos.id_equipo"), nullable=True)
    salario_precontrato: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Cesión a préstamo: mientras está cedido, id_equipo pasa a ser el club
    # que lo tiene a préstamo (así juega, entrena, etc. como cualquier otro
    # jugador de ese plantel sin tocar el resto del código) e
    # id_equipo_dueno guarda quién es el dueño real, para que vuelva solo
    # al terminar la cesión.
    id_equipo_dueno: Mapped[int | None] = mapped_column(ForeignKey("equipos.id_equipo"), nullable=True)
    fin_cesion: Mapped[date | None] = mapped_column(Date, nullable=True)
    opcion_compra: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Precio de salida garantizado: cualquier club que ofrezca >= este monto
    # se queda con el jugador sin negociación (ver /fichajes/ofertar). Se fija
    # al renovar/precontrato/libre, como condición del jugador/representante.
    clausula_rescision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Reventa (sell-on): el club vendedor pide un % de lo que este jugador
    # genere en su PRÓXIMA venta al aceptar una oferta recibida. Se consume
    # (vuelve a None) apenas dispara una vez — ver _efectivizar_ofertas_pendientes.
    id_club_reventa: Mapped[int | None] = mapped_column(ForeignKey("equipos.id_equipo"), nullable=True)
    porcentaje_reventa: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-100
    # Partidos jugados con el club ACTUAL — se resetea a 0 en cada cambio de
    # id_equipo. Solo existe para poder evaluar add-ons de transferencia
    # (ver AddOnTransferencia y _calcular_efectos_fisicos).
    partidos_club_actual: Mapped[int] = mapped_column(Integer, default=0)

    # Foco de entrenamiento individual (OFENSIVO/DEFENSIVO/PASE/FISICO),
    # además del plan grupal del equipo — progresa solo cada semana, ver
    # _procesar_entrenamiento_individual.
    foco_individual: Mapped[str | None] = mapped_column(String(12), nullable=True)

    equipo: Mapped["Equipo"] = relationship(back_populates="jugadores", foreign_keys=[id_equipo])

    @property
    def overall(self) -> int:
        if self.posicion == "POR":
            valor = self.defensa * 0.6 + self.fisico * 0.2 + self.pase * 0.2
        elif self.posicion == "DEF":
            valor = self.defensa * 0.5 + self.fisico * 0.25 + self.pase * 0.25
        elif self.posicion == "MED":
            valor = self.pase * 0.4 + self.ataque * 0.25 + self.defensa * 0.2 + self.fisico * 0.15
        else:
            valor = self.ataque * 0.55 + self.fisico * 0.25 + self.pase * 0.2
        # Techo absoluto del juego: aunque los 4 atributos individuales
        # puedan llegar a 99, nadie llega a superar 94 de overall (mismo
        # techo que _generar_potencial en engine/data_gen.py) — sin este
        # límite acá, un jugador con varios atributos muy altos a la vez
        # podía terminar con un overall combinado por encima de 94.
        return min(94, round(valor))


class Tactica(Base):
    __tablename__ = "tacticas"

    id_equipo: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"), primary_key=True)
    formacion: Mapped[str] = mapped_column(String(10), default="4-4-2")
    mentalidad: Mapped[str] = mapped_column(String(20), default="BALANCEADA")
    presion: Mapped[str] = mapped_column(String(20), default="MEDIA")
    estilo_pase: Mapped[str] = mapped_column(String(20), default="MIXTO")

    equipo: Mapped["Equipo"] = relationship(back_populates="tactica")


class PlanEntrenamiento(Base):
    __tablename__ = "plan_entrenamiento"

    id_equipo: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"), primary_key=True)
    foco: Mapped[str] = mapped_column(String(20), default="EQUILIBRADO")
    intensidad: Mapped[str] = mapped_column(String(20), default="MEDIA")

    equipo: Mapped["Equipo"] = relationship(back_populates="plan_entrenamiento")


class PersonalTecnico(Base):
    """Asistente del club — una fila por equipo. El entrenamiento y la
    táctica los maneja directamente el propio DT (el usuario), así que acá
    no hay un "entrenador" separado: el asistente es la única voz de staff
    aparte de los ojeadores."""
    __tablename__ = "personal_tecnico"

    id_equipo: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"), primary_key=True)
    nombre_asistente: Mapped[str] = mapped_column(String(100), default="")

    equipo: Mapped["Equipo"] = relationship(back_populates="personal_tecnico")


class Ojeador(Base):
    """Un ojeador del club. Scoutea a un jugador a la vez
    (`id_jugador_asignado`); el progreso acumulado de esa investigación vive
    en `ReporteScouting`, no acá, para no perderlo si se reasigna a otro
    objetivo y después vuelve."""
    __tablename__ = "ojeadores"

    id_ojeador: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_partida: Mapped[int] = mapped_column(ForeignKey("partidas.id_partida"))
    id_equipo: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"))
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    calidad: Mapped[int] = mapped_column(Integer, default=50)
    id_jugador_asignado: Mapped[int | None] = mapped_column(ForeignKey("jugadores.id_jugador"), nullable=True)


class ReporteScouting(Base):
    """Cuánto sabe `id_equipo` sobre `id_jugador` (0-100). El rango de
    overall/potencial que se le muestra al usuario se calcula al vuelo a
    partir de este progreso — ver `_rango_fog` en main.py."""
    __tablename__ = "reportes_scouting"

    id_equipo: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"), primary_key=True)
    id_jugador: Mapped[int] = mapped_column(ForeignKey("jugadores.id_jugador"), primary_key=True)
    id_partida: Mapped[int] = mapped_column(ForeignKey("partidas.id_partida"))
    progreso: Mapped[int] = mapped_column(Integer, default=0)
    fecha_ultimo_reporte: Mapped[date | None] = mapped_column(Date, nullable=True)


class Calendario(Base):
    __tablename__ = "calendario"

    id_fixture: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_partida: Mapped[int] = mapped_column(ForeignKey("partidas.id_partida"))
    # Nulo para partidos de copa (cruzan equipos de distintas ligas).
    id_liga: Mapped[int | None] = mapped_column(ForeignKey("ligas.id_liga"), nullable=True)
    num_jornada: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    id_local: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"))
    id_visitante: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"))
    jugado: Mapped[bool] = mapped_column(Boolean, default=False)
    goles_local: Mapped[int | None] = mapped_column(Integer, nullable=True)
    goles_visitante: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # LIGA | COPA. Un fixture de copa no actualiza la tabla doméstica.
    tipo: Mapped[str] = mapped_column(String(10), default="LIGA")
    # CAMPEONES_UEFA | EUROPEA_UEFA | LIBERTADORES | SUDAMERICANA (None para liga).
    competencia: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Fase de grupos: "GRUPO_A".."GRUPO_H" (el partido 1-6 del grupo usa
    # `num_jornada`, igual que en la liga). Eliminatorias: "OCTAVOS_IDA",
    # "OCTAVOS_VUELTA", "CUARTOS_IDA", "CUARTOS_VUELTA", "SEMIS_IDA",
    # "SEMIS_VUELTA", "FINAL" (la final es a partido único, como en la realidad).
    ronda_copa: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Ganador de penales si la eliminatoria de copa terminó empatada en el
    # global — no modifica goles_local/goles_visitante del partido en sí.
    desempate_id_equipo: Mapped[int | None] = mapped_column(ForeignKey("equipos.id_equipo"), nullable=True)


class EventoPartido(Base):
    __tablename__ = "eventos_partido"

    id_evento: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_fixture: Mapped[int] = mapped_column(ForeignKey("calendario.id_fixture"))
    minuto: Mapped[int] = mapped_column(Integer)
    id_equipo: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"))
    id_jugador: Mapped[int | None] = mapped_column(ForeignKey("jugadores.id_jugador"), nullable=True)
    tipo_evento: Mapped[str] = mapped_column(String(20))  # GOL, TARJETA_AMARILLA, TARJETA_ROJA, LESION
    texto: Mapped[str] = mapped_column(Text, default="")


class OfertaFichaje(Base):
    __tablename__ = "ofertas_fichaje"

    id_oferta: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_jugador: Mapped[int] = mapped_column(ForeignKey("jugadores.id_jugador"))
    id_equipo_comprador: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"))
    id_equipo_vendedor: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"))
    monto_oferta: Mapped[int] = mapped_column(Integer)
    # Salario semanal del contrato nuevo pactado con el jugador (además del
    # precio pactado con el club vendedor). Se aplica recién al efectivizarse.
    salario_pactado: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estado: Mapped[str] = mapped_column(String(20), default="PENDIENTE")  # PENDIENTE, ACEPTADA, RECHAZADA
    efectivizada: Mapped[bool] = mapped_column(Boolean, default=False)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AddOnTransferencia(Base):
    """Pago extra pactado en una transferencia, atado a que el jugador sume
    `partidos_objetivo` partidos jugados con el club comprador — se crea
    junto al OfertaFichaje (ver /fichajes/negociar-contrato) y se cobra solo
    cuando se cumple, procesando cada jornada (ver _calcular_efectos_fisicos
    / _cerrar_jornada_del_dia en main.py)."""
    __tablename__ = "addons_transferencia"

    id_addon: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_jugador: Mapped[int] = mapped_column(ForeignKey("jugadores.id_jugador"))
    id_equipo_beneficiario: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"))  # vendedor original
    partidos_objetivo: Mapped[int] = mapped_column(Integer)
    monto: Mapped[int] = mapped_column(Integer)
    cumplido: Mapped[bool] = mapped_column(Boolean, default=False)


class HistorialTemporada(Base):
    """Foto de un jugador al cerrar cada temporada — permite ver evolución
    de carrera (overall, valor, potencial) en vez de solo el estado actual."""
    __tablename__ = "historial_temporada"

    id_historial: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_partida: Mapped[int] = mapped_column(ForeignKey("partidas.id_partida"))
    # SET NULL (no CASCADE): un jugador retirado se borra de `jugadores`,
    # pero su historial de carrera tiene que sobrevivirlo — por eso además
    # se guarda `nombre_jugador` como copia, para poder mostrarlo igual.
    id_jugador: Mapped[int | None] = mapped_column(ForeignKey("jugadores.id_jugador", ondelete="SET NULL"), nullable=True)
    nombre_jugador: Mapped[str] = mapped_column(String(100), default="")
    temporada: Mapped[int] = mapped_column(Integer)  # año de inicio de la temporada (2027, 2028, ...)
    id_equipo: Mapped[int | None] = mapped_column(ForeignKey("equipos.id_equipo"), nullable=True)
    nombre_equipo: Mapped[str] = mapped_column(String(100), default="")  # copia del nombre, por si el equipo cambia después
    edad: Mapped[int] = mapped_column(Integer)
    overall: Mapped[int] = mapped_column(Integer)
    potencial: Mapped[int] = mapped_column(Integer)
    valor_mercado: Mapped[int] = mapped_column(Integer)
    salario: Mapped[int] = mapped_column(Integer)
    rol: Mapped[str] = mapped_column(String(10), default="RESERVA")


class PaqueteClubes(Base):
    """Lista de nombres de club personalizados, guardada aparte de
    cualquier carrera puntual para poder reusarla al crear otra (igual que
    un dataset editado por la comunidad en FM: separado de los datos
    oficiales, combinado recién al generar la carrera)."""
    __tablename__ = "paquetes_clubes"

    id_paquete: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    # {"ARG1": [["BOC","Xeneize FC"], ...], ...} — cada club puede llevar 2
    # elementos (código, nombre), 3 (+ escudo_url) o 4 (+ nombre_competencia
    # de esa liga, ver crear_partida en seed.py).
    nombres_json: Mapped[str] = mapped_column(Text, nullable=False)
    # {"ARG1": {"BOC": [{"nombre":..., "posicion":..., "posicion_especifica":...,
    #                     "nacionalidad":..., "edad":..., "ataque":..., "defensa":...,
    #                     "pase":..., "fisico":...}, ...]}, ...} — jugadores
    # reales opcionales, anidados por liga y código de club (el código NO es
    # único entre ligas, ej. "BOC" existe en ARG1 y en ALE1). NULL = paquete
    # solo de nombres de club (el formato de siempre, sigue funcionando igual).
    jugadores_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # {"CAMPEONES_UEFA": "...", "EUROPEA_UEFA": "...", "LIBERTADORES": "...",
    # "SUDAMERICANA": "..."} — nombres opcionales para las copas
    # internacionales, mismas claves que engine/copa_engine.py COMPETENCIAS.
    competencias_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
