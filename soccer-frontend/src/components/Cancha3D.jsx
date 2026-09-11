import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { FORMACIONES_SLOTS } from '../utils/formaciones';

const ANCHO = 40;
const LARGO = 62;
const COLOR_LOCAL = 0x38bdf8;
const COLOR_VISITA = 0xf43f5e;
const COLOR_ARQUERO = 0xfbbf24;
// Ángulo de reposo tipo cámara principal de transmisión de TV: elevada, a
// un costado a la altura del medio campo, mostrando la cancha completa de
// punta a punta (no la vista cenital de un plano táctico, ni un primer
// plano — eso queda solo para el acercamiento del gol).
const CAMARA_REPOSO_POS = { x: 70, y: 36, z: 0 };
const CAMARA_REPOSO_TARGET = { x: 0, y: 1, z: 0 };

// Busca a qué jugador (mesh real) corresponde el nombre completo real de un
// evento — `nombres` está alineado 1 a 1 con `jugadores` (mismo orden en el
// que se armaron los slots), así que el índice del nombre es el índice del
// jugador.
function buscarJugadorPorNombre(jugadores, nombres, nombreCompleto) {
  if (!nombreCompleto || !nombres) return null;
  const idx = nombres.findIndex((n) => n === nombreCompleto);
  return idx !== -1 ? jugadores[idx] : null;
}

function slotsATablero(codigoFormacion, esLocal) {
  const slots = FORMACIONES_SLOTS[codigoFormacion] || FORMACIONES_SLOTS['4-4-2'];
  return slots.map((s) => {
    const x = (s.x / 100 - 0.5) * ANCHO;
    // El local ataca hacia +Z (arco rival), el visitante hacia -Z — su
    // propia formación (arquero y%=8 cerca del arco propio) se refleja.
    const z = esLocal ? -LARGO / 2 + (s.y / 100) * (LARGO / 2 - 2) : LARGO / 2 - (s.y / 100) * (LARGO / 2 - 2);
    return { x, z, posEspecifica: s.posEspecifica, esArquero: s.posEspecifica === 'POR' };
  });
}

// Textura de tribuna con público: puntos de color al azar sobre un fondo
// oscuro, simula la hinchada sin necesitar una imagen externa.
function crearTexturaTribuna() {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 64;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#1e293b';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  const colores = ['#ef4444', '#f8fafc', '#0f172a', '#3b82f6', '#facc15'];
  for (let y = 6; y < canvas.height; y += 5) {
    for (let x = 0; x < canvas.width; x += 5) {
      ctx.fillStyle = colores[Math.floor(Math.random() * colores.length)];
      ctx.fillRect(x + Math.random() * 1.5, y + Math.random() * 1.5, 3, 3);
    }
  }
  const textura = new THREE.CanvasTexture(canvas);
  textura.wrapS = THREE.RepeatWrapping;
  textura.wrapT = THREE.ClampToEdgeWrapping;
  textura.repeat.set(6, 1);
  return textura;
}

// Cartelería perimetral tipo LED, con el nombre del juego (nada de marcas
// reales) repetido a lo largo del cartel.
function crearTexturaPublicidad() {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 64;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#0b1326';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.font = 'bold 30px sans-serif';
  ctx.fillStyle = '#38bdf8';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText('PARTIDOS MANAGER', canvas.width / 2, canvas.height / 2);
  const textura = new THREE.CanvasTexture(canvas);
  textura.wrapS = THREE.RepeatWrapping;
  textura.wrapT = THREE.ClampToEdgeWrapping;
  textura.repeat.set(3, 1);
  return textura;
}

// Red de arco: una grilla dibujada sobre fondo transparente.
function crearTexturaRed() {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext('2d');
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.55)';
  ctx.lineWidth = 1.5;
  for (let i = 0; i <= 128; i += 12) {
    ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, 128); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(128, i); ctx.stroke();
  }
  const textura = new THREE.CanvasTexture(canvas);
  textura.wrapS = THREE.RepeatWrapping;
  textura.wrapT = THREE.RepeatWrapping;
  textura.repeat.set(4, 2);
  return textura;
}

function lineaPiso(escena, ancho, alto, x, z, color = 0xffffff) {
  const geo = new THREE.BoxGeometry(ancho, 0.05, alto);
  const mat = new THREE.MeshBasicMaterial({ color });
  const linea = new THREE.Mesh(geo, mat);
  linea.position.set(x, 0.03, z);
  escena.add(linea);
  return linea;
}

function crearEtiquetaNombre(texto) {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 64;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = 'rgba(11, 19, 38, 0.85)';
  ctx.fillRect(0, 18, 256, 28);
  ctx.font = 'bold 26px sans-serif';
  ctx.fillStyle = '#ffffff';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(texto, 128, 32);
  const textura = new THREE.CanvasTexture(canvas);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: textura, depthTest: false }));
  sprite.scale.set(3, 0.75, 1);
  return sprite;
}

