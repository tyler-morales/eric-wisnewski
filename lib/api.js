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
};

const DEFAULT_FROM_EMAIL = 'hello@ericwisnewski.com';

export function listLabel(list) {
  return LIST_LABELS[list] || '';
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
