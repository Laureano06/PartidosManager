import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useDragScroll } from '../utils/useDragScroll';

export default function TablaPage({ API_URL, idPartida }) {
  const [tabla, setTabla] = useState([]);
  const [cargando, setCargando] = useState(true);
  const { ref, dragHandlers } = useDragScroll();

  useEffect(() => {
    if (!idPartida) return;
    setCargando(true);
    fetch(`${API_URL}/tabla?id_partida=${idPartida}`)
      .then((r) => r.json())
      .then((data) => setTabla(data.tabla))
      .catch((error) => console.error('Error cargando la tabla:', error))
      .finally(() => setCargando(false));
  }, [API_URL, idPartida]);

  return (
    <div className="h-full min-h-0 flex flex-col gap-4">
      <div className="shrink-0">
        <Link to="/panel" className="text-xs text-sky-400 hover:underline">← Volver al panel</Link>
        <h1 className="text-lg font-black text-white mt-1">Tabla de Posiciones</h1>
      </div>

      <div ref={ref} {...dragHandlers} className="flex-1 min-h-0 overflow-y-auto overflow-x-auto scroll-slide cursor-grab pr-1">
        {cargando ? (
          <p className="text-xs text-slate-400">Cargando tabla...</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-[#0b1326]">
              <tr className="border-b border-slate-800 text-slate-400 text-xs">
                <th className="p-3">Pos</th>
                <th className="p-3">Equipo</th>
                <th className="p-3">PJ</th>
                <th className="p-3">G</th>
                <th className="p-3">E</th>
                <th className="p-3">P</th>
                <th className="p-3">GF</th>
                <th className="p-3">GC</th>
                <th className="p-3">DIF</th>
                <th className="p-3 font-bold text-white">Pts</th>
              </tr>
            </thead>
            <tbody>
              {tabla.map((row, i) => (
                <tr key={row.id_equipo} className={`border-b border-slate-800/40 ${row.es_usuario ? 'bg-sky-950/40 font-bold text-sky-300' : ''}`}>
                  <td className="p-3">{i + 1}</td>
                  <td className="p-3">
                    <Link to={`/club/${row.id_equipo}`} className="hover:text-sky-400 hover:underline">{row.nombre}</Link>
                  </td>
                  <td className="p-3">{row.jugados}</td>
                  <td className="p-3">{row.ganados}</td>
                  <td className="p-3">{row.empatados}</td>
                  <td className="p-3">{row.perdidos}</td>
                  <td className="p-3">{row.goles_favor}</td>
                  <td className="p-3">{row.goles_contra}</td>
                  <td className="p-3">{row.diferencia_goles}</td>
                  <td className="p-3 font-bold text-white">{row.puntos}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
