"""Calibra un pack nativo, conservando assets y datos originales."""
import argparse
import json
import sys
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pack_ratings import calibrar_planteles


def convert(source, output):
    if source.resolve() == output.resolve():
        raise ValueError('Usá otro archivo de salida para conservar el original')
    with zipfile.ZipFile(source) as z:
        files = {n: z.read(n) for n in z.namelist()}
    players = json.loads(files['database/jugadores.json'])
    report = calibrar_planteles(players)
    config = json.loads(files.get('database/configuracion.json', b'{}'))
    config['calibracion_ovr'] = report
    manifest = json.loads(files['manifest.json'])
    manifest['version'] = '1.2.0'
    for key, obj in [('database/jugadores.json', players), ('database/configuracion.json', config), ('manifest.json', manifest)]:
        files[key] = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, data in files.items():
            z.writestr(n, data)
    print(json.dumps(report))
    for clubs in players.values():
        for squad in clubs.values():
            for p in squad:
                if p['nombre'] in ('Erling Haaland', 'Rodri', 'Kylian Mbappé'):
                    print(p['nombre'], p['calibracion_ovr']['ovr_objetivo'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    convert(args.source, args.output)