const COLOR_PIEL = 0xd8a878;
const COLOR_MEDIA = 0xf1f5f9;
const COLOR_BOTIN = 0x1c1c1c;

// Pivote a la altura de la cadera para que la pierna gire desde ahí (no
// desde su propio centro) — así el balanceo de correr/patear se ve como
// una pierna real, no un cilindro rotando sobre sí mismo.
function crearPierna(matMedia, matBotin, x) {
  const pivote = new THREE.Group();
  pivote.position.set(x, 0.99, 0);
  const pierna = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.14, 0.85, 8), matMedia);
  pierna.position.y = -0.425;
  pierna.castShadow = true;
  pivote.add(pierna);
  const botin = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.14, 0.34), matBotin);
  botin.position.set(0, -0.85 - 0.07, 0.05);
  botin.castShadow = true;
  pivote.add(botin);
  return pivote;
}

// Mismo criterio para el brazo: pivote a la altura del hombro.
function crearBrazo(matKit, x) {
  const pivote = new THREE.Group();
  pivote.position.set(x, 1.6, 0);
  const brazo = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.09, 0.55, 8), matKit);
  brazo.position.y = -0.275;
  brazo.castShadow = true;
  pivote.add(brazo);
  return pivote;
}

// Jugador armado con formas simples (botines, medias, camiseta del color
// del club, brazos, cabeza) en vez de una sola cápsula — así se distingue
// una figura humana real y no un marcador genérico. Las piernas y brazos
// son pivotes rotables (ver `crearPierna`/`crearBrazo`) para poder animar
// trote, sprint y patada desde el loop de `animar()` en vez de solo
// trasladar el grupo entero.
function crearJugador(color, nombre) {
  const grupo = new THREE.Group();
  const matKit = new THREE.MeshStandardMaterial({ color, roughness: 0.6 });
  const matPiel = new THREE.MeshStandardMaterial({ color: COLOR_PIEL, roughness: 0.7 });
  const matMedia = new THREE.MeshStandardMaterial({ color: COLOR_MEDIA, roughness: 0.8 });
  const matBotin = new THREE.MeshStandardMaterial({ color: COLOR_BOTIN, roughness: 0.5 });

  const piernaIzq = crearPierna(matMedia, matBotin, -0.16);
  const piernaDer = crearPierna(matMedia, matBotin, 0.16);
  grupo.add(piernaIzq, piernaDer);

  const torso = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.34, 0.7, 8), matKit);
  torso.position.y = 1.34;
  torso.castShadow = true;
  grupo.add(torso);

  const brazoIzq = crearBrazo(matKit, -0.42);
  const brazoDer = crearBrazo(matKit, 0.42);
  grupo.add(brazoIzq, brazoDer);

  const cabeza = new THREE.Mesh(new THREE.SphereGeometry(0.22, 12, 12), matPiel);
  cabeza.position.y = 1.91;
  cabeza.castShadow = true;
  grupo.add(cabeza);

  if (nombre) {
    const etiqueta = crearEtiquetaNombre(nombre);
    etiqueta.position.y = cabeza.position.y + 0.5;
    grupo.add(etiqueta);
  }

  grupo.userData = { piernaIzq, piernaDer, brazoIzq, brazoDer };
  return grupo;
}

