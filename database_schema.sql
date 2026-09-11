-- =====================================================================
-- PARTIDOS MANAGER — esquema real de la base (Postgres / Neon)
-- Generado a partir de models.py. Esto es lo que la app crea sola al
-- arrancar (Base.metadata.create_all en main.py) — este archivo es solo
-- documentación/referencia para quien necesite entender la estructura
-- SIN correr la app Python (por ejemplo, para incorporar datos reales).
--
-- TODO EN ESTA BASE ESTÁ FICTICIO A PROPÓSITO (nombres de club, de
-- jugador, de liga) — es el mismo criterio que usa Football Manager: el
-- juego nunca trae nombres reales con licencia, y es un tercero quien los
-- incorpora en SU PROPIA copia de la base, aparte del código fuente.
--
-- Tablas que un tercero SÍ tiene sentido que edite para cargar datos
-- reales: `ligas`, `equipos` (nombre/escudo_url), `jugadores` — o, mejor,
-- el camino ya soportado por la app sin tocar SQL directamente: subir un
-- CSV de clubes/jugadores/competencias desde "Datos personalizados" al
-- crear la carrera, que arma un `paquetes_clubes` (ver el comentario en
-- esa tabla, al final).
--
-- Tablas que NO conviene tocar a mano: son estado de partida que la app
-- genera/mantiene sola (`calendario`, `ofertas_fichaje`, `mensajes`,
-- `historial_temporada`, `ciclo_temporada`, `ofertas_club_dt`,
-- `eventos_partido`, `reportes_scouting`, `ojeadores`, `tacticas`,
-- `plan_entrenamiento`, `personal_tecnico`).
-- =====================================================================


-- ---------- CARRERA ----------

-- Una carrera/guardado independiente: su propio DT, su propio mundo de
-- ligas/equipos/jugadores/calendario (TODO lo demás se filtra por
-- id_partida) y su propia fecha actual.
CREATE TABLE partidas (
    id_partida SERIAL PRIMARY KEY,
    nombre_dt VARCHAR(100) NOT NULL,
    dataset VARCHAR(20) NOT NULL DEFAULT 'ficticia',           -- 'ficticia' | 'personalizada'
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actual DATE NOT NULL,

    -- Contrato del DT con la directiva del club actual.
    objetivo_temporada VARCHAR(255) NOT NULL DEFAULT '',
    contrato_dt_anios INTEGER NOT NULL DEFAULT 1,
    contrato_dt_fecha_fin DATE,

    -- Sistema de Directiva: paciencia del club actual (se resetea a 60 al
    -- cambiar de club), trayectoria de toda la carrera del DT (nunca se
    -- resetea), y el estado de una decisión pendiente (despido/fin de
    -- contrato/renuncia) que bloquea el juego hasta resolverse.
    confianza_directiva INTEGER NOT NULL DEFAULT 60,
    balance_dt INTEGER NOT NULL DEFAULT 50,
    estado_dt VARCHAR(30) NOT NULL DEFAULT 'NORMAL',
        -- 'NORMAL' | 'DESPEDIDO' | 'CONTRATO_FIN_EXITO'
        -- | 'CONTRATO_FIN_RENOVACION_OFRECIDA' | 'CONTRATO_FIN_SIN_RENOVACION'
        -- | 'RENUNCIO'

    -- Nombres personalizados de las copas internacionales para ESTA
    -- partida (editor de datos reales), fijados al crearla. NULL o clave
    -- ausente = nombre ficticio por defecto (ver copa_engine.py).
    competencias_json TEXT   -- {"CAMPEONES_UEFA": "...", "EUROPEA_UEFA": "...", "LIBERTADORES": "...", "SUDAMERICANA": "..."}
);

