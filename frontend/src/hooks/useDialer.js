// Shared "place one call" sequence - used by both the manual per-contact Call
// button (ContactTable) and the power-dial queue (usePowerDialer), so the
// initiate+connect logic only exists in one place.
export function useDialer(makeCall) {
  const placeCall = async (contact) => {
    const res = await fetch('/calls/initiate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ contact_id: contact.id, phone: contact.phone }),
    });
    if (!res.ok) {
      throw new Error(`Could not start a call for ${contact.name}`);
    }
    const data = await res.json();
    const call = await makeCall({ To: contact.phone, callId: data.call_id });
    if (!call) {
      throw new Error(`Device could not connect the call for ${contact.name}`);
    }
    return { contact, callId: data.call_id };
  };

  return { placeCall };
}