// Estadio simple (tribunas + torres de luz), al estilo de los managers de
// fútbol clásicos: no hace falta que sea detallado, alcanza con que la
// cancha no quede flotando en la nada.
function crearEstadio(escena) {
  const grupo = new THREE.Group();
  const margen = 4;
  const anchoGrada = 8;
  // Bien alta a propósito: con la cámara fija, cualquier tribuna más baja
  // deja ver el color de fondo por arriba (se ve como "cielo" abierto).
  const alturaGrada = 26;
  const matGrada = new THREE.MeshStandardMaterial({ map: crearTexturaTribuna(), roughness: 0.9 });
  const matTecho = new THREE.MeshStandardMaterial({ color: 0x111827, roughness: 0.8 });
  const matPublicidad = new THREE.MeshBasicMaterial({ map: crearTexturaPublicidad() });
  const alturaPublicidad = 1.2;

  // Tribuna en escalones (4 niveles, cada uno más atrás y más alto que el
  // anterior — como una platea real) en vez de un solo bloque plano: así se
  // ve profundidad real desde la cámara fija, no una pared lisa.
  const NIVELES = 4;
  const profNivel = anchoGrada / NIVELES;
  const altNivel = alturaGrada / NIVELES;

  // Tribuna lateral: solo del lado OPUESTO a la cámara fija (que está del
  // lado positivo de X) — la del mismo lado taparía la cancha entera.
  for (let i = 0; i < NIVELES; i++) {
    const nivel = new THREE.Mesh(new THREE.BoxGeometry(profNivel, altNivel, LARGO + margen * 2), matGrada);
    nivel.position.set(-(ANCHO / 2 + margen + i * profNivel + profNivel / 2), i * altNivel + altNivel / 2, 0);
    nivel.receiveShadow = true;
    grupo.add(nivel);
  }
  const techoLateral = new THREE.Mesh(new THREE.BoxGeometry(profNivel + 2, 0.4, LARGO + margen * 2 + 2), matTecho);
  techoLateral.position.set(-(ANCHO / 2 + margen + (NIVELES - 1) * profNivel + profNivel / 2), alturaGrada + 0.5, 0);
  grupo.add(techoLateral);

  [-1, 1].forEach((lado) => {
    const cartel = new THREE.Mesh(new THREE.BoxGeometry(0.15, alturaPublicidad, LARGO), matPublicidad);
    cartel.position.set(lado * (ANCHO / 2 + 0.6), alturaPublicidad / 2, 0);
    grupo.add(cartel);
  });

  [-1, 1].forEach((lado) => {
    for (let i = 0; i < NIVELES; i++) {
      const nivel = new THREE.Mesh(new THREE.BoxGeometry(ANCHO + margen * 2 + anchoGrada * 2, altNivel, profNivel), matGrada);
      nivel.position.set(0, i * altNivel + altNivel / 2, lado * (LARGO / 2 + margen + i * profNivel + profNivel / 2));
      nivel.receiveShadow = true;
      grupo.add(nivel);
    }
    const cartel = new THREE.Mesh(new THREE.BoxGeometry(ANCHO, alturaPublicidad, 0.15), matPublicidad);
    cartel.position.set(0, alturaPublicidad / 2, lado * (LARGO / 2 + 0.6));
    grupo.add(cartel);
  });

  // Paredón alto detrás de cada tribuna, apilado justo arriba de su techo:
  // con la cámara fija no hace falta calcular el frustum exacto — alcanza
  // con que cualquier resto de "cielo" quede tapado por más estructura.
  const matFondoAlto = new THREE.MeshBasicMaterial({ color: 0x1e293b });
  const alturaExtra = 95;
  const fondoLateral = new THREE.Mesh(new THREE.BoxGeometry(1, alturaExtra, LARGO + margen * 2 + 8), matFondoAlto);
  fondoLateral.position.set(-(ANCHO / 2 + margen + anchoGrada / 2), alturaGrada + alturaExtra / 2, 0);
  grupo.add(fondoLateral);
  [-1, 1].forEach((lado) => {
    const fondo = new THREE.Mesh(new THREE.BoxGeometry(ANCHO + margen * 2 + anchoGrada * 2 + 8, alturaExtra, 1), matFondoAlto);
    fondo.position.set(0, alturaGrada + alturaExtra / 2, lado * (LARGO / 2 + margen + anchoGrada / 2));
    grupo.add(fondo);
  });

  const matPoste = new THREE.MeshStandardMaterial({ color: 0xcbd5e1 });
  const matFoco = new THREE.MeshStandardMaterial({ color: 0xfef9c3, emissive: 0xfef08a, emissiveIntensity: 0.6 });
  [-1, 1].forEach((lx) => [-1, 1].forEach((lz) => {
    const x = lx * (ANCHO / 2 + margen + anchoGrada + 2);
    const z = lz * (LARGO / 2 + margen + anchoGrada + 2);
    const poste = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.4, 22, 8), matPoste);
    poste.position.set(x, 11, z);
    grupo.add(poste);
    const foco = new THREE.Mesh(new THREE.BoxGeometry(3, 1.6, 0.6), matFoco);
    foco.position.set(x, 21.5, z);
    foco.lookAt(0, 0, 0);
    grupo.add(foco);
    const luz = new THREE.PointLight(0xfff7d6, 0.5, 60);
    luz.position.copy(foco.position);
    grupo.add(luz);
  }));

  escena.add(grupo);
  return grupo;
}

