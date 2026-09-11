"""
Directiva: evaluación de objetivo de temporada, confianza del club actual,
balance de carrera del DT y rango de ofertas de club. Funciones puras (no
tocan la base) al estilo de academia_engine.py — main.py hace las consultas/commits.
"""
import random

UMBRAL_DESPIDO = 15  # confianza <= esto: despido inmediato, sin importar el contrato
CONFIANZA_INICIAL = 60
BALANCE_INICIAL = 50


def posicion_objetivo(nivel: float, cantidad_clubes: int) -> int:
    """Misma banda de tiers que objetivo_por_nivel (data_gen.py) pero como
    posición numérica evaluable, no un texto para mostrar."""
    if nivel >= 0.8:
        return 3
    if nivel >= 0.55:
        return max(4, round(cantidad_clubes * 0.35))
    if nivel >= 0.3:
        return round(cantidad_clubes * 0.65)
    return max(1, cantidad_clubes - 2)


def objetivo_cumplido(posicion_final: int, nivel: float, cantidad_clubes: int) -> bool:
    return posicion_final <= posicion_objetivo(nivel, cantidad_clubes)


def actualizar_confianza(confianza: int, cumplido: bool) -> int:
    return max(0, min(100, confianza + (20 if cumplido else -25)))


def actualizar_balance(balance: int, cumplido: bool) -> int:
    return max(0, min(100, balance + (12 if cumplido else -10)))


def probabilidad_renovacion_pese_a_incumplir(confianza: int) -> float:
    return confianza / 100 * 0.6


# Nunca 100% seguro ni 100% imposible, mismo criterio que
# engine/player_ai_engine.py (PROB_MIN/PROB_MAX).
PROB_MIN_OBRA = 0.10
PROB_MAX_OBRA = 0.95


def dias_espera_obra(confianza_directiva: int, costo: int, presupuesto_disponible: int) -> int:
    """Estimación de cuánto va a tardar la directiva en resolver un pedido de
    obra (se calcula al PEDIRLA, para fijar fecha_resolucion) — más caro
    relativo al presupuesto y menos confianza = evaluación más lenta."""
    ratio = costo / max(1, presupuesto_disponible)
    dias_base = 5 + round(min(1.5, ratio) * 25) + round((100 - confianza_directiva) * 0.15)
    return max(3, min(45, dias_base + random.randint(-2, 4)))


def evaluar_solicitud_obra(confianza_directiva: int, costo: int, presupuesto_disponible: int) -> dict:
    """Veredicto final de un pedido de obra, evaluado el día que se RESUELVE
    (no el día que se pidió — la confianza/presupuesto del club pueden haber
    cambiado mientras tanto). Más confianza y un pedido barato relativo al
    presupuesto disponible = más probable que se apruebe."""
    ratio = costo / max(1, presupuesto_disponible)
    prob = (confianza_directiva / 100) * (1 - min(0.85, ratio * 0.7))
    prob = max(PROB_MIN_OBRA, min(PROB_MAX_OBRA, prob))

    if random.random() >= prob:
        motivo = (
            "La directiva considera que el costo no se justifica con el presupuesto actual del club."
            if ratio > 0.5 else
            "La directiva prefiere esperar a un mejor momento para aprobar esta inversión."
        )
        return {"estado": "RECHAZADA", "motivo": motivo}
    return {"estado": "APROBADA", "motivo": "La directiva aprobó la inversión solicitada."}


def rango_ofertas(reputacion_actual: int, tipo: str) -> tuple[int, int]:
    """tipo: 'peor' (despido), 'mismo' (fin de contrato sin renovar),
    'mejor' (fin de contrato exitoso). Devuelve (min, max) de reputación a
    buscar — el caller ensancha el rango si no hay 3 clubes disponibles."""
    if tipo == "peor":
        return (0, max(0, reputacion_actual - 10))
    if tipo == "mejor":
        return (min(100, reputacion_actual + 10), 100)
    return (max(0, reputacion_actual - 12), min(100, reputacion_actual + 12))
