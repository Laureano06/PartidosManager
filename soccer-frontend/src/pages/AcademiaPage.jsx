import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Bandera from '../components/Bandera';
import NegociacionFichajeModal from '../components/NegociacionFichajeModal';
import ConfirmarReclutamientoModal from '../components/ConfirmarReclutamientoModal';
import { CATEGORIAS_ACADEMIA, CATEGORIA_LABEL } from '../utils/academia';
import { formatOverall } from '../utils/scouting';

function PanelCategoria({ categoria, jugadores, onClick }) {
  const mejor = jugadores.length ? jugadores.reduce((a, b) => (b.potencial > a.potencial ? b : a)) : null;
  const completo = jugadores.length >= 15;
  return (
    <button
      onClick={onClick}
      className="bg-[#121e36] border border-slate-800 hover:border-sky-500/60 rounded-2xl p-5 text-left transition space-y-2"
    >
      <h3 className="text-xs font-bold text-amber-400 uppercase tracking-wider">{CATEGORIA_LABEL[categoria]}</h3>
      <p className={`text-lg font-black ${completo ? 'text-white' : 'text-amber-300'}`}>{jugadores.length}/15</p>
      {mejor ? (
        <p className="text-[11px] text-slate-400">
          Mejor potencial: <span className="text-slate-200 font-bold">{mejor.nombre}</span> ({mejor.potencial})
        </p>
      ) : (
        <p className="text-[11px] text-slate-500">Sin jugadores todavía.</p>
      )}
      <p className="text-[10px] text-sky-400">Ver plantilla →</p>
    </button>
  );
}

function TarjetaIntake({ jugador, onDecidir }) {
  return (
    <div className="bg-[#0b1326] border border-slate-800 rounded-xl p-4 flex items-center justify-between gap-4">
      <div>
        <p className="font-bold text-slate-200 text-sm">{jugador.nombre}</p>
        <p className="text-[11px] text-slate-500">
          {jugador.posicion_especifica || jugador.posicion} · {jugador.edad} años · Ovr {jugador.overall} · Pot{' '}
          <span className="text-amber-300 font-bold">{jugador.potencial}</span>
        </p>
      </div>
      <div className="flex gap-2 shrink-0">
        <button
          onClick={() => onDecidir(jugador.id_jugador, true)}
          className="text-[11px] font-bold px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950"
        >
          Incorporar
        </button>
        <button
          onClick={() => onDecidir(jugador.id_jugador, false)}
          className="text-[11px] font-bold px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
        >
          Rechazar
        </button>
      </div>
    </div>
  );
}

