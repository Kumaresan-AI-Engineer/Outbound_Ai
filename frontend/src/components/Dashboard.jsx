import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import {
  Phone, Star, Clock, CalendarClock, TrendingUp, TrendingDown, Minus,
  Loader2, Sparkles, CheckCircle2, AlertTriangle, BarChart3, X, User, ChevronDown,
} from 'lucide-react';

function CallVolumeChart({ data }) {
  if (!data?.length) return <p className="text-[13px] text-gray-400 text-center py-8">No call data yet</p>;
  const max = Math.max(...data.map(d => d.count), 1);
  // Build SVG area chart with gradient fill
  const w = 500, h = 140, pad = { top: 10, bottom: 28, left: 0, right: 0 };
  const chartW = w - pad.left - pad.right;
  const chartH = h - pad.top - pad.bottom;
  const stepX = data.length > 1 ? chartW / (data.length - 1) : chartW;

  const pts = data.map((d, i) => ({
    x: pad.left + (data.length > 1 ? i * stepX : chartW / 2),
    y: pad.top + chartH - (d.count / max) * chartH,
    ...d,
  }));

  const linePath = pts.map((p, i) => {
    if (i === 0) return `M ${p.x},${p.y}`;
    const prev = pts[i - 1];
    const cpx = (prev.x + p.x) / 2;
    return `C ${cpx},${prev.y} ${cpx},${p.y} ${p.x},${p.y}`;
  }).join(' ');

  const areaPath = `${linePath} L ${pts[pts.length - 1].x},${pad.top + chartH} L ${pts[0].x},${pad.top + chartH} Z`;

  // Show ~5 date labels spread evenly
  const labelCount = Math.min(data.length, 5);
  const labelIndices = Array.from({ length: labelCount }, (_, i) =>
    Math.round(i * (data.length - 1) / (labelCount - 1 || 1))
  );

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height: '160px' }} preserveAspectRatio="none">
        <defs>
          <linearGradient id="volumeGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        {/* Grid lines */}
        {[0.25, 0.5, 0.75, 1].map(frac => {
          const y = pad.top + chartH - frac * chartH;
          return <line key={frac} x1={pad.left} y1={y} x2={w - pad.right} y2={y} stroke="#f1f5f9" strokeWidth="1" />;
        })}
        {/* Area fill */}
        <path d={areaPath} fill="url(#volumeGrad)" />
        {/* Line */}
        <path d={linePath} fill="none" stroke="#3b82f6" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {/* Dots */}
        {pts.map((p, i) => (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r="5" fill="white" stroke="#3b82f6" strokeWidth="2" opacity="0" className="hover:opacity-100 transition-opacity">
              <title>{`${p.date}: ${p.count} calls`}</title>
            </circle>
            <circle cx={p.x} cy={p.y} r="3" fill="#3b82f6" opacity="0.8">
              <title>{`${p.date}: ${p.count} calls`}</title>
            </circle>
          </g>
        ))}
        {/* Date labels */}
        {labelIndices.map(idx => (
          <text key={idx} x={pts[idx].x} y={h - 4} textAnchor="middle" className="fill-gray-400" style={{ fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
            {data[idx].date.slice(5)}
          </text>
        ))}
      </svg>
    </div>
  );
}

