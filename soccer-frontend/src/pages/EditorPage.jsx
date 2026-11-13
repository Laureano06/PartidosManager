import PlayerFace from '../components/PlayerFace';
import React, { useEffect, useState } from 'react';
import { parsearCsvClubes, parsearCsvJugadores, leerArchivoComoTexto, combinarEscudosSubidos } from '../utils/csvClubes';

function nombreSinExtension(nombreArchivo) {
  return nombreArchivo.replace(/\.[^/.]+$/, '');
}

function Campo({ label, children }) {
  return (
    <div>
      <label className="text-xs text-slate-400 block mb-1">{label}</label>
      {children}
    </div>
  );
}

const claseInput = "w-full bg-[#121e36] border border-slate-700 p-2.5 rounded-lg text-white text-sm";

// ---------- Crear pack nuevo (CSV, igual que antes + metadata del manifest) ----------
function FormularioNuevoPaquete({ API_URL, onCreado, onCancelar }) {
  const [nombre, setNombre] = useState('');
  const [version, setVersion] = useState('1.0.0');
  const [autor, setAutor] = useState('');
  const [descripcion, setDescripcion] = useState('');
  const [csvTexto, setCsvTexto] = useState('');
  const [csvJugadoresTexto, setCsvJugadoresTexto] = useState('');
  const [competencias, setCompetencias] = useState({
    CAMPEONES_UEFA: '', EUROPEA_UEFA: '', LIBERTADORES: '', SUDAMERICANA: '',
  });
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);
  const [mapaEscudos, setMapaEscudos] = useState({});
  const [subiendoEscudos, setSubiendoEscudos] = useState(false);
  const [erroresEscudos, setErroresEscudos] = useState([]);

  const nombresClubesBase = parsearCsvClubes(csvTexto);
  const nombresClubes = combinarEscudosSubidos(nombresClubesBase, mapaEscudos);
  const jugadoresClubes = parsearCsvJugadores(csvJugadoresTexto);
  const competenciasFiltradas = Object.fromEntries(Object.entries(competencias).filter(([, v]) => v.trim()));
  const cantidadClubes = Object.values(nombresClubes).reduce((acc, arr) => acc + arr.length, 0);
  const cantidadEscudos = Object.keys(mapaEscudos).length;

  const subirEscudos = async (archivos) => {
    setSubiendoEscudos(true);
    setErroresEscudos([]);
    const nuevosErrores = [];
    const nuevoMapa = { ...mapaEscudos };
    for (const archivo of archivos) {
      const codigo = nombreSinExtension(archivo.name).toUpperCase();
      try {
        const formData = new FormData();
        formData.append('archivo', archivo);
        const r = await fetch(`${API_URL}/escudos/subir`, { method: 'POST', body: formData });
        const data = await r.json();
        if (!r.ok) { nuevosErrores.push(`${archivo.name}: ${data.detail || 'no se pudo subir'}`); continue; }
        nuevoMapa[codigo] = data.url;
      } catch (e) {
        console.error('Error subiendo escudo:', e);
        nuevosErrores.push(`${archivo.name}: error de conexión`);
      }
    }
    setMapaEscudos(nuevoMapa);
    setErroresEscudos(nuevosErrores);
    setSubiendoEscudos(false);
  };

  const guardar = async () => {
    if (subiendoEscudos || !nombre.trim() || !cantidadClubes) return;
    setGuardando(true);
    setError(null);
    try {
      const r = await fetch(`${API_URL}/paquetes-clubes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nombre: nombre.trim(), version: version.trim(), autor: autor.trim(), descripcion: descripcion.trim(),
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
        <h2 className="text-sm font-bold text-white">Crear nuevo Data Pack</h2>
        <button onClick={onCancelar} className="text-xs text-slate-400 hover:text-slate-300">Cancelar</button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Campo label="Nombre"><input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Ej: Mi liga de amigos" className={claseInput} /></Campo>
        <Campo label="Versión"><input value={version} onChange={(e) => setVersion(e.target.value)} placeholder="1.0.0" className={claseInput} /></Campo>
        <Campo label="Autor"><input value={autor} onChange={(e) => setAutor(e.target.value)} placeholder="Tu nombre" className={claseInput} /></Campo>
      </div>
      <Campo label="Descripción">
        <input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} placeholder="De qué se trata este Data Pack" className={claseInput} />
      </Campo>

      <div>
        <label htmlFor="editor-csv-clubes" className="text-xs text-slate-400 block mb-1">
          Clubes — una línea por club: LIGA,CODIGO,NOMBRE,ESCUDO_URL,NOMBRE_COMPETENCIA
        </label>
        <input
          type="file" accept=".csv,text/csv" aria-label="Subir archivo CSV de clubes"
          onChange={async (e) => { const a = e.target.files?.[0]; if (a) setCsvTexto(await leerArchivoComoTexto(a)); e.target.value = ''; }}
          className="w-full text-xs text-slate-400 file:mr-3 file:bg-slate-800 file:hover:bg-slate-700 file:text-slate-300 file:text-xs file:font-bold file:border-0 file:px-3 file:py-1.5 file:rounded-lg mb-2"
        />
        <textarea
          id="editor-csv-clubes" value={csvTexto} onChange={(e) => setCsvTexto(e.target.value)}
          placeholder={"ARG1,BOC,Mi Club Favorito\nARG1,RIV,Otro Club,https://ejemplo.com/escudo.png,Mi Liga Real"}
          rows={4} className="w-full bg-[#121e36] border border-slate-700 p-3 rounded-xl text-white text-xs font-mono"
        />
        <p className="text-[10px] text-slate-400 mt-1">
          ESCUDO_URL y NOMBRE_COMPETENCIA son opcionales. Vos sos responsable de qué nombres/URLs pongas acá.
        </p>
      </div>

      <div>
        <label htmlFor="editor-escudos" className="text-xs text-slate-400 block mb-1">
          Escudos (opcional) — subí una imagen por club, nombrada igual que su CODIGO
        </label>
        <input
          id="editor-escudos" type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" multiple
          aria-label="Subir imágenes de escudos" disabled={subiendoEscudos}
          onChange={async (e) => { const archivos = Array.from(e.target.files || []); if (archivos.length) await subirEscudos(archivos); e.target.value = ''; }}
          className="w-full text-xs text-slate-400 file:mr-3 file:bg-slate-800 file:hover:bg-slate-700 file:text-slate-300 file:text-xs file:font-bold file:border-0 file:px-3 file:py-1.5 file:rounded-lg disabled:opacity-50"
        />
        <p className="text-[10px] text-slate-400 mt-1">
          Usá "BOC.png" o "ARG1_BOC.png" para distinguir ligas. La imagen subida reemplaza la URL del CSV. Máximo 2 MB por imagen.
        </p>
        {subiendoEscudos && <p className="text-[11px] text-sky-400 mt-1">Subiendo...</p>}
        {cantidadEscudos > 0 && <p className="text-[11px] text-emerald-400 mt-1">{cantidadEscudos} escudo{cantidadEscudos === 1 ? '' : 's'} cargado{cantidadEscudos === 1 ? '' : 's'}.</p>}
        {erroresEscudos.length > 0 && <ul className="text-[11px] text-rose-400 mt-1 space-y-0.5">{erroresEscudos.map((err) => <li key={err}>{err}</li>)}</ul>}
      </div>

      <div>
        <label htmlFor="editor-csv-jugadores" className="text-xs text-slate-400 block mb-1">
          Jugadores reales (opcional) — LIGA,CODIGO_CLUB,NOMBRE,POSICION,POSICION_ESPECIFICA,NACIONALIDAD,EDAD,ATAQUE,DEFENSA,PASE,FISICO
        </label>
        <input
          type="file" accept=".csv,text/csv" aria-label="Subir archivo CSV de jugadores"
          onChange={async (e) => { const a = e.target.files?.[0]; if (a) setCsvJugadoresTexto(await leerArchivoComoTexto(a)); e.target.value = ''; }}
          className="w-full text-xs text-slate-400 file:mr-3 file:bg-slate-800 file:hover:bg-slate-700 file:text-slate-300 file:text-xs file:font-bold file:border-0 file:px-3 file:py-1.5 file:rounded-lg mb-2"
        />
        <textarea
          id="editor-csv-jugadores" value={csvJugadoresTexto} onChange={(e) => setCsvJugadoresTexto(e.target.value)}
          placeholder={"ARG1,BOC,Nombre Real,DEL,DC,Argentina,24,82,30,65,78"} rows={4}
          className="w-full bg-[#121e36] border border-slate-700 p-3 rounded-xl text-white text-xs font-mono"
        />
        <p className="text-[10px] text-slate-400 mt-1">Los clubes que no incluyas acá quedan con plantel 100% ficticio.</p>
      </div>

      <div>
        <label className="text-xs text-slate-400 block mb-1">Copas internacionales (opcional)</label>
        <div className="grid grid-cols-2 gap-2">
          {[
            ['CAMPEONES_UEFA', 'Copa top UEFA'], ['EUROPEA_UEFA', 'Copa 2ª UEFA'],
            ['LIBERTADORES', 'Copa top CONMEBOL'], ['SUDAMERICANA', 'Copa 2ª CONMEBOL'],
          ].map(([clave, etiqueta]) => (
            <input
              key={clave} value={competencias[clave]} onChange={(e) => setCompetencias((prev) => ({ ...prev, [clave]: e.target.value }))}
              placeholder={etiqueta} aria-label={etiqueta} className="w-full bg-[#121e36] border border-slate-700 p-2 rounded-lg text-white text-xs"
            />
          ))}
        </div>
      </div>

      {error && <p className="text-xs text-rose-400">{error}</p>}

      <button
        onClick={guardar} disabled={guardando || subiendoEscudos || !nombre.trim() || !cantidadClubes}
        className="w-full bg-sky-500 hover:bg-sky-400 disabled:opacity-40 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
      >
        {guardando ? 'Creando...' : `Crear Data Pack (${cantidadClubes} club${cantidadClubes === 1 ? '' : 'es'})`}
      </button>
    </div>
  );
}

// ---------- Importar .pmpack ----------
function ImportarPack({ API_URL, onImportado, onCancelar }) {
  const [preview, setPreview] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [instalando, setInstalando] = useState(false);
  const [error, setError] = useState(null);

  const elegirArchivo = async (archivo) => {
    setCargando(true);
    setError(null);
    setPreview(null);
    try {
      const formData = new FormData();
      formData.append('archivo', archivo);
      const r = await fetch(`${API_URL}/paquetes-clubes/importar`, { method: 'POST', body: formData });
      const data = await r.json();
      if (!r.ok) { setError(data.detail || 'No se pudo leer el .pmpack.'); return; }
      setPreview(data);
    } catch (e) {
      console.error('Error importando pmpack:', e);
      setError('Error de conexión con el servidor.');
    } finally {
      setCargando(false);
    }
  };

  const instalar = async () => {
    setInstalando(true);
    setError(null);
    try {
      const r = await fetch(`${API_URL}/paquetes-clubes/importar/confirmar`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(preview),
      });
      const data = await r.json();
      if (!r.ok) { setError(data.detail || 'No se pudo instalar el pack.'); return; }
      onImportado();
    } catch (e) {
      console.error('Error confirmando importación:', e);
      setError('Error de conexión con el servidor.');
    } finally {
      setInstalando(false);
    }
  };

  return (
    <div className="bg-[#0b1326] border border-slate-800 rounded-2xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold text-white">Importar Data Pack</h2>
        <button onClick={onCancelar} className="text-xs text-slate-400 hover:text-slate-300">Cancelar</button>
      </div>

      {!preview && (
        <>
          <input
            type="file" accept=".pmpack" aria-label="Elegir archivo .pmpack"
            onChange={(e) => { const a = e.target.files?.[0]; if (a) elegirArchivo(a); e.target.value = ''; }}
            disabled={cargando}
            className="w-full text-xs text-slate-400 file:mr-3 file:bg-slate-800 file:hover:bg-slate-700 file:text-slate-300 file:text-xs file:font-bold file:border-0 file:px-3 file:py-1.5 file:rounded-lg disabled:opacity-50"
          />
          {cargando && <p className="text-xs text-sky-400">Leyendo el pack...</p>}
        </>
      )}

      {error && <p className="text-xs text-rose-400">{error}</p>}

      {preview && (
        <div className="space-y-3">
          <div className="bg-[#121e36] border border-slate-800 rounded-xl p-4 space-y-1.5 text-sm">
            <p className="font-bold text-white">{preview.manifest.name}</p>
            <p className="text-xs text-slate-400">{preview.manifest.description}</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-400 pt-2">
              <p>Versión: <span className="text-slate-200 font-bold">{preview.manifest.version}</span></p>
              <p>Autor: <span className="text-slate-200 font-bold">{preview.manifest.author || '—'}</span></p>
              <p>Clubes: <span className="text-slate-200 font-bold">{preview.conteos.numberOfClubs}</span></p>
              <p>Jugadores: <span className="text-slate-200 font-bold">{preview.conteos.numberOfPlayers}</span></p>
              <p>Ligas: <span className="text-slate-200 font-bold">{preview.conteos.numberOfLeagues}</span></p>
              <p>Assets: <span className="text-slate-200 font-bold">{preview.manifest.assetsIncluded ? 'Sí' : 'No'}</span></p>
            </div>
            {preview.configuracion?.rellenar_planteles === false && <p className="text-xs text-sky-300">Planteles del pack: no se agregarán jugadores ficticios al crear la carrera.</p>}
          </div>

          {preview.avisos.length > 0 && (
            <div className="bg-amber-950/40 border border-amber-500/40 rounded-xl p-3 space-y-1">
              {preview.avisos.map((a) => <p key={a} className="text-xs text-amber-300">{a}</p>)}
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={instalar} disabled={instalando}
              className="flex-1 bg-sky-500 hover:bg-sky-400 disabled:opacity-40 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
            >
              {instalando ? 'Instalando...' : 'Instalar'}
            </button>
            <button onClick={() => setPreview(null)} disabled={instalando} className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-3 rounded-xl text-sm">
              Elegir otro archivo
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------- Formulario individual de club ----------
function FormularioClub({ API_URL, idPaquete, liga, club, onGuardado, onBorrado, onCerrar }) {
  const esNuevo = club == null;
  const metaInicial = club?.meta || {};
  const [codigo, setCodigo] = useState(club?.codigo || '');
  const [nombre, setNombre] = useState(club?.nombre || '');
  const [escudoUrl, setEscudoUrl] = useState(club?.escudoUrl || '');
  const [nombreCompetencia, setNombreCompetencia] = useState(club?.nombreCompetencia || '');
  const [ciudad, setCiudad] = useState(metaInicial.ciudad || '');
  const [estadio, setEstadio] = useState(metaInicial.estadio || '');
  const [capacidad, setCapacidad] = useState(metaInicial.capacidad || '');
  const [manager, setManager] = useState(metaInicial.manager || '');
  const [staff, setStaff] = useState(metaInicial.staff || '');
  const [subiendo, setSubiendo] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [confirmarBorrado, setConfirmarBorrado] = useState(false);
  const [error, setError] = useState(null);

  const subirEscudo = async (archivo) => {
    setSubiendo(true);
    try {
      const formData = new FormData();
      formData.append('archivo', archivo);
      const r = await fetch(`${API_URL}/escudos/subir`, { method: 'POST', body: formData });
      const data = await r.json();
      if (r.ok) setEscudoUrl(data.url);
      else setError(data.detail || 'No se pudo subir el escudo.');
    } catch (e) {
      console.error('Error subiendo escudo:', e);
      setError('Error de conexión al subir el escudo.');
    } finally {
      setSubiendo(false);
    }
  };

  const guardar = async () => {
    if (!codigo.trim() || !nombre.trim()) { setError('Código y nombre son obligatorios.'); return; }
    setGuardando(true);
    setError(null);
    try {
      const r = await fetch(`${API_URL}/paquetes-clubes/${idPaquete}/clubes/${liga}/${codigo.trim().toUpperCase()}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nombre: nombre.trim(), escudo_url: escudoUrl, nombre_competencia: nombreCompetencia, ciudad, estadio, capacidad, manager, staff }),
      });
      if (!r.ok) { const d = await r.json().catch(() => ({})); setError(d.detail || 'No se pudo guardar.'); return; }
      onGuardado();
    } catch (e) {
      console.error('Error guardando club:', e);
      setError('Error de conexión con el servidor.');
    } finally {
      setGuardando(false);
    }
  };

  const borrar = async () => {
    setGuardando(true);
    try {
      await fetch(`${API_URL}/paquetes-clubes/${idPaquete}/clubes/${liga}/${club.codigo}`, { method: 'DELETE' });
      onBorrado();
    } catch (e) {
      console.error('Error borrando club:', e);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="bg-[#121e36] border border-slate-700 rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-white">{esNuevo ? `Nuevo club en ${liga}` : `Editar ${club.nombre}`}</h3>
        <button onClick={onCerrar} className="text-xs text-slate-400 hover:text-slate-300">✕</button>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Campo label="Código (ID estable)">
          <input value={codigo} onChange={(e) => setCodigo(e.target.value.toUpperCase())} disabled={!esNuevo} className={`${claseInput} disabled:opacity-50`} />
        </Campo>
        <Campo label="Nombre"><input value={nombre} onChange={(e) => setNombre(e.target.value)} className={claseInput} /></Campo>
      </div>

      <Campo label="Escudo">
        <div className="flex items-center gap-3">
          {escudoUrl && <img src={escudoUrl.startsWith('/') ? `${API_URL}${escudoUrl}` : escudoUrl} alt="" className="w-10 h-10 rounded-lg object-contain bg-[#0b1326] border border-slate-800" />}
          <input
            type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" disabled={subiendo}
            onChange={(e) => { const a = e.target.files?.[0]; if (a) subirEscudo(a); e.target.value = ''; }}
            className="flex-1 text-xs text-slate-400 file:mr-3 file:bg-slate-800 file:hover:bg-slate-700 file:text-slate-300 file:text-xs file:font-bold file:border-0 file:px-3 file:py-1.5 file:rounded-lg disabled:opacity-50"
          />
        </div>
        {subiendo && <p className="text-[11px] text-sky-400 mt-1">Subiendo...</p>}
      </Campo>

      <Campo label="Nombre de la liga/competencia (opcional)"><input value={nombreCompetencia} onChange={(e) => setNombreCompetencia(e.target.value)} className={claseInput} /></Campo>

      <div className="grid grid-cols-2 gap-3">
        <Campo label="Ciudad"><input value={ciudad} onChange={(e) => setCiudad(e.target.value)} className={claseInput} /></Campo>
        <Campo label="Estadio"><input value={estadio} onChange={(e) => setEstadio(e.target.value)} className={claseInput} /></Campo>
        <Campo label="Capacidad"><input value={capacidad} onChange={(e) => setCapacidad(e.target.value)} className={claseInput} /></Campo>
        <Campo label="Manager"><input value={manager} onChange={(e) => setManager(e.target.value)} className={claseInput} /></Campo>
      </div>
      <Campo label="Staff"><input value={staff} onChange={(e) => setStaff(e.target.value)} className={claseInput} /></Campo>
      <p className="text-[10px] text-slate-500">Ciudad/Estadio/Manager/Staff todavía no los usa el motor del juego — viajan guardados en el pack para más adelante.</p>

      {error && <p className="text-xs text-rose-400">{error}</p>}

      <div className="flex gap-2">
        <button onClick={guardar} disabled={guardando} className="flex-1 bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-bold px-3 py-2 rounded-lg text-xs">
          {guardando ? 'Guardando...' : 'Guardar'}
        </button>
        {!esNuevo && !confirmarBorrado && (
          <button onClick={() => setConfirmarBorrado(true)} className="text-rose-400 hover:text-rose-300 text-xs font-bold px-3 py-2 rounded-lg hover:bg-rose-950/60">Borrar</button>
        )}
        {confirmarBorrado && (
          <>
            <button onClick={borrar} disabled={guardando} className="bg-rose-500 hover:bg-rose-400 text-slate-950 font-bold px-3 py-2 rounded-lg text-xs">Confirmar</button>
            <button onClick={() => setConfirmarBorrado(false)} className="bg-slate-800 text-slate-300 px-3 py-2 rounded-lg text-xs">Cancelar</button>
          </>
        )}
      </div>
    </div>
  );
}

