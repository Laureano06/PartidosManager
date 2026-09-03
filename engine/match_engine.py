"""Motor de simulación de partidos minuto a minuto."""
import random

from engine.tactics_engine import calcular_matriz_tactica
from engine.injury_engine import evaluar_lesion

CHANCE_LINES = [
    "{p} encara por la banda y tira el centro al área.",
    "{p} probó de media distancia, exige al arquero.",
    "{p} queda mano a mano con el arquero.",
    "Córner cerrado, {p} cabecea dentro del área chica.",
    "Contragolpe rápido, {p} define solo frente al arco.",
]
GOAL_LINES = [
    "¡GOL! La pelota se clava en el ángulo.",
    "¡GOL! Remate cruzado, imposible para el arquero.",
    "¡GOL! Cabezazo letal.",
    "¡GOL! Definición fría dentro del área.",
]
SAVE_LINES = [
    "El arquero rechaza al córner.",
    "Gran atajada, la pelota se va al lateral.",
    "El palo le niega el gol.",
    "El defensor corta antes del remate.",
]


def _avg(players, attr, default=50):
    vals = [p[attr] for p in players]
    return sum(vals) / len(vals) if vals else default


# Cuánto pesa cada posición en el ataque/defensa del equipo (base, con
# "duty" EQUILIBRADO). Con estos valores el cálculo da EXACTAMENTE lo mismo
# que antes de existir el duty: solo DEL+MED aportan a ataque, solo DEF+POR
# aportan a defensa. DEF/MED tienen un peso base chico en el otro lado
# (0.15) para que un "duty" OFENSIVO/DEFENSIVO tenga algo real que amplificar.
PESO_BASE_ATAQUE = {"POR": 0.0, "DEF": 0.15, "MED": 0.9, "DEL": 1.3}
PESO_BASE_DEFENSA = {"POR": 1.0, "DEF": 1.2, "MED": 0.15, "DEL": 0.0}

# El "duty" es la instrucción individual del jugador dentro de la táctica:
# no cambia sus atributos, cambia cuánto pesa su ataque/defensa en el
# cálculo del equipo (un lateral en modo OFENSIVO empuja el ataque del
# equipo más que uno DEFENSIVO, a costa de aportar menos atrás).
MOD_DUTY_ATAQUE = {"DEFENSIVO": 0.6, "EQUILIBRADO": 1.0, "OFENSIVO": 1.4}
MOD_DUTY_DEFENSA = {"DEFENSIVO": 1.4, "EQUILIBRADO": 1.0, "OFENSIVO": 0.6}


def _promedio_ponderado(players, attr, peso_base, mod_duty):
    num = 0.0
    den = 0.0
    for p in players:
        peso = peso_base.get(p["posicion"], 0.0) * mod_duty.get(p.get("duty", "EQUILIBRADO"), 1.0)
        num += p[attr] * peso
        den += peso
    return num / den if den else 50.0


def team_power(players: list[dict]) -> dict:
    atk = _promedio_ponderado(players, "ataque", PESO_BASE_ATAQUE, MOD_DUTY_ATAQUE)
    dfn = _promedio_ponderado(players, "defensa", PESO_BASE_DEFENSA, MOD_DUTY_DEFENSA)
    energia_prom = _avg(players, "energia", 100)
    return {"ataque": atk, "defensa": dfn, "energia_promedio": energia_prom}


def _pick_scorer(players: list[dict]) -> dict:
    pool = [p for p in players if p["posicion"] in ("DEL", "MED")] or players
    pesos = [max(1, p["ataque"]) for p in pool]
    return random.choices(pool, weights=pesos, k=1)[0]


