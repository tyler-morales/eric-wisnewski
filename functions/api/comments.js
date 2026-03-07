/**
 * Blog comments API: GET list by url, POST new comment, PUT edit, DELETE comment.
 * D1 binding: COMMENTS_DB.
 */

const MAX_AUTHOR = 200;
const MAX_TEXT = 5000;

function isValidUrlParam(url) {
  if (typeof url !== 'string' || !url) return false;
  const t = url.trim();
  return t.startsWith('/') && !t.startsWith('//') && !t.includes('://');
}

/** Canonical form: trim, ensure single leading slash, trailing slash (except for "/"). */
function canonicalCommentUrl(url) {
  if (typeof url !== 'string' || !url) return '';
  const t = url.trim().replace(/\/+/g, '/');
  if (!t.startsWith('/')) return '';
  if (t === '/') return '/';
  return t.endsWith('/') ? t : t + '/';
}

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
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
        'SELECT id, url, author, email, body, created_at, parent_id, edit_token FROM comments ORDER BY url ASC, created_at ASC'
      );
      const { results } = await stmt.all();
      return jsonResponse(results ?? []);
    } catch (e) {
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

  const canonical = canonicalCommentUrl(url);
  const alt = canonical === '/' ? '/' : canonical.slice(0, -1);

  try {
    const stmt = db.prepare(
      'SELECT id, url, author, body, created_at, parent_id FROM comments WHERE url = ? OR url = ? ORDER BY created_at ASC'
    );
    const { results } = await stmt.bind(canonical, alt).all();
    return jsonResponse(results ?? []);
  } catch (e) {
    const msg = e?.message != null ? String(e.message) : '';
    const missingColumn = /no such column|parent_id/i.test(msg);
    if (missingColumn) {
      try {
        const stmtLegacy = db.prepare(
          'SELECT id, url, author, body, created_at FROM comments WHERE url = ? OR url = ? ORDER BY created_at ASC'
        );
        const { results: legacyResults } = await stmtLegacy.bind(canonical, alt).all();
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
    try {
      const verifyRes = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ secret, response: token }),
      });
      const verifyData = await verifyRes.json();
      if (!verifyData || verifyData.success !== true) {
        return jsonResponse({ error: 'Verification failed' }, 400);
      }
    } catch (e) {
      return jsonResponse({ error: 'Verification failed' }, 400);
    }
  }

  const rawUrl = body.url != null ? String(body.url).trim() : '';
  const url = canonicalCommentUrl(rawUrl);
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

  if (parentId != null) {
    if (!Number.isInteger(parentId) || parentId < 1) {
      return jsonResponse({ error: 'Invalid parent_id' }, 400);
    }
    const altUrl = url === '/' ? '/' : url.slice(0, -1);
    const parent = await db
      .prepare('SELECT id, parent_id FROM comments WHERE id = ? AND (url = ? OR url = ?)')
      .bind(parentId, url, altUrl)
      .first();
    if (!parent) {
      return jsonResponse({ error: 'Parent comment not found' }, 400);
    }
    if (parent.parent_id != null) {
      return jsonResponse({ error: 'Replies can only be to top-level comments' }, 400);
    }
  }

  const editToken = crypto.randomUUID();

  try {
    const stmt = db.prepare(
      'INSERT INTO comments (url, author, email, body, parent_id, edit_token) VALUES (?, ?, ?, ?, ?, ?)'
    );
    const { meta } = await stmt
      .bind(url, author, email || null, text, parentId, editToken)
      .run();
    const row = await db
      .prepare(
        'SELECT id, url, author, body, created_at, parent_id FROM comments WHERE id = ?'
      )
      .bind(meta.last_row_id)
      .first();
    return jsonResponse({ ...row, edit_token: editToken }, 201);
  } catch (e) {
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
  const author = body.author != null ? String(body.author).trim() : null;

  if (!Number.isInteger(id) || id < 1) {
    return jsonResponse({ error: 'Invalid or missing id' }, 400);
  }
  if (!editToken) return jsonResponse({ error: 'edit_token is required' }, 400);
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
  if (row.edit_token !== editToken) {
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
    .prepare('SELECT id, edit_token, parent_id FROM comments WHERE id = ?')
    .bind(id)
    .first();
  if (!row) return jsonResponse({ error: 'Comment not found' }, 404);
  if (!asAdmin && row.edit_token !== editToken) {
    return jsonResponse({ error: 'Not authorized to delete this comment' }, 403);
  }

  try {
    if (row.parent_id == null) {
      await db.prepare('DELETE FROM comments WHERE id = ? OR parent_id = ?').bind(id, id).run();
    } else {
      await db.prepare('DELETE FROM comments WHERE id = ?').bind(id).run();
    }
    return new Response(null, { status: 204 });
  } catch (e) {
    return jsonResponse({ error: 'Failed to delete comment' }, 500);
  }
}
