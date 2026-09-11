"""Formato de moneda estilo argentino ($7.000.200, punto como separador de miles)."""


def money(n: int) -> str:
    return f"{n:,}".replace(",", ".")
