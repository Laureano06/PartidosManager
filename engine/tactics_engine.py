"""Motor táctico: calcula modificadores de ataque/defensa/desgaste según la
configuración del equipo (formación, mentalidad, presión)."""

FORMACIONES = {
    "4-4-2": (1.00, 1.00),
    "4-3-3": (1.12, 0.92),
    "4-2-3-1": (1.05, 1.05),
    "4-5-1": (0.90, 1.15),
    "3-5-2": (1.08, 0.95),
    "3-4-3": (1.20, 0.85),
    "5-4-1": (0.85, 1.20),
    "5-3-2": (0.88, 1.18),
}

MENTALIDADES = {
    "ULTRA_DEFENSIVA": (0.65, 1.40, 0.85, 1.00),
    "DEFENSIVA": (0.85, 1.20, 0.90, 1.00),
    "BALANCEADA": (1.00, 1.00, 1.00, 1.00),
    "OFENSIVA": (1.25, 0.80, 1.15, 1.00),
    "PRESION_ALTA": (1.35, 0.70, 1.40, 1.30),
}


def calcular_matriz_tactica(formacion: str, mentalidad: str, presion: str, energia_promedio: float = 100) -> dict:
    m_atq_f, m_def_f = FORMACIONES.get(formacion, (1.0, 1.0))
    m_atq_m, m_def_m, m_desgaste, m_tarjeta = MENTALIDADES.get(mentalidad, (1.0, 1.0, 1.0, 1.0))

    mod_ataque = m_atq_f * m_atq_m
    mod_defensa = m_def_f * m_def_m
    mod_desgaste = m_desgaste
    mod_tarjeta = m_tarjeta

    if presion == "ALTA":
        mod_desgaste *= 1.25
        mod_tarjeta *= 1.20
        mod_defensa *= 1.10
    elif presion == "BAJA":
        mod_desgaste *= 0.80
        mod_defensa *= 0.90

    if energia_promedio < 50:
        factor_fatiga = max(0.5, energia_promedio / 100)
        mod_ataque *= factor_fatiga
        mod_defensa *= factor_fatiga

    return {
        "mod_ataque": mod_ataque,
        "mod_defensa": mod_defensa,
        "mod_desgaste": mod_desgaste,
        "mod_tarjeta": mod_tarjeta,
    }
