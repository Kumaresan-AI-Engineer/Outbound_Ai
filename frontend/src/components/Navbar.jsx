import { LayoutDashboard, Users, History, Settings, Headphones, Wifi, WifiOff } from 'lucide-react';

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', id: 'dashboard' },
  { icon: Users, label: 'Contacts', id: 'contacts' },
  { icon: History, label: 'History', id: 'history' },
  { icon: Settings, label: 'Settings', id: 'settings' },
];

export default function Navbar({ activePage, onNavigate, deviceReady }) {
  return (
    <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-xl border-b border-gray-200/80">
      <div className="max-w-[1400px] mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center shadow-md shadow-blue-600/20">
            <Headphones className="w-4 h-4 text-white" />
          </div>
          <span className="text-[18px] font-extrabold text-gray-900 tracking-tight">
            Outbound<span className="text-blue-600">AI</span>
          </span>
        </div>

        {/* Nav tabs */}
        <nav className="flex items-center gap-1 bg-gray-100 rounded-xl p-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = activePage === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-[14px] font-semibold transition-all duration-300 ${
                  active
                    ? 'bg-white text-blue-600 shadow-sm shadow-blue-500/10'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-white/50'
                }`}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </button>
            );
          })}
        </nav>

        {/* Status */}
        <div className="flex items-center gap-4">
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-[13px] font-semibold ${
            deviceReady ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600'
          }`}>
            {deviceReady ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
            {deviceReady ? 'Ready' : 'Connecting...'}
          </div>
          <div className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center text-[11px] font-bold">
            BA
          </div>
        </div>
      </div>
    </header>
  );
}
