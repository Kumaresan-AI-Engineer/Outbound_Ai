import { apiFetch } from '../../services/apiClient';

export async function getCallLogs() {
  const res = await apiFetch('/calls/logs');
  return res.json();
}

// Used by features/calls/components/PowerDialerSummary.jsx too - per-contact
// call-log data is owned here regardless of which feature calls it.
export async function getCallLogsForContact(contactId) {
  const res = await apiFetch(`/calls/logs/${contactId}`);
  if (!res.ok) return null;
  return res.json();
}
