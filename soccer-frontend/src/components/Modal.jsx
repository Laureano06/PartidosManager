import React, { useEffect, useRef } from 'react';

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

// 'lg' es el tamaño histórico (ficha de jugador/partido: ocupa casi toda la
// pantalla). 'sm' es para diálogos de formulario chicos que antes se
// armaban a mano por archivo (sin role=dialog, focus trap ni Escape) — con
// esto quedan con la misma accesibilidad que el resto sin forzarlos al
// tamaño grande.
const TAMANOS = {
  lg: 'w-full h-full max-w-6xl max-h-[94vh]',
  sm: 'w-full max-w-md',
};

export default function Modal({ open, onClose, children, labelledBy, size = 'lg' }) {
  const contentRef = useRef(null);
  const previousFocusRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      if (e.key !== 'Tab' || !contentRef.current) return;
      const focusable = contentRef.current.querySelectorAll(FOCUSABLE_SELECTOR);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (open) {
      // Guard necesario por StrictMode (dev): este efecto se invoca dos
      // veces al montar. En la segunda invocación el foco ya está dentro
      // del modal (lo dejó la primera invocación), así que sin este chequeo
      // se pisaba previousFocusRef con un elemento del propio modal en vez
      // de con el trigger real.
      if (!contentRef.current?.contains(document.activeElement)) {
        previousFocusRef.current = document.activeElement;
      }
      const focusable = contentRef.current?.querySelectorAll(FOCUSABLE_SELECTOR);
      (focusable && focusable[0] ? focusable[0] : contentRef.current)?.focus();
    } else if (previousFocusRef.current instanceof HTMLElement) {
      previousFocusRef.current.focus();
      previousFocusRef.current = null;
    }
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-3 sm:p-6"
      onClick={onClose}
    >
      <div
        ref={contentRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        tabIndex={-1}
        className={`bg-[#121e36] border border-slate-700 rounded-2xl shadow-2xl overflow-y-auto scroll-slide outline-none ${TAMANOS[size]}`}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