export default function Cancha3D({ formacionLocal = '4-4-2', formacionVisita = '4-3-3', eventoGol, eventoReaccion, colorLocal, colorVisita, nombresLocal = [], nombresVisita = [], equipoPresiona = null }) {
  const montajeRef = useRef(null);
  const estadoRef = useRef({});

  useEffect(() => {
    const contenedor = montajeRef.current;
    if (!contenedor) return;

    const escena = new THREE.Scene();
    escena.background = new THREE.Color(0x0b1326);
    escena.fog = new THREE.Fog(0x0b1326, 50, 110);

    const camara = new THREE.PerspectiveCamera(22, contenedor.clientWidth / contenedor.clientHeight, 0.1, 200);
    camara.position.set(CAMARA_REPOSO_POS.x, CAMARA_REPOSO_POS.y, CAMARA_REPOSO_POS.z);
    camara.lookAt(CAMARA_REPOSO_TARGET.x, CAMARA_REPOSO_TARGET.y, CAMARA_REPOSO_TARGET.z);

    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setSize(contenedor.clientWidth, contenedor.clientHeight);
    renderer.shadowMap.enabled = true;
    contenedor.appendChild(renderer.domElement);

    // Cámara fija tipo transmisión de TV — no orbitable por el usuario y sin
    // ningún acercamiento automático: el gol se ve desde este mismo plano.

    // Luces
    escena.add(new THREE.AmbientLight(0xffffff, 0.6));
    const sol = new THREE.DirectionalLight(0xffffff, 1.1);
    sol.position.set(20, 40, 10);
    sol.castShadow = true;
    sol.shadow.mapSize.set(1024, 1024);
    escena.add(sol);

    // Cancha
    const cesped = new THREE.Mesh(
      new THREE.PlaneGeometry(ANCHO + 6, LARGO + 6),
      new THREE.MeshStandardMaterial({ color: 0x1b7a3a, roughness: 1 }),
    );
    cesped.rotation.x = -Math.PI / 2;
    cesped.receiveShadow = true;
    escena.add(cesped);
    crearEstadio(escena);
    // Franjas de corte de césped, alternadas
    for (let i = 0; i < 8; i++) {
      if (i % 2 !== 0) continue;
      const franja = new THREE.Mesh(
        new THREE.PlaneGeometry(ANCHO + 6, (LARGO + 6) / 8),
        new THREE.MeshStandardMaterial({ color: 0x1f8a42, roughness: 1 }),
      );
      franja.rotation.x = -Math.PI / 2;
      franja.position.set(0, 0.001, -LARGO / 2 - 3 + ((LARGO + 6) / 8) * (i + 0.5));
      escena.add(franja);
    }

    // Líneas
    lineaPiso(escena, ANCHO, 0.15, 0, -LARGO / 2); // línea de fondo local
    lineaPiso(escena, ANCHO, 0.15, 0, LARGO / 2); // línea de fondo visita
    lineaPiso(escena, 0.15, LARGO, -ANCHO / 2, 0); // banda izquierda
    lineaPiso(escena, 0.15, LARGO, ANCHO / 2, 0); // banda derecha
    lineaPiso(escena, ANCHO, 0.15, 0, 0); // mitad de cancha
    const circulo = new THREE.Mesh(
      new THREE.RingGeometry(6.9, 7, 48),
      new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide }),
    );
    circulo.rotation.x = -Math.PI / 2;
    circulo.position.y = 0.03;
    escena.add(circulo);
    // Áreas
    [-1, 1].forEach((lado) => {
      lineaPiso(escena, 18, 0.15, 0, lado * (LARGO / 2 - 9));
      lineaPiso(escena, 0.15, 9, -9, lado * (LARGO / 2 - 4.5));
      lineaPiso(escena, 0.15, 9, 9, lado * (LARGO / 2 - 4.5));
    });

    // Arcos (marco simple)
    [-1, 1].forEach((lado) => {
      const arco = new THREE.Group();
      const mat = new THREE.MeshStandardMaterial({ color: 0xf1f5f9 });
      const postes = [-3.66, 3.66].map((px) => {
        const poste = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 2.44, 8), mat);
        poste.position.set(px, 1.22, 0);
        return poste;
      });
      const travesano = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 7.32, 8), mat);
      travesano.rotation.z = Math.PI / 2;
      travesano.position.set(0, 2.44, 0);
      postes.forEach((p) => arco.add(p));
      arco.add(travesano);

      const matRed = new THREE.MeshBasicMaterial({ map: crearTexturaRed(), transparent: true, side: THREE.DoubleSide });
      const redFondo = new THREE.Mesh(new THREE.PlaneGeometry(7.32, 2.6), matRed);
      redFondo.position.set(0, 1.3, lado * 1.4);
      arco.add(redFondo);
      [-3.66, 3.66].forEach((px) => {
        const redLateral = new THREE.Mesh(new THREE.PlaneGeometry(1.4, 2.6), matRed);
        redLateral.position.set(px, 1.3, lado * 0.7);
        redLateral.rotation.y = Math.PI / 2;
        arco.add(redLateral);
      });

      arco.position.set(0, 0, lado * LARGO / 2);
      escena.add(arco);
    });

    // Jugadores
    const cLocal = colorLocal || COLOR_LOCAL;
    const cVisita = colorVisita || COLOR_VISITA;
    const jugadoresLocal = slotsATablero(formacionLocal, true).map((s, i) => {
      const nombre = (nombresLocal[i] || '').split(' ').pop();
      const j = crearJugador(s.esArquero ? COLOR_ARQUERO : cLocal, nombre);
      j.position.set(s.x, 0, s.z);
      escena.add(j);
      return { mesh: j, base: { x: s.x, z: s.z }, esArquero: s.esArquero };
    });
    const jugadoresVisita = slotsATablero(formacionVisita, false).map((s, i) => {
      const nombre = (nombresVisita[i] || '').split(' ').pop();
      const j = crearJugador(s.esArquero ? COLOR_ARQUERO : cVisita, nombre);
      j.position.set(s.x, 0, s.z);
      escena.add(j);
      return { mesh: j, base: { x: s.x, z: s.z }, esArquero: s.esArquero };
    });

    // Pelota
    const pelota = new THREE.Mesh(
      new THREE.SphereGeometry(0.35, 16, 16),
      new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.3 }),
    );
    pelota.position.set(0, 0.35, 0);
    pelota.castShadow = true;
    escena.add(pelota);

    estadoRef.current = { escena, camara, renderer, jugadoresLocal, jugadoresVisita, pelota, animGol: null, equipoPresiona, nombresLocal, nombresVisita };

    let vivo = true;
    const reloj = new THREE.Clock();
    const lerp = (a, b, t) => a + (b - a) * Math.min(1, Math.max(0, t));

    // Juego ambiental: fuera de los goles, la pelota va pasando de jugador
    // en jugador para que la cancha se sienta como un partido en curso, no
    // jugadores parados esperando el próximo evento real. Los pases respetan
    // el equipo casi siempre (juego real, no una pelota que salta al azar
    // entre los 22) y de vez en cuando hay una "intercepción" al rival.
    // El arquero no sale a driblear en el juego ambiental (se ve rarísimo un
    // arquero corriendo por la mitad de la cancha) — se arma un pool aparte
    // sin arqueros para elegir portador.
    const jugadoresLocalDeCampo = jugadoresLocal.filter((j) => !j.esArquero);
    const jugadoresVisitaDeCampo = jugadoresVisita.filter((j) => !j.esArquero);
    const todosDeCampo = [...jugadoresLocalDeCampo, ...jugadoresVisitaDeCampo];
    const esLocalJugador = (j) => jugadoresLocal.includes(j);
    let portadorActual = null;
    const elegirNuevoPortador = () => {
      const anterior = portadorActual;
      const referencia = anterior ? anterior.mesh.position : pelota.position;
      const propioEquipo = anterior ? (esLocalJugador(anterior) ? jugadoresLocalDeCampo : jugadoresVisitaDeCampo) : todosDeCampo;
      const equipoRival = anterior ? (esLocalJugador(anterior) ? jugadoresVisitaDeCampo : jugadoresLocalDeCampo) : [];
      // El equipo que va perdiendo presiona más: le cuesta más al que tiene
      // la pelota retenerla si el rival es quien está "presionando", y le
      // cuesta menos si el que la tiene es justamente el que presiona — así
      // el 3D refleja el estado real del marcador, no una moneda al aire.
      const nombreAnterior = anterior ? (esLocalJugador(anterior) ? 'local' : 'visitante') : null;
      const presiona = estadoRef.current.equipoPresiona;
      let probIntercepcion = 0.22;
      if (presiona && nombreAnterior) {
        probIntercepcion = presiona === nombreAnterior ? 0.14 : 0.32;
      }
      const intercepcion = anterior && Math.random() < probIntercepcion;
      const grupo = intercepcion ? equipoRival : propioEquipo;
      const candidatos = [...grupo]
        .filter((j) => j !== anterior)
        .sort((a, b) => {
          const da = (a.mesh.position.x - referencia.x) ** 2 + (a.mesh.position.z - referencia.z) ** 2;
          const db = (b.mesh.position.x - referencia.x) ** 2 + (b.mesh.position.z - referencia.z) ** 2;
          return da - db;
        })
        .slice(0, 4);
      portadorActual = candidatos[Math.floor(Math.random() * candidatos.length)] || todosDeCampo[0];
      estadoRef.current.animAmbiente = { progreso: 0, desde: { x: pelota.position.x, z: pelota.position.z }, pasador: anterior };
    };
    elegirNuevoPortador();
    const intervaloAmbiente = setInterval(() => {
      if (!estadoRef.current.animGol) elegirNuevoPortador();
    }, 2600);
    const animar = () => {
      if (!vivo) return;
      requestAnimationFrame(animar);
      const t = reloj.getElapsedTime();

      const anim = estadoRef.current.animGol;
      const reaccion = estadoRef.current.animReaccion;
      const involucrados = anim
        ? new Set([anim.corredor1?.mesh.id, anim.corredor2?.mesh.id].filter(Boolean))
        : new Set([portadorActual?.mesh.id, reaccion?.jugador?.mesh.id].filter(Boolean));

      [...jugadoresLocal, ...jugadoresVisita].forEach((j, i) => {
        if (involucrados && involucrados.has(j.mesh.id)) return;
        // Deriva leve hacia donde está la pelota — se ve como si el equipo
        // se acomodara según por dónde viene la jugada, no un vaivén ciego.
        const haciaBalonX = (pelota.position.x - j.base.x) * 0.08;
        const haciaBalonZ = (pelota.position.z - j.base.z) * 0.08;
        j.mesh.position.y = Math.sin(t * 1.6 + i) * 0.05;
        j.mesh.position.x = j.base.x + Math.sin(t * 0.5 + i * 1.3) * 2.2 + haciaBalonX;
        j.mesh.position.z = j.base.z + Math.cos(t * 0.4 + i * 1.7) * 2.2 + haciaBalonZ;
        // Trote permanente (piernas y brazos en fase opuesta) para que se
        // vea movimiento real y no jugadores estáticos deslizándose.
        const fase = t * 4 + i;
        const { piernaIzq, piernaDer, brazoIzq, brazoDer } = j.mesh.userData;
        piernaIzq.rotation.x = Math.sin(fase) * 0.35;
        piernaDer.rotation.x = -Math.sin(fase) * 0.35;
        brazoIzq.rotation.x = -Math.sin(fase) * 0.3;
        brazoDer.rotation.x = Math.sin(fase) * 0.3;
      });

      if (reaccion) {
        // Tarjeta: protesta con los dos brazos. Lesión: se dobla y cae unos
        // instantes. Sube y baja de intensidad (entra, sostiene, sale) en
        // vez de aparecer/desaparecer de golpe.
        reaccion.progreso = Math.min(1, reaccion.progreso + 0.011);
        const p = reaccion.progreso;
        const intensidad = p < 0.15 ? p / 0.15 : p > 0.85 ? (1 - p) / 0.15 : 1;
        const { piernaIzq, piernaDer, brazoIzq, brazoDer } = reaccion.jugador.mesh.userData;
        if (reaccion.tipo === 'LESION') {
          reaccion.jugador.mesh.position.y = -0.4 * intensidad;
          piernaIzq.rotation.x = 0.4 * intensidad;
          piernaDer.rotation.x = 0.4 * intensidad;
          brazoIzq.rotation.x = 0.5 * intensidad;
          brazoDer.rotation.x = 0.5 * intensidad;
        } else {
          brazoIzq.rotation.x = -Math.PI * 0.55 * intensidad;
          brazoDer.rotation.x = -Math.PI * 0.55 * intensidad;
        }
        if (reaccion.progreso >= 1) estadoRef.current.animReaccion = null;
      }

      if (anim) {
        // Jugada de gol en 3 tramos: pase al primer corredor, pase/gambeta
        // al segundo, remate con arco hacia el arco — simula una jugada
        // real en vez de que la pelota viaje sola en línea recta.
        anim.progreso = Math.min(1, anim.progreso + 0.016);
        const p = anim.progreso;
        let bx, bz;
        let altura = 0.35;
        const faseSprint = t * 11;
        const correr = (corredor, intensidad) => {
          if (!corredor) return;
          const { piernaIzq, piernaDer, brazoIzq, brazoDer } = corredor.mesh.userData;
          piernaIzq.rotation.x = Math.sin(faseSprint) * intensidad;
          piernaDer.rotation.x = -Math.sin(faseSprint) * intensidad;
          brazoIzq.rotation.x = -Math.sin(faseSprint) * (intensidad * 0.7);
          brazoDer.rotation.x = Math.sin(faseSprint) * (intensidad * 0.7);
        };
        // La pelota controlada va pegada al pie del corredor, un paso
        // adelante en la dirección hacia la que corre — no viaja sola en
        // paralelo. Recién se suelta a volar independiente en el remate.
        const balonControlado = (corredor, objetivoX, objetivoZ) => {
          const dx = objetivoX - corredor.base.x;
          const dz = objetivoZ - corredor.base.z;
          const dist = Math.hypot(dx, dz) || 1;
          return { x: corredor.mesh.position.x + (dx / dist) * 0.7, z: corredor.mesh.position.z + (dz / dist) * 0.7 };
        };

        if (p < 0.35) {
          const local = p / 0.35;
          if (anim.corredor1) {
            anim.corredor1.mesh.position.x = lerp(anim.corredor1.base.x, anim.p1.x, local);
            anim.corredor1.mesh.position.z = lerp(anim.corredor1.base.z, anim.p1.z, local);
            anim.corredor1.mesh.position.y = Math.sin(local * Math.PI) * 0.08;
            const conBalon = balonControlado(anim.corredor1, anim.p1.x, anim.p1.z);
            bx = conBalon.x;
            bz = conBalon.z;
          } else {
            bx = lerp(anim.p0.x, anim.p1.x, local);
            bz = lerp(anim.p0.z, anim.p1.z, local);
          }
          correr(anim.corredor1, 0.7);
        } else if (p < 0.7) {
          const local = (p - 0.35) / 0.35;
          if (anim.corredor1) anim.corredor1.mesh.position.set(anim.p1.x, 0, anim.p1.z);
          if (anim.corredor2) {
            anim.corredor2.mesh.position.x = lerp(anim.corredor2.base.x, anim.p2.x, local);
            anim.corredor2.mesh.position.z = lerp(anim.corredor2.base.z, anim.p2.z, local);
            anim.corredor2.mesh.position.y = Math.sin(local * Math.PI) * 0.08;
            const conBalon = balonControlado(anim.corredor2, anim.p2.x, anim.p2.z);
            bx = conBalon.x;
            bz = conBalon.z;
          } else {
            bx = lerp(anim.p1.x, anim.p2.x, local);
            bz = lerp(anim.p1.z, anim.p2.z, local);
          }
          correr(anim.corredor2, 0.7);
        } else {
          const local = (p - 0.7) / 0.3;
          bx = lerp(anim.p2.x, anim.p3.x, local);
          bz = lerp(anim.p2.z, anim.p3.z, local);
          altura = 0.35 + Math.sin(local * Math.PI) * 2.2;
          if (anim.corredor2) {
            anim.corredor2.mesh.position.x = lerp(anim.p2.x, anim.p3.x, local * 0.4);
            anim.corredor2.mesh.position.z = lerp(anim.p2.z, anim.p3.z, local * 0.4);
            // Patada: la pierna de remate se dispara hacia adelante y
            // vuelve, en vez de solo trotar hasta la pelota.
            const golpe = Math.sin(Math.min(1, local * 2.2) * Math.PI);
            const { piernaDer, piernaIzq, brazoIzq, brazoDer } = anim.corredor2.mesh.userData;
            piernaDer.rotation.x = -golpe * 1.1;
            piernaIzq.rotation.x = golpe * 0.25;
            brazoIzq.rotation.x = golpe * 0.4;
            brazoDer.rotation.x = -golpe * 0.2;
          }
        }
        pelota.position.set(bx, altura, bz);
        if (anim.progreso >= 1) estadoRef.current.animGol = null;
      } else if (portadorActual) {
        // El que tiene la pelota corre de verdad (no el sway idle genérico)
        // y también se desplaza un poco, como si llevara la pelota al pie.
        const faseControl = t * 6;
        const { piernaIzq: pcI, piernaDer: pcD, brazoIzq: bcI, brazoDer: bcD } = portadorActual.mesh.userData;
        pcI.rotation.x = Math.sin(faseControl) * 0.4;
        pcD.rotation.x = -Math.sin(faseControl) * 0.4;
        bcI.rotation.x = -Math.sin(faseControl) * 0.3;
        bcD.rotation.x = Math.sin(faseControl) * 0.3;
        portadorActual.mesh.position.y = Math.abs(Math.sin(faseControl)) * 0.06;
        portadorActual.mesh.position.x = portadorActual.base.x + Math.sin(t * 0.4) * 1.2;
        portadorActual.mesh.position.z = portadorActual.base.z + Math.cos(t * 0.35) * 1.2;

        // Pase ambiental: la pelota viaja hacia el portador actual (con una
        // patada de verdad del que la tenía antes) y, al llegar, queda
        // pegada a su pie un poco adelante del cuerpo, no clavada en el
        // centro — hasta el próximo pase, cada ~2.6s.
        const ambi = estadoRef.current.animAmbiente;
        const destino = portadorActual.mesh.position;
        const balanceo = Math.sin(faseControl) * 0.18;
        if (ambi && ambi.pasador) {
          const fasePase = ambi.progreso / 0.4;
          if (fasePase < 1) {
            const golpe = Math.sin(Math.min(1, fasePase) * Math.PI);
            const { piernaDer: pd, piernaIzq: pi } = ambi.pasador.mesh.userData;
            pd.rotation.x = -golpe * 0.9;
            pi.rotation.x = golpe * 0.2;
          }
        }
        if (ambi && ambi.progreso < 1) {
          ambi.progreso = Math.min(1, ambi.progreso + 0.035);
          pelota.position.set(
            lerp(ambi.desde.x, destino.x, ambi.progreso) + balanceo,
            0.35 + Math.sin(ambi.progreso * Math.PI) * 0.6,
            lerp(ambi.desde.z, destino.z, ambi.progreso),
          );
        } else {
          pelota.position.set(destino.x + balanceo, 0.35, destino.z);
        }
      } else {
        pelota.rotation.y += 0.01;
      }

      renderer.render(escena, camara);
    };
    animar();

    const alRedimensionar = () => {
      if (!contenedor) return;
      camara.aspect = contenedor.clientWidth / contenedor.clientHeight;
      camara.updateProjectionMatrix();
      renderer.setSize(contenedor.clientWidth, contenedor.clientHeight);
    };
    window.addEventListener('resize', alRedimensionar);

    return () => {
      vivo = false;
      clearInterval(intervaloAmbiente);
      window.removeEventListener('resize', alRedimensionar);
      renderer.dispose();
      escena.traverse((obj) => {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) {
          // material.dispose() no cascadea a su .map: sin liberarlo a mano
          // acá, las texturas de tribuna/publicidad/red/etiquetas de nombre
          // (todas CanvasTexture creadas por montaje) se filtran en memoria
          // de GPU en cada remonte de este componente — y se remonta al
          // menos 2 veces por partido (un Cancha3D por cada mitad jugada).
          const materiales = Array.isArray(obj.material) ? obj.material : [obj.material];
          materiales.forEach((m) => {
            if (m.map) m.map.dispose();
            m.dispose();
          });
        }
      });
      if (contenedor.contains(renderer.domElement)) contenedor.removeChild(renderer.domElement);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formacionLocal, formacionVisita]);

  // El marcador puede cambiar sin que la escena se remonte (mismo partido,
  // mismo medio tiempo) — se guarda en estadoRef para que `elegirNuevoPortador`
  // siempre lea el valor actual, no el que había al montar el componente.
  useEffect(() => {
    estadoRef.current.equipoPresiona = equipoPresiona;
  }, [equipoPresiona]);

  // Mismo motivo que arriba: los nombres reales pueden cambiar (cambios en
  // el entretiempo) sin que la escena se remonte, así que el efecto del gol
  // necesita leerlos frescos de acá, no de un closure viejo.
  useEffect(() => {
    estadoRef.current.nombresLocal = nombresLocal;
    estadoRef.current.nombresVisita = nombresVisita;
  }, [nombresLocal, nombresVisita]);

  // Dispara la jugada de gol (pase, pase/gambeta, remate) cuando cambia
  // `eventoGol` ({ equipo: 'local'|'visitante' }) — la cámara se queda
  // siempre en el plano principal, el gol se ve desde ahí, sin acercamiento.
  useEffect(() => {
    const { pelota, jugadoresLocal, jugadoresVisita, nombresLocal: nl, nombresVisita: nv } = estadoRef.current;
    if (!eventoGol || !pelota) return;

    const esLocal = eventoGol.equipo === 'local';
    const signo = esLocal ? 1 : -1;
    const golZ = esLocal ? LARGO / 2 - 1 : -LARGO / 2 + 1;
    const equipoAnota = esLocal ? jugadoresLocal : jugadoresVisita;
    const nombresEquipo = esLocal ? nl : nv;
    // El que remata es el GOLEADOR REAL si se lo puede identificar por
    // nombre; el que arma la jugada (corredor1) sigue siendo el más
    // avanzado disponible aparte del goleador — no hay forma de saber
    // quién dio el pase real, así que ese sigue siendo genérico.
    const goleadorReal = buscarJugadorPorNombre(equipoAnota, nombresEquipo, eventoGol.jugador);
    const candidatos = [...equipoAnota]
      .filter((j) => !j.esArquero && j !== goleadorReal)
      .sort((a, b) => (signo > 0 ? b.base.z - a.base.z : a.base.z - b.base.z));

    estadoRef.current.animGol = {
      progreso: 0,
      p0: { x: pelota.position.x, z: pelota.position.z },
      p1: { x: (Math.random() - 0.5) * 10, z: signo * (LARGO / 2 - 18) },
      p2: { x: (Math.random() - 0.5) * 6, z: signo * (LARGO / 2 - 7) },
      p3: { x: (Math.random() - 0.5) * 4, z: golZ },
      corredor1: candidatos[0],
      corredor2: goleadorReal || candidatos[1] || candidatos[0],
    };

    const t = setTimeout(() => {
      if (estadoRef.current.pelota) estadoRef.current.pelota.position.set(0, 0.35, 0);
    }, 1600);
    return () => clearTimeout(t);
  }, [eventoGol]);

  // Tarjeta o lesión: reacciona el jugador REAL del evento si se lo puede
  // identificar por nombre; si no (el nombre no está en las listas, por
  // ejemplo un suplente recién ingresado), se elige uno al azar del equipo
  // afectado como respaldo.
  useEffect(() => {
    const { jugadoresLocal, jugadoresVisita, nombresLocal: nl, nombresVisita: nv } = estadoRef.current;
    if (!eventoReaccion || !jugadoresLocal) return;
    const equipo = eventoReaccion.equipo === 'local' ? jugadoresLocal : jugadoresVisita;
    const nombresEquipo = eventoReaccion.equipo === 'local' ? nl : nv;
    const jugador = buscarJugadorPorNombre(equipo, nombresEquipo, eventoReaccion.jugador)
      || equipo[Math.floor(Math.random() * equipo.length)];
    if (!jugador) return;
    estadoRef.current.animReaccion = { jugador, tipo: eventoReaccion.tipo, progreso: 0 };
  }, [eventoReaccion]);

  return <div ref={montajeRef} className="w-full h-full rounded-2xl overflow-hidden" />;
}
