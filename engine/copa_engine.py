"""
Torneos internacionales: Copa de Campeones / Copa Europea (UEFA) y Copa
Libertadores / Copa Sudamericana Ficticias (CONMEBOL).

Formato real (Copa Libertadores 2025, ver investigación en el plan): 32
equipos, 8 grupos de 4 todos-contra-todos, los 2 primeros de cada grupo
pasan a octavos de final. Acá se juega ida y vuelta en todas las fases
salvo la final (partido único, como en la realidad).

Este módulo NO toca la base de datos — solo calcula fechas, arma grupos,
calcula posiciones y decide quién avanza a partir de datos ya cargados.
main.py es responsable de leer/escribir `Calendario`.
"""
import random
from datetime import date, timedelta

GRUPOS = ["GRUPO_A", "GRUPO_B", "GRUPO_C", "GRUPO_D", "GRUPO_E", "GRUPO_F", "GRUPO_G", "GRUPO_H"]

# Semanas desde el inicio de temporada de la confederación. Los partidos de
# copa se juegan siempre martes o miércoles (al azar por fecha) — la liga
# doméstica juega viernes o sábado (ver seed.py) — así nunca chocan entre sí.
DIAS_COPA = [1, 2]  # martes, miércoles (0=lunes en date.weekday())
OFFSET_SEMANAS_GRUPO = [1, 2, 3, 4, 5, 6]
OFFSET_SEMANAS_ELIMINATORIA = {
    "OCTAVOS_IDA": 8, "OCTAVOS_VUELTA": 9,
    "CUARTOS_IDA": 10, "CUARTOS_VUELTA": 11,
    "SEMIS_IDA": 12, "SEMIS_VUELTA": 13,
    "FINAL": 15,
}
RONDAS_ELIMINATORIA = ["OCTAVOS", "CUARTOS", "SEMIS", "FINAL"]

COMPETENCIAS = {
    "UEFA": {"top": "CAMPEONES_UEFA", "segundo": "EUROPEA_UEFA"},
    "CONMEBOL": {"top": "LIBERTADORES", "segundo": "SUDAMERICANA"},
}

# Nombre mostrado por defecto de cada código de competencia, cuando la
# partida no trae nombres personalizados en Partida.competencias_json.
NOMBRES_COMPETENCIA_DEFAULT = {
    "CAMPEONES_UEFA": "Copa de Campeones Ficticia",
    "EUROPEA_UEFA": "Copa Europea Ficticia",
    "LIBERTADORES": "Copa Libertadores Ficticia",
    "SUDAMERICANA": "Copa Sudamericana Ficticia",
}


def fecha_ronda(fecha_inicio_temporada: date, offset_semanas: int) -> date:
    lunes = fecha_inicio_temporada - timedelta(days=fecha_inicio_temporada.weekday())
    return lunes + timedelta(weeks=offset_semanas, days=random.choice(DIAS_COPA))


