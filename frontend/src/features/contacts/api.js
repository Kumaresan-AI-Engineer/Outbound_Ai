import { apiFetch } from '../../services/apiClient';

export async function getContacts() {
  const res = await apiFetch('/contacts/');
  return res.json();
}

export async function createContact(payload) {
  const res = await apiFetch('/contacts/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return res.ok;
}

export async function updateContact(id, payload) {
  const res = await apiFetch(`/contacts/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return res.ok;
}

export async function deleteContact(id) {
  await apiFetch(`/contacts/${id}`, { method: 'DELETE' });
}

export async function uploadClientsExcel(file, countryCode = '') {
  const body = new FormData();
  body.append('file', file);
  if (countryCode) body.append('country_code', countryCode);
  const res = await apiFetch('/clients/upload', { method: 'POST', body });
  const data = await res.json();
  return { ok: res.ok, data };
}
