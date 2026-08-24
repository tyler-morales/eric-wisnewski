(function () {
  var STORAGE_SECRET = 'add_photos_secret';
  var STORAGE_GOOGLE = 'add_photos_google_token';
  var MAX_EDGE = 2048;
  var JPEG_QUALITY = 0.82;
  var API = '/api/photos';

  var unlockForm = document.getElementById('add-photos-unlock');
  var secretInput = document.getElementById('add-photos-secret');
  var unlockError = document.getElementById('add-photos-unlock-error');
  var tools = document.getElementById('add-photos-tools');
  var googleBtn = document.getElementById('add-photos-google');
  var fileInput = document.getElementById('add-photos-files');
  var statusEl = document.getElementById('add-photos-status');
  var listEl = document.getElementById('add-photos-list');

  if (!unlockForm || !tools) return;

  function redirectUri() {
    return window.location.origin + '/add-photos/';
  }

  function getSecret() {
    return sessionStorage.getItem(STORAGE_SECRET) || '';
  }

  function setStatus(msg) {
    statusEl.textContent = msg || '';
  }

  function showError(msg) {
    unlockError.textContent = msg || '';
    unlockError.hidden = !msg;
  }

  function addRow(name) {
    var li = document.createElement('li');
    li.textContent = name + ' — starting';
    listEl.appendChild(li);
    return li;
  }

  function post(payload) {
    return fetch(API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) throw new Error(data.error || 'Request failed');
        return data;
      });
    });
  }

  function blobToBase64(blob) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () {
        var result = String(reader.result || '');
        var comma = result.indexOf(',');
        resolve(comma >= 0 ? result.slice(comma + 1) : result);
      };
      reader.onerror = function () {
        reject(new Error('Could not read the photo'));
      };
      reader.readAsDataURL(blob);
    });
  }

  function compressImage(source) {
    return createImageBitmap(source).then(function (bitmap) {
      var scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height));
      var canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(bitmap.width * scale));
      canvas.height = Math.max(1, Math.round(bitmap.height * scale));
      var ctx = canvas.getContext('2d');
      ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      bitmap.close();
      return new Promise(function (resolve, reject) {
        canvas.toBlob(
          function (blob) {
            if (!blob) reject(new Error('Could not compress that photo'));
            else resolve(blob);
          },
          'image/jpeg',
          JPEG_QUALITY
        );
      });
    });
  }

  function jpegName(name) {
    var base = String(name || 'photo').replace(/\.[^.]+$/, '');
    base = base.replace(/[^A-Za-z0-9._-]/g, '-').slice(0, 80) || 'photo';
    return base + '.jpg';
  }

  function uploadBlob(name, blob) {
    var row = addRow(name);
    return compressImage(blob)
      .catch(function () {
        return blob;
      })
      .then(function (out) {
        row.textContent = name + ' — saving';
        return blobToBase64(out).then(function (contentBase64) {
          return post({
            action: 'upload',
            secret: getSecret(),
            filename: jpegName(name),
            contentBase64: contentBase64,
          });
        });
      })
      .then(function (data) {
        row.textContent = name + ' — Saved as ' + data.path;
      })
      .catch(function (err) {
        row.textContent = name + ' — ' + (err.message || 'failed');
      });
  }

  function showTools() {
    unlockForm.hidden = true;
    tools.hidden = false;
    showError('');
  }

  function unlock(secret) {
    return post({ action: 'unlock', secret: secret }).then(function () {
      sessionStorage.setItem(STORAGE_SECRET, secret);
      showTools();
    });
  }

  function finishGoogleCode(code) {
    setStatus('Connecting Google Photos…');
    return post({
      action: 'google-token',
      secret: getSecret(),
      code: code,
      redirectUri: redirectUri(),
    }).then(function (data) {
      sessionStorage.setItem(STORAGE_GOOGLE, data.accessToken);
      history.replaceState({}, '', '/add-photos/');
      return startPicker(data.accessToken);
    });
  }

  function pollSession(accessToken, sessionId) {
    return post({
      action: 'google-session',
      secret: getSecret(),
      accessToken: accessToken,
      sessionId: sessionId,
    }).then(function (data) {
      if (data.mediaItemsSet) return data;
      return new Promise(function (resolve) {
        setTimeout(resolve, 1500);
      }).then(function () {
        return pollSession(accessToken, sessionId);
      });
    });
  }

  function startPicker(accessToken) {
    setStatus('Opening Google Photos…');
    return post({
      action: 'google-session-create',
      secret: getSecret(),
      accessToken: accessToken,
    }).then(function (data) {
      var picker = data.pickerUri + '/autoclose';
      window.open(picker, 'google-photos-picker', 'width=480,height=720');
      setStatus('Pick photos in the Google window, then come back here.');
      return pollSession(accessToken, data.sessionId).then(function () {
        return post({
          action: 'google-items',
          secret: getSecret(),
          accessToken: accessToken,
          sessionId: data.sessionId,
        });
      });
    }).then(function (listed) {
      var items = listed.items || [];
      if (!items.length) {
        setStatus('No photos were selected.');
        return;
      }
      setStatus('Saving ' + items.length + ' photo(s)…');
      var chain = Promise.resolve();
      items.forEach(function (item) {
        chain = chain.then(function () {
          return post({
            action: 'google-file',
            secret: getSecret(),
            accessToken: accessToken,
            baseUrl: item.baseUrl,
          }).then(function (file) {
            var bytes = atob(file.contentBase64);
            var arr = new Uint8Array(bytes.length);
            for (var i = 0; i < bytes.length; i += 1) arr[i] = bytes.charCodeAt(i);
            var blob = new Blob([arr], { type: item.mimeType || 'image/jpeg' });
            return uploadBlob(item.filename, blob);
          });
        });
      });
      return chain.then(function () {
        setStatus('Done. Attach these files in Pages CMS after the site rebuilds.');
      });
    });
  }

  unlockForm.addEventListener('submit', function (event) {
    event.preventDefault();
    var secret = (secretInput.value || '').trim();
    unlock(secret).catch(function (err) {
      showError(err.message || 'Could not unlock');
    });
  });

  googleBtn.addEventListener('click', function () {
    post({
      action: 'google-auth-url',
      secret: getSecret(),
      redirectUri: redirectUri(),
    })
      .then(function (data) {
        window.location.href = data.url;
      })
      .catch(function (err) {
        setStatus(err.message || 'Could not start Google Photos');
      });
  });

  fileInput.addEventListener('change', function () {
    var files = Array.prototype.slice.call(fileInput.files || []);
    fileInput.value = '';
    var chain = Promise.resolve();
    files.forEach(function (file) {
      chain = chain.then(function () {
        return uploadBlob(file.name, file);
      });
    });
    chain.then(function () {
      setStatus('Done. Attach these files in Pages CMS after the site rebuilds.');
    });
  });

  var params = new URLSearchParams(window.location.search);
  var code = params.get('code');
  var existingSecret = getSecret();
  if (existingSecret) {
    unlock(existingSecret)
      .then(function () {
        if (code) return finishGoogleCode(code);
      })
      .catch(function () {
        sessionStorage.removeItem(STORAGE_SECRET);
        showError('Enter the password again.');
      });
  } else if (code) {
    showError('Unlock with the password, then try Google Photos again.');
  }
})();
