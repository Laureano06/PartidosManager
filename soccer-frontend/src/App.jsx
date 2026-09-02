import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

import Header from './components/Header';
import Sidebar from './components/Sidebar';
import LoadingOverlay from './components/LoadingOverlay';

import PanelPage from './pages/PanelPage';
import PlantelPage from './pages/PlantelPage';
import TacticasPage from './pages/TacticasPage';
import TransferenciasPage from './pages/TransferenciasPage';
import DirectivaPage from './pages/DirectivaPage';
import DecisionDTPage from './pages/DecisionDTPage';
import DbSelectorPage from './pages/DbSelectorPage';
import RoadmapPage from './pages/RoadmapPage';
import CrearCarreraPage from './pages/CrearCarreraPage';
import DesarrolloPage from './pages/DesarrolloPage';
import AcademiaPage from './pages/AcademiaPage';
import CuerpoTecnicoPage from './pages/CuerpoTecnicoPage';
import MulticlubPage from './pages/MulticlubPage';
import EconomiaPage from './pages/EconomiaPage';
import MercadoPage from './pages/MercadoPage';
import BuzonPage from './pages/BuzonPage';
import CalendarioPage from './pages/CalendarioPage';
import TablaPage from './pages/TablaPage';
import MatchDayPage from './pages/MatchDayPage';
import JugarPage from './pages/JugarPage';

const API_URL = "http://127.0.0.1:8000";
const INICIO_TEMPORADA = new Date(2027, 1, 1); // debe coincidir con seed.py: INICIO_TEMPORADA

