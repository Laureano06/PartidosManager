import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';

// Prototipo mínimo de motor JUGABLE — a propósito separado de Cancha3D.jsx
// (que es la visualización de espectador, no tocar esa lógica desde acá).
// Esto es el primer escalón de un camino largo: un jugador se mueve con
// WASD sobre la cancha con aceleración/desaceleración real (nada de
// teletransporte), con el resto del plantel parado de referencia. Sin
// pelota, sin física de pelota, sin IA de los otros 21, sin animaciones más
// allá del trote — eso viene en pasos futuros, uno por vez.

const ANCHO = 40;
const LARGO = 62;
const VELOCIDAD_MAX = 6.5;
const VELOCIDAD_SPRINT = 10.5;
const ACELERACION = 28;
const DESACELERACION = 34;

const FORMACION_442 = [
  { x: 50, y: 8 },
  { x: 15, y: 28 }, { x: 38, y: 25 }, { x: 62, y: 25 }, { x: 85, y: 28 },
  { x: 15, y: 55 }, { x: 38, y: 50 }, { x: 62, y: 50 }, { x: 85, y: 55 },
  { x: 38, y: 80 }, { x: 62, y: 80 },
];

function slotAMundo(slot, esLocal) {
  const x = (slot.x / 100 - 0.5) * ANCHO;
  const z = esLocal ? -LARGO / 2 + (slot.y / 100) * (LARGO / 2 - 2) : LARGO / 2 - (slot.y / 100) * (LARGO / 2 - 2);
  return { x, z };
}

function crearPiernaSimple(mat, x) {
  const pivote = new THREE.Group();
  pivote.position.set(x, 0.99, 0);
  const pierna = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.14, 0.85, 8), mat);
  pierna.position.y = -0.425;
  pivote.add(pierna);
  return pivote;
}

function crearBrazoSimple(mat, x) {
  const pivote = new THREE.Group();
  pivote.position.set(x, 1.6, 0);
  const brazo = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.09, 0.55, 8), mat);
  brazo.position.y = -0.275;
  pivote.add(brazo);
  return pivote;
}

// Mismo estilo de figura que Cancha3D (piernas/brazos como pivotes
// rotables), pero reconstruido acá aparte a propósito — los dos motores no
// comparten código interno, cada uno se puede tocar sin romper al otro.
function crearJugadorSimple(color) {
  const grupo = new THREE.Group();
  const matKit = new THREE.MeshStandardMaterial({ color, roughness: 0.6 });
  const matPiel = new THREE.MeshStandardMaterial({ color: 0xd8a878, roughness: 0.7 });
  const matMedia = new THREE.MeshStandardMaterial({ color: 0xf1f5f9, roughness: 0.8 });

  const piernaIzq = crearPiernaSimple(matMedia, -0.16);
  const piernaDer = crearPiernaSimple(matMedia, 0.16);
  grupo.add(piernaIzq, piernaDer);

  const torso = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.34, 0.7, 8), matKit);
  torso.position.y = 1.34;
  grupo.add(torso);

  const brazoIzq = crearBrazoSimple(matKit, -0.42);
  const brazoDer = crearBrazoSimple(matKit, 0.42);
  grupo.add(brazoIzq, brazoDer);

  const cabeza = new THREE.Mesh(new THREE.SphereGeometry(0.22, 12, 12), matPiel);
  cabeza.position.y = 1.91;
  grupo.add(cabeza);

  grupo.userData = { piernaIzq, piernaDer, brazoIzq, brazoDer };
  return grupo;
}

function lineaPiso(escena, ancho, alto, x, z) {
  const geo = new THREE.BoxGeometry(ancho, 0.05, alto);
  const mat = new THREE.MeshBasicMaterial({ color: 0xffffff });
  const linea = new THREE.Mesh(geo, mat);
  linea.position.set(x, 0.03, z);
  escena.add(linea);
}

