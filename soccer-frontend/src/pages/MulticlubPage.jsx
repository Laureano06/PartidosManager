import React, { useCallback, useEffect, useState } from 'react';

const NOMBRE_TIPO = { PROPIETARIO: 'Propietario', SATELITE: 'Club Satélite', MINORITARIO: 'Inversión Minoritaria', MARCA: 'Red de Marca' };
const NOMBRE_ROL = { PARTICIPADO: 'te controla', INVERSOR: 'controlás vos', MARCA: 'comparten identidad' };

const MODELOS = [
  { tipo: 'MINORITARIO', rango: '1-14%', ejemplo: 'Brighton en Alavés', desc: 'Solo inversión: cobrás si al club le va bien y accedés a algo de su scouting, pero no tenés control deportivo.' },
  { tipo: 'SATELITE', rango: '15-34%', ejemplo: 'Chelsea–Strasbourg, Udinese', desc: 'Peso real sin control total: pipeline de jugadores más fluido y bono más fuerte, pero el club sigue siendo independiente.' },
  { tipo: 'PROPIETARIO', rango: '35-100%', ejemplo: 'City Football Group', desc: 'Control total: el club pasa a ser parte de tu grupo, comparte scouting y metodología a fondo.' },
  { tipo: 'MARCA', rango: 'fijo, no comprable', ejemplo: 'Red Bull (Leipzig/Bragantino)', desc: 'Identidad y filosofía compartida entre clubes, sin relación de accionista — se define al crear la carrera, no se compra ni se vende.' },
];

const NOMBRE_INTERES = {
  MUY_INTERESADOS: { texto: 'Muy interesados', color: 'text-emerald-400' },
  INTERESADOS: { texto: 'Interesados', color: 'text-sky-400' },
  RETICENTES: { texto: 'Reticentes', color: 'text-amber-400' },
  MUY_RETICENTES: { texto: 'Muy reticentes', color: 'text-rose-400' },
};

