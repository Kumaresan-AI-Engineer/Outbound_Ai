import { useRef, useState, useEffect, useCallback } from 'react';
import { useDialer } from './useDialer';

const ADVANCE_DELAY_MS = 400;   // brief pause so back-to-back calls don't feel instantaneous
const SAFETY_NET_MS = 3000;     // force-advance if callState never confirms disconnect
const MAX_CONSECUTIVE_FAILURES = 3;

// Sequential auto-dialer. Advancing is driven by callState (the browser's
// WebRTC leg to Twilio) reaching a terminal value - fast and event-driven,
// not a poll round-trip. Disposition (why a call ended: answered/no-answer/
// busy/failed) is recorded separately from callStatus/backend polling and
// never blocks the advance - it can land a beat late without stalling the
// queue. A ref-based settle-guard makes skip() and natural termination
// mutually exclusive so the same queue slot can never advance twice.
//
// Every dialAt() call is tagged with the session's generation token,
// re-checked against the live token both before dialing and after the async
// placeCall() resolves. Any stale/duplicate/late-firing call from a session
// that has since ended (or been superseded) is a structural no-op - this is
// what makes "loop back to an earlier contact" impossible regardless of
// which particular race would otherwise have triggered it.
export function usePowerDialer({ makeCall, hangUp }) {
  const { placeCall } = useDialer(makeCall);

  const [sessionActive, setSessionActive] = useState(false);
  const [paused, setPaused] = useState(false);
  const [contacts, setContacts] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(-1);
  const [history, setHistory] = useState([]);

  // Control-flow state lives in refs so timeouts/callbacks never act on a
  // stale render's closure; the state above exists purely for rendering.
  const contactsR = useRef([]);
  const indexR = useRef(-1);
  const pausedR = useRef(false);
  const activeR = useRef(false);
  const sessionTokenR = useRef(0);
  const currentCallIdR = useRef(null);
  const settledCallIdR = useRef(null);
  const dispositionR = useRef({});
  const pendingAdvanceR = useRef(null); // null | { index, phoneOverride } - what to dial once resumed
  const failuresR = useRef(0);
  const safetyTimerR = useRef(null);
  const setActiveCallR = useRef(null);
  const retriedSecondaryR = useRef({}); // index -> true once its secondary number has been tried

  const clearSafetyTimer = () => {
    if (safetyTimerR.current) {
      clearTimeout(safetyTimerR.current);
      safetyTimerR.current = null;
    }
  };
  useEffect(() => clearSafetyTimer, []);

  const recordHistory = (contact, callId, status) => {
    setHistory((prev) => [...prev, { contact, callId, status }]);
  };

  const endSession = () => {
    sessionTokenR.current += 1; // invalidate any pending scheduled work from this session
    activeR.current = false;
    indexR.current = -1;
    currentCallIdR.current = null;
    clearSafetyTimer();
    setSessionActive(false);
    setCurrentIndex(-1);
    setActiveCallR.current?.(null);
    console.log('[PowerDialer] Session ended');
  };

  const dialAt = async (index, token, phoneOverride) => {
    if (token !== sessionTokenR.current) {
      console.log(`[PowerDialer] Ignoring stale dialAt(${index}) from a superseded session`);
      return;
    }
    const list = contactsR.current;
    if (index >= list.length) { endSession(); return; }

    const original = list[index];
    const contact = phoneOverride ? { ...original, phone: phoneOverride, isSecondaryAttempt: true } : original;
    console.log(`[PowerDialer] Dialing index ${index}: ${contact.name}${phoneOverride ? ' (secondary number)' : ''}`);
    indexR.current = index;
    settledCallIdR.current = null;
    clearSafetyTimer();
    setCurrentIndex(index);

    try {
      const { callId } = await placeCall(contact);
      if (token !== sessionTokenR.current) {
        console.log(`[PowerDialer] Session ended while placing call to ${contact.name} - hanging up`);
        hangUp();
        return;
      }
      currentCallIdR.current = callId;
      failuresR.current = 0;
      setActiveCallR.current?.({ contact, callId });
    } catch (err) {
      console.error('[PowerDialer] Failed to place call:', err);
      failuresR.current += 1;
      recordHistory(contact, null, 'failed_to_place');
      if (failuresR.current >= MAX_CONSECUTIVE_FAILURES) {
        console.error('[PowerDialer] Too many consecutive placement failures - stopping session');
        endSession();
        return;
      }
      dialAt(index + 1, token);
    }
  };

  const start = useCallback((selectedContacts, { setActiveCall }) => {
    if (!selectedContacts?.length) return;
    const token = ++sessionTokenR.current;
    setActiveCallR.current = setActiveCall;
    contactsR.current = selectedContacts;
    dispositionR.current = {};
    pendingAdvanceR.current = null;
    failuresR.current = 0;
    pausedR.current = false;
    activeR.current = true;
    retriedSecondaryR.current = {};
    setContacts(selectedContacts);
    setHistory([]);
    setPaused(false);
    setSessionActive(true);
    console.log(`[PowerDialer] Starting session (token ${token}) with ${selectedContacts.length} contacts`);
    dialAt(0, token);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The one place a queue slot is actually closed out. Guarded so skip() and
  // the natural callState-terminal path can never both advance it.
  const settle = (callId, status) => {
    if (!activeR.current) return;
    if (settledCallIdR.current === callId) return;
    settledCallIdR.current = callId;
    clearSafetyTimer();
    console.log(`[PowerDialer] Settling call ${callId} as "${status}"`);

    const index = indexR.current;
    const contact = contactsR.current[index];
    if (contact) recordHistory(contact, callId, status);

    // 'in_progress' is the one status that only ever lands once Twilio's own
    // "answered" event fires for the callee leg - everything else (failed,
    // unknown, or still ringing/connecting when the browser leg tore down,
    // e.g. a Twilio trial-account block that doesn't fire a clean status
    // callback) means we have zero confirmation of a real pickup. 'skipped'
    // is excluded since that's an explicit agent action, not a disposition.
    // Try the contact's secondary number once before moving on.
    const secondary = contact?.secondary_phone;
    const noConfirmedPickup = status !== 'in_progress' && status !== 'completed' && status !== 'skipped';
    const shouldRetrySecondary = noConfirmedPickup && secondary && secondary !== contact.phone && !retriedSecondaryR.current[index];
    if (shouldRetrySecondary) {
      retriedSecondaryR.current[index] = true;
      console.log(`[PowerDialer] ${contact.name} didn't answer the primary number - trying secondary`);
    }
    const nextAction = shouldRetrySecondary ? { index, phoneOverride: secondary } : { index: index + 1 };

    if (pausedR.current) {
      pendingAdvanceR.current = nextAction;
      return;
    }
    const token = sessionTokenR.current;
    setTimeout(() => dialAt(nextAction.index, token, nextAction.phoneOverride), ADVANCE_DELAY_MS);
  };

  // Called by App.jsx when Twilio's browser-side call object reaches a
  // terminal state (disconnected/idle/error) - the fast, event-driven signal
  // that the Device is free. This is what actually advances the queue.
  const onDeviceFreed = (callId) => {
    if (!activeR.current || !callId || callId !== currentCallIdR.current) return;
    settle(callId, dispositionR.current[callId] || 'unknown');
  };

  // Called by CallPanel's onStatusChange whenever the backend/Twilio-status
  // poll updates. Records disposition only - does not drive advancing. If
  // callState never confirms disconnect (missed SDK event), this starts a
  // safety-net timer so the queue can't wedge on a single stuck call.
  const reportDisposition = (callId, status) => {
    dispositionR.current[callId] = status;
    if (
      activeR.current &&
      callId === currentCallIdR.current &&
      (status === 'completed' || status === 'failed') &&
      settledCallIdR.current !== callId &&
      !safetyTimerR.current
    ) {
      safetyTimerR.current = setTimeout(() => {
        // Re-verify this call is still the live one - a stale timer must
        // never hang up whatever call happens to be active by the time it
        // fires (that call could belong to a later contact by now).
        if (callId !== currentCallIdR.current || settledCallIdR.current === callId) {
          console.log(`[PowerDialer] Safety net for ${callId} is stale - ignoring`);
          return;
        }
        console.warn(`[PowerDialer] callState never confirmed disconnect for ${callId} - forcing advance`);
        hangUp();
        settle(callId, status);
      }, SAFETY_NET_MS);
    }
  };

  const skip = () => {
    if (!activeR.current || !currentCallIdR.current) return;
    const callId = currentCallIdR.current;
    hangUp();
    settle(callId, 'skipped');
  };

  const pause = () => { pausedR.current = true; setPaused(true); };

  const resume = () => {
    pausedR.current = false;
    setPaused(false);
    if (pendingAdvanceR.current) {
      const { index, phoneOverride } = pendingAdvanceR.current;
      pendingAdvanceR.current = null;
      dialAt(index, sessionTokenR.current, phoneOverride);
    }
  };

  const stop = () => {
    if (activeR.current && currentCallIdR.current) hangUp();
    endSession();
  };

  return {
    sessionActive, paused, contacts, currentIndex, history,
    start, skip, pause, resume, stop, onDeviceFreed, reportDisposition,
  };
}
