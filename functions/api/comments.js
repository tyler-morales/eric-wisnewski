/**
 * Blog comments API: GET list by url, POST new comment, PUT edit, DELETE comment.
 * D1 binding: COMMENTS_DB.
 *
 * The URL helpers stay here because they are only used by this route; shared
 * helpers come from lib/, outside the functions/ router.
 */

import {
  adminSecretFromRequest,
  isAdmin,
  isValidEmail,
  isValidToken,
  isValidVisitorId,
  jsonResponse,
  normalizeEmail,
  publicOrigin,
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

/** SQLite datetime('now') is UTC with no zone; JS Date treats that as local. */
export function asIsoUtc(value) {
  if (value == null) return value;
  const s = String(value).trim();
  if (!s) return s;
  if (/Z$/i.test(s) || /[+-]\d{2}:\d{2}$/.test(s)) return s.replace(' ', 'T');
  return s.replace(' ', 'T') + 'Z';
}

export function withIsoCreatedAt(row) {
  if (!row || typeof row !== 'object') return row;
  return { ...row, created_at: asIsoUtc(row.created_at) };
}

export function withPublicLikeFields(row) {
  const src = row && typeof row === 'object' ? row : {};
  const likeCount = Number(src.like_count);
  return withIsoCreatedAt({
    ...src,
    like_count: Number.isFinite(likeCount) && likeCount > 0 ? Math.floor(likeCount) : 0,
    liked: Boolean(src.liked),
  });
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
  // ponytail: no inbox confirm. Anyone can put another address on a comment;
  // that inbox then gets reply notices. Upgrade: confirm click before notify.
  const to = typeof parentEmail === 'string' ? parentEmail.trim() : '';
  if (!to || to.length > MAX_EMAIL || /[\r\n]/.test(to)) return '';
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

/** Section id for a comment URL (`posts` / `gradys-tour` / `da-breakdown-w-tad` / `jers-prospect-profiles`); empty means skip. */
export function commentListId(url) {
  const live = relocateCommentUrl(url);
  if (live.startsWith('/gradys-tour/')) return 'gradys-tour';
  if (live.startsWith('/da-breakdown-w-tad/')) return 'da-breakdown-w-tad';
  if (live.startsWith('/jers-prospect-profiles/')) return 'jers-prospect-profiles';
  if (live.startsWith('/posts/')) return 'posts';
  return '';
}

/** Address to email the post's writer; empty means skip. */
export function writerNotifyTo(listId, env, commentEmail) {
  if (!listId || !env) return '';
  const key = `WRITER_EMAIL_${String(listId).replace(/-/g, '_').toUpperCase()}`;
  const to = typeof env[key] === 'string' ? env[key].trim() : '';
  if (!isValidEmail(to)) return '';
  const from = typeof commentEmail === 'string' ? commentEmail.trim() : '';
  if (from && to.toLowerCase() === from.toLowerCase()) return '';
  return to;
}

export function writerNotifyEmail({ commentAuthor, commentText, postUrl }) {
  const who = (typeof commentAuthor === 'string' && commentAuthor.trim()) || 'Someone';
  const snippet = String(commentText || '').trim().slice(0, 280);
  const url = typeof postUrl === 'string' ? postUrl : '';
  const subject = `${who} commented on your post`;
  const text = `${who} commented on your post:\n\n${snippet}\n\n${url}`;
  const html = `<p>${escapeHtml(who)} commented on your post:</p>
<blockquote>${escapeHtml(snippet).replace(/\n/g, '<br>')}</blockquote>
<p><a href="${escapeAttr(url)}">Read the comment</a></p>
<p style="color:#666;font-size:12px;">You got this because you wrote this post.</p>`;
  return { subject, html, text };
}

async function sendCommentNotice(env, to, mail) {
  // ponytail: From is always NEWSLETTER_FROM_EMAIL (Eric). Ceiling: Grady/Tad/Jer see Eric in From. Upgrade: newsletterFromHeader(env, sectionName).
  if (!env || !env.RESEND_API_KEY || !to || !mail) return;
  try {
    await sendResendEmail(env, { to, subject: mail.subject, html: mail.html, text: mail.text });
  } catch (e) {
    console.error(e);
  }
}

function queueCommentEmail(context, to, mail) {
  if (!context || !to || !mail) return Promise.resolve();
  const job = sendCommentNotice(context.env, to, mail);
  if (typeof context.waitUntil === 'function') {
    context.waitUntil(job);
    return Promise.resolve();
  }
  return job;
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
      return jsonResponse((results ?? []).map(withIsoCreatedAt));
    } catch (e) {
      const msg = e?.message != null ? String(e.message) : '';
      if (/no such column: status/i.test(msg)) {
        const stmt = db.prepare(
          'SELECT id, url, author, email, body, created_at, parent_id FROM comments ORDER BY created_at DESC'
        );
        const { results } = await stmt.all();
        return jsonResponse((results ?? []).map((row) => withIsoCreatedAt({ ...row, status: 'approved' })));
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
  const visitorId = isValidVisitorId(searchParams.get('visitor_id'))
    ? searchParams.get('visitor_id')
    : '';

  try {
    const likeSelect = visitorId
      ? `(SELECT COUNT(*) FROM comment_likes WHERE comment_id = comments.id) AS like_count,
         EXISTS(SELECT 1 FROM comment_likes WHERE comment_id = comments.id AND visitor_id = ?) AS liked`
      : `(SELECT COUNT(*) FROM comment_likes WHERE comment_id = comments.id) AS like_count,
         0 AS liked`;
    const stmt = db.prepare(
      `SELECT id, url, author, body, created_at, parent_id, ${likeSelect}
       FROM comments
       WHERE url IN (${placeholders}) AND (status IS NULL OR status = 'approved') ORDER BY created_at ASC`
    );
    const { results } = visitorId
      ? await stmt.bind(visitorId, ...variants).all()
      : await stmt.bind(...variants).all();
    return jsonResponse((results ?? []).map(withPublicLikeFields));
  } catch (e) {
    const msg = e?.message != null ? String(e.message) : '';
    const missingLikes = /no such table: comment_likes/i.test(msg);
    const missingColumn = /no such column/i.test(msg);
    if (missingLikes || missingColumn) {
      try {
        const stmtApproved = db.prepare(
          `SELECT id, url, author, body, created_at, parent_id FROM comments
           WHERE url IN (${placeholders}) AND (status IS NULL OR status = 'approved') ORDER BY created_at ASC`
        );
        const { results } = await stmtApproved.bind(...variants).all();
        return jsonResponse((results ?? []).map(withPublicLikeFields));
      } catch (approvedErr) {
        const approvedMsg = approvedErr?.message != null ? String(approvedErr.message) : '';
        if (!/no such column/i.test(approvedMsg)) {
          return jsonResponse({ error: 'Failed to load comments' }, 500);
        }
      }
      try {
        const stmtLegacy = db.prepare(
          `SELECT id, url, author, body, created_at FROM comments WHERE url IN (${placeholders}) ORDER BY created_at ASC`
        );
        const { results: legacyResults } = await stmtLegacy.bind(...variants).all();
        const withParentId = (legacyResults || []).map((row) =>
          withPublicLikeFields({ ...row, parent_id: null })
        );
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
          null,
          null
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
    const origin = publicOrigin(context.env, context.request);
    const postUrl = `${origin}${url}#comments`;
    const notifyTo = parentReplyNotifyTo(parentRow && parentRow.email, email);
    const writerTo = writerNotifyTo(commentListId(url), context.env, email);
    if (notifyTo) {
      await queueCommentEmail(
        context,
        notifyTo,
        replyNotifyEmail({
          parentAuthor: parentRow.author,
          replyAuthor: author,
          replyText: text,
          postUrl,
        })
      );
    }
    if (writerTo && writerTo.toLowerCase() !== (notifyTo || '').toLowerCase()) {
      await queueCommentEmail(
        context,
        writerTo,
        writerNotifyEmail({ commentAuthor: author, commentText: text, postUrl })
      );
    }
    return jsonResponse(withIsoCreatedAt({ ...row, edit_token: editToken }), 201);
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
    return jsonResponse(withIsoCreatedAt(updated));
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
    try {
      await db
        .prepare(
          `WITH RECURSIVE tree(id) AS (
             SELECT id FROM comments WHERE id = ?
             UNION ALL
             SELECT c.id FROM comments c INNER JOIN tree t ON c.parent_id = t.id
           )
           DELETE FROM comment_likes WHERE comment_id IN (SELECT id FROM tree)`
        )
        .bind(id)
        .run();
    } catch (likesErr) {
      const likesMsg = likesErr?.message != null ? String(likesErr.message) : '';
      if (!/no such table: comment_likes/i.test(likesMsg)) throw likesErr;
    }
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
