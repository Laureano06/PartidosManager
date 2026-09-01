"""
Generación de datos ficticios para poblar el juego.

Igual que en el prototipo web: nombres 100% inventados, con nacionalidad
como dato de sabor (no hay jugadores ni clubes reales acá). Los atributos
de juego siempre se generan, nunca se copian de ninguna base de datos con
licencia (FIFA, FM, Opta, etc.).
"""
import random

NATIONS = {
    "Argentina": {
        "first": ["Mateo", "Lucas", "Thiago", "Benjamín", "Joaquín", "Franco", "Nicolás", "Ezequiel", "Agustín", "Bautista", "Ignacio", "Tomás", "Facundo", "Gonzalo", "Rodrigo"],
        "last": ["Gómez", "Fernández", "Rodríguez", "López", "Martínez", "García", "Pérez", "Sosa", "Romero", "Álvarez", "Torres", "Ruiz", "Díaz", "Molina", "Acosta"],
    },
    "Brasil": {
        "first": ["Gabriel", "Lucas", "Matheus", "Rafael", "Vinícius", "Bruno", "Thiago", "Caio", "Igor", "Wesley"],
        "last": ["Silva", "Souza", "Oliveira", "Santos", "Pereira", "Costa", "Almeida", "Ribeiro", "Carvalho", "Barbosa"],
    },
    "España": {
        "first": ["Pablo", "Álvaro", "Sergio", "Marc", "Iker", "Hugo", "Adrián", "Diego", "Mario", "Pau"],
        "last": ["García", "Fernández", "López", "Martín", "Sánchez", "Pérez", "Gómez", "Ruiz", "Hernández", "Jiménez"],
    },
    "Inglaterra": {
        "first": ["Jack", "Harry", "Oliver", "George", "Charlie", "James", "Tom", "Ben", "Josh", "Sam"],
        "last": ["Smith", "Jones", "Taylor", "Brown", "Wilson", "Evans", "Walker", "Wright", "Robinson", "Clarke"],
    },
    "Italia": {
        "first": ["Matteo", "Lorenzo", "Andrea", "Davide", "Alessio", "Francesco", "Marco", "Luca", "Simone", "Riccardo"],
        "last": ["Rossi", "Ferrari", "Russo", "Romano", "Colombo", "Ricci", "Marino", "Greco", "Bruno", "Gallo"],
    },
    "Francia": {
        "first": ["Léo", "Hugo", "Nathan", "Enzo", "Jules", "Théo", "Rayan", "Mathis", "Antoine", "Clément"],
        "last": ["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Petit", "Durand", "Leroy", "Moreau", "Simon"],
    },
    "Alemania": {
        "first": ["Lukas", "Finn", "Jonas", "Leon", "Paul", "Niklas", "Tim", "Julian", "Max", "Felix"],
        "last": ["Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker", "Hoffmann", "Koch"],
    },
    "Uruguay": {
        "first": ["Diego", "Nahuel", "Maximiliano", "Rodrigo", "Santiago", "Federico", "Bruno", "Nicolás", "Sebastián", "Martín"],
        "last": ["Suárez", "Cáceres", "Silva", "Rodríguez", "Fernández", "Pereira", "Techera", "Recoba", "Gargano", "Lodeiro"],
    },
    "Chile": {
        "first": ["Matías", "Alexis", "Arturo", "Charles", "Gary", "Claudio", "Eduardo", "Mauricio", "Esteban", "Jean"],
        "last": ["Muñoz", "Aránguiz", "Medel", "Vidal", "Isla", "Bravo", "Fuenzalida", "Orellana", "Sánchez", "Pinilla"],
    },
}
NATION_LIST = list(NATIONS.keys())

