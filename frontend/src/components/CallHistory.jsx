import { useState, useEffect } from 'react';
import {
  Phone, Clock, FileText, Loader2, ChevronDown, ChevronUp,
  PhoneIncoming, PhoneOff, Star, TrendingUp, TrendingDown, Minus,
  CheckCircle2, AlertTriangle, CalendarClock, Lightbulb, ThumbsUp, Target,
} from 'lucide-react';

const sentimentConfig = {
  Positive: { icon: TrendingUp, color: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-200' },
  Neutral: { icon: Minus, color: 'text-amber-600', bg: 'bg-amber-50', border: 'border-amber-200' },
  Negative: { icon: TrendingDown, color: 'text-red-500', bg: 'bg-red-50', border: 'border-red-200' },
};

function ScoreBadge({ score }) {
  const color = score >= 7 ? 'text-emerald-600 bg-emerald-50' : score >= 4 ? 'text-amber-600 bg-amber-50' : 'text-red-500 bg-red-50';
  return (
    <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg ${color}`}>
      <Star className="w-3.5 h-3.5" />
      <span className="text-[13px] font-bold">{score}/10</span>
    </div>
  );
}

function AnalysisSection({ icon: Icon, title, children, color = 'text-gray-400' }) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`w-3.5 h-3.5 ${color}`} />
        <span className="text-[12px] font-bold text-gray-400 uppercase tracking-wider">{title}</span>
      </div>
      {children}
    </div>
  );
}

export default function CallHistory() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);

  useEffect(() => {
    (async () => {
      try { const res = await fetch('/calls/logs'); setLogs(await res.json()); }
      catch (err) { console.error(err); }
      finally { setLoading(false); }
    })();
  }, []);

  // Re-fetch a specific log to check for analysis updates
  useEffect(() => {
    if (!expanded) return;
    const log = logs.find(l => l.id === expanded);
    if (log && log.status === 'completed' && (!log.analysis || log.analysis.error)) {
      console.log(`[Analysis] Polling started for call ${expanded}`);
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts++;
        console.log(`[Analysis] Poll attempt #${attempts} for call ${expanded}`);
        try {
          const res = await fetch('/calls/logs');
          const updated = await res.json();
          setLogs(updated);
          const found = updated.find(l => l.id === expanded);
          if (found?.analysis && !found.analysis.error) {
            console.log(`[Analysis] Success for call ${expanded}`, found.analysis);
            clearInterval(interval);
          } else if (found?.analysis?.error) {
            console.warn(`[Analysis] Still failing for call ${expanded}:`, found.analysis.error);
          }
          if (attempts >= 20) {
            console.error(`[Analysis] Gave up after ${attempts} attempts for call ${expanded}`);
            clearInterval(interval);
          }
        } catch (err) {
          console.error(`[Analysis] Poll error:`, err);
        }
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [expanded]);

  const fmt = (s) => `${Math.floor(s/60)}m ${s%60}s`;

  const renderAnalysis = (analysis) => {
    if (!analysis) return null;
    if (analysis.error) {
      return <p className="text-[13px] text-red-400 mt-3">Analysis failed: {analysis.error}</p>;
    }

    const sentiment = sentimentConfig[analysis.sentiment] || sentimentConfig.Neutral;
    const SentimentIcon = sentiment.icon;

    return (
      <div className="mt-5 space-y-5">
        {/* Summary + Sentiment + Score row */}
        <div className="flex items-start gap-4">
          <div className="flex-1">
            <AnalysisSection icon={FileText} title="Summary">
              <p className="text-[14px] text-gray-700 leading-relaxed">{analysis.summary}</p>
            </AnalysisSection>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg ${sentiment.bg} ${sentiment.border} border`}>
              <SentimentIcon className={`w-3.5 h-3.5 ${sentiment.color}`} />
              <span className={`text-[13px] font-bold ${sentiment.color}`}>{analysis.sentiment}</span>
            </div>
            {analysis.quality_score && <ScoreBadge score={analysis.quality_score} />}
          </div>
        </div>

        {/* Key Points */}
        {analysis.key_points?.length > 0 && (
          <AnalysisSection icon={Lightbulb} title="Key Points" color="text-blue-400">
            <div className="flex flex-wrap gap-2">
              {analysis.key_points.map((p, i) => (
                <span key={i} className="px-3 py-1 bg-blue-50 text-blue-700 text-[13px] rounded-lg border border-blue-100">{p}</span>
              ))}
            </div>
          </AnalysisSection>
        )}

        {/* Went Well + To Improve */}
        <div className="grid grid-cols-2 gap-4">
          {analysis.went_well?.length > 0 && (
            <AnalysisSection icon={ThumbsUp} title="Went Well" color="text-emerald-400">
              <ul className="space-y-1.5">
                {analysis.went_well.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-[13px] text-gray-600">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 mt-0.5 shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>
            </AnalysisSection>
          )}
          {analysis.to_improve?.length > 0 && (
            <AnalysisSection icon={Target} title="To Improve" color="text-amber-400">
              <ul className="space-y-1.5">
                {analysis.to_improve.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-[13px] text-gray-600">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>
            </AnalysisSection>
          )}
        </div>

        {/* Action Items */}
        {analysis.action_items?.length > 0 && (
          <AnalysisSection icon={CheckCircle2} title="Action Items" color="text-indigo-400">
            <ul className="space-y-1.5">
              {analysis.action_items.map((item, i) => (
                <li key={i} className="flex items-start gap-2 text-[13px] text-gray-600">
                  <span className="w-5 h-5 rounded-md bg-indigo-50 text-indigo-500 text-[11px] font-bold flex items-center justify-center shrink-0 mt-px">{i+1}</span>
                  {item}
                </li>
              ))}
            </ul>
          </AnalysisSection>
        )}

        {/* Follow-up Alert */}
        {analysis.follow_up_needed && (
          <div className="flex items-start gap-3 p-4 bg-amber-50 rounded-xl border border-amber-200">
            <CalendarClock className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />
            <div>
              <p className="text-[13px] font-semibold text-amber-700">Follow-up Needed</p>
              {analysis.follow_up_reason && <p className="text-[13px] text-amber-600 mt-0.5">{analysis.follow_up_reason}</p>}
              {analysis.follow_up_date_suggestion && (
                <p className="text-[12px] text-amber-500 mt-1 font-mono">{analysis.follow_up_date_suggestion}</p>
              )}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="py-8 anim-enter">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-[26px] font-extrabold text-gray-900">Call History</h2>
          <p className="text-gray-400 text-[15px] mt-1">{logs.length} calls recorded</p>
        </div>
      </div>

      {loading ? (
        <div className="card flex items-center justify-center py-24">
          <Loader2 className="w-6 h-6 animate-spin text-blue-500 mr-3" />
          <span className="text-[15px] text-gray-400">Loading...</span>
        </div>
      ) : logs.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-24">
          <Phone className="w-12 h-12 text-gray-200 mb-4" />
          <p className="text-[15px] text-gray-400">No calls yet.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {logs.map((log, i) => (
            <div key={log.id} className={`card card-hover hover-glow overflow-hidden anim-enter`} style={{ animationDelay: `${i*30}ms` }}>
              <button
                onClick={() => setExpanded(expanded === log.id ? null : log.id)}
                className="w-full flex items-center justify-between px-6 py-4 hover:bg-gray-50/50 transition-colors"
              >
                <div className="flex items-center gap-4">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                    log.status === 'completed' ? 'bg-emerald-50' : log.status === 'failed' ? 'bg-red-50' : 'bg-gray-100'
                  }`}>
                    {log.status === 'completed' ? <PhoneIncoming className="w-4 h-4 text-emerald-500" /> :
                     log.status === 'failed' ? <PhoneOff className="w-4 h-4 text-red-500" /> :
                     <Phone className="w-4 h-4 text-gray-400" />}
                  </div>
                  <div className="text-left">
                    <p className="text-[15px] font-semibold text-gray-800">{log.contact_name}</p>
                    <p className="text-[13px] text-gray-400 font-mono">{log.phone}</p>
                  </div>
                </div>
                <div className="flex items-center gap-5">
                  {log.analysis?.sentiment && (() => {
                    const s = sentimentConfig[log.analysis.sentiment] || sentimentConfig.Neutral;
                    return <span className={`px-2 py-0.5 rounded-md text-[12px] font-semibold ${s.bg} ${s.color}`}>{log.analysis.sentiment}</span>;
                  })()}
                  {log.analysis?.quality_score && (
                    <span className="text-[12px] font-bold text-gray-500 flex items-center gap-1">
                      <Star className="w-3 h-3 text-amber-400" />{log.analysis.quality_score}/10
                    </span>
                  )}
                  <span className={`badge-hover px-2.5 py-0.5 rounded-md text-[12px] font-semibold ${
                    log.status === 'completed' ? 'bg-emerald-50 text-emerald-600' :
                    log.status === 'failed' ? 'bg-red-50 text-red-500' :
                    'bg-gray-100 text-gray-500'
                  }`}>{log.status}</span>
                  <span className="text-[13px] text-gray-400 flex items-center gap-1.5 font-mono">
                    <Clock className="w-3 h-3" />{fmt(log.duration)}
                  </span>
                  <span className="text-[13px] text-gray-400">{new Date(log.created_at).toLocaleString()}</span>
                  {expanded === log.id ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-300" />}
                </div>
              </button>
              {expanded === log.id && (
                <div className="px-6 pb-5 border-t border-gray-100 anim-enter">
                  {/* Analysis */}
                  {log.status === 'completed' && (!log.analysis || log.analysis.error) && (
                    <div className="mt-5 flex items-center gap-2.5 text-gray-400">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span className="text-[13px]">Analyzing call...</span>
                    </div>
                  )}
                  {log.analysis && !log.analysis.error && renderAnalysis(log.analysis)}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
