"""Valores del snapshot del pack, convertidos a la moneda USD del juego."""
from decimal import Decimal, ROUND_HALF_UP
from pack_ratings import numero

# Referencia fija reproducible del snapshot; no es una cotización en vivo.
EUR_USD = '1.1622'
FX_DATE = '2026-09-04'
FX_SOURCE = 'https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.nl.html'


def valor_importado(datos, fallback):
    source = datos.get('datos_fuente') or {}
    eur = source.get('market_value_eur')
    if numero(eur, 1, 1_000_000_000):
        value = int((Decimal(str(eur)) * Decimal(EUR_USD)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        return value, {'metodo': 'proveedor', 'moneda': 'USD', 'valor_origen_eur': eur,
                       'eur_usd': EUR_USD, 'fecha_cambio': FX_DATE, 'fuente_cambio': FX_SOURCE,
                       'fuente_jugador': source.get('source')}
    return fallback, {'metodo': 'estimacion_ovr', 'moneda': 'USD'}
