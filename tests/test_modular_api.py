import json
import os
import unittest
from pathlib import Path
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
from main import app
from schemas import NegociarContratoTraspasoIn
from api.routers.conversaciones import conversar, ConversacionIn
from database import Base
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from models import Partida, Equipo, Jugador, Liga
from datetime import date
from fastapi import HTTPException
from unittest.mock import patch, AsyncMock


class RouteTests(unittest.TestCase):
    def test_all_original_routes_remain(self):
        spec = app.openapi()['paths']
        baseline = json.loads(Path(__file__).with_name('api_routes_baseline.json').read_text())
        for method, path, name in baseline:
            self.assertIn(method.lower(), spec[path], (method, path, name))

    def test_contract_terms_are_bounded(self):
        base = dict(id_jugador=1, id_equipo_comprador=2, monto_oferta=100, salario_ofrecido=10)
        self.assertEqual(NegociarContratoTraspasoIn(**base, anios=5).anios, 5)
        for kwargs in ({'anios': 0}, {'anios': 6}, {'clausula_rescision': -1}):
            with self.assertRaises(ValueError):
                NegociarContratoTraspasoIn(**base, **kwargs)


class ConversationTests(unittest.IsolatedAsyncioTestCase):
    async def test_effect_history_and_daily_limit(self):
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            carrera = Partida(nombre_dt='Test', dataset='personalizada', fecha_actual=date(2027,7,1))
            db.add(carrera); await db.flush()
            liga = Liga(id_partida=carrera.id_partida, codigo='ARG1', pais='Argentina', nombre='Liga')
            db.add(liga); await db.flush()
            team = Equipo(nombre='Club', id_partida=carrera.id_partida, id_liga=liga.id_liga)
            db.add(team); await db.flush()
            player = Jugador(nombre='Jugador', posicion='DEL', nacionalidad='Argentina', edad=25,
                             id_partida=carrera.id_partida, id_equipo=team.id_equipo, moral=50, energia=80)
            db.add(player); await db.commit()
            result = await conversar(player.id_jugador, ConversacionIn(id_equipo=team.id_equipo,tema='apoyar'), db)
            self.assertEqual(result['moral'], 53)
            with self.assertRaises(HTTPException) as caught:
                await conversar(player.id_jugador, ConversacionIn(id_equipo=team.id_equipo,tema='exigir'), db)
            self.assertEqual(caught.exception.status_code, 409)
            self.assertEqual(player.moral, 53)
            from models import HistorialNegociacion, OfertaFichaje
            from api.routers.transferencias import negociar_contrato_traspaso
            from sqlalchemy import select
            buyer = Equipo(nombre='Comprador', id_partida=carrera.id_partida, id_liga=liga.id_liga,
                           presupuesto_fichajes=10_000_000)
            db.add(buyer); await db.flush()
            datos = NegociarContratoTraspasoIn(id_jugador=player.id_jugador, id_equipo_comprador=buyer.id_equipo,
                       monto_oferta=100_000, salario_ofrecido=2_000, anios=5, clausula_rescision=500_000)
            denied = await negociar_contrato_traspaso(datos, db)
            self.assertEqual(denied['estado'], 'RECHAZADA')
            db.add(HistorialNegociacion(id_jugador=player.id_jugador, id_equipo=buyer.id_equipo,
                detalle_json=json.dumps({'estado': 'ACEPTADA_CLUB', 'monto_acordado': 100_000, 'id_vendedor': team.id_equipo})))
            await db.commit()
            with patch('api.routers.transferencias.disposicion_fichar', return_value={'quiere': True}), \
                 patch('api.routers.transferencias.evaluar_renovacion', return_value={'estado':'ACEPTADA'}), \
                 patch('api.routers.transferencias._margen_salarial_disponible', new=AsyncMock(return_value=100_000)), \
                 patch('api.routers.transferencias._efectivizar_ofertas_pendientes', new=AsyncMock()):
                result = await negociar_contrato_traspaso(datos, db)
            self.assertEqual(result['estado'], 'ACEPTADA')
            offer = await db.scalar(select(OfertaFichaje))
            self.assertEqual(json.loads(offer.condiciones_json), {'anios': 5, 'clausula_rescision': 500_000})
        await engine.dispose()
