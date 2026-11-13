"""Corrige valores de una carrera con respaldo previo y transacción única."""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


async def run(args):
    from sqlalchemy import select, update
    from database import AsyncSessionLocal, engine
    from models import Jugador, Partida
    from pack_market import valor_importado
    from pack_contracts import contrato_importado
    from engine.data_gen import _valor_mercado_real
    async with AsyncSessionLocal() as db:
        career = await db.get(Partida, args.career)
        if not career or career.dataset != 'personalizada':
            raise ValueError('Carrera personalizada inexistente')
        players = (await db.scalars(select(Jugador).where(Jugador.id_partida == args.career).with_for_update())).all()
        backup, updates, counts = [], [], {'proveedor': 0, 'estimacion_ovr': 0, 'fechas': 0, 'salarios': 0, 'fechas_vencidas': 0}
        for p in players:
            if not p.datos_pack_json:
                continue
            data = json.loads(p.datos_pack_json)
            if args.contracts:
                if data.get('contrato_importado', {}).get('version') == 1 or p.id_equipo_dueno or p.id_equipo_precontrato:
                    continue
                fields, info = contrato_importado(data, career.fecha_actual)
                counts['fechas'] += int('fecha_fin_contrato' in fields)
                counts['salarios'] += int('salario' in fields)
                counts['fechas_vencidas'] += int(info['fecha_estado'] == 'vencido_en_fecha_del_juego')
                backup.append({'id_jugador': p.id_jugador, 'fecha_fin_contrato': p.fecha_fin_contrato.isoformat() if p.fecha_fin_contrato else None,
                               'salario': p.salario, 'datos_pack_json': p.datos_pack_json})
                data['contrato_importado'] = info
                updates.append({'id_jugador': p.id_jugador,
                                'fecha_fin_contrato': fields.get('fecha_fin_contrato', p.fecha_fin_contrato),
                                'salario': fields.get('salario', p.salario), 'datos_pack_json': json.dumps(data, ensure_ascii=False)})
                continue
            if data.get('calibracion_valor', {}).get('version') == 1:
                continue
            fallback = _valor_mercado_real(p.overall, p.edad, p.potencial)
            value, info = valor_importado(data, fallback)
            counts[info['metodo']] += 1
            backup.append({'id_jugador': p.id_jugador, 'valor_mercado': p.valor_mercado, 'datos_pack_json': p.datos_pack_json})
            data['calibracion_valor'] = {**info, 'version': 1, 'valor_inicial_usd': value}
            updates.append({'id_jugador': p.id_jugador, 'valor_mercado': value, 'datos_pack_json': json.dumps(data, ensure_ascii=False)})
        print(json.dumps({'career': args.career, **counts}), flush=True)
        if args.apply:
            args.backup_dir.mkdir(parents=True, exist_ok=True)
            kind = 'contracts' if args.contracts else 'market'
            path = args.backup_dir / f'{kind}-career-{args.career}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.json'
            with path.open('x', encoding='utf-8') as f:
                json.dump(backup, f, ensure_ascii=False)
            if updates:
                await db.execute(update(Jugador), updates)
            await db.commit()
            print('Backup:', path, flush=True)
        else:
            await db.rollback()
    await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--installation', required=True, type=Path)
    parser.add_argument('--career', required=True, type=int)
    parser.add_argument('--backup-dir', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--contracts', action='store_true')
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(args.installation / '.env', override=True)
    os.chdir(args.installation)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    asyncio.run(run(args))
