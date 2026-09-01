import React, { useEffect, useState } from 'react';

const FFP_ESTILO = {
  verde: { barra: 'bg-emerald-400', texto: 'text-emerald-300', panel: 'bg-emerald-950/60 border-emerald-500/40' },
  amarillo: { barra: 'bg-amber-400', texto: 'text-amber-300', panel: 'bg-amber-950/60 border-amber-500/40' },
  rojo: { barra: 'bg-rose-500', texto: 'text-rose-300', panel: 'bg-rose-950/60 border-rose-500/40' },
};

function Metrica({ titulo, valor, sub }) {
  return (
    <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-5 space-y-1">
      <p className="text-xs text-slate-400 uppercase tracking-wider">{titulo}</p>
      <p className="text-2xl font-black text-white">{valor}</p>
      {sub && <p className="text-[11px] text-slate-500">{sub}</p>}
    </div>
  );
}

export default function EconomiaPage({ API_URL, idEquipoUsuario }) {
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    if (!idEquipoUsuario) return;
    setCargando(true);
    fetch(`${API_URL}/equipos/${idEquipoUsuario}/economia`)
      .then((r) => r.json())
      .then(setDatos)
      .catch((e) => console.error('Error cargando economía:', e))
      .finally(() => setCargando(false));
  }, [API_URL, idEquipoUsuario]);

  if (cargando || !datos) {
    return <p className="text-xs text-slate-400">Cargando economía del club...</p>;
  }

  const estilo = FFP_ESTILO[datos.color_ffp] || FFP_ESTILO.verde;
  const pctMasaSalarial = Math.min(100, Math.round(datos.ratio_masa_salarial * 100));

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Metrica titulo="Presupuesto de fichajes" valor={`$${datos.presupuesto_fichajes.toLocaleString('es-AR')}`} />
        <Metrica titulo="Presupuesto de sueldos" valor={`$${datos.presupuesto_salarios.toLocaleString('es-AR')}/sem`} />
        <Metrica titulo="Masa salarial actual" valor={`$${datos.masa_salarial_semanal.toLocaleString('es-AR')}/sem`} sub={`${datos.cantidad_jugadores} jugadores bajo contrato`} />
        <Metrica titulo="Valor de plantilla" valor={`$${datos.valor_plantilla.toLocaleString('es-AR')}`} />
      </div>

      <div className={`rounded-2xl p-6 border ${estilo.panel}`}>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-bold text-white">Progreso en el Juego Limpio Financiero</h2>
          <span className={`text-xs font-bold uppercase ${estilo.texto}`}>{datos.estado_ffp}</span>
        </div>
        <p className="text-xs text-slate-400 mb-3">
          Sueldos comprometidos: ${datos.masa_salarial_semanal.toLocaleString('es-AR')}/sem de ${datos.presupuesto_salarios.toLocaleString('es-AR')}/sem disponibles ({pctMasaSalarial}%).
        </p>
        <div className="w-full bg-[#0b1326] h-3 rounded-full overflow-hidden border border-slate-800">
          <div className={`h-full ${estilo.barra}`} style={{ width: `${pctMasaSalarial}%` }} />
        </div>
      </div>

      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
        <h2 className="text-sm font-bold text-white mb-1">Sueldos más altos del plantel</h2>
        <p className="text-[11px] text-slate-500 mb-4">Los jugadores que más pesan en la masa salarial semanal.</p>
        {datos.top_sueldos.length === 0 ? (
          <p className="text-xs text-slate-500">No hay jugadores bajo contrato todavía.</p>
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400">
                <th className="p-2">Jugador</th>
                <th className="p-2">Pos</th>
                <th className="p-2">Ovr</th>
                <th className="p-2">Sueldo/sem</th>
                <th className="p-2">% de la masa salarial</th>
              </tr>
            </thead>
            <tbody>
              {datos.top_sueldos.map((j) => (
                <tr key={j.id_jugador} className="border-b border-slate-800/40 hover:bg-[#0b1326]">
                  <td className="p-2 font-bold text-slate-200">{j.nombre}</td>
                  <td className="p-2 text-sky-400" title={j.posicion}>{j.posicion_especifica || j.posicion}</td>
                  <td className="p-2 font-bold text-white">{j.overall}</td>
                  <td className="p-2 font-bold text-sky-400">${j.salario.toLocaleString('es-AR')}</td>
                  <td className="p-2 text-slate-400">
                    {datos.masa_salarial_semanal ? Math.round((j.salario / datos.masa_salarial_semanal) * 100) : 0}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
