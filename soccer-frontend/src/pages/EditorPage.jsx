import React, { useEffect, useState } from 'react';
import { parsearCsvClubes, parsearCsvJugadores, leerArchivoComoTexto } from '../utils/csvClubes';

function formatearFecha(iso) {
  if (!iso) return '';
  const conHora = iso.includes('T') ? iso : `${iso}T00:00:00`;
  return new Date(conHora).toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' });
}

function FormularioNuevoPaquete({ API_URL, onCreado, onCancelar }) {
  const [nombre, setNombre] = useState('');
  const [csvTexto, setCsvTexto] = useState('');
  const [csvJugadoresTexto, setCsvJugadoresTexto] = useState('');
  const [competencias, setCompetencias] = useState({
    CAMPEONES_UEFA: '', EUROPEA_UEFA: '', LIBERTADORES: '', SUDAMERICANA: '',
  });
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  const nombresClubes = parsearCsvClubes(csvTexto);
  const jugadoresClubes = parsearCsvJugadores(csvJugadoresTexto);
  const competenciasFiltradas = Object.fromEntries(Object.entries(competencias).filter(([, v]) => v.trim()));
  const cantidadClubes = Object.values(nombresClubes).reduce((acc, arr) => acc + arr.length, 0);

  const guardar = async () => {
    if (!nombre.trim() || !cantidadClubes) return;
    setGuardando(true);
    setError(null);
    try {
      const r = await fetch(`${API_URL}/paquetes-clubes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nombre: nombre.trim(),
          nombres_clubes: nombresClubes,
          jugadores_clubes: Object.keys(jugadoresClubes).length ? jugadoresClubes : undefined,
          competencias: Object.keys(competenciasFiltradas).length ? competenciasFiltradas : undefined,
        }),
      });
      const data = await r.json();
      if (!r.ok) { setError(data.detail || 'No se pudo guardar el paquete.'); return; }
      onCreado();
    } catch (e) {
      console.error('Error guardando el paquete de datos:', e);
      setError('Error de conexión con el servidor.');
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="bg-[#0b1326] border border-slate-800 rounded-2xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold text-white">Nuevo paquete de datos</h2>
        <button onClick={onCancelar} className="text-xs text-slate-400 hover:text-slate-300">Cancelar</button>
      </div>

      <div>
        <label htmlFor="editor-nombre-paquete" className="text-xs text-slate-400 block mb-1">Nombre del paquete</label>
        <input
          id="editor-nombre-paquete"
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          placeholder="Ej: Mi liga de amigos"
          className="w-full bg-[#121e36] border border-slate-700 p-3 rounded-xl text-white text-sm"
        />
      </div>

      <div>
        <label htmlFor="editor-csv-clubes" className="text-xs text-slate-400 block mb-1">
          Clubes — una línea por club: LIGA,CODIGO,NOMBRE,ESCUDO_URL,NOMBRE_COMPETENCIA
        </label>
        <input
          type="file"
          accept=".csv,text/csv"
          aria-label="Subir archivo CSV de clubes"
          onChange={async (e) => {
            const archivo = e.target.files?.[0];
            if (archivo) setCsvTexto(await leerArchivoComoTexto(archivo));
            e.target.value = '';
          }}
          className="w-full text-xs text-slate-400 file:mr-3 file:bg-slate-800 file:hover:bg-slate-700 file:text-slate-300 file:text-xs file:font-bold file:border-0 file:px-3 file:py-1.5 file:rounded-lg mb-2"
        />
        <textarea
          id="editor-csv-clubes"
          value={csvTexto}
          onChange={(e) => setCsvTexto(e.target.value)}
          placeholder={"ARG1,BOC,Mi Club Favorito\nARG1,RIV,Otro Club,https://ejemplo.com/escudo.png,Mi Liga Real"}
          rows={4}
          className="w-full bg-[#121e36] border border-slate-700 p-3 rounded-xl text-white text-xs font-mono"
        />
        <p className="text-[10px] text-slate-400 mt-1">
          ESCUDO_URL y NOMBRE_COMPETENCIA son opcionales. Vos sos responsable de qué nombres/URLs pongas acá.
        </p>
      </div>

      <div>
        <label htmlFor="editor-csv-jugadores" className="text-xs text-slate-400 block mb-1">
          Jugadores reales (opcional) — LIGA,CODIGO_CLUB,NOMBRE,POSICION,POSICION_ESPECIFICA,NACIONALIDAD,EDAD,ATAQUE,DEFENSA,PASE,FISICO
        </label>
        <input
          type="file"
          accept=".csv,text/csv"
          aria-label="Subir archivo CSV de jugadores"
          onChange={async (e) => {
            const archivo = e.target.files?.[0];
            if (archivo) setCsvJugadoresTexto(await leerArchivoComoTexto(archivo));
            e.target.value = '';
          }}
          className="w-full text-xs text-slate-400 file:mr-3 file:bg-slate-800 file:hover:bg-slate-700 file:text-slate-300 file:text-xs file:font-bold file:border-0 file:px-3 file:py-1.5 file:rounded-lg mb-2"
        />
        <textarea
          id="editor-csv-jugadores"
          value={csvJugadoresTexto}
          onChange={(e) => setCsvJugadoresTexto(e.target.value)}
          placeholder={"ARG1,BOC,Nombre Real,DEL,DC,Argentina,24,82,30,65,78"}
          rows={4}
          className="w-full bg-[#121e36] border border-slate-700 p-3 rounded-xl text-white text-xs font-mono"
        />
        <p className="text-[10px] text-slate-400 mt-1">
          Los clubes que no incluyas acá quedan con plantel 100% ficticio.
        </p>
      </div>

      <div>
        <label className="text-xs text-slate-400 block mb-1">Copas internacionales (opcional)</label>
        <div className="grid grid-cols-2 gap-2">
          {[
            ['CAMPEONES_UEFA', 'Copa top UEFA'],
            ['EUROPEA_UEFA', 'Copa 2ª UEFA'],
            ['LIBERTADORES', 'Copa top CONMEBOL'],
            ['SUDAMERICANA', 'Copa 2ª CONMEBOL'],
          ].map(([clave, etiqueta]) => (
            <input
              key={clave}
              value={competencias[clave]}
              onChange={(e) => setCompetencias((prev) => ({ ...prev, [clave]: e.target.value }))}
              placeholder={etiqueta}
              aria-label={etiqueta}
              className="w-full bg-[#121e36] border border-slate-700 p-2 rounded-lg text-white text-xs"
            />
          ))}
        </div>
      </div>

      {error && <p className="text-xs text-rose-400">{error}</p>}

      <button
        onClick={guardar}
        disabled={guardando || !nombre.trim() || !cantidadClubes}
        className="w-full bg-sky-500 hover:bg-sky-400 disabled:opacity-40 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
      >
        {guardando ? 'Guardando...' : `Guardar paquete (${cantidadClubes} club${cantidadClubes === 1 ? '' : 'es'})`}
      </button>
    </div>
  );
}

function DetallePaquete({ API_URL, idPaquete, onCerrar, onBorrado }) {
  const [detalle, setDetalle] = useState(null);
  const [borrando, setBorrando] = useState(false);
  const [confirmarBorrado, setConfirmarBorrado] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/paquetes-clubes/${idPaquete}`).then((r) => r.json()).then(setDetalle).catch((e) => console.error('Error cargando el paquete:', e));
  }, [API_URL, idPaquete]);

  const borrar = async () => {
    setBorrando(true);
    try {
      await fetch(`${API_URL}/paquetes-clubes/${idPaquete}`, { method: 'DELETE' });
      onBorrado(idPaquete);
    } catch (e) {
      console.error('Error borrando el paquete:', e);
    } finally {
      setBorrando(false);
    }
  };

  return (
    <div className="bg-[#0b1326] border border-slate-800 rounded-2xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold text-white">{detalle?.nombre || 'Cargando...'}</h2>
        <button onClick={onCerrar} className="text-xs text-slate-400 hover:text-slate-300">← Volver</button>
      </div>

      {detalle && (
        <div className="space-y-3 max-h-72 overflow-y-auto scroll-slide pr-1">
          {Object.entries(detalle.nombres_clubes).map(([liga, clubes]) => (
            <div key={liga}>
              <p className="text-[10px] font-bold text-sky-400 uppercase tracking-wider mb-1">{liga}</p>
              <div className="space-y-1">
                {clubes.map(([codigo, nombreClub]) => (
                  <div key={codigo} className="text-xs bg-[#121e36] border border-slate-800 rounded-lg px-3 py-1.5 flex justify-between">
                    <span className="text-slate-200">{nombreClub}</span>
                    <span className="text-slate-500">{codigo}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {confirmarBorrado ? (
        <div className="bg-rose-950/40 border border-rose-500/40 rounded-xl p-3 flex items-center justify-between gap-3 flex-wrap">
          <p className="text-xs text-rose-300">¿Borrar este paquete? No se puede deshacer.</p>
          <div className="flex gap-2 shrink-0">
            <button onClick={borrar} disabled={borrando} className="bg-rose-500 hover:bg-rose-400 disabled:opacity-50 text-slate-950 font-bold px-3 py-1.5 rounded-lg text-[11px]">
              {borrando ? 'Borrando...' : 'Sí, borrar'}
            </button>
            <button onClick={() => setConfirmarBorrado(false)} disabled={borrando} className="bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1.5 rounded-lg text-[11px]">
              Cancelar
            </button>
          </div>
        </div>
      ) : (
        <button onClick={() => setConfirmarBorrado(true)} className="text-xs text-rose-400 hover:text-rose-300 font-bold">
          Borrar este paquete
        </button>
      )}
    </div>
  );
}

export default function EditorPage({ API_URL, onVolver }) {
  const [paquetes, setPaquetes] = useState(null);
  const [vista, setVista] = useState('lista'); // 'lista' | 'nuevo' | detalle: id_paquete
  const [busqueda, setBusqueda] = useState('');

  const cargarPaquetes = () => {
    setPaquetes(null);
    fetch(`${API_URL}/paquetes-clubes`)
      .then((r) => r.json())
      .then(setPaquetes)
      .catch((e) => { console.error('Error cargando paquetes de datos:', e); setPaquetes([]); });
  };

  useEffect(cargarPaquetes, [API_URL]);

  const paquetesFiltrados = (paquetes || []).filter((p) => p.nombre.toLowerCase().includes(busqueda.toLowerCase()));

  return (
    <div className="min-h-screen bg-[#0b1326] text-slate-100 flex items-center justify-center p-6 font-sans">
      <div className="max-w-lg w-full bg-[#121e36] border border-slate-700/60 rounded-3xl p-8 shadow-2xl space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-sky-400 font-bold uppercase tracking-wider">Editor de datos</p>
            <h1 className="text-xl font-black text-white mt-1">Paquetes de clubes reales</h1>
          </div>
          <button onClick={onVolver} className="text-xs text-slate-400 hover:text-slate-300">← Volver al inicio</button>
        </div>

        <p className="text-xs text-slate-400">
          Un paquete es una lista de nombres de club (y opcionalmente jugadores reales) que después podés elegir
          al crear una carrera con "Datos personalizados", sin tener que volver a cargarla cada vez.
        </p>

        {vista === 'nuevo' && (
          <FormularioNuevoPaquete
            API_URL={API_URL}
            onCancelar={() => setVista('lista')}
            onCreado={() => { setVista('lista'); cargarPaquetes(); }}
          />
        )}

        {typeof vista === 'number' && (
          <DetallePaquete
            API_URL={API_URL}
            idPaquete={vista}
            onCerrar={() => setVista('lista')}
            onBorrado={() => { setVista('lista'); cargarPaquetes(); }}
          />
        )}

        {vista === 'lista' && (
          <>
            {paquetes && paquetes.length > 0 && (
              <input
                type="text"
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
                placeholder="Buscar paquete..."
                className="w-full bg-[#0b1326] border border-slate-700 p-2.5 rounded-xl text-white text-sm"
              />
            )}

            {paquetes === null && <p className="text-sm text-slate-400 text-center py-6">Cargando paquetes...</p>}

            {paquetes !== null && (
              <div className="space-y-2 max-h-72 overflow-y-auto scroll-slide pr-1">
                {paquetes.length === 0 && (
                  <p className="text-sm text-slate-400 text-center py-4">Todavía no cargaste ningún paquete de datos reales.</p>
                )}
                {paquetesFiltrados.map((p) => (
                  <button
                    key={p.id_paquete}
                    onClick={() => setVista(p.id_paquete)}
                    className="w-full bg-[#0b1326] border border-slate-700 hover:border-sky-500/40 hover:bg-sky-950 rounded-xl p-4 text-left transition flex justify-between items-center"
                  >
                    <div className="min-w-0">
                      <p className="font-bold text-white text-sm truncate">{p.nombre}</p>
                      <p className="text-xs text-slate-400 mt-0.5">
                        {p.cantidad_clubes} clubes en {p.cantidad_ligas} liga{p.cantidad_ligas === 1 ? '' : 's'} · creado el {formatearFecha(p.fecha_creacion)}
                      </p>
                    </div>
                    <span className="text-sky-400 text-xs font-bold shrink-0 ml-3">Ver ➔</span>
                  </button>
                ))}
              </div>
            )}

            <button
              onClick={() => setVista('nuevo')}
              className="w-full bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
            >
              + Nuevo paquete de datos
            </button>
          </>
        )}
      </div>
    </div>
  );
}
