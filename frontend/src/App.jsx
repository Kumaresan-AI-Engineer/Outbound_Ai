import { useState, useEffect, useRef } from 'react';
import Navbar from './components/Navbar';
import Dashboard from './components/Dashboard';
import ContactTable from './components/ContactTable';
import CallPanel from './components/CallPanel';
import CallHistory from './components/CallHistory';
import SettingsPanel from './components/SettingsPanel';
import ProjectsPanel from './components/ProjectsPanel';
import PowerDialerBar from './components/PowerDialerBar';
import PowerDialerSummary from './components/PowerDialerSummary';
import { useTwilioDevice } from './hooks/useTwilioDevice';
import { usePowerDialer } from './hooks/usePowerDialer';
import { useDialer } from './hooks/useDialer';

const DEVICE_FREE_STATES = ['disconnected', 'idle'];
const MANUAL_CALL_TIMEOUT_MS = 25000; // absolute upper bound before a hung manual call is treated as failed

function App() {
  const [activePage, setActivePage] = useState('dashboard');
  const [activeCall, setActiveCall] = useState(null);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);
  const [showSummary, setShowSummary] = useState(false);
  const { initDevice, makeCall, hangUp, toggleMute, deviceReady, callState } = useTwilioDevice();
  const powerDialer = usePowerDialer({ makeCall, hangUp });
  const { placeCall } = useDialer(makeCall);
  const wasSessionActiveRef = useRef(false);
  // Manual (non-power-dial) no-answer -> secondary-number retry. gen guards
  // against a slow redial landing after the agent has already moved on to a
  // different call; retriedIds ensures at most one retry per manual call.
  const manualCallGenRef = useRef(0);
  const manualRetriedIdsRef = useRef(new Set());
  // callIds ever confirmed as genuinely answered (status reached
  // 'in_progress' at some point). Sticky by design - a fully completed call
  // later reports 'completed', not 'in_progress', so checking only the
  // *latest* status would be a race that could misfire the safety nets
  // below and redial the secondary number right after a normal, successful
  // call. Once a callId is answered, it can never become retry-eligible.
  const answeredCallIdsRef = useRef(new Set());
  const manualCallTimeoutRef = useRef(null);

  useEffect(() => { initDevice(); }, [initDevice]);

  // The fast, event-driven "Device is free" signal - drives the queue's
  // auto-advance. Safe to call unconditionally: usePowerDialer no-ops this
  // when no session is running or the callId doesn't match its current call.
  useEffect(() => {
    if (DEVICE_FREE_STATES.includes(callState)) {
      powerDialer.onDeviceFreed(activeCall?.callId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [callState]);

  // Manual-flow fallback: the backend's Twilio status webhook is the normal
  // source of truth for "did the callee pick up", but it isn't guaranteed to
  // fire cleanly for every rejection (e.g. a Twilio trial account blocking a
  // call to an unverified number). 'in_progress' is the one status that only
  // ever lands once Twilio's "answered" event fires for the callee leg - if
  // the browser's own call leg ends and we never saw that, there is zero
  // risk of interrupting a real conversation, so it's safe to treat it as a
  // failure and fall back to the secondary number.
  useEffect(() => {
    if (powerDialer.sessionActive) return; // the queue has its own device-freed handling
    if (!DEVICE_FREE_STATES.includes(callState)) return;
    if (!activeCall) return;
    const { callId, contact } = activeCall;
    if (!answeredCallIdsRef.current.has(callId)) {
      tryRetrySecondary(contact);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [callState]);

  // Show the end-of-session summary exactly once, on the active->inactive edge.
  useEffect(() => {
    if (wasSessionActiveRef.current && !powerDialer.sessionActive) {
      setShowSummary(true);
    }
    wasSessionActiveRef.current = powerDialer.sessionActive;
  }, [powerDialer.sessionActive]);

  const clearManualCallTimeout = () => {
    if (manualCallTimeoutRef.current) {
      clearTimeout(manualCallTimeoutRef.current);
      manualCallTimeoutRef.current = null;
    }
  };

  // Absolute safety net for the manual-call flow: some rejections (e.g. a
  // Twilio trial-account block on an unverified number) may never produce a
  // clean status callback OR a browser-side disconnect event at all. If
  // nothing has resolved a call within a generous window, force it closed.
  // tryRetrySecondary() below is itself idempotent per contact, so arming
  // this same timeout for the secondary-number attempt too is harmless -
  // worst case it just force-closes a stuck secondary call with no further
  // retry, instead of leaving the agent staring at a frozen panel forever.
  const armManualCallTimeout = (contact, callId) => {
    clearManualCallTimeout();
    manualCallTimeoutRef.current = setTimeout(() => {
      manualCallTimeoutRef.current = null;
      if (answeredCallIdsRef.current.has(callId)) return; // genuinely answered - leave it alone
      console.warn(`[App] Call ${callId} never resolved within ${MANUAL_CALL_TIMEOUT_MS}ms - forcing failure`);
      hangUp();
      tryRetrySecondary(contact);
    }, MANUAL_CALL_TIMEOUT_MS);
  };

  const handleCallContact = (contact, callId) => {
    manualCallGenRef.current += 1; // a fresh manual call gets its own retry attempt
    manualRetriedIdsRef.current.delete(contact.id);
    setActiveCall({ contact, callId });
    armManualCallTimeout(contact, callId);
  };
  const handleCloseCall = () => {
    // During a power-dial session, the queue's own advance logic owns
    // activeCall (moving it to the next contact, or to null once the queue
    // is exhausted) - clearing it here too would race with that and could
    // wipe out the next call right after it starts.
    if (!powerDialer.sessionActive) setActiveCall(null);
    setHistoryRefreshKey((k) => k + 1);
  };
  const handleStartPowerCall = (contacts) => {
    manualCallGenRef.current += 1; // invalidate any manual retry still in flight
    clearManualCallTimeout();
    powerDialer.start(contacts, { setActiveCall });
  };

  // Manual-call flow only: no-answer/busy/failed on the primary number
  // triggers exactly one automatic redial to the contact's secondary
  // number, mirroring the power dialer's own retry rule.
  const redialSecondary = async (contact, secondaryPhone, gen) => {
    try {
      const dialContact = { ...contact, phone: secondaryPhone, isSecondaryAttempt: true };
      const { callId } = await placeCall(dialContact);
      if (gen !== manualCallGenRef.current) return; // superseded by a newer manual call or a power-dial session
      setActiveCall({ contact: dialContact, callId });
      armManualCallTimeout(dialContact, callId);
    } catch (err) {
      console.error('[App] Secondary-number redial failed:', err);
    }
  };
  const tryRetrySecondary = (contact) => {
    const secondary = contact.secondary_phone;
    if (!secondary || secondary === contact.phone) return;
    if (manualRetriedIdsRef.current.has(contact.id)) return;
    manualRetriedIdsRef.current.add(contact.id);
    redialSecondary(contact, secondary, manualCallGenRef.current);
  };
  const handleCallStatusChange = (callId, status) => {
    powerDialer.reportDisposition(callId, status);
    if (status === 'in_progress') answeredCallIdsRef.current.add(callId);
    if (powerDialer.sessionActive) return; // the queue owns its own retry logic
    if (status !== 'failed') return; // 'completed' means the primary number was answered
    if (!activeCall || activeCall.callId !== callId) return;
    tryRetrySecondary(activeCall.contact);
  };

  const sessionInfo = powerDialer.sessionActive
    ? `${powerDialer.currentIndex + 1} of ${powerDialer.contacts.length}`
    : undefined;

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      <Navbar activePage={activePage} onNavigate={setActivePage} deviceReady={deviceReady} />
      {powerDialer.sessionActive && (
        <PowerDialerBar
          contacts={powerDialer.contacts}
          currentIndex={powerDialer.currentIndex}
          paused={powerDialer.paused}
          onPause={powerDialer.pause}
          onResume={powerDialer.resume}
          onSkip={powerDialer.skip}
          onStop={powerDialer.stop}
        />
      )}
      <main className="flex-1 px-6 pb-8 max-w-[1400px] w-full mx-auto">
        {activePage === 'dashboard' && <Dashboard />}
        {activePage === 'contacts' && (
          <ContactTable
            onCallContact={handleCallContact}
            makeCall={makeCall}
            deviceReady={deviceReady}
            onStartPowerCall={handleStartPowerCall}
            sessionActive={powerDialer.sessionActive}
          />
        )}
        {activePage === 'projects' && <ProjectsPanel />}
        {activePage === 'history' && <CallHistory key={historyRefreshKey} />}
        {activePage === 'settings' && <SettingsPanel />}
      </main>

      {activeCall && (
        <CallPanel
          key={activeCall.callId}
          contact={activeCall.contact}
          callId={activeCall.callId}
          onClose={handleCloseCall}
          hangUp={hangUp}
          toggleMute={toggleMute}
          onStatusChange={handleCallStatusChange}
          sessionInfo={sessionInfo}
        />
      )}

      {showSummary && (
        <PowerDialerSummary history={powerDialer.history} onClose={() => setShowSummary(false)} />
      )}
    </div>
  );
}

export default App;
