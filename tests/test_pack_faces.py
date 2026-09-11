import json
import tempfile
import unittest
from pathlib import Path
from models import PaqueteClubes
from pack_engine import importar_pmpack, exportar_pmpack


class FaceTests(unittest.TestCase):
    def test_face_is_embedded_and_resolved_after_export_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = b'\x89PNG\r\n\x1a\nface-fixture'
            (root / 'face.png').write_bytes(content)
            player = dict(nombre='Jugador', posicion='DEL', edad=25, ataque=70, defensa=30,
                          pase=65, fisico=70, foto_url='/static/escudos/face.png')
            p = PaqueteClubes(nombre='Faces', version='1.0', pack_id='faces-test',
                             nombres_json=json.dumps({'ARG1': [['CLUB', 'Club']]}),
                             jugadores_json=json.dumps({'ARG1': {'CLUB': [player]}}))
            received = []
            def save(data, ext):
                received.append(data)
                return '/static/escudos/imported' + ext
            result = importar_pmpack(exportar_pmpack(p, root), save)
            self.assertIn(content, received)
            self.assertEqual(result['jugadores_clubes']['ARG1']['CLUB'][0]['foto_url'], '/static/escudos/imported.png')
