/**
 * Comment page keys. Tour posts moved from /posts/gradys-tour/<slug>/ to
 * /gradys-tour/<slug>/; keep both forms equivalent so existing D1 rows still show.
 */

const LEGACY_TOUR_PREFIX = '/posts/gradys-tour/';
const LIVE_TOUR_PREFIX = '/gradys-tour/';

const EXACT_ALIASES = {
  '/posts/gradys-how-to-use-this-blog/': '/gradys-tour/how-to-use-this-blog/',
};

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
