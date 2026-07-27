import { useState, useEffect, useRef, useCallback } from 'react';
import { Loader2, Network, ChevronDown, Cpu, RotateCw, Hand, Layers } from 'lucide-react';
import { domainStyle, hexToRgba } from '../utils/domainColors';
import ProjectDetailModal from './ProjectDetailModal';

// Node geometry (px) — used for layout, drag math, and edge anchoring
const HUB_W = 200, HUB_H = 52;
const CARD_W = 172, CARD_H = 72;
const CELL_W = 440, CELL_H = 420, PER_ROW = 3;
const CLICK_THRESHOLD = 4; // px of movement below which a pointer-up counts as a click, not a drag

function clusterRadius(count) {
  return Math.max(125, 75 + count * 13);
}

function computeLayout(domains) {
  const positions = {};
  domains.forEach((d, i) => {
    const col = i % PER_ROW;
    const row = Math.floor(i / PER_ROW);
    const cx = col * CELL_W + 240;
    const cy = row * CELL_H + 210;
    positions[`domain:${d.domain}`] = { x: cx - HUB_W / 2, y: cy - HUB_H / 2 };
    const n = d.projects.length;
    const radius = clusterRadius(n);
    d.projects.forEach((p, j) => {
      const angle = (2 * Math.PI * j) / n - Math.PI / 2;
      positions[p.id] = {
        x: cx + radius * Math.cos(angle) - CARD_W / 2,
        y: cy + radius * Math.sin(angle) - CARD_H / 2,
      };
    });
  });
  return positions;
}

// Quadratic-bezier control point offset perpendicular to the hub→card
// direction — turns straight wires into a consistent orbital sweep.
function orbitPath(x1, y1, x2, y2) {
  const dx = x2 - x1, dy = y2 - y1;
  const len = Math.hypot(dx, dy) || 1;
  const px = -dy / len, py = dx / len;
  const bend = len * 0.16;
  const cx = (x1 + x2) / 2 + px * bend;
  const cy = (y1 + y2) / 2 + py * bend;
  return `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`;
}

