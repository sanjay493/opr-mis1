import React from 'react';

/**
 * Render chemical formulae inside a parameter label / unit string with the
 * digit runs as <sub>. Mirror of backend/chem_format.py's `chemsub` Jinja
 * filter — keep the two token lists in sync.
 *
 * Whitelist-only: apply to techno / environmental / BF parameter labels and
 * unit strings, never to free prose or generic headers (so "H2" as a
 * half-year, "12 Parameters", dates, etc. are never touched).
 */
const CHEM_TOKENS = [
  // acids / misc
  'H2SO4', 'H2O2', 'H3PO4',
  // oxides
  'Al2O3', 'Fe2O3', 'Fe3O4', 'Cr2O3', 'V2O5', 'P2O5', 'SiO2', 'TiO2',
  'MnO2', 'Mn3O4', 'Na2O', 'K2O',
  // carbonates
  'CaCO3', 'MgCO3', 'Na2CO3',
  // gases / molecules
  'CO2', 'SO2', 'SO3', 'NO2', 'N2O', 'NH3', 'CH4', 'C2H2', 'C2H4', 'C2H6',
  'H2O', 'H2S', 'H2', 'N2', 'O2',
];

// Longest first so "H2SO4" wins over "H2", "Fe3O4" over "Fe3", etc.
const _ALT = CHEM_TOKENS.slice()
  .sort((a, b) => b.length - a.length)
  .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  .join('|');
const TOKEN_RE = new RegExp(`\\b(?:${_ALT})\\b`, 'gi');

function _renderFormula(tok, keyBase) {
  return tok
    .split(/(\d+)/)
    .filter(Boolean)
    .map((part, i) =>
      /^\d+$/.test(part)
        ? <sub key={`${keyBase}s${i}`}>{part}</sub>
        : <React.Fragment key={`${keyBase}t${i}`}>{part}</React.Fragment>
    );
}

/**
 * @param {*} text
 * @returns the original value when there's nothing to format (string /
 *   null / non-string passthrough), otherwise a React fragment.
 */
export function chemSub(text) {
  if (text == null || typeof text !== 'string') return text;
  const nodes = [];
  let last = 0;
  let idx = 0;
  let m;
  TOKEN_RE.lastIndex = 0;
  while ((m = TOKEN_RE.exec(text)) !== null) {
    if (m.index > last) {
      nodes.push(<React.Fragment key={`p${idx++}`}>{text.slice(last, m.index)}</React.Fragment>);
    }
    nodes.push(<React.Fragment key={`f${idx++}`}>{_renderFormula(m[0], `f${idx}`)}</React.Fragment>);
    last = m.index + m[0].length;
  }
  if (last === 0) return text; // no formula found — plain string, cheapest path
  if (last < text.length) {
    nodes.push(<React.Fragment key={`p${idx++}`}>{text.slice(last)}</React.Fragment>);
  }
  return <>{nodes}</>;
}
