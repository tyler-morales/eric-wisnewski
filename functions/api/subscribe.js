/**
 * Newsletter subscribe API: POST signup, GET confirm / unsubscribe.
 * D1 binding: COMMENTS_DB. Resend via fetch (no SDK).
 */

import {
  adminSecretFromRequest,
  confirmMailAllowed,
  isAdmin,
  isValidEmail,
  isValidToken,
  jsonResponse,
  listLabel,
  newsletterFromHeader,
  normalizeEmail,
  publicOrigin,
  randomToken,
  sendResendEmail,
  verifyTurnstile,
} from '../../lib/api.js';

const VALID_LISTS = ['posts', 'gradys-tour', 'da-breakdown-w-tad'];
const GENERIC_OK =
  "Check your inbox for a confirmation link. You won't get posts until you click it. If you don't see it, look in spam.";

export {
  VALID_LISTS,
  confirmMailAllowed,
  isValidEmail,
  isValidToken,
  listLabel,
  newsletterFromHeader,
  normalizeEmail,
  publicOrigin,
};

export function getValidLists() {
  return [...VALID_LISTS];
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

export function subscriptionStatusMessage(_alreadyConfirmed, _needingConfirm) {
  return GENERIC_OK;
}

export function signupNeedsConfirm(needingConfirm) {
  return normalizeLists(needingConfirm).length > 0;
}

export function signupAlreadySubscribed(alreadyConfirmed, needingConfirm) {
  return (
    normalizeLists(alreadyConfirmed).length > 0 &&
    normalizeLists(needingConfirm).length === 0
  );
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

export function confirmEmailBody(origin, token, lists) {
  const labels = lists.map(listLabel).filter(Boolean).join(' and ');
  const link = `${origin}/api/subscribe?confirm=${encodeURIComponent(token)}`;
  const text = `Confirm your subscription to ${labels} on Eric Wisnewski.\n\nYou won't get new-post emails until you click this link:\n\n${link}\n\nIf you did not request this, ignore this email.`;
  const html = `<p>Confirm your subscription to <strong>${labels}</strong> on Eric Wisnewski.</p>
<p>You won't get new-post emails until you click this link:</p>
<p><a href="${link}">Confirm subscription</a></p>
<p>If you did not request this, ignore this email.</p>`;
  return { subject: `Confirm your subscription — ${labels}`, html, text };
}

export function manageEmailBody(origin, token) {
  const link = managePageUrl(origin, token);
  const text = `Manage your subscriptions on Eric Wisnewski.\n\nUse this link to choose which lists you get, or unsubscribe:\n\n${link}\n\nIf you did not request this, ignore this email.`;
  const html = `<p>Manage your subscriptions on Eric Wisnewski.</p>
<p><a href="${link}">Manage subscriptions</a></p>
<p>If you did not request this, ignore this email.</p>`;
  return { subject: 'Manage your subscriptions — Eric Wisnewski', html, text };
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
      .prepare('SELECT id, list, status, unsub_token FROM subscribers WHERE email = ?')
      .bind(owner.email)
      .all();
    const currentRows = existing.results || [];
    const byList = new Map(currentRows.map((row) => [row.list, row]));
    const plan = preferenceUpdatePlan(currentRows, lists);
    const needingConfirm = [];
    const confirmToken = randomToken();

    for (const list of plan.subscribe) {
      const row = byList.get(list);
      if (row && row.status === 'pending') continue;
      const unsub = (row && row.unsub_token) || randomToken();
      if (row) {
        await db
          .prepare(
            `UPDATE subscribers
             SET status = 'pending', confirm_token = ?, unsub_token = ?,
                 confirmed_at = NULL, unsubscribed_at = NULL
             WHERE id = ?`
          )
          .bind(confirmToken, unsub, row.id)
          .run();
      } else {
        await db
          .prepare(
            `INSERT INTO subscribers (email, list, status, confirm_token, unsub_token)
             VALUES (?, ?, 'pending', ?, ?)`
          )
          .bind(owner.email, list, confirmToken, unsub)
          .run();
      }
      needingConfirm.push(list);
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

    if (needingConfirm.length && context.env.RESEND_API_KEY) {
      const lastSent = await db
        .prepare('SELECT MAX(confirm_sent_at) AS sent FROM subscribers WHERE email = ?')
        .bind(owner.email)
        .first();
      if (confirmMailAllowed(lastSent && lastSent.sent)) {
        const origin = publicOrigin(context.env, context.request);
        const mail = confirmEmailBody(origin, confirmToken, needingConfirm);
        await sendResendEmail(context.env, {
          to: owner.email,
          subject: mail.subject,
          html: mail.html,
          text: mail.text,
        });
        await db
          .prepare(
            `UPDATE subscribers SET confirm_sent_at = datetime('now')
             WHERE email = ? AND list IN (${needingConfirm.map(() => '?').join(', ')})`
          )
          .bind(owner.email, ...needingConfirm)
          .run();
      }
    }

    const message = needingConfirm.length
      ? `Check your inbox to confirm ${joinListLabels(needingConfirm)}. You won't get those emails until you click the link.`
      : lists.length
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
  let rotateAndSend = true;

  try {
    try {
      const lastSent = await db
        .prepare('SELECT MAX(confirm_sent_at) AS sent FROM subscribers WHERE email = ?')
        .bind(email)
        .first();
      rotateAndSend = confirmMailAllowed(lastSent && lastSent.sent);
    } catch {
      rotateAndSend = true;
    }

    for (const list of lists) {
      const existing = await db
        .prepare('SELECT id, status, confirm_token, unsub_token FROM subscribers WHERE email = ? AND list = ?')
        .bind(email, list)
        .first();

      if (existing && existing.status === 'confirmed') {
        alreadyConfirmed.push(list);
        continue;
      }

      if (existing && existing.status === 'pending' && !rotateAndSend) {
        listsNeedingConfirm.push(list);
        continue;
      }

      const unsubToken = existing?.unsub_token || randomToken();
      const rowToken = rotateAndSend ? confirmToken : existing?.confirm_token || confirmToken;

      if (existing) {
        await db
          .prepare(
            `UPDATE subscribers
             SET status = 'pending', confirm_token = ?, unsub_token = ?, confirmed_at = NULL, unsubscribed_at = NULL
             WHERE id = ?`
          )
          .bind(rowToken, unsubToken, existing.id)
          .run();
      } else {
        await db
          .prepare(
            `INSERT INTO subscribers (email, list, status, confirm_token, unsub_token)
             VALUES (?, ?, 'pending', ?, ?)`
          )
          .bind(email, list, rowToken, unsubToken)
          .run();
      }
      listsNeedingConfirm.push(list);
    }

    if (listsNeedingConfirm.length && rotateAndSend) {
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
      await db
        .prepare(
          `UPDATE subscribers SET confirm_sent_at = datetime('now')
           WHERE email = ? AND list IN (${listsNeedingConfirm.map(() => '?').join(', ')})`
        )
        .bind(email, ...listsNeedingConfirm)
        .run();
    } else if (
      signupAlreadySubscribed(alreadyConfirmed, listsNeedingConfirm) &&
      rotateAndSend &&
      context.env.RESEND_API_KEY
    ) {
      try {
        const row = await db
          .prepare(
            `SELECT unsub_token FROM subscribers
             WHERE email = ? AND status = 'confirmed'
             LIMIT 1`
          )
          .bind(email)
          .first();
        if (row && isValidToken(row.unsub_token)) {
          const mail = manageEmailBody(origin, row.unsub_token);
          await sendResendEmail(context.env, {
            to: email,
            subject: mail.subject,
            html: mail.html,
            text: mail.text,
          });
          await db
            .prepare(`UPDATE subscribers SET confirm_sent_at = datetime('now') WHERE email = ?`)
            .bind(email)
            .run();
        }
      } catch (e) {
        console.error('subscribe manage mail', e);
      }
    }

    return jsonResponse({
      ok: true,
      needsConfirm: signupNeedsConfirm(listsNeedingConfirm),
      alreadySubscribed: signupAlreadySubscribed(alreadyConfirmed, listsNeedingConfirm),
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

  const adminSecret = adminSecretFromRequest(context.request);
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

  return jsonResponse({ error: 'Missing confirm, unsubscribe, or preferences parameter' }, 400);
}