-- Lista de nombres/jugadores/competencias de club personalizados, reusable
-- entre carreras — el camino YA SOPORTADO por la app para datos custom sin
-- tocar SQL directamente (pantalla "Datos personalizados" al crear
-- carrera, con subida de CSV de clubes y de jugadores reales).
CREATE TABLE paquetes_clubes (
    id_paquete SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    -- Cada club: 2 elementos (código, nombre), 3 (+ escudo_url) o 4
    -- (+ nombre de la liga, reemplaza ligas.nombre para toda esa liga).
    nombres_json TEXT NOT NULL,       -- {"ARG1": [["BOC","Boca Juniors","https://...","Liga Profesional Argentina"], ...], ...}
    -- Jugadores reales opcionales, anidados por liga y código de club (el
    -- código NO es único entre ligas). NULL = paquete solo de nombres de club.
    jugadores_json TEXT,              -- {"ARG1": {"BOC": [{"nombre":..., "posicion":..., "ataque":..., ...}, ...]}, ...}
    -- Nombres opcionales de copas internacionales, mismas claves que
    -- partidas.competencias_json.
    competencias_json TEXT,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ---------- LIGAS Y CLUBES ----------

CREATE TABLE ligas (
    id_liga SERIAL PRIMARY KEY,
    id_partida INTEGER NOT NULL REFERENCES partidas(id_partida),
    codigo VARCHAR(10) NOT NULL,          -- ARG1, BRA1, ESP1, ING1, ITA1, FRA1, ALE1, URU1, CHI1 (único POR partida)
    pais VARCHAR(60) NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    confederacion VARCHAR(10) NOT NULL DEFAULT 'UEFA',   -- 'UEFA' | 'CONMEBOL'
    modo VARCHAR(10) NOT NULL DEFAULT 'COMPLETA'         -- 'COMPLETA' (fixture propio) | 'VISTA' (solo clubes/jugadores)
);

-- Reloj de temporada de UNA confederación dentro de una partida — UEFA y
-- CONMEBOL corren temporadas independientes (fechas reales de inicio
-- distintas) aunque comparten el mismo contador de día (partidas.fecha_actual).
CREATE TABLE ciclo_temporada (
    id_partida INTEGER NOT NULL REFERENCES partidas(id_partida),
    confederacion VARCHAR(10) NOT NULL,
    temporada INTEGER NOT NULL,
    fecha_inicio DATE NOT NULL,
    PRIMARY KEY (id_partida, confederacion)
);

CREATE TABLE equipos (
    id_equipo SERIAL PRIMARY KEY,
    id_partida INTEGER NOT NULL REFERENCES partidas(id_partida),
    id_liga INTEGER NOT NULL REFERENCES ligas(id_liga),
    nombre VARCHAR(100) NOT NULL,
    color VARCHAR(10) NOT NULL DEFAULT '#173C2E',
    -- URL de escudo provista por un tercero (su propio hosting) al crear la
    -- partida con datos personalizados — el juego solo la muestra con
    -- <img>, nunca la descarga ni la aloja. NULL = sin escudo.
    escudo_url VARCHAR(500),
    es_usuario BOOLEAN NOT NULL DEFAULT FALSE,
    -- Reputación en escala COMPARABLE ENTRE LIGAS (no 0-100 parejo: está
    -- anclada al techo/piso real de cada liga, así que ligas europeas
    -- pesan más que ligas sudamericanas del mismo "tamaño relativo" dentro
    -- de su propia liga — ver reputacion_club() en engine/data_gen.py).
    reputacion INTEGER NOT NULL DEFAULT 50,

    presupuesto_fichajes INTEGER NOT NULL DEFAULT 800000,
    presupuesto_salarios INTEGER NOT NULL DEFAULT 200000,

    -- Estadísticas de la liga en curso (se resetean a 0 en cada fin de temporada).
    puntos INTEGER NOT NULL DEFAULT 0,
    jugados INTEGER NOT NULL DEFAULT 0,
    ganados INTEGER NOT NULL DEFAULT 0,
    empatados INTEGER NOT NULL DEFAULT 0,
    perdidos INTEGER NOT NULL DEFAULT 0,
    goles_favor INTEGER NOT NULL DEFAULT 0,
    goles_contra INTEGER NOT NULL DEFAULT 0
);

-- Una de las 3 ofertas de club vigentes mientras partidas.estado_dt no es
-- 'NORMAL' (despido, fin de contrato sin renovar, o renuncia).
CREATE TABLE ofertas_club_dt (
    id_oferta SERIAL PRIMARY KEY,
    id_partida INTEGER NOT NULL REFERENCES partidas(id_partida),
    id_equipo INTEGER NOT NULL REFERENCES equipos(id_equipo)
);


-- ---------- JUGADORES ----------

CREATE TABLE jugadores (
    id_jugador SERIAL PRIMARY KEY,
    id_partida INTEGER NOT NULL REFERENCES partidas(id_partida),
    id_equipo INTEGER REFERENCES equipos(id_equipo),   -- NULL = agente libre / prospecto sin club

    nombre VARCHAR(100) NOT NULL,
    posicion VARCHAR(10) NOT NULL DEFAULT 'MED',        -- 'POR' | 'DEF' | 'MED' | 'DEL'
    -- Posición específica dentro de la amplia — solo para tácticas/formación.
    posicion_especifica VARCHAR(5),                     -- DFC/DFI/DFD, MCD/MC/MCO/MI/MD, EI/ED/DC/MP
    nacionalidad VARCHAR(40) NOT NULL DEFAULT 'Argentina',
    edad INTEGER NOT NULL DEFAULT 20,

    ataque INTEGER NOT NULL DEFAULT 50,
    defensa INTEGER NOT NULL DEFAULT 50,
    pase INTEGER NOT NULL DEFAULT 50,
    fisico INTEGER NOT NULL DEFAULT 50,
    potencial INTEGER NOT NULL DEFAULT 65,
    -- NOTA: "overall" NO es una columna — se calcula al vuelo a partir de
    -- ataque/defensa/pase/fisico según la posición (ver Jugador.overall en
    -- models.py). Un tercero que cargue jugadores reales debe completar
    -- ataque/defensa/pase/fisico con valores coherentes, no un "overall" directo.

    energia INTEGER NOT NULL DEFAULT 100,
    moral INTEGER NOT NULL DEFAULT 75,

    valor_mercado INTEGER NOT NULL DEFAULT 50000,
    salario INTEGER NOT NULL DEFAULT 2000,

    lesionado BOOLEAN NOT NULL DEFAULT FALSE,
    semanas_lesion INTEGER NOT NULL DEFAULT 0,
    tipo_lesion VARCHAR(50),

    rol VARCHAR(10) NOT NULL DEFAULT 'RESERVA',         -- 'TITULAR' | 'SUPLENTE' | 'RESERVA' (solo plantel de Primera)
    en_transferible BOOLEAN NOT NULL DEFAULT FALSE,

    -- Academia: a qué plantel pertenece dentro del club.
    categoria VARCHAR(10) NOT NULL DEFAULT 'PRIMERA',   -- 'PRIMERA' | 'SUB13' | 'SUB15' | 'SUB18' | 'SUB21'
    -- Club al que se le está OFRECIENDO este jugador en el intake anual de
    -- la Academia (id_equipo sigue NULL hasta que el club lo acepta).
    id_equipo_intake INTEGER REFERENCES equipos(id_equipo),

    -- Instrucción individual dentro de la táctica (independiente del rol).
    duty VARCHAR(15) NOT NULL DEFAULT 'EQUILIBRADO',    -- 'DEFENSIVO' | 'EQUILIBRADO' | 'OFENSIVO'

    -- Contrato: fecha_fin_contrato NULL = agente libre (o menor de 15 años
    -- sin contrato todavía, en categorías de Academia). Si a <=180 días de
    -- vencer, otro club puede pactar un precontrato que se hace efectivo
    -- solo cuando el contrato actual termina.
    fecha_fin_contrato DATE,
    id_equipo_precontrato INTEGER REFERENCES equipos(id_equipo),
    salario_precontrato INTEGER,

    -- Cesión a préstamo: mientras está cedido, id_equipo pasa a ser el
    -- club que lo tiene a préstamo e id_equipo_dueno guarda al dueño real.
    id_equipo_dueno INTEGER REFERENCES equipos(id_equipo),
    fin_cesion DATE,
    opcion_compra INTEGER
);


-- ---------- STAFF Y TÁCTICA (una fila por equipo) ----------

CREATE TABLE tacticas (
    id_equipo INTEGER PRIMARY KEY REFERENCES equipos(id_equipo),
    formacion VARCHAR(10) NOT NULL DEFAULT '4-4-2',
    mentalidad VARCHAR(20) NOT NULL DEFAULT 'BALANCEADA',
    presion VARCHAR(20) NOT NULL DEFAULT 'MEDIA',
    estilo_pase VARCHAR(20) NOT NULL DEFAULT 'MIXTO'
);

CREATE TABLE plan_entrenamiento (
    id_equipo INTEGER PRIMARY KEY REFERENCES equipos(id_equipo),
    foco VARCHAR(20) NOT NULL DEFAULT 'EQUILIBRADO',
    intensidad VARCHAR(20) NOT NULL DEFAULT 'MEDIA'
);

-- Asistente del club. El entrenamiento/táctica los maneja el propio DT
-- (usuario), así que no hay "entrenador" separado.
CREATE TABLE personal_tecnico (
    id_equipo INTEGER PRIMARY KEY REFERENCES equipos(id_equipo),
    nombre_asistente VARCHAR(100) NOT NULL DEFAULT ''
);

-- Ojeador del club — scoutea un jugador a la vez.
CREATE TABLE ojeadores (
    id_ojeador SERIAL PRIMARY KEY,
    id_partida INTEGER NOT NULL REFERENCES partidas(id_partida),
    id_equipo INTEGER NOT NULL REFERENCES equipos(id_equipo),
    nombre VARCHAR(100) NOT NULL,
    calidad INTEGER NOT NULL DEFAULT 50,
    id_jugador_asignado INTEGER REFERENCES jugadores(id_jugador)
);

-- Cuánto sabe id_equipo sobre id_jugador (0-100) — el rango de
-- overall/potencial mostrado al usuario se calcula a partir de esto
-- (fog-of-war de scouting).
CREATE TABLE reportes_scouting (
    id_equipo INTEGER NOT NULL REFERENCES equipos(id_equipo),
    id_jugador INTEGER NOT NULL REFERENCES jugadores(id_jugador),
    id_partida INTEGER NOT NULL REFERENCES partidas(id_partida),
    progreso INTEGER NOT NULL DEFAULT 0,
    fecha_ultimo_reporte DATE,
    PRIMARY KEY (id_equipo, id_jugador)
);


-- ---------- CALENDARIO Y PARTIDOS ----------

CREATE TABLE calendario (
    id_fixture SERIAL PRIMARY KEY,
    id_partida INTEGER NOT NULL REFERENCES partidas(id_partida),
    id_liga INTEGER REFERENCES ligas(id_liga),   -- NULL en partidos de copa (cruzan ligas)
    num_jornada INTEGER NOT NULL,
    fecha DATE NOT NULL,
    id_local INTEGER NOT NULL REFERENCES equipos(id_equipo),
    id_visitante INTEGER NOT NULL REFERENCES equipos(id_equipo),
    jugado BOOLEAN NOT NULL DEFAULT FALSE,
    goles_local INTEGER,
    goles_visitante INTEGER,

    tipo VARCHAR(10) NOT NULL DEFAULT 'LIGA',          -- 'LIGA' | 'COPA'
    competencia VARCHAR(20),                            -- 'CAMPEONES_UEFA' | 'EUROPEA_UEFA' | 'LIBERTADORES' | 'SUDAMERICANA'
    -- Fase de grupos: 'GRUPO_A'..'GRUPO_H' (usa num_jornada para el 1-6 del
    -- grupo). Eliminatorias: 'OCTAVOS_IDA'|'OCTAVOS_VUELTA'|'CUARTOS_IDA'|
    -- 'CUARTOS_VUELTA'|'SEMIS_IDA'|'SEMIS_VUELTA'|'FINAL' (final a partido único).
    ronda_copa VARCHAR(20),
    desempate_id_equipo INTEGER REFERENCES equipos(id_equipo)   -- ganador de penales si el global quedó empatado
);

CREATE TABLE eventos_partido (
    id_evento SERIAL PRIMARY KEY,
    id_fixture INTEGER NOT NULL REFERENCES calendario(id_fixture),
    minuto INTEGER NOT NULL,
    id_equipo INTEGER NOT NULL REFERENCES equipos(id_equipo),
    id_jugador INTEGER REFERENCES jugadores(id_jugador),
    tipo_evento VARCHAR(20) NOT NULL,   -- 'GOL' | 'TARJETA_AMARILLA' | 'TARJETA_ROJA' | 'LESION'
    texto TEXT NOT NULL DEFAULT ''
);


-- ---------- MERCADO DE PASES Y MENSAJERÍA ----------

CREATE TABLE ofertas_fichaje (
    id_oferta SERIAL PRIMARY KEY,
    id_jugador INTEGER NOT NULL REFERENCES jugadores(id_jugador),
    id_equipo_comprador INTEGER NOT NULL REFERENCES equipos(id_equipo),
    id_equipo_vendedor INTEGER NOT NULL REFERENCES equipos(id_equipo),
    monto_oferta INTEGER NOT NULL,
    salario_pactado INTEGER,             -- salario semanal del contrato nuevo, se aplica al efectivizarse
    estado VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',   -- 'PENDIENTE' | 'ACEPTADA' | 'RECHAZADA'
    efectivizada BOOLEAN NOT NULL DEFAULT FALSE,
    creado TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE mensajes (
    id_mensaje SERIAL PRIMARY KEY,
    id_equipo_destino INTEGER NOT NULL REFERENCES equipos(id_equipo),
    remitente VARCHAR(100) NOT NULL,
    asunto VARCHAR(200) NOT NULL,
    contenido TEXT NOT NULL DEFAULT '',
    fecha DATE NOT NULL,
    leido BOOLEAN NOT NULL DEFAULT FALSE,
    tipo VARCHAR(20) NOT NULL DEFAULT 'SISTEMA',   -- 'SISTEMA' | 'MERCADO' | 'PARTIDO' | 'TACTICA' | 'ENTRENAMIENTO'
    id_oferta INTEGER REFERENCES ofertas_fichaje(id_oferta)
);


-- ---------- HISTORIAL ----------

-- Foto de un jugador al cerrar cada temporada — evolución de carrera
-- (overall, valor, potencial) en vez de solo el estado actual.
CREATE TABLE historial_temporada (
    id_historial SERIAL PRIMARY KEY,
    id_partida INTEGER NOT NULL REFERENCES partidas(id_partida),
    -- SET NULL (no CASCADE): un jugador retirado se borra de `jugadores`,
    -- pero su historial tiene que sobrevivirlo — por eso también se guarda
    -- nombre_jugador como copia.
    id_jugador INTEGER REFERENCES jugadores(id_jugador) ON DELETE SET NULL,
    nombre_jugador VARCHAR(100) NOT NULL DEFAULT '',
    temporada INTEGER NOT NULL,          -- año de inicio de temporada (2027, 2028, ...)
    id_equipo INTEGER REFERENCES equipos(id_equipo),
    nombre_equipo VARCHAR(100) NOT NULL DEFAULT '',   -- copia del nombre, por si el equipo cambia después
    edad INTEGER NOT NULL,
    overall INTEGER NOT NULL,
    potencial INTEGER NOT NULL,
    valor_mercado INTEGER NOT NULL,
    salario INTEGER NOT NULL,
    rol VARCHAR(10) NOT NULL DEFAULT 'RESERVA'
);