# Ligas ficticias inspiradas en el mapa futbolístico real (país y "aire" del
# club), pero con códigos y nombres 100% inventados: ningún nombre, escudo
# ni dato de club real se usa acá.
LIGAS = {
    "ARG1": {"pais": "Argentina", "nombre": "Liga Profesional Ficticia"},
    "BRA1": {"pais": "Brasil", "nombre": "Brasileirao Ficticio"},
    "ESP1": {"pais": "España", "nombre": "Liga Ibérica Ficticia"},
    "ING1": {"pais": "Inglaterra", "nombre": "Premier Ficticia"},
    "ITA1": {"pais": "Italia", "nombre": "Serie Ficticia"},
    "FRA1": {"pais": "Francia", "nombre": "Ligue Ficticia"},
    "ALE1": {"pais": "Alemania", "nombre": "Bundesliga Ficticia"},
    "URU1": {"pais": "Uruguay", "nombre": "Liga Charrúa Ficticia"},
    "CHI1": {"pais": "Chile", "nombre": "Liga Andina Ficticia"},
}

# UEFA (Europa) vs CONMEBOL (Sudamérica) — determina qué liga entra en cada
# par de torneos internacionales (Copa de Campeones/Europea vs Libertadores/
# Sudamericana Ficticias) y qué fecha real de inicio de temporada le toca
# (agosto vs enero) — ver `engine/copa_engine.py`.
CONFEDERACION = {
    "ARG1": "CONMEBOL", "BRA1": "CONMEBOL", "URU1": "CONMEBOL", "CHI1": "CONMEBOL",
    "ESP1": "UEFA", "ING1": "UEFA", "ITA1": "UEFA", "FRA1": "UEFA", "ALE1": "UEFA",
}