def simulate_match(
    local_players: list[dict],
    visit_players: list[dict],
    tactica_local: dict,
    tactica_visit: dict,
    generar_relato: bool = True,
    ia_local: bool = False,
    ia_visit: bool = False,
    minuto_inicio: int = 1,
    minuto_fin: int = 90,
    gh_inicial: int = 0,
    gv_inicial: int = 0,
    factor_medico_local: float = 1.0,
    factor_medico_visit: float = 1.0,
) -> dict:
    """
    players: lista de dicts con al menos id_jugador, nombre, posicion, ataque,
    defensa, energia.
    tactica_*: dict con formacion, mentalidad, presion.
    ia_local/ia_visit: si es True, ese equipo ajusta su mentalidad solo
    según el marcador (perdiendo min 65+ -> ofensiva, ganando min 80+ -> defensiva).
    minuto_inicio/minuto_fin: para simular por tramos (p. ej. 1-45 y 46-90 en
    el modo "jugar el partido" con entretiempo real) — cada llamada solo
    corre esos minutos, y gh_inicial/gv_inicial continúan el marcador del
    tramo anterior.

    Devuelve: {gh, gv, events, lesiones, energia_gastada: {id_jugador: delta}}
    """
    pow_local = team_power(local_players)
    pow_visit = team_power(visit_players)

    tactica_local = dict(tactica_local)
    tactica_visit = dict(tactica_visit)

    events = []
    lesiones = []
    energia_gastada: dict[int, int] = {}
    gh = gh_inicial
    gv = gv_inicial

    for minuto in range(minuto_inicio, minuto_fin + 1):
        # --- IA táctica: reacciona al marcador ---
        if minuto >= 65 and (ia_local or ia_visit):
            diff = gh - gv
            if ia_local:
                if diff < 0 and tactica_local["mentalidad"] != "OFENSIVA":
                    tactica_local["mentalidad"] = "OFENSIVA"
                    tactica_local["presion"] = "ALTA"
                    if generar_relato:
                        events.append({"minuto": minuto, "tipo": "CAMBIO_TACTICO", "equipo": "local",
                                        "jugador": None, "texto": "El local se vuelca al ataque buscando el empate."})
                elif diff > 0 and minuto >= 80 and tactica_local["mentalidad"] != "DEFENSIVA":
                    tactica_local["mentalidad"] = "DEFENSIVA"
                    tactica_local["presion"] = "BAJA"
                    if generar_relato:
                        events.append({"minuto": minuto, "tipo": "CAMBIO_TACTICO", "equipo": "local",
                                        "jugador": None, "texto": "El local se replantea atrás para cuidar el resultado."})
            if ia_visit:
                if diff > 0 and tactica_visit["mentalidad"] != "OFENSIVA":
                    tactica_visit["mentalidad"] = "OFENSIVA"
                    tactica_visit["presion"] = "ALTA"
                    if generar_relato:
                        events.append({"minuto": minuto, "tipo": "CAMBIO_TACTICO", "equipo": "visitante",
                                        "jugador": None, "texto": "La visita se vuelca al ataque buscando el empate."})
                elif diff < 0 and minuto >= 80 and tactica_visit["mentalidad"] != "DEFENSIVA":
                    tactica_visit["mentalidad"] = "DEFENSIVA"
                    tactica_visit["presion"] = "BAJA"
                    if generar_relato:
                        events.append({"minuto": minuto, "tipo": "CAMBIO_TACTICO", "equipo": "visitante",
                                        "jugador": None, "texto": "La visita se replantea atrás para cuidar el resultado."})

        matriz_local = calcular_matriz_tactica(
            tactica_local.get("formacion", "4-4-2"),
            tactica_local.get("mentalidad", "BALANCEADA"),
            tactica_local.get("presion", "MEDIA"),
            pow_local["energia_promedio"],
        )
        matriz_visit = calcular_matriz_tactica(
            tactica_visit.get("formacion", "4-4-2"),
            tactica_visit.get("mentalidad", "BALANCEADA"),
            tactica_visit.get("presion", "MEDIA"),
            pow_visit["energia_promedio"],
        )

        # desgaste físico del minuto
        for p in local_players:
            delta = round(0.5 * matriz_local["mod_desgaste"], 2)
            energia_gastada[p["id_jugador"]] = energia_gastada.get(p["id_jugador"], 0) + delta
        for p in visit_players:
            delta = round(0.5 * matriz_visit["mod_desgaste"], 2)
            energia_gastada[p["id_jugador"]] = energia_gastada.get(p["id_jugador"], 0) + delta

        # oportunidad local (con ventaja de localía)
        atk_l = pow_local["ataque"] * matriz_local["mod_ataque"] * 1.05
        def_v = pow_visit["defensa"] * matriz_visit["mod_defensa"]
        prob_gol_local = max(0.003, min(0.05, (atk_l / (atk_l + def_v)) * 0.055))
        if random.random() < prob_gol_local:
            gh += 1
            scorer = _pick_scorer(local_players)
            if generar_relato:
                events.append({"minuto": minuto, "tipo": "GOL", "equipo": "local",
                                "jugador": scorer["nombre"],
                                "texto": f"{random.choice(GOAL_LINES)} {scorer['nombre']} marca para el local."})

        # oportunidad visitante
        atk_v = pow_visit["ataque"] * matriz_visit["mod_ataque"]
        def_l = pow_local["defensa"] * matriz_local["mod_defensa"]
        prob_gol_visit = max(0.003, min(0.05, (atk_v / (atk_v + def_l)) * 0.05))
        if random.random() < prob_gol_visit:
            gv += 1
            scorer = _pick_scorer(visit_players)
            if generar_relato:
                events.append({"minuto": minuto, "tipo": "GOL", "equipo": "visitante",
                                "jugador": scorer["nombre"],
                                "texto": f"{random.choice(GOAL_LINES)} {scorer['nombre']} marca para la visita."})

        # tarjetas (chance chica ligada a mod_tarjeta)
        if random.random() < 0.004 * matriz_local["mod_tarjeta"]:
            p = random.choice(local_players)
            events.append({"minuto": minuto, "tipo": "TARJETA_AMARILLA", "equipo": "local",
                            "jugador": p["nombre"], "texto": f"Amarilla para {p['nombre']}."})
        if random.random() < 0.004 * matriz_visit["mod_tarjeta"]:
            p = random.choice(visit_players)
            events.append({"minuto": minuto, "tipo": "TARJETA_AMARILLA", "equipo": "visitante",
                            "jugador": p["nombre"], "texto": f"Amarilla para {p['nombre']}."})

        # lesiones (chequeo liviano, no todos los minutos para no saturar)
        if minuto % 7 == 0:
            for p in local_players:
                energia_actual = p["energia"] - energia_gastada.get(p["id_jugador"], 0)
                lesion = evaluar_lesion(energia_actual, factor_medico_local)
                if lesion:
                    lesiones.append({"id_jugador": p["id_jugador"], "nombre": p["nombre"], **lesion})
                    events.append({"minuto": minuto, "tipo": "LESION",
                                    "equipo": "local",
                                    "jugador": p["nombre"],
                                    "texto": f"{p['nombre']} se resiente físicamente y no puede continuar."})
            for p in visit_players:
                energia_actual = p["energia"] - energia_gastada.get(p["id_jugador"], 0)
                lesion = evaluar_lesion(energia_actual, factor_medico_visit)
                if lesion:
                    lesiones.append({"id_jugador": p["id_jugador"], "nombre": p["nombre"], **lesion})
                    events.append({"minuto": minuto, "tipo": "LESION",
                                    "equipo": "visitante",
                                    "jugador": p["nombre"],
                                    "texto": f"{p['nombre']} se resiente físicamente y no puede continuar."})

    if generar_relato:
        events.sort(key=lambda e: e["minuto"])

    return {
        "gh": gh,
        "gv": gv,
        "events": events,
        "lesiones": lesiones,
        "energia_gastada": energia_gastada,
    }
