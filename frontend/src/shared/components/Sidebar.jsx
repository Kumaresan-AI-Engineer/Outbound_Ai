import { Users, History, Settings, Headphones, Activity } from 'lucide-react';

const navItems = [
  { icon: Users, label: 'Contacts', id: 'contacts' },
  { icon: History, label: 'History', id: 'history' },
  { icon: Settings, label: 'Settings', id: 'settings' },
];

export default function Sidebar({ activePage, onNavigate }) {
  return (
    <aside className="w-[260px] bg-sand-50 border-r border-sand-200 flex flex-col h-screen sticky top-0">
      {/* Brand */}
      <div className="px-6 pt-8 pb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-sand-900 rounded-xl flex items-center justify-center">
            <Headphones className="w-[18px] h-[18px] text-sand-100" />
          </div>
          <div>
            <h1 className="text-[15px] font-bold text-sand-900 tracking-tight leading-none">OutboundAI</h1>
            <p className="text-[10px] text-sand-400 font-medium mt-0.5 tracking-widest uppercase">Call Assistant</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 space-y-0.5">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = activePage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-150 ${
                active
                  ? 'bg-sand-900 text-sand-50'
                  : 'text-sand-500 hover:text-sand-800 hover:bg-sand-200/60'
              }`}
            >
              <Icon className="w-[16px] h-[16px]" />
              {item.label}
            </button>
          );
        })}
      </nav>

      {/* Status pill */}
      <div className="mx-3 mb-4">
        <div className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-forest-bg border border-forest/10">
          <Activity className="w-3.5 h-3.5 text-forest" />
          <span className="text-[11px] font-semibold text-forest">System Active</span>
        </div>
      </div>

      {/* User */}
      <div className="px-4 py-4 border-t border-sand-200">
        <div className="flex items-center gap-3 px-2">
          <div className="w-8 h-8 rounded-lg bg-clay text-white flex items-center justify-center text-[11px] font-bold">
            BA
          </div>
          <div className="flex-1">
            <p className="text-[12px] font-semibold text-sand-800">BA Agent</p>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-forest animate-breathe" />
              <span className="text-[10px] text-sand-400">Online</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