function PanelModelos() {
  const [abierto, setAbierto] = useState(false);
  return (
    <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
      <button onClick={() => setAbierto((v) => !v)} className="w-full flex items-center justify-between text-left">
        <h2 className="text-xs font-bold text-sky-400 uppercase tracking-wider">¿Qué son los modelos multiclub?</h2>
        <span className="text-slate-500 text-xs">{abierto ? 'Ocultar ▲' : 'Ver ▼'}</span>
      </button>
      {abierto && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
          {MODELOS.map((m) => (
            <div key={m.tipo} className="bg-[#0b1326] border border-slate-800 rounded-xl p-3 text-xs space-y-1">
              <div className="flex justify-between items-baseline">
                <span className="text-white font-bold">{NOMBRE_TIPO[m.tipo]}</span>
                <span className="text-slate-500">{m.rango}</span>
              </div>
              <p className="text-slate-400">{m.desc}</p>
              <p className="text-slate-600 italic">Ej: {m.ejemplo}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TarjetaPosicion({ multiclub }) {
  const { posicion, red_marca: redMarca, socio_marca: socioMarca, bono } = multiclub;

  return (
    <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 space-y-3">
      <h2 className="text-xs font-bold text-sky-400 uppercase tracking-wider">Tu posición en la red</h2>
      {redMarca ? (
        <p className="text-sm text-slate-300">
          Formás parte de la red de marca <span className="text-white font-bold">{redMarca}</span>, junto a{' '}
          <span className="text-white font-bold">{socioMarca}</span>.
        </p>
      ) : posicion ? (
        <p className="text-sm text-slate-300">
          <span className="text-white font-bold">{NOMBRE_TIPO[posicion.tipo_relacion] || posicion.tipo_relacion}</span> junto a{' '}
          <span className="text-white font-bold">{posicion.contraparte}</span> ({NOMBRE_ROL[posicion.rol] || posicion.rol}).
        </p>
      ) : (
        <p className="text-sm text-slate-400">Club independiente — sin afiliaciones multiclub por ahora.</p>
      )}
      {bono && (posicion || redMarca) && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs pt-2 border-t border-slate-800">
          <div><p className="text-slate-500">Entrenamiento</p><p className="text-sky-400 font-bold">+{Math.round(bono.bono_centro * 100)}%</p></div>
          <div><p className="text-slate-500">Riesgo de lesión</p><p className="text-sky-400 font-bold">-{Math.round((1 - bono.factor_medico) * 100)}%</p></div>
          <div><p className="text-slate-500">Scouting</p><p className="text-sky-400 font-bold">+{bono.bono_analitica}</p></div>
          <div><p className="text-slate-500">Academia</p><p className="text-sky-400 font-bold">+{Math.round(bono.bono_instalaciones_juveniles * 100)}%</p></div>
          <div><p className="text-slate-500">Captación</p><p className="text-sky-400 font-bold">+{bono.bono_captacion_juvenil}</p></div>
        </div>
      )}
    </div>
  );
}

function FormularioOperacion({ idEquipo, contraparte, operacion, onCerrar, onConfirmado, API_URL, tuPorcentaje }) {
  const [porcentaje, setPorcentaje] = useState(operacion === 'VENDER' ? Math.min(5, tuPorcentaje) : 5);
  const [cotizacion, setCotizacion] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!porcentaje || porcentaje <= 0) { setCotizacion(null); return; }
    setCargando(true);
    const params = new URLSearchParams({
      id_equipo_iniciador: idEquipo, id_equipo_contraparte: contraparte.id_equipo, operacion, porcentaje: String(porcentaje),
    });
    fetch(`${API_URL}/multiclub/cotizar?${params.toString()}`)
      .then((r) => r.json())
      .then(setCotizacion)
      .catch(() => setCotizacion(null))
      .finally(() => setCargando(false));
  }, [porcentaje, idEquipo, contraparte.id_equipo, operacion, API_URL]);

  const confirmar = async () => {
    setEnviando(true);
    setError(null);
    try {
      const r = await fetch(`${API_URL}/multiclub/ofertar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_equipo_iniciador: idEquipo, id_equipo_contraparte: contraparte.id_equipo, operacion, porcentaje }),
      });
      const data = await r.json();
      if (!r.ok) { setError(data.detail || 'No se pudo enviar la oferta.'); return; }
      onConfirmado();
    } catch (e) {
      console.error('Error ofertando participación:', e);
      setError('No se pudo enviar la oferta.');
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onCerrar}>
      <div className="bg-[#121e36] border border-slate-700 rounded-2xl p-6 w-full max-w-sm space-y-4" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-sm font-bold text-white">
          {operacion === 'COMPRAR' ? 'Comprar participación en' : 'Vender participación en'} {contraparte.nombre}
        </h3>
        <div>
          <label className="text-xs text-slate-400 block mb-1">Puntos porcentuales</label>
          <input
            type="number" min={1} max={operacion === 'VENDER' ? tuPorcentaje : 100 - (cotizacion?.porcentaje_actual ?? tuPorcentaje)} value={porcentaje}
            onChange={(e) => setPorcentaje(Number(e.target.value))}
            className="w-full bg-[#0b1326] border border-slate-700 p-2.5 rounded-lg text-white text-sm"
          />
        </div>
        <div className="bg-[#0b1326] border border-slate-800 rounded-xl p-3 text-xs space-y-1">
          {cargando && <p className="text-slate-500">Cotizando...</p>}
          {!cargando && cotizacion && (
            <>
              <p className="text-slate-400">Valor estimado del club: <span className="text-slate-200 font-bold">${cotizacion.valor_club.toLocaleString('es-AR')}</span></p>
              <p className="text-slate-400">Tu participación actual: <span className="text-slate-200 font-bold">{cotizacion.porcentaje_actual}%</span></p>
              <p className="text-slate-400">Quedarías con: <span className="text-slate-200 font-bold">{NOMBRE_TIPO[cotizacion.tipo_relacion_resultante] || cotizacion.tipo_relacion_resultante}</span></p>
              <p className="text-slate-400">
                {operacion === 'COMPRAR' ? 'Costo' : 'Ingreso'}: <span className="text-sky-400 font-bold">${cotizacion.monto.toLocaleString('es-AR')}</span>
              </p>
              <p className="text-slate-400 pt-1 border-t border-slate-800">
                Directiva de {contraparte.nombre}:{' '}
                <span className={`font-bold ${NOMBRE_INTERES[cotizacion.interes_directiva_contraparte]?.color || 'text-slate-300'}`}>
                  {NOMBRE_INTERES[cotizacion.interes_directiva_contraparte]?.texto || cotizacion.interes_directiva_contraparte}
                </span>
              </p>
            </>
          )}
        </div>
        {error && <p className="text-xs text-rose-400">{error}</p>}
        <div className="flex gap-2">
          <button
            onClick={confirmar}
            disabled={enviando || !cotizacion}
            className="flex-1 bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-2.5 rounded-lg text-sm"
          >
            {enviando ? 'Enviando...' : 'Elevar a la directiva'}
          </button>
          <button onClick={onCerrar} className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-2.5 rounded-lg text-sm">
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}

export default function MulticlubPage({ API_URL, idEquipoUsuario }) {
  const [multiclub, setMulticlub] = useState(null);
  const [mercado, setMercado] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [busqueda, setBusqueda] = useState('');
  const [operacionAbierta, setOperacionAbierta] = useState(null); // { contraparte, operacion, tuPorcentaje }

  const cargar = useCallback(() => {
    if (!idEquipoUsuario) return;
    setCargando(true);
    Promise.all([
      fetch(`${API_URL}/equipos/${idEquipoUsuario}/multiclub`).then((r) => r.json()),
      fetch(`${API_URL}/equipos/${idEquipoUsuario}/multiclub/mercado`).then((r) => r.json()),
    ])
      .then(([mc, mkt]) => { setMulticlub(mc); setMercado(mkt); })
      .catch((e) => console.error('Error cargando multiclub:', e))
      .finally(() => setCargando(false));
  }, [API_URL, idEquipoUsuario]);

  useEffect(() => { cargar(); }, [cargar]);

  if (cargando || !multiclub || !mercado) {
    return <p className="text-xs text-slate-400">Cargando multiclub...</p>;
  }

  const clubesFiltrados = mercado.clubes.filter((c) => c.nombre.toLowerCase().includes(busqueda.toLowerCase()));

  return (
    <div className="space-y-6">
      <TarjetaPosicion multiclub={multiclub} />
      <PanelModelos />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
          <h2 className="text-xs font-bold text-sky-400 uppercase tracking-wider mb-3">Tus participaciones</h2>
          {multiclub.tus_participaciones.length === 0 && <p className="text-xs text-slate-500">No tenés participación en otros clubes.</p>}
          <div className="space-y-2">
            {multiclub.tus_participaciones.map((p) => (
              <div key={p.id_equipo} className="flex items-center justify-between bg-[#0b1326] border border-slate-800 rounded-xl p-3 text-xs">
                <div>
                  <p className="text-slate-200 font-bold">{p.nombre}</p>
                  <p className="text-slate-500">{p.porcentaje}% · {NOMBRE_TIPO[p.tipo_relacion] || p.tipo_relacion}</p>
                </div>
                <button
                  onClick={() => setOperacionAbierta({ contraparte: p, operacion: 'VENDER', tuPorcentaje: p.porcentaje })}
                  className="bg-rose-950 hover:bg-rose-900 border border-rose-500/40 text-rose-300 font-bold px-3 py-1.5 rounded-lg"
                >
                  Vender
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
          <h2 className="text-xs font-bold text-sky-400 uppercase tracking-wider mb-3">Participaciones sobre tu club</h2>
          {multiclub.participaciones_sobre_tu_club.length === 0 && <p className="text-xs text-slate-500">Ningún club tiene participación en el tuyo.</p>}
          <div className="space-y-2">
            {multiclub.participaciones_sobre_tu_club.map((p) => (
              <div key={p.id_equipo} className="bg-[#0b1326] border border-slate-800 rounded-xl p-3 text-xs">
                <p className="text-slate-200 font-bold">{p.nombre}</p>
                <p className="text-slate-500">{p.porcentaje}% · {NOMBRE_TIPO[p.tipo_relacion] || p.tipo_relacion}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {multiclub.solicitudes_pendientes.length > 0 && (
        <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
          <h2 className="text-xs font-bold text-sky-400 uppercase tracking-wider mb-3">Solicitudes pendientes</h2>
          <div className="space-y-2">
            {multiclub.solicitudes_pendientes.map((s) => {
              const club = mercado.clubes.find((c) => c.id_equipo === s.id_equipo_contraparte);
              return (
                <div key={s.id_solicitud} className="bg-[#0b1326] border border-slate-800 rounded-xl p-3 text-xs flex justify-between items-center">
                  <div>
                    <p className="text-slate-200 font-bold">{s.operacion === 'COMPRAR' ? 'Compra' : 'Venta'} de {s.porcentaje}% — {club?.nombre || '?'}</p>
                    <p className="text-slate-500">${s.monto.toLocaleString('es-AR')} · fase: {s.fase === 'DIRECTIVA_PROPIA' ? 'tu directiva' : 'directiva del club objetivo'}</p>
                  </div>
                  <span className="text-slate-500">ETA {new Date(`${s.fecha_resolucion}T00:00:00`).toLocaleDateString('es-AR')}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
        <h2 className="text-xs font-bold text-sky-400 uppercase tracking-wider mb-3">Explorar clubes</h2>
        <input
          type="text" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} placeholder="Buscar club por nombre..."
          className="w-full bg-[#0b1326] border border-slate-700 p-2.5 rounded-lg text-white text-sm mb-3"
        />
        <div className="space-y-1.5 max-h-96 overflow-y-auto scroll-slide">
          {clubesFiltrados.slice(0, 60).map((c) => (
            <div key={c.id_equipo} className="flex items-center justify-between bg-[#0b1326] border border-slate-800 rounded-lg px-3 py-2 text-xs">
              <div>
                <p className="text-slate-200 font-bold">{c.nombre}</p>
                <p className="text-slate-500">Reputación {c.reputacion} · Valor ${c.valor_club.toLocaleString('es-AR')}{c.tu_porcentaje > 0 && ` · Tenés ${c.tu_porcentaje}%`}</p>
              </div>
              <button
                onClick={() => setOperacionAbierta({ contraparte: c, operacion: 'COMPRAR', tuPorcentaje: c.tu_porcentaje })}
                className="bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold px-3 py-1.5 rounded-lg"
              >
                Comprar
              </button>
            </div>
          ))}
        </div>
      </div>

      {operacionAbierta && (
        <FormularioOperacion
          idEquipo={idEquipoUsuario}
          contraparte={operacionAbierta.contraparte}
          operacion={operacionAbierta.operacion}
          tuPorcentaje={operacionAbierta.tuPorcentaje}
          API_URL={API_URL}
          onCerrar={() => setOperacionAbierta(null)}
          onConfirmado={() => { setOperacionAbierta(null); cargar(); }}
        />
      )}
    </div>
  );
}
