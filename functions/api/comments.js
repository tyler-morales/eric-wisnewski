/**
 * Blog comments API: GET list by url, POST new comment, PUT edit, DELETE comment.
 * D1 binding: COMMENTS_DB.
 *
 * The URL helpers stay here because they are only used by this route; shared
 * helpers come from lib/, outside the functions/ router.
 */

import {
  adminSecretFromRequest,
  confirmMailAllowed,
  isAdmin,
  isValidEmail,
  isValidToken,
  jsonResponse,
  normalizeEmail,
  publicOrigin,
  randomToken,
  sendResendEmail,
  verifyTurnstile,
} from '../../lib/api.js';

const MAX_AUTHOR = 200;
const MAX_TEXT = 5000;
const MAX_EMAIL = 320;

const LEGACY_TOUR_PREFIX = '/posts/gradys-tour/';
const LIVE_TOUR_PREFIX = '/gradys-tour/';
const EXACT_ALIASES = {
  '/posts/gradys-how-to-use-this-blog/': '/gradys-tour/how-to-use-this-blog/',
};

function isValidUrlParam(url) {
  if (typeof url !== 'string' || !url) return false;
  const t = url.trim();
  return t.startsWith('/') && !t.startsWith('//') && !t.includes('://');
}

function urlInPlaceholders(variants) {
  return variants.map(() => '?').join(', ');
}

/** Canonical form: trim, collapse slashes, trailing slash (except for "/"). */
export function canonicalCommentUrl(url) {
  if (typeof url !== 'string' || !url) return '';
  const t = url.trim().replace(/\/+/g, '/');
  if (!t.startsWith('/')) return '';
  if (t === '/') return '/';
  return t.endsWith('/') ? t : t + '/';
}

/** Map a stored or requested comment URL to the live post path. */
export function relocateCommentUrl(url) {
  const canonical = canonicalCommentUrl(url);
  if (!canonical) return '';
  if (EXACT_ALIASES[canonical]) return EXACT_ALIASES[canonical];
  if (canonical.startsWith(LEGACY_TOUR_PREFIX)) {
    return canonicalCommentUrl(LIVE_TOUR_PREFIX + canonical.slice(LEGACY_TOUR_PREFIX.length));
  }
  return canonical;
}

function withAndWithoutSlash(url) {
  if (!url) return [];
  if (url === '/') return ['/'];
  return url.endsWith('/') ? [url, url.slice(0, -1)] : [url + '/', url];
}

/**
 * All URL keys that should be treated as the same post when reading comments.
 */
