import { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import Dashboard from './components/Dashboard';
import ContactTable from './components/ContactTable';
import CallPanel from './components/CallPanel';
import CallHistory from './components/CallHistory';
import SettingsPanel from './components/SettingsPanel';
import { useTwilioDevice } from './hooks/useTwilioDevice';

function App() {
  const [activePage, setActivePage] = useState('dashboard');
  const [activeCall, setActiveCall] = useState(null);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);
  const { initDevice, makeCall, hangUp, toggleMute, deviceReady, callState } = useTwilioDevice();

  useEffect(() => { initDevice(); }, [initDevice]);

  const handleCallContact = (contact, callId) => setActiveCall({ contact, callId });
  const handleCloseCall = () => { setActiveCall(null); setHistoryRefreshKey((k) => k + 1); };

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      <Navbar activePage={activePage} onNavigate={setActivePage} deviceReady={deviceReady} />
      <main className="flex-1 px-6 pb-8 max-w-[1400px] w-full mx-auto">
        {activePage === 'dashboard' && <Dashboard />}
        {activePage === 'contacts' && (
          <ContactTable onCallContact={handleCallContact} makeCall={makeCall} deviceReady={deviceReady} />
        )}
        {activePage === 'history' && <CallHistory key={historyRefreshKey} />}
        {activePage === 'settings' && <SettingsPanel />}
      </main>

      {activeCall && (
        <CallPanel
          contact={activeCall.contact}
          callId={activeCall.callId}
          onClose={handleCloseCall}
          hangUp={hangUp}
          toggleMute={toggleMute}
          callState={callState}
        />
      )}
    </div>
  );
}

export default App;
