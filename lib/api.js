/**
 * Helpers shared by the Pages Functions in functions/api/.
 *
 * This file lives outside functions/ on purpose: every module inside that
 * directory is part of the file-based router, and an earlier attempt to share
 * code from functions/_lib/ failed the Cloudflare build. Importing across the
 * boundary is the documented pattern.
 * https://developers.cloudflare.com/pages/functions/module-support/
 */

export const LIST_LABELS = {
  posts: "Eric's blog",
  'gradys-tour': "Grady's Tour",
  'da-breakdown-w-tad': 'Da Breakdown w Tad',
  'jers-prospect-profiles': "Jer's Prospect Profiles",
};

const DEFAULT_FROM_EMAIL = 'hello@ericwisnewski.com';

export function listLabel(list) {
  return LIST_LABELS[list] || '';
}

export function secretsMatch(a, b) {
  if (Array.isArray(a)) {
    b = a[1];
    a = a[0];
  }
  if (typeof a !== 'string' || typeof b !== 'string' || !a.length || !b.length) {
    return false;
  }
  if (a.length !== b.length) return false;
  let mismatch = 0;
  for (let i = 0; i < a.length; i += 1) {
    mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return mismatch === 0;
}

export function isAdmin(secret, env) {
  return secretsMatch(env && env.COMMENTS_ADMIN_SECRET, secret);
}

/** Bearer header first; JSON body.admin_secret second. Never the query string. */
export function adminSecretFromHeader(authorization, body) {
  if (typeof authorization === 'string' && /^Bearer\s+/i.test(authorization)) {
    const token = authorization.replace(/^Bearer\s+/i, '').trim();
    if (token) return token;
  }
  if (body && typeof body.admin_secret === 'string') {
    return body.admin_secret.trim();
  }
  return '';
}

export function adminSecretFromRequest(request, body) {
  const header =
    request && request.headers && typeof request.headers.get === 'function'
      ? request.headers.get('authorization') || ''
      : '';
  return adminSecretFromHeader(header, body);
}

export const MAX_EMAIL = 320;
export const TOKEN_RE = /^[a-f0-9]{48}$/i;
export const VISITOR_ID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const CONFIRM_COOLDOWN_MS = 24 * 60 * 60 * 1000;

export function normalizeEmail(email) {
  if (typeof email !== 'string') return '';
  return email.trim().toLowerCase();
}

export function isValidEmail(email) {
  if (typeof email !== 'string' || !email) return false;
  if (email.length > MAX_EMAIL) return false;
  if (/[\r\n]/.test(email)) return false;
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export function isValidToken(token) {
  return typeof token === 'string' && TOKEN_RE.test(token);
}

export function isValidVisitorId(id) {
  return typeof id === 'string' && VISITOR_ID_RE.test(id);
}

export function randomToken() {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  return [...bytes].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export function confirmMailAllowed(sentAt, now = Date.now()) {
  if (sentAt == null || sentAt === '') return true;
  const raw = String(sentAt).trim();
  const iso = raw.includes('T') ? raw : raw.replace(' ', 'T');
  const t = Date.parse(/Z$/i.test(iso) || /[+-]\d{2}:\d{2}$/.test(iso) ? iso : `${iso}Z`);
  if (Number.isNaN(t)) return false;
  return now - t >= CONFIRM_COOLDOWN_MS;
}

export function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

/** Pinned NEWSLETTER_SITE_ORIGIN when set, else the origin of the request. */
export function publicOrigin(env, request) {
  const pinned =
    env && typeof env.NEWSLETTER_SITE_ORIGIN === 'string'
      ? env.NEWSLETTER_SITE_ORIGIN.trim().replace(/\/+$/, '')
      : '';
  if (pinned && /^https?:\/\//i.test(pinned)) return pinned;
  const url = typeof request === 'string' ? request : request && request.url;
  if (typeof url === 'string' && url) {
    const parsed = new URL(url);
    return `${parsed.protocol}//${parsed.host}`;
  }
  return '';
}

export function newsletterFromHeader(env, displayName) {
  const name =
    typeof displayName === 'string' && displayName.trim()
      ? displayName.trim()
      : 'Eric Wisnewski';
  const fromEmail =
    typeof env?.NEWSLETTER_FROM_EMAIL === 'string' && env.NEWSLETTER_FROM_EMAIL.trim()
      ? env.NEWSLETTER_FROM_EMAIL.trim()
      : DEFAULT_FROM_EMAIL;
  const from = typeof env?.NEWSLETTER_FROM === 'string' ? env.NEWSLETTER_FROM.trim() : '';
  if (from.includes('<')) return from;
  const email = from.includes('@') ? from : fromEmail;
  return `${name} <${email}>`;
}

/** True when no secret is configured (dev), so callers can skip verification. */
export async function verifyTurnstile(token, secret) {
  if (!secret) return true;
  if (!token) return false;
  try {
    const verifyRes = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ secret, response: token }),
    });
    const verifyData = await verifyRes.json();
    return Boolean(verifyData && verifyData.success === true);
  } catch {
    return false;
  }
}

export async function sendResendEmail(env, { from, to, subject, html, text, headers }) {
  const apiKey = env.RESEND_API_KEY;
  if (!apiKey) throw new Error('RESEND_API_KEY not configured');
  const payload = { from: from || newsletterFromHeader(env), to: [to], subject, html, text };
  if (headers && typeof headers === 'object') payload.headers = headers;
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errBody = await res.text();
    throw new Error(`Resend failed (${res.status}): ${errBody}`);
  }
  return res.json();
}
