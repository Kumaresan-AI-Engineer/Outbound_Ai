const TOKEN_KEY = 'outboundai_token';

// Base URL for the backend API. Defaults to same-origin (''), which uses the
// Vite dev proxy (see vite.config.js) or the production static serve. Only
// override with VITE_API_BASE_URL in frontend/.env if the backend genuinely
// isn't reachable through that proxy - pointing this at a stray/duplicate
// backend process (e.g. a leftover one on a different port) silently splits
// every REST call away from the one Twilio's webhooks actually reach.
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');

// Resolved once per page load - the IANA zone name (e.g. "Asia/Kolkata") the
// backend uses to convert stored UTC timestamps to this user's local time
// before sending them back (see app/core/timezone.py). Falls back to UTC
// server-side if this is ever missing or invalid.
const CLIENT_TIMEZONE = Intl.DateTimeFormat().resolvedOptions().timeZone;

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

// Drop-in replacement for the native fetch() used everywhere else in the
// app - attaches the JWT and forces a logout on 401 so every call site
// gets auth "for free" just by swapping the import.
export async function apiFetch(url, options = {}) {
  const token = getToken();
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (CLIENT_TIMEZONE) headers['X-Timezone'] = CLIENT_TIMEZONE;

  const res = await fetch(`${API_BASE_URL}${url}`, { ...options, headers });

  if (res.status === 401) {
    setToken(null);
    window.dispatchEvent(new Event('auth:unauthorized'));
  }

  return res;
}
