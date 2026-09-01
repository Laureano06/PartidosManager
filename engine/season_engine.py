import random

from engine.data_gen import gen_player_dict, _valor_mercado_real, _overall, _generar_potencial
from engine.academia_engine import crecer_juvenil, categoria_tras_cumplir_anios

TIPOS_RETIRO_EDAD = 35


def aplicar_desgaste(jugadores_por_id: dict, energia_gastada: dict) -> None:
    """jugadores_por_id: {id_jugador: objeto ORM Jugador}"""
    for id_j, delta in energia_gastada.items():
        j = jugadores_por_id.get(id_j)
        if j:
            j.energia = max(0, round(j.energia - delta))


def procesar_lesiones(jugadores_por_id: dict, lesiones: list[dict]) -> None:
    for les in lesiones:
        j = jugadores_por_id.get(les["id_jugador"])
        if j:
            j.lesionado = True
            j.tipo_lesion = les["tipo"]
            j.semanas_lesion = les["semanas"]


def reducir_lesiones(jugadores: list) -> None:
    """Se llama una vez por jornada para que los lesionados se vayan recuperando."""
    for j in jugadores:
        if j.lesionado:
            j.semanas_lesion -= 1
            if j.semanas_lesion <= 0:
                j.lesionado = False
                j.semanas_lesion = 0
                j.tipo_lesion = None


def procesar_fin_temporada(jugadores: list) -> list:
    """Envejece, mejora/declina y retira jugadores. Devuelve la lista de
    objetos ORM que deben eliminarse (retirados) para que el caller cree
    sus reemplazos (regens) en la misma posición."""
    retirados = []
    for j in jugadores:
        j.edad += 1
        j.energia = 100

        if j.categoria != "PRIMERA":
            # Un juvenil no se retira ni declina — todavía tiene todo el
            # desarrollo por delante. Solo crece y, si corresponde, asciende
            # solo de categoría (nunca baja, nunca toca PRIMERA).
            crecer_juvenil(j)
            j.categoria = categoria_tras_cumplir_anios(j.categoria, j.edad)
            j.valor_mercado = _valor_mercado_real(j.overall, j.edad, j.potencial)
            continue

        if j.edad >= TIPOS_RETIRO_EDAD:
            prob_retiro = (j.edad - TIPOS_RETIRO_EDAD + 1) * 0.2
            if random.random() < prob_retiro:
                retirados.append(j)
                continue

        # Proxy de "tuvo buena temporada": si fue titular, jugó y rindió lo
        # suficiente como para no perder su lugar. No es una estadística de
        # partidos en serio, pero evita que la mejora/declive sea puro azar
        # desconectado de cómo le fue en la cancha.
        tuvo_buena_temporada = j.rol == "TITULAR"

        if j.edad < 23:
            if tuvo_buena_temporada:
                mejora = random.randint(1, 3)
            elif j.rol == "SUPLENTE":
                mejora = random.randint(0, 1)  # sumó algunos minutos, progreso mínimo
            else:
                mejora = 0  # apenas jugó: sin rodaje no hay desarrollo
            j.ataque = min(j.potencial, j.ataque + mejora)
            j.defensa = min(j.potencial, j.defensa + mejora)
        elif j.edad > 30:
            if tuvo_buena_temporada:
                # Puede sostener su nivel — incluso una gran temporada a
                # veces alcanza para mejorar un poco pese a la edad.
                declive = random.choice([-1, 0, 0, 1, 1])
            else:
                declive = random.randint(1, 3)  # perdió el puesto: declive más marcado
            j.ataque = max(30, j.ataque - declive)
            j.defensa = max(30, j.defensa - declive)

        # El pase de un jugador tiene que reflejar cómo quedó después de
        # envejecer/desarrollarse, no el valor congelado del día que se
        # generó — si no, un juvenil nunca se revaloriza ni un veterano
        # se abarata con el tiempo.
        j.valor_mercado = _valor_mercado_real(j.overall, j.edad, j.potencial)

    return retirados


def generar_regen(posicion: str) -> dict:
    """Jugador juvenil de reemplazo (17-19 años) para cubrir un retiro."""
    data = gen_player_dict(posicion)
    data["edad"] = random.randint(17, 19)
    # gen_player_dict ya calculó un potencial acorde a sus atributos base;
    # lo volvemos a tirar acá porque pisamos la edad (misma distribución
    # que cualquier otro jugador del juego, pero con el margen ancho que le
    # corresponde a un juvenil de 17-19, no el de la edad random original).
    overall = _overall({**data, "posicion": posicion})
    data["potencial"] = _generar_potencial(overall, data["edad"])
    # gen_player_dict calculó valor/salario con la edad y el potencial
    # originales (antes de pisarlos acá arriba) — hay que recalcularlos,
    # si no el regen queda con un precio que no corresponde a un juvenil.
    data["valor_mercado"] = _valor_mercado_real(overall, data["edad"], data["potencial"])
    data["salario"] = max(400, round(data["valor_mercado"] * random.uniform(0.0015, 0.004) / 100) * 100)
    return data
