"""
Redes multiclub: participación accionaria entre clubes (Propietario/
Satélite/Minoritario, un único mecanismo continuo de % de tenencia) y redes
de marca (Marca, un tag fijo sin equity real — ver Equipo.red_marca en
models.py). Funciones puras (no tocan la base), mismo estilo que
directiva_engine.py/academia_engine.py — main.py hace las consultas/commits.
"""
import random

# Mapeo curado de clubes ficticios (códigos ya existentes en
# engine/data_gen.py::CLUB_NAMES) a modelos multiclub reales conocidos.
# Solo se siembra en partidas "Base Ficticia" (ver seed.py) — en "Datos
# personalizados" el nombre del club no lleva el código como prefijo
# recuperable, así que no hay forma confiable de aplicar el mapeo.
AFILIACIONES_CURADAS = [
    # City Football Group -> Girona
    {"tipo": "PROPIETARIO", "liga_inversor": "ING1", "codigo_inversor": "MANC",
     "liga_participado": "ESP1", "codigo_participado": "GIR", "porcentaje": 47},
    # Mismo grupo -> Udinese (así elegir el club "Udinese" da SATELITE de un
    # grande, sin forzar la dirección real de la red Pozzo).
    {"tipo": "SATELITE", "liga_inversor": "ING1", "codigo_inversor": "MANC",
     "liga_participado": "ITA1", "codigo_participado": "FRI", "porcentaje": 20},
    # BlueCo (Chelsea) -> Strasbourg
    {"tipo": "SATELITE", "liga_inversor": "ING1", "codigo_inversor": "CHE",
     "liga_participado": "FRA1", "codigo_participado": "ALS", "porcentaje": 20},
    # Tony Bloom (Brighton) -> Alavés
    {"tipo": "MINORITARIO", "liga_inversor": "ING1", "codigo_inversor": "BRI",
     "liga_participado": "ESP1", "codigo_participado": "ALA", "porcentaje": 10},
]

# Redes de marca curadas (no son equity — ver Equipo.red_marca).
GRUPOS_MARCA_CURADOS = [
    # Red Bull: RB Leipzig + RB Bragantino.
    {"grupo_marca": "ROJOTORO", "miembros": [("ALE1", "ROJ"), ("BRA1", "BRG")]},
]

UMBRAL_SATELITE = 15
UMBRAL_PROPIETARIO = 35


def tipo_relacion_por_porcentaje(porcentaje: int) -> str | None:
    """Los 3 modelos comprables son en realidad un único mecanismo continuo
    de % de tenencia — subís de MINORITARIO a SATELITE a PROPIETARIO
    comprando más, bajás vendiendo."""
    if porcentaje <= 0:
        return None
    if porcentaje < UMBRAL_SATELITE:
        return "MINORITARIO"
    if porcentaje < UMBRAL_PROPIETARIO:
        return "SATELITE"
    return "PROPIETARIO"


def valor_club(reputacion: int, presupuesto_fichajes: int, valor_plantel: int) -> int:
    """Valuación de un club (no existía ningún concepto de esto antes en el
    juego). Calibrada contra presupuesto_fichajes (12M-280M en todo el
    juego, ver LIGA_PRESUPUESTO_BASE) para que comprar una participación sea
    afrontable de verdad — no una valuación de "empresa" tipo mundo real
    (ahí un club grande vale miles de millones, pero eso volvería la compra/
    venta injugable). La reputación vive ~60-94 en todo el juego (ver
    LIGA_TECHO_OVR/LIGA_PISO_OVR) — un gigante europeo vale más que un club
    chico con el mismo presupuesto/plantel, no solo proporcionalmente, de
    ahí el factor multiplicativo en vez de aditivo."""
    factor_reputacion = 1 + max(0, reputacion - 60) * 0.025
    base = presupuesto_fichajes * 0.5 + valor_plantel * 0.3
    return round(base * factor_reputacion / 10_000) * 10_000