export default function KnowledgeGraph() {
  const [domains, setDomains] = useState([]);
  const [loading, setLoading] = useState(true);
  const [positions, setPositions] = useState({});
  const [collapsed, setCollapsed] = useState(new Set());
  const [selectedProjectId, setSelectedProjectId] = useState(null);
  const dragRef = useRef(null);
  const canvasRef = useRef(null);

  const fetchGraph = useCallback(async () => {
    try {
      const res = await fetch('/projects/graph');
      if (res.ok) {
        const data = await res.json();
        setDomains(data.domains || []);
        setPositions(computeLayout(data.domains || []));
      }
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchGraph(); }, [fetchGraph]);

  const toggleDomain = (domain) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(domain)) next.delete(domain);
      else next.add(domain);
      return next;
    });
  };

  // ── drag + click handling (a drag that never moves is a click) ──
  const startDrag = (e, id, type, domain) => {
    e.preventDefault();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    dragRef.current = { id, type, domain, startX: e.clientX, startY: e.clientY, lastX: e.clientX, lastY: e.clientY, moved: false };
  };

  const onPointerMove = (e) => {
    const drag = dragRef.current;
    if (!drag) return;
    const dx = e.clientX - drag.lastX;
    const dy = e.clientY - drag.lastY;
    drag.lastX = e.clientX;
    drag.lastY = e.clientY;
    if (!drag.moved && Math.hypot(e.clientX - drag.startX, e.clientY - drag.startY) > CLICK_THRESHOLD) {
      drag.moved = true;
    }

    setPositions((prev) => {
      const next = { ...prev };
      const move = (key) => {
        const p = next[key];
        if (p) next[key] = { x: p.x + dx, y: p.y + dy };
      };
      if (drag.type === 'domain') {
        // Dragging a domain hub carries its whole cluster along
        move(`domain:${drag.domain}`);
        const group = domains.find((d) => d.domain === drag.domain);
        group?.projects.forEach((p) => move(p.id));
      } else {
        move(drag.id);
      }
      return next;
    });
  };

  const endDrag = () => {
    const drag = dragRef.current;
    if (drag && drag.type === 'project' && !drag.moved) {
      setSelectedProjectId(drag.id);
    }
    dragRef.current = null;
  };

  if (loading) {
    return (
      <div className="card flex items-center justify-center py-24">
        <Loader2 className="w-6 h-6 animate-spin text-blue-500 mr-3" />
        <span className="text-[15px] text-gray-400 font-medium">Building knowledge map...</span>
      </div>
    );
  }

  if (domains.length === 0) {
    return (
      <div className="card flex flex-col items-center justify-center py-24">
        <Network className="w-12 h-12 text-gray-200 mb-4" />
        <p className="text-[15px] text-gray-400 font-medium">No processed projects yet.</p>
        <p className="text-[13px] text-gray-400 mt-1">Upload project documents and the AI agent will map them here by domain.</p>
      </div>
    );
  }

  const rows = Math.ceil(domains.length / PER_ROW);
  const canvasW = Math.min(domains.length, PER_ROW) * CELL_W + 60;
  const canvasH = rows * CELL_H + 60;

  const center = (id, w, h) => {
    const p = positions[id];
    return p ? { x: p.x + w / 2, y: p.y + h / 2 } : { x: 0, y: 0 };
  };

  return (
    <div className="anim-enter">
      {/* Legend + controls */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          {domains.map((d) => {
            const style = domainStyle(d.domain);
            const isCollapsed = collapsed.has(d.domain);
            return (
              <button
                key={d.domain}
                onClick={() => toggleDomain(d.domain)}
                title={isCollapsed ? `Expand ${d.domain}` : `Collapse ${d.domain}`}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[12px] font-semibold border transition-all ${style.chip} ${isCollapsed ? 'opacity-50' : 'hover:opacity-80'}`}
              >
                <span className={`w-2 h-2 rounded-full ${style.dot}`} />
                {d.domain} · {d.count}
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 text-[12px] text-gray-400">
            <Hand className="w-3.5 h-3.5" />Drag to rearrange · click a project to open it
          </span>
          <button
            onClick={() => setPositions(computeLayout(domains))}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-200 text-gray-500 rounded-lg text-[12px] font-semibold hover:bg-gray-50 hover:border-gray-300 transition-all"
          >
            <RotateCw className="w-3 h-3" />Reset layout
          </button>
        </div>
      </div>

      {/* Canvas */}
      <div className="card map-canvas overflow-auto" style={{ height: '640px' }}>
        <div
          ref={canvasRef}
          className="relative"
          style={{ width: canvasW, height: canvasH, minWidth: '100%' }}
          onPointerMove={onPointerMove}
          onPointerUp={endDrag}
          onPointerLeave={endDrag}
        >
          {/* Domain energy glow — halo size/opacity reflects how much of our
              portfolio lives in that domain; a quiet way to show weight. */}
          {domains.map((d) => {
            if (collapsed.has(d.domain)) return null;
            const hub = center(`domain:${d.domain}`, HUB_W, HUB_H);
            const style = domainStyle(d.domain);
            const size = clusterRadius(d.projects.length) * 1.7;
            return (
              <div
                key={`glow-${d.domain}`}
                className="absolute rounded-full pointer-events-none anim-glow-breathe"
                style={{
                  left: hub.x - size / 2, top: hub.y - size / 2, width: size, height: size,
                  background: `radial-gradient(circle, ${hexToRgba(style.hex, 0.16)} 0%, transparent 70%)`,
                  filter: 'blur(6px)',
                }}
              />
            );
          })}

          {/* Orbital connections */}
          <svg className="absolute inset-0 pointer-events-none" width={canvasW} height={canvasH}>
            {domains.map((d) => {
              if (collapsed.has(d.domain)) return null;
              const hub = center(`domain:${d.domain}`, HUB_W, HUB_H);
              const hex = domainStyle(d.domain).hex;
              return d.projects.map((p) => {
                const node = center(p.id, CARD_W, CARD_H);
                return (
                  <g key={p.id}>
                    <path d={orbitPath(hub.x, hub.y, node.x, node.y)} fill="none" stroke={hex} strokeOpacity="0.3" strokeWidth="1.75" />
                    <circle cx={node.x} cy={node.y} r="3" fill={hex} fillOpacity="0.7" />
                  </g>
                );
              });
            })}
          </svg>

          {/* Project nodes */}
          {domains.map((d) => {
            if (collapsed.has(d.domain)) return null;
            const style = domainStyle(d.domain);
            return d.projects.map((p) => {
              const pos = positions[p.id];
              if (!pos) return null;
              return (
                <div
                  key={p.id}
                  onPointerDown={(e) => startDrag(e, p.id, 'project', d.domain)}
                  className="absolute bg-white border border-gray-200 rounded-xl px-3.5 py-3 shadow-sm cursor-grab active:cursor-grabbing select-none touch-none transition-shadow duration-200 hover:shadow-lg group"
                  style={{
                    left: pos.x, top: pos.y, width: CARD_W, height: CARD_H,
                    borderTop: `3px solid ${style.hex}`,
                    boxShadow: `0 1px 3px rgba(15,23,42,0.04)`,
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.boxShadow = `0 10px 28px ${hexToRgba(style.hex, 0.18)}`; }}
                  onMouseLeave={(e) => { e.currentTarget.style.boxShadow = `0 1px 3px rgba(15,23,42,0.04)`; }}
                >
                  <p className="text-[13px] font-bold text-gray-800 leading-tight truncate">{p.name}</p>
                  <div className="flex items-center gap-1.5 mt-2 overflow-hidden">
                    {p.has_ai && (
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-violet-50 text-violet-600 shrink-0">
                        <Cpu className="w-2.5 h-2.5" />AI
                      </span>
                    )}
                    {(p.technologies || []).slice(0, 2).map((t, i) => (
                      <span key={i} className="px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded text-[10px] font-medium truncate">{t}</span>
                    ))}
                  </div>
                  <p className="absolute bottom-2 right-3 text-[10px] font-semibold opacity-0 group-hover:opacity-100 transition-opacity" style={{ color: style.hex }}>
                    View →
                  </p>
                </div>
              );
            });
          })}

          {/* Domain hubs */}
          {domains.map((d) => {
            const pos = positions[`domain:${d.domain}`];
            if (!pos) return null;
            const style = domainStyle(d.domain);
            const isCollapsed = collapsed.has(d.domain);
            return (
              <div
                key={d.domain}
                onPointerDown={(e) => startDrag(e, `domain:${d.domain}`, 'domain', d.domain)}
                className="absolute bg-white border border-gray-200 rounded-2xl shadow-md flex items-center gap-3 px-3.5 cursor-grab active:cursor-grabbing select-none touch-none z-10"
                style={{ left: pos.x, top: pos.y, width: HUB_W, height: HUB_H, borderTop: `3px solid ${style.hex}` }}
              >
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                  style={{ backgroundColor: hexToRgba(style.hex, 0.12) }}
                >
                  <Layers className="w-4 h-4" style={{ color: style.hex }} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-bold text-gray-900 truncate leading-tight">{d.domain}</p>
                  <p className="text-[11px] text-gray-400 leading-tight">{d.count} project{d.count !== 1 ? 's' : ''}</p>
                </div>
                <button
                  onPointerDown={(e) => e.stopPropagation()}
                  onClick={() => toggleDomain(d.domain)}
                  title={isCollapsed ? 'Expand domain' : 'Collapse domain'}
                  className="p-1 text-gray-300 hover:text-gray-600 hover:bg-gray-100 rounded-md transition-all shrink-0"
                >
                  <ChevronDown className={`w-4 h-4 transition-transform duration-300 ${isCollapsed ? '-rotate-90' : ''}`} />
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {selectedProjectId && (
        <ProjectDetailModal key={selectedProjectId} projectId={selectedProjectId} onClose={() => setSelectedProjectId(null)} />
      )}
    </div>
  );
}
