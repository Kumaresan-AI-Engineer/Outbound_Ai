import { apiFetch } from '../../services/apiClient';

export async function getAnalytics() {
  const res = await apiFetch('/calls/analytics');
  return res.json();
}

export async function getTodayFollowUps() {
  const res = await apiFetch('/calls/follow-ups/today');
  return res.json();
}

export async function generateWeeklySummary() {
  const res = await apiFetch('/calls/weekly-summary', { method: 'POST' });
  return res.json();
}

export async function getFollowUps() {
  const res = await apiFetch('/calls/follow-ups');
  return res.json();
}

export async function completeFollowUp(callId) {
  await apiFetch(`/calls/follow-ups/${callId}/complete`, { method: 'POST' });
}
