import { apiFetch } from '../../services/apiClient';

export async function getCallToken() {
  const res = await apiFetch('/calls/token');
  return res.json();
}

export async function initiateCall(contact) {
  const res = await apiFetch('/calls/initiate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ contact_id: contact.id, phone: contact.phone }),
  });
  if (!res.ok) {
    throw new Error(`Could not start a call for ${contact.name}`);
  }
  return res.json();
}

export async function getLiveCallState(callId) {
  const res = await apiFetch(`/calls/live/${callId}`);
  if (!res.ok) return null;
  return res.json();
}
