"""Contrato del proveedor: fechas exactas y salario semanal en USD."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pack_market import EUR_USD, FX_DATE
from pack_ratings import numero


def contrato_importado(datos, fecha_actual):
    source = datos.get('datos_fuente') or {}
    result = {}
    info = {'version': 1, 'fuente': source.get('source'), 'fecha_origen': source.get('contract_until')}
    try:
        end = date.fromisoformat(str(source.get('contract_until')))
    except ValueError:
        info['fecha_estado'] = 'sin_dato'
    else:
        if end > fecha_actual:
            result['fecha_fin_contrato'] = end
            info['fecha_estado'] = 'proveedor'
        else:
            info['fecha_estado'] = 'vencido_en_fecha_del_juego'
    wage = source.get('wage_eur_annual')
    if numero(wage, 1, 1_000_000_000):
        result['salario'] = max(1, int((Decimal(str(wage)) * Decimal(EUR_USD) / 52).quantize(Decimal('1'), rounding=ROUND_HALF_UP)))
        info.update(salario_estado='proveedor', salario_origen_eur_anual=wage,
                    moneda='USD', periodo='semana', eur_usd=EUR_USD, fecha_cambio=FX_DATE)
    else:
        info['salario_estado'] = 'sin_dato'
    return result, info
