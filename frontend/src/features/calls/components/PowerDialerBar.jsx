import { Phone, Pause, Play, SkipForward, Square } from 'lucide-react';

export default function PowerDialerBar({ contacts, currentIndex, paused, onPause, onResume, onSkip, onStop }) {
  const total = contacts.length;
  const current = contacts[currentIndex];
  const progressPct = total > 0 ? Math.min(100, Math.round(((currentIndex + 1) / total) * 100)) : 0;

  return (
    <div className="sticky top-16 z-30 bg-blue-600 text-white shadow-md">
      <div className="max-w-[1400px] mx-auto px-6 py-2.5 flex items-center gap-4">
        <div className="flex items-center gap-2 shrink-0">
          <span className="flex items-center justify-center w-6 h-6 rounded-full bg-white/15">
            <Phone className="w-3.5 h-3.5" />
          </span>
          <span className="text-[13px] font-bold">Power Calling</span>
        </div>

        <div className="h-4 w-px bg-white/25 shrink-0" />

        <div className="flex-1 min-w-0 flex items-center gap-3">
          <span className="text-[13px] font-semibold shrink-0">
            {Math.min(currentIndex + 1, total)} of {total}
          </span>
          <div className="flex-1 h-1.5 bg-white/20 rounded-full overflow-hidden max-w-[200px]">
            <div className="h-full bg-white rounded-full transition-all duration-500" style={{ width: `${progressPct}%` }} />
          </div>
          {current && (
            <span className="text-[13px] text-white/90 truncate">
              {paused ? 'Paused on' : 'Calling'} <span className="font-semibold">{current.name}</span>
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {paused ? (
            <button onClick={onResume} className="flex items-center gap-1.5 px-3 py-1.5 bg-white text-blue-600 rounded-lg text-[13px] font-semibold hover:bg-blue-50 transition-all">
              <Play className="w-3.5 h-3.5" />Resume
            </button>
          ) : (
            <button onClick={onPause} className="flex items-center gap-1.5 px-3 py-1.5 bg-white/15 hover:bg-white/25 rounded-lg text-[13px] font-semibold transition-all">
              <Pause className="w-3.5 h-3.5" />Pause
            </button>
          )}
          <button onClick={onSkip} className="flex items-center gap-1.5 px-3 py-1.5 bg-white/15 hover:bg-white/25 rounded-lg text-[13px] font-semibold transition-all">
            <SkipForward className="w-3.5 h-3.5" />Skip
          </button>
          <button onClick={onStop} className="flex items-center gap-1.5 px-3 py-1.5 bg-red-500 hover:bg-red-400 rounded-lg text-[13px] font-semibold transition-all">
            <Square className="w-3 h-3" />End Session
          </button>
        </div>
      </div>
    </div>
  );
}
