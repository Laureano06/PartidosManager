"""
IA de los equipos rivales (no controlados por el usuario). Es el mismo
comportamiento que armamos en el prototipo web:

- Cada club de la IA detecta su posición más floja (menor overall promedio).
- Busca el mejor jugador disponible en esa posición, en cualquier club.
- Si el vendedor es otro club de la IA: la operación se resuelve sola.
- Si el vendedor es el club del usuario: se genera una OFERTA PENDIENTE
  que el usuario acepta o rechaza (no se le saca el jugador de prepo).
"""
import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Equipo, Jugador, OfertaFichaje, Mensaje, AfiliacionClub
from engine.transfer_engine import evaluar_oferta
from engine.contract_engine import salario_esperado
from engine.player_ai_engine import disposicion_fichar
from engine.data_gen import tope_salarial
from formato import money

POSICIONES = ["POR", "DEF", "MED", "DEL"]
PROB_INTENTO_POR_EQUIPO = 0.4


def _avg_overall(jugadores: list[Jugador], pos: str) -> float:
    grupo = [j for j in jugadores if j.posicion == pos]
    if not grupo:
        return 0.0
    return sum(j.overall for j in grupo) / len(grupo)


def _posicion_mas_debil(jugadores: list[Jugador]) -> str:
    return min(POSICIONES, key=lambda p: _avg_overall(jugadores, p))


async def ejecutar_ia_mercado(db: AsyncSession, log: list[str], fecha: date, id_partida: int) -> None:
    """Recorre todos los clubes que no son del usuario (de ESTA carrera) e
    intenta 1 fichaje cada uno con cierta probabilidad. Se llama después de
    simular cada jornada, igual que en el prototipo JS."""
    equipos = (await db.execute(select(Equipo).where(Equipo.id_partida == id_partida))).scalars().all()
    todos_jugadores = (await db.execute(
        select(Jugador).where(Jugador.id_partida == id_partida, Jugador.categoria == "PRIMERA")
    )).scalars().all()

    jugadores_por_equipo: dict[int, list[Jugador]] = {}
    for j in todos_jugadores:
        if j.id_equipo:
            jugadores_por_equipo.setdefault(j.id_equipo, []).append(j)

    clubes_influenciados = set((await db.execute(
        select(AfiliacionClub.id_equipo_participado).where(
            AfiliacionClub.id_partida == id_partida,
            AfiliacionClub.influencia_habilitada == True,  # noqa: E712
        )
    )).scalars().all())

    for equipo in equipos:
        if equipo.es_usuario:
            continue
        if equipo.id_equipo in clubes_influenciados:
            continue
        if random.random() > PROB_INTENTO_POR_EQUIPO:
            continue
        if equipo.presupuesto_fichajes < 200_000:
            continue

        plantilla = jugadores_por_equipo.get(equipo.id_equipo, [])
        if not plantilla:
            continue
        pos_debil = _posicion_mas_debil(plantilla)

        candidatos = []
        for otro in equipos:
            if otro.id_equipo == equipo.id_equipo:
                continue
            plantilla_otro = jugadores_por_equipo.get(otro.id_equipo, [])
            if len(plantilla_otro) <= 14:
                continue
            for j in plantilla_otro:
                if j.posicion == pos_debil:
                    candidatos.append((otro, j))

        if not candidatos:
            continue

        candidatos.sort(key=lambda t: t[1].overall, reverse=True)
        pool = candidatos[:4]
        vendedor, jugador = random.choice(pool)

        # Si el jugador no querría sumarse a este club (viene de uno mucho
        # mejor), la IA ni intenta — evita ofertas que no tendrían sentido
        # recibir del lado del jugador.
        if not disposicion_fichar(jugador.overall, jugador.edad, vendedor.reputacion, equipo.reputacion)["quiere"]:
            continue

        demanda = jugador.valor_mercado
        if demanda > equipo.presupuesto_fichajes * 1.15:
            continue

        oferta_monto = min(equipo.presupuesto_fichajes, round(demanda * random.randint(85, 105) / 100 / 10_000) * 10_000)

        if vendedor.es_usuario:
            ya_existe = any(
                o for o in (await db.execute(
                    select(OfertaFichaje).where(
                        OfertaFichaje.id_jugador == jugador.id_jugador,
                        OfertaFichaje.estado == "PENDIENTE",
                    )
                )).scalars().all()
            )
            if ya_existe:
                continue
            oferta = OfertaFichaje(
                id_jugador=jugador.id_jugador,
                id_equipo_comprador=equipo.id_equipo,
                id_equipo_vendedor=vendedor.id_equipo,
                monto_oferta=oferta_monto,
                salario_pactado=salario_esperado(jugador.valor_mercado, jugador.edad),
                estado="PENDIENTE",
            )
            db.add(oferta)
            await db.flush()  # asigna id_oferta
            db.add(Mensaje(
                id_equipo_destino=vendedor.id_equipo,
                remitente="Mercado de Pases",
                asunto=f"Oferta recibida por {jugador.nombre}",
                contenido=f"{equipo.nombre} ofrece ${money(oferta_monto)} por {jugador.nombre} ({pos_debil}). Podés aceptarla o rechazarla desde tu bandeja.",
                fecha=fecha,
                tipo="MERCADO",
                id_oferta=oferta.id_oferta,
            ))
            log.append(f"{equipo.nombre} ofertó ${money(oferta_monto)} por {jugador.nombre} (tu club) — pendiente de tu respuesta.")
        else:
            resultado = evaluar_oferta(oferta_monto, demanda, es_clave=(jugador.rol == "TITULAR"))
            if resultado["estado"] == "ACEPTADA" and equipo.presupuesto_fichajes >= oferta_monto:
                era_titular = jugador.rol == "TITULAR"
                equipo.presupuesto_fichajes -= oferta_monto
                vendedor.presupuesto_fichajes += oferta_monto
                equipo.presupuesto_salarios = tope_salarial(equipo.presupuesto_fichajes)
                vendedor.presupuesto_salarios = tope_salarial(vendedor.presupuesto_fichajes)
                jugador.id_equipo = equipo.id_equipo
                jugador.rol = "RESERVA"
                # Contrato nuevo con el club comprador, como en cualquier traspaso.
                jugador.salario = salario_esperado(jugador.valor_mercado, jugador.edad)
                jugador.fecha_fin_contrato = fecha + timedelta(days=365 * 3)
                if era_titular:
                    # El club vendedor se queda sin titular en esa posición:
                    # promovemos al mejor suplente/reserva que le quede, si tiene.
                    plantel_vendedor = jugadores_por_equipo.get(vendedor.id_equipo, [])
                    candidatos_reemplazo = [
                        c for c in plantel_vendedor
                        if c.posicion == pos_debil and c.rol in ("SUPLENTE", "RESERVA") and c.id_jugador != jugador.id_jugador
                    ]
                    if candidatos_reemplazo:
                        mejor = min(candidatos_reemplazo, key=lambda c: (c.rol != "SUPLENTE", -c.overall))
                        mejor.rol = "TITULAR"
                log.append(f"{equipo.nombre} fichó a {jugador.nombre} ({pos_debil}) de {vendedor.nombre} por ${money(oferta_monto)}.")
