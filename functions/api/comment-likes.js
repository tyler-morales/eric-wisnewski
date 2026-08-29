/**
 * Toggle a like on a comment. Identity is a browser visitor_id, not an account.
 */

import { isValidVisitorId, jsonResponse } from '../../lib/api.js';

export function parseLikeToggleBody(body) {
  const commentId = body && body.comment_id != null ? Number(body.comment_id) : null;
  const visitorId = body && body.visitor_id != null ? String(body.visitor_id).trim() : '';
  if (!Number.isInteger(commentId) || commentId < 1) {
    return { error: 'Invalid or missing comment_id', status: 400 };
  }
  if (!isValidVisitorId(visitorId)) {
    return { error: 'Invalid or missing visitor_id', status: 400 };
  }
  return { commentId, visitorId };
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

  const parsed = parseLikeToggleBody(body);
  if (parsed.error) return jsonResponse({ error: parsed.error }, parsed.status);

  // ponytail: one like per (comment, browser visitor_id). Clearing site data or a
  // new UUID likes again. Upgrade: bind a confirmed email or a signed cookie.
  try {
    const comment = await db
      .prepare(
        `SELECT id FROM comments WHERE id = ? AND (status IS NULL OR status = 'approved')`
      )
      .bind(parsed.commentId)
      .first();
    if (!comment) return jsonResponse({ error: 'Comment not found' }, 404);

    const existing = await db
      .prepare('SELECT comment_id FROM comment_likes WHERE comment_id = ? AND visitor_id = ?')
      .bind(parsed.commentId, parsed.visitorId)
      .first();

    let liked;
    if (existing) {
      await db
        .prepare('DELETE FROM comment_likes WHERE comment_id = ? AND visitor_id = ?')
        .bind(parsed.commentId, parsed.visitorId)
        .run();
      liked = false;
    } else {
      try {
        await db
          .prepare('INSERT INTO comment_likes (comment_id, visitor_id) VALUES (?, ?)')
          .bind(parsed.commentId, parsed.visitorId)
          .run();
        liked = true;
      } catch (insertErr) {
        const insertMsg = insertErr?.message != null ? String(insertErr.message) : '';
        if (!/UNIQUE constraint failed/i.test(insertMsg)) throw insertErr;
        liked = true;
      }
    }

    const countRow = await db
      .prepare('SELECT COUNT(*) AS like_count FROM comment_likes WHERE comment_id = ?')
      .bind(parsed.commentId)
      .first();
    const likeCount = Number(countRow && countRow.like_count);
    return jsonResponse({
      liked,
      like_count: Number.isFinite(likeCount) && likeCount > 0 ? Math.floor(likeCount) : 0,
    });
  } catch (e) {
    const msg = e?.message != null ? String(e.message) : '';
    if (/no such table: comment_likes/i.test(msg)) {
      return jsonResponse({ error: 'Comment likes not configured' }, 503);
    }
    console.error(e);
    return jsonResponse({ error: 'Failed to like comment' }, 500);
  }
}