def _prima_control(porcentaje: int) -> float:
    """Precio por punto porcentual sube al cruzar los umbrales de control —
    comprar hacia la mayoría cuesta desproporcionadamente más que ir
    acumulando una posición chica, como en una adquisición real."""
    if porcentaje < UMBRAL_SATELITE:
        return 1.0
    if porcentaje < UMBRAL_PROPIETARIO:
        return 1.4
    return 2.2


def costo_participacion(valor_club_objetivo: int, porcentaje_actual: int, porcentaje_nuevo: int) -> int:
    """Costo de subir de porcentaje_actual a porcentaje_nuevo, integrando la
    prima de control banda por banda (no lineal)."""
    total, pct, paso = 0.0, porcentaje_actual, 1
    while pct < porcentaje_nuevo:
        siguiente = min(pct + paso, porcentaje_nuevo)
        total += (valor_club_objetivo / 100) * _prima_control(pct) * (siguiente - pct)
        pct = siguiente
    return round(total / 10_000) * 10_000


def ingreso_venta(valor_club_objetivo: int, porcentaje_actual: int, porcentaje_objetivo: int) -> int:
    """Mismo esquema al revés, con 10% de fricción de mercado — vender
    siempre rinde un poco menos de lo que costaría comprar lo mismo."""
    bruto = costo_participacion(valor_club_objetivo, porcentaje_objetivo, porcentaje_actual)
    return round(bruto * 0.90 / 10_000) * 10_000


# Nunca 100% seguro ni 100% imposible, mismo criterio que el resto del juego.
PROB_MIN_PARTICIPACION = 0.10
PROB_MAX_PARTICIPACION = 0.95


def evaluar_directiva_propia(confianza_directiva: int, monto: int, presupuesto_disponible: int, operacion: str) -> dict:
    """Tu propia directiva evalúa la operación — mismo patrón que
    evaluar_solicitud_obra. Vender casi siempre se aprueba (un club rara vez
    bloquea cobrar un activo propio)."""
    if operacion == "VENDER":
        prob = 0.85 + (confianza_directiva / 100) * 0.15
    else:
        ratio = monto / max(1, presupuesto_disponible)
        prob = (confianza_directiva / 100) * (1 - min(0.85, ratio * 0.75))
    prob = max(PROB_MIN_PARTICIPACION, min(PROB_MAX_PARTICIPACION, prob))
    if random.random() >= prob:
        motivo = (
            "La directiva prefiere no comprometer el presupuesto en esta inversión externa por ahora."
            if operacion == "COMPRAR" else
            "La directiva prefiere mantener la participación actual por ahora."
        )
        return {"estado": "RECHAZADA", "motivo": motivo}
    return {"estado": "APROBADA", "motivo": "La directiva autorizó la operación."}


def evaluar_directiva_contraparte(
    reputacion: int, presupuesto_fichajes: int, presupuesto_referencia_liga: int,
    tipo_relacion: str, operacion: str,
) -> dict:
    """La directiva del club CONTRAPARTE (IA) evalúa si acepta ceder o
    recomprar la participación. Como los clubes de la IA no tienen una
    'confianza' propia hacia terceros (ese campo es de Partida, la relación
    del usuario con SU club), la señal sale de orgullo (reputación — un
    club grande resiste más ceder control) y necesidad de caja (presupuesto
    bajo relativo al promedio de su liga = más dispuesto a vender/aceptar)."""
    orgullo = reputacion / 100
    if operacion == "COMPRAR":
        necesidad = max(0.0, min(1.5, 1 - presupuesto_fichajes / max(1, presupuesto_referencia_liga)))
        resistencia_tipo = {"MINORITARIO": 0.05, "SATELITE": 0.25, "PROPIETARIO": 0.55}.get(tipo_relacion, 0.3)
        prob = 0.55 + necesidad * 0.35 - orgullo * resistencia_tipo
    else:  # VENDER: la contraparte recompra tu stake con su propio presupuesto
        capacidad = max(0.0, min(1.0, presupuesto_fichajes / max(1, presupuesto_referencia_liga)))
        prob = 0.20 + capacidad * 0.5 + orgullo * 0.3
    prob = max(PROB_MIN_PARTICIPACION, min(PROB_MAX_PARTICIPACION, prob))
    if random.random() >= prob:
        motivo = (
            "El club objetivo rechaza ceder esa participación por ahora." if operacion == "COMPRAR" else
            "El club objetivo no está en condiciones de recomprar esa participación por ahora."
        )
        return {"estado": "RECHAZADA", "motivo": motivo}
    return {"estado": "ACEPTADA", "motivo": "El club objetivo aceptó la operación."}


