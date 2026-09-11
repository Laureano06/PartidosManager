import React, { useEffect, useState } from 'react';
import PlayerDetailModal from '../components/PlayerDetailModal';
import { CATEGORIA_LABEL } from '../utils/academia';

function BarraPotencial({ overall, potencial }) {
  const pct = potencial > 0 ? Math.min(100, Math.round((overall / potencial) * 100)) : 0;
  return (
    <div className="w-24 bg-slate-800 h-1.5 rounded-full overflow-hidden shrink-0">
      <div className={`h-full ${pct >= 85 ? 'bg-emerald-400' : pct >= 60 ? 'bg-sky-400' : 'bg-amber-400'}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function ConsejoDesarrollo({ jugador }) {
  const margen = jugador.margen_desarrollo;
  if (margen <= 0) return <span className="text-slate-400">Ya cerca de su techo de potencial.</span>;
  if (margen >= 15) return <span className="text-emerald-300">Podría llegar a ser un jugador de calidad, con mucho margen de mejora.</span>;
  if (margen >= 7) return <span className="text-sky-300">Tiene un potencial decente si sigue entrenando bien.</span>;
  return <span className="text-slate-400">Progresión limitada, pero puede sumar minutos.</span>;
}

function TablaJugadores({ jugadores, vacio, onSubirAPrimera, onVerJugador, mostrarCategoria }) {
  if (jugadores.length === 0) {
    return <p className="text-xs text-slate-400">{vacio}</p>;
  }
  return (
    <div className="overflow-x-auto">
    <table className="w-full text-left text-xs">
      <thead>
        <tr className="border-b border-slate-800 text-slate-400">
          <th className="p-2">Jugador</th>
          {mostrarCategoria && <th className="p-2">Categoría</th>}
          <th className="p-2">Pos</th>
          <th className="p-2">Edad</th>
          <th className="p-2">Ovr</th>
          <th className="p-2">Pot</th>
          <th className="p-2">Progreso</th>
          <th className="p-2">Consejo de desarrollo</th>
          {onSubirAPrimera && <th className="p-2"></th>}
        </tr>
      </thead>
      <tbody>
        {jugadores.map((j) => (
          <tr
            key={j.id_jugador}
            onClick={onVerJugador ? () => onVerJugador(j) : undefined}
            onKeyDown={onVerJugador ? (e) => { if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); onVerJugador(j); } } : undefined}
            role={onVerJugador ? 'button' : undefined}
            tabIndex={onVerJugador ? 0 : undefined}
            aria-label={onVerJugador ? `Ver ficha de ${j.nombre}` : undefined}
            className={`border-b border-slate-800/40 hover:bg-[#0b1326] focus-visible:outline focus-visible:outline-sky-500 ${onVerJugador ? 'cursor-pointer' : ''}`}
          >
            <td className="p-2 font-bold text-slate-200">{j.nombre}</td>
            {mostrarCategoria && (
              <td className="p-2">
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-800 text-sky-400">
                  {CATEGORIA_LABEL[j.categoria] || j.categoria}
                </span>
              </td>
            )}
            <td className="p-2 text-sky-400" title={j.posicion}>{j.posicion_especifica || j.posicion}</td>
            <td className="p-2 text-slate-300">{j.edad}</td>
            <td className="p-2 font-bold text-white">{j.overall}</td>
            <td className="p-2 font-bold text-amber-300">{j.potencial}</td>
            <td className="p-2"><BarraPotencial overall={j.overall} potencial={j.potencial} /></td>
            <td className="p-2 max-w-xs"><ConsejoDesarrollo jugador={j} /></td>
            {onSubirAPrimera && (
              <td className="p-2">
                {j.edad >= 15 ? (
                  <button
                    onClick={(e) => { e.stopPropagation(); onSubirAPrimera(j.id_jugador); }}
                    className="text-[10px] font-bold px-2 py-1 rounded bg-sky-500 hover:bg-sky-400 text-slate-950"
                  >
                    Subir a Primera
                  </button>
                ) : (
                  <span className="text-[10px] text-slate-400">Muy joven</span>
                )}
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}

function TablaCedidos({ jugadores, tipo = 'salida' }) {
  if (jugadores.length === 0) {
    return <p className="text-xs text-slate-400">No tenés jugadores cedidos a préstamo en este momento.</p>;
  }
  return (
    <div className="overflow-x-auto">
    <table className="w-full text-left text-xs">
      <thead>
        <tr className="border-b border-slate-800 text-slate-400">
          <th className="p-2">Jugador</th>
          <th className="p-2">Pos</th>
          <th className="p-2">Ovr</th>
          <th className="p-2">{tipo === 'salida' ? 'A préstamo en' : 'Cedido desde'}</th>
          <th className="p-2">Vuelve el</th>
          <th className="p-2">Opción de compra</th>
        </tr>
      </thead>
      <tbody>
        {jugadores.map((j) => (
          <tr key={j.id_jugador} className="border-b border-slate-800/40 hover:bg-[#0b1326]">
            <td className="p-2 font-bold text-slate-200">{j.nombre}</td>
            <td className="p-2 text-sky-400" title={j.posicion}>{j.posicion_especifica || j.posicion}</td>
            <td className="p-2 font-bold text-white">{j.overall}</td>
            <td className="p-2 text-slate-300">{tipo === 'salida' ? j.club_prestamista : j.club_dueno}</td>
            <td className="p-2 text-slate-400">{j.fin_cesion ? new Date(`${j.fin_cesion}T00:00:00`).toLocaleDateString('es-AR') : '—'}</td>
            <td className="p-2 text-amber-300">{j.opcion_compra ? `$${j.opcion_compra.toLocaleString('es-AR')}` : 'Sin opción'}</td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}

function TarjetaCategoria({ titulo, resumen, cantidad }) {
  return (
    <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-5 space-y-2">
      <h3 className="text-xs font-bold text-amber-400 uppercase tracking-wider">{titulo}</h3>
      <p className="text-lg font-black text-white">{cantidad} jugador{cantidad === 1 ? '' : 'es'}</p>
      <p className="text-xs text-slate-400 leading-relaxed">{resumen}</p>
    </div>
  );
}

const CATEGORIAS_TABLA = [
  { key: 'sub13', titulo: 'Sub-13' },
  { key: 'sub15', titulo: 'Sub-15' },
  { key: 'sub18', titulo: 'Sub-18' },
  { key: 'sub21', titulo: 'Sub-21' },
];

export default function DesarrolloPage({ API_URL, idEquipoUsuario }) {
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [jugadorDetalle, setJugadorDetalle] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!idEquipoUsuario) return;
    setCargando(true);
    fetch(`${API_URL}/equipos/${idEquipoUsuario}/desarrollo`)
      .then((r) => r.json())
      .then(setDatos)
      .catch((e) => console.error('Error cargando el centro de desarrollo:', e))
      .finally(() => setCargando(false));
  }, [API_URL, idEquipoUsuario]);

  if (cargando || !datos) {
    return <p className="text-xs text-slate-400">Cargando centro de desarrollo...</p>;
  }

  const subirAPrimera = async (idJugador) => {
    setError(null);
    try {
      const r = await fetch(`${API_URL}/jugadores/${idJugador}/categoria`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ categoria: 'PRIMERA' }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        setError(err.detail || 'No se pudo ascender al jugador.');
        return;
      }
      setDatos((prev) => {
        const sinJugador = (lista) => lista.filter((j) => j.id_jugador !== idJugador);
        return {
          ...prev,
          destacados_academia: sinJugador(prev.destacados_academia),
          sub13: { ...prev.sub13, jugadores: sinJugador(prev.sub13.jugadores) },
          sub15: { ...prev.sub15, jugadores: sinJugador(prev.sub15.jugadores) },
          sub18: { ...prev.sub18, jugadores: sinJugador(prev.sub18.jugadores) },
          sub21: { ...prev.sub21, jugadores: sinJugador(prev.sub21.jugadores) },
        };
      });
      setJugadorDetalle(null);
    } catch (e) {
      console.error('Error ascendiendo a Primera:', e);
      setError('No se pudo conectar con el servidor.');
    }
  };

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-rose-950/60 border border-rose-500/40 text-rose-300 rounded-xl p-3 text-xs flex items-center justify-between gap-3">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-rose-300 hover:text-rose-100 font-bold shrink-0">✕</button>
        </div>
      )}
      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-5">
        <p className="text-xs text-slate-400">INFORME DE:</p>
        <p className="text-sm font-bold text-white">Secretaría Técnica — Centro de Desarrollo de {datos.nombre_equipo}</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {CATEGORIAS_TABLA.map(({ key, titulo }) => (
          <TarjetaCategoria key={key} titulo={`Plantilla ${titulo}`} resumen={datos[key].resumen} cantidad={datos[key].jugadores.length} />
        ))}
      </div>

      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
        <h2 className="text-sm font-bold text-white mb-1">Destacados de la Academia</h2>
        <p className="text-[11px] text-slate-400 mb-4">Los mejores prospectos de toda la cantera, sin importar la categoría — lo primero que conviene mirar.</p>
        <TablaJugadores
          jugadores={datos.destacados_academia}
          vacio="Todavía no hay prospectos destacados en la Academia."
          onVerJugador={setJugadorDetalle}
          onSubirAPrimera={subirAPrimera}
          mostrarCategoria
        />
      </div>

      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
        <h2 className="text-sm font-bold text-white mb-1">Cesiones activas</h2>
        <p className="text-[11px] text-slate-400 mb-4">Jugadores tuyos jugando a préstamo en otro club.</p>
        <TablaCedidos jugadores={datos.cedidos} />
      </div>

      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
        <h2 className="text-sm font-bold text-white mb-1">Préstamos recibidos</h2>
        <p className="text-[11px] text-slate-400 mb-4">Jugadores de otro club que están disponibles en tu plantel mientras dure su cesión.</p>
        <TablaCedidos jugadores={datos.cedidos_recibidos || []} tipo="entrada" />
      </div>

      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
        <h2 className="text-sm font-bold text-white mb-1">Candidatos al primer equipo</h2>
        <p className="text-[11px] text-slate-400 mb-4">Jugadores de Primera (≤21 años) que ya suman minutos en el plantel principal.</p>
        <TablaJugadores jugadores={datos.candidatos_primer_equipo} vacio="No hay jugadores jóvenes cerca de tener oportunidades en el primer equipo." onVerJugador={setJugadorDetalle} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
          <h2 className="text-sm font-bold text-white mb-1">Necesita atención</h2>
          <p className="text-[11px] text-slate-400 mb-4">Jugadores de Primera en el banco de reservas con margen de progreso.</p>
          <TablaJugadores jugadores={datos.necesita_atencion} vacio="Ningún jugador en reserva necesita atención especial ahora mismo." onVerJugador={setJugadorDetalle} />
        </div>
        <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
          <h2 className="text-sm font-bold text-white mb-1">Jugadores a vigilar</h2>
          <p className="text-[11px] text-slate-400 mb-4">Jugadores de Primera con proyección que conviene seguir de cerca.</p>
          <TablaJugadores jugadores={datos.jugadores_a_vigilar} vacio="No hay jugadores destacados para vigilar por ahora." onVerJugador={setJugadorDetalle} />
        </div>
      </div>

      {CATEGORIAS_TABLA.map(({ key, titulo }) => (
        <div key={key} className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
          <h2 className="text-sm font-bold text-white mb-1">Plantilla {titulo} completa</h2>
          <p className="text-[11px] text-slate-400 mb-4">
            Jugadores reales de la categoría {titulo} de la Academia — hacé click en uno para ver su ficha completa.
          </p>
          <TablaJugadores
            jugadores={datos[key].jugadores}
            vacio={`No hay jugadores en ${titulo} todavía.`}
            onSubirAPrimera={subirAPrimera}
            onVerJugador={setJugadorDetalle}
          />
        </div>
      ))}

      <PlayerDetailModal
        jugador={jugadorDetalle}
        open={!!jugadorDetalle}
        onClose={() => setJugadorDetalle(null)}
        API_URL={API_URL}
      />
    </div>
  );
}
