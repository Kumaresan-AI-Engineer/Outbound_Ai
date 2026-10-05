import { apiFetch } from '../../services/apiClient';

export async function getUsers() {
  const res = await apiFetch('/users/');
  return res.json();
}

export async function createUser(payload) {
  const res = await apiFetch('/users/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  return { ok: res.ok, data };
}

export async function updateUser(id, payload) {
  const res = await apiFetch(`/users/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  return { ok: res.ok, data };
}

export async function deleteUser(id) {
  await apiFetch(`/users/${id}`, { method: 'DELETE' });
}

export async function getTwilioNumbers() {
  const res = await apiFetch('/twilio-numbers/');
  return res.json();
}

export async function createTwilioNumber(payload) {
  const res = await apiFetch('/twilio-numbers/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  return { ok: res.ok, data };
}

export async function assignTwilioNumber(numberId, userId, action) {
  await apiFetch(`/twilio-numbers/${numberId}/assign`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, action }),
  });
}

export async function updateTwilioNumber(id, payload) {
  await apiFetch(`/twilio-numbers/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function deleteTwilioNumber(id) {
  await apiFetch(`/twilio-numbers/${id}`, { method: 'DELETE' });
}
