import { useRef, useState, useCallback, useEffect } from 'react';

export function useCallPolling(callId) {
  const [transcript, setTranscript] = useState([]);
  const [suggestion, setSuggestion] = useState(null);
  const [callStatus, setCallStatus] = useState('connecting');
  const [contactProfile, setContactProfile] = useState(null);
  const [relevantProjects, setRelevantProjects] = useState(null);
  const intervalRef = useRef(null);
  const lastTranscriptRef = useRef('');
  const lastInterimsRef = useRef('');

  const startPolling = useCallback(() => {
    if (!callId) return;
    if (intervalRef.current) clearInterval(intervalRef.current);
    lastTranscriptRef.current = '';
    lastInterimsRef.current = '';

    console.log('[Polling] Started for call:', callId);

    const poll = async () => {
      try {
        const res = await fetch(`/calls/live/${callId}`);
        if (!res.ok) return;
        const data = await res.json();

        // Status, suggestions, and client context must be evaluated on every
        // tick, independent of whether the transcript changed - a silent
        // (no-answer) call never touches transcript/interims but still needs
        // its terminal status to land, and a suggestion can arrive on a tick
        // where transcript has already gone quiet while the LLM call ran.
        // 'in_progress' only ever lands once Twilio's own "answered" event
        // fires for the callee leg - it's the one value that means a human
        // actually picked up. 'initiated'/'initiating' are left alone (stay
        // at the default 'connecting') since nothing meaningful has happened yet.
        if (data.status === 'in_progress' || data.status === 'ringing') setCallStatus(data.status);
        else if (data.status === 'completed' || data.status === 'failed') setCallStatus(data.status);

        if (data.suggestions?.length > 0) {
          const latest = data.suggestions[data.suggestions.length - 1];
          if (typeof latest === 'object') setSuggestion(latest);
        }

        setContactProfile(data.contact_profile ?? null);
        setRelevantProjects(data.relevant_projects ?? null);

        // Transcript entries: keep the diff-check as a pure perf guard around
        // the (re-)parsing + re-render, not around anything correctness-critical.
        const interimsKey = JSON.stringify(data.interims || {});
        const changed = data.transcript !== lastTranscriptRef.current || interimsKey !== lastInterimsRef.current;
        if (!changed) return;

        lastTranscriptRef.current = data.transcript || '';
        lastInterimsRef.current = interimsKey;

        // Parse committed transcript lines
        const entries = [];
        if (data.transcript) {
          const lines = data.transcript.split('\n').filter(Boolean);
          for (const line of lines) {
            const match = line.match(/^\[(.+?)\]:\s*(.+)$/);
            entries.push({
              speaker: match ? match[1] : '',
              text: match ? match[2] : line,
              final: true,
              time: new Date(),
            });
          }
        }

        // Add interim entries (shown dimmed)
        const interims = data.interims || {};
        // Only add interims that aren't already the last line for that speaker
        for (const [speaker, text] of Object.entries(interims)) {
          entries.push({
            speaker,
            text,
            final: false,
            time: new Date(),
          });
        }

        setTranscript(entries);
      } catch {
        // Silently ignore
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 1000);
  }, [callId]);

  const stopPolling = useCallback(() => {
    console.log('[Polling] Stopped');
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (callId) startPolling();
    return () => stopPolling();
  }, [callId, startPolling, stopPolling]);

  return {
    connect: startPolling,
    disconnect: stopPolling,
    send: () => {},
    transcript,
    suggestion,
    callStatus,
    contactProfile,
    relevantProjects,
    connected: true,
    setCallStatus,
  };
}
