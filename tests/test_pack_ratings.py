import copy
import unittest
from pack_ratings import calibrar_planteles, atributos_calibrados, overall
from engine.data_gen import gen_player_real, recalcular_derivados


def player(pid, rating=None, value=None, pos='DEL'):
    return dict(nombre=str(pid), edad=26, posicion=pos, ataque=50, defensa=50, pase=50, fisico=50,
                datos_fuente=dict(id=pid, rating=rating, market_value_eur=value))


class RatingTests(unittest.TestCase):
    def test_provider_and_engine_agree_for_each_position(self):
        for pos in ('POR', 'DEF', 'MED', 'DEL'):
            for rating in (45, 71, 90, 95):
                p = player(1, rating, 200_000_000, pos)
                calibrar_planteles({'L': {'C': [p]}})
                self.assertEqual(overall(p), min(94, rating))
                generated = gen_player_real(p)
                self.assertEqual(overall(generated), min(94, rating))
                self.assertEqual(overall({**recalcular_derivados(atributos_calibrados(p), pos), 'posicion': pos}), min(94, rating))

    def test_market_uses_comparable_median_and_is_idempotent(self):
        ps = [player(i, 80+i, 10_000_000) for i in range(5)] + [player(10, None, 10_000_000)]
        pack = {'L': {'C': ps}}
        report = calibrar_planteles(pack)
        self.assertEqual(overall(ps[-1]), 82)
        self.assertEqual(report['mercado_comparables'], 1)
        before = copy.deepcopy(pack)
        calibrar_planteles(pack)
        self.assertEqual(pack, before)

    def test_missing_and_invalid_values_do_not_invent_reference(self):
        for value in (None, 0, -1, '100m', True, float('nan')):
            p = player(1, None, value)
            report = calibrar_planteles({'L': {'C': [p]}})
            self.assertEqual(report['sin_referencia'], 1)
            self.assertEqual(p['ataque'], 50)


if __name__ == '__main__':
    unittest.main()
