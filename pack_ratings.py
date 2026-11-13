"""OVR v1: rating del proveedor, o mediana de referencias de mercado similares.

No convierte precio en habilidad mediante una equivalencia fija. Usa únicamente
referencias del snapshot del pack; las estimaciones conservan sus IDs y método.
"""
import math
from statistics import median

VERSION = 'referencias-v1'
CAMPOS = ('ataque', 'defensa', 'pase', 'fisico')
PESOS = {'POR': (0, .6, .2, .2), 'DEF': (0, .5, .25, .25),
         'MED': (.25, .2, .4, .15), 'DEL': (.55, 0, .2, .25)}


def numero(value, low, high):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and low <= value <= high


def overall(player):
    return min(94, round(sum(player[k] * w for k, w in zip(CAMPOS, PESOS[player['posicion']]))))


def calibrar_planteles(planteles):
    players = [p for clubs in planteles.values() for squad in clubs.values() for p in squad]
    refs = [p for p in players if numero(p.get('datos_fuente', {}).get('rating'), 40, 99)
            and numero(p['datos_fuente'].get('market_value_eur'), 1, 2_000_000_000)]
    counts = {'rating_proveedor': 0, 'mercado_comparables': 0, 'sin_referencia': 0}
    for p in players:
        source = p.get('datos_fuente') or {}
        rating, value = source.get('rating'), source.get('market_value_eur')
        info = {'version': VERSION, 'fuente': source.get('source'), 'market_value_eur': value}
        if numero(rating, 40, 99):
            target, method = min(94, round(rating)), 'rating_proveedor'
            info['rating_original'] = rating
        elif numero(value, 1, 2_000_000_000):
            # Misma posición; distancia logarítmica de precio y edad (no potencial).
            candidates = [r for r in refs if r['posicion'] == p['posicion']
                          and abs(math.log(r['datos_fuente']['market_value_eur'] / value)) <= math.log(4)
                          and abs(r['edad'] - p['edad']) <= 5]
            candidates.sort(key=lambda r: (abs(math.log(r['datos_fuente']['market_value_eur'] / value))
                                           + .12 * abs(r['edad'] - p['edad']), str(r['datos_fuente']['id'])))
            nearby = candidates[:15]
            if len(nearby) < 5:
                counts['sin_referencia'] += 1
                p['calibracion_ovr'] = {**info, 'metodo': 'sin_referencia', 'ovr_objetivo': overall(p)}
                continue
            target, method = min(94, round(median(r['datos_fuente']['rating'] for r in nearby))), 'mercado_comparables'
            info['referencias'] = [r['datos_fuente']['id'] for r in nearby]
            info['rango_referencias'] = [min(r['datos_fuente']['rating'] for r in nearby), max(r['datos_fuente']['rating'] for r in nearby)]
        else:
            counts['sin_referencia'] += 1
            p['calibracion_ovr'] = {**info, 'metodo': 'sin_referencia', 'ovr_objetivo': overall(p)}
            continue
        # Perfil de posición explícitamente estimado; no reutilizar el azar previo.
        offsets = {'POR': (-45, 3, -5, -4), 'DEF': (-22, 4, -3, -5),
                   'MED': (-2, -9, 6, -1), 'DEL': (5, -30, -8, -5)}[p['posicion']]
        options = [{k: max(1, min(99, target + off + shift)) for k, off in zip(CAMPOS, offsets)} for shift in range(-15, 16)]
        attrs = min(options, key=lambda a: abs(overall({**a, 'posicion': p['posicion']}) - target))
        p.update(attrs)
        p['calibracion_ovr'] = {**info, 'metodo': method, 'ovr_objetivo': overall(p), 'atributos_estimados': True}
        counts[method] += 1
    return {'version': VERSION, 'referencias_disponibles': len(refs), **counts}


def atributos_calibrados(p):
    """Componentes coherentes: recalcular derivados no cambia el OVR importado."""
    a, d, pas, f = (int(p[k]) for k in CAMPOS)
    result = {k: a for k in ('finalizacion', 'regate', 'tiros_lejanos', 'centros')}
    result.update({k: d for k in ('marcaje', 'entradas', 'cabeceo', 'valentia', 'anticipacion')})
    result.update({k: pas for k in ('pase', 'primer_toque', 'vision', 'decisiones')})
    result.update({k: f for k in ('ritmo', 'aceleracion', 'resistencia', 'fuerza', 'agilidad')})
    result.update({k: round((pas + f) / 2) for k in ('agresividad', 'concentracion', 'compostura', 'liderazgo')})
    result.update(ataque=a, defensa=d, fisico=f, porteria=d if p['posicion'] == 'POR' else 10)
    return result
