import React from 'react';

const soloDigitos = (s) => s.replace(/\D/g, '');

// Input de texto que se ve como "$680.000" pero por dentro maneja un valor
// numérico plano (string de dígitos) vía onChange, igual que un <input type="number">.
export default function MoneyInput({ value, onChange, className = '', placeholder }) {
  const formateado = value ? Number(soloDigitos(String(value))).toLocaleString('es-AR') : '';

  return (
    <div className="relative">
      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none">$</span>
      <input
        type="text"
        inputMode="numeric"
        value={formateado}
        onChange={(e) => onChange(soloDigitos(e.target.value))}
        placeholder={placeholder}
        className={`pl-7 ${className}`}
      />
    </div>
  );
}
