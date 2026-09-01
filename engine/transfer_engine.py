"""Evalúa una oferta de fichaje contra el valor de mercado del jugador.

`es_clave` (titular del equipo vendedor) encarece la demanda base 50%.
`ronda` modela una negociación real: en cada vuelta de ida y vuelta el club
afloja un poco su pedido (hasta un piso), pero si después de varias rondas
no hay acuerdo, corta las negociaciones.

El club nunca rechaza una primera oferta sin más — o dice directamente que
el jugador es intransferible (no se sienta a negociar bajo ningún precio,
algo más probable cuanto más importante es para el plantel), o siempre
abre una contraoferta con su pedido real, por lejos que haya quedado la
propuesta. Recién si se agotan las rondas sin acuerdo se corta.
"""
import random

from formato import money

RONDAS_MAX = 3
PROB_INTRANSFERIBLE_CLAVE = 0.15
PROB_INTRANSFERIBLE_NORMAL = 0.03


def evaluar_oferta(monto_oferta: int, valor_mercado: int, es_clave: bool = False, ronda: int = 0) -> dict:
    demanda_base = round(valor_mercado * (1.5 if es_clave else 1.0))
    ablande = max(0.90, 1 - 0.035 * ronda)
    demanda = round(demanda_base * ablande / 10_000) * 10_000
    ratio = monto_oferta / demanda if demanda else 1.0

    if ratio >= 1.0:
        return {"estado": "ACEPTADA", "mensaje": f"El club acepta la oferta de ${money(monto_oferta)}.", "demanda": demanda}

    if ronda == 0:
        prob_intransferible = PROB_INTRANSFERIBLE_CLAVE if es_clave else PROB_INTRANSFERIBLE_NORMAL
        if random.random() < prob_intransferible:
            return {
                "estado": "INTRANSFERIBLE",
                "mensaje": "El club no lo pone en venta bajo ningún concepto — no hay negociación posible por este jugador.",
                "demanda": demanda,
            }

    if ronda >= RONDAS_MAX:
        return {
            "estado": "RECHAZADA",
            "mensaje": "El club corta las negociaciones: no hubo acuerdo tras varias rondas.",
            "demanda": demanda,
        }

    if ratio >= 0.80:
        contraoferta = round((monto_oferta + demanda) / 2 / 10_000) * 10_000
        return {
            "estado": "CONTRAOFERTA",
            "mensaje": f"El club rechaza esa cifra pero pide ${money(contraoferta)}.",
            "contraoferta": contraoferta,
            "demanda": demanda,
        }

    return {
        "estado": "CONTRAOFERTA",
        "mensaje": f"El club considera la oferta muy baja, pero está dispuesto a negociar por ${money(demanda)}.",
        "contraoferta": demanda,
        "demanda": demanda,
    }