function BuscarEnOtrosClubes({ API_URL, idEquipoUsuario, idPartida }) {
  const [categoria, setCategoria] = useState('SUB18');
  const [club, setClub] = useState('');
  const [resultados, setResultados] = useState([]);
  const [buscando, setBuscando] = useState(false);
  const [mensaje, setMensaje] = useState('');
  const [jugadorAReclutar, setJugadorAReclutar] = useState(null);
  const [jugadorANegociar, setJugadorANegociar] = useState(null);

  const buscar = () => {
    if (!club.trim()) return;
    setBuscando(true);
    setMensaje('');
    fetch(`${API_URL}/mercado/jugadores?categoria=${categoria}&id_equipo=${idEquipoUsuario}&id_partida=${idPartida}&club=${encodeURIComponent(club)}`)
      .then((r) => r.json())
      .then((d) => setResultados(d.jugadores || []))
      .catch((e) => console.error('Error buscando en el mercado juvenil:', e))
      .finally(() => setBuscando(false));
  };

  const quitarDeResultados = (idJugador) => setResultados((prev) => prev.filter((j) => j.id_jugador !== idJugador));

  return (
    <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 space-y-4">
      <div>
        <h2 className="text-sm font-bold text-white mb-1">Buscar en otros clubes</h2>
        <p className="text-[11px] text-slate-500">
          Si el jugador no tiene contrato, se recluta directo pagando una compensación por formación. Si ya tiene contrato con su club, hay que negociar el fichaje.
          Reclutar/negociar un menor de 18 solo es posible si el club de origen es del mismo país (regla real de la FIFA).
        </p>
      </div>
      <div className="flex flex-wrap gap-2 items-center">
        <select
          value={categoria}
          onChange={(e) => setCategoria(e.target.value)}
          className="bg-slate-800 text-slate-200 text-xs px-3 py-2 rounded-lg border-none"
        >
          {CATEGORIAS_ACADEMIA.map((c) => (
            <option key={c} value={c}>{CATEGORIA_LABEL[c]}</option>
          ))}
        </select>
        <input
          value={club}
          onChange={(e) => setClub(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && buscar()}
          placeholder="Nombre del club..."
          className="flex-1 min-w-[180px] bg-slate-800 text-slate-200 text-xs px-3 py-2 rounded-lg border-none placeholder:text-slate-500"
        />
        <button
          onClick={buscar}
          className="text-xs font-bold px-4 py-2 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950"
        >
          Buscar
        </button>
      </div>
      {mensaje && <p className="text-[11px] text-amber-300">{mensaje}</p>}
      {buscando && <p className="text-xs text-slate-500">Buscando...</p>}
      {!buscando && resultados.length > 0 && (
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400">
              <th className="p-2">Jugador</th>
              <th className="p-2">Club</th>
              <th className="p-2">Nac</th>
              <th className="p-2">Edad</th>
              <th className="p-2">Ovr</th>
              <th className="p-2">Contrato</th>
              <th className="p-2"></th>
            </tr>
          </thead>
          <tbody>
            {resultados.map((j) => (
              <tr key={j.id_jugador} className="border-b border-slate-800/40">
                <td className="p-2 font-bold text-slate-200">{j.nombre}</td>
                <td className="p-2 text-slate-400">{j.club}</td>
                <td className="p-2"><Bandera pais={j.nacionalidad} /></td>
                <td className="p-2 text-slate-300">{j.edad}</td>
                <td className="p-2 font-bold text-white">{formatOverall(j)}</td>
                <td className="p-2">
                  {j.fecha_fin_contrato ? (
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-950 text-amber-400 border border-amber-500/40">Con contrato</span>
                  ) : (
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-500/40">Libre</span>
                  )}
                </td>
                <td className="p-2">
                  {j.fecha_fin_contrato ? (
                    <button
                      onClick={() => setJugadorANegociar(j)}
                      className="text-[10px] font-bold px-2 py-1 rounded bg-sky-500 hover:bg-sky-400 text-slate-950"
                    >
                      Negociar
                    </button>
                  ) : (
                    <button
                      onClick={() => setJugadorAReclutar(j)}
                      className="text-[10px] font-bold px-2 py-1 rounded bg-emerald-500 hover:bg-emerald-400 text-slate-950"
                    >
                      Reclutar
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <ConfirmarReclutamientoModal
        jugador={jugadorAReclutar}
        open={!!jugadorAReclutar}
        onClose={() => setJugadorAReclutar(null)}
        API_URL={API_URL}
        idEquipoUsuario={idEquipoUsuario}
        onConfirmado={(idJugador, compensacion) => {
          setMensaje(`Reclutado: pagaste $${compensacion.toLocaleString('es-AR')} de compensación por formación.`);
          quitarDeResultados(idJugador);
          setJugadorAReclutar(null);
        }}
      />
      <NegociacionFichajeModal
        jugador={jugadorANegociar}
        open={!!jugadorANegociar}
        onClose={() => setJugadorANegociar(null)}
        API_URL={API_URL}
        idEquipoUsuario={idEquipoUsuario}
        onResuelto={() => {
          setMensaje(`Acuerdo cerrado con ${jugadorANegociar?.nombre}.`);
          if (jugadorANegociar) quitarDeResultados(jugadorANegociar.id_jugador);
          setJugadorANegociar(null);
        }}
      />
    </div>
  );
}

export default function AcademiaPage({ API_URL, idEquipoUsuario, idPartida }) {
  const navigate = useNavigate();
  const [academia, setAcademia] = useState(null);
  const [intake, setIntake] = useState(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    if (!idEquipoUsuario) return;
    setCargando(true);
    Promise.all([
      fetch(`${API_URL}/equipos/${idEquipoUsuario}/academia`).then((r) => r.json()),
      fetch(`${API_URL}/equipos/${idEquipoUsuario}/academia/intake`).then((r) => r.json()),
    ])
      .then(([a, i]) => { setAcademia(a); setIntake(i); })
      .catch((e) => console.error('Error cargando la Academia:', e))
      .finally(() => setCargando(false));
  }, [API_URL, idEquipoUsuario]);

  const decidirIntake = async (idJugador, aceptar) => {
    try {
      const r = await fetch(`${API_URL}/jugadores/${idJugador}/intake/decidir`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ aceptar }),
      });
      if (!r.ok) return;
      setIntake((prev) => {
        const copia = { ...prev };
        for (const c of Object.keys(copia)) {
          copia[c] = copia[c].filter((j) => j.id_jugador !== idJugador);
        }
        return copia;
      });
      if (aceptar) setAcademia(null); // se invalida, se vuelve a pedir la próxima vez que se visite Plantel/Academia
    } catch (error) {
      console.error('Error decidiendo intake:', error);
    }
  };

  if (cargando || !academia) {
    return <p className="text-xs text-slate-400">Cargando Academia...</p>;
  }

  const totalIntake = intake ? Object.values(intake).reduce((sum, l) => sum + l.length, 0) : 0;

  return (
    <div className="space-y-6">
      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-5">
        <p className="text-xs text-slate-400">INFORME DE:</p>
        <p className="text-sm font-bold text-white">Academia de {academia.nombre_equipo}</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {CATEGORIAS_ACADEMIA.map((c) => (
          <PanelCategoria
            key={c}
            categoria={c}
            jugadores={academia[c.toLowerCase()] || []}
            onClick={() => navigate(`/equipo?categoria=${c}`)}
          />
        ))}
      </div>

      {totalIntake > 0 && (
        <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 space-y-4">
          <div>
            <h2 className="text-sm font-bold text-white mb-1">Intake Anual</h2>
            <p className="text-[11px] text-slate-500">
              Nuevos prospectos de esta temporada. Decidí uno por uno si se suman a la Academia — 15 es el piso por categoría, no el techo.
            </p>
          </div>
          {CATEGORIAS_ACADEMIA.map((c) => {
            const lista = intake[c.toLowerCase()] || [];
            if (lista.length === 0) return null;
            return (
              <div key={c} className="space-y-2">
                <h3 className="text-xs font-bold text-amber-400 uppercase tracking-wider">{CATEGORIA_LABEL[c]}</h3>
                <div className="space-y-2">
                  {lista.map((j) => (
                    <TarjetaIntake key={j.id_jugador} jugador={j} onDecidir={decidirIntake} />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <BuscarEnOtrosClubes API_URL={API_URL} idEquipoUsuario={idEquipoUsuario} idPartida={idPartida} />
    </div>
  );
}
