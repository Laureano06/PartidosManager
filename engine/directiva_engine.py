"""
Directiva: evaluación de objetivo de temporada, confianza del club actual,
balance de carrera del DT y rango de ofertas de club. Funciones puras (no
tocan la base) al estilo de academia_engine.py — main.py hace las consultas/commits.
"""

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


def rango_ofertas(reputacion_actual: int, tipo: str) -> tuple[int, int]:
    """tipo: 'peor' (despido), 'mismo' (fin de contrato sin renovar),
    'mejor' (fin de contrato exitoso). Devuelve (min, max) de reputación a
    buscar — el caller ensancha el rango si no hay 3 clubes disponibles."""
    if tipo == "peor":
        return (0, max(0, reputacion_actual - 10))
    if tipo == "mejor":
        return (min(100, reputacion_actual + 10), 100)
    return (max(0, reputacion_actual - 12), min(100, reputacion_actual + 12))