CLUB_NAMES = {
    "ARG1": [
        ("BOC", "Xeneize FC"), ("RIV", "Millonario AC"), ("RAC", "Academia FC"),
        ("IND", "Rojo Fuerte"), ("SLO", "Cuervo Santo"), ("EST", "Pincharrata CD"),
        ("VEL", "Fortín Liniers"), ("HUR", "Globo Parque"), ("NEW", "Lepra Rosarina"),
        ("ROS", "Canalla Central"), ("TAL", "Matador Cordobés"), ("BEL", "Pirata Celeste"),
        ("GIM", "Lobo Platense"), ("ARG", "Bicho Junior"), ("BAN", "Taladro Sur"),
        ("LAN", "Granate Este"), ("TIG", "Matador Victoria"), ("COL", "Sabalero Santa Fe"),
        ("UNI", "Tatengue FC"), ("GOD", "Tomba Mendocina"),
    ],
    "BRA1": [
        ("FLA", "Rubro Nação"), ("PAL", "Verdão Porco"), ("COR", "Timão Fiel"),
        ("SAO", "Tricolor Paulista"), ("SAN", "Peixe Vila"), ("GRE", "Imortal Tricolor"),
        ("INT", "Colorado Beira-Rio"), ("FLU", "Pó de Arroz"), ("BOT", "Fogão Glorioso"),
        ("VAS", "Gigante Cruzmaltino"), ("ATM", "Galo Mineiro"), ("CRU", "Raposa Celeste"),
        ("BAH", "Esquadrão Baiano"), ("SPO", "Leão Recifense"), ("CEA", "Vovô Cearense"),
        ("FOR", "Leão Pici"), ("ATP", "Furacão Paranaense"), ("CTB", "Coxa Verde"),
        ("GOI", "Esmeraldino Goiano"), ("BRG", "Massa Bruta"),
    ],
    "ESP1": [
        ("MAD", "Merengue Real"), ("BAR", "Blaugrana Culé"), ("ATL", "Colchonero Metropolitano"),
        ("SEV", "Nervionense FC"), ("VAL", "Che Turia"), ("VIL", "Submarino Amarillo"),
        ("RSO", "Txuri Urdin"), ("ATH", "León Vizcaíno"), ("BET", "Verdiblanco Bético"),
        ("CEL", "Celeste Vigués"), ("ESP", "Perico Catalán"), ("GET", "Azulón Getafense"),
        ("OSA", "Rojillo Navarro"), ("MLL", "Bermellón Balear"), ("GIR", "Gironí FC"),
        ("RAY", "Franjirrojo Vallecano"), ("ALA", "Babazorro Alavés"), ("LPA", "Amarillo Canario"),
        ("CAD", "Amarillo Gaditano"), ("GRA", "Nazarí Granadino"),
    ],
    "ING1": [
        ("MANC", "Sky Blue City"), ("MANU", "Red Devils United"), ("LIV", "Kop Reds"),
        ("CHE", "Blues Bridge"), ("ARS", "Gunners North"), ("TOT", "Lilywhite Spurs"),
        ("NEW", "Magpie Toon"), ("AVL", "Claret Villans"), ("WHU", "Hammers East"),
        ("BRI", "Seagull Coast"), ("EVE", "Toffee Blue"), ("LEI", "Foxes Central"),
        ("WOL", "Wanderer Wolves"), ("CRY", "Eagle Palace"), ("FUL", "Cottager Craven"),
        ("BRE", "Bee Griffin"), ("NFO", "Forest Tricky"), ("BOU", "Cherry Coast"),
        ("BUR", "Claret Clarets"), ("SHU", "Blade Sheffield"),
    ],
    "ITA1": [
        ("VEC", "Vecchia Signora FC"), ("ROS", "Rossonero Milanese"), ("NER", "Nerazzurro Interno"),
        ("PAR", "Partenopeo del Golfo"), ("GIA", "Giallorosso Capitolino"), ("BIA", "Biancoceleste Laziale"),
        ("VIO", "Viola Toscana"), ("DEA", "Dea Orobica"), ("TOR", "Toro Granata"),
        ("FEL", "Felsineo Rossoblu"), ("GRI", "Grifone Ligure"), ("BLU", "Blucerchiato Doriano"),
        ("FRI", "Friulano Bianconero"), ("ISO", "Rossoblu Isolano"), ("SCA", "Scaligero Veronese"),
        ("NEV", "Neroverde Emiliano"), ("AZE", "Azzurro Empolese"), ("SAL", "Salentino Giallorosso"),
        ("DUC", "Ducale Emiliano"), ("BRI2", "Brianzolo Rossoblu"),
    ],
    "FRA1": [
        ("PAR", "Parisien Capital"), ("OLY", "Olympien Phocéen"), ("GON", "Gone Rhodanien"),
        ("MON", "Monegasco Rojiblanco"), ("DOG", "Dogue Nordista"), ("ROU", "Rojinegro Bretón"),
        ("AIG", "Águila Niçoise"), ("SAN", "Sang y Oro Artesiano"), ("ALS", "Alsaciano Fronterizo"),
        ("CAN", "Canario Atlántico"), ("PAI", "Paillade Occitano"), ("VIT", "Violeta Toulousain"),
        ("CHA", "Champenois Espoir"), ("TYZ", "Ty-Zefs Bretón"), ("MAR", "Marino Havrais"),
        ("NOI", "Noir et Blanc Angevin"), ("GRE", "Grenat Lorrain"), ("AUV", "Auvernés de Altura"),
        ("MER", "Merlú Lorientais"), ("AUX", "Auxerrois Borgoñón"),
    ],
    "ALE1": [
        ("BAV", "Bávaro del Sur"), ("AMA", "Amarillo del Ruhr"), ("ROJ", "Rojotoro Sajón"),
        ("WER", "Werkself Renano"), ("AGU", "Águila del Meno"), ("EIS", "Eiserne Berlinés"),
        ("BRE2", "Breisgauer Selvático"), ("LOB", "Lobo de Baja Sajonia"), ("POT", "Potro Renano"),
        ("SUA", "Suabo del Neckar"), ("HOF", "Kraichgau Aldeano"), ("FUG", "Fuggerstadt Suabo"),
        ("KAR", "Carnaval Renano"), ("MUS", "Musel Hanseático"), ("BOC", "Cuenca del Ruhr"),
        ("HEI", "Heidenheim Suabo"), ("KIE", "Kiezkicker Portuario"), ("HOL", "Holstein Báltico"),
        ("UNB", "Ferroviario Berlinés"), ("PAD", "Paderborn Oriental"),
    ],
    "URU1": [
        ("PEN", "Carbonero Aurinegro"), ("NAC", "Tricolor Bolso"), ("DEF", "Violeta Sportinguista"),
        ("DAN", "Franjeado Danubiano"), ("WAN", "Wanderer Montevideano"), ("CER", "Albiceleste Cerrense"),
        ("RAC", "Academista Charrúa"), ("LIV", "Liverpool de la Aguada"), ("RIV", "River Plate Charrúa"),
        ("FEN", "Fénix Capurrense"), ("RAM", "Rampla Juniorista"), ("PRO", "Progresista Palermitano"),
        ("BOS", "Boston Riverense"), ("CEL", "Celeste del Este"), ("PLZ", "Colonial Portuario"),
        ("VIL", "Villista del Cerro"), ("MIR", "Mirasol Villero"), ("TAC", "Tacuaremboense Norteño"),
        ("SAL", "Salteño Litoraleño"), ("JUV", "Juvenil Sarandiense"),
    ],
    "CHI1": [
        ("COL", "Cacique Popular"), ("UCH", "Azul Universitario"), ("UCA", "Cruzado Franjeado"),
        ("PAL", "Árabe Tino"), ("COB", "Naranja Loino"), ("AUD", "Verde Italiano"),
        ("UES", "Hispano Independencia"), ("OHI", "Celeste Rancagüino"), ("HUA", "Acerero Sureño"),
        ("EVE", "Ruletero Viñamarino"), ("COQ", "Pirata Nortino"), ("ANT", "Minero del Desierto"),
        ("NUB", "Ñuble Diaguita"), ("CUR", "Curicano Torino"), ("SER", "Papayero Serenense"),
        ("PAL2", "Palestino del Norte"), ("SLU", "Canario Luisino"), ("IQU", "Dragón Celeste"),
        ("MEL", "Pencopolitano Sureño"), ("BAR", "Barrabases Sureños"),
    ],
}

