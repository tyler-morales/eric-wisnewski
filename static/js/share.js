export function sharePayload(title, url) {
  var t = String(title || '').trim();
  var u = String(url || '').trim();
  return { title: t, text: t, url: u };
}

export function canUseNativeShare(nav, ua) {
  if (!nav || typeof nav.share !== 'function') return false;
  if (ua === undefined) return true;
  return /iPhone|iPad|iPod|Android/i.test(String(ua || ''));
}

export function shareOrFallback(nav, payload, fallback) {
  if (canUseNativeShare(nav)) {
    return Promise.resolve(nav.share(payload)).then(function () { }, function (err) {
      if (err && err.name === 'AbortError') return;
      if (typeof fallback === 'function') fallback();
    });
  }
  if (typeof fallback === 'function') fallback();
  return Promise.resolve();
}

export function copyLink(url, clipboard, doc) {
  var text = String(url || '');
  if (clipboard && typeof clipboard.writeText === 'function') {
    return clipboard.writeText(text).catch(function () {
      return copyWithExecCommand(text, doc);
    });
  }
  return copyWithExecCommand(text, doc);
}

function copyWithExecCommand(text, doc) {
  if (!doc || !doc.body || typeof doc.execCommand !== 'function') {
    return Promise.reject(new Error('clipboard unavailable'));
  }
  var input = doc.createElement('textarea');
  input.value = text;
  input.setAttribute('readonly', '');
  input.style.cssText = 'position:fixed;left:-9999px;top:0';
  doc.body.appendChild(input);
  input.select();
  var ok = false;
  try {
    ok = doc.execCommand('copy');
  } catch (_) { }
  doc.body.removeChild(input);
  return ok ? Promise.resolve() : Promise.reject(new Error('copy failed'));
}

function setOpen(root, open) {
  var toggle = root.querySelector('.post-share-toggle');
  var menu = root.querySelector('.post-share-menu');
  if (!toggle || !menu) return;
  toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  menu.hidden = !open;
}

function initShare() {
  if (typeof document === 'undefined') return;

  var roots = document.querySelectorAll('.post-share');
  if (!roots.length) return;

  function closeAll(except) {
    roots.forEach(function (root) {
      if (root !== except) setOpen(root, false);
    });
  }

  roots.forEach(function (root) {
    var toggle = root.querySelector('.post-share-toggle');
    var menu = root.querySelector('.post-share-menu');
    var copyBtn = root.querySelector('.post-share-copy');
    var statusEl = root.querySelector('.post-share-status');
    if (!toggle || !menu) return;

    var payload = sharePayload(root.dataset.shareTitle, root.dataset.shareUrl);
    var native = canUseNativeShare(navigator, navigator.userAgent);

    if (native) {
      toggle.removeAttribute('aria-expanded');
      toggle.removeAttribute('aria-controls');
    }

    function openMenu() {
      closeAll(root);
      setOpen(root, true);
    }

    toggle.addEventListener('click', function (event) {
      event.stopPropagation();
      if (native) {
        shareOrFallback(navigator, payload, openMenu);
        return;
      }
      if (toggle.getAttribute('aria-expanded') === 'true') {
        setOpen(root, false);
      } else {
        openMenu();
      }
    });

    if (copyBtn) {
      copyBtn.addEventListener('click', function () {
        copyLink(payload.url, navigator.clipboard, document).then(function () {
          if (statusEl) statusEl.textContent = 'Link copied';
          copyBtn.textContent = 'Copied';
          window.setTimeout(function () {
            copyBtn.textContent = 'Copy link';
            if (statusEl) statusEl.textContent = '';
          }, 2000);
        }).catch(function () {
          if (statusEl) statusEl.textContent = 'Could not copy the link';
        });
      });
    }
  });

  document.addEventListener('click', function (event) {
    var inside = event.target && event.target.closest && event.target.closest('.post-share');
    if (!inside) closeAll();
  });

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    var openToggle = document.querySelector('.post-share-toggle[aria-expanded="true"]');
    closeAll();
    if (openToggle) openToggle.focus();
  });
}

initShare();
