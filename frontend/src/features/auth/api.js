import { apiFetch } from '../../services/apiClient';

export async function getCurrentUser() {
  const res = await apiFetch('/auth/me');
  if (!res.ok) return null;
  return res.json();
}

export async function login(email, password) {
  const res = await apiFetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Invalid email or password');
  }
  return res.json();
}