# Techo/piso de overall por liga (Europa por encima de Sudamérica, como en
# el fútbol real) y presupuesto base de fichajes por liga (economías más
# grandes en Europa). Dentro de cada liga, el índice del club en su lista
# de CLUB_NAMES ya está ordenado de "grande" a "chico", así que ese índice
# se usa directamente como nivel del club: cuanto más grande, mejores
# jugadores y más presupuesto. Rangos de PRIMERA (no aplica a Academia, que
# escala su propio factor a partir del overall real del plantel de Primera
# de cada club, no de estas constantes): Chile/Uruguay 60-75, Argentina
# 65-80, Brasil 68-82 (un escalón arriba de Argentina), Europa 75-94 (con
# jerarquía interna España/Inglaterra > Italia/Alemania > Francia, todas
# dentro de ese rango).
LIGA_TECHO_OVR = {
    "ARG1": 80, "BRA1": 82, "ESP1": 94, "ING1": 94,
    "ITA1": 92, "FRA1": 90, "ALE1": 91, "URU1": 75, "CHI1": 75,
}
LIGA_PISO_OVR = {
    "ARG1": 65, "BRA1": 68, "ESP1": 80, "ING1": 80,
    "ITA1": 77, "FRA1": 75, "ALE1": 76, "URU1": 60, "CHI1": 60,
}
# Presupuesto de fichajes base por liga, en dólares reales (economías de
# Europa muy por encima de Sudamérica, como en el fútbol real).
LIGA_PRESUPUESTO_BASE = {
    "ARG1": 25_000_000, "BRA1": 35_000_000, "ESP1": 220_000_000, "ING1": 280_000_000,
    "ITA1": 180_000_000, "FRA1": 150_000_000, "ALE1": 200_000_000, "URU1": 12_000_000, "CHI1": 15_000_000,
}
_MAX_OVERALL_CRUDO = 85  # techo aproximado de overall que devuelve gen_attributes sin escalar
# Overall PROMEDIO (no el techo teórico) que gen_attributes devuelve sin
# escalar — usado SOLO por factor_overall_liga (planteles de Primera), para
# que LIGA_TECHO_OVR/LIGA_PISO_OVR describan el overall PROMEDIO real que
# va a tener un plantel, no un techo teórico que casi ningún jugador toca
# (la inmensa mayoría de los atributos salen bien por debajo del máximo de
# su rango random, así que escalar contra el máximo dejaba todo el rango
# de liga sistemáticamente más bajo de lo que decían las constantes). La
# Academia usa su propia calibración aparte (calcular_factor_desde_plantel,
# en academia_engine.py) — estos rangos por liga son solo para Primera.
_OVERALL_CRUDO_PROMEDIO = 66


