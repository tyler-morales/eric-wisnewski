/**
 * Blog comments API: GET list by url, POST new comment, PUT edit, DELETE comment.
 * D1 binding: COMMENTS_DB.
 *
 * The URL helpers stay here because they are only used by this route; shared
 * helpers come from lib/, outside the functions/ router.
 */

import { jsonResponse, publicOrigin, sendResendEmail, verifyTurnstile } from '../../lib/api.js';

const MAX_AUTHOR = 200;
const MAX_TEXT = 5000;

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

/** Address to notify when someone replies; empty means skip. */
export function parentReplyNotifyTo(parentEmail, replyEmail) {
  const to = typeof parentEmail === 'string' ? parentEmail.trim() : '';
  if (!to || to.length > 320 || /[\r\n]/.test(to)) return '';
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(to)) return '';
  const from = typeof replyEmail === 'string' ? replyEmail.trim() : '';
  if (from && to.toLowerCase() === from.toLowerCase()) return '';
  return to;
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

function isAdmin(secret, env) {
  const configured = env.COMMENTS_ADMIN_SECRET;
  return typeof configured === 'string' && configured.length > 0 && secret === configured;
}

export async function onRequestGet(context) {
  const db = context.env.COMMENTS_DB;
  if (!db) return jsonResponse({ error: 'Comments not configured' }, 503);

  const { searchParams } = new URL(context.request.url);
  const url = searchParams.get('url');
  const adminSecret = searchParams.get('admin_secret') ?? '';

  if (adminSecret && isAdmin(adminSecret, context.env)) {
    try {
      const stmt = db.prepare(
        `SELECT id, url, author, email, body, created_at, parent_id, edit_token, status FROM comments
         ORDER BY created_at DESC`
      );
      const { results } = await stmt.all();
      return jsonResponse(results ?? []);
    } catch (e) {
      const msg = e?.message != null ? String(e.message) : '';
      if (/no such column: status/i.test(msg)) {
        const stmt = db.prepare(
          'SELECT id, url, author, email, body, created_at, parent_id, edit_token FROM comments ORDER BY created_at DESC'
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
  const email = body.email != null ? String(body.email).trim() : null;
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
    parentRow = await db
      .prepare(
        `SELECT id, author, email FROM comments WHERE id = ? AND url IN (${urlInPlaceholders(variants)})`
      )
      .bind(parentId, ...variants)
      .first();
    if (!parentRow) {
      return jsonResponse({ error: 'Parent comment not found' }, 400);
    }
  }

  const editToken = crypto.randomUUID();

  try {
    let meta;
    try {
      const stmt = db.prepare(
        'INSERT INTO comments (url, author, email, body, parent_id, edit_token, status) VALUES (?, ?, ?, ?, ?, ?, ?)'
      );
      const result = await stmt
        .bind(url, author, email || null, text, parentId, editToken, 'approved')
        .run();
      meta = result.meta;
    } catch (insertErr) {
      const msg = insertErr?.message != null ? String(insertErr.message) : '';
      if (/no such column: status/i.test(msg)) {
        const stmt = db.prepare(
          'INSERT INTO comments (url, author, email, body, parent_id, edit_token) VALUES (?, ?, ?, ?, ?, ?)'
        );
        const result = await stmt
          .bind(url, author, email || null, text, parentId, editToken)
          .run();
        meta = result.meta;
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
    const notifyTo = parentReplyNotifyTo(parentRow && parentRow.email, email);
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

  const { searchParams } = new URL(context.request.url);
  const id = body.id != null ? Number(body.id) : null;
  const text = body.text != null ? String(body.text).trim() : '';
  const editToken = body.edit_token != null ? String(body.edit_token).trim() : '';
  const adminSecret = body.admin_secret != null ? String(body.admin_secret).trim() : (searchParams.get('admin_secret') ?? '');
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
    .prepare('SELECT id, edit_token, email FROM comments WHERE id = ?')
    .bind(id)
    .first();
  if (!row) return jsonResponse({ error: 'Comment not found' }, 404);
  if (!asAdmin && row.edit_token !== editToken) {
    return jsonResponse({ error: 'Not authorized to edit this comment' }, 403);
  }

  try {
    if (author !== null) {
      if (row.email) {
        await db.prepare('UPDATE comments SET author = ? WHERE email = ?').bind(author, row.email).run();
      } else {
        await db.prepare('UPDATE comments SET author = ? WHERE id = ?').bind(author, id).run();
      }
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

  const { searchParams } = new URL(context.request.url);
  const id = searchParams.get('id') != null ? Number(searchParams.get('id')) : null;
  const editToken = searchParams.get('edit_token') ?? '';
  const adminSecret = searchParams.get('admin_secret') ?? '';
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
