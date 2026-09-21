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
  'jeremy-on-tap': 'Jeremy On Tap',
};

const DEFAULT_FROM_EMAIL = 'hello@ericwisnewski.com';
export const DEFAULT_POSTAL_ADDRESS = '1340 W 18th Pl, Chicago, IL 60608, USA';

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

export function newsletterPostalAddress(env) {
  const raw =
    env && typeof env.NEWSLETTER_POSTAL_ADDRESS === 'string'
      ? env.NEWSLETTER_POSTAL_ADDRESS.trim()
      : '';
  return raw || DEFAULT_POSTAL_ADDRESS;
}

export function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function escapeAttr(s) {
  return escapeHtml(s).replace(/'/g, '&#39;');
}

function formatEmailDate(date) {
  const d = date instanceof Date ? date : date != null && date !== '' ? new Date(date) : new Date();
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/**
 * Overreacted-style transactional HTML (tables + inline CSS, no images, no CTA buttons).
 * bodyHtml is already-escaped HTML from the caller; title/from/address are escaped here.
 */
export function brandedTransactionalEmail({
  markLabel = 'EW',
  markVariant = 'orange',
  fromName = 'Eric Wisnewski',
  toName = '',
  date,
  title = '',
  bodyHtml = '',
  bodyText = '',
  unsubUrl = '',
  unsubLabel = 'Unsubscribe',
  postalAddress,
  year,
  copyrightName = 'Eric Wisnewski',
} = {}) {
  const y = year || new Date().getFullYear();
  const address = String(postalAddress == null ? '' : postalAddress).trim() || DEFAULT_POSTAL_ADDRESS;
  const dateLabel = formatEmailDate(date);
  const to = typeof toName === 'string' ? toName.trim() : '';
  const markBg = markVariant === 'dark' ? '#111111' : '#ea580c';
  const markFg = markVariant === 'dark' ? '#ea580c' : '#ffffff';
  const toLine = to
    ? `<div style="font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:1.3;color:#2563eb;">To: ${escapeHtml(to)}</div>`
    : '';
  const unsub = typeof unsubUrl === 'string' ? unsubUrl.trim() : '';
  const unsubHtml = unsub
    ? `<div style="font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.4;color:#9ca3af;margin:0;">
<a href="${escapeAttr(unsub)}" style="color:#9ca3af;text-decoration:underline;">${escapeHtml(unsubLabel)}</a>
</div>`
    : '';
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="x-ua-compatible" content="ie=edge">
<title>${escapeHtml(title)}</title>
</head>
<body style="margin:0;padding:0;background-color:#ffffff;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#ffffff;">
<tr><td align="center" style="padding:0;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:560px;width:100%;">
<tr><td style="padding:28px 24px 8px 24px;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
<tr>
<td width="44" valign="middle" style="padding:0 12px 0 0;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" aria-hidden="true">
<tr>
<td width="40" height="40" align="center" valign="middle" style="width:40px;height:40px;background-color:${markBg};color:${markFg};border-radius:8px;font-family:Arial,Helvetica,sans-serif;font-size:13px;font-weight:700;letter-spacing:0.02em;">${escapeHtml(markLabel)}</td>
</tr>
</table>
</td>
<td valign="middle" style="padding:0;">
<div style="font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.3;font-weight:700;color:#111111;">${escapeHtml(fromName)}</div>
${toLine}
</td>
<td valign="top" align="right" style="padding:0 0 0 12px;font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:1.3;color:#6b7280;white-space:nowrap;">${escapeHtml(dateLabel)}</td>
</tr>
</table>
</td></tr>
<tr><td style="padding:20px 24px 8px 24px;">
<h1 style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:28px;line-height:1.2;font-weight:800;color:#111111;">${escapeHtml(title)}</h1>
</td></tr>
<tr><td style="padding:12px 24px 8px 24px;font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.55;color:#222222;">
${bodyHtml}
</td></tr>
<tr><td align="center" style="padding:28px 24px 32px 24px;">
<div style="font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.5;color:#9ca3af;">© ${y} ${escapeHtml(copyrightName)}</div>
<div style="font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.5;color:#9ca3af;">${escapeHtml(address)}</div>
${unsubHtml}
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>`;

  const textLines = [fromName];
  if (to) textLines.push(`To: ${to}`);
  if (dateLabel) textLines.push(dateLabel);
  textLines.push('', title, '', String(bodyText || '').trim());
  textLines.push('', `© ${y} ${copyrightName}`, address);
  if (unsub) textLines.push(`${unsubLabel}: ${unsub}`);
  return { html, text: textLines.join('\n') };
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