def nivel_club(indice: int, total: int = 20) -> float:
    """1.0 = club más grande de la liga (primero en la lista), 0.0 = el más chico."""
    if total <= 1:
        return 1.0
    return 1.0 - indice / (total - 1)


def objetivo_por_nivel(nivel: float) -> str:
    """Expectativa de la directiva para la temporada, según qué tan grande
    es el club dentro de su liga (1.0 = el más grande, 0.0 = el más chico)."""
    if nivel >= 0.8:
        return "Pelear el título de liga. No se acepta terminar fuera del podio."
    if nivel >= 0.55:
        return "Clasificar a las copas internacionales, entre los mejores de la tabla."
    if nivel >= 0.3:
        return "Consolidarse a mitad de tabla, sin sobresaltos."
    return "Evitar el descenso. La prioridad absoluta es la permanencia en la categoría."


def factor_overall_liga(codigo_liga: str, tier: float) -> float:
    techo = LIGA_TECHO_OVR.get(codigo_liga, 80)
    piso = LIGA_PISO_OVR.get(codigo_liga, 50)
    techo_club = piso + (techo - piso) * tier
    return techo_club / _OVERALL_CRUDO_PROMEDIO


def presupuesto_club(codigo_liga: str, tier: float) -> int:
    base = LIGA_PRESUPUESTO_BASE.get(codigo_liga, 25_000_000)
    return round(base * (0.15 + 0.85 * tier) / 10_000) * 10_000


def tope_salarial(presupuesto_fichajes: int) -> int:
    """Tope de sueldos (fair play financiero) proporcional al presupuesto de
    fichajes ACTUAL — a diferencia de fijarlo una sola vez por temporada,
    esto se llama cada vez que presupuesto_fichajes cambia (compra, venta,
    préstamo) para que el margen salarial se acomode en el momento, no
    recién en la temporada siguiente."""
    return round(presupuesto_fichajes * 0.3 / 10_000) * 10_000


def nivel_desde_reputacion(codigo_liga: str, reputacion: int) -> float:
    """Inversa exacta de reputacion_club: recupera el tier 0.0-1.0 DENTRO DE
    SU PROPIA LIGA a partir de la reputación (que está en escala global,
    cruza ligas). Hace falta para evaluar el objetivo de temporada, que es
    ambición relativa a la propia liga ("pelear el título" es sobre tu
    liga, no sobre el mundo) — no se puede usar la reputación cruda ahí."""
    techo = LIGA_TECHO_OVR.get(codigo_liga, 80)
    piso = LIGA_PISO_OVR.get(codigo_liga, 50)
    if techo == piso:
        return 0.5
    return max(0.0, min(1.0, (reputacion - piso) / (techo - piso)))


def reputacion_club(codigo_liga: str, tier: float) -> int:
    """Reputación del club en una escala COMPARABLE ENTRE LIGAS (a diferencia
    de `tier`, que es 0.0-1.0 solo dentro de su propia liga) — ancla al mismo
    techo/piso real de `LIGA_TECHO_OVR`/`LIGA_PISO_OVR` que ya usa
    factor_overall_liga, así un club medio de una liga europea (techo alto)
    puede pesar más que el mejor club de una liga sudamericana chica. Usado
    para armar el mercado de ofertas de DT (ver engine/directiva_engine.py)."""
    techo = LIGA_TECHO_OVR.get(codigo_liga, 80)
    piso = LIGA_PISO_OVR.get(codigo_liga, 50)
    return round(piso + (techo - piso) * tier)


