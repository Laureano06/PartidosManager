import React, { useEffect, useState } from 'react';

// Parsea líneas "LIGA,CODIGO,NOMBRE[,ESCUDO_URL[,NOMBRE_COMPETENCIA]]" en el
// formato que espera el backend: { ARG1: [["BOC","Xeneize FC", escudo?, competencia?], ...] }.
function parsearCsvClubes(texto) {
  const porLiga = {};
  texto.split('\n').map((l) => l.trim()).filter((l) => l && !l.startsWith('#')).forEach((linea) => {
    const partes = linea.split(',').map((s) => s.trim());
    if (partes.length < 3) return;
    const [liga, codigo, nombre, escudoUrl, nombreCompetencia] = partes;
    if (!liga || !codigo || !nombre) return;
    porLiga[liga] = porLiga[liga] || [];
    const fila = [codigo, nombre];
    if (escudoUrl || nombreCompetencia) fila.push(escudoUrl || '');
    if (nombreCompetencia) fila.push(nombreCompetencia);
    porLiga[liga].push(fila);
  });
  return porLiga;
}

// Parsea líneas "LIGA,CODIGO_CLUB,NOMBRE,POSICION,POSICION_ESPECIFICA,
// NACIONALIDAD,EDAD,ATAQUE,DEFENSA,PASE,FISICO" agrupadas por liga y código
// de club: { ARG1: { BOC: [{nombre, posicion, ...}, ...] }, ... }. Anidar
// por liga es necesario porque el código de club no es único entre ligas
// (ej. "BOC" existe en ARG1 y en ALE1).
function parsearCsvJugadores(texto) {
  const porLiga = {};
  texto.split('\n').map((l) => l.trim()).filter((l) => l && !l.startsWith('#')).forEach((linea) => {
    const partes = linea.split(',').map((s) => s.trim());
    if (partes.length < 11) return;
    const [liga, codigoClub, nombre, posicion, posicionEspecifica, nacionalidad, edad, ataque, defensa, pase, fisico] = partes;
    if (!liga || !codigoClub || !nombre || !posicion) return;
    porLiga[liga] = porLiga[liga] || {};
    porLiga[liga][codigoClub] = porLiga[liga][codigoClub] || [];
    porLiga[liga][codigoClub].push({
      nombre, posicion, posicion_especifica: posicionEspecifica || null,
      nacionalidad: nacionalidad || null, edad: Number(edad) || 24,
      ataque: Number(ataque) || 50, defensa: Number(defensa) || 50,
      pase: Number(pase) || 50, fisico: Number(fisico) || 50,
    });
  });
  return porLiga;
}

function leerArchivoComoTexto(archivo) {
  return new Promise((resolve, reject) => {
    const lector = new FileReader();
    lector.onload = () => resolve(String(lector.result || ''));
    lector.onerror = reject;
    lector.readAsText(archivo);
  });
}

const NUEVO = '__nuevo__';
const NINGUNO = '__ninguno__';
const LIGAS_COMPLETAS_DEFAULT = ['ARG1', 'BRA1', 'ESP1', 'ING1'];

