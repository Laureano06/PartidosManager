import random

TIPOS_LESION = [
    {"nombre": "Sobrecarga Muscular", "min": 1, "max": 2},
    {"nombre": "Esguince de Tobillo", "min": 2, "max": 4},
    {"nombre": "Rotura de Fibras", "min": 4, "max": 8},
    {"nombre": "Ligamento Cruzado", "min": 16, "max": 30},
]


def evaluar_lesion(energia: int) -> dict | None:
    """Devuelve un dict de lesión si ocurre, o None."""
    prob = 0.00012
    if energia < 40:
        prob *= 6
    if random.random() < prob:
        tipo = random.choice(TIPOS_LESION)
        semanas = random.randint(tipo["min"], tipo["max"])
        return {"tipo": tipo["nombre"], "semanas": semanas}
    return None