_PALETA_COLORES = [
    "#173C2E", "#A6402F", "#3A6EA5", "#6B4E9E", "#B0701C", "#2B6E52", "#7A2F4F", "#1E5A6B",
    "#8C1F28", "#264653", "#2A9D8F", "#E76F51", "#4A4E69", "#606C38", "#9B2226", "#023047",
    "#5F0F40", "#0B6E4F", "#3D348B", "#BC6C25",
]


def color_para_indice(i: int) -> str:
    return _PALETA_COLORES[i % len(_PALETA_COLORES)]


def random_nation() -> str:
    return "Argentina" if random.random() < 0.6 else random.choice(NATION_LIST[1:])


def random_name(nation: str) -> str:
    pool = NATIONS.get(nation, NATIONS["Argentina"])
    return f"{random.choice(pool['first'])} {random.choice(pool['last'])}"


# Posición específica dentro de la posición amplia (POR/DEF/MED/DEL). Es
# solo para tácticas/formación — el resto del juego (mercado, promedios,
# motor de partido) sigue funcionando con la posición amplia sin cambios,
# porque los atributos (ataque/defensa/pase/físico) no distinguen entre,
# por ejemplo, un DFI y un DFC.
POSICIONES_ESPECIFICAS = {
    "POR": ["POR"],
    "DEF": ["DFC", "DFI", "DFD"],
    "MED": ["MCD", "MC", "MCO", "MI", "MD"],
    "DEL": ["EI", "ED", "DC", "MP"],
}


def random_posicion_especifica(pos: str) -> str:
    opciones = POSICIONES_ESPECIFICAS.get(pos, [pos])
    return random.choice(opciones)


def gen_attributes(pos: str) -> dict:
    if pos == "POR":
        ata, de, pa, fi = random.randint(15, 35), random.randint(55, 90), random.randint(35, 65), random.randint(50, 85)
    elif pos == "DEF":
        ata, de, pa, fi = random.randint(20, 50), random.randint(55, 90), random.randint(35, 65), random.randint(55, 85)
    elif pos == "MED":
        ata, de, pa, fi = random.randint(40, 75), random.randint(35, 70), random.randint(55, 90), random.randint(50, 80)
    else:
        ata, de, pa, fi = random.randint(55, 90), random.randint(15, 45), random.randint(35, 70), random.randint(50, 85)
    return {"ataque": ata, "defensa": de, "pase": pa, "fisico": fi}


def _escalar_attrs(attrs: dict, factor: float) -> dict:
    return {k: max(15, min(99, round(v * factor))) for k, v in attrs.items()}


def _valor_mercado_real(overall: int, edad: int, potencial: int | None = None) -> int:
    """Curva de valor de pase en dólares reales, calibrada contra el rango
    real de precios de mercado: un top mundial en su pico (~90+ overall)
    debe rondar los USD 150-220M, no unos pocos millones.

    A diferencia de la versión anterior, ser joven es una PRIMA (más años
    de carrera y reventa por delante), no un descuento — así es como
    cotizan de verdad los juveniles de elite. Si además todavía le falta
    desarrollo hasta su potencial, se suma una prima extra por proyección
    futura (la razón por la que una promesa de 19 años ya vale decenas o
    cientos de millones aunque su rendimiento actual sea menor al de un
    titular consagrado)."""
    base = 200_000 * (1.179 ** (overall - 50))

    if edad <= 21:
        edad_factor = 1.15
    elif edad <= 29:
        edad_factor = 1.0
    elif edad <= 30:
        edad_factor = 0.85
    elif edad <= 33:
        edad_factor = max(0.35, 0.85 - 0.15 * (edad - 30))
    else:
        edad_factor = max(0.12, 0.40 - 0.08 * (edad - 33))

    premio_potencial = 1.0
    if potencial is not None and edad <= 23:
        margen = max(0, potencial - overall)
        premio_potencial = 1.0 + min(3.5, margen * 0.09)

    valor = base * edad_factor * premio_potencial
    return max(50_000, round(valor / 1000) * 1000)


