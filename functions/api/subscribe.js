/**
 * Newsletter subscribe API: POST signup, GET confirm / unsubscribe.
 * D1 binding: COMMENTS_DB. Resend via fetch (no SDK).
 */

import {
  isAdmin,
  jsonResponse,
  listLabel,
  newsletterFromHeader,
  publicOrigin,
  sendResendEmail,
  verifyTurnstile,
} from '../../lib/api.js';

const VALID_LISTS = ['posts', 'gradys-tour', 'da-breakdown-w-tad'];
const MAX_EMAIL = 320;
const GENERIC_OK =
  "Check your inbox to confirm your subscription. If you don't see it, look in spam.";
const TOKEN_RE = /^[a-f0-9]{48}$/i;

export { VALID_LISTS, listLabel, newsletterFromHeader, publicOrigin };

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
  if (/[\r\n]/.test(email)) return false;
  // Practical RFC5322-ish check; reject spaces and missing domain.
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export function isValidToken(token) {
  return typeof token === 'string' && TOKEN_RE.test(token);
}

export function normalizeLists(lists) {
  if (typeof lists === 'string') lists = [lists];
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

export function joinListLabels(lists) {
  const labels = normalizeLists(lists).map(listLabel).filter(Boolean);
  if (!labels.length) return '';
  if (labels.length === 1) return labels[0];
  return `${labels.slice(0, -1).join(', ')} and ${labels[labels.length - 1]}`;
}

export function subscriptionStatusMessage(alreadyConfirmed, needingConfirm) {
  const confirmed = normalizeLists(alreadyConfirmed);
  const pending = normalizeLists(needingConfirm);
  if (!pending.length && confirmed.length) {
    return `You're already subscribed to ${joinListLabels(confirmed)}.`;
  }
  if (confirmed.length && pending.length) {
    return `You're already subscribed to ${joinListLabels(confirmed)}. Check your inbox to confirm ${joinListLabels(pending)}.`;
  }
  return GENERIC_OK;
}

export function preferenceUpdatePlan(currentRows, requestedLists) {
  const requested = new Set(normalizeLists(requestedLists));
  const byList = new Map();
  for (const row of Array.isArray(currentRows) ? currentRows : []) {
    if (row && VALID_LISTS.includes(row.list)) {
      byList.set(row.list, row.status);
    }
  }
  const subscribe = [];
  const unsubscribe = [];
  for (const list of VALID_LISTS) {
    const status = byList.get(list);
    const want = requested.has(list);
    if (want && status !== 'confirmed') {
      subscribe.push(list);
    } else if (!want && (status === 'confirmed' || status === 'pending')) {
      unsubscribe.push(list);
    }
  }
  return { subscribe, unsubscribe };
}

export function groupSubscribersByEmail(rows) {
  const byEmail = new Map();
  const listOrder = new Map(VALID_LISTS.map((id, i) => [id, i]));
  for (const row of Array.isArray(rows) ? rows : []) {
    if (!row || typeof row.email !== 'string' || !row.email) continue;
    let person = byEmail.get(row.email);
    if (!person) {
      person = { email: row.email, lists: [] };
      byEmail.set(row.email, person);
    }
    person.lists.push({
      list: row.list,
      label: listLabel(row.list) || String(row.list || ''),
      status: row.status,
      created_at: row.created_at || '',
      confirmed_at: row.confirmed_at || null,
    });
  }
  const people = [...byEmail.values()];
  people.sort((a, b) => a.email.localeCompare(b.email, undefined, { sensitivity: 'base' }));
  for (const person of people) {
    person.lists.sort(
      (a, b) => (listOrder.get(a.list) ?? 99) - (listOrder.get(b.list) ?? 99)
    );
  }
  return people;
}

export function preferencesPayload(email, rows) {
  const selected = [];
  const seen = new Set();
  for (const row of Array.isArray(rows) ? rows : []) {
    if (!row || !VALID_LISTS.includes(row.list) || seen.has(row.list)) continue;
    if (row.status === 'confirmed' || row.status === 'pending') {
      seen.add(row.list);
      selected.push(row.list);
    }
  }
  return {
    ok: true,
    email: typeof email === 'string' ? email : '',
    lists: selected,
  };
}

export function confirmOutcome(rows) {
  if (!Array.isArray(rows) || !rows.length) return 'invalid';
  let hasPending = false;
  let hasConfirmed = false;
  for (const row of rows) {
    if (!row) continue;
    if (row.status === 'pending') hasPending = true;
    if (row.status === 'confirmed') hasConfirmed = true;
  }
  if (hasPending) return 'confirm';
  if (hasConfirmed) return 'already';
  return 'invalid';
}

export function confirmRedirectPath(rows) {
  return confirmOutcome(rows) === 'invalid' ? '/subscribe/invalid/' : '/subscribe/confirmed/';
}

function managePageUrl(origin, token) {
  return `${origin}/subscribe/manage/?token=${encodeURIComponent(token)}`;
}

function redirect(path) {
  return Response.redirect(path, 302);
}

function randomToken() {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  return [...bytes].map((b) => b.toString(16).padStart(2, '0')).join('');
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

async function handleOneClickUnsubscribe(context, rawToken) {
  const db = context.env.COMMENTS_DB;
  if (!db) return jsonResponse({ error: 'Newsletter not configured' }, 503);
  const token = String(rawToken || '').trim();
  if (!isValidToken(token)) return jsonResponse({ ok: true });
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
    console.error('subscribe one-click unsubscribe', e);
    return jsonResponse({ error: 'Failed to unsubscribe' }, 500);
  }
  return jsonResponse({ ok: true });
}

async function savePreferences(context, body) {
  const db = context.env.COMMENTS_DB;
  if (!db) return jsonResponse({ error: 'Newsletter not configured' }, 503);
  const token = typeof body.token === 'string' ? body.token.trim() : '';
  if (!isValidToken(token)) return jsonResponse({ error: 'Invalid or expired link' }, 404);
  const lists = normalizeLists(body.lists);

  try {
    const owner = await db
      .prepare('SELECT email FROM subscribers WHERE unsub_token = ?')
      .bind(token)
      .first();
    if (!owner || !owner.email) {
      return jsonResponse({ error: 'Invalid or expired link' }, 404);
    }

    const existing = await db
      .prepare('SELECT id, list, status FROM subscribers WHERE email = ?')
      .bind(owner.email)
      .all();
    const currentRows = existing.results || [];
    const byList = new Map(currentRows.map((row) => [row.list, row]));
    const plan = preferenceUpdatePlan(currentRows, lists);

    for (const list of plan.subscribe) {
      const row = byList.get(list);
      if (row) {
        await db
          .prepare(
            `UPDATE subscribers
             SET status = 'confirmed', confirmed_at = datetime('now'), unsubscribed_at = NULL
             WHERE id = ?`
          )
          .bind(row.id)
          .run();
      } else {
        await db
          .prepare(
            `INSERT INTO subscribers (email, list, status, confirm_token, unsub_token, confirmed_at)
             VALUES (?, ?, 'confirmed', ?, ?, datetime('now'))`
          )
          .bind(owner.email, list, randomToken(), randomToken())
          .run();
      }
    }

    for (const list of plan.unsubscribe) {
      const row = byList.get(list);
      if (!row) continue;
      await db
        .prepare(
          `UPDATE subscribers
           SET status = 'unsubscribed', unsubscribed_at = datetime('now')
           WHERE id = ?`
        )
        .bind(row.id)
        .run();
    }

    const message = lists.length
      ? `Preferences saved. You'll get email for ${joinListLabels(lists)}.`
      : "You're unsubscribed from all emails.";
    return jsonResponse({ ok: true, message, lists });
  } catch (e) {
    console.error('subscribe preferences POST', e);
    return jsonResponse({ error: 'Failed to save preferences' }, 500);
  }
}

export async function onRequestPost(context) {
  const unsubscribeParam = new URL(context.request.url).searchParams.get('unsubscribe');
  if (unsubscribeParam) {
    return handleOneClickUnsubscribe(context, unsubscribeParam);
  }

  const db = context.env.COMMENTS_DB;
  if (!db) return jsonResponse({ error: 'Newsletter not configured' }, 503);

  let body;
  try {
    body = await context.request.json();
  } catch {
    return jsonResponse({ error: 'Invalid JSON body' }, 400);
  }

  const prefToken = typeof body.token === 'string' ? body.token.trim() : '';
  if (prefToken && (body.email == null || String(body.email).trim() === '')) {
    return savePreferences(context, body);
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
  const origin = publicOrigin(context.env, context.request);
  const alreadyConfirmed = [];
  const listsNeedingConfirm = [];

  try {
    for (const list of lists) {
      const existing = await db
        .prepare('SELECT id, status, confirm_token, unsub_token FROM subscribers WHERE email = ? AND list = ?')
        .bind(email, list)
        .first();

      if (existing && existing.status === 'confirmed') {
        alreadyConfirmed.push(list);
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

    if (listsNeedingConfirm.length) {
      if (!context.env.RESEND_API_KEY) {
        return jsonResponse({ error: 'Could not send confirmation email. Try again later.' }, 503);
      }
      const mail = confirmEmailBody(origin, confirmToken, listsNeedingConfirm);
      await sendResendEmail(context.env, {
        to: email,
        subject: mail.subject,
        html: mail.html,
        text: mail.text,
      });
    }

    return jsonResponse({
      ok: true,
      message: subscriptionStatusMessage(alreadyConfirmed, listsNeedingConfirm),
    });
  } catch (e) {
    console.error('subscribe POST', e);
    return jsonResponse({ error: 'Failed to subscribe' }, 500);
  }
}

export async function onRequestGet(context) {
  const db = context.env.COMMENTS_DB;
  if (!db) return jsonResponse({ error: 'Newsletter not configured' }, 503);

  const { searchParams } = new URL(context.request.url);
  const origin = publicOrigin(context.env, context.request);

  if (searchParams.has('confirm')) {
    const token = String(searchParams.get('confirm') || '').trim();
    if (!isValidToken(token)) {
      return redirect(`${origin}/subscribe/invalid/`);
    }
    try {
      const found = await db
        .prepare('SELECT status FROM subscribers WHERE confirm_token = ?')
        .bind(token)
        .all();
      const rows = found.results || [];
      if (confirmOutcome(rows) === 'confirm') {
        await db
          .prepare(
            `UPDATE subscribers
             SET status = 'confirmed', confirmed_at = datetime('now')
             WHERE confirm_token = ? AND status = 'pending'`
          )
          .bind(token)
          .run();
      }
      return redirect(`${origin}${confirmRedirectPath(rows)}`);
    } catch (e) {
      console.error('subscribe confirm', e);
      return redirect(`${origin}/subscribe/invalid/`);
    }
  }

  if (searchParams.has('unsubscribe')) {
    const token = String(searchParams.get('unsubscribe') || '').trim();
    if (!isValidToken(token)) {
      return redirect(`${origin}/subscribe/manage/`);
    }
    return redirect(managePageUrl(origin, token));
  }

  const adminSecret = String(searchParams.get('admin_secret') || '').trim();
  if (adminSecret) {
    if (!isAdmin(adminSecret, context.env)) {
      const configuredSet =
        typeof context.env.COMMENTS_ADMIN_SECRET === 'string' &&
        context.env.COMMENTS_ADMIN_SECRET.length > 0;
      return jsonResponse(
        { error: configuredSet ? 'Invalid admin secret.' : 'Admin secret not configured on server.' },
        401
      );
    }
    try {
      const found = await db
        .prepare(
          `SELECT email, list, status, created_at, confirmed_at, unsubscribed_at
           FROM subscribers
           ORDER BY email COLLATE NOCASE, list`
        )
        .all();
      return jsonResponse({
        ok: true,
        subscribers: groupSubscribersByEmail(found.results || []),
      });
    } catch (e) {
      console.error('subscribe admin list', e);
      return jsonResponse({ error: 'Failed to load subscribers' }, 500);
    }
  }

  if (searchParams.has('preferences')) {
    const token = String(searchParams.get('preferences') || '').trim();
    if (!isValidToken(token)) {
      return jsonResponse({ error: 'Invalid or expired link' }, 404);
    }
    try {
      const owner = await db
        .prepare('SELECT email FROM subscribers WHERE unsub_token = ?')
        .bind(token)
        .first();
      if (!owner || !owner.email) {
        return jsonResponse({ error: 'Invalid or expired link' }, 404);
      }
      const rows = await db
        .prepare('SELECT list, status FROM subscribers WHERE email = ?')
        .bind(owner.email)
        .all();
      return jsonResponse(preferencesPayload(owner.email, rows.results || []));
    } catch (e) {
      console.error('subscribe preferences GET', e);
      return jsonResponse({ error: 'Failed to load preferences' }, 500);
    }
  }

  return jsonResponse({ error: 'Missing confirm, unsubscribe, or preferences parameter' }, 400);
}