export default function CrearCarreraPage({ API_URL, dataset, onCarreraCreada, onVolver }) {
  const [catalogo, setCatalogo] = useState(null);
  const [nombreDT, setNombreDT] = useState('');
  const [paquetes, setPaquetes] = useState([]);
  const [paqueteElegido, setPaqueteElegido] = useState(NINGUNO); // NINGUNO | NUEVO | id_paquete
  const [nombresPaqueteElegido, setNombresPaqueteElegido] = useState(null);
  const [jugadoresPaqueteElegido, setJugadoresPaqueteElegido] = useState(null);
  const [competenciasPaqueteElegido, setCompetenciasPaqueteElegido] = useState(null);
  const [csvTexto, setCsvTexto] = useState('');
  const [csvJugadoresTexto, setCsvJugadoresTexto] = useState('');
  const [competencias, setCompetencias] = useState({
    CAMPEONES_UEFA: '', EUROPEA_UEFA: '', LIBERTADORES: '', SUDAMERICANA: '',
  });
  const [guardarComoPaquete, setGuardarComoPaquete] = useState(false);
  const [nombrePaqueteNuevo, setNombrePaqueteNuevo] = useState('');
  const [ligaSeleccionada, setLigaSeleccionada] = useState('');
  const [clubSeleccionado, setClubSeleccionado] = useState('');
  const [creando, setCreando] = useState(false);
  const [error, setError] = useState(null);
  const [contratoOfrecido, setContratoOfrecido] = useState(null); // {id_partida, nombre_club, objetivo_temporada, contrato_dt_anios}
  const [descartando, setDescartando] = useState(false);
  const [ligasCompletas, setLigasCompletas] = useState(() => new Set(LIGAS_COMPLETAS_DEFAULT));

  useEffect(() => {
    fetch(`${API_URL}/catalogo/clubes?dataset=ficticia`)
      .then((r) => r.json())
      .then((data) => {
        setCatalogo(data);
        if (data.ligas?.length) setLigaSeleccionada(data.ligas[0].codigo);
      })
      .catch((e) => console.error('Error cargando el catálogo de clubes:', e));
  }, [API_URL]);

  const toggleLigaCompleta = (codigo) => {
    setLigasCompletas((prev) => {
      const next = new Set(prev);
      if (next.has(codigo)) next.delete(codigo);
      else next.add(codigo);
      return next;
    });
  };

  useEffect(() => {
    if (dataset !== 'personalizada') return;
    fetch(`${API_URL}/paquetes-clubes`).then((r) => r.json()).then(setPaquetes).catch((e) => console.error('Error cargando paquetes de clubes:', e));
  }, [API_URL, dataset]);

  // Si se elige un paquete guardado, trae sus nombres/jugadores/competencias para armar el picker.
  useEffect(() => {
    if (paqueteElegido === NINGUNO || paqueteElegido === NUEVO) {
      setNombresPaqueteElegido(null);
      setJugadoresPaqueteElegido(null);
      setCompetenciasPaqueteElegido(null);
      return;
    }
    fetch(`${API_URL}/paquetes-clubes/${paqueteElegido}`)
      .then((r) => r.json())
      .then((data) => {
        setNombresPaqueteElegido(data.nombres_clubes);
        setJugadoresPaqueteElegido(data.jugadores_clubes || null);
        setCompetenciasPaqueteElegido(data.competencias || null);
      })
      .catch((e) => console.error('Error cargando el paquete:', e));
  }, [API_URL, paqueteElegido]);

  const nombresCustom = dataset === 'personalizada'
    ? (paqueteElegido === NUEVO ? parsearCsvClubes(csvTexto) : (nombresPaqueteElegido || null))
    : null;
  const jugadoresCustom = dataset === 'personalizada'
    ? (paqueteElegido === NUEVO ? parsearCsvJugadores(csvJugadoresTexto) : (jugadoresPaqueteElegido || null))
    : null;
  const competenciasCustom = dataset === 'personalizada'
    ? (paqueteElegido === NUEVO
        ? Object.fromEntries(Object.entries(competencias).filter(([, v]) => v.trim()))
        : (competenciasPaqueteElegido || null))
    : null;

  const ligaInfo = catalogo?.ligas.find((l) => l.codigo === ligaSeleccionada);
  // Con datos personalizados el club se guarda con el nombre real solo, sin
  // el código antepuesto (a diferencia del catálogo ficticio, que sí lo
  // lleva) — ver seed.py::crear_partida.
  const clubesLiga = nombresCustom?.[ligaSeleccionada]
    ? nombresCustom[ligaSeleccionada].map(([, n]) => n)
    : (ligaInfo?.clubes || []);

  useEffect(() => {
    setClubSeleccionado('');
  }, [ligaSeleccionada, csvTexto, paqueteElegido]);

  const crear = async (randomizar) => {
    setCreando(true);
    setError(null);
    try {
      // Si el usuario escribió una lista nueva y pidió guardarla, se guarda
      // primero como paquete reusable (separado de esta carrera puntual).
      if (paqueteElegido === NUEVO && guardarComoPaquete && nombrePaqueteNuevo.trim() && nombresCustom && Object.keys(nombresCustom).length) {
        await fetch(`${API_URL}/paquetes-clubes`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            nombre: nombrePaqueteNuevo.trim(),
            nombres_clubes: nombresCustom,
            jugadores_clubes: jugadoresCustom && Object.keys(jugadoresCustom).length ? jugadoresCustom : undefined,
            competencias: competenciasCustom && Object.keys(competenciasCustom).length ? competenciasCustom : undefined,
          }),
        }).catch((e) => console.error('Error guardando el paquete de clubes:', e));
      }

      const res = await fetch(`${API_URL}/partidas`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nombre_dt: nombreDT,
          dataset,
          codigo_liga: randomizar ? undefined : (ligaSeleccionada || undefined),
          nombre_club: randomizar ? undefined : (clubSeleccionado || undefined),
          id_paquete_clubes: typeof paqueteElegido === 'string' && paqueteElegido !== NINGUNO && paqueteElegido !== NUEVO ? paqueteElegido : undefined,
          nombres_clubes_custom: paqueteElegido === NUEVO && nombresCustom && Object.keys(nombresCustom).length ? nombresCustom : undefined,
          jugadores_clubes_custom: paqueteElegido === NUEVO && jugadoresCustom && Object.keys(jugadoresCustom).length ? jugadoresCustom : undefined,
          competencias_custom: paqueteElegido === NUEVO && competenciasCustom && Object.keys(competenciasCustom).length ? competenciasCustom : undefined,
          ligas_completas: Array.from(ligasCompletas),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || 'No se pudo crear la carrera.');
        return;
      }
      // No se entra al juego todavía: primero la directiva presenta sus
      // expectativas y el contrato inicial (esto es la base del sistema de
      // confianza/objetivos que va a vivir en Directiva).
      setContratoOfrecido(data);
    } catch (e) {
      console.error('Error creando la carrera:', e);
      setError('Error de conexión con el servidor.');
    } finally {
      setCreando(false);
    }
  };

  // Si el club randomizado no convence, se borra la carrera recién creada
  // (todavía no se jugó nada) y se vuelve al formulario para probar de nuevo.
  const descartarYVolver = async () => {
    if (!contratoOfrecido) return;
    setDescartando(true);
    try {
      await fetch(`${API_URL}/partidas/${contratoOfrecido.id_partida}`, { method: 'DELETE' });
    } catch (e) {
      console.error('Error descartando la carrera:', e);
    } finally {
      setDescartando(false);
      setContratoOfrecido(null);
    }
  };

  if (contratoOfrecido) {
    return (
      <div className="min-h-screen bg-[#0b1326] text-slate-100 flex items-center justify-center p-6 font-sans">
        <div className="max-w-lg w-full bg-[#121e36] border border-slate-700/60 rounded-3xl p-8 shadow-2xl space-y-6">
          <div>
            <p className="text-xs text-amber-400 font-bold uppercase tracking-wider">Reunión con la directiva</p>
            <h1 className="text-xl font-black text-white mt-1">{contratoOfrecido.nombre_club}</h1>
          </div>

          <div className="bg-[#0b1326] border border-slate-800 rounded-2xl p-5 space-y-4">
            <p className="text-sm text-slate-300 leading-relaxed">
              "Bienvenido, {nombreDT.trim() || 'Técnico'}. Antes de empezar, queremos ser claros sobre lo que esperamos de esta temporada."
            </p>
            <div>
              <p className="text-[11px] text-slate-500 uppercase tracking-wider mb-1">Objetivo de la temporada</p>
              <p className="text-sm font-bold text-amber-300">{contratoOfrecido.objetivo_temporada}</p>
            </div>
            <div>
              <p className="text-[11px] text-slate-500 uppercase tracking-wider mb-1">Oferta de contrato</p>
              <p className="text-sm font-bold text-white">
                {contratoOfrecido.contrato_dt_anios} año{contratoOfrecido.contrato_dt_anios === 1 ? '' : 's'}
                {contratoOfrecido.contrato_dt_fecha_fin ? ` — hasta el ${new Date(`${contratoOfrecido.contrato_dt_fecha_fin}T00:00:00`).toLocaleDateString('es-AR')}` : ''}
              </p>
            </div>
          </div>

          <p className="text-[11px] text-slate-500">
            No cumplir el objetivo con el correr de las temporadas puede costarte la confianza de la directiva — y el puesto.
          </p>

          <button
            onClick={() => onCarreraCreada(contratoOfrecido.id_partida)}
            disabled={descartando}
            className="w-full bg-sky-500 hover:bg-sky-400 disabled:opacity-40 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
          >
            Firmar contrato y asumir el cargo
          </button>
          <button
            onClick={descartarYVolver}
            disabled={descartando}
            className="w-full text-slate-500 hover:text-slate-300 disabled:opacity-40 text-xs font-bold py-1"
          >
            {descartando ? 'Descartando...' : 'No me convence este club, volver a elegir'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0b1326] text-slate-100 flex items-center justify-center p-6 font-sans">
      <div className="max-w-lg w-full bg-[#121e36] border border-slate-700/60 rounded-3xl p-8 shadow-2xl space-y-5">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-black text-white">Crear carrera nueva</h1>
          <button onClick={onVolver} className="text-xs text-slate-500 hover:text-slate-300">← Volver</button>
        </div>

        <div>
          <label className="text-xs text-slate-400 block mb-1">Nombre del DT</label>
          <input
            value={nombreDT}
            onChange={(e) => setNombreDT(e.target.value)}
            placeholder="Tu nombre"
            className="w-full bg-[#0b1326] border border-slate-700 p-3 rounded-xl text-white text-sm"
          />
        </div>

        {dataset === 'personalizada' && (
          <div className="space-y-3">
            <div>
              <label className="text-xs text-slate-400 block mb-1">Nombres de club</label>
              <select
                value={paqueteElegido}
                onChange={(e) => setPaqueteElegido(e.target.value)}
                className="w-full bg-[#0b1326] border border-slate-700 p-3 rounded-xl text-white text-sm"
              >
                <option value={NINGUNO}>Usar nombres ficticios por defecto</option>
                <option value={NUEVO}>Escribir nombres nuevos</option>
                {paquetes.map((p) => (
                  <option key={p.id_paquete} value={p.id_paquete}>
                    {p.nombre} ({p.cantidad_clubes} clubes guardados)
                  </option>
                ))}
              </select>
            </div>

            {paqueteElegido === NUEVO && (
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-slate-400 block mb-1">
                    Clubes — una línea por club: LIGA,CODIGO,NOMBRE,ESCUDO_URL,NOMBRE_COMPETENCIA
                  </label>
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    onChange={async (e) => {
                      const archivo = e.target.files?.[0];
                      if (archivo) setCsvTexto(await leerArchivoComoTexto(archivo));
                      e.target.value = '';
                    }}
                    className="w-full text-xs text-slate-400 file:mr-3 file:bg-slate-800 file:hover:bg-slate-700 file:text-slate-300 file:text-xs file:font-bold file:border-0 file:px-3 file:py-1.5 file:rounded-lg mb-2"
                  />
                  <textarea
                    value={csvTexto}
                    onChange={(e) => setCsvTexto(e.target.value)}
                    placeholder={"ARG1,BOC,Mi Club Favorito\nARG1,RIV,Otro Club,https://ejemplo.com/escudo.png,Mi Liga Real"}
                    rows={4}
                    className="w-full bg-[#0b1326] border border-slate-700 p-3 rounded-xl text-white text-xs font-mono"
                  />
                  <p className="text-[10px] text-slate-500 mt-1">
                    ESCUDO_URL y NOMBRE_COMPETENCIA son opcionales. Las ligas o clubes que no incluyas acá quedan con nombres ficticios
                    por defecto. Vos sos responsable de qué nombres/URLs pongas acá.
                  </p>
                </div>

                <div>
                  <label className="text-xs text-slate-400 block mb-1">
                    Jugadores reales (opcional) — LIGA,CODIGO_CLUB,NOMBRE,POSICION,POSICION_ESPECIFICA,NACIONALIDAD,EDAD,ATAQUE,DEFENSA,PASE,FISICO
                  </label>
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    onChange={async (e) => {
                      const archivo = e.target.files?.[0];
                      if (archivo) setCsvJugadoresTexto(await leerArchivoComoTexto(archivo));
                      e.target.value = '';
                    }}
                    className="w-full text-xs text-slate-400 file:mr-3 file:bg-slate-800 file:hover:bg-slate-700 file:text-slate-300 file:text-xs file:font-bold file:border-0 file:px-3 file:py-1.5 file:rounded-lg mb-2"
                  />
                  <textarea
                    value={csvJugadoresTexto}
                    onChange={(e) => setCsvJugadoresTexto(e.target.value)}
                    placeholder={"ARG1,BOC,Nombre Real,DEL,DC,Argentina,24,82,30,65,78"}
                    rows={4}
                    className="w-full bg-[#0b1326] border border-slate-700 p-3 rounded-xl text-white text-xs font-mono"
                  />
                  <p className="text-[10px] text-slate-500 mt-1">
                    Solo POSICION/NOMBRE/atributos son obligatorios — el resto del plantel de cada club se completa ficticio normal.
                    Los clubes que no incluyas acá quedan 100% ficticios. Vos sos responsable de qué datos pongas acá.
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
                        className="w-full bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs"
                      />
                    ))}
                  </div>
                </div>

                <label className="flex items-center gap-2 text-xs text-slate-400">
                  <input type="checkbox" checked={guardarComoPaquete} onChange={(e) => setGuardarComoPaquete(e.target.checked)} />
                  Guardar esta lista para reusarla en otra carrera
                </label>
                {guardarComoPaquete && (
                  <input
                    value={nombrePaqueteNuevo}
                    onChange={(e) => setNombrePaqueteNuevo(e.target.value)}
                    placeholder="Nombre para esta lista (ej: Mi liga de amigos)"
                    className="w-full bg-[#0b1326] border border-slate-700 p-2.5 rounded-xl text-white text-xs"
                  />
                )}
              </div>
            )}
          </div>
        )}

        {catalogo && (
          <>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Liga</label>
              <select
                value={ligaSeleccionada}
                onChange={(e) => setLigaSeleccionada(e.target.value)}
                className="w-full bg-[#0b1326] border border-slate-700 p-3 rounded-xl text-white text-sm"
              >
                {catalogo.ligas.map((l) => (
                  <option key={l.codigo} value={l.codigo}>{l.nombre} ({l.codigo})</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs text-slate-400 block mb-1">Tu club</label>
              <select
                value={clubSeleccionado}
                onChange={(e) => setClubSeleccionado(e.target.value)}
                className="w-full bg-[#0b1326] border border-slate-700 p-3 rounded-xl text-white text-sm"
              >
                <option value="">— Elegir club —</option>
                {clubesLiga.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs text-slate-400 block mb-1">Ligas a cargar completas</label>
              <p className="text-[10px] text-slate-500 mb-2">
                Una liga "completa" tiene fixture y tabla propia. Las demás quedan "de vista": tienen clubes y jugadores
                (podés scoutearlos, ficharlos, y pueden clasificar a los torneos internacionales) pero sin liga propia jugándose.
                La liga de tu club se carga completa siempre.
              </p>
              <div className="grid grid-cols-2 gap-1.5 max-h-40 overflow-y-auto scroll-slide bg-[#0b1326] border border-slate-700 rounded-xl p-3">
                {['UEFA', 'CONMEBOL'].map((confed) => (
                  <React.Fragment key={confed}>
                    <p className="col-span-2 text-[10px] font-bold text-sky-400 uppercase tracking-wider mt-1 first:mt-0">{confed}</p>
                    {catalogo.ligas.filter((l) => l.confederacion === confed).map((l) => {
                      const forzada = l.codigo === ligaSeleccionada;
                      const marcada = forzada || ligasCompletas.has(l.codigo);
                      return (
                        <label key={l.codigo} className="flex items-center gap-1.5 text-xs text-slate-300">
                          <input
                            type="checkbox"
                            checked={marcada}
                            disabled={forzada}
                            onChange={() => toggleLigaCompleta(l.codigo)}
                            className="accent-sky-500"
                          />
                          {l.nombre} {forzada && <span className="text-slate-500">(la tuya)</span>}
                        </label>
                      );
                    })}
                  </React.Fragment>
                ))}
              </div>
            </div>
          </>
        )}

        {error && <p className="text-xs text-rose-400">{error}</p>}

        <div className="flex gap-3">
          <button
            onClick={() => crear(false)}
            disabled={creando || !clubSeleccionado || !nombreDT.trim()}
            className="flex-1 bg-sky-500 hover:bg-sky-400 disabled:opacity-40 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
          >
            {creando ? 'Creando...' : 'Empezar con este club'}
          </button>
          <button
            onClick={() => crear(true)}
            disabled={creando || !nombreDT.trim()}
            className="flex-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300 font-bold px-4 py-3 rounded-xl text-sm"
          >
            Randomizar
          </button>
        </div>
      </div>
    </div>
  );
}