def _margen_potencial_por_edad(edad: int) -> int:
    """Cuánto margen de crecimiento sobre el overall actual es razonable
    esperar según la edad: a los 17 queda toda la carrera por delante, a
    los 32+ ya no queda casi nada."""
    if edad <= 18:
        return 25
    if edad <= 21:
        return 18
    if edad <= 24:
        return 12
    if edad <= 28:
        return 6
    if edad <= 31:
        return 2
    return 0


def _generar_potencial(base: int, edad: int = 24) -> int:
    """Techo de desarrollo del jugador. Deliberadamente escaso en el tramo
    alto, como en la vida real: la inmensa mayoría tiene un margen modesto
    sobre su nivel actual, un grupo (~15%) llega a nivel top de liga
    europea (80-90), y solo un puñado de jugadores en todo el juego son
    promesas mundiales por encima de 90 — con techo absoluto 94, nadie
    llega a 99. Los roles de "promesa"/"mundial" solo pueden salir en
    jugadores con carrera por delante (<=23 años); a partir de ahí (y
    también en el caso general) el margen normal está acotado por la edad
    — un veterano de 32+ ya está en su techo, no tiene margen."""
    roll = random.random()
    if edad <= 23 and roll < 0.005:
        techo = random.randint(91, 94)
    elif edad <= 23 and roll < 0.15:
        techo = random.randint(80, 90)
    else:
        techo = base + random.randint(0, _margen_potencial_por_edad(edad))
    return max(base, min(94, techo))


def gen_player_dict(pos: str, nation: str | None = None, name: str | None = None, factor: float = 1.0) -> dict:
    nation = nation or random_nation()
    attrs = _escalar_attrs(gen_attributes(pos), factor)
    edad = random.randint(17, 35)
    overall = _overall({**attrs, "posicion": pos})
    potencial = _generar_potencial(overall, edad)
    valor_mercado = _valor_mercado_real(overall, edad, potencial)
    return {
        "nombre": name or random_name(nation),
        "posicion": pos,
        "posicion_especifica": random_posicion_especifica(pos),
        "nacionalidad": nation,
        "edad": edad,
        **attrs,
        "potencial": potencial,
        "energia": 100,
        "moral": random.randint(65, 85),
        "valor_mercado": valor_mercado,
        # salario semanal real: entre ~0.15% y ~0.4% del valor de pase por semana
        "salario": max(400, round(valor_mercado * random.uniform(0.0015, 0.004) / 100) * 100),
    }


def gen_player_real(datos: dict) -> dict:
    """Arma el dict de un jugador a partir de datos reales provistos por un
    tercero (ver PaqueteClubes.jugadores_json) — nombre/posición/nacionalidad/
    edad/atributos base se usan tal cual (no se escalan por `factor`, a
    diferencia de gen_player_dict: son datos reales, no se inventan).
    overall/potencial/valor/salario se calculan con las MISMAS fórmulas que
    el resto del juego."""
    pos = datos["posicion"]
    attrs = {
        "ataque": int(datos["ataque"]), "defensa": int(datos["defensa"]),
        "pase": int(datos["pase"]), "fisico": int(datos["fisico"]),
    }
    edad = int(datos["edad"])
    overall = _overall({**attrs, "posicion": pos})
    potencial = _generar_potencial(overall, edad)
    valor_mercado = _valor_mercado_real(overall, edad, potencial)
    return {
        "nombre": datos["nombre"],
        "posicion": pos,
        "posicion_especifica": datos.get("posicion_especifica") or random_posicion_especifica(pos),
        "nacionalidad": datos.get("nacionalidad") or random_nation(),
        "edad": edad,
        **attrs,
        "potencial": potencial,
        "energia": 100,
        "moral": random.randint(65, 85),
        "valor_mercado": valor_mercado,
        "salario": max(400, round(valor_mercado * random.uniform(0.0015, 0.004) / 100) * 100),
    }


