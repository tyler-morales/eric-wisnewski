/**
 * Photo ingest for /add-photos/: Google Photos picker + compressed uploads.
 * Commits files into assets/images/uploads/ through the GitHub Contents API.
 * Helpers are exported for tests.
 */

import { jsonResponse, secretsMatch } from '../../lib/api.js';

const MAX_BYTES = 8 * 1024 * 1024;
const UPLOAD_DIR = 'assets/images/uploads';
const GOOGLE_SCOPE = 'https://www.googleapis.com/auth/photospicker.mediaitems.readonly';
const PICKER_SESSIONS = 'https://photospicker.googleapis.com/v1/sessions';
const PICKER_ITEMS = 'https://photospicker.googleapis.com/v1/mediaItems';

export { secretsMatch };

export function sanitizeUploadFilename(name) {
  if (typeof name !== 'string' || !name) return '';
  if (name.includes('..') || name.includes('/') || name.includes('\\')) return '';
  const match = name.match(/^([A-Za-z0-9._-]{1,80})\.(jpe?g|png|webp)$/i);
  if (!match) return '';
  let ext = match[2].toLowerCase();
  if (ext === 'jpeg') ext = 'jpg';
  return `${match[1]}.${ext}`;
}

export function isAllowedImageBytes(bytes) {
  const arr = bytes instanceof Uint8Array ? bytes : Uint8Array.from(bytes || []);
  if (arr.length < 4) return false;
  if (arr[0] === 0xff && arr[1] === 0xd8 && arr[2] === 0xff) return true;
  if (arr[0] === 0x89 && arr[1] === 0x50 && arr[2] === 0x4e && arr[3] === 0x47) return true;
  return (
    arr.length >= 12 &&
    arr[0] === 0x52 &&
    arr[1] === 0x49 &&
    arr[2] === 0x46 &&
    arr[3] === 0x46 &&
    arr[8] === 0x57 &&
    arr[9] === 0x45 &&
    arr[10] === 0x42 &&
    arr[11] === 0x50
  );
}

export function isAllowedGoogleMediaUrl(url) {
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'https:') return false;
    const host = parsed.hostname;
    return host === 'photospicker.googleapis.com' || host.endsWith('.googleusercontent.com');
  } catch {
    return false;
  }
}

export function isAllowedRedirectUri(uri) {
  if (typeof uri !== 'string') return false;
  try {
    const parsed = new URL(uri);
    const pathOk = parsed.pathname === '/add-photos/' || parsed.pathname === '/add-photos';
    if (!pathOk) return false;
    if (parsed.hostname === 'ericwisnewski.com' || parsed.hostname === 'www.ericwisnewski.com') {
      return parsed.protocol === 'https:';
    }
    if (parsed.hostname === 'localhost' || parsed.hostname === '127.0.0.1') {
      return parsed.protocol === 'http:';
    }
    return parsed.hostname.endsWith('.pages.dev') && parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

function bytesFromBase64(b64) {
  if (typeof b64 !== 'string' || !b64) return new Uint8Array();
  const binary = atob(b64);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) out[i] = binary.charCodeAt(i);
  return out;
}

function bytesToBase64(bytes) {
  let binary = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

function googleClientId(env) {
  return env.GOOGLE_CLIENT_ID || '';
}

function googleClientSecret(env) {
  return env.GOOGLE_CLIENT_SECRET || '';
}

function uploadSecret(env) {
  return env.UPLOAD_SECRET || '';
}

function requireSecret(env, secret) {
  const configured = uploadSecret(env);
  if (typeof configured !== 'string' || !configured) {
    return { error: 'Upload is not configured on the server', status: 503 };
  }
  if (!secretsMatch(configured, secret)) {
    return { error: 'Wrong password', status: 401 };
  }
  return null;
}

function githubRepo(env) {
  return env.GITHUB_REPO || 'tyler-morales/eric-wisnewski';
}

function githubBranch(env) {
  return env.GITHUB_BRANCH || 'main';
}

function githubHeaders(env) {
  const token = env.GITHUB_TOKEN;
  if (!token) return null;
  return {
    Authorization: `Bearer ${token}`,
    Accept: 'application/vnd.github+json',
    'User-Agent': 'eric-wisnewski-add-photos',
    'X-GitHub-Api-Version': '2022-11-28',
  };
}

async function commitImage(env, filename, bytes) {
  const headers = githubHeaders(env);
  if (!headers) {
    return { error: 'GITHUB_TOKEN is not set', status: 503 };
  }
  const path = `${UPLOAD_DIR}/${filename}`;
  const apiBase = `https://api.github.com/repos/${githubRepo(env)}/contents/${path}`;
  const branch = githubBranch(env);
  const getRes = await fetch(`${apiBase}?ref=${encodeURIComponent(branch)}`, { headers });
  let sha;
  if (getRes.ok) {
    const existing = await getRes.json();
    sha = existing.sha;
  } else if (getRes.status !== 404) {
    return { error: 'Could not check GitHub for an existing file', status: 502 };
  }
  const putRes = await fetch(apiBase, {
    method: 'PUT',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: `Add photo ${filename} via /add-photos/`,
      content: bytesToBase64(bytes),
      branch,
      ...(sha ? { sha } : {}),
    }),
  });
  if (!putRes.ok) {
    return { error: 'GitHub did not accept the file', status: 502 };
  }
  return { path: `/images/uploads/${filename}` };
}

