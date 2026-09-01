import { useRef } from 'react';

// Permite deslizar el contenido arrastrando con el mouse (click + movimiento),
// igual que el touch nativo. Se usa junto con la clase CSS "scroll-slide"
// que oculta la barra de scroll visual sin desactivar el desplazamiento.
export function useDragScroll() {
  const ref = useRef(null);
  const estado = useRef({ arrastrando: false, x: 0, y: 0, scrollTop: 0, scrollLeft: 0 });

  const onMouseDown = (e) => {
    const el = ref.current;
    if (!el) return;
    estado.current = { arrastrando: true, x: e.clientX, y: e.clientY, scrollTop: el.scrollTop, scrollLeft: el.scrollLeft };
    el.classList.add('dragging');
  };

  const detener = () => {
    const el = ref.current;
    estado.current.arrastrando = false;
    if (el) el.classList.remove('dragging');
  };

  const onMouseMove = (e) => {
    const el = ref.current;
    if (!el || !estado.current.arrastrando) return;
    const deltaY = e.clientY - estado.current.y;
    const deltaX = e.clientX - estado.current.x;
    el.scrollTop = estado.current.scrollTop - deltaY;
    el.scrollLeft = estado.current.scrollLeft - deltaX;
  };

  return {
    ref,
    dragHandlers: {
      onMouseDown,
      onMouseMove,
      onMouseUp: detener,
      onMouseLeave: detener,
    },
  };
}