def gen_squad(n_por=3, n_def=9, n_med=8, n_del=5, factor: float = 1.0) -> list[dict]:
    """Plantel de 25 jugadores (default): POR 3, DEF 9, MED 8, DEL 5.

    Alcanza para clasificar_plantel() en 11 titulares / 9 suplentes / 5
    reservas siguiendo un 4-4-2 base (1-4-4-2 titular). `factor` escala los
    atributos según liga/nivel del club (ver factor_overall_liga).
    """
    squad = []
    for _ in range(n_por):
        squad.append(gen_player_dict("POR", factor=factor))
    for _ in range(n_def):
        squad.append(gen_player_dict("DEF", factor=factor))
    for _ in range(n_med):
        squad.append(gen_player_dict("MED", factor=factor))
    for _ in range(n_del):
        squad.append(gen_player_dict("DEL", factor=factor))
    return squad


def gen_squad_mixto(jugadores_reales: list[dict], factor: float, n_por=3, n_def=9, n_med=8, n_del=5) -> list[dict]:
    """Plantel de un club con datos reales (editor de datos): arranca con
    `jugadores_reales` (ya armados por gen_player_real) y completa lo que
    falte de la composición estándar (POR/DEF/MED/DEL) con generación
    ficticia normal — igual que gen_squad, pero descontando las posiciones
    ya cubiertas por jugadores reales."""
    objetivo = {"POR": n_por, "DEF": n_def, "MED": n_med, "DEL": n_del}
    for j in jugadores_reales:
        objetivo[j["posicion"]] = max(0, objetivo.get(j["posicion"], 0) - 1)

    squad = list(jugadores_reales)
    for pos, cantidad in objetivo.items():
        for _ in range(cantidad):
            squad.append(gen_player_dict(pos, factor=factor))
    return squad


def _overall(p: dict) -> int:
    pos = p["posicion"]
    if pos == "POR":
        valor = p["defensa"] * 0.6 + p["fisico"] * 0.2 + p["pase"] * 0.2
    elif pos == "DEF":
        valor = p["defensa"] * 0.5 + p["fisico"] * 0.25 + p["pase"] * 0.25
    elif pos == "MED":
        valor = p["pase"] * 0.4 + p["ataque"] * 0.25 + p["defensa"] * 0.2 + p["fisico"] * 0.15
    else:
        valor = p["ataque"] * 0.55 + p["fisico"] * 0.25 + p["pase"] * 0.2
    # Mismo techo absoluto que Jugador.overall en models.py: nadie supera
    # 94 de overall, aunque los 4 atributos individuales puedan llegar a 99.
    return min(94, round(valor))


# Cantidad de titulares/suplentes/reservas por posición para un plantel de
# 25 (POR 3, DEF 9, MED 8, DEL 5) siguiendo el 4-4-2 base de Tactica.
_FRANJAS_ROL = {
    "POR": {"TITULAR": 1, "SUPLENTE": 1, "RESERVA": 1},
    "DEF": {"TITULAR": 4, "SUPLENTE": 3, "RESERVA": 2},
    "MED": {"TITULAR": 4, "SUPLENTE": 3, "RESERVA": 1},
    "DEL": {"TITULAR": 2, "SUPLENTE": 2, "RESERVA": 1},
}


def clasificar_plantel(jugadores: list[dict]) -> None:
    """Asigna in-place `rol` (TITULAR/SUPLENTE/RESERVA) a cada jugador del
    plantel, tomando los mejores `overall` de cada posición como titulares,
    los siguientes como suplentes y el resto como reservas.
    """
    por_posicion: dict[str, list[dict]] = {"POR": [], "DEF": [], "MED": [], "DEL": []}
    for j in jugadores:
        por_posicion.setdefault(j["posicion"], []).append(j)

    for pos, grupo in por_posicion.items():
        grupo.sort(key=_overall, reverse=True)
        franjas = _FRANJAS_ROL.get(pos, {"TITULAR": 0, "SUPLENTE": 0, "RESERVA": len(grupo)})
        i = 0
        for rol, cantidad in franjas.items():
            for j in grupo[i:i + cantidad]:
                j["rol"] = rol
            i += cantidad
        for j in grupo[i:]:
            j["rol"] = "RESERVA"