export default function CanchaJugable() {
  const montajeRef = useRef(null);
  const estadoRef = useRef({});

  useEffect(() => {
    const contenedor = montajeRef.current;
    if (!contenedor) return;

    const escena = new THREE.Scene();
    escena.background = new THREE.Color(0x0b1326);
    escena.fog = new THREE.Fog(0x0b1326, 40, 100);

    const camara = new THREE.PerspectiveCamera(55, contenedor.clientWidth / contenedor.clientHeight, 0.1, 200);
    camara.position.set(0, 10, -16);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(contenedor.clientWidth, contenedor.clientHeight);
    contenedor.appendChild(renderer.domElement);

    escena.add(new THREE.AmbientLight(0xffffff, 0.7));
    const sol = new THREE.DirectionalLight(0xffffff, 1);
    sol.position.set(20, 40, 10);
    escena.add(sol);

    // Cancha (sin estadio, sin tribunas — no hace falta para probar el
    // movimiento, eso es parte de la visualización de espectador, no de esto).
    const cesped = new THREE.Mesh(
      new THREE.PlaneGeometry(ANCHO + 6, LARGO + 6),
      new THREE.MeshStandardMaterial({ color: 0x1b7a3a, roughness: 1 }),
    );
    cesped.rotation.x = -Math.PI / 2;
    escena.add(cesped);

    lineaPiso(escena, ANCHO, 0.15, 0, -LARGO / 2);
    lineaPiso(escena, ANCHO, 0.15, 0, LARGO / 2);
    lineaPiso(escena, 0.15, LARGO, -ANCHO / 2, 0);
    lineaPiso(escena, 0.15, LARGO, ANCHO / 2, 0);
    lineaPiso(escena, ANCHO, 0.15, 0, 0);
    const circulo = new THREE.Mesh(
      new THREE.RingGeometry(6.9, 7, 48),
      new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide }),
    );
    circulo.rotation.x = -Math.PI / 2;
    circulo.position.y = 0.03;
    escena.add(circulo);

    [-1, 1].forEach((lado) => {
      const mat = new THREE.MeshStandardMaterial({ color: 0xf1f5f9 });
      const arco = new THREE.Group();
      [-3.66, 3.66].forEach((px) => {
        const poste = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 2.44, 8), mat);
        poste.position.set(px, 1.22, 0);
        arco.add(poste);
      });
      const travesano = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 7.32, 8), mat);
      travesano.rotation.z = Math.PI / 2;
      travesano.position.set(0, 2.44, 0);
      arco.add(travesano);
      arco.position.set(0, 0, lado * LARGO / 2);
      escena.add(arco);
    });

    // El resto del plantel: parado de referencia, sin IA todavía (es el
    // paso que sigue después de esto).
    FORMACION_442.forEach((slot) => {
      const { x, z } = slotAMundo(slot, true);
      const j = crearJugadorSimple(0x38bdf8);
      j.position.set(x, 0, z);
      escena.add(j);
    });
    FORMACION_442.forEach((slot) => {
      const { x, z } = slotAMundo(slot, false);
      const j = crearJugadorSimple(0xf43f5e);
      j.position.set(x, 0, z);
      escena.add(j);
    });

    // El jugador controlable — verde para distinguirlo del resto a simple vista.
    const jugador = crearJugadorSimple(0x22c55e);
    jugador.position.set(0, 0, -10);
    escena.add(jugador);

    // Input: WASD + Shift, guardado en un Set leído cada frame — nada de
    // lógica de juego acá adentro, solo qué teclas están apretadas ahora.
    const teclas = new Set();
    const alApretar = (e) => teclas.add(e.key.toLowerCase());
    const alSoltar = (e) => teclas.delete(e.key.toLowerCase());
    window.addEventListener('keydown', alApretar);
    window.addEventListener('keyup', alSoltar);

    const velocidad = new THREE.Vector2(0, 0);
    let anguloActual = 0;

    estadoRef.current = { camara, renderer, jugador, velocidad };

    let vivo = true;
    const reloj = new THREE.Clock();
    const animar = () => {
      if (!vivo) return;
      requestAnimationFrame(animar);
      const dt = Math.min(0.05, reloj.getDelta());
      const t = reloj.elapsedTime;

      // Movimiento: dirección deseada -> aceleración -> velocidad ->
      // posición. Nunca se teletransporta, siempre se acelera/frena.
      let dx = 0;
      let dz = 0;
      if (teclas.has('w')) dz += 1;
      if (teclas.has('s')) dz -= 1;
      if (teclas.has('d')) dx += 1;
      if (teclas.has('a')) dx -= 1;
      const hayInput = dx !== 0 || dz !== 0;
      const sprint = teclas.has('shift');
      const topeVelocidad = sprint ? VELOCIDAD_SPRINT : VELOCIDAD_MAX;

      if (hayInput) {
        const largo = Math.hypot(dx, dz) || 1;
        const dirX = (dx / largo) * topeVelocidad;
        const dirZ = (dz / largo) * topeVelocidad;
        velocidad.x += (dirX - velocidad.x) * Math.min(1, ACELERACION * dt);
        velocidad.y += (dirZ - velocidad.y) * Math.min(1, ACELERACION * dt);
      } else {
        velocidad.x += (0 - velocidad.x) * Math.min(1, DESACELERACION * dt);
        velocidad.y += (0 - velocidad.y) * Math.min(1, DESACELERACION * dt);
      }

      jugador.position.x = Math.max(-ANCHO / 2 + 1, Math.min(ANCHO / 2 - 1, jugador.position.x + velocidad.x * dt));
      jugador.position.z = Math.max(-LARGO / 2 + 1, Math.min(LARGO / 2 - 1, jugador.position.z + velocidad.y * dt));

      const rapidez = Math.hypot(velocidad.x, velocidad.y);
      if (rapidez > 0.3) {
        const anguloObjetivo = Math.atan2(velocidad.x, velocidad.y);
        let diff = anguloObjetivo - anguloActual;
        diff = Math.atan2(Math.sin(diff), Math.cos(diff)); // ángulo más corto
        anguloActual += diff * Math.min(1, 10 * dt);
        jugador.rotation.y = anguloActual;
      }

      // Trote proporcional a la velocidad — parado si no se mueve, más
      // marcado cerca del sprint.
      const { piernaIzq, piernaDer, brazoIzq, brazoDer } = jugador.userData;
      const intensidad = Math.min(1, rapidez / VELOCIDAD_MAX);
      const faseTrote = t * (4 + intensidad * 4);
      piernaIzq.rotation.x = Math.sin(faseTrote) * 0.5 * intensidad;
      piernaDer.rotation.x = -Math.sin(faseTrote) * 0.5 * intensidad;
      brazoIzq.rotation.x = -Math.sin(faseTrote) * 0.4 * intensidad;
      brazoDer.rotation.x = Math.sin(faseTrote) * 0.4 * intensidad;

      // Cámara: sigue al jugador con un offset fijo detrás y arriba — no
      // rota con él todavía, eso es un refinamiento futuro.
      camara.position.set(jugador.position.x, 10, jugador.position.z - 16);
      camara.lookAt(jugador.position.x, 1, jugador.position.z);

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
      window.removeEventListener('keydown', alApretar);
      window.removeEventListener('keyup', alSoltar);
      window.removeEventListener('resize', alRedimensionar);
      renderer.dispose();
      escena.traverse((obj) => {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) {
          if (Array.isArray(obj.material)) obj.material.forEach((m) => m.dispose());
          else obj.material.dispose();
        }
      });
      if (contenedor.contains(renderer.domElement)) contenedor.removeChild(renderer.domElement);
    };
  }, []);

  return <div ref={montajeRef} className="w-full h-full rounded-2xl overflow-hidden" tabIndex={0} />;
}
