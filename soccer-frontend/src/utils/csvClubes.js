// Parsea líneas "LIGA,CODIGO,NOMBRE[,ESCUDO_URL[,NOMBRE_COMPETENCIA]]" en el
// formato que espera el backend: { ARG1: [["BOC","Xeneize FC", escudo?, competencia?], ...] }.
function filasCsv(texto) {
  const filas = [];
  let fila = [], campo = '', entreComillas = false;
  const csv = texto.replace(/^\uFEFF/, '');
  for (let i = 0; i <= csv.length; i++) {
    const c = csv[i];
    if (c === '"') {
      if (entreComillas && csv[i + 1] === '"') { campo += '"'; i++; }
      else entreComillas = !entreComillas;
    } else if (!entreComillas && (c === ',' || c === '\n' || c === undefined)) {
      fila.push(campo.trim()); campo = '';
      if (c !== ',') {
        if (fila.some(Boolean) && !fila[0].startsWith('#')) filas.push(fila);
        fila = [];
      }
    } else if (c !== undefined) campo += c;
  }
  return filas;
}

export function parsearCsvClubes(texto) {
  const porLiga = {};
  filasCsv(texto).forEach((partes) => {
    if (partes.length < 3) return;
    const [liga, codigo] = partes.slice(0, 2).map((v) => v.toUpperCase());
    const [, , nombre, escudoUrl, nombreCompetencia] = partes;
    if (liga === 'LIGA' && codigo === 'CODIGO') return;
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
export function parsearCsvJugadores(texto) {
  const porLiga = {};
  filasCsv(texto).forEach((partes) => {
    if (partes.length < 11) return;
    const [liga, codigoClub] = partes.slice(0, 2).map((v) => v.toUpperCase());
    const [, , nombre, posicionBase, posicionEspecifica, nacionalidad, edad, ataque, defensa, pase, fisico] = partes;
    const posicion = posicionBase.toUpperCase();
    if (liga === 'LIGA' && codigoClub === 'CODIGO_CLUB') return;
    const numero = (valor, defecto) => valor === '' ? defecto : (Number.isFinite(Number(valor)) ? Number(valor) : valor);
    if (!liga || !codigoClub || !nombre || !posicion) return;
    porLiga[liga] = porLiga[liga] || {};
    porLiga[liga][codigoClub] = porLiga[liga][codigoClub] || [];
    porLiga[liga][codigoClub].push({
      nombre, posicion, posicion_especifica: posicionEspecifica || null,
      nacionalidad: nacionalidad || null, edad: numero(edad, 24),
      ataque: numero(ataque, 50), defensa: numero(defensa, 50),
      pase: numero(pase, 50), fisico: numero(fisico, 50),
    });
  });
  return porLiga;
}

// Igual que el mapeo "ID de club → archivo" que usan los packs de escudos de
// FM (un config.xml ligando cada club a su imagen) — acá el "ID" es
// simplemente el nombre del archivo sin extensión, que tiene que coincidir
// con el CODIGO de club del CSV. La imagen subida reemplaza la URL del CSV.
// LIGA_CODIGO permite distinguir códigos repetidos entre ligas.
export function combinarEscudosSubidos(porLiga, mapaEscudosPorCodigo) {
  const resultado = {};
  for (const [liga, clubes] of Object.entries(porLiga)) {
    resultado[liga] = clubes.map((fila) => {
      const [codigo, nombre, escudoUrl, competencia] = fila;
      const escudoFinal = mapaEscudosPorCodigo[`${liga}_${codigo}`.toUpperCase()]
        || mapaEscudosPorCodigo[codigo.toUpperCase()] || escudoUrl || '';
      if (competencia) return [codigo, nombre, escudoFinal, competencia];
      if (escudoFinal) return [codigo, nombre, escudoFinal];
      return [codigo, nombre];
    });
  }
  return resultado;
}

export function leerArchivoComoTexto(archivo) {
  return new Promise((resolve, reject) => {
    const lector = new FileReader();
    lector.onload = () => resolve(String(lector.result || ''));
    lector.onerror = reject;
    lector.readAsText(archivo);
  });
}
