/**
 * Newsletter dispatch: secret-gated RSS poll + per-list send via Resend.
 * D1 binding: COMMENTS_DB.
 */

import {
  LIST_LABELS,
  jsonResponse,
  newsletterFromHeader,
  publicOrigin,
  sendResendEmail,
} from '../../lib/api.js';

const LISTS = [
  { id: 'posts', feedPath: '/posts/index.xml', fromName: 'Eric Wisnewski' },
  { id: 'gradys-tour', feedPath: '/gradys-tour/index.xml', fromName: "Grady's Tour" },
];

export { newsletterFromHeader };

export function parseRssItems(xml) {
  if (typeof xml !== 'string' || !xml) return [];
  const items = [];
  const itemRe = /<item>([\s\S]*?)<\/item>/gi;
  let match;
  while ((match = itemRe.exec(xml)) !== null) {
    const block = match[1];
    const title = extractTag(block, 'title');
    const link = extractTag(block, 'link');
    let guid = extractTag(block, 'guid');
    if (!guid) guid = link;
    const description = extractTag(block, 'description');
    if (!guid || !link) continue;
    items.push({
      title: decodeXml(title || 'New post'),
      url: link.trim(),
      guid: guid.trim(),
      description: decodeXml(description || ''),
    });
  }
  return items;
}

/**
 * When seeding (list never sent), return [] so callers only record GUIDs.
 * Otherwise return items whose guid is not in knownGuids.
 */
export function selectNewItems(items, knownGuids, seedMode) {
  if (!Array.isArray(items)) return [];
  if (seedMode) return [];
  const known = new Set(Array.isArray(knownGuids) ? knownGuids : []);
  return items.filter((item) => item && item.guid && !known.has(item.guid));
}

function extractTag(block, tag) {
  const re = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`, 'i');
  const m = re.exec(block);
  if (!m) return '';
  return stripCdata(m[1].trim());
}

function stripCdata(s) {
  const m = /^<!\[CDATA\[([\s\S]*?)\]\]>$/i.exec(s);
  return m ? m[1] : s;
}

function decodeXml(s) {
  return String(s)
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

function isAuthorized(request, env) {
  const configured = env.NEWSLETTER_DISPATCH_SECRET;
  if (typeof configured !== 'string' || !configured) return false;
  const header = request.headers.get('authorization') || '';
  const bearer = header.startsWith('Bearer ') ? header.slice(7).trim() : '';
  const url = new URL(request.url);
  const querySecret = url.searchParams.get('secret') || '';
  return bearer === configured || querySecret === configured;
}

export function newsletterLinks(origin, unsubToken) {
  const token = encodeURIComponent(unsubToken || '');
  return {
    manageUrl: `${origin}/subscribe/manage/?token=${token}`,
    oneClickUrl: `${origin}/api/subscribe?unsubscribe=${token}`,
  };
}

function postEmailContent(listId, item, origin, unsubToken, postalAddress) {
  const label = LIST_LABELS[listId] || listId;
  const links = newsletterLinks(origin, unsubToken);
  const subject = `New on ${label}: ${item.title}`;
  const addressLine = postalAddress
    ? `<p style="color:#666;font-size:12px;">${escapeHtml(postalAddress)}</p>`
    : '';
  const html = `<p>There's a new post on <strong>${escapeHtml(label)}</strong>.</p>
<p><a href="${escapeAttr(item.url)}">${escapeHtml(item.title)}</a></p>
<p><a href="${escapeAttr(item.url)}">Read the post</a></p>
<hr>
<p style="color:#666;font-size:12px;"><a href="${escapeAttr(links.manageUrl)}">Unsubscribe or manage email preferences</a></p>
${addressLine}`;
  const text = `There's a new post on ${label}: ${item.title}\n\n${item.url}\n\nUnsubscribe or manage email preferences: ${links.manageUrl}${
    postalAddress ? `\n\n${postalAddress}` : ''
  }`;
  return { subject, html, text, unsubUrl: links.oneClickUrl };
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

async function processList(db, env, origin, listConfig) {
  const feedUrl = `${origin}${listConfig.feedPath}`;
  const feedRes = await fetch(feedUrl, {
    headers: { Accept: 'application/rss+xml, application/xml, text/xml' },
  });
  if (!feedRes.ok) {
    return { list: listConfig.id, error: `Feed fetch failed (${feedRes.status})`, sent: 0, seeded: 0 };
  }
  const xml = await feedRes.text();
  const items = parseRssItems(xml);

  const sentRows = await db
    .prepare('SELECT post_guid FROM newsletter_sends WHERE list = ?')
    .bind(listConfig.id)
    .all();
  const knownGuids = (sentRows.results || []).map((r) => r.post_guid);
  const seedMode = knownGuids.length === 0;

  if (seedMode) {
    let seeded = 0;
    for (const item of items) {
      await db
        .prepare(
          `INSERT OR IGNORE INTO newsletter_sends (list, post_guid, post_url, post_title)
           VALUES (?, ?, ?, ?)`
        )
        .bind(listConfig.id, item.guid, item.url, item.title)
        .run();
      seeded += 1;
    }
    return { list: listConfig.id, seeded, sent: 0, newItems: 0 };
  }

  const toSend = selectNewItems(items, knownGuids, false);
  let sent = 0;

  const subscribers = await db
    .prepare(
      `SELECT email, unsub_token FROM subscribers
       WHERE list = ? AND status = 'confirmed'`
    )
    .bind(listConfig.id)
    .all();
  const recipients = subscribers.results || [];
  const from = newsletterFromHeader(env, listConfig.fromName);
  const postal = env.NEWSLETTER_POSTAL_ADDRESS || '';

  for (const item of toSend) {
    for (const sub of recipients) {
      const mail = postEmailContent(listConfig.id, item, origin, sub.unsub_token, postal);
      await sendResendEmail(env, {
        from,
        to: sub.email,
        subject: mail.subject,
        html: mail.html,
        text: mail.text,
        headers: {
          'List-Unsubscribe': `<${mail.unsubUrl}>`,
          'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
        },
      });
      sent += 1;
    }
    await db
      .prepare(
        `INSERT OR IGNORE INTO newsletter_sends (list, post_guid, post_url, post_title)
         VALUES (?, ?, ?, ?)`
      )
      .bind(listConfig.id, item.guid, item.url, item.title)
      .run();
  }

  return {
    list: listConfig.id,
    seeded: 0,
    sent,
    newItems: toSend.length,
    recipients: recipients.length,
  };
}

export async function onRequestPost(context) {
  if (!isAuthorized(context.request, context.env)) {
    return jsonResponse({ error: 'Unauthorized' }, 401);
  }

  const db = context.env.COMMENTS_DB;
  if (!db) return jsonResponse({ error: 'Newsletter not configured' }, 503);
  if (!context.env.RESEND_API_KEY) {
    return jsonResponse({ error: 'RESEND_API_KEY not configured' }, 503);
  }

  const origin = publicOrigin(context.env, context.request);
  const results = [];

  try {
    for (const listConfig of LISTS) {
      results.push(await processList(db, context.env, origin, listConfig));
    }
    return jsonResponse({ ok: true, results });
  } catch (e) {
    console.error('newsletter dispatch', e);
    return jsonResponse({ error: 'Dispatch failed', detail: String(e?.message || e) }, 500);
  }
}

/** Allow GET with secret for simple curl/cron smoke tests. */
export async function onRequestGet(context) {
  return onRequestPost(context);
}
