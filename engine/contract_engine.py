"""Negociación salarial: renovaciones de contrato, precontratos (jugador a
<=180 días de quedar libre) y fichajes de agentes libres comparten la misma
mecánica — el club ofrece un salario semanal, el jugador lo compara con lo
que "espera" ganar según su valor de mercado y edad.

Igual que en las negociaciones de pase, el jugador (o su representante)
nunca rechaza una primera propuesta sin más: o es inflexible con su pedido
(no está dispuesto a negociar, algo más probable cuanto más veterano/caro
es) o siempre dice cuánto pide, por lejos que haya quedado la oferta.
"""
import random

from formato import money

RONDAS_MAX = 3
PROB_INFLEXIBLE_VETERANO = 0.12
PROB_INFLEXIBLE_NORMAL = 0.04


def salario_esperado(valor_mercado: int, edad: int) -> int:
    factor_edad = 1.0
    if edad >= 30:
        factor_edad = 1.0 + 0.025 * (edad - 29)  # veteranos piden más seguridad económica
    elif edad <= 22:
        factor_edad = 0.85  # promesas aceptan un poco menos a cambio de continuidad
    return max(400, round(valor_mercado * 0.0025 * factor_edad / 100) * 100)


def evaluar_renovacion(salario_propuesto: int, valor_mercado: int, edad: int, ronda: int = 0) -> dict:
    demanda_base = salario_esperado(valor_mercado, edad)
    ablande = max(0.90, 1 - 0.04 * ronda)
    demanda = round(demanda_base * ablande / 100) * 100
    ratio = salario_propuesto / demanda if demanda else 1.0

    if ratio >= 1.0:
        return {"estado": "ACEPTADA", "mensaje": f"El jugador acepta ${money(salario_propuesto)}/semana.", "demanda": demanda}

    if ronda == 0:
        prob_inflexible = PROB_INFLEXIBLE_VETERANO if edad >= 30 else PROB_INFLEXIBLE_NORMAL
        if random.random() < prob_inflexible:
            return {
                "estado": "INFLEXIBLE",
                "mensaje": f"El jugador no negocia: exige ${money(demanda)}/semana o nada.",
                "demanda": demanda,
            }

    if ronda >= RONDAS_MAX:
        return {
            "estado": "RECHAZADA",
            "mensaje": "El jugador corta la negociación: no hubo acuerdo salarial.",
            "demanda": demanda,
        }

    if ratio >= 0.75:
        contraoferta = round((salario_propuesto + demanda) / 2 / 100) * 100
        return {
            "estado": "CONTRAOFERTA",
            "mensaje": f"No le alcanza esa cifra, pide ${money(contraoferta)}/semana.",
            "contraoferta": contraoferta,
            "demanda": demanda,
        }

    return {
        "estado": "CONTRAOFERTA",
        "mensaje": f"Considera la oferta salarial muy baja, pero está dispuesto a negociar por ${money(demanda)}/semana.",
        "contraoferta": demanda,
        "demanda": demanda,
    }
