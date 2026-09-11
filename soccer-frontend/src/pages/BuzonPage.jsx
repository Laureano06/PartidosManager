import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import MailModal from '../components/MailModal';
import { useDragScroll } from '../utils/useDragScroll';

export default function BuzonPage({ API_URL, idEquipoUsuario }) {
  const [mails, setMails] = useState([]);
  const [mailSeleccionado, setMailSeleccionado] = useState(null);
  const [cargando, setCargando] = useState(true);
  const { ref, dragHandlers } = useDragScroll();

  const cargarInbox = useCallback(() => {
    if (!idEquipoUsuario) return;
    setCargando(true);
    fetch(`${API_URL}/inbox?id_equipo=${idEquipoUsuario}`)
      .then((r) => r.json())
      .then((data) => setMails(data.emails))
      .catch((error) => console.error('Error conectando con la API (/inbox):', error))
      .finally(() => setCargando(false));
  }, [API_URL, idEquipoUsuario]);

  useEffect(() => { cargarInbox(); }, [cargarInbox]);

  const abrirMail = (m) => {
    setMailSeleccionado(m);
    if (!m.leido) {
      fetch(`${API_URL}/inbox/${m.id}/leido`, { method: 'POST' }).catch(() => {});
      setMails((prev) => prev.map((x) => (x.id === m.id ? { ...x, leido: true } : x)));
    }
  };

  const marcarTodoLeido = () => {
    setMails((prev) => prev.map((x) => ({ ...x, leido: true })));
    fetch(`${API_URL}/inbox/marcar-todo-leido?id_equipo=${idEquipoUsuario}`, { method: 'POST' }).catch(() => {});
  };

  const hayNoLeidos = mails.some((m) => !m.leido);

  return (
    <div className="h-full min-h-0 flex flex-col gap-4">
      <div className="flex items-center justify-between shrink-0">
        <div>
          <Link to="/panel" className="text-xs text-sky-400 hover:underline">← Volver al panel</Link>
          <h1 className="text-lg font-black text-white mt-1">Buzón de Mensajes</h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400">{mails.filter((m) => !m.leido).length} sin leer</span>
          {hayNoLeidos && (
            <button onClick={marcarTodoLeido} className="text-xs text-sky-400 hover:underline font-bold">
              Marcar todo como leído
            </button>
          )}
        </div>
      </div>

      <div ref={ref} {...dragHandlers} className="flex-1 min-h-0 overflow-y-auto scroll-slide space-y-2 cursor-grab pr-1">
        {cargando ? (
          <p className="text-xs text-slate-400">Cargando mensajes...</p>
        ) : mails.length === 0 ? (
          <p className="text-xs text-slate-500">No tenés mensajes todavía.</p>
        ) : (
          mails.map((m) => (
            <button
              key={m.id}
              onClick={() => abrirMail(m)}
              className={`w-full text-left p-4 rounded-xl border text-sm transition ${
                m.leido
                  ? 'bg-[#121e36] border-slate-800/80 text-slate-300 hover:border-slate-700'
                  : 'bg-sky-950/60 border-sky-500/50 text-white'
              }`}
            >
              <div className="flex justify-between font-bold gap-2">
                <span className="truncate">{m.remitente}</span>
                <span className="text-[11px] text-slate-500 shrink-0">{m.fecha}</span>
              </div>
              <p className="text-slate-400 truncate mt-1 text-xs">{m.asunto}</p>
            </button>
          ))
        )}
      </div>

      <MailModal
        mail={mailSeleccionado}
        open={!!mailSeleccionado}
        onClose={() => setMailSeleccionado(null)}
        API_URL={API_URL}
        onRespondida={cargarInbox}
      />
    </div>
  );
}
