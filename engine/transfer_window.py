"""Ventanas de mercado (mercatos) reales del fútbol mundial.

Mercado de verano: junio/julio a agosto/septiembre (acá: 1 jun - 30 sep).
Mercado de invierno: enero (1 ene - 31 ene).

Fuera de esas fechas la negociación sigue abierta (se puede acordar un
fichaje en cualquier momento), pero la incorporación real del jugador al
plantel se aplaza hasta que abra la próxima ventana.
"""
from datetime import date


def ventana_activa(fecha: date) -> str | None:
    if fecha.month == 1:
        return "INVIERNO"
    if 6 <= fecha.month <= 9:
        return "VERANO"
    return None


def proxima_apertura(fecha: date) -> date:
    """Fecha de inicio de la próxima ventana de mercado distinta a la
    actual (útil para el mensaje informativo cuando `fecha` NO está dentro
    de una ventana). Meses 1-5 -> 1 de junio de este año; meses 6-12 -> 1 de
    enero del año siguiente."""
    if fecha.month < 6:
        return date(fecha.year, 6, 1)
    return date(fecha.year + 1, 1, 1)