// ---------- Formulario individual de jugador ----------
function FormularioJugador({ API_URL, idPaquete, liga, codigoClub, indice, jugador, onGuardado, onBorrado, onCerrar }) {
  const esNuevo = jugador == null;
  const [nombre, setNombre] = useState(jugador?.nombre || '');
  const [fotoUrl, setFotoUrl] = useState(jugador?.foto_url || jugador?.datos_fuente?.image || '');
  const [subiendoFoto, setSubiendoFoto] = useState(false);
  const subirFoto = async (file) => {
    if (!file) return;
    setSubiendoFoto(true); setError(null);
    try {
      const body = new FormData(); body.append('archivo', file);
      const r = await fetch(`${API_URL}/escudos/subir`, { method: 'POST', body });
      const d = await r.json(); if (!r.ok) throw new Error(d.detail || 'No se pudo subir la cara');
      setFotoUrl(d.url);
    } catch (e) { setError(e.message); } finally { setSubiendoFoto(false); }
  };
  const [posicion, setPosicion] = useState(jugador?.posicion || 'DEL');
  const [posicionEspecifica, setPosicionEspecifica] = useState(jugador?.posicion_especifica || '');
  const [nacionalidad, setNacionalidad] = useState(jugador?.nacionalidad || '');
  const [edad, setEdad] = useState(String(jugador?.edad ?? 24));
  const [ataque, setAtaque] = useState(String(jugador?.ataque ?? 50));
  const [defensa, setDefensa] = useState(String(jugador?.defensa ?? 50));
  const [pase, setPase] = useState(String(jugador?.pase ?? 50));
  const [fisico, setFisico] = useState(String(jugador?.fisico ?? 50));
  const [guardando, setGuardando] = useState(false);
  const [confirmarBorrado, setConfirmarBorrado] = useState(false);
  const [error, setError] = useState(null);

  const guardar = async () => {
    if (subiendoFoto) return;
    if (!nombre.trim()) { setError('El jugador necesita un nombre.'); return; }
    setGuardando(true);
    setError(null);
    try {
      const r = await fetch(`${API_URL}/paquetes-clubes/${idPaquete}/jugadores/${liga}/${codigoClub}/${indice}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nombre: nombre.trim(), posicion, posicion_especifica: posicionEspecifica, nacionalidad, foto_url: fotoUrl,
          edad: Number(edad) || 24, ataque: (ataque === '' ? 50 : Number(ataque)), defensa: (defensa === '' ? 50 : Number(defensa)),
          pase: (pase === '' ? 50 : Number(pase)), fisico: (fisico === '' ? 50 : Number(fisico)),
        }),
      });
      if (!r.ok) { const d = await r.json().catch(() => ({})); setError(d.detail || 'No se pudo guardar.'); return; }
      onGuardado();
    } catch (e) {
      console.error('Error guardando jugador:', e);
      setError('Error de conexión con el servidor.');
    } finally {
      setGuardando(false);
    }
  };

  const borrar = async () => {
    setGuardando(true);
    try {
      await fetch(`${API_URL}/paquetes-clubes/${idPaquete}/jugadores/${liga}/${codigoClub}/${indice}`, { method: 'DELETE' });
      onBorrado();
    } catch (e) {
      console.error('Error borrando jugador:', e);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="bg-[#121e36] border border-slate-700 rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-white">{esNuevo ? 'Nuevo jugador' : `Editar ${jugador.nombre}`}</h3>
        <button onClick={onCerrar} className="text-xs text-slate-400 hover:text-slate-300">✕</button>
      </div>

      <div className="flex items-center gap-4">
        <PlayerFace player={{ foto_url: fotoUrl }} API_URL={API_URL} className="editor-face" />
        <div className="space-y-2 flex-1">
          <label className="block text-xs">Cara del jugador (PNG, JPG o WEBP, hasta 2 MB)
            <input type="file" accept="image/png,image/jpeg,image/webp" disabled={subiendoFoto} onChange={(e) => subirFoto(e.target.files?.[0])} className="block mt-2 w-full" />
          </label>
          <label className="block text-xs">URL de la cara<input value={fotoUrl} onChange={(e) => setFotoUrl(e.target.value)} className={claseInput} /></label>
          {subiendoFoto && <p role="status">Subiendo cara…</p>}
        </div>
      </div>
      {jugador?.datos_fuente && (
        <div className="text-xs text-slate-400 space-y-1">
          <p>Fuente: {jugador.datos_fuente.source?.provider || 'Pack importado'}</p>
          <p>Nacimiento: {jugador.datos_fuente.date_of_birth || 'Sin dato'} · Dorsal: {jugador.datos_fuente.shirt_number || jugador.datos_fuente.jersey_number || 'Sin dato'}</p>
          {jugador.campos_estimados?.length > 0 && <p>Valores de juego estimados: {jugador.campos_estimados.join(', ')}.</p>}
        </div>
      )}

      <Campo label="Nombre"><input value={nombre} onChange={(e) => setNombre(e.target.value)} className={claseInput} /></Campo>

      <div className="grid grid-cols-2 gap-3">
        <Campo label="Posición">
          <select value={posicion} onChange={(e) => setPosicion(e.target.value)} className={claseInput}>
            <option value="POR">POR</option><option value="DEF">DEF</option><option value="MED">MED</option><option value="DEL">DEL</option>
          </select>
        </Campo>
        <Campo label="Posición específica"><input value={posicionEspecifica} onChange={(e) => setPosicionEspecifica(e.target.value)} placeholder="Ej: DC, MCO" className={claseInput} /></Campo>
        <Campo label="Nacionalidad"><input value={nacionalidad} onChange={(e) => setNacionalidad(e.target.value)} className={claseInput} /></Campo>
        <Campo label="Edad"><input type="number" value={edad} onChange={(e) => setEdad(e.target.value)} className={claseInput} /></Campo>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <Campo label="Ataque"><input type="number" min={1} max={99} value={ataque} onChange={(e) => setAtaque(e.target.value)} className={claseInput} /></Campo>
        <Campo label="Defensa"><input type="number" min={1} max={99} value={defensa} onChange={(e) => setDefensa(e.target.value)} className={claseInput} /></Campo>
        <Campo label="Pase"><input type="number" min={1} max={99} value={pase} onChange={(e) => setPase(e.target.value)} className={claseInput} /></Campo>
        <Campo label="Físico"><input type="number" min={1} max={99} value={fisico} onChange={(e) => setFisico(e.target.value)} className={claseInput} /></Campo>
      </div>

      {error && <p className="text-xs text-rose-400">{error}</p>}

      <div className="flex gap-2">
        <button onClick={guardar} disabled={guardando} className="flex-1 bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-bold px-3 py-2 rounded-lg text-xs">
          {guardando ? 'Guardando...' : 'Guardar'}
        </button>
        {!esNuevo && !confirmarBorrado && (
          <button onClick={() => setConfirmarBorrado(true)} className="text-rose-400 hover:text-rose-300 text-xs font-bold px-3 py-2 rounded-lg hover:bg-rose-950/60">Borrar</button>
        )}
        {confirmarBorrado && (
          <>
            <button onClick={borrar} disabled={guardando} className="bg-rose-500 hover:bg-rose-400 text-slate-950 font-bold px-3 py-2 rounded-lg text-xs">Confirmar</button>
            <button onClick={() => setConfirmarBorrado(false)} className="bg-slate-800 text-slate-300 px-3 py-2 rounded-lg text-xs">Cancelar</button>
          </>
        )}
      </div>
    </div>
  );
}

// ---------- Detalle de un pack: General | Clubes | Jugadores | Competencias ----------
function DetallePack({ API_URL, idPaquete, onCerrar, onBorrado }) {
  const [detalle, setDetalle] = useState(null);
  const [tab, setTab] = useState('general');
  const [reporteCaras, setReporteCaras] = useState('');
  const [busquedaClub, setBusquedaClub] = useState('');
  const [clubActivo, setClubActivo] = useState(null); // {liga, codigo} | 'nuevo:{liga}' | null
  const [ligaParaNuevoClub, setLigaParaNuevoClub] = useState('');
  const [clubParaJugadores, setClubParaJugadores] = useState(null); // {liga, codigo}
  const [jugadorActivo, setJugadorActivo] = useState(null); // indice | 'nuevo' | null
  const [confirmarBorrado, setConfirmarBorrado] = useState(false);
  const [borrando, setBorrando] = useState(false);
  const [general, setGeneral] = useState(null);
  const [guardandoGeneral, setGuardandoGeneral] = useState(false);
  const [competencias, setCompetencias] = useState({ CAMPEONES_UEFA: '', EUROPEA_UEFA: '', LIBERTADORES: '', SUDAMERICANA: '' });
  const [guardandoCompetencias, setGuardandoCompetencias] = useState(false);

  const cargar = () => {
    fetch(`${API_URL}/paquetes-clubes/${idPaquete}`).then((r) => r.json()).then((data) => {
      setDetalle(data);
      setGeneral({ nombre: data.nombre, version: data.version, autor: data.autor, descripcion: data.descripcion });
      setCompetencias((prev) => ({ ...prev, ...(data.competencias || {}) }));
    }).catch((e) => console.error('Error cargando el pack:', e));
  };

  useEffect(cargar, [API_URL, idPaquete]);

  if (!detalle) return <p className="text-xs text-slate-400">Cargando...</p>;

  const guardarGeneral = async () => {
    setGuardandoGeneral(true);
    try {
      await fetch(`${API_URL}/paquetes-clubes/${idPaquete}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(general),
      });
      cargar();
    } catch (e) {
      console.error('Error guardando datos generales:', e);
    } finally {
      setGuardandoGeneral(false);
    }
  };

  const guardarCompetencias = async () => {
    setGuardandoCompetencias(true);
    try {
      const filtradas = Object.fromEntries(Object.entries(competencias).filter(([, v]) => v.trim()));
      await fetch(`${API_URL}/paquetes-clubes/${idPaquete}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ competencias: filtradas }),
      });
      cargar();
    } catch (e) {
      console.error('Error guardando competencias:', e);
    } finally {
      setGuardandoCompetencias(false);
    }
  };

  const borrarPack = async () => {
    setBorrando(true);
    try {
      const r = await fetch(`${API_URL}/paquetes-clubes/${idPaquete}`, { method: 'DELETE' });
      if (r.ok) onBorrado();
      else { const d = await r.json().catch(() => ({})); alert(d.detail || 'No se pudo borrar.'); }
    } catch (e) {
      console.error('Error borrando pack:', e);
    } finally {
      setBorrando(false);
    }
  };

  const clubesFiltrados = [];
  for (const [liga, clubes] of Object.entries(detalle.nombres_clubes)) {
    for (const fila of clubes) {
      const [codigo, nombre, escudoUrl, nombreCompetencia] = fila;
      if (busquedaClub && !nombre.toLowerCase().includes(busquedaClub.toLowerCase()) && !codigo.toLowerCase().includes(busquedaClub.toLowerCase())) continue;
      clubesFiltrados.push({ liga, codigo, nombre, escudoUrl, nombreCompetencia, meta: detalle.metadata_clubes?.[liga]?.[codigo] || {} });
    }
  }

  const jugadoresDelClub = clubParaJugadores
    ? (detalle.jugadores_clubes?.[clubParaJugadores.liga]?.[clubParaJugadores.codigo] || [])
    : [];

  return (
    <div className="bg-[#0b1326] border border-slate-800 rounded-2xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-white">{detalle.nombre}</h2>
          <p className="text-[11px] text-slate-500">v{detalle.version} · {detalle.numberOfClubs} clubes · {detalle.numberOfPlayers} jugadores · {detalle.numberOfLeagues} ligas</p>
        </div>
        <button onClick={onCerrar} className="text-xs text-slate-400 hover:text-slate-300">← Volver</button>
      </div>

      <div className="flex gap-1 bg-[#121e36] p-1 rounded-xl border border-slate-800 overflow-x-auto">
        {['general', 'clubes', 'jugadores', 'competencias'].map((t) => (
          <button
            key={t} onClick={() => setTab(t)}
            className={`px-3 py-1.5 rounded-lg text-[11px] font-bold whitespace-nowrap ${tab === t ? 'bg-sky-500 text-slate-950' : 'text-slate-400 hover:text-white'}`}
          >
            {t === 'general' ? 'General' : t === 'clubes' ? 'Clubes' : t === 'jugadores' ? 'Jugadores' : 'Competencias'}
          </button>
        ))}
      </div>

      {tab === 'general' && general && (
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Campo label="Nombre"><input value={general.nombre} onChange={(e) => setGeneral((g) => ({ ...g, nombre: e.target.value }))} className={claseInput} /></Campo>
            <Campo label="Versión"><input value={general.version} onChange={(e) => setGeneral((g) => ({ ...g, version: e.target.value }))} className={claseInput} /></Campo>
            <Campo label="Autor"><input value={general.autor} onChange={(e) => setGeneral((g) => ({ ...g, autor: e.target.value }))} className={claseInput} /></Campo>
          </div>
          <Campo label="Descripción"><input value={general.descripcion} onChange={(e) => setGeneral((g) => ({ ...g, descripcion: e.target.value }))} className={claseInput} /></Campo>
          <button onClick={guardarGeneral} disabled={guardandoGeneral} className="bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-2 rounded-lg text-xs">
            {guardandoGeneral ? 'Guardando...' : 'Guardar cambios'}
          </button>

          <div className="pt-3 border-t border-slate-800">
            {!confirmarBorrado ? (
              <button
                onClick={() => setConfirmarBorrado(true)} disabled={detalle.es_oficial}
                className="text-rose-400 hover:text-rose-300 disabled:text-slate-600 disabled:cursor-not-allowed text-xs font-bold"
                title={detalle.es_oficial ? 'Este pack viene incluido con el juego — duplicalo para editar una copia borrable' : undefined}
              >
                Borrar este Data Pack
              </button>
            ) : (
              <div className="flex gap-2 items-center">
                <span className="text-xs text-rose-300">¿Confirmar? No se puede deshacer.</span>
                <button onClick={borrarPack} disabled={borrando} className="bg-rose-500 hover:bg-rose-400 text-slate-950 font-bold px-3 py-1.5 rounded-lg text-xs">Sí, borrar</button>
                <button onClick={() => setConfirmarBorrado(false)} className="bg-slate-800 text-slate-300 px-3 py-1.5 rounded-lg text-xs">Cancelar</button>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'clubes' && (
        <div className="space-y-3">
          <input
            type="text" value={busquedaClub} onChange={(e) => setBusquedaClub(e.target.value)}
            placeholder="Buscar club por nombre o código..." className={claseInput}
          />

          {clubActivo && (
            <FormularioClub
              API_URL={API_URL} idPaquete={idPaquete}
              liga={typeof clubActivo === 'object' ? clubActivo.liga : ligaParaNuevoClub}
              club={typeof clubActivo === 'object' ? clubActivo : null}
              onCerrar={() => setClubActivo(null)}
              onGuardado={() => { setClubActivo(null); cargar(); }}
              onBorrado={() => { setClubActivo(null); cargar(); }}
            />
          )}

          {!clubActivo && (
            <>
              <div className="space-y-1.5 max-h-80 overflow-y-auto scroll-slide">
                {clubesFiltrados.map((c) => (
                  <button
                    key={`${c.liga}-${c.codigo}`} onClick={() => setClubActivo(c)}
                    className="w-full flex items-center justify-between bg-[#121e36] border border-slate-800 hover:border-sky-500/40 rounded-lg px-3 py-2 text-xs text-left"
                  >
                    <span className="text-slate-200 font-bold flex items-center gap-2">
                      {c.escudoUrl && <img src={c.escudoUrl.startsWith('/') ? `${API_URL}${c.escudoUrl}` : c.escudoUrl} alt="" className="w-8 h-8 object-contain" />}
                      {c.nombre}
                    </span>
                    <span className="text-slate-500">{c.liga} · {c.codigo}</span>
                  </button>
                ))}
                {clubesFiltrados.length === 0 && <p className="text-xs text-slate-600 text-center py-4">Sin resultados.</p>}
              </div>

              <div className="flex gap-2 items-center pt-2 border-t border-slate-800">
                <select value={ligaParaNuevoClub} onChange={(e) => setLigaParaNuevoClub(e.target.value)} className={`${claseInput} flex-1`}>
                  <option value="">Elegir liga...</option>
                  {Object.keys(detalle.nombres_clubes).map((l) => <option key={l} value={l}>{l}</option>)}
                </select>
                <button
                  onClick={() => setClubActivo('nuevo')} disabled={!ligaParaNuevoClub}
                  className="bg-sky-500 hover:bg-sky-400 disabled:opacity-40 text-slate-950 font-bold px-3 py-2.5 rounded-lg text-xs whitespace-nowrap"
                >
                  + Agregar club
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {tab === 'jugadores' && (
        <div className="space-y-3">
          <label className="block p-3 border border-slate-700 text-xs">
            Cargar caras en lote (hasta 200). Nombre de archivo: ID del proveedor o LIGA_CODIGO_INDICE, por ejemplo ARG1_BOC_0.png.
            <input type="file" multiple accept="image/png,image/jpeg,image/webp" className="block mt-2" onChange={async (e) => {
              const input = e.currentTarget; if (!input.files?.length) return;
              input.disabled = true;
              try {
                const body = new FormData(); for (const file of input.files) body.append('archivos', file);
                const r = await fetch(`${API_URL}/paquetes-clubes/${idPaquete}/caras`, { method: 'POST', body });
                const data = await r.json(); if (!r.ok) throw new Error(data.detail || 'No se pudieron subir las caras');
                cargar();
                setReporteCaras(`${data.cargadas} caras guardadas. ${data.sin_coincidencia.length} archivos sin jugador coincidente.`);
              } catch (err) { setReporteCaras(err.message); } finally { input.disabled = false; input.value = ''; }
            }} />
            {reporteCaras && <p role="status" className="mt-2 text-sky-300">{reporteCaras}</p>}
          </label>
          {!clubParaJugadores ? (
            <>
              <p className="text-xs text-slate-400">Elegí un club para ver/editar sus jugadores reales.</p>
              <input type="text" value={busquedaClub} onChange={(e) => setBusquedaClub(e.target.value)} placeholder="Buscar club..." className={claseInput} />
              <div className="space-y-1.5 max-h-80 overflow-y-auto scroll-slide">
                {clubesFiltrados.map((c) => {
                  const cant = detalle.jugadores_clubes?.[c.liga]?.[c.codigo]?.length || 0;
                  return (
                    <button
                      key={`${c.liga}-${c.codigo}`} onClick={() => setClubParaJugadores(c)}
                      className="w-full flex items-center justify-between bg-[#121e36] border border-slate-800 hover:border-sky-500/40 rounded-lg px-3 py-2 text-xs text-left"
                    >
                      <span className="text-slate-200 font-bold">{c.nombre}</span>
                      <span className="text-slate-500">{cant} jugador{cant === 1 ? '' : 'es'} real{cant === 1 ? '' : 'es'}</span>
                    </button>
                  );
                })}
              </div>
            </>
          ) : jugadorActivo !== null ? (
            <FormularioJugador
              API_URL={API_URL} idPaquete={idPaquete} liga={clubParaJugadores.liga} codigoClub={clubParaJugadores.codigo}
              indice={jugadorActivo === 'nuevo' ? jugadoresDelClub.length : jugadorActivo}
              jugador={jugadorActivo === 'nuevo' ? null : jugadoresDelClub[jugadorActivo]}
              onCerrar={() => setJugadorActivo(null)}
              onGuardado={() => { setJugadorActivo(null); cargar(); }}
              onBorrado={() => { setJugadorActivo(null); cargar(); }}
            />
          ) : (
            <>
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold text-white">{clubParaJugadores.nombre}</p>
                <button onClick={() => setClubParaJugadores(null)} className="text-[11px] text-slate-400 hover:text-slate-300">← Otro club</button>
              </div>
              <div className="space-y-1.5 max-h-72 overflow-y-auto scroll-slide">
                {jugadoresDelClub.map((j, i) => (
                  <button
                    key={i} onClick={() => setJugadorActivo(i)}
                    className="w-full flex items-center justify-between bg-[#121e36] border border-slate-800 hover:border-sky-500/40 rounded-lg px-3 py-2 text-xs text-left"
                  >
                    <span className="text-slate-200 font-bold">{j.nombre}</span>
                    <span className="text-slate-500">{j.posicion_especifica || j.posicion} · {j.edad} años</span>
                  </button>
                ))}
                {jugadoresDelClub.length === 0 && <p className="text-xs text-slate-600 text-center py-4">Sin jugadores reales cargados para este club.</p>}
              </div>
              <button onClick={() => setJugadorActivo('nuevo')} className="w-full bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold px-3 py-2 rounded-lg text-xs">
                + Agregar jugador
              </button>
            </>
          )}
        </div>
      )}

      {tab === 'competencias' && (
        <div className="space-y-3">
          {detalle.configuracion?.competencias?.map((c) => (
            <div key={`${c.id}-${c.game_code || ''}`} className="text-xs text-slate-300 border-b border-slate-800 py-2">
              <strong>{c.name}</strong> · {c.country || 'Internacional'}
              {c.season?.name && <span className="text-slate-500"> · {c.season.name}</span>}
            </div>
          ))}
          {detalle.configuracion?.competencias?.length > 0 && <p className="text-xs text-slate-400">El pack conserva las competiciones y sus datos de origen. Los calendarios y formatos de disputa se generan con las reglas del juego.</p>}
          <p className="text-xs text-slate-400">Nombres personalizados para las copas internacionales de las carreras creadas con este pack.</p>
          <div className="grid grid-cols-2 gap-2">
            {[
              ['CAMPEONES_UEFA', 'Copa top UEFA'], ['EUROPEA_UEFA', 'Copa 2ª UEFA'],
              ['LIBERTADORES', 'Copa top CONMEBOL'], ['SUDAMERICANA', 'Copa 2ª CONMEBOL'],
            ].map(([clave, etiqueta]) => (
              <input
                key={clave} value={competencias[clave] || ''} onChange={(e) => setCompetencias((prev) => ({ ...prev, [clave]: e.target.value }))}
                placeholder={etiqueta} className={claseInput}
              />
            ))}
          </div>
          <button onClick={guardarCompetencias} disabled={guardandoCompetencias} className="bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-2 rounded-lg text-xs">
            {guardandoCompetencias ? 'Guardando...' : 'Guardar'}
          </button>
        </div>
      )}
    </div>
  );
}

// ---------- Lista principal (Data Pack Manager) ----------
export default function EditorPage({ API_URL, onVolver }) {
  const [packs, setPacks] = useState(null);
  const [vista, setVista] = useState('lista'); // 'lista' | 'nuevo' | 'importar' | id_paquete (número)
  const [busqueda, setBusqueda] = useState('');
  const [exportando, setExportando] = useState(null);

  const cargarPacks = () => {
    setPacks(null);
    fetch(`${API_URL}/paquetes-clubes`)
      .then((r) => r.json())
      .then(setPacks)
      .catch((e) => { console.error('Error cargando Data Packs:', e); setPacks([]); });
  };

  useEffect(cargarPacks, [API_URL]);

  const duplicar = async (p) => {
    try {
      const r = await fetch(`${API_URL}/paquetes-clubes/${p.id_paquete}/duplicar`, { method: 'POST' });
      const data = await r.json();
      if (r.ok) { cargarPacks(); setVista(data.id_paquete); }
    } catch (e) {
      console.error('Error duplicando pack:', e);
    }
  };

  const exportar = async (p) => {
    setExportando(p.id_paquete);
    try {
      const r = await fetch(`${API_URL}/paquetes-clubes/${p.id_paquete}/exportar`);
      if (!r.ok) return;
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${p.pack_id || 'pack'}.pmpack`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Error exportando pack:', e);
    } finally {
      setExportando(null);
    }
  };

  const packsFiltrados = (packs || []).filter((p) => p.nombre.toLowerCase().includes(busqueda.toLowerCase()));

  return (
    <div className="min-h-screen bg-[#0b1326] text-slate-100 flex items-center justify-center p-6 font-sans">
      <div className="max-w-xl w-full bg-[#121e36] border border-slate-700/60 rounded-3xl p-8 shadow-2xl space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-sky-400 font-bold uppercase tracking-wider">Editor</p>
            <h1 className="text-xl font-black text-white mt-1">Data Packs</h1>
          </div>
          <button onClick={onVolver} className="text-xs text-slate-400 hover:text-slate-300">← Volver al inicio</button>
        </div>

        {vista === 'nuevo' && (
          <FormularioNuevoPaquete API_URL={API_URL} onCancelar={() => setVista('lista')} onCreado={() => { setVista('lista'); cargarPacks(); }} />
        )}

        {vista === 'importar' && (
          <ImportarPack API_URL={API_URL} onCancelar={() => setVista('lista')} onImportado={() => { setVista('lista'); cargarPacks(); }} />
        )}

        {typeof vista === 'number' && (
          <DetallePack API_URL={API_URL} idPaquete={vista} onCerrar={() => { setVista('lista'); cargarPacks(); }} onBorrado={() => { setVista('lista'); cargarPacks(); }} />
        )}

        {vista === 'lista' && (
          <>
            <p className="text-xs text-slate-400">
              Un Data Pack es un archivo <code className="text-sky-400">.pmpack</code> con clubes, jugadores reales y escudos —
              elegilo al crear una carrera nueva, editalo acá, o compartilo exportándolo.
            </p>

            {packs && packs.length > 1 && (
              <input type="text" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} placeholder="Buscar Data Pack..." className={claseInput} />
            )}

            {packs === null && <p className="text-sm text-slate-400 text-center py-6">Cargando Data Packs...</p>}

            {packs !== null && (
              <div className="space-y-2 max-h-96 overflow-y-auto scroll-slide pr-1">
                {packsFiltrados.map((p) => (
                  <div key={p.pack_id} className="bg-[#0b1326] border border-slate-700 rounded-xl p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="min-w-0">
                        <p className="font-bold text-white text-sm truncate">
                          {p.nombre}
                          {p.es_oficial && <span className="ml-2 text-[9px] font-bold px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 align-middle">OFICIAL</span>}
                          {p.tipo === 'PROCEDURAL' && <span className="ml-2 text-[9px] font-bold px-1.5 py-0.5 rounded bg-sky-950 text-sky-400 border border-sky-500/40 align-middle">GENERADOR</span>}
                        </p>
                        <p className="text-[11px] text-slate-400 mt-0.5">
                          v{p.version} · {p.autor || 'sin autor'} {p.tipo !== 'PROCEDURAL' && `· ${p.numberOfClubs} clubes · ${p.numberOfPlayers} jugadores`}
                        </p>
                      </div>
                    </div>
                    <p className="text-[11px] text-slate-500 line-clamp-2">{p.descripcion}</p>
                    <div className="flex gap-2 flex-wrap pt-1">
                      <button onClick={() => setVista(p.id_paquete)} disabled={p.tipo === 'PROCEDURAL'} className="text-[11px] font-bold px-2.5 py-1 rounded-lg bg-sky-950 text-sky-300 border border-sky-500/40 disabled:opacity-30 disabled:cursor-not-allowed">
                        {p.tipo === 'PROCEDURAL' ? 'No editable' : 'Ver / Editar'}
                      </button>
                      <button onClick={() => duplicar(p)} disabled={p.tipo === 'PROCEDURAL'} className="text-[11px] font-bold px-2.5 py-1 rounded-lg bg-slate-800 text-slate-300 disabled:opacity-30 disabled:cursor-not-allowed">
                        Duplicar
                      </button>
                      <button onClick={() => exportar(p)} disabled={p.tipo === 'PROCEDURAL' || exportando === p.id_paquete} className="text-[11px] font-bold px-2.5 py-1 rounded-lg bg-slate-800 text-slate-300 disabled:opacity-30 disabled:cursor-not-allowed">
                        {p.id_paquete != null && exportando === p.id_paquete ? 'Exportando...' : 'Exportar'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="flex gap-3">
              <button onClick={() => setVista('nuevo')} className="flex-1 bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm">
                + Crear nuevo Data Pack
              </button>
              <button onClick={() => setVista('importar')} className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold px-4 py-3 rounded-xl text-sm">
                Importar Data Pack
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
