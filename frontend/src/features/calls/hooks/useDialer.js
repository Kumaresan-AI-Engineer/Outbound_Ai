// Shared "place one call" sequence - used by both the manual per-contact Call
// button (ContactTable) and the power-dial queue (usePowerDialer), so the
// initiate+connect logic only exists in one place.
import { initiateCall } from '../api';

export function useDialer(makeCall) {
  const placeCall = async (contact) => {
    const data = await initiateCall(contact);
    const call = await makeCall({ To: contact.phone, callId: data.call_id });
    if (!call) {
      throw new Error(`Device could not connect the call for ${contact.name}`);
    }
    return { contact, callId: data.call_id };
  };

  return { placeCall };
}
