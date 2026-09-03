from datetime import date

from pydantic import BaseModel, ConfigDict


class JugadorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_jugador: int
    id_equipo: int | None
    nombre: str
    posicion: str
    posicion_especifica: str | None = None
    nacionalidad: str
    edad: int
    ataque: int
    defensa: int
    pase: int
    fisico: int
    finalizacion: int
    regate: int
    primer_toque: int
    centros: int
    cabeceo: int
    marcaje: int
    entradas: int
    tiros_lejanos: int
    agresividad: int
    valentia: int
    decisiones: int
    concentracion: int
    anticipacion: int
    compostura: int
    vision: int
    liderazgo: int
    ritmo: int
    aceleracion: int
    resistencia: int
    fuerza: int
    agilidad: int
    porteria: int
    energia: int
    moral: int
    valor_mercado: int
    salario: int
    lesionado: bool
    semanas_lesion: int
    tipo_lesion: str | None
    rol: str
    duty: str
    overall: int
    potencial: int
    categoria: str
    fecha_fin_contrato: date | None
    en_transferible: bool
    id_equipo_dueno: int | None
    fin_cesion: date | None
    opcion_compra: int | None
    clausula_rescision: int | None = None
    foco_individual: str | None = None


class LigaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_liga: int
    codigo: str
    pais: str
    nombre: str


class EquipoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_equipo: int
    id_liga: int
    nombre: str
    color: str
    escudo_url: str | None = None
    es_usuario: bool
    reputacion: int
    presupuesto_fichajes: int
    presupuesto_salarios: int
    puntos: int
    jugados: int
    ganados: int
    empatados: int
    perdidos: int
    goles_favor: int
    goles_contra: int
    id_capitan: int | None = None


class CapitanIn(BaseModel):
    id_jugador: int | None = None


class ClubJugadorIn(BaseModel):
    nombre: str
    posicion: str  # POR|DEF|MED|DEL
    nacionalidad: str = "Argentina"
    numero: int | None = None


class CargarPlantelIn(BaseModel):
    nombre_club: str
    jugadores: list[ClubJugadorIn]


class TacticaIn(BaseModel):
    id_equipo: int
    formacion: str
    mentalidad: str
    presion: str
    estilo_pase: str = "MIXTO"


class EntrenamientoIn(BaseModel):
    id_equipo: int
    foco: str
    intensidad: str


class EntrenamientoIndividualIn(BaseModel):
    id_jugador: int
    foco: str | None = None


class OfertaParticipacionIn(BaseModel):
    id_equipo_iniciador: int
    id_equipo_contraparte: int
    operacion: str   # COMPRAR | VENDER
    porcentaje: int


class MoverJugadorIn(BaseModel):
    id_jugador: int
    id_equipo_destino: int
    operacion: str  # PRESTAMO | TRANSFERENCIA
    duracion_meses: int | None = None  # requerido si operacion == PRESTAMO
    opcion_compra: int | None = None


class InfluenciaIn(BaseModel):
    id_afiliacion: int
    habilitada: bool


class OfertaIn(BaseModel):
    id_jugador: int
    id_equipo_comprador: int
    monto_oferta: int
    ronda: int = 0


class RespuestaOfertaIn(BaseModel):
    id_oferta: int
    aceptar: bool
    # Solo tiene efecto si aceptar=True: el vendedor pide quedarse con este %
    # de lo que el jugador genere en su PRÓXIMA venta (se consume al disparar
    # una vez — ver _efectivizar_ofertas_pendientes en main.py).
    porcentaje_reventa_solicitado: int | None = None


class AddOnIn(BaseModel):
    partidos: int
    monto: int


class NegociarContratoTraspasoIn(BaseModel):
    id_jugador: int
    id_equipo_comprador: int
    monto_oferta: int
    salario_ofrecido: int
    ronda: int = 0
    addons: list[AddOnIn] = []


class SimularJornadaIn(BaseModel):
    id_liga: int
    num_jornada: int


class RenovarContratoIn(BaseModel):
    id_jugador: int
    salario_propuesto: int
    anios: int = 3
    ronda: int = 0
    clausula_rescision: int | None = None


class PrecontratoIn(BaseModel):
    id_jugador: int
    id_equipo_destino: int
    salario_ofrecido: int
    ronda: int = 0
    clausula_rescision: int | None = None


class FicharLibreIn(BaseModel):
    id_jugador: int
    id_equipo: int
    salario_ofrecido: int
    ronda: int = 0
    clausula_rescision: int | None = None


class TransferibleIn(BaseModel):
    en_transferible: bool


class OfrecerJugadorIn(BaseModel):
    id_jugador: int
    id_equipos: list[int] | None = None  # None/vacío = ofrecer a todos los rivales


class CederJugadorIn(BaseModel):
    id_jugador: int
    duracion_meses: int  # 6 o 12
    opcion_compra: int | None = None  # monto negociado para comprarlo al terminar la cesión (opcional)
    id_equipos: list[int] | None = None  # None/vacío = ofrecer a todos los rivales


class CategoriaJugadorIn(BaseModel):
    categoria: str  # PRIMERA | SUB13 | SUB15 | SUB18 | SUB21


class IntakeDecidirIn(BaseModel):
    aceptar: bool


class ReclutarJuvenilIn(BaseModel):
    id_equipo_destino: int


class ElegirDestinoDTIn(BaseModel):
    opcion: str  # "renovar" | "id_equipo:<N>"
