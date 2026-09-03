"""
Academia (plantel juvenil) de un club: categorías, reglas de movimiento y
generación de jugadores. Funciones puras (no tocan la base) al estilo de
training_engine.py — main.py hace las consultas/commits.
"""
import random

from engine import data_gen

CATEGORIAS = ["SUB13", "SUB15", "SUB18", "SUB21"]
EDAD_MINIMA_CONTRATO = 15  # sin contrato antes de esta edad: no hay Primera ni robo posible
TAMANIO_MINIMO_CATEGORIA = 15

RANGOS_EDAD = {
    "SUB13": (10, 13),
    "SUB15": (14, 15),
    "SUB18": (16, 18),
    "SUB21": (19, 21),
}

# 15 jugadores por categoría: 2 arqueros, 5 defensores, 5 mediocampistas, 3 delanteros.
DISTRIBUCION_POSICIONES = [("POR", 2), ("DEF", 5), ("MED", 5), ("DEL", 3)]

_ORDEN_CATEGORIA = {c: i for i, c in enumerate(CATEGORIAS)}


def categoria_minima_por_edad(edad: int) -> str:
    if edad <= 13:
        return "SUB13"
    if edad <= 15:
        return "SUB15"
    if edad <= 18:
        return "SUB18"
    return "SUB21"


def puede_mover_a_categoria(edad: int, categoria_destino: str) -> bool:
    """Regla única: nunca bajar por debajo de la categoría mínima de la edad.
    Sub-21 no tiene techo (acepta cualquier edad, incluso bajar ahí a un
    jugador grande de Primera). Ascenso a Primera exige >= EDAD_MINIMA_CONTRATO
    porque implica firmarle un contrato."""
    if categoria_destino == "PRIMERA":
        return edad >= EDAD_MINIMA_CONTRATO
    return _ORDEN_CATEGORIA[categoria_destino] >= _ORDEN_CATEGORIA[categoria_minima_por_edad(edad)]


def categoria_tras_cumplir_anios(categoria_actual: str, edad_nueva: int) -> str:
    """Ascenso automático por edad — nunca baja, nunca toca a un jugador de Primera."""
    if categoria_actual == "PRIMERA":
        return categoria_actual
    minima = categoria_minima_por_edad(edad_nueva)
    return minima if _ORDEN_CATEGORIA[minima] > _ORDEN_CATEGORIA[categoria_actual] else categoria_actual


def puede_reclutar(edad: int, pais_origen: str | None, pais_destino: str) -> bool:
    """Robo de un juvenil de otro club. Nunca antes de EDAD_MINIMA_CONTRATO
    (no se le puede robar algo a quien ni contrato puede tener). Entre esa
    edad y 18 exclusive, solo mismo país (Art. 19 RSTP: transferencia
    internacional de menores de 18 prohibida salvo excepciones acotadas)."""
    if edad < EDAD_MINIMA_CONTRATO:
        return False
    if edad < 18:
        return pais_origen == pais_destino
    return True


def _nacionalidad_academia(pais_club: str) -> str:
    """~85% nace en el país del club (una academia se nutre de pibes
    locales), ~15% extranjero — le da sentido real a la restricción de país
    al robar juveniles."""
    if pais_club in data_gen.NATIONS and random.random() < 0.85:
        return pais_club
    return data_gen.random_nation()


def _tiene_contrato_juvenil(edad: int, potencial: int) -> bool:
    """A partir de los 15 el club puede haberle atado un contrato juvenil
    formal — más probable cuanto mejor es el prospecto (un club se apura a
    firmar a sus mejores canteranos). Antes de esa edad nunca hay contrato:
    reclutarlo es directo. Si lo hay, hay que negociar con el club como con
    cualquier jugador contratado (ver /fichajes/ofertar)."""
    if edad < EDAD_MINIMA_CONTRATO:
        return False
    prob = 0.25 + min(0.5, max(0, potencial - 70) * 0.02)
    return random.random() < prob


def _salario_juvenil(valor_mercado: int) -> int:
    """Sueldo de un contrato juvenil: una fracción chica de lo que cobraría
    ya siendo profesional — todavía no es santa de la primera plantilla."""
    return max(200, round(valor_mercado * random.uniform(0.0005, 0.0015) / 100) * 100)