export function commentUrlLookupVariants(url) {
  const canonical = canonicalCommentUrl(url);
  const live = relocateCommentUrl(canonical);
  const variants = new Set();

  for (const candidate of [canonical, live]) {
    for (const item of withAndWithoutSlash(candidate)) variants.add(item);
  }

  if (live.startsWith(LIVE_TOUR_PREFIX) && live !== LIVE_TOUR_PREFIX) {
    for (const item of withAndWithoutSlash(LEGACY_TOUR_PREFIX + live.slice(LIVE_TOUR_PREFIX.length))) {
      variants.add(item);
    }
  }

  for (const [legacy, dest] of Object.entries(EXACT_ALIASES)) {
    if (live === dest) {
      for (const item of withAndWithoutSlash(legacy)) variants.add(item);
    }
  }

  return [...variants];
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function escapeAttr(s) {
  return escapeHtml(s).replace(/'/g, '&#39;');
}

/** Address to notify when someone replies; empty means skip. confirmed must be true. */
export function parentReplyNotifyTo(parentEmail, replyEmail, confirmed) {
  if (!confirmed) return '';
  const to = typeof parentEmail === 'string' ? parentEmail.trim() : '';
  if (!to || to.length > MAX_EMAIL || /[\r\n]/.test(to)) return '';
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(to)) return '';
  const from = typeof replyEmail === 'string' ? replyEmail.trim() : '';
  if (from && to.toLowerCase() === from.toLowerCase()) return '';
  return to;
}

export function confirmCommentEmailBody(origin, token) {
  const link = `${origin}/api/comments?confirm=${encodeURIComponent(token)}`;
  const text = `Confirm this email to get a message when someone replies to your comment on Eric Wisnewski.\n\nWe won't send reply emails until you click this link:\n\n${link}\n\nIf you did not leave a comment, ignore this.`;
  const html = `<p>Confirm this email to get a message when someone replies to your comment on Eric Wisnewski.</p>
<p>We won't send reply emails until you click this link:</p>
<p><a href="${link}">Confirm email</a></p>
<p>If you did not leave a comment, ignore this.</p>`;
  return { subject: 'Confirm your comment email', html, text };
}

export function replyNotifyEmail({ parentAuthor, replyAuthor, replyText, postUrl }) {
  const who = (typeof replyAuthor === 'string' && replyAuthor.trim()) || 'Someone';
  const you = typeof parentAuthor === 'string' ? parentAuthor.trim() : '';
  const snippet = String(replyText || '').trim().slice(0, 280);
  const url = typeof postUrl === 'string' ? postUrl : '';
  const greeting = you ? `${you}, ` : '';
  const subject = `${who} replied to your comment`;
  const text = `${greeting}${who} replied to your comment:\n\n${snippet}\n\n${url}`;
  const html = `<p>${escapeHtml(greeting)}${escapeHtml(who)} replied to your comment:</p>
<blockquote>${escapeHtml(snippet).replace(/\n/g, '<br>')}</blockquote>
<p><a href="${escapeAttr(url)}">Read the comment</a></p>
<p style="color:#666;font-size:12px;">You got this because you left a comment with this email.</p>`;
  return { subject, html, text };
}

async function sendParentReplyEmail(env, to, mail) {
  if (!env || !env.RESEND_API_KEY || !to || !mail) return;
  try {
    await sendResendEmail(env, { to, subject: mail.subject, html: mail.html, text: mail.text });
  } catch (e) {
    console.error(e);
  }
}

export async function onRequestGet(context) {
  const db = context.env.COMMENTS_DB;
  if (!db) return jsonResponse({ error: 'Comments not configured' }, 503);

  const { searchParams } = new URL(context.request.url);
  const origin = publicOrigin(context.env, context.request);

  if (searchParams.has('confirm')) {
    const token = String(searchParams.get('confirm') || '').trim();
    if (!isValidToken(token)) {
      return Response.redirect(`${origin}/`, 302);
    }
    try {
      const found = await db
        .prepare('SELECT email, url FROM comments WHERE email_confirm_token = ?')
        .bind(token)
        .first();
      if (!found || !found.email) {
        return Response.redirect(`${origin}/`, 302);
      }
      await db
        .prepare(
          `UPDATE comments SET email_confirmed_at = datetime('now')
           WHERE lower(email) = lower(?) AND email_confirmed_at IS NULL`
        )
        .bind(found.email)
        .run();
      const path = relocateCommentUrl(found.url) || '/';
      return Response.redirect(`${origin}${path}#comments`, 302);
    } catch (e) {
      console.error('comment email confirm', e);
      return Response.redirect(`${origin}/`, 302);
    }
  }

  const url = searchParams.get('url');
  const adminSecret = adminSecretFromRequest(context.request);

  if (adminSecret && isAdmin(adminSecret, context.env)) {
    try {
      const stmt = db.prepare(
        `SELECT id, url, author, email, body, created_at, parent_id, status FROM comments
         ORDER BY created_at DESC`
      );
      const { results } = await stmt.all();
      return jsonResponse(results ?? []);
    } catch (e) {
      const msg = e?.message != null ? String(e.message) : '';
      if (/no such column: status/i.test(msg)) {
        const stmt = db.prepare(
          'SELECT id, url, author, email, body, created_at, parent_id FROM comments ORDER BY created_at DESC'
        );
        const { results } = await stmt.all();
        return jsonResponse((results ?? []).map((row) => ({ ...row, status: 'approved' })));
      }
      return jsonResponse({ error: 'Failed to load comments' }, 500);
    }
  }

  if (adminSecret) {
    const configuredSet =
      typeof context.env.COMMENTS_ADMIN_SECRET === 'string' && context.env.COMMENTS_ADMIN_SECRET.length > 0;
    return jsonResponse(
      { error: configuredSet ? 'Invalid admin secret.' : 'Admin secret not configured on server.' },
      401
    );
  }

  if (!isValidUrlParam(url)) {
    return jsonResponse({ error: 'Missing or invalid url parameter' }, 400);
  }

  const variants = commentUrlLookupVariants(url);
  if (!variants.length) {
    return jsonResponse({ error: 'Missing or invalid url parameter' }, 400);
  }
  const placeholders = urlInPlaceholders(variants);

  try {
    const stmt = db.prepare(
      `SELECT id, url, author, body, created_at, parent_id FROM comments
       WHERE url IN (${placeholders}) AND (status IS NULL OR status = 'approved') ORDER BY created_at ASC`
    );
    const { results } = await stmt.bind(...variants).all();
    return jsonResponse(results ?? []);
  } catch (e) {
    const msg = e?.message != null ? String(e.message) : '';
    const missingColumn = /no such column/i.test(msg);
    if (missingColumn) {
      try {
        const stmtLegacy = db.prepare(
          `SELECT id, url, author, body, created_at FROM comments WHERE url IN (${placeholders}) ORDER BY created_at ASC`
        );
        const { results: legacyResults } = await stmtLegacy.bind(...variants).all();
        const withParentId = (legacyResults || []).map((row) => ({ ...row, parent_id: null }));
        return jsonResponse(withParentId);
      } catch (e2) {
        return jsonResponse({ error: 'Failed to load comments' }, 500);
      }
    }
    return jsonResponse({ error: 'Failed to load comments' }, 500);
  }
}

export async function onRequestPost(context) {
  const db = context.env.COMMENTS_DB;
  if (!db) return jsonResponse({ error: 'Comments not configured' }, 503);

  let body;
  try {
    body = await context.request.json();
  } catch {
    return jsonResponse({ error: 'Invalid JSON body' }, 400);
  }

  const secret = context.env.TURNSTILE_SECRET_KEY;
  if (secret) {
    const token =
      body.cf_turnstile_response != null
        ? String(body.cf_turnstile_response).trim()
        : (body['cf-turnstile-response'] != null ? String(body['cf-turnstile-response']).trim() : '');
    if (!token) {
      return jsonResponse({ error: 'Verification required' }, 400);
    }
    if (!(await verifyTurnstile(token, secret))) {
      return jsonResponse({ error: 'Verification failed' }, 400);
    }
  }

  const rawUrl = body.url != null ? String(body.url).trim() : '';
  const url = relocateCommentUrl(rawUrl);
  const author = body.author != null ? String(body.author).trim() : '';
  const text = body.text != null ? String(body.text).trim() : '';
  const rawEmail = body.email != null ? String(body.email).trim() : '';
  let email = null;
  if (rawEmail) {
    email = normalizeEmail(rawEmail);
    if (!isValidEmail(email)) {
      return jsonResponse({ error: 'Invalid email' }, 400);
    }
  }
  const parentId = body.parent_id != null ? Number(body.parent_id) : null;

  if (!url || !isValidUrlParam(rawUrl)) {
    return jsonResponse({ error: 'Missing or invalid url' }, 400);
  }
  if (!author) return jsonResponse({ error: 'Author is required' }, 400);
  if (author.length > MAX_AUTHOR) {
    return jsonResponse({ error: `Author must be at most ${MAX_AUTHOR} characters` }, 400);
  }
  if (!text) return jsonResponse({ error: 'Comment text is required' }, 400);
  if (text.length > MAX_TEXT) {
    return jsonResponse({ error: `Comment must be at most ${MAX_TEXT} characters` }, 400);
  }

  let parentRow = null;
  if (parentId != null) {
    if (!Number.isInteger(parentId) || parentId < 1) {
      return jsonResponse({ error: 'Invalid parent_id' }, 400);
    }
    const variants = commentUrlLookupVariants(url);
    try {
      parentRow = await db
        .prepare(
          `SELECT id, author, email, email_confirmed_at FROM comments WHERE id = ? AND url IN (${urlInPlaceholders(variants)})`
        )
        .bind(parentId, ...variants)
        .first();
    } catch (e) {
      const msg = e?.message != null ? String(e.message) : '';
      if (/no such column: email_confirmed_at/i.test(msg)) {
        parentRow = await db
          .prepare(
            `SELECT id, author, email FROM comments WHERE id = ? AND url IN (${urlInPlaceholders(variants)})`
          )
          .bind(parentId, ...variants)
          .first();
      } else {
        throw e;
      }
    }
    if (!parentRow) {
      return jsonResponse({ error: 'Parent comment not found' }, 400);
    }
  }

  const editToken = crypto.randomUUID();
  let emailConfirmToken = null;
  let emailConfirmedAt = null;
  let sendConfirm = false;

  if (email) {
    try {
      const prior = await db
        .prepare(
          `SELECT email_confirmed_at FROM comments
           WHERE lower(email) = ? AND email_confirmed_at IS NOT NULL LIMIT 1`
        )
        .bind(email)
        .first();
      if (prior && prior.email_confirmed_at) {
        // ponytail: email-level confirm (like newsletter). A later comment with
        // this address skips a second click; replies still go only to this inbox.
        emailConfirmedAt = prior.email_confirmed_at;
      } else {
        emailConfirmToken = randomToken();
        const lastSent = await db
          .prepare(
            `SELECT created_at FROM comments
             WHERE lower(email) = ? AND email_confirm_token IS NOT NULL
             ORDER BY created_at DESC LIMIT 1`
          )
          .bind(email)
          .first();
        sendConfirm = confirmMailAllowed(lastSent && lastSent.created_at);
      }
    } catch (e) {
      const msg = e?.message != null ? String(e.message) : '';
      if (!/no such column/i.test(msg)) throw e;
    }
  }

  try {
    let meta;
    try {
      const stmt = db.prepare(
        `INSERT INTO comments
         (url, author, email, body, parent_id, edit_token, status, email_confirm_token, email_confirmed_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
      );
      const result = await stmt
        .bind(
          url,
          author,
          email || null,
          text,
          parentId,
          editToken,
          'approved',
          emailConfirmToken,
          emailConfirmedAt
        )
        .run();
      meta = result.meta;
    } catch (insertErr) {
      const msg = insertErr?.message != null ? String(insertErr.message) : '';
      if (/no such column: email_confirm_token/i.test(msg) || /no such column: status/i.test(msg)) {
        try {
          const stmt = db.prepare(
            'INSERT INTO comments (url, author, email, body, parent_id, edit_token, status) VALUES (?, ?, ?, ?, ?, ?, ?)'
          );
          const result = await stmt
            .bind(url, author, email || null, text, parentId, editToken, 'approved')
            .run();
          meta = result.meta;
        } catch (statusErr) {
          const statusMsg = statusErr?.message != null ? String(statusErr.message) : '';
          if (/no such column: status/i.test(statusMsg)) {
            const stmt = db.prepare(
              'INSERT INTO comments (url, author, email, body, parent_id, edit_token) VALUES (?, ?, ?, ?, ?, ?)'
            );
            const result = await stmt
              .bind(url, author, email || null, text, parentId, editToken)
              .run();
            meta = result.meta;
          } else {
            throw statusErr;
          }
        }
        sendConfirm = false;
      } else {
        throw insertErr;
      }
    }
    const lastId = meta?.last_row_id;
    if (lastId == null) {
      return jsonResponse({ error: 'Failed to save comment' }, 500);
    }
    const row = await db
      .prepare(
        'SELECT id, url, author, body, created_at, parent_id FROM comments WHERE id = ?'
      )
      .bind(lastId)
      .first();
    if (!row) {
      return jsonResponse({ error: 'Failed to save comment' }, 500);
    }
    const notifyTo = parentReplyNotifyTo(
      parentRow && parentRow.email,
      email,
      Boolean(parentRow && parentRow.email_confirmed_at)
    );
    if (notifyTo && context.env.RESEND_API_KEY) {
      const origin = publicOrigin(context.env, context.request);
      const mail = replyNotifyEmail({
        parentAuthor: parentRow.author,
        replyAuthor: author,
        replyText: text,
        postUrl: `${origin}${url}#comments`,
      });
      if (typeof context.waitUntil === 'function') {
        context.waitUntil(sendParentReplyEmail(context.env, notifyTo, mail));
      }
    }
    if (sendConfirm && emailConfirmToken && context.env.RESEND_API_KEY) {
      const origin = publicOrigin(context.env, context.request);
      const mail = confirmCommentEmailBody(origin, emailConfirmToken);
      if (typeof context.waitUntil === 'function') {
        context.waitUntil(sendParentReplyEmail(context.env, email, mail));
      } else {
        await sendParentReplyEmail(context.env, email, mail);
      }
    }
    return jsonResponse({ ...row, edit_token: editToken }, 201);
  } catch (e) {
    console.error(e);
    return jsonResponse({ error: 'Failed to save comment' }, 500);
  }
}