// Componente con las Rutas y la Interfaz del Juego
function GameLayout({
  fechaActualDate, diaNumero, avanzarDia, esDiaDePartido, presupuesto, nombreClubUsuario, escudoClubUsuario, confianzaDirectiva,
  plantilla, setPlantilla, idEquipoUsuario, idPartida, fechaActualISO, onPartidoJugado, refrescarEquipo, cargarPlantilla,
  simularHasta, resultadoSimulacion, cambiarDeCarrera, volverAlInicio, onEstadoCambiado,
}) {
  return (
    <div className="h-screen bg-[#0b1326] text-slate-100 flex flex-col font-sans overflow-hidden">
      <Header
        fechaActual={fechaActualDate}
        diaNumero={diaNumero}
        avanzarDia={avanzarDia}
        esDiaDePartido={esDiaDePartido}
        simularHasta={simularHasta}
        resultadoSimulacion={resultadoSimulacion}
      />

      <div className="flex flex-1 min-h-0">
        <Sidebar
          presupuesto={presupuesto}
          nombreClub={nombreClubUsuario}
          escudoUrl={escudoClubUsuario}
          confianzaDirectiva={confianzaDirectiva}
          cambiarDeCarrera={cambiarDeCarrera}
          volverAlInicio={volverAlInicio}
        />

        <main className="flex-1 p-6 overflow-y-auto scroll-slide min-h-0">
          <Routes>
            <Route path="/" element={<Navigate to="/panel" replace />} />
            <Route path="/panel" element={<PanelPage API_URL={API_URL} idEquipoUsuario={idEquipoUsuario} idPartida={idPartida} fechaActual={fechaActualISO} />} />
            <Route path="/partido" element={<MatchDayPage API_URL={API_URL} idPartida={idPartida} idEquipoUsuario={idEquipoUsuario} fechaActual={fechaActualISO} plantilla={plantilla} setPlantilla={setPlantilla} onPartidoJugado={onPartidoJugado} />} />
            <Route path="/buzon" element={<BuzonPage API_URL={API_URL} idEquipoUsuario={idEquipoUsuario} />} />
            <Route path="/calendario" element={<CalendarioPage API_URL={API_URL} idEquipoUsuario={idEquipoUsuario} fechaActual={fechaActualISO} />} />
            <Route path="/tabla" element={<TablaPage API_URL={API_URL} idPartida={idPartida} />} />
            <Route path="/equipo" element={<PlantelPage plantilla={plantilla} setPlantilla={setPlantilla} API_URL={API_URL} idEquipoUsuario={idEquipoUsuario} idPartida={idPartida} />} />
            <Route path="/tacticas" element={<TacticasPage plantilla={plantilla} setPlantilla={setPlantilla} API_URL={API_URL} idEquipoUsuario={idEquipoUsuario} />} />
            <Route path="/transferencias" element={<TransferenciasPage API_URL={API_URL} idEquipoUsuario={idEquipoUsuario} idPartida={idPartida} onPresupuestoCambiado={refrescarEquipo} onPlantillaCambiada={cargarPlantilla} />} />
            <Route path="/mercado" element={<MercadoPage API_URL={API_URL} idEquipoUsuario={idEquipoUsuario} idPartida={idPartida} plantilla={plantilla} setPlantilla={setPlantilla} onPresupuestoCambiado={refrescarEquipo} onPlantillaCambiada={cargarPlantilla} />} />
            <Route path="/desarrollo" element={<DesarrolloPage API_URL={API_URL} idEquipoUsuario={idEquipoUsuario} />} />
            <Route path="/academia" element={<AcademiaPage API_URL={API_URL} idEquipoUsuario={idEquipoUsuario} idPartida={idPartida} />} />
            <Route path="/cuerpo-tecnico" element={<CuerpoTecnicoPage API_URL={API_URL} idEquipoUsuario={idEquipoUsuario} />} />
            <Route path="/multiclub" element={<MulticlubPage API_URL={API_URL} idEquipoUsuario={idEquipoUsuario} />} />
            <Route path="/economia" element={<EconomiaPage API_URL={API_URL} idEquipoUsuario={idEquipoUsuario} />} />
            <Route path="/directiva" element={<DirectivaPage API_URL={API_URL} idPartida={idPartida} onEstadoCambiado={onEstadoCambiado} />} />
            <Route path="/jugar" element={<JugarPage />} />
            <Route path="*" element={<Navigate to="/panel" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  const [dataset, setDataset] = useState(() => localStorage.getItem('dataset_seleccionado') || null);
  const [idPartida, setIdPartida] = useState(() => {
    const guardado = localStorage.getItem('id_partida');
    return guardado ? Number(guardado) : null;
  });
  const [vista, setVista] = useState('roadmap'); // 'roadmap' | 'crear' -- solo importa cuando hay dataset pero no partida

  const [directiva, setDirectiva] = useState(null); // {estado_dt, ofertas} — null hasta el primer fetch

  const [idEquipoUsuario, setIdEquipoUsuario] = useState(null);
  const [nombreClubUsuario, setNombreClubUsuario] = useState('');
  const [escudoClubUsuario, setEscudoClubUsuario] = useState(null);
  const [presupuesto, setPresupuesto] = useState(0);
  const [plantilla, setPlantilla] = useState([]);
  const [fechaActualISO, setFechaActualISO] = useState(null);
  const [proximoPartidoFecha, setProximoPartidoFecha] = useState(null);
  const [avanzandoDia, setAvanzandoDia] = useState(false);
  const [simulandoHasta, setSimulandoHasta] = useState(false);
  const [resultadoSimulacion, setResultadoSimulacion] = useState(null);

  useEffect(() => {
    document.title = "PARTIDOS Manager";
    let link = document.querySelector("link[rel*='icon']");
    if (!link) {
      link = document.createElement('link');
      link.rel = 'shortcut icon';
      document.getElementsByTagName('head')[0].appendChild(link);
    }
    link.type = 'image/png';
    link.href = '/iconoPARTIDOS.png';
  }, []);

  const seleccionarDataset = (ds) => {
    localStorage.setItem('dataset_seleccionado', ds);
    setDataset(ds);
    setVista('roadmap');
  };

  const seleccionarPartida = (id) => {
    localStorage.setItem('id_partida', String(id));
    setIdPartida(id);
  };

  const cambiarDeCarrera = () => {
    localStorage.removeItem('id_partida');
    setIdPartida(null);
    setIdEquipoUsuario(null);
    setFechaActualISO(null);
    setVista('roadmap');
  };

  // A diferencia de cambiarDeCarrera, esto también suelta el dataset
  // elegido (ficticia/personalizada) y vuelve a la pantalla inicial del
  // juego, no solo a la hoja de ruta de carreras.
  const volverAlInicio = () => {
    localStorage.removeItem('id_partida');
    localStorage.removeItem('dataset_seleccionado');
    setIdPartida(null);
    setIdEquipoUsuario(null);
    setFechaActualISO(null);
    setVista('roadmap');
    setDataset(null);
  };

  // Encontrar el equipo del usuario (es_usuario=true) de esta carrera, una sola vez.
  // Si la partida guardada en localStorage ya no existe (por ej. se borró desde
  // otra pestaña/sesión), el fetch vuelve vacío: sin esto, el juego se queda
  // trabado para siempre en "Cargando tu club desde el servidor..." — en vez
  // de eso, se limpia la partida stale y se vuelve a la hoja de ruta.
  const cargarEquipoUsuario = useCallback(() => {
    if (!idPartida) return;
    fetch(`${API_URL}/equipos?id_partida=${idPartida}`)
      .then((r) => r.json())
      .then((equipos) => {
        const propio = equipos.find((e) => e.es_usuario);
        if (propio) {
          setIdEquipoUsuario(propio.id_equipo);
          setNombreClubUsuario(propio.nombre);
          setEscudoClubUsuario(propio.escudo_url || null);
          setPresupuesto(propio.presupuesto_fichajes);
        } else {
          cambiarDeCarrera();
        }
      })
      .catch((error) => console.error('Error obteniendo el equipo del usuario:', error));
  }, [idPartida]);

  useEffect(() => { cargarEquipoUsuario(); }, [cargarEquipoUsuario]);

  // Directiva: se refresca al cargar, y de nuevo cada vez que avanzar el día
  // (o simular varios) puede haber cruzado un fin de temporada — si
  // estado_dt deja de ser NORMAL, se bloquea el juego con DecisionDTPage.
  const cargarDirectiva = useCallback(() => {
    if (!idPartida) return;
    fetch(`${API_URL}/partidas/${idPartida}/directiva`)
      .then((r) => r.json())
      .then(setDirectiva)
      .catch((error) => console.error('Error obteniendo la situación de Directiva:', error));
  }, [idPartida]);

  useEffect(() => { cargarDirectiva(); }, [cargarDirectiva]);

  const onDecisionResuelta = useCallback(() => {
    cargarEquipoUsuario(); // el club puede haber cambiado
    cargarDirectiva();
  }, [cargarEquipoUsuario, cargarDirectiva]);

  const refrescarEquipo = useCallback(() => {
    if (!idEquipoUsuario || !idPartida) return;
    fetch(`${API_URL}/equipos?id_partida=${idPartida}`)
      .then((r) => r.json())
      .then((equipos) => {
        const propio = equipos.find((e) => e.id_equipo === idEquipoUsuario);
        if (propio) setPresupuesto(propio.presupuesto_fichajes);
      })
      .catch(() => {});
  }, [idEquipoUsuario, idPartida]);

  const cargarPlantilla = useCallback(() => {
    if (!idEquipoUsuario) return;
    fetch(`${API_URL}/equipos/${idEquipoUsuario}/jugadores`)
      .then((r) => r.json())
      .then(setPlantilla)
      .catch((error) => console.error('Error cargando la plantilla:', error));
  }, [idEquipoUsuario]);

  const cargarProximoPartido = useCallback(() => {
    if (!idEquipoUsuario) return;
    fetch(`${API_URL}/calendario/equipo/${idEquipoUsuario}`)
      .then((r) => r.json())
      .then((data) => {
        const pendiente = data.partidos.find((p) => !p.jugado);
        setProximoPartidoFecha(pendiente ? pendiente.fecha : null);
      })
      .catch((error) => console.error('Error cargando el calendario:', error));
  }, [idEquipoUsuario]);

  useEffect(() => {
    if (!idEquipoUsuario || !idPartida) return;
    cargarPlantilla();
    cargarProximoPartido();
    fetch(`${API_URL}/juego/estado?id_partida=${idPartida}`)
      .then((r) => r.json())
      .then((data) => setFechaActualISO(data.fecha_actual))
      .catch((error) => console.error('Error obteniendo la fecha del juego:', error));
  }, [idEquipoUsuario, idPartida, cargarPlantilla, cargarProximoPartido]);

  // "Atrasado" incluye tanto el partido de hoy como uno que quedó de una
  // fecha anterior sin jugarse (por ej. si se avanzó el día por afuera de
  // la UI) — en ambos casos hay que jugarlo antes de poder continuar,
  // igual que ahora exige el backend.
  const partidoAtrasado = !!proximoPartidoFecha && fechaActualISO && proximoPartidoFecha <= fechaActualISO;
  const esDiaDePartido = partidoAtrasado;

  const onPartidoJugado = useCallback(() => {
    cargarProximoPartido();
    refrescarEquipo();
    cargarPlantilla();
  }, [cargarProximoPartido, refrescarEquipo, cargarPlantilla]);

  const avanzarDia = async () => {
    if (esDiaDePartido) return;
    setAvanzandoDia(true);
    try {
      const res = await fetch(`${API_URL}/juego/avanzar-dia?id_partida=${idPartida}`, { method: 'POST' });
      if (!res.ok) {
        // El backend rechazó el avance (partido pendiente que la UI no
        // tenía sincronizado) — resincronizamos en vez de quedar pegados.
        cargarProximoPartido();
        return;
      }
      const data = await res.json();
      setFechaActualISO(data.fecha_actual);
      refrescarEquipo();
      cargarPlantilla(); // si se efectivizó una compra/venta al abrir la ventana, el plantel cambió
      cargarDirectiva(); // pudo haber cruzado un fin de temporada (despido/fin de contrato)
    } catch (error) {
      console.error('Error avanzando el día:', error);
    } finally {
      setAvanzandoDia(false);
    }
  };

  const simularHasta = async (fechaObjetivoISO) => {
    setSimulandoHasta(true);
    setResultadoSimulacion(null);
    try {
      const res = await fetch(`${API_URL}/juego/simular-hasta?id_partida=${idPartida}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fecha_objetivo: fechaObjetivoISO }),
      });
      const data = await res.json();
      if (!res.ok) {
        setResultadoSimulacion({ error: data.detail || 'No se pudo simular hasta esa fecha.' });
        return;
      }
      setFechaActualISO(data.fecha_actual);
      refrescarEquipo();
      cargarPlantilla();
      cargarProximoPartido();
      cargarDirectiva(); // pudo haber cruzado un fin de temporada (despido/fin de contrato)
      setResultadoSimulacion({
        fechaActual: data.fecha_actual,
        partidosJugados: data.partidos_jugados,
        nuevaTemporada: data.nueva_temporada,
      });
    } catch (error) {
      console.error('Error simulando hasta la fecha elegida:', error);
      setResultadoSimulacion({ error: 'Error de conexión con el servidor.' });
    } finally {
      setSimulandoHasta(false);
    }
  };

  const fechaActualDate = fechaActualISO ? new Date(`${fechaActualISO}T00:00:00`) : INICIO_TEMPORADA;
  const diaNumero = Math.max(1, Math.round((fechaActualDate - INICIO_TEMPORADA) / 86400000) + 1);

  let contenido;
  if (!dataset) {
    contenido = <DbSelectorPage onSelectDataset={seleccionarDataset} />;
  } else if (!idPartida) {
    contenido = vista === 'crear'
      ? <CrearCarreraPage API_URL={API_URL} dataset={dataset} onCarreraCreada={seleccionarPartida} onVolver={() => setVista('roadmap')} />
      : <RoadmapPage API_URL={API_URL} dataset={dataset} onContinuar={seleccionarPartida} onCrearNueva={() => setVista('crear')} onCambiarDataset={() => setDataset(null)} />;
  } else if (!idEquipoUsuario) {
    contenido = (
      <div className="min-h-screen bg-[#0b1326] text-slate-100 flex items-center justify-center text-sm">
        Cargando tu club desde el servidor...
      </div>
    );
  } else if (directiva && directiva.estado_dt !== 'NORMAL') {
    contenido = (
      <DecisionDTPage
        API_URL={API_URL}
        idPartida={idPartida}
        nombreClubActual={nombreClubUsuario}
        estadoDt={directiva.estado_dt}
        ofertas={directiva.ofertas}
        onResuelto={onDecisionResuelta}
      />
    );
  } else {
    contenido = (
      <GameLayout
        fechaActualDate={fechaActualDate}
        fechaActualISO={fechaActualISO}
        diaNumero={diaNumero}
        avanzarDia={avanzarDia}
        esDiaDePartido={esDiaDePartido}
        presupuesto={presupuesto}
        nombreClubUsuario={nombreClubUsuario}
        escudoClubUsuario={escudoClubUsuario}
        confianzaDirectiva={directiva ? directiva.confianza_directiva : 60}
        onEstadoCambiado={onDecisionResuelta}
        plantilla={plantilla}
        setPlantilla={setPlantilla}
        idEquipoUsuario={idEquipoUsuario}
        idPartida={idPartida}
        onPartidoJugado={onPartidoJugado}
        refrescarEquipo={refrescarEquipo}
        cargarPlantilla={cargarPlantilla}
        simularHasta={simularHasta}
        resultadoSimulacion={resultadoSimulacion}
        cambiarDeCarrera={cambiarDeCarrera}
        volverAlInicio={volverAlInicio}
      />
    );
  }

  return (
    <BrowserRouter>
      <LoadingOverlay show={avanzandoDia} mensaje="Avanzando el día..." />
      <LoadingOverlay show={simulandoHasta} mensaje="Simulando hasta la fecha elegida..." />
      {contenido}
    </BrowserRouter>
  );
}
