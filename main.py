"""Entrada ASGI: middleware y routers por dominio."""

from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from fastapi.staticfiles import StaticFiles

from api.runtime import lifespan, DIRECTORIO_STATIC
from api.routers import conversaciones

app = FastAPI(title="Partidos Soccer Manager API", version="1.0.0", lifespan=lifespan)
app.include_router(conversaciones.router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/static", StaticFiles(directory=DIRECTORIO_STATIC), name="static")


from api.routers import carreras

app.include_router(carreras.router)

from api.routers.carreras import subir_escudo, catalogo_clubes, listar_partidas, borrar_partida, crear_partida_endpoint

from api.routers import panel

app.include_router(panel.router)

from api.routers.panel import obtener_estado_juego, avanzar_dia, simular_hasta, get_inbox, marcar_leido, marcar_todo_leido

from api.routers import liga

app.include_router(liga.router)

from api.routers.liga import listar_ligas, obtener_tabla, ver_jornada, calendario_equipo

from api.routers import equipos

app.include_router(equipos.router)

from api.routers.equipos import listar_equipos, obtener_plantilla, obtener_jugador, dialogo_jugador, historial_jugador, cambiar_rol_jugador, cambiar_duty_jugador, marcar_transferible

from api.routers import torneos

app.include_router(torneos.router)

from api.routers.torneos import obtener_torneos

from api.routers import simulacion

app.include_router(simulacion.router)

from api.routers.simulacion import simular_partido, simular_primer_tiempo, simular_segundo_tiempo, charla_equipo, simular_jornada

from api.routers import tacticas

app.include_router(tacticas.router)

from api.routers.tacticas import obtener_tactica, configurar_tactica

from api.routers import entrenamiento

app.include_router(entrenamiento.router)

from api.routers.entrenamiento import configurar_entrenamiento, configurar_entrenamiento_individual

from api.routers import transferencias

app.include_router(transferencias.router)

from api.routers.transferencias import listar_mercado, ofertar_fichaje, negociar_contrato_traspaso, firmar_precontrato, fichar_libre, en_negociacion, ofertas_recibidas, responder_oferta, recomendaciones_fichaje, ofrecer_jugador, ceder_jugador

from api.routers import contratos

app.include_router(contratos.router)

from api.routers.contratos import obtener_contrato, renovar_contrato

from api.routers import desarrollo

app.include_router(desarrollo.router)

from api.routers.desarrollo import obtener_desarrollo

from api.routers import academia

app.include_router(academia.router)

from api.routers.academia import obtener_academia, mover_categoria_jugador, obtener_intake_academia, decidir_intake_academia, reclutar_juvenil

from api.routers import economia

app.include_router(economia.router)

from api.routers.economia import obtener_economia

from api.routers import multiclub

app.include_router(multiclub.router)

from api.routers.multiclub import obtener_multiclub, mercado_multiclub, cotizar_participacion, ofertar_participacion, retirar_solicitud_participacion, mover_jugador_afiliado, togglear_influencia

from api.routers import selecciones

app.include_router(selecciones.router)

from api.routers import cuerpo_tecnico

app.include_router(cuerpo_tecnico.router)

from api.routers.cuerpo_tecnico import asignar_capitan, obtener_cuerpo_tecnico, asignar_scouting, quitar_scouting

from api.routers import directiva

app.include_router(directiva.router)

from api.routers.directiva import obtener_directiva, renunciar_dt, elegir_destino_dt

from api.routers import data_packs

app.include_router(data_packs.router)

from api.routers.data_packs import listar_paquetes_clubes, obtener_paquete_clubes, crear_paquete_clubes, actualizar_paquete_clubes, actualizar_club_paquete, borrar_club_paquete, actualizar_jugador_paquete, borrar_jugador_paquete, duplicar_paquete_clubes, exportar_paquete_clubes, previsualizar_importar_pmpack, confirmar_importar_pmpack, borrar_paquete_clubes

from api.routers import admin

app.include_router(admin.router)

from api.routers.admin import seed_endpoint