export async function onRequestPut(context) {
  const db = context.env.COMMENTS_DB;
  if (!db) return jsonResponse({ error: 'Comments not configured' }, 503);

  let body;
  try {
    body = await context.request.json();
  } catch {
    return jsonResponse({ error: 'Invalid JSON body' }, 400);
  }

  const id = body.id != null ? Number(body.id) : null;
  const text = body.text != null ? String(body.text).trim() : '';
  const editToken = body.edit_token != null ? String(body.edit_token).trim() : '';
  const adminSecret = adminSecretFromRequest(context.request, body);
  const author = body.author != null ? String(body.author).trim() : null;
  const asAdmin = adminSecret && isAdmin(adminSecret, context.env);

  if (!Number.isInteger(id) || id < 1) {
    return jsonResponse({ error: 'Invalid or missing id' }, 400);
  }
  if (!asAdmin && !editToken) {
    return jsonResponse({ error: 'edit_token or admin_secret is required' }, 400);
  }
  if (!text) return jsonResponse({ error: 'Comment text is required' }, 400);
  if (text.length > MAX_TEXT) {
    return jsonResponse({ error: `Comment must be at most ${MAX_TEXT} characters` }, 400);
  }
  if (author !== null) {
    if (!author) return jsonResponse({ error: 'Author cannot be empty' }, 400);
    if (author.length > MAX_AUTHOR) {
      return jsonResponse({ error: `Author must be at most ${MAX_AUTHOR} characters` }, 400);
    }
  }

  const row = await db
    .prepare('SELECT id, edit_token FROM comments WHERE id = ?')
    .bind(id)
    .first();
  if (!row) return jsonResponse({ error: 'Comment not found' }, 404);
  if (!asAdmin && row.edit_token !== editToken) {
    return jsonResponse({ error: 'Not authorized to edit this comment' }, 403);
  }

  try {
    if (author !== null) {
      await db.prepare('UPDATE comments SET author = ? WHERE id = ?').bind(author, id).run();
    }
    await db.prepare('UPDATE comments SET body = ? WHERE id = ?').bind(text, id).run();
    const updated = await db
      .prepare(
        'SELECT id, url, author, body, created_at, parent_id FROM comments WHERE id = ?'
      )
      .bind(id)
      .first();
    return jsonResponse(updated);
  } catch (e) {
    return jsonResponse({ error: 'Failed to update comment' }, 500);
  }
}

