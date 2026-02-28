import { useEffect, useRef, useState } from 'react';
import {
  Mic, MicOff, PhoneOff, Clock, Wifi, WifiOff,
  Lightbulb, AlertTriangle, TrendingUp, MessageSquare, Zap, Radio, Copy, Check
} from 'lucide-react';
import { useCallPolling } from '../hooks/useCallPolling';

const SENTIMENT = {
  Positive: { color: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-100' },
  Neutral: { color: 'text-gray-500', bg: 'bg-gray-50', border: 'border-gray-200' },
  Negative: { color: 'text-red-600', bg: 'bg-red-50', border: 'border-red-100' },
};

export default function CallPanel({ contact, callId, onClose, hangUp: twilioHangUp, toggleMute: twilioToggleMute, callState }) {
  const { connect, disconnect, send, transcript, suggestion, callStatus, connected } = useCallPolling(callId);
  const [muted, setMuted] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [aiProvider, setAiProvider] = useState('groq');
  const [copied, setCopied] = useState(false);
  const transcriptRef = useRef(null);

  useEffect(() => { connect(); return () => disconnect(); }, [callId]);
  useEffect(() => { const i = setInterval(() => setElapsed((e) => e + 1), 1000); return () => clearInterval(i); }, [callStatus]);
  useEffect(() => {
    requestAnimationFrame(() => { if (transcriptRef.current) transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight + 100; });
  }, [transcript, transcript.length]);

  const fmt = (s) => `${Math.floor(s/60).toString().padStart(2,'0')}:${(s%60).toString().padStart(2,'0')}`;
  const handleEndCall = () => { if (twilioHangUp) twilioHangUp(); disconnect(); setTimeout(() => onClose(), 500); };
  const toggleProvider = () => { const n = aiProvider === 'groq' ? 'openai' : 'groq'; setAiProvider(n); send({ type: 'change_provider', provider: n }); };

  const copyTranscript = () => {
    const text = transcript.map(e => `[${e.speaker}]: ${e.text}`).join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const ss = SENTIMENT[suggestion?.sentiment] || SENTIMENT.Neutral;

  return (
    <div className="fixed inset-0 bg-gray-900/25 backdrop-blur-sm z-50 flex items-center justify-center p-6">
      <div className="bg-white rounded-2xl w-full max-w-[1100px] h-[88vh] flex flex-col shadow-2xl border border-gray-200 overflow-hidden anim-modal">

        {/* Top bar */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-white">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center text-[14px] font-bold text-white shadow-md shadow-blue-600/20">
              {contact.name.charAt(0).toUpperCase()}
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h3 className="text-[16px] font-bold text-gray-900">{contact.name}</h3>
                <span className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-[12px] font-semibold ${
                  callStatus === 'in_progress' ? 'bg-emerald-50 text-emerald-600' :
                  callStatus === 'ringing' ? 'bg-amber-50 text-amber-600 animate-pulse' :
                  'bg-gray-100 text-gray-500'
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${callStatus === 'in_progress' ? 'bg-emerald-500 anim-pulse' : callStatus === 'ringing' ? 'bg-amber-500' : 'bg-gray-400'}`} />
                  {callStatus === 'in_progress' ? 'Live' : callStatus === 'ringing' ? 'Ringing' : callStatus}
                </span>
              </div>
              <p className="text-[13px] text-gray-400 font-mono">{contact.phone}</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50 border border-gray-100 text-gray-600 font-mono text-[14px] font-medium">
              <Clock className="w-3.5 h-3.5 text-gray-400" />{fmt(elapsed)}
            </div>
            {connected ? <Wifi className="w-4 h-4 text-emerald-500" /> : <WifiOff className="w-4 h-4 text-red-400" />}
            <button onClick={handleEndCall} className="flex items-center gap-2 px-4 py-2 bg-red-500 hover:bg-red-400 text-white rounded-xl text-[14px] font-semibold transition-all shadow-md shadow-red-500/15 hover:shadow-red-500/25">
              <PhoneOff className="w-4 h-4" />End
            </button>
          </div>
        </div>

        {/* Body: 3 column */}
        <div className="flex-1 flex overflow-hidden">

          {/* Transcript */}
          <div className="flex-1 flex flex-col border-r border-gray-100">
            <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
              <div className="flex items-center gap-2 text-[13px] font-bold text-gray-400 uppercase tracking-wider">
                <MessageSquare className="w-3.5 h-3.5" />Transcript
                {callStatus === 'in_progress' && <Radio className="w-3 h-3 text-emerald-500 anim-pulse" />}
              </div>
              <div className="flex items-center gap-2">
                <button onClick={copyTranscript} className="flex items-center gap-1.5 px-2.5 py-1 text-[12px] font-semibold text-gray-400 hover:text-gray-600 bg-gray-50 hover:bg-gray-100 rounded-lg transition-all">
                  {copied ? <><Check className="w-3 h-3 text-emerald-500" />Copied</> : <><Copy className="w-3 h-3" />Copy</>}
                </button>
                <button
                  onClick={() => { if (twilioToggleMute) { setMuted(twilioToggleMute()); } else { setMuted(!muted); }}}
                  className={`p-2 rounded-lg transition-all ${muted ? 'bg-red-50 text-red-500' : 'bg-gray-50 text-gray-400 hover:text-gray-600'}`}
                >
                  {muted ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <div ref={transcriptRef} className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
              {transcript.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-gray-300">
                  <MessageSquare className="w-10 h-10 mb-3 anim-float" />
                  <p className="text-[14px]">Waiting for conversation...</p>
                </div>
              ) : (
                transcript.map((entry, i) => {
                  const isYou = entry.speaker === 'You';
                  return (
                    <div key={i} className={`anim-enter ${!entry.final ? 'opacity-40' : ''}`}>
                      <div className={`inline-block max-w-[85%] px-4 py-2.5 rounded-2xl ${
                        isYou
                          ? 'bg-blue-600 text-white ml-auto float-right rounded-br-md'
                          : 'bg-gray-100 text-gray-800 rounded-bl-md'
                      }`}>
                        <p className="text-[14px] leading-[1.6]">{entry.text}</p>
                      </div>
                      <div className={`clear-both text-[11px] mt-1 mb-1 ${isYou ? 'text-right' : 'text-left'}`}>
                        <span className={`font-semibold ${isYou ? 'text-blue-400' : 'text-gray-400'}`}>{entry.speaker}</span>
                        <span className="text-gray-300 ml-2 font-mono">{entry.time.toLocaleTimeString()}</span>
                        {!entry.final && <span className="ml-1.5 text-amber-400">typing...</span>}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* AI Panel */}
          <div className="w-[340px] flex flex-col bg-gray-50/50">
            <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
              <div className="flex items-center gap-2 text-[13px] font-bold text-gray-400 uppercase tracking-wider">
                <Zap className="w-3.5 h-3.5" />AI Assist
              </div>
              <button onClick={toggleProvider} className="px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider bg-white text-gray-400 border border-gray-200 rounded-md hover:text-gray-600 hover:border-gray-300 transition-all">
                {aiProvider}
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {!suggestion ? (
                <div className="flex flex-col items-center justify-center h-full text-gray-300">
                  <Zap className="w-10 h-10 mb-3 anim-float" />
                  <p className="text-[14px] text-center">AI suggestions appear here during the call...</p>
                </div>
              ) : (
                <>
                  <div className={`p-4 rounded-xl border ${ss.bg} ${ss.border} anim-enter`}>
                    <div className="flex items-center gap-2 mb-1">
                      <TrendingUp className={`w-3.5 h-3.5 ${ss.color}`} />
                      <span className={`text-[11px] font-bold uppercase tracking-wider ${ss.color}`}>Sentiment</span>
                    </div>
                    <p className={`text-[14px] font-bold ${ss.color} ml-[22px]`}>{suggestion.sentiment}</p>
                  </div>

                  <div className="p-4 rounded-xl bg-blue-50 border border-blue-100 anim-enter delay-1">
                    <div className="flex items-center gap-2 mb-2">
                      <Lightbulb className="w-3.5 h-3.5 text-blue-600" />
                      <span className="text-[11px] font-bold uppercase tracking-wider text-blue-600">Say Next</span>
                    </div>
                    <p className="text-[14px] text-gray-700 leading-[1.7] ml-[22px]">{suggestion.next_talking_point}</p>
                  </div>

                  {suggestion.objection_handling && (
                    <div className="p-4 rounded-xl bg-amber-50 border border-amber-100 anim-enter delay-2">
                      <div className="flex items-center gap-2 mb-2">
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                        <span className="text-[11px] font-bold uppercase tracking-wider text-amber-600">Handle Objection</span>
                      </div>
                      <p className="text-[14px] text-gray-700 leading-[1.7] ml-[22px]">{suggestion.objection_handling}</p>
                    </div>
                  )}

                  {suggestion.key_insight && (
                    <div className="p-4 rounded-xl bg-purple-50 border border-purple-100 anim-enter delay-3">
                      <div className="flex items-center gap-2 mb-2">
                        <MessageSquare className="w-3.5 h-3.5 text-purple-600" />
                        <span className="text-[11px] font-bold uppercase tracking-wider text-purple-600">Key Insight</span>
                      </div>
                      <p className="text-[14px] text-gray-700 leading-[1.7] ml-[22px]">{suggestion.key_insight}</p>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
