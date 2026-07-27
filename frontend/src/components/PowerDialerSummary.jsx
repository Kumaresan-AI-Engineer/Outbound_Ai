import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, CheckCircle2, PhoneMissed, SkipForward, AlertCircle, HelpCircle, Loader2, CalendarClock } from 'lucide-react';

const OUTCOME = {
  completed: { label: 'Completed', icon: CheckCircle2, style: 'bg-emerald-50 text-emerald-600' },
  failed: { label: 'Not Answered', icon: PhoneMissed, style: 'bg-amber-50 text-amber-600' },
  skipped: { label: 'Skipped', icon: SkipForward, style: 'bg-gray-100 text-gray-500' },
  failed_to_place: { label: "Couldn't Connect", icon: AlertCircle, style: 'bg-red-50 text-red-600' },
  unknown: { label: 'Unknown', icon: HelpCircle, style: 'bg-gray-100 text-gray-500' },
};

const fmtDuration = (s) => (s ? `${Math.floor(s / 60)}m ${s % 60}s` : '');

export default function PowerDialerSummary({ history, onClose }) {
  const [rows, setRows] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const resolved = await Promise.all(history.map(async (entry) => {
        if (!entry.callId) return entry; // failed_to_place - nothing to look up
        try {
          const res = await fetch(`/calls/logs/${entry.contact.id}`);
          if (!res.ok) return entry;
          const logs = await res.json();
          // Most recent log for this contact should be this session's call;
          // confirm by call id where possible, otherwise trust local status.
          const match = logs.find((l) => l.id === entry.callId) || logs[0];
          if (!match) return entry;
          return {
            ...entry,
            status: match.status || entry.status,
            duration: match.duration,
            summary: match.analysis?.summary,
            comment: match.analysis?.follow_up_reason,
            followUpDate: match.follow_up_date,
          };
        } catch {
          return entry;
        }
      }));
      if (!cancelled) setRows(resolved);
    })();
    return () => { cancelled = true; };
  }, [history]);

  const counts = (rows || history).reduce((acc, r) => {
    acc[r.status] = (acc[r.status] || 0) + 1;
    return acc;
  }, {});

  return createPortal(
    <div className="fixed inset-0 bg-gray-900/30 backdrop-blur-sm z-50 flex items-center justify-center p-6">
      <div className="bg-white rounded-2xl w-full max-w-[600px] max-h-[80vh] flex flex-col shadow-2xl border border-gray-200 anim-modal overflow-hidden">
        <div className="flex items-center justify-between px-7 pt-7 pb-5 border-b border-gray-100 shrink-0">
          <div>
            <h3 className="text-[18px] font-bold text-gray-900">Power Call Session Ended</h3>
            <p className="text-[13px] text-gray-400 mt-0.5">
              {counts.completed || 0} completed · {counts.failed || 0} not answered · {(counts.skipped || 0) + (counts.failed_to_place || 0)} skipped
            </p>
          </div>
          <button onClick={onClose} className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-all">
            <X className="w-4.5 h-4.5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-7 py-4">
          {!rows ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-5 h-5 animate-spin text-blue-500 mr-3" />
              <span className="text-[14px] text-gray-400">Confirming outcomes...</span>
            </div>
          ) : (
            <div className="space-y-2">
              {rows.map((r, i) => {
                const outcome = OUTCOME[r.status] || OUTCOME.unknown;
                const Icon = outcome.icon;
                return (
                  <div key={i} className="px-4 py-3 bg-gray-50 rounded-xl">
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${outcome.style}`}>
                        <Icon className="w-4 h-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-[14px] font-semibold text-gray-800 truncate">{r.contact.name}</p>
                        {r.summary && !r.comment && <p className="text-[12px] text-gray-400 truncate">{r.summary}</p>}
                      </div>
                      {r.duration > 0 && <span className="text-[12px] text-gray-400 font-mono shrink-0">{fmtDuration(r.duration)}</span>}
                      <span className={`px-2 py-0.5 rounded-md text-[11px] font-semibold shrink-0 ${outcome.style}`}>{outcome.label}</span>
                    </div>
                    {r.comment && (
                      <div className="flex items-start gap-1.5 mt-2 pt-2 pl-11 border-t border-gray-200/70">
                        <CalendarClock className="w-3.5 h-3.5 text-amber-500 mt-0.5 shrink-0" />
                        <p className="text-[12px] text-gray-500">
                          {r.comment}
                          {r.followUpDate && (
                            <span className="text-gray-400"> — follow up {new Date(r.followUpDate).toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' })}</span>
                          )}
                        </p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="px-7 py-4 border-t border-gray-100 shrink-0">
          <button onClick={onClose} className="w-full py-2.5 btn-primary text-[15px] text-center">Done</button>
        </div>
      </div>
    </div>,
    document.body
  );
}
