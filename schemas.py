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
    presupuesto_fichajes: int
    presupuesto_salarios: int
    puntos: int
    jugados: int
    ganados: int
    empatados: int
    perdidos: int
    goles_favor: int
    goles_contra: int


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


class SolicitarObraIn(BaseModel):
    id_equipo: int
    tipo_instalacion: str


class OfertaIn(BaseModel):
    id_jugador: int
    id_equipo_comprador: int
    monto_oferta: int
    ronda: int = 0


class RespuestaOfertaIn(BaseModel):
    id_oferta: int
    aceptar: bool


class NegociarContratoTraspasoIn(BaseModel):
    id_jugador: int
    id_equipo_comprador: int
    monto_oferta: int
    salario_ofrecido: int
    ronda: int = 0


class SimularJornadaIn(BaseModel):
    id_liga: int
    num_jornada: int


class RenovarContratoIn(BaseModel):
    id_jugador: int
    salario_propuesto: int
    anios: int = 3
    ronda: int = 0


class PrecontratoIn(BaseModel):
    id_jugador: int
    id_equipo_destino: int
    salario_ofrecido: int
    ronda: int = 0


class FicharLibreIn(BaseModel):
    id_jugador: int
    id_equipo: int
    salario_ofrecido: int
    ronda: int = 0


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
