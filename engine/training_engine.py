import random


def aplicar_entrenamiento(jugadores: list, foco: str, intensidad: str) -> None:
    """Modifica in-place los objetos ORM Jugador según el plan de entrenamiento."""
    mult_fatiga = {"BAJA": -10, "MEDIA": 5, "ALTA": 15}.get(intensidad, 5)
    prob_mejora = {"BAJA": 0.05, "MEDIA": 0.08, "ALTA": 0.15}.get(intensidad, 0.08)

    for j in jugadores:
        if foco == "DESCANSO":
            j.energia = min(100, j.energia + 30)
            continue

        j.energia = max(0, min(100, j.energia - mult_fatiga))

        if j.edad < 29 and random.random() < prob_mejora:
            if foco == "OFENSIVO" and j.ataque < j.potencial:
                j.ataque = min(j.potencial, j.ataque + 1)
            elif foco == "DEFENSIVO" and j.defensa < j.potencial:
                j.defensa = min(j.potencial, j.defensa + 1)
            elif foco == "FISICO" and j.fisico < 95:
                j.fisico = min(95, j.fisico + 1)