def generar_jugador_academia(categoria: str, pais_club: str, posicion: str, factor: float = 1.0) -> dict:
    """`factor` escala los atributos igual que en un plantel de Primera
    (`factor_overall_liga`/`_escalar_attrs`) — un canterano de hoy es el
    profesional de dentro de 10 años, así que su nivel de base tiene que
    guardar relación con el nivel actual DE ESE CLUB, no ser parejo en
    cualquier academia del juego (ver _asegurar_academia en main.py, que
    calcula el factor a partir del overall promedio del plantel de Primera)."""
    edad_min, edad_max = RANGOS_EDAD[categoria]
    edad = random.randint(edad_min, edad_max)
    nation = _nacionalidad_academia(pais_club)
    attrs = data_gen._escalar_attrs(data_gen.gen_attributes(posicion), factor)
    overall = data_gen._overall({**attrs, "posicion": posicion})
    # Misma distribución que cualquier otro jugador del juego (data_gen._generar_potencial):
    # la inmensa mayoría tiene margen modesto, y solo un puñado en TODO el juego
    # es una futura estrella — un canterano no es la excepción a esa escasez.
    # Sí se beneficia del margen más ancho que la fórmula da por ser joven.
    potencial = data_gen._generar_potencial(overall, edad)
    valor_mercado = data_gen._valor_mercado_real(overall, edad, potencial)
    tiene_contrato = _tiene_contrato_juvenil(edad, potencial)
    return {
        "nombre": data_gen.random_name(nation),
        "posicion": posicion,
        "posicion_especifica": data_gen.random_posicion_especifica(posicion),
        "nacionalidad": nation,
        "edad": edad,
        **attrs,
        "potencial": potencial,
        "energia": 100,
        "moral": random.randint(65, 85),
        "valor_mercado": valor_mercado,
        # salario==0 (y sin fecha_fin_contrato, que pone el caller con la
        # fecha actual de la partida) es la señal de "sin contrato": se puede
        # reclutar directo. Si tiene salario, hay que negociar con el club.
        "salario": _salario_juvenil(valor_mercado) if tiene_contrato else 0,
        "categoria": categoria,
    }


def generar_categoria_academia(categoria: str, pais_club: str, factor: float = 1.0) -> list[dict]:
    return [
        generar_jugador_academia(categoria, pais_club, pos, factor)
        for pos, cantidad in DISTRIBUCION_POSICIONES
        for _ in range(cantidad)
    ]


def generar_academia_completa(pais_club: str, factor: float = 1.0) -> list[dict]:
    """Las 4 categorías, 15 jugadores cada una (60 en total)."""
    jugadores = []
    for categoria in CATEGORIAS:
        jugadores.extend(generar_categoria_academia(categoria, pais_club, factor))
    return jugadores


def calcular_factor_desde_plantel(jugadores_primera: list, bono_instalaciones: float = 0.0) -> float:
    """Factor de escala para generar la Academia a partir del nivel ACTUAL
    del plantel de Primera de ese club — un canterano de hoy va a ser el
    profesional de dentro de 10 años, así que su punto de partida tiene que
    guardar relación con lo que ese club concreto produce, no ser parejo en
    cualquier academia del juego (mismo mecanismo que factor_overall_liga
    para planteles de Primera, pero anclado al club en vez de a la liga).

    `bono_instalaciones` es el bono combinado de Instalaciones Juveniles +
    Entrenadores Juveniles del club (0.0 = sin bono, ver Equipo en
    models.py) — un club que invierte en su cantera saca canteranos por
    encima de lo que su plantel de Primera solo justificaría."""
    if not jugadores_primera:
        return 1.0
    promedio = sum(j.overall for j in jugadores_primera) / len(jugadores_primera)
    return max(0.4, min(1.15, (promedio / data_gen._MAX_OVERALL_CRUDO) * (1 + bono_instalaciones)))


def calcular_n_candidatos_intake(cantidad_actual: int, bono_captacion: int = 0) -> int:
    """Cuántos candidatos ofrecer en el intake anual de una categoría: si
    falta gente para llegar a 15, justo los que faltan; si ya está completa,
    5 igual, de pura oportunidad (15 es el piso anual, no el techo).
    `bono_captacion` (0-5) suma candidatos extra según el nivel de
    Captación Juvenil del club."""
    gap = max(0, TAMANIO_MINIMO_CATEGORIA - cantidad_actual)
    base = gap if gap > 0 else 5
    return base + bono_captacion


def crecer_juvenil(jugador) -> None:
    """Crecimiento de fin de temporada de un jugador de Academia: sin
    declive ni retiro (no corresponde a esta edad), probabilidad de mejora
    más alta y pareja que un profesional consagrado — todavía tiene todo el
    margen de desarrollo por delante."""
    if random.random() >= 0.35:
        return
    attrs = {a: getattr(jugador, a) for a in data_gen.ATRIBUTOS_ENTRENABLES}
    for a, valor in attrs.items():
        attrs[a] = min(jugador.potencial, valor + random.randint(1, 3))
    data_gen.recalcular_derivados(attrs, jugador.posicion)
    for a, valor in attrs.items():
        setattr(jugador, a, valor)
