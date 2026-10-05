import { useCallback, useEffect, useRef, useState } from 'react';

const MARGIN = 8;

function clamp(value, max) {
  return Math.min(Math.max(value, MARGIN), Math.max(MARGIN, max));
}

// Pointer-based drag for a fixed-position element. `elementRef` must point
// at the positioned node so drops can be clamped against its real (current)
// size - callers that swap between a small pill and a large panel don't need
// to know their own dimensions up front.
export function useDraggable(initialPosition, elementRef) {
  const [position, setPosition] = useState(initialPosition);
  const draggingRef = useRef(false);
  const movedRef = useRef(false);
  const downRef = useRef({ x: 0, y: 0 });
  const offsetRef = useRef({ x: 0, y: 0 });

  const clampToViewport = useCallback((pos) => {
    const rect = elementRef.current?.getBoundingClientRect();
    const w = rect?.width || 0;
    const h = rect?.height || 0;
    return {
      x: clamp(pos.x, window.innerWidth - w - MARGIN),
      y: clamp(pos.y, window.innerHeight - h - MARGIN),
    };
  }, [elementRef]);

  const onPointerDown = useCallback((e) => {
    if (e.target.closest('button, input, textarea, a')) return; // let interactive children behave normally
    draggingRef.current = true;
    movedRef.current = false;
    downRef.current = { x: e.clientX, y: e.clientY };
    offsetRef.current = { x: e.clientX - position.x, y: e.clientY - position.y };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  }, [position]);

  const onPointerMove = useCallback((e) => {
    if (!draggingRef.current) return;
    if (!movedRef.current && Math.hypot(e.clientX - downRef.current.x, e.clientY - downRef.current.y) > 4) {
      movedRef.current = true;
    }
    setPosition(clampToViewport({ x: e.clientX - offsetRef.current.x, y: e.clientY - offsetRef.current.y }));
  }, [clampToViewport]);

  const onPointerUp = useCallback(() => { draggingRef.current = false; }, []);

  const reclamp = useCallback(() => setPosition((p) => clampToViewport(p)), [clampToViewport]);

  // Re-clamp on viewport resize so it never gets stranded off-screen.
  useEffect(() => {
    reclamp();
    window.addEventListener('resize', reclamp);
    return () => window.removeEventListener('resize', reclamp);
  }, [reclamp]);

  return {
    position,
    dragHandleProps: { onPointerDown, onPointerMove, onPointerUp },
    wasDragged: () => movedRef.current,
    reclamp,
  };
}