async function googleAuthUrl(env, redirectUri) {
  const clientId = googleClientId(env);
  if (!clientId) return { error: 'GOOGLE_CLIENT_ID is not set', status: 503 };
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: 'code',
    scope: GOOGLE_SCOPE,
    access_type: 'online',
    prompt: 'select_account',
  });
  return { url: `https://accounts.google.com/o/oauth2/v2/auth?${params}` };
}

async function exchangeGoogleCode(env, code, redirectUri) {
  const clientId = googleClientId(env);
  const clientSecret = googleClientSecret(env);
  if (!clientId || !clientSecret) {
    return { error: 'Google OAuth is not configured', status: 503 };
  }
  const res = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      code,
      client_id: clientId,
      client_secret: clientSecret,
      redirect_uri: redirectUri,
      grant_type: 'authorization_code',
    }),
  });
  if (!res.ok) return { error: 'Google sign-in failed', status: 401 };
  const data = await res.json();
  if (!data.access_token) return { error: 'Google did not return a token', status: 401 };
  return { accessToken: data.access_token };
}

async function googleJson(accessToken, url, init = {}) {
  const res = await fetch(url, {
    ...init,
    headers: {
      Authorization: `Bearer ${accessToken}`,
      ...(init.headers || {}),
    },
  });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

export async function onRequest(context) {
  if (context.request.method !== 'POST') {
    return jsonResponse({ error: 'POST only' }, 405);
  }
  let body;
  try {
    body = await context.request.json();
  } catch {
    return jsonResponse({ error: 'Invalid JSON' }, 400);
  }
  const action = body?.action;
  const denied = requireSecret(context.env, body?.secret);
  if (denied) return jsonResponse({ error: denied.error }, denied.status);

  if (action === 'unlock') {
    return jsonResponse({ ok: true });
  }

  if (action === 'google-auth-url') {
    if (!isAllowedRedirectUri(body.redirectUri)) {
      return jsonResponse({ error: 'Redirect URI is not allowed' }, 400);
    }
    const result = await googleAuthUrl(context.env, body.redirectUri);
    if (result.error) return jsonResponse({ error: result.error }, result.status);
    return jsonResponse(result);
  }

  if (action === 'google-token') {
    if (!isAllowedRedirectUri(body.redirectUri) || typeof body.code !== 'string') {
      return jsonResponse({ error: 'Missing Google auth code' }, 400);
    }
    const result = await exchangeGoogleCode(context.env, body.code, body.redirectUri);
    if (result.error) return jsonResponse({ error: result.error }, result.status);
    return jsonResponse(result);
  }

  const accessToken = body.accessToken;
  if (action === 'google-session-create') {
    if (typeof accessToken !== 'string' || !accessToken) {
      return jsonResponse({ error: 'Sign in with Google first' }, 401);
    }
    const result = await googleJson(accessToken, PICKER_SESSIONS, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    if (!result.ok) return jsonResponse({ error: 'Could not open Google Photos' }, 502);
    return jsonResponse({
      sessionId: result.data.id,
      pickerUri: result.data.pickerUri,
    });
  }

  if (action === 'google-session') {
    if (typeof accessToken !== 'string' || typeof body.sessionId !== 'string') {
      return jsonResponse({ error: 'Missing session' }, 400);
    }
    const result = await googleJson(
      accessToken,
      `${PICKER_SESSIONS}/${encodeURIComponent(body.sessionId)}`,
    );
    if (!result.ok) return jsonResponse({ error: 'Could not read picker session' }, 502);
    return jsonResponse({
      mediaItemsSet: Boolean(result.data.mediaItemsSet),
    });
  }

  if (action === 'google-items') {
    if (typeof accessToken !== 'string' || typeof body.sessionId !== 'string') {
      return jsonResponse({ error: 'Missing session' }, 400);
    }
    const result = await googleJson(
      accessToken,
      `${PICKER_ITEMS}?sessionId=${encodeURIComponent(body.sessionId)}&pageSize=50`,
    );
    if (!result.ok) return jsonResponse({ error: 'Could not list picked photos' }, 502);
    const items = (result.data.mediaItems || []).map((item) => ({
      id: item.id,
      filename: item.mediaFile?.filename || 'photo.jpg',
      mimeType: item.mediaFile?.mimeType || 'image/jpeg',
      baseUrl: item.mediaFile?.baseUrl || '',
    }));
    return jsonResponse({ items });
  }

  if (action === 'google-file') {
    if (typeof accessToken !== 'string' || typeof body.baseUrl !== 'string') {
      return jsonResponse({ error: 'Missing photo URL' }, 400);
    }
    if (!isAllowedGoogleMediaUrl(body.baseUrl)) {
      return jsonResponse({ error: 'Photo URL is not from Google' }, 400);
    }
    const downloadUrl = body.baseUrl.includes('=') ? `${body.baseUrl}-d` : `${body.baseUrl}=d`;
    const res = await fetch(downloadUrl, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!res.ok) return jsonResponse({ error: 'Could not download from Google Photos' }, 502);
    const buf = new Uint8Array(await res.arrayBuffer());
    if (buf.byteLength > MAX_BYTES) {
      return jsonResponse({ error: 'That Google photo is larger than 8 MB' }, 413);
    }
    if (!isAllowedImageBytes(buf)) {
      return jsonResponse({ error: 'Google did not return an image' }, 415);
    }
    return jsonResponse({ contentBase64: bytesToBase64(buf) });
  }

  if (action === 'upload') {
    const filename = sanitizeUploadFilename(body.filename);
    if (!filename) return jsonResponse({ error: 'Invalid filename' }, 400);
    const bytes = bytesFromBase64(body.contentBase64);
    if (!bytes.byteLength) return jsonResponse({ error: 'Empty file' }, 400);
    if (bytes.byteLength > MAX_BYTES) {
      return jsonResponse({ error: 'File is larger than 8 MB after compress' }, 413);
    }
    if (!isAllowedImageBytes(bytes)) {
      return jsonResponse({ error: 'Only JPEG, PNG, or WebP' }, 415);
    }
    const result = await commitImage(context.env, filename, bytes);
    if (result.error) return jsonResponse({ error: result.error }, result.status);
    return jsonResponse({ ok: true, path: result.path });
  }

  return jsonResponse({ error: 'Unknown action' }, 400);
}
