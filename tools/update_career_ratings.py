"""Actualiza una carrera explícita; respalda campos afectados antes del commit.

Sin --apply solo informa. No modifica dinero, contratos, resultados ni otros saves.
"""
import argparse
import asyncio
import copy
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


async def run(args):
    from sqlalchemy import select, update
    from database import AsyncSessionLocal, engine
    from models import Partida, Jugador, PaqueteClubes
    from pack_ratings import VERSION, calibrar_planteles, atributos_calibrados
    async with AsyncSessionLocal() as db:
        career = await db.get(Partida, args.career)
        if not career or career.dataset != 'personalizada':
            raise ValueError('Se requiere una carrera personalizada existente')
        pack = await db.get(PaqueteClubes, career.id_paquete_clubes) if career.id_paquete_clubes else None
        players = (await db.scalars(select(Jugador).where(Jugador.id_partida == args.career).with_for_update())).all()
        originals = [(p, json.loads(p.datos_pack_json)) for p in players if p.datos_pack_json]
        rows = [copy.deepcopy(d) for _, d in originals]
        report = calibrar_planteles({'career': {'squad': rows}})
        backup = {'career': args.career, 'players': []}
        updates = []
        changed = 0
        for (player, old), new in zip(originals, rows):
            calibration = new['calibracion_ovr']
            if old.get('calibracion_ovr', {}).get('version') == VERSION or calibration['metodo'] == 'sin_referencia':
                continue
            baseline = atributos_calibrados(old)
            desired = atributos_calibrados(new)
            previous = {k: getattr(player, k) for k in desired}
            backup['players'].append({'id_jugador': player.id_jugador, **previous,
                                      'potencial': player.potencial, 'datos_pack_json': player.datos_pack_json})
            # Conservar progreso acumulado de cada atributo respecto a la base importada.
            # Los componentes iniciales tenían jitter: se conserva también esa diferencia.
            for key, value in desired.items():
                setattr(player, key, max(1, min(99, value + previous[key] - baseline[key])))
            player.potencial = max(player.potencial, player.overall)
            player.datos_pack_json = json.dumps(new, ensure_ascii=False)
            updates.append({'id_jugador': player.id_jugador,
                            **{k: getattr(player, k) for k in desired},
                            'potencial': player.potencial, 'datos_pack_json': player.datos_pack_json})
            db.expunge(player)
            changed += 1
        if pack and pack.jugadores_json:
            backup['pack'] = {'id_paquete': pack.id_paquete, 'jugadores_json': pack.jugadores_json,
                              'configuracion_json': pack.configuracion_json}
            squads = json.loads(pack.jugadores_json)
            pack_report = calibrar_planteles(squads)
            config = json.loads(pack.configuracion_json or '{}')
            config['calibracion_ovr'] = pack_report
            pack.jugadores_json = json.dumps(squads, ensure_ascii=False)
            pack.configuracion_json = json.dumps(config, ensure_ascii=False)
        print(json.dumps({'career': args.career, 'updated_players': changed, 'coverage': report}))
        if args.apply:
            args.backup_dir.mkdir(parents=True, exist_ok=True)
            path = args.backup_dir / f'ratings-career-{args.career}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.json'
            with path.open('x', encoding='utf-8') as f:
                json.dump(backup, f, ensure_ascii=False)
            if updates:
                await db.execute(update(Jugador), updates)
            await db.commit()
            print('Backup:', path)
        else:
            await db.rollback()
    await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--installation', type=Path, required=True)
    parser.add_argument('--career', type=int, required=True)
    parser.add_argument('--backup-dir', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(args.installation / '.env', override=True)
    os.chdir(args.installation)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    asyncio.run(run(args))
