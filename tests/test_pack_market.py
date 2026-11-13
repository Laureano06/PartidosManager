import unittest
from pack_market import valor_importado
from engine.data_gen import gen_player_real


class MarketTests(unittest.TestCase):
    def test_conversion(self):
        value, meta = valor_importado({'datos_fuente': {'market_value_eur': 240_000_000}}, 100)
        self.assertEqual(value, 278_928_000)
        self.assertEqual(meta['moneda'], 'USD')

    def test_missing_invalid_and_zero_keep_estimate(self):
        for v in (None, 0, -1, True, '100m', float('nan')):
            self.assertEqual(valor_importado({'datos_fuente': {'market_value_eur': v}}, 123)[0], 123)

    def test_new_career_uses_source(self):
        p = dict(nombre='Test', posicion='DEL', edad=26, ataque=90, defensa=30, pase=80, fisico=80,
                 datos_fuente={'market_value_eur': 100_000_000})
        self.assertEqual(gen_player_real(p)['valor_mercado'], 116_220_000)


if __name__ == '__main__':
    unittest.main()
