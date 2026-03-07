/**
 * Blog comments API: GET list by url, POST new comment.
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
  if (!isValidUrlParam(url)) {
    return jsonResponse({ error: 'Missing or invalid url parameter' }, 400);
  }

  try {
    const stmt = db.prepare(
      'SELECT id, url, author, body, created_at FROM comments WHERE url = ? ORDER BY created_at ASC'
    );
    const { results } = await stmt.bind(url.trim()).all();
    return jsonResponse(results);
  } catch (e) {
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

  try {
    const stmt = db.prepare(
      'INSERT INTO comments (url, author, email, body) VALUES (?, ?, ?, ?)'
    );
    const { meta } = await stmt.bind(url, author, email || null, text).run();
    const row = await db
      .prepare(
        'SELECT id, url, author, body, created_at FROM comments WHERE id = ?'
      )
      .bind(meta.last_row_id)
      .first();
    return jsonResponse(row, 201);
  } catch (e) {
    return jsonResponse({ error: 'Failed to save comment' }, 500);
  }
}
