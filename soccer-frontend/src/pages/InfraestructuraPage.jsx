import React, { useCallback, useEffect, useState } from 'react';

function BarraNivel({ nivel }) {
  return (
    <div className="w-full bg-[#0b1326] h-2 rounded-full overflow-hidden border border-slate-800">
      <div className="bg-sky-400 h-full" style={{ width: `${(nivel / 20) * 100}%` }} />
    </div>
  );
}

function TarjetaInstalacion({ inst, onSolicitar, solicitando }) {
  const pendiente = inst.solicitud_pendiente;
  const maxNivel = inst.nivel_actual >= 20;

  return (
    <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold text-white">{inst.nombre}</h2>
        <span className="text-xs font-bold text-sky-400">Nivel {inst.nivel_actual}/20</span>
      </div>
      <BarraNivel nivel={inst.nivel_actual} />
      <p className="text-[11px] text-slate-500">
        Mantenimiento actual: ${inst.mantenimiento_mensual_actual.toLocaleString('es-AR')}/mes
      </p>

      {maxNivel ? (
        <p className="text-xs text-slate-400 pt-1">Instalación en su nivel máximo.</p>
      ) : pendiente ? (
        <div className="bg-[#0b1326] border border-slate-800 rounded-xl p-3 space-y-1">
          <p className="text-xs text-slate-300">
            Pedido de mejora a nivel <span className="font-bold text-white">{pendiente.nivel_objetivo}</span> en evaluación.
          </p>
          <p className="text-[11px] text-slate-500">
            Costo ${pendiente.costo.toLocaleString('es-AR')} — respuesta estimada el{' '}
            {new Date(pendiente.fecha_resolucion + 'T00:00:00').toLocaleDateString('es-AR')}.
          </p>
        </div>
      ) : (
        <button
          onClick={() => onSolicitar(inst.tipo)}
          disabled={solicitando === inst.tipo}
          className="w-full bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-2 rounded-lg text-xs"
        >
          {solicitando === inst.tipo
            ? 'Enviando...'
            : `Solicitar mejora a nivel ${inst.nivel_actual + 1} — $${inst.costo_proximo_nivel.toLocaleString('es-AR')}`}
        </button>
      )}
    </div>
  );
}

export default function InfraestructuraPage({ API_URL, idEquipoUsuario }) {
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [solicitando, setSolicitando] = useState(null);
  const [error, setError] = useState(null);

  const cargar = useCallback(() => {
    if (!idEquipoUsuario) return;
    setCargando(true);
    fetch(`${API_URL}/equipos/${idEquipoUsuario}/infraestructura`)
      .then((r) => r.json())
      .then(setDatos)
      .catch((e) => console.error('Error cargando infraestructura:', e))
      .finally(() => setCargando(false));
  }, [API_URL, idEquipoUsuario]);

  useEffect(() => { cargar(); }, [cargar]);

  const solicitar = async (tipoInstalacion) => {
    setSolicitando(tipoInstalacion);
    setError(null);
    try {
      const r = await fetch(`${API_URL}/infraestructura/solicitar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_equipo: idEquipoUsuario, tipo_instalacion: tipoInstalacion }),
      });
      const data = await r.json();
      if (!r.ok) {
        setError(data.detail || 'No se pudo enviar la solicitud.');
        return;
      }
      cargar();
    } catch (e) {
      console.error('Error solicitando obra:', e);
      setError('No se pudo enviar la solicitud.');
    } finally {
      setSolicitando(null);
    }
  };

  if (cargando || !datos) {
    return <p className="text-xs text-slate-400">Cargando infraestructura...</p>;
  }

  return (
    <div className="space-y-6">
      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
        <h2 className="text-xs font-bold text-sky-400 uppercase tracking-wider mb-1">Infraestructura del Club</h2>
        <p className="text-sm text-slate-300">
          Cada mejora requiere aprobación de la directiva, que tarda en resolver según el costo y la confianza que tenga
          en el proyecto. El mantenimiento mensual se descuenta a diario del presupuesto de fichajes.
        </p>
        <p className="text-xs text-slate-500 mt-2">
          Presupuesto disponible: <span className="text-sky-400 font-bold">${datos.presupuesto_fichajes.toLocaleString('es-AR')}</span>
        </p>
      </div>

      {error && (
        <div className="bg-red-950/40 border border-red-500/40 rounded-xl p-3 text-xs text-red-300">{error}</div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {datos.instalaciones.map((inst) => (
          <TarjetaInstalacion key={inst.tipo} inst={inst} onSolicitar={solicitar} solicitando={solicitando} />
        ))}
      </div>
    </div>
  );
}
