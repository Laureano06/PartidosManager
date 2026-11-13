"""Conversaciones del vestuario con efecto diario limitado y registro persistente."""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Literal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Jugador, Equipo, Partida, Conversacion

router = APIRouter(tags=['Conversaciones'])




class ConversacionIn(BaseModel):
    id_equipo: int
    tema: Literal['apoyar', 'exigir', 'descanso']


def reaccion(tema, moral, energia):
    if tema == 'apoyar':
        return ('Gracias por la confianza. Voy a intentar responder en la cancha.', 3 if moral < 70 else 1)
    if tema == 'descanso':
        return ('Me vendría bien bajar la carga. Gracias por escucharme.', 2) if energia < 70 else ('Me siento bien físicamente. Quiero seguir jugando.', -1)
    return ('Entiendo lo que esperás. Voy a dar un paso más.', 1) if moral >= 60 and energia >= 60 else ('Ya estoy haciendo un esfuerzo. Esa presión no me ayuda ahora.', -3)


@router.get('/jugadores/{id_jugador}/conversaciones')
async def historial_conversaciones(id_jugador: int, id_equipo: int, db: AsyncSession = Depends(get_db)):
    player = await db.get(Jugador, id_jugador)
    if not player or player.id_equipo != id_equipo:
        raise HTTPException(404, 'Jugador fuera del plantel')
    rows = (await db.scalars(select(Conversacion).where(Conversacion.id_jugador == id_jugador,
        Conversacion.id_equipo == id_equipo).order_by(Conversacion.id.desc()).limit(30))).all()
    return [{'tema': r.tema, 'frase': r.respuesta, 'fecha': r.fecha.isoformat(), 'delta_moral': r.delta_moral} for r in reversed(rows)]


@router.post('/jugadores/{id_jugador}/conversaciones')
async def conversar(id_jugador: int, datos: ConversacionIn, db: AsyncSession = Depends(get_db)):
    player = await db.scalar(select(Jugador).where(Jugador.id_jugador == id_jugador).with_for_update())
    if not player or player.id_equipo != datos.id_equipo:
        raise HTTPException(400, 'Las charlas de vestuario son para jugadores de tu plantel')
    equipo = await db.get(Equipo, datos.id_equipo)
    partida = await db.get(Partida, player.id_partida)
    if not equipo or not partida:
        raise HTTPException(404, 'Carrera no encontrada')
    previous = await db.scalar(select(Conversacion.id).where(Conversacion.id_jugador == id_jugador, Conversacion.fecha == partida.fecha_actual))
    if previous:
        raise HTTPException(409, 'Ya tuviste una charla con este jugador hoy. Podés volver a hablar mañana.')
    frase, delta = reaccion(datos.tema, player.moral, player.energia)
    old = player.moral
    player.moral = max(0, min(100, old + delta))
    delta = player.moral - old
    relacion_anterior = player.relacion_dt
    # Escuchar cuando hace falta mejora el vínculo; presionar a un jugador
    # agotado lo perjudica. Se acota para que una sola charla no lo defina todo.
    delta_relacion = {"apoyar": 3 if old < 70 else 1, "descanso": 2 if player.energia < 70 else -1,
                      "exigir": 1 if old >= 60 and player.energia >= 60 else -3}[datos.tema]
    player.relacion_dt = max(0, min(100, relacion_anterior + delta_relacion))
    db.add(Conversacion(id_jugador=id_jugador, id_equipo=datos.id_equipo, fecha=partida.fecha_actual,
        tema=datos.tema, respuesta=frase, delta_moral=delta))
    await db.commit()
    return {'tema': datos.tema, 'frase': frase, 'delta_moral': delta, 'moral': player.moral,
            'relacion_dt': player.relacion_dt, 'delta_relacion': player.relacion_dt - relacion_anterior,
            'fecha': partida.fecha_actual.isoformat()}
