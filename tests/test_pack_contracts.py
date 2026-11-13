import unittest
from datetime import date
from pack_contracts import contrato_importado


class ContractTests(unittest.TestCase):
    def test_real_date_and_annual_to_weekly(self):
        fields, info = contrato_importado({'datos_fuente': {'contract_until': '2034-06-30', 'wage_eur_annual': 52_000}}, date(2027, 7, 1))
        self.assertEqual(fields, {'fecha_fin_contrato': date(2034, 6, 30), 'salario': 1162})
        self.assertEqual(info['periodo'], 'semana')

    def test_missing_or_expired_dates_are_not_invented(self):
        for value in (None, 'invalid', '2027-06-30', '2027-07-01'):
            fields, _ = contrato_importado({'datos_fuente': {'contract_until': value}}, date(2027, 7, 1))
            self.assertEqual(fields, {})

    def test_missing_or_invalid_wage_does_not_zero_salary(self):
        for value in (None, True, -1, 0, '100', float('nan')):
            fields, _ = contrato_importado({'datos_fuente': {'wage_eur_annual': value}}, date(2027, 7, 1))
            self.assertNotIn('salario', fields)