export async function onRequestDelete(context) {
  const db = context.env.COMMENTS_DB;
  if (!db) return jsonResponse({ error: 'Comments not configured' }, 503);

  let body = {};
  try {
    const raw = await context.request.text();
    if (raw) body = JSON.parse(raw);
  } catch {
    return jsonResponse({ error: 'Invalid JSON body' }, 400);
  }

  const id = body.id != null ? Number(body.id) : null;
  const editToken = body.edit_token != null ? String(body.edit_token).trim() : '';
  const adminSecret = adminSecretFromRequest(context.request, body);
  const asAdmin = adminSecret && isAdmin(adminSecret, context.env);

  if (!Number.isInteger(id) || id < 1) {
    return jsonResponse({ error: 'Invalid or missing id' }, 400);
  }
  if (!asAdmin && !editToken) {
    return jsonResponse({ error: 'edit_token or admin_secret is required' }, 400);
  }

  const row = await db
    .prepare('SELECT id, edit_token FROM comments WHERE id = ?')
    .bind(id)
    .first();
  if (!row) return jsonResponse({ error: 'Comment not found' }, 404);
  if (!asAdmin && row.edit_token !== editToken) {
    return jsonResponse({ error: 'Not authorized to delete this comment' }, 403);
  }

  try {
    await db
      .prepare(
        `WITH RECURSIVE tree(id) AS (
           SELECT id FROM comments WHERE id = ?
           UNION ALL
           SELECT c.id FROM comments c INNER JOIN tree t ON c.parent_id = t.id
         )
         DELETE FROM comments WHERE id IN (SELECT id FROM tree)`
      )
      .bind(id)
      .run();
    return new Response(null, { status: 204 });
  } catch (e) {
    return jsonResponse({ error: 'Failed to delete comment' }, 500);
  }
}