def dias_espera_directiva_propia(confianza_directiva: int, monto: int, presupuesto_disponible: int) -> int:
    ratio = monto / max(1, presupuesto_disponible)
    dias_base = 4 + round(min(1.5, ratio) * 20) + round((100 - confianza_directiva) * 0.1)
    return max(3, min(30, dias_base + random.randint(-2, 3)))


def dias_espera_directiva_contraparte(porcentaje: int) -> int:
    """Ceder o recomprar control se delibera más cuanto mayor el %."""
    dias_base = 5 + round(porcentaje * 0.4)
    return max(4, min(40, dias_base + random.randint(-3, 5)))


# Techos calcados a los que tenía el viejo sistema de "nivel 20" — cambia de
# dónde sale el bono, no el rango de balance del juego.
_TECHO_BONO_CENTRO = 0.2
_PISO_FACTOR_MEDICO = 0.4
_TECHO_BONO_ANALITICA = 8
_TECHO_BONO_INSTALACIONES_JUVENILES = 0.3
_TECHO_BONO_CAPTACION_JUVENIL = 5

PESO_ROL_PARTICIPADO = {"PROPIETARIO": 1.0, "SATELITE": 0.65, "MINORITARIO": 0.30, "MARCA": 0.55}
PESO_ROL_INVERSOR = {"PROPIETARIO": 0.5, "SATELITE": 0.35, "MINORITARIO": 0.15, "MARCA": 0.55}


def fuerza_relacion(tipo_relacion: str | None, rol: str | None, reputacion_contraparte: int) -> float:
    """Qué tan fuerte es un vínculo multiclub (0.0-1.0) — más fuerte cuanto
    mejor la contraparte y cuanto más 'heredás' de ella (rol=PARTICIPADO,
    alguien más grande te controla, heredás más que si sos vos el que
    controla a alguien más chico, rol=INVERSOR)."""
    if not tipo_relacion:
        return 0.0
    tabla = PESO_ROL_PARTICIPADO if rol != "INVERSOR" else PESO_ROL_INVERSOR
    peso = tabla.get(tipo_relacion, 0.0)
    # 60->0.0, 94->1.0, mismo rango de reputacion_club en data_gen.py.
    escala = max(0.0, min(1.0, (reputacion_contraparte - 60) / 34))
    return peso * escala


def bono_red(tipo_relacion: str | None, rol: str | None, reputacion_contraparte: int) -> dict:
    """Reemplaza el bono que antes salía de nivel_* — ahora sale de tu
    posición en la red multiclub. Sin red, sin bono (ser independiente es
    la norma, no una carencia)."""
    fuerza = fuerza_relacion(tipo_relacion, rol, reputacion_contraparte)
    return {
        "bono_centro": round(min(_TECHO_BONO_CENTRO, fuerza * _TECHO_BONO_CENTRO), 4),
        "factor_medico": max(_PISO_FACTOR_MEDICO, round(1 - fuerza * (1 - _PISO_FACTOR_MEDICO), 4)),
        "bono_analitica": round(fuerza * _TECHO_BONO_ANALITICA),
        "bono_instalaciones_juveniles": round(min(_TECHO_BONO_INSTALACIONES_JUVENILES, fuerza * _TECHO_BONO_INSTALACIONES_JUVENILES), 4),
        "bono_captacion_juvenil": round(fuerza * _TECHO_BONO_CAPTACION_JUVENIL),
    }
