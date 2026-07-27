import { useEffect, useRef, useState } from 'react';
import {
  Mic, MicOff, PhoneOff, Clock, Wifi, WifiOff, Phone, Tag, Minimize2,
  Lightbulb, AlertTriangle, TrendingUp, MessageSquare, Zap, Briefcase,
  IdCard, Building2, FolderKanban, HelpCircle
} from 'lucide-react';
import { useCallPolling } from '../hooks/useCallPolling';
import { useDraggable } from '../hooks/useDraggable';

const SENTIMENT = {
  Positive: { color: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-100' },
  Neutral: { color: 'text-gray-500', bg: 'bg-gray-50', border: 'border-gray-200' },
  Negative: { color: 'text-red-600', bg: 'bg-red-50', border: 'border-red-100' },
};

const STATUS_STYLES = {
  new: 'bg-blue-50 text-blue-600',
  called: 'bg-emerald-50 text-emerald-600',
  follow_up: 'bg-amber-50 text-amber-600',
  closed: 'bg-gray-100 text-gray-500',
};
const STATUS_LABELS = { new: 'New', called: 'Called', follow_up: 'Follow Up', closed: 'Closed' };

const PANEL_WIDTH = 860;
const INITIAL_POSITION = { x: Math.max(24, window.innerWidth - PANEL_WIDTH - 24), y: 24 };

export default function CallPanel({
  contact, callId, onClose, hangUp: twilioHangUp, toggleMute: twilioToggleMute,
  onStatusChange, sessionInfo,
}) {
  const { connect, disconnect, send, suggestion, callStatus, contactProfile, relevantProjects, connected } = useCallPolling(callId);
  const [muted, setMuted] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [aiProvider, setAiProvider] = useState('groq');
  const [minimized, setMinimized] = useState(false);
  const ended = callStatus === 'completed' || callStatus === 'failed';

  const containerRef = useRef(null);
  const { position, dragHandleProps, wasDragged, reclamp } = useDraggable(INITIAL_POSITION, containerRef);

  useEffect(() => { connect(); return () => disconnect(); }, [callId]);
  useEffect(() => {
    if (ended) return; // freeze the timer once the call is over instead of counting forever
    const i = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(i);
  }, [callStatus]);
  useEffect(() => { onStatusChange?.(callId, callStatus); }, [callId, callStatus, onStatusChange]);
  // The pill and the full panel are very different sizes - re-clamp position
  // against whichever one is currently on screen so toggling never leaves it
  // hanging off the edge of the viewport.
  useEffect(() => { reclamp(); }, [minimized, reclamp]);

  // The other party hanging up (or the call failing server-side) only ever
  // surfaces here as a polled callStatus change - nothing else closes the
  // panel unless the agent clicks End, so it must self-close on that signal.
  useEffect(() => {
    if (!ended) return;
    if (twilioHangUp) twilioHangUp();
    disconnect();
    const t = setTimeout(() => onClose(), 1500);
    return () => clearTimeout(t);
  }, [ended]);

  const fmt = (s) => `${Math.floor(s/60).toString().padStart(2,'0')}:${(s%60).toString().padStart(2,'0')}`;
  const handleEndCall = () => { if (twilioHangUp) twilioHangUp(); disconnect(); setTimeout(() => onClose(), 500); };
  const toggleProvider = () => { const n = aiProvider === 'groq' ? 'openai' : 'groq'; setAiProvider(n); send({ type: 'change_provider', provider: n }); };
  const handleToggleMute = () => { if (twilioToggleMute) { setMuted(twilioToggleMute()); } else { setMuted(!muted); } };

  const ss = SENTIMENT[suggestion?.sentiment] || SENTIMENT.Neutral;
  const profile = contactProfile || {};
  const client = relevantProjects?.client || {};
  const projects = relevantProjects?.projects || [];
  const status = profile.status || contact.status;
  const company = profile.company || contact.company;
  const notes = profile.notes || contact.notes;

  return (
    <div
      ref={containerRef}
      className="fixed z-50 select-none"
      style={{ left: position.x, top: position.y }}
    >
      {minimized ? (
        <div
          {...dragHandleProps}
          onClick={() => { if (!wasDragged()) setMinimized(false); }}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setMinimized(false); }}
          role="button"
          tabIndex={0}
          title="Click to expand"
          className="flex items-center gap-2.5 pl-2 pr-2.5 py-2 bg-white rounded-full shadow-2xl border border-gray-200 cursor-grab active:cursor-grabbing hover:shadow-[0_10px_35px_rgba(0,0,0,0.18)] transition-shadow anim-modal"
        >
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-[12px] font-bold text-white shrink-0">
            {contact.name.charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0 pr-1">
            <p className="text-[12.5px] font-semibold text-gray-900 truncate max-w-[110px]">{contact.name}</p>
            <div className="flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${!ended ? 'bg-emerald-500 anim-pulse' : 'bg-gray-400'}`} />
              <span className="text-[11px] text-gray-400 font-mono">{fmt(elapsed)}</span>
            </div>
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); handleToggleMute(); }}
            className={`p-2 rounded-full transition-all ${muted ? 'bg-red-50 text-red-500' : 'bg-gray-50 text-gray-400 hover:text-gray-600'}`}
          >
            {muted ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); handleEndCall(); }}
            className="p-2 rounded-full bg-red-500 hover:bg-red-400 text-white transition-all"
          >
            <PhoneOff className="w-3.5 h-3.5" />
          </button>
        </div>
      ) : (
        <div style={{ width: PANEL_WIDTH }} className="bg-white rounded-2xl h-[94vh] flex flex-col shadow-2xl border border-gray-200 overflow-hidden anim-modal">

          {/* Top bar - drag handle */}
          <div {...dragHandleProps} className="flex items-center justify-between px-5 py-3.5 border-b border-gray-100 bg-white cursor-grab active:cursor-grabbing">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center text-[13px] font-bold text-white shadow-md shadow-blue-600/20 shrink-0">
                {contact.name.charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="text-[14.5px] font-bold text-gray-900 truncate">{contact.name}</h3>
                  <span className={`flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-semibold shrink-0 ${
                    callStatus === 'in_progress' ? 'bg-emerald-50 text-emerald-600' :
                    callStatus === 'ringing' ? 'bg-amber-50 text-amber-600 animate-pulse' :
                    'bg-gray-100 text-gray-500'
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${callStatus === 'in_progress' ? 'bg-emerald-500 anim-pulse' : callStatus === 'ringing' ? 'bg-amber-500' : 'bg-gray-400'}`} />
                    {callStatus === 'in_progress' ? 'Live' : callStatus === 'ringing' ? 'Ringing' : callStatus}
                  </span>
                  {sessionInfo && (
                    <span className="shrink-0 px-2 py-0.5 rounded-md text-[10.5px] font-semibold bg-blue-50 text-blue-600">
                      {sessionInfo}
                    </span>
                  )}
                  {contact.isSecondaryAttempt && (
                    <span className="shrink-0 px-2 py-0.5 rounded-md text-[10.5px] font-semibold bg-amber-50 text-amber-600">
                      Secondary Number
                    </span>
                  )}
                </div>
                <p className="text-[12px] text-gray-400 font-mono">{contact.phone}</p>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-gray-50 border border-gray-100 text-gray-600 font-mono text-[13px] font-medium">
                <Clock className="w-3.5 h-3.5 text-gray-400" />{fmt(elapsed)}
              </div>
              {connected ? <Wifi className="w-4 h-4 text-emerald-500" /> : <WifiOff className="w-4 h-4 text-red-400" />}
              <button
                onClick={handleToggleMute}
                title={muted ? 'Unmute' : 'Mute'}
                className={`p-2 rounded-xl transition-all ${muted ? 'bg-red-50 text-red-500' : 'bg-gray-50 text-gray-400 hover:text-gray-600'}`}
              >
                {muted ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              </button>
              <button
                onClick={() => setMinimized(true)}
                title="Minimize"
                className="p-2 rounded-xl bg-gray-50 text-gray-400 hover:text-gray-600 transition-all"
              >
                <Minimize2 className="w-4 h-4" />
              </button>
              <button onClick={handleEndCall} className="flex items-center gap-1.5 px-3 py-2 bg-red-500 hover:bg-red-400 text-white rounded-xl text-[13px] font-semibold transition-all shadow-md shadow-red-500/15 hover:shadow-red-500/25">
                <PhoneOff className="w-3.5 h-3.5" />End
              </button>
            </div>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto bg-gray-50/60">
            <div className="grid grid-cols-2 gap-5 px-5 py-5 items-start">

              {/* Client Details */}
              <section className="bg-white rounded-2xl border border-gray-200 p-4">
                <div className="flex items-center justify-between mb-3.5">
                  <div className="flex items-center gap-2 text-[12px] font-bold text-gray-400 uppercase tracking-wider">
                    <IdCard className="w-3.5 h-3.5" />Client Details
                  </div>
                  {status && (
                    <span className={`px-2.5 py-0.5 rounded-md text-[11.5px] font-semibold ${STATUS_STYLES[status] || STATUS_STYLES.new}`}>
                      {STATUS_LABELS[status] || status}
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-3.5">
                  <div>
                    <p className="text-[10.5px] font-bold uppercase tracking-wider text-gray-400 mb-1 flex items-center gap-1.5">
                      <Building2 className="w-3 h-3" />Company
                    </p>
                    <p className="text-[13.5px] text-gray-800 font-medium">{company || '—'}</p>
                  </div>
                  <div>
                    <p className="text-[10.5px] font-bold uppercase tracking-wider text-gray-400 mb-1 flex items-center gap-1.5">
                      <Phone className="w-3 h-3" />Phone
                    </p>
                    <p className="text-[13.5px] text-gray-800 font-medium font-mono">{contact.phone}</p>
                  </div>
                  <div>
                    <p className="text-[10.5px] font-bold uppercase tracking-wider text-gray-400 mb-1 flex items-center gap-1.5">
                      <Tag className="w-3 h-3" />Industry / Domain
                    </p>
                    <p className="text-[13.5px] text-gray-800 font-medium">{client.domain || '—'}</p>
                  </div>
                  <div>
                    <p className="text-[10.5px] font-bold uppercase tracking-wider text-gray-400 mb-1 flex items-center gap-1.5">
                      <Briefcase className="w-3 h-3" />Current Initiative
                    </p>
                    <p className="text-[13.5px] text-gray-800 font-medium">{client.project || '—'}</p>
                  </div>
                </div>

                {notes && (
                  <div className="mt-3.5 pt-3.5 border-t border-gray-100">
                    <p className="text-[10.5px] font-bold uppercase tracking-wider text-gray-400 mb-1">Notes</p>
                    <p className="text-[13px] text-gray-600 leading-relaxed">{notes}</p>
                  </div>
                )}

                {projects.length > 0 && (
                  <div className="mt-3.5 pt-3.5 border-t border-gray-100">
                    <p className="text-[10.5px] font-bold uppercase tracking-wider text-gray-400 mb-2 flex items-center gap-1.5">
                      <FolderKanban className="w-3 h-3" />Similar Past Work
                    </p>
                    <div className="grid grid-cols-1 gap-2">
                      {projects.slice(0, 3).map((p) => (
                        <div key={p.name} className="p-2.5 rounded-lg bg-indigo-50/60 border border-indigo-100">
                          <div className="flex items-center justify-between gap-2 mb-1">
                            <span className="text-[13px] font-semibold text-gray-800">{p.name}</span>
                            {p.domain && <span className="shrink-0 text-[10.5px] font-semibold text-indigo-500">{p.domain}</span>}
                          </div>
                          {p.summary && <p className="text-[12.5px] text-gray-600 leading-snug">{p.summary}</p>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </section>

              {/* AI Coaching */}
              <section>
                <div className="flex items-center justify-between mb-2.5">
                  <div className="flex items-center gap-2 text-[12px] font-bold text-gray-400 uppercase tracking-wider">
                    <Zap className="w-3.5 h-3.5" />AI Coaching
                  </div>
                  <button onClick={toggleProvider} className="px-2.5 py-1 text-[10.5px] font-bold uppercase tracking-wider bg-white text-gray-400 border border-gray-200 rounded-md hover:text-gray-600 hover:border-gray-300 transition-all">
                    {aiProvider}
                  </button>
                </div>

                {!suggestion ? (
                  <div className="flex flex-col items-center justify-center py-12 text-gray-300 bg-white rounded-2xl border border-dashed border-gray-200">
                    <Zap className="w-9 h-9 mb-3 anim-float" />
                    <p className="text-[13px] text-center px-6">AI suggestions will appear here once the conversation starts...</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-2.5">
                    <div className={`col-span-2 p-3.5 rounded-xl border flex items-center gap-3 ${ss.bg} ${ss.border} anim-enter`}>
                      <TrendingUp className={`w-4 h-4 ${ss.color} shrink-0`} />
                      <span className={`text-[10.5px] font-bold uppercase tracking-wider ${ss.color}`}>Sentiment</span>
                      <span className={`text-[13.5px] font-bold ${ss.color}`}>{suggestion.sentiment}</span>
                    </div>

                    <div className="col-span-2 p-3.5 rounded-xl bg-blue-50 border border-blue-100 anim-enter delay-1">
                      <div className="flex items-center gap-2 mb-1.5">
                        <Lightbulb className="w-3.5 h-3.5 text-blue-600" />
                        <span className="text-[10.5px] font-bold uppercase tracking-wider text-blue-600">Say Next</span>
                      </div>
                      <p className="text-[13.5px] text-gray-700 leading-[1.65]">{suggestion.next_talking_point}</p>
                    </div>

                    {suggestion.clarifying_question && (
                      <div className="p-3.5 rounded-xl bg-teal-50 border border-teal-100 anim-enter delay-2">
                        <div className="flex items-center gap-2 mb-1.5">
                          <HelpCircle className="w-3.5 h-3.5 text-teal-600" />
                          <span className="text-[10.5px] font-bold uppercase tracking-wider text-teal-600">Ask This</span>
                        </div>
                        <p className="text-[13.5px] text-gray-700 leading-[1.65]">{suggestion.clarifying_question}</p>
                      </div>
                    )}

                    {suggestion.objection_handling && (
                      <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-100 anim-enter delay-2">
                        <div className="flex items-center gap-2 mb-1.5">
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                          <span className="text-[10.5px] font-bold uppercase tracking-wider text-amber-600">Handle Objection</span>
                        </div>
                        <p className="text-[13.5px] text-gray-700 leading-[1.65]">{suggestion.objection_handling}</p>
                      </div>
                    )}

                    {suggestion.recommended_project && (
                      <div className="p-3.5 rounded-xl bg-indigo-50 border border-indigo-100 anim-enter delay-2">
                        <div className="flex items-center gap-2 mb-1.5">
                          <Briefcase className="w-3.5 h-3.5 text-indigo-600" />
                          <span className="text-[10.5px] font-bold uppercase tracking-wider text-indigo-600">From Our Portfolio</span>
                        </div>
                        <p className="text-[13.5px] text-gray-700 leading-[1.65]">{suggestion.recommended_project}</p>
                      </div>
                    )}

                    {suggestion.key_insight && (
                      <div className="col-span-2 p-3.5 rounded-xl bg-purple-50 border border-purple-100 anim-enter delay-3">
                        <div className="flex items-center gap-2 mb-1.5">
                          <MessageSquare className="w-3.5 h-3.5 text-purple-600" />
                          <span className="text-[10.5px] font-bold uppercase tracking-wider text-purple-600">Key Insight</span>
                        </div>
                        <p className="text-[13.5px] text-gray-700 leading-[1.65]">{suggestion.key_insight}</p>
                      </div>
                    )}
                  </div>
                )}
              </section>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
