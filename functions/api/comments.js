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

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function onRequestGet(context) {
  const db = context.env.COMMENTS_DB;
  if (!db) return jsonResponse({ error: 'Comments not configured' }, 503);

  const url = new URL(context.request.url).searchParams.get('url');
  // #region agent log
  fetch('http://127.0.0.1:7686/ingest/1f2a7c1a-b240-4716-9fcc-d7c56788a7e8', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '313ca2' },
    body: JSON.stringify({
      sessionId: '313ca2',
      location: 'functions/api/comments.js:onRequestGet',
      message: 'GET comments entry',
      data: { urlParam: url != null ? url.substring(0, 80) : null, hasDb: true },
      timestamp: Date.now(),
      hypothesisId: 'H3'
    })
  }).catch(() => {});
  // #endregion
  if (!isValidUrlParam(url)) {
    return jsonResponse({ error: 'Missing or invalid url parameter' }, 400);
  }

  try {
    const stmt = db.prepare(
      'SELECT id, url, author, body, created_at, parent_id FROM comments WHERE url = ? ORDER BY created_at ASC'
    );
    const { results } = await stmt.bind(url.trim()).all();
    return jsonResponse(results);
  } catch (e) {
    const msg = e?.message != null ? String(e.message) : '';
    const missingColumn = /no such column|parent_id/i.test(msg);
    if (missingColumn) {
      try {
        const stmtLegacy = db.prepare(
          'SELECT id, url, author, body, created_at FROM comments WHERE url = ? ORDER BY created_at ASC'
        );
        const { results: legacyResults } = await stmtLegacy.bind(url.trim()).all();
        const withParentId = (legacyResults || []).map((row) => ({ ...row, parent_id: null }));
        // #region agent log
        fetch('http://127.0.0.1:7686/ingest/1f2a7c1a-b240-4716-9fcc-d7c56788a7e8', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '313ca2' },
          body: JSON.stringify({
            sessionId: '313ca2',
            location: 'functions/api/comments.js:onRequestGet:legacy',
            message: 'GET comments used legacy query (no parent_id)',
            data: { rowCount: withParentId.length },
            timestamp: Date.now(),
            runId: 'post-fix'
          })
        }).catch(() => {});
        // #endregion
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

  const url = body.url != null ? String(body.url).trim() : '';
  const author = body.author != null ? String(body.author).trim() : '';
  const text = body.text != null ? String(body.text).trim() : '';
  const email = body.email != null ? String(body.email).trim() : null;
  const parentId = body.parent_id != null ? Number(body.parent_id) : null;

  if (!isValidUrlParam(url)) {
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
    const parent = await db
      .prepare('SELECT id, parent_id FROM comments WHERE id = ? AND url = ?')
      .bind(parentId, url)
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

  if (!Number.isInteger(id) || id < 1) {
    return jsonResponse({ error: 'Invalid or missing id' }, 400);
  }
  if (!editToken) return jsonResponse({ error: 'edit_token is required' }, 400);
  if (!text) return jsonResponse({ error: 'Comment text is required' }, 400);
  if (text.length > MAX_TEXT) {
    return jsonResponse({ error: `Comment must be at most ${MAX_TEXT} characters` }, 400);
  }

  const row = await db
    .prepare('SELECT id, edit_token FROM comments WHERE id = ?')
    .bind(id)
    .first();
  if (!row) return jsonResponse({ error: 'Comment not found' }, 404);
  if (row.edit_token !== editToken) {
    return jsonResponse({ error: 'Not authorized to edit this comment' }, 403);
  }

  try {
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
  const editToken = searchParams.get('edit_token') || '';

  if (!Number.isInteger(id) || id < 1) {
    return jsonResponse({ error: 'Invalid or missing id' }, 400);
  }
  if (!editToken) return jsonResponse({ error: 'edit_token is required' }, 400);

  const row = await db
    .prepare('SELECT id, edit_token, parent_id FROM comments WHERE id = ?')
    .bind(id)
    .first();
  if (!row) return jsonResponse({ error: 'Comment not found' }, 404);
  if (row.edit_token !== editToken) {
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
