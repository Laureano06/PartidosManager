"""IA de jugadores: a diferencia de contract_engine.py/transfer_engine.py
(que solo discuten PLATA, y siempre terminan cerrando trato si se ofrece lo
suficiente), esto modela si el jugador está siquiera DISPUESTO a renovar
con su club actual o a sumarse a uno nuevo — antes de que la plata entre en
juego. Mismo estilo que el resto de engine/: funciones puras, reciben
valores, devuelven un dict, nunca tocan la DB.

`reputacion_club`/`reputacion_destino`/`reputacion_actual` son siempre
Equipo.reputacion (ya en escala comparable ENTRE ligas, ver
engine/data_gen.py::reputacion_club) — no hace falta recalcular nada acá.
"""
import random

PROB_MIN = 0.05  # nunca "imposible" del todo
PROB_MAX = 0.97  # nunca 100% seguro tampoco


def _clamp(p: float) -> float:
    return max(PROB_MIN, min(PROB_MAX, p))


def disposicion_renovar(overall: int, edad: int, rol: str, moral: int, reputacion_club: int, relacion_dt: int = 50) -> dict:
    """¿Este jugador está dispuesto a renovar con SU club actual?"""
    probabilidad = 0.75

    brecha_calidad = overall - reputacion_club
    motivo_dominante = None
    if brecha_calidad > 5:
        probabilidad -= min(0.5, brecha_calidad * 0.02)
        motivo_dominante = "brecha"

    if rol == "RESERVA" and edad >= 24:
        probabilidad -= 0.15
        motivo_dominante = motivo_dominante or "protagonismo"
    elif rol == "SUPLENTE" and edad >= 27:
        probabilidad -= 0.10
        motivo_dominante = motivo_dominante or "protagonismo"

    if edad >= 32:
        probabilidad += 0.15
        motivo_dominante = motivo_dominante or "estabilidad"

    probabilidad += (moral - 75) * 0.004
    # Una relación construida con el DT no reemplaza salario ni ambición, pero
    # pesa lo suficiente para destrabar o enfriar una renovación.
    probabilidad += (relacion_dt - 50) * 0.003

    probabilidad = _clamp(probabilidad)
    quiere = random.random() < probabilidad
    motivo = _frase_renovar(quiere, motivo_dominante, moral)
    return {"quiere": quiere, "probabilidad": round(probabilidad, 2), "motivo": motivo}


def disposicion_fichar(overall: int, edad: int, reputacion_actual: int | None, reputacion_destino: int) -> dict:
    """¿Este jugador está abierto a sumarse a OTRO club (el que hace la
    oferta)? reputacion_actual=None: agente libre / sin club, casi siempre
    abierto (no tiene nada que lo ate a un lugar mejor)."""
    if reputacion_actual is None:
        probabilidad = 0.90
        gap = None
    else:
        gap = reputacion_destino - reputacion_actual
        if gap >= 0:
            probabilidad = min(PROB_MAX, 0.75 + gap * 0.01)
        else:
            probabilidad = 0.75 + gap * 0.03  # gap negativo: baja proporcional a la caída

    probabilidad = _clamp(probabilidad)
    quiere = random.random() < probabilidad
    motivo = _frase_fichar(quiere, gap, edad)
    return {"quiere": quiere, "probabilidad": round(probabilidad, 2), "motivo": motivo}


def ajustar_moral(moral_actual: int, jugo: bool, resultado_partido: str | None, rol: str) -> int:
    """resultado_partido: 'GANO' | 'PERDIO' | 'EMPATO' | None (no jugó)."""
    delta = 0
    if jugo:
        delta = {"GANO": 3, "EMPATO": 1, "PERDIO": -2}.get(resultado_partido, 0)
    elif rol == "RESERVA":
        delta = -2
    elif rol == "SUPLENTE":
        delta = -1
    return max(0, min(100, moral_actual + delta))


# ---------- Frases (el "diálogo") ----------

def _frase_renovar(quiere: bool, motivo_dominante: str | None, moral: int) -> str:
    if quiere:
        opciones = [
            "Me siento cómodo acá, con gusto sigo.",
            "Este club me da continuidad, no tengo apuro en irme.",
            "Estoy conforme, renovaría sin problema.",
        ]
    elif motivo_dominante == "brecha":
        opciones = [
            "Siento que ya di todo lo que podía dar acá, busco un desafío más grande.",
            "Creo que mi nivel pide un club de más peso que este.",
        ]
    elif motivo_dominante == "protagonismo":
        opciones = [
            "Necesito jugar más de lo que estoy jugando, si no cambia eso prefiero buscar otro lugar.",
            "Ya me cansé de mirar desde el banco, quiero protagonismo.",
        ]
    else:
        opciones = [
            "No estoy del todo convencido de seguir, lo estoy pensando.",
            "Tengo mis dudas sobre renovar en este momento.",
        ]
    return random.choice(opciones)


def _frase_fichar(quiere: bool, gap: float | None, edad: int) -> str:
    if gap is None:
        opciones = [
            "Estoy libre, escucho cualquier propuesta seria.",
            "Necesito club, si el proyecto me convence firmo ya.",
        ]
    elif quiere:
        opciones = [
            "Es un lindo desafío, me interesa.",
            "Sí, me sumaría con gusto a este proyecto.",
        ]
    elif gap < -15:
        opciones = [
            "La verdad no lo veo, hoy estoy en un club de otro nivel.",
            "No es algo que me mueva el piso ahora mismo.",
        ]
    else:
        opciones = [
            "Lo pensaría, pero no es mi prioridad hoy.",
            "No lo descarto del todo, aunque no me convence del todo.",
        ]
    return random.choice(opciones)


def frase_dialogo(tema: str, *, moral: int, disposicion: dict, overall: int, potencial: int, edad: int) -> str:
    """Frases para el modal 'Hablar con el jugador' (consulta sin comprometer
    una oferta) — mismos datos que ya usan disposicion_renovar/fichar, solo
    que acá se leen sin gastar ninguna ronda de negociación real."""
    if tema == "club":
        if moral >= 80:
            return "Estoy muy bien acá, contento con mi presente."
        if moral >= 60:
            return "Estoy bien, sin quejas grandes por ahora."
        if moral >= 40:
            return "La verdad, no es mi mejor momento en el club."
        return "No la estoy pasando bien acá, necesito un cambio de aire."
    if tema == "continuidad":
        return disposicion["motivo"]
    if tema == "futuro":
        margen = potencial - overall
        if edad <= 21 and margen >= 8:
            return "Todavía tengo mucho margen para crecer, quiero un club que apueste a mi desarrollo."
        if edad >= 32:
            return "A esta altura de mi carrera priorizo estabilidad, no aventuras."
        return "Quiero seguir creciendo y pelear cosas importantes."
    return "..."
