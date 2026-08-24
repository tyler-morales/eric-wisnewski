/**
 * Newsletter subscribe API: POST signup, GET confirm / unsubscribe.
 * D1 binding: COMMENTS_DB. Resend via fetch (no SDK). Self-contained file.
 */

const VALID_LISTS = ['posts', 'gradys-tour'];
const LIST_LABELS = {
  posts: "Eric's blog",
  'gradys-tour': "Grady's Tour",
};
const MAX_EMAIL = 320;
const GENERIC_OK = 'Check your inbox to confirm your subscription.';

export { VALID_LISTS };

export function getValidLists() {
  return [...VALID_LISTS];
}

export function normalizeEmail(email) {
  if (typeof email !== 'string') return '';
  return email.trim().toLowerCase();
}

export function isValidEmail(email) {
  if (typeof email !== 'string' || !email) return false;
  if (email.length > MAX_EMAIL) return false;
  // Practical RFC5322-ish check; reject spaces and missing domain.
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export function normalizeLists(lists) {
  if (!Array.isArray(lists)) return [];
  const out = [];
  const seen = new Set();
  for (const raw of lists) {
    const list = typeof raw === 'string' ? raw.trim() : '';
    if (!VALID_LISTS.includes(list) || seen.has(list)) continue;
    seen.add(list);
    out.push(list);
  }
  return out;
}

export function listLabel(list) {
  return LIST_LABELS[list] || '';
}

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function redirect(path) {
  return Response.redirect(path, 302);
}

function randomToken() {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  return [...bytes].map((b) => b.toString(16).padStart(2, '0')).join('');
}

async function verifyTurnstile(token, secret) {
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

async function sendResendEmail(env, { to, subject, html, text, headers }) {
  const apiKey = env.RESEND_API_KEY;
  if (!apiKey) {
    throw new Error('RESEND_API_KEY not configured');
  }
  const from = env.NEWSLETTER_FROM || 'Eric Wisnewski <hello@ericwisnewski.com>';
  const payload = { from, to: [to], subject, html, text };
  if (headers && typeof headers === 'object') {
    payload.headers = headers;
  }
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

function originFromRequest(request) {
  const url = new URL(request.url);
  return `${url.protocol}//${url.host}`;
}

function confirmEmailBody(origin, token, lists) {
  const labels = lists.map(listLabel).filter(Boolean).join(' and ');
  const link = `${origin}/api/subscribe?confirm=${encodeURIComponent(token)}`;
  const text = `Confirm your subscription to ${labels} on Eric Wisnewski.\n\n${link}\n\nIf you did not request this, ignore this email.`;
  const html = `<p>Confirm your subscription to <strong>${labels}</strong> on Eric Wisnewski.</p>
<p><a href="${link}">Confirm subscription</a></p>
<p>If you did not request this, ignore this email.</p>`;
  return { subject: `Confirm your subscription — ${labels}`, html, text };
}

export async function onRequestPost(context) {
  const db = context.env.COMMENTS_DB;
  if (!db) return jsonResponse({ error: 'Newsletter not configured' }, 503);

  let body;
  try {
    body = await context.request.json();
  } catch {
    return jsonResponse({ error: 'Invalid JSON body' }, 400);
  }

  const email = normalizeEmail(body.email != null ? String(body.email) : '');
  const lists = normalizeLists(body.lists);
  const turnstileToken =
    body.cf_turnstile_response != null
      ? String(body.cf_turnstile_response).trim()
      : body['cf-turnstile-response'] != null
        ? String(body['cf-turnstile-response']).trim()
        : '';

  if (!isValidEmail(email)) {
    return jsonResponse({ error: 'Valid email is required' }, 400);
  }
  if (!lists.length) {
    return jsonResponse({ error: 'Select at least one list' }, 400);
  }

  const ok = await verifyTurnstile(turnstileToken, context.env.TURNSTILE_SECRET_KEY);
  if (!ok) {
    return jsonResponse({ error: 'Verification failed' }, 400);
  }

  const confirmToken = randomToken();
  const origin = originFromRequest(context.request);
  const listsNeedingConfirm = [];

  try {
    for (const list of lists) {
      const existing = await db
        .prepare('SELECT id, status, confirm_token, unsub_token FROM subscribers WHERE email = ? AND list = ?')
        .bind(email, list)
        .first();

      if (existing && existing.status === 'confirmed') {
        continue;
      }

      const unsubToken = existing?.unsub_token || randomToken();

      if (existing) {
        await db
          .prepare(
            `UPDATE subscribers
             SET status = 'pending', confirm_token = ?, unsub_token = ?, confirmed_at = NULL, unsubscribed_at = NULL
             WHERE id = ?`
          )
          .bind(confirmToken, unsubToken, existing.id)
          .run();
      } else {
        await db
          .prepare(
            `INSERT INTO subscribers (email, list, status, confirm_token, unsub_token)
             VALUES (?, ?, 'pending', ?, ?)`
          )
          .bind(email, list, confirmToken, unsubToken)
          .run();
      }
      listsNeedingConfirm.push(list);
    }

    if (listsNeedingConfirm.length && context.env.RESEND_API_KEY) {
      const mail = confirmEmailBody(origin, confirmToken, listsNeedingConfirm);
      await sendResendEmail(context.env, {
        to: email,
        subject: mail.subject,
        html: mail.html,
        text: mail.text,
      });
    }

    return jsonResponse({ ok: true, message: GENERIC_OK });
  } catch (e) {
    console.error('subscribe POST', e);
    return jsonResponse({ error: 'Failed to subscribe' }, 500);
  }
}

export async function onRequestGet(context) {
  const db = context.env.COMMENTS_DB;
  if (!db) return jsonResponse({ error: 'Newsletter not configured' }, 503);

  const { searchParams } = new URL(context.request.url);
  const confirm = searchParams.get('confirm');
  const unsubscribe = searchParams.get('unsubscribe');
  const origin = originFromRequest(context.request);

  if (confirm) {
    const token = String(confirm).trim();
    if (!token) {
      return redirect(`${origin}/subscribe/confirmed/`);
    }
    try {
      await db
        .prepare(
          `UPDATE subscribers
           SET status = 'confirmed', confirmed_at = datetime('now')
           WHERE confirm_token = ? AND status = 'pending'`
        )
        .bind(token)
        .run();
    } catch (e) {
      console.error('subscribe confirm', e);
    }
    return redirect(`${origin}/subscribe/confirmed/`);
  }

  if (unsubscribe) {
    const token = String(unsubscribe).trim();
    if (!token) {
      return redirect(`${origin}/subscribe/unsubscribed/`);
    }
    try {
      await db
        .prepare(
          `UPDATE subscribers
           SET status = 'unsubscribed', unsubscribed_at = datetime('now')
           WHERE unsub_token = ? AND status != 'unsubscribed'`
        )
        .bind(token)
        .run();
    } catch (e) {
      console.error('subscribe unsubscribe', e);
    }
    return redirect(`${origin}/subscribe/unsubscribed/`);
  }

  return jsonResponse({ error: 'Missing confirm or unsubscribe parameter' }, 400);
}