function SentimentChart({ breakdown }) {
  const total = (breakdown?.Positive || 0) + (breakdown?.Neutral || 0) + (breakdown?.Negative || 0) || 1;
  const bars = [
    { label: 'Positive', count: breakdown?.Positive || 0, color: 'bg-emerald-500' },
    { label: 'Neutral', count: breakdown?.Neutral || 0, color: 'bg-amber-400' },
    { label: 'Negative', count: breakdown?.Negative || 0, color: 'bg-red-400' },
  ];
  return (
    <div className="space-y-3">
      {bars.map(b => (
        <div key={b.label}>
          <div className="flex justify-between text-[13px] mb-1">
            <span className="text-gray-600 font-medium">{b.label}</span>
            <span className="text-gray-400">{b.count} ({Math.round(b.count / total * 100)}%)</span>
          </div>
          <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className={`h-full ${b.color} rounded-full transition-all duration-700`}
              style={{ width: `${(b.count / total) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function QualitySparkline({ trend }) {
  if (!trend?.length) return <p className="text-[13px] text-gray-400 text-center py-4">No data yet</p>;
  const scores = trend.map(t => t.avg_score);
  const max = Math.max(...scores, 10);
  const min = Math.min(...scores, 0);
  const range = max - min || 1;
  const w = 300, h = 120, pad = { top: 16, bottom: 28, left: 30, right: 10 };
  const chartW = w - pad.left - pad.right;
  const chartH = h - pad.top - pad.bottom;

  const pts = scores.map((s, i) => ({
    x: pad.left + (scores.length > 1 ? (i / (scores.length - 1)) * chartW : chartW / 2),
    y: pad.top + chartH - ((s - min) / range) * chartH,
    score: s,
  }));

  const linePath = pts.map((p, i) => {
    if (i === 0) return `M ${p.x},${p.y}`;
    const prev = pts[i - 1];
    const cpx = (prev.x + p.x) / 2;
    return `C ${cpx},${prev.y} ${cpx},${p.y} ${p.x},${p.y}`;
  }).join(' ');

  const areaPath = `${linePath} L ${pts[pts.length - 1].x},${pad.top + chartH} L ${pts[0].x},${pad.top + chartH} Z`;

  // Y-axis labels
  const yLabels = [min, min + range / 2, max].map(v => ({
    value: Math.round(v * 10) / 10,
    y: pad.top + chartH - ((v - min) / range) * chartH,
  }));

  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height: '140px' }}>
        <defs>
          <linearGradient id="qualityGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.01" />
          </linearGradient>
        </defs>
        {/* Grid lines + Y labels */}
        {yLabels.map(yl => (
          <g key={yl.value}>
            <line x1={pad.left} y1={yl.y} x2={w - pad.right} y2={yl.y} stroke="#f1f5f9" strokeWidth="1" />
            <text x={pad.left - 6} y={yl.y + 4} textAnchor="end" className="fill-gray-400" style={{ fontSize: '10px', fontFamily: 'var(--font-mono)' }}>
              {yl.value}
            </text>
          </g>
        ))}
        {/* Area */}
        <path d={areaPath} fill="url(#qualityGrad)" />
        {/* Line */}
        <path d={linePath} fill="none" stroke="#8b5cf6" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {/* Dots with score labels */}
        {pts.map((p, i) => (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r="4.5" fill="white" stroke="#8b5cf6" strokeWidth="2" />
            <text x={p.x} y={p.y - 10} textAnchor="middle" className="fill-violet-600" style={{ fontSize: '10px', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
              {p.score}
            </text>
          </g>
        ))}
        {/* X-axis date labels */}
        {trend.map((t, i) => (
          <text key={t.date} x={pts[i].x} y={h - 4} textAnchor="middle" className="fill-gray-400" style={{ fontSize: '10px', fontFamily: 'var(--font-mono)' }}>
            {t.date.slice(5)}
          </text>
        ))}
      </svg>
    </div>
  );
}

const outlookConfig = {
  'Positive': 'bg-emerald-50 text-emerald-600 border-emerald-200',
  'Neutral': 'bg-amber-50 text-amber-600 border-amber-200',
  'Needs Attention': 'bg-red-50 text-red-500 border-red-200',
};

export default function Dashboard() {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [weeklySummary, setWeeklySummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [followUps, setFollowUps] = useState(null);
  const [followUpsOpen, setFollowUpsOpen] = useState(false);
  const [followUpsLoading, setFollowUpsLoading] = useState(false);
  const [todayFollowUps, setTodayFollowUps] = useState([]);
  const [todayBannerExpanded, setTodayBannerExpanded] = useState(false);

  useEffect(() => {
    fetch('/calls/analytics')
      .then(r => r.json())
      .then(data => { setAnalytics(data); setLoading(false); })
      .catch(() => setLoading(false));
    fetch('/calls/follow-ups/today')
      .then(r => r.json())
      .then(data => setTodayFollowUps(data || []))
      .catch(() => {});
  }, []);

  const handleWeeklySummary = async () => {
    setSummaryLoading(true);
    try {
      const data = await fetch('/calls/weekly-summary', { method: 'POST' }).then(r => r.json());
      setWeeklySummary(data);
    } catch { setWeeklySummary({ error: 'Failed to generate summary.' }); }
    setSummaryLoading(false);
  };

  const handleFollowUpsClick = async () => {
    setFollowUpsOpen(true);
    if (!followUps) {
      setFollowUpsLoading(true);
      try {
        const data = await fetch('/calls/follow-ups').then(r => r.json());
        setFollowUps(data);
      } catch { setFollowUps([]); }
      setFollowUpsLoading(false);
    }
  };

  const markFollowUpDone = async (callId) => {
    await fetch(`/calls/follow-ups/${callId}/complete`, { method: 'POST' });
    setTodayFollowUps(prev => prev.filter(f => f.id !== callId));
    if (followUps) setFollowUps(prev => prev.filter(f => f.id !== callId));
    // Refresh analytics count
    fetch('/calls/analytics').then(r => r.json()).then(setAnalytics).catch(() => {});
  };

  const fmt = (s) => `${Math.floor(s / 60)}m ${s % 60}s`;

  if (loading) return (
    <div className="py-8 flex items-center justify-center">
      <Loader2 className="w-6 h-6 animate-spin text-blue-500 mr-3" />
      <span className="text-[15px] text-gray-400">Loading analytics...</span>
    </div>
  );

  const a = analytics || {};
  const qualityTrend = a.recent_quality_trend || [];
  const trendDir = qualityTrend.length >= 2
    ? qualityTrend[qualityTrend.length - 1].avg_score - qualityTrend[0].avg_score
    : 0;

  return (
    <div className="py-8 anim-enter">
      <div className="mb-8">
        <h2 className="text-[26px] font-extrabold text-gray-900">Dashboard</h2>
        <p className="text-gray-400 text-[15px] mt-1">Your call performance at a glance</p>
      </div>

      {/* Today's Follow-ups Banner */}
      {todayFollowUps.length > 0 && (
        <div className="mb-6 anim-enter">
          <button
            onClick={() => setTodayBannerExpanded(!todayBannerExpanded)}
            className="w-full p-4 rounded-2xl bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 hover:border-amber-300 transition-all flex items-center justify-between group"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center icon-hover">
                <CalendarClock className="w-5 h-5 text-amber-600" />
              </div>
              <div className="text-left">
                <p className="text-[15px] font-bold text-amber-800">
                  You have {todayFollowUps.length} follow-up{todayFollowUps.length > 1 ? 's' : ''} due today
                </p>
                <p className="text-[13px] text-amber-600/70">Click to {todayBannerExpanded ? 'collapse' : 'view contacts'}</p>
              </div>
            </div>
            <ChevronDown className={`w-5 h-5 text-amber-400 transition-transform duration-300 ${todayBannerExpanded ? 'rotate-180' : ''}`} />
          </button>

          {todayBannerExpanded && (
            <div className="mt-2 space-y-2 anim-enter">
              {todayFollowUps.map((fu, i) => (
                <div key={fu.id} className="card hover-glow p-4 flex items-center justify-between anim-enter" style={{ animationDelay: `${i * 50}ms` }}>
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-blue-50 flex items-center justify-center">
                      <User className="w-4 h-4 text-blue-500" />
                    </div>
                    <div>
                      <p className="text-[14px] font-semibold text-gray-800">{fu.contact_name}</p>
                      <p className="text-[12px] text-gray-400 font-mono">{fu.phone}</p>
                    </div>
                  </div>
                  {fu.follow_up_reason && (
                    <p className="text-[13px] text-gray-500 flex-1 mx-6 line-clamp-1">{fu.follow_up_reason}</p>
                  )}
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={(e) => { e.stopPropagation(); markFollowUpDone(fu.id); }}
                      className="px-3 py-1.5 rounded-lg text-[12px] font-semibold bg-emerald-50 text-emerald-600 border border-emerald-200 hover:bg-emerald-100 transition-all badge-hover"
                    >
                      <span className="flex items-center gap-1.5"><CheckCircle2 className="w-3 h-3" />Done</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Row 1: Stat Cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          {
            icon: Phone, iconBg: 'bg-blue-50', iconColor: 'text-blue-600',
            label: 'Total Calls', value: a.total_calls || 0,
            sub: `${a.completed_calls || 0} completed, ${a.failed_calls || 0} failed`,
          },
          {
            icon: Star, iconBg: 'bg-amber-50', iconColor: 'text-amber-500',
            label: 'Avg Quality', value: a.avg_quality_score || '—',
            sub: trendDir > 0 ? 'Trending up' : trendDir < 0 ? 'Trending down' : 'Stable',
            trend: trendDir,
          },
          {
            icon: Clock, iconBg: 'bg-indigo-50', iconColor: 'text-indigo-500',
            label: 'Avg Duration', value: fmt(a.avg_duration || 0),
            sub: `Total: ${fmt(a.total_duration || 0)}`,
          },
          {
            icon: CalendarClock, iconBg: 'bg-rose-50', iconColor: 'text-rose-500',
            label: 'Follow-ups', value: a.follow_ups_needed || 0,
            sub: 'Click to view',
            onClick: handleFollowUpsClick,
          },
        ].map((card, i) => {
          const Icon = card.icon;
          return (
            <div
              key={i}
              className={`card hover-glow p-5 anim-enter ${card.onClick ? 'cursor-pointer' : ''}`}
              style={{ animationDelay: `${i * 50}ms` }}
              onClick={card.onClick}
            >
              <div className="flex items-center justify-between mb-3">
                <div className={`w-9 h-9 rounded-xl ${card.iconBg} flex items-center justify-center icon-hover`}>
                  <Icon className={`w-4 h-4 ${card.iconColor}`} />
                </div>
                {card.trend !== undefined && (
                  card.trend > 0 ? <TrendingUp className="w-4 h-4 text-emerald-500" /> :
                  card.trend < 0 ? <TrendingDown className="w-4 h-4 text-red-400" /> :
                  <Minus className="w-4 h-4 text-gray-300" />
                )}
              </div>
              <p className="text-[24px] font-extrabold text-gray-900">{card.value}</p>
              <p className="text-[13px] text-gray-400 mt-0.5">{card.label}</p>
              <p className="text-[12px] text-gray-300 mt-1">{card.sub}</p>
            </div>
          );
        })}
      </div>

      {/* Row 2: Charts */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="card hover-glow p-5 anim-enter" style={{ animationDelay: '200ms' }}>
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="w-4 h-4 text-blue-500" />
            <h3 className="text-[15px] font-bold text-gray-800">Call Volume</h3>
            <span className="text-[12px] text-gray-400 ml-auto">Last 30 days</span>
          </div>
          <CallVolumeChart data={a.calls_by_date} />
        </div>
        <div className="card hover-glow p-5 anim-enter" style={{ animationDelay: '250ms' }}>
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-4 h-4 text-emerald-500" />
            <h3 className="text-[15px] font-bold text-gray-800">Sentiment</h3>
          </div>
          <SentimentChart breakdown={a.sentiment_breakdown} />
        </div>
      </div>

      {/* Row 3: Trend + Actions + Weekly Summary */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card hover-glow p-5 anim-enter" style={{ animationDelay: '300ms' }}>
          <div className="flex items-center gap-2 mb-4">
            <Star className="w-4 h-4 text-amber-500" />
            <h3 className="text-[15px] font-bold text-gray-800">Quality Trend</h3>
            <span className="text-[12px] text-gray-400 ml-auto">Last 7 days</span>
          </div>
          <QualitySparkline trend={a.recent_quality_trend} />
        </div>

        <div className="card hover-glow p-5 anim-enter" style={{ animationDelay: '350ms' }}>
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle2 className="w-4 h-4 text-indigo-500" />
            <h3 className="text-[15px] font-bold text-gray-800">Top Action Items</h3>
          </div>
          {(a.top_action_items || []).length === 0 ? (
            <p className="text-[13px] text-gray-400 text-center py-4">No action items yet</p>
          ) : (
            <div className="space-y-0.5 max-h-48 overflow-y-auto">
              {a.top_action_items.map((item, i) => (
                <div key={i} className="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0">
                  <span className="w-5 h-5 rounded-md bg-indigo-50 text-indigo-500 text-[11px] font-bold flex items-center justify-center shrink-0">{i + 1}</span>
                  <span className="text-[13px] text-gray-700 flex-1 line-clamp-2">{item.item}</span>
                  {item.count > 1 && <span className="text-[11px] text-gray-400 font-mono shrink-0">x{item.count}</span>}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card hover-glow p-5 anim-enter" style={{ animationDelay: '400ms' }}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-blue-500" />
              <h3 className="text-[15px] font-bold text-gray-800">AI Weekly Summary</h3>
            </div>
            <button
              onClick={handleWeeklySummary}
              disabled={summaryLoading}
              className="btn-primary px-3 py-1.5 text-[12px] flex items-center gap-1.5"
            >
              {summaryLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
              {summaryLoading ? 'Generating...' : 'Generate'}
            </button>
          </div>

          {weeklySummary && !weeklySummary.error ? (
            <div className="space-y-3 anim-enter">
              <div className="flex items-center gap-2">
                {weeklySummary.outlook && (
                  <span className={`px-2.5 py-0.5 rounded-md text-[12px] font-semibold border ${outlookConfig[weeklySummary.outlook] || outlookConfig.Neutral}`}>
                    {weeklySummary.outlook}
                  </span>
                )}
              </div>
              <p className="text-[14px] font-semibold text-gray-800">{weeklySummary.headline}</p>

              {weeklySummary.wins?.length > 0 && (
                <div>
                  <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1.5">Wins</p>
                  {weeklySummary.wins.map((w, i) => (
                    <p key={i} className="text-[13px] text-gray-600 flex items-start gap-2 mb-1">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 mt-0.5 shrink-0" />{w}
                    </p>
                  ))}
                </div>
              )}

              {weeklySummary.areas_to_improve?.length > 0 && (
                <div>
                  <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1.5">To Improve</p>
                  {weeklySummary.areas_to_improve.map((a, i) => (
                    <p key={i} className="text-[13px] text-gray-600 flex items-start gap-2 mb-1">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />{a}
                    </p>
                  ))}
                </div>
              )}

              {weeklySummary.top_priority_action && (
                <div className="p-3 bg-blue-50 rounded-xl border border-blue-100">
                  <p className="text-[11px] font-bold text-blue-400 uppercase tracking-wider mb-1">Top Priority</p>
                  <p className="text-[13px] text-blue-700 font-medium">{weeklySummary.top_priority_action}</p>
                </div>
              )}
            </div>
          ) : weeklySummary?.error ? (
            <p className="text-[13px] text-red-400 text-center py-4">{weeklySummary.error}</p>
          ) : (
            <p className="text-[13px] text-gray-400 text-center py-6">
              Click Generate for an AI-powered summary of this week's calls.
            </p>
          )}
        </div>
      </div>

      {/* Follow-ups Modal */}
      {followUpsOpen && createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setFollowUpsOpen(false)}>
          <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" />
          <div
            className="relative bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col anim-enter"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-5 border-b border-gray-100">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-rose-50 flex items-center justify-center">
                  <CalendarClock className="w-5 h-5 text-rose-500" />
                </div>
                <div>
                  <h3 className="text-[18px] font-extrabold text-gray-900">Follow-ups Needed</h3>
                  <p className="text-[13px] text-gray-400">{followUps?.length || 0} contacts to follow up</p>
                </div>
              </div>
              <button onClick={() => setFollowUpsOpen(false)} className="w-8 h-8 rounded-lg hover:bg-gray-100 flex items-center justify-center transition-colors">
                <X className="w-4 h-4 text-gray-400" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-4">
              {followUpsLoading ? (
                <div className="flex items-center justify-center py-16">
                  <Loader2 className="w-5 h-5 animate-spin text-blue-500 mr-2" />
                  <span className="text-[14px] text-gray-400">Loading follow-ups...</span>
                </div>
              ) : !followUps?.length ? (
                <div className="flex flex-col items-center justify-center py-16">
                  <CheckCircle2 className="w-10 h-10 text-emerald-300 mb-3" />
                  <p className="text-[15px] font-semibold text-gray-700">All caught up!</p>
                  <p className="text-[13px] text-gray-400 mt-1">No follow-ups needed right now.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {followUps.map((fu, i) => {
                    const sentimentColor = fu.sentiment === 'Positive' ? 'text-emerald-600 bg-emerald-50' :
                      fu.sentiment === 'Negative' ? 'text-red-500 bg-red-50' : 'text-amber-600 bg-amber-50';

                    // Date status: overdue / today / upcoming
                    const today = new Date(); today.setHours(0,0,0,0);
                    const fuDate = fu.follow_up_date ? new Date(fu.follow_up_date) : null;
                    let dateStatus = 'upcoming', dateBadge = 'bg-blue-50 text-blue-600 border-blue-100';
                    if (fuDate) {
                      const fuDay = new Date(fuDate); fuDay.setHours(0,0,0,0);
                      if (fuDay < today) { dateStatus = 'overdue'; dateBadge = 'bg-red-50 text-red-500 border-red-200'; }
                      else if (fuDay.getTime() === today.getTime()) { dateStatus = 'today'; dateBadge = 'bg-amber-50 text-amber-600 border-amber-200'; }
                    }

                    return (
                      <div key={fu.id} className={`p-4 rounded-xl border hover:shadow-sm transition-all anim-enter ${
                        dateStatus === 'overdue' ? 'border-red-200 bg-red-50/30' :
                        dateStatus === 'today' ? 'border-amber-200 bg-amber-50/30' :
                        'border-gray-100 hover:border-gray-200'
                      }`} style={{ animationDelay: `${i * 40}ms` }}>
                        <div className="flex items-start justify-between mb-2.5">
                          <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-xl bg-blue-50 flex items-center justify-center">
                              <User className="w-4 h-4 text-blue-500" />
                            </div>
                            <div>
                              <p className="text-[15px] font-semibold text-gray-800">{fu.contact_name}</p>
                              <p className="text-[12px] text-gray-400 font-mono">{fu.phone}</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {fu.sentiment && (
                              <span className={`px-2 py-0.5 rounded-md text-[11px] font-semibold ${sentimentColor}`}>{fu.sentiment}</span>
                            )}
                            {fuDate && (
                              <span className={`px-2.5 py-0.5 rounded-md text-[11px] font-semibold border ${dateBadge}`}>
                                {dateStatus === 'overdue' ? 'Overdue' : dateStatus === 'today' ? 'Due Today' :
                                  fuDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                              </span>
                            )}
                            {!fuDate && fu.follow_up_date_suggestion && (
                              <span className="px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-blue-50 text-blue-600 border border-blue-100">
                                {fu.follow_up_date_suggestion}
                              </span>
                            )}
                          </div>
                        </div>

                        {fu.follow_up_reason && (
                          <div className="ml-12 mb-2">
                            <p className="text-[13px] text-gray-600 leading-relaxed">
                              <span className="font-semibold text-gray-700">Reason: </span>{fu.follow_up_reason}
                            </p>
                          </div>
                        )}

                        {fu.summary && (
                          <div className="ml-12 p-3 bg-gray-50 rounded-lg">
                            <p className="text-[12px] text-gray-500 leading-relaxed">{fu.summary}</p>
                          </div>
                        )}

                        <div className="ml-12 mt-2.5 flex items-center justify-between">
                          <p className="text-[11px] text-gray-300">
                            Called {new Date(fu.call_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                          </p>
                          <button
                            onClick={() => markFollowUpDone(fu.id)}
                            className="px-3 py-1.5 rounded-lg text-[12px] font-semibold bg-emerald-50 text-emerald-600 border border-emerald-200 hover:bg-emerald-100 transition-all badge-hover"
                          >
                            <span className="flex items-center gap-1.5"><CheckCircle2 className="w-3 h-3" />Mark Done</span>
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
