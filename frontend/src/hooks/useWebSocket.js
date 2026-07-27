import { useRef, useState, useCallback, useEffect } from 'react';

export function useWebSocket(callId) {
  const wsRef = useRef(null);
  const transcriptRef = useRef([]);
  const [transcript, setTranscript] = useState([]);
  const [suggestion, setSuggestion] = useState(null);
  const [callStatus, setCallStatus] = useState('connecting');
  const [connected, setConnected] = useState(false);
  const manualCloseRef = useRef(false);
  const reconnectTimerRef = useRef(null);

  const connect = useCallback(() => {
    if (!callId) return;
    manualCloseRef.current = false;
    if (wsRef.current) {
      wsRef.current.close();
    }

    // Connect directly to backend, bypassing Vite proxy which kills WS connections
    const url = `ws://localhost:8080/ws/call/${callId}`;
    console.log('[WS] Connecting to:', url);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[WS] Connected');
      setConnected(true);
    };

    ws.onclose = (e) => {
      console.log('[WS] Closed:', e.code, e.reason);
      setConnected(false);
      // Auto-reconnect if not manually closed
      if (!manualCloseRef.current) {
        console.log('[WS] Unexpected close, reconnecting in 1s...');
        reconnectTimerRef.current = setTimeout(() => connect(), 1000);
      }
    };

    ws.onerror = (e) => {
      console.error('[WS] Error:', e);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'ping') {
        // Respond to server ping to keep connection alive
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'pong' }));
        }
        return;
      }
      console.log('[WS] Message:', data.type, data.text || '');

      switch (data.type) {
        case 'transcript': {
          const entry = {
            text: data.text,
            speaker: data.speaker || '',
            final: data.is_final,
            time: new Date(),
          };

          if (data.is_final) {
            // Always append final entries
            transcriptRef.current = [...transcriptRef.current, entry];
          } else {
            // Replace last interim or add new interim
            const prev = transcriptRef.current;
            if (prev.length > 0 && !prev[prev.length - 1].final) {
              transcriptRef.current = [...prev.slice(0, -1), entry];
            } else {
              transcriptRef.current = [...prev, entry];
            }
          }
          setTranscript([...transcriptRef.current]);
          break;
        }

        case 'suggestion':
          setSuggestion({
            next_talking_point: data.next_talking_point,
            objection_handling: data.objection_handling,
            sentiment: data.sentiment,
            key_insight: data.key_insight,
          });
          break;

        case 'call_status':
          setCallStatus(data.status);
          break;
      }
    };
  }, [callId]);

  const disconnect = useCallback(() => {
    manualCloseRef.current = true;
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const send = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  useEffect(() => {
    return () => disconnect();
  }, [disconnect]);

  return {
    connect,
    disconnect,
    send,
    transcript,
    suggestion,
    callStatus,
    connected,
    setCallStatus,
  };
}
