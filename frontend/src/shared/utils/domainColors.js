// Fixed domain → color assignment (color follows the entity, never its rank).
// The 8 hex hues are a categorical palette validated for lightness band,
// chroma, CVD separation, and contrast on the app's light surface.
// Domain identity is always also carried by a text label — color is a
// supporting cue, so domains sharing a hue remain distinguishable.
export const DOMAIN_STYLES = {
  'Banking & Finance':        { hex: '#2563eb', chip: 'bg-blue-50 text-blue-700 border-blue-100', dot: 'bg-blue-500' },
  'Healthcare':               { hex: '#059669', chip: 'bg-emerald-50 text-emerald-700 border-emerald-100', dot: 'bg-emerald-500' },
  'Logistics & Supply Chain': { hex: '#d97706', chip: 'bg-amber-50 text-amber-700 border-amber-100', dot: 'bg-amber-500' },
  'Education':                { hex: '#7c3aed', chip: 'bg-violet-50 text-violet-700 border-violet-100', dot: 'bg-violet-500' },
  'Retail & E-Commerce':      { hex: '#e11d48', chip: 'bg-rose-50 text-rose-700 border-rose-100', dot: 'bg-rose-500' },
  'Insurance':                { hex: '#0891b2', chip: 'bg-cyan-50 text-cyan-700 border-cyan-100', dot: 'bg-cyan-500' },
  'Manufacturing':            { hex: '#ea580c', chip: 'bg-orange-50 text-orange-700 border-orange-100', dot: 'bg-orange-500' },
  'Media & Entertainment':    { hex: '#c026d3', chip: 'bg-fuchsia-50 text-fuchsia-700 border-fuchsia-100', dot: 'bg-fuchsia-500' },
  'Real Estate':              { hex: '#ea580c', chip: 'bg-orange-50 text-orange-700 border-orange-100', dot: 'bg-orange-500' },
  'Travel & Hospitality':     { hex: '#0891b2', chip: 'bg-cyan-50 text-cyan-700 border-cyan-100', dot: 'bg-cyan-500' },
  'Energy & Utilities':       { hex: '#d97706', chip: 'bg-amber-50 text-amber-700 border-amber-100', dot: 'bg-amber-500' },
  'Telecom':                  { hex: '#7c3aed', chip: 'bg-violet-50 text-violet-700 border-violet-100', dot: 'bg-violet-500' },
  'Government':               { hex: '#2563eb', chip: 'bg-blue-50 text-blue-700 border-blue-100', dot: 'bg-blue-500' },
  'HR & Recruitment':         { hex: '#e11d48', chip: 'bg-rose-50 text-rose-700 border-rose-100', dot: 'bg-rose-500' },
  'Legal':                    { hex: '#059669', chip: 'bg-emerald-50 text-emerald-700 border-emerald-100', dot: 'bg-emerald-500' },
};

export const FALLBACK_DOMAIN_STYLE = {
  hex: '#64748b', chip: 'bg-gray-100 text-gray-600 border-gray-200', dot: 'bg-gray-400',
};

export const domainStyle = (domain) => DOMAIN_STYLES[domain] || FALLBACK_DOMAIN_STYLE;

// For glows/rings derived from a domain's hex where Tailwind's static classes
// don't reach (opacity needs to vary with e.g. project count).
export const hexToRgba = (hex, alpha) => {
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};