def _round_robin_simple(ids: list[int]) -> list[list[tuple[int, int]]]:
    """Round robin de 4 equipos (método del círculo) — 3 rondas, cada una
    con 2 partidos."""
    equipos = ids[:]
    n = len(equipos)
    rondas = []
    for r in range(n - 1):
        pares = []
        for i in range(n // 2):
            local, visita = equipos[i], equipos[n - 1 - i]
            pares.append((local, visita) if r % 2 == 0 else (visita, local))
        rondas.append(pares)
        equipos = [equipos[0]] + [equipos[-1]] + equipos[1:-1]
    return rondas


def fixtures_grupo(ids_equipo_grupo: list[int]) -> list[list[tuple[int, int]]]:
    """6 jornadas de ida y vuelta para un grupo de 4 (todos contra todos,
    local y visitante)."""
    ida = _round_robin_simple(ids_equipo_grupo)
    vuelta = [[(visita, local) for local, visita in ronda] for ronda in ida]
    return ida + vuelta


def seleccionar_participantes(overall_por_club: list[tuple[int, float]], cupo: int = 32) -> tuple[list[int], list[int]]:
    """`overall_por_club`: [(id_equipo, overall_promedio_plantel), ...] de
    TODOS los clubes de una confederación. Devuelve (top, segundo_nivel) —
    los `cupo` mejores van al torneo de elite, los siguientes `cupo` al de
    segundo nivel."""
    ordenados = [id_eq for id_eq, _ in sorted(overall_por_club, key=lambda t: -t[1])]
    return ordenados[:cupo], ordenados[cupo:cupo * 2]


def armar_grupos(participantes: list[int]) -> dict[str, list[int]]:
    """Sorteo: reparte los participantes (32, o menos si la confederación no
    llega) en grupos de 4."""
    mezclados = participantes[:]
    random.shuffle(mezclados)
    grupos = {}
    for i, nombre_grupo in enumerate(GRUPOS):
        lote = mezclados[i * 4:(i + 1) * 4]
        if len(lote) == 4:
            grupos[nombre_grupo] = lote
    return grupos


def posiciones_grupo(ids_equipo_grupo: list[int], fixtures_jugados: list[dict]) -> list[int]:
    """`fixtures_jugados`: [{"id_local", "id_visitante", "goles_local", "goles_visitante"}, ...]
    ya filtrados a un solo grupo. Devuelve los ids de equipo ordenados por
    puntos/diferencia de gol/goles a favor (igual criterio que la tabla
    doméstica)."""
    tabla = {id_eq: {"pts": 0, "gf": 0, "gc": 0} for id_eq in ids_equipo_grupo}
    for f in fixtures_jugados:
        gl, gv = f["goles_local"], f["goles_visitante"]
        tabla[f["id_local"]]["gf"] += gl
        tabla[f["id_local"]]["gc"] += gv
        tabla[f["id_visitante"]]["gf"] += gv
        tabla[f["id_visitante"]]["gc"] += gl
        if gl > gv:
            tabla[f["id_local"]]["pts"] += 3
        elif gv > gl:
            tabla[f["id_visitante"]]["pts"] += 3
        else:
            tabla[f["id_local"]]["pts"] += 1
            tabla[f["id_visitante"]]["pts"] += 1
    return sorted(
        ids_equipo_grupo,
        key=lambda id_eq: (-tabla[id_eq]["pts"], -(tabla[id_eq]["gf"] - tabla[id_eq]["gc"]), -tabla[id_eq]["gf"]),
    )


def emparejar_octavos(clasificados_por_grupo: dict[str, list[int]]) -> list[tuple[int, int]]:
    """Cruza 1° de un grupo contra 2° de otro, como en el torneo real —
    simplificado acá a un cruce fijo entre grupos consecutivos de a pares
    (A-B, C-D, E-F, G-H) para no depender de bombos."""
    cruces = []
    nombres = list(clasificados_por_grupo.keys())
    for i in range(0, len(nombres), 2):
        if i + 1 >= len(nombres):
            break
        primero_a, segundo_a = clasificados_por_grupo[nombres[i]]
        primero_b, segundo_b = clasificados_por_grupo[nombres[i + 1]]
        cruces.append((primero_a, segundo_b))
        cruces.append((primero_b, segundo_a))
    return cruces


def ganador_eliminatoria(ida: dict, vuelta: dict) -> tuple[int, bool]:
    """`ida`/`vuelta`: {"id_local", "id_visitante", "goles_local", "goles_visitante"}
    de los dos partidos de una eliminatoria (la vuelta con local/visitante
    invertidos respecto a la ida). Devuelve (id_equipo_ganador, hubo_empate_en_agregado)
    — si hubo empate, el llamador es responsable de sortear el desempate de
    penales y pasar ESE ganador acá afuera; esta función solo informa si hace falta."""
    equipo_a = ida["id_local"]
    equipo_b = ida["id_visitante"]
    agregado_a = ida["goles_local"] + vuelta["goles_visitante"]
    agregado_b = ida["goles_visitante"] + vuelta["goles_local"]
    if agregado_a > agregado_b:
        return equipo_a, False
    if agregado_b > agregado_a:
        return equipo_b, False
    return equipo_a, True  # empate en agregado — el ganador real se decide por penales
