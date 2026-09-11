import random

from engine.data_gen import recalcular_derivados

# Grupo de atributos base que mejora cada foco — igual que antes (OFENSIVO/
# DEFENSIVO/FISICO), más PASE, que antes no existía (el entrenamiento nunca
# mejoraba `pase`). Cada atributo del grupo tiene su propia chance de subir
# +1 (no todos a la vez), y al final se recalculan los 4 derivados de
# siempre desde sus componentes.
_GRUPOS_FOCO = {
    "OFENSIVO": ["finalizacion", "regate", "tiros_lejanos", "centros"],
    "DEFENSIVO": ["marcaje", "entradas", "cabeceo", "valentia"],
    "PASE": ["pase", "vision", "primer_toque", "decisiones"],
    "FISICO": ["ritmo", "aceleracion", "resistencia", "fuerza", "agilidad"],
}


def grupo_atributos(foco: str) -> list[str] | None:
    """Atributos que entrena cada foco — expuesto para el entrenamiento
    individual (main.py), que reutiliza la misma taxonomía de grupos."""
    return _GRUPOS_FOCO.get(foco)


def recalcular_derivados_jugador(j) -> None:
    """Recompone ataque/defensa/pase/fisico de un Jugador ORM desde sus
    componentes — compartido entre el entrenamiento grupal y el individual
    para no duplicar la lista de 19 atributos en los dos lados."""
    derivados = recalcular_derivados({
        "finalizacion": j.finalizacion, "regate": j.regate, "tiros_lejanos": j.tiros_lejanos,
        "centros": j.centros, "marcaje": j.marcaje, "entradas": j.entradas, "cabeceo": j.cabeceo,
        "valentia": j.valentia, "pase": j.pase, "vision": j.vision, "primer_toque": j.primer_toque,
        "decisiones": j.decisiones, "ritmo": j.ritmo, "aceleracion": j.aceleracion,
        "resistencia": j.resistencia, "fuerza": j.fuerza, "agilidad": j.agilidad,
        "porteria": j.porteria, "anticipacion": j.anticipacion,
    }, j.posicion)
    j.ataque, j.defensa, j.pase, j.fisico = (
        derivados["ataque"], derivados["defensa"], derivados["pase"], derivados["fisico"],
    )


def aplicar_entrenamiento(jugadores: list, foco: str, intensidad: str, bono_centro: float = 0.0) -> None:
    """Modifica in-place los objetos ORM Jugador según el plan de entrenamiento.

    `bono_centro` es el bono de probabilidad de mejora que aporta la red
    multiclub del club (0.0 = sin red), ver
    engine/multiclub_engine.py::bono_red."""
    mult_fatiga = {"BAJA": -10, "MEDIA": 5, "ALTA": 15}.get(intensidad, 5)
    prob_mejora = {"BAJA": 0.05, "MEDIA": 0.08, "ALTA": 0.15}.get(intensidad, 0.08) + bono_centro

    grupo = _GRUPOS_FOCO.get(foco)

    for j in jugadores:
        if foco == "DESCANSO":
            j.energia = min(100, j.energia + 30)
            continue

        j.energia = max(0, min(100, j.energia - mult_fatiga))

        if grupo and j.edad < 29:
            cambio = False
            for atributo in grupo:
                if random.random() < prob_mejora and getattr(j, atributo) < j.potencial:
                    setattr(j, atributo, min(j.potencial, getattr(j, atributo) + 1))
                    cambio = True
            if cambio:
                recalcular_derivados_jugador(j)
