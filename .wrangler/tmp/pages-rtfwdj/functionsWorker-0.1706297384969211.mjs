var __defProp = Object.defineProperty;
var __name = (target, value) => __defProp(target, "name", { value, configurable: true });

// api/comments.js
var MAX_AUTHOR = 200;
var MAX_TEXT = 5e3;
function isValidUrlParam(url) {
  if (typeof url !== "string" || !url) return false;
  const t = url.trim();
  return t.startsWith("/") && !t.startsWith("//") && !t.includes("://");
}
__name(isValidUrlParam, "isValidUrlParam");
function canonicalCommentUrl(url) {
  if (typeof url !== "string" || !url) return "";
  const t = url.trim().replace(/\/+/g, "/");
  if (!t.startsWith("/")) return "";
  if (t === "/") return "/";
  return t.endsWith("/") ? t : t + "/";
}
__name(canonicalCommentUrl, "canonicalCommentUrl");
function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}
__name(jsonResponse, "jsonResponse");
function isAdmin(secret, env) {
  const configured = env.COMMENTS_ADMIN_SECRET;
  return typeof configured === "string" && configured.length > 0 && secret === configured;
}
__name(isAdmin, "isAdmin");
async function onRequestGet(context) {
  const db = context.env.COMMENTS_DB;
  if (!db) return jsonResponse({ error: "Comments not configured" }, 503);
  const { searchParams } = new URL(context.request.url);
  const url = searchParams.get("url");
  const adminSecret = searchParams.get("admin_secret") ?? "";
  if (adminSecret && isAdmin(adminSecret, context.env)) {
    try {
      const stmt = db.prepare(
        `SELECT id, url, author, email, body, created_at, parent_id, edit_token FROM comments
         WHERE status = 'pending' ORDER BY url ASC, created_at ASC`
      );
      const { results } = await stmt.all();
      return jsonResponse(results ?? []);
    } catch (e) {
      const msg = e?.message != null ? String(e.message) : "";
      if (/no such column: status/i.test(msg)) {
        const stmt = db.prepare(
          "SELECT id, url, author, email, body, created_at, parent_id, edit_token FROM comments ORDER BY url ASC, created_at ASC"
        );
        const { results } = await stmt.all();
        return jsonResponse(results ?? []);
      }
      return jsonResponse({ error: "Failed to load comments" }, 500);
    }
  }
  if (adminSecret) {
    const configuredSet = typeof context.env.COMMENTS_ADMIN_SECRET === "string" && context.env.COMMENTS_ADMIN_SECRET.length > 0;
    return jsonResponse(
      { error: configuredSet ? "Invalid admin secret." : "Admin secret not configured on server." },
      401
    );
  }
  if (!isValidUrlParam(url)) {
    return jsonResponse({ error: "Missing or invalid url parameter" }, 400);
  }
  const canonical = canonicalCommentUrl(url);
  const alt = canonical === "/" ? "/" : canonical.slice(0, -1);
  try {
    const stmt = db.prepare(
      `SELECT id, url, author, body, created_at, parent_id FROM comments
       WHERE (url = ? OR url = ?) AND (status IS NULL OR status = 'approved') ORDER BY created_at ASC`
    );
    const { results } = await stmt.bind(canonical, alt).all();
    return jsonResponse(results ?? []);
  } catch (e) {
    const msg = e?.message != null ? String(e.message) : "";
    const missingColumn = /no such column/i.test(msg);
    if (missingColumn) {
      try {
        const stmtLegacy = db.prepare(
          "SELECT id, url, author, body, created_at FROM comments WHERE url = ? OR url = ? ORDER BY created_at ASC"
        );
        const { results: legacyResults } = await stmtLegacy.bind(canonical, alt).all();
        const withParentId = (legacyResults || []).map((row) => ({ ...row, parent_id: null }));
        return jsonResponse(withParentId);
      } catch (e2) {
        return jsonResponse({ error: "Failed to load comments" }, 500);
      }
    }
    return jsonResponse({ error: "Failed to load comments" }, 500);
  }
}
__name(onRequestGet, "onRequestGet");
async function onRequestPatch(context) {
  const db = context.env.COMMENTS_DB;
  if (!db) return jsonResponse({ error: "Comments not configured" }, 503);
  const { searchParams } = new URL(context.request.url);
  const id = searchParams.get("id") != null ? Number(searchParams.get("id")) : null;
  const adminSecret = searchParams.get("admin_secret") ?? "";
  if (!Number.isInteger(id) || id < 1) {
    return jsonResponse({ error: "Invalid or missing id" }, 400);
  }
  if (!adminSecret || !isAdmin(adminSecret, context.env)) {
    if (adminSecret) {
      const configuredSet = typeof context.env.COMMENTS_ADMIN_SECRET === "string" && context.env.COMMENTS_ADMIN_SECRET.length > 0;
      return jsonResponse(
        {
          error: configuredSet ? "Invalid admin secret." : "Admin secret not configured on server."
        },
        401
      );
    }
    return jsonResponse({ error: "admin_secret is required" }, 400);
  }
  const row = await db.prepare("SELECT id FROM comments WHERE id = ?").bind(id).first();
  if (!row) return jsonResponse({ error: "Comment not found" }, 404);
  try {
    await db.prepare("UPDATE comments SET status = ? WHERE id = ?").bind("approved", id).run();
    return new Response(null, { status: 204 });
  } catch (e) {
    const msg = e?.message != null ? String(e.message) : "";
    if (/no such column: status/i.test(msg)) {
      return jsonResponse({ error: "Comment approval not available (migration required)" }, 501);
    }
    return jsonResponse({ error: "Failed to approve comment" }, 500);
  }
}
__name(onRequestPatch, "onRequestPatch");
async function onRequestPost(context) {
  const db = context.env.COMMENTS_DB;
  if (!db) return jsonResponse({ error: "Comments not configured" }, 503);
  let body;
  try {
    body = await context.request.json();
  } catch {
    return jsonResponse({ error: "Invalid JSON body" }, 400);
  }
  const secret = context.env.TURNSTILE_SECRET_KEY;
  if (secret) {
    const token = body.cf_turnstile_response != null ? String(body.cf_turnstile_response).trim() : body["cf-turnstile-response"] != null ? String(body["cf-turnstile-response"]).trim() : "";
    if (!token) {
      return jsonResponse({ error: "Verification required" }, 400);
    }
    try {
      const verifyRes = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secret, response: token })
      });
      const verifyData = await verifyRes.json();
      if (!verifyData || verifyData.success !== true) {
        return jsonResponse({ error: "Verification failed" }, 400);
      }
    } catch (e) {
      return jsonResponse({ error: "Verification failed" }, 400);
    }
  }
  const rawUrl = body.url != null ? String(body.url).trim() : "";
  const url = canonicalCommentUrl(rawUrl);
  const author = body.author != null ? String(body.author).trim() : "";
  const text = body.text != null ? String(body.text).trim() : "";
  const email = body.email != null ? String(body.email).trim() : null;
  const parentId = body.parent_id != null ? Number(body.parent_id) : null;
  if (!url || !isValidUrlParam(rawUrl)) {
    return jsonResponse({ error: "Missing or invalid url" }, 400);
  }
  if (!author) return jsonResponse({ error: "Author is required" }, 400);
  if (author.length > MAX_AUTHOR) {
    return jsonResponse({ error: `Author must be at most ${MAX_AUTHOR} characters` }, 400);
  }
  if (!text) return jsonResponse({ error: "Comment text is required" }, 400);
  if (text.length > MAX_TEXT) {
    return jsonResponse({ error: `Comment must be at most ${MAX_TEXT} characters` }, 400);
  }
  if (parentId != null) {
    if (!Number.isInteger(parentId) || parentId < 1) {
      return jsonResponse({ error: "Invalid parent_id" }, 400);
    }
    const altUrl = url === "/" ? "/" : url.slice(0, -1);
    const parent = await db.prepare("SELECT id, parent_id FROM comments WHERE id = ? AND (url = ? OR url = ?)").bind(parentId, url, altUrl).first();
    if (!parent) {
      return jsonResponse({ error: "Parent comment not found" }, 400);
    }
    if (parent.parent_id != null) {
      return jsonResponse({ error: "Replies can only be to top-level comments" }, 400);
    }
  }
  const editToken = crypto.randomUUID();
  try {
    let meta;
    try {
      const stmt = db.prepare(
        "INSERT INTO comments (url, author, email, body, parent_id, edit_token, status) VALUES (?, ?, ?, ?, ?, ?, ?)"
      );
      const result = await stmt.bind(url, author, email || null, text, parentId, editToken, "pending").run();
      meta = result.meta;
    } catch (insertErr) {
      const msg = insertErr?.message != null ? String(insertErr.message) : "";
      if (/no such column: status/i.test(msg)) {
        const stmt = db.prepare(
          "INSERT INTO comments (url, author, email, body, parent_id, edit_token) VALUES (?, ?, ?, ?, ?, ?)"
        );
        const result = await stmt.bind(url, author, email || null, text, parentId, editToken).run();
        meta = result.meta;
      } else {
        throw insertErr;
      }
    }
    const row = await db.prepare(
      "SELECT id, url, author, body, created_at, parent_id FROM comments WHERE id = ?"
    ).bind(meta.last_row_id).first();
    return jsonResponse({ ...row, edit_token: editToken }, 201);
  } catch (e) {
    return jsonResponse({ error: "Failed to save comment" }, 500);
  }
}
__name(onRequestPost, "onRequestPost");
async function onRequestPut(context) {
  const db = context.env.COMMENTS_DB;
  if (!db) return jsonResponse({ error: "Comments not configured" }, 503);
  let body;
  try {
    body = await context.request.json();
  } catch {
    return jsonResponse({ error: "Invalid JSON body" }, 400);
  }
  const id = body.id != null ? Number(body.id) : null;
  const text = body.text != null ? String(body.text).trim() : "";
  const editToken = body.edit_token != null ? String(body.edit_token).trim() : "";
  const author = body.author != null ? String(body.author).trim() : null;
  if (!Number.isInteger(id) || id < 1) {
    return jsonResponse({ error: "Invalid or missing id" }, 400);
  }
  if (!editToken) return jsonResponse({ error: "edit_token is required" }, 400);
  if (!text) return jsonResponse({ error: "Comment text is required" }, 400);
  if (text.length > MAX_TEXT) {
    return jsonResponse({ error: `Comment must be at most ${MAX_TEXT} characters` }, 400);
  }
  if (author !== null) {
    if (!author) return jsonResponse({ error: "Author cannot be empty" }, 400);
    if (author.length > MAX_AUTHOR) {
      return jsonResponse({ error: `Author must be at most ${MAX_AUTHOR} characters` }, 400);
    }
  }
  const row = await db.prepare("SELECT id, edit_token, email FROM comments WHERE id = ?").bind(id).first();
  if (!row) return jsonResponse({ error: "Comment not found" }, 404);
  if (row.edit_token !== editToken) {
    return jsonResponse({ error: "Not authorized to edit this comment" }, 403);
  }
  try {
    if (author !== null) {
      if (row.email) {
        await db.prepare("UPDATE comments SET author = ? WHERE email = ?").bind(author, row.email).run();
      } else {
        await db.prepare("UPDATE comments SET author = ? WHERE id = ?").bind(author, id).run();
      }
    }
    await db.prepare("UPDATE comments SET body = ? WHERE id = ?").bind(text, id).run();
    const updated = await db.prepare(
      "SELECT id, url, author, body, created_at, parent_id FROM comments WHERE id = ?"
    ).bind(id).first();
    return jsonResponse(updated);
  } catch (e) {
    return jsonResponse({ error: "Failed to update comment" }, 500);
  }
}
__name(onRequestPut, "onRequestPut");
async function onRequestDelete(context) {
  const db = context.env.COMMENTS_DB;
  if (!db) return jsonResponse({ error: "Comments not configured" }, 503);
  const { searchParams } = new URL(context.request.url);
  const id = searchParams.get("id") != null ? Number(searchParams.get("id")) : null;
  const editToken = searchParams.get("edit_token") ?? "";
  const adminSecret = searchParams.get("admin_secret") ?? "";
  const asAdmin = adminSecret && isAdmin(adminSecret, context.env);
  if (!Number.isInteger(id) || id < 1) {
    return jsonResponse({ error: "Invalid or missing id" }, 400);
  }
  if (!asAdmin && !editToken) {
    return jsonResponse({ error: "edit_token or admin_secret is required" }, 400);
  }
  const row = await db.prepare("SELECT id, edit_token, parent_id FROM comments WHERE id = ?").bind(id).first();
  if (!row) return jsonResponse({ error: "Comment not found" }, 404);
  if (!asAdmin && row.edit_token !== editToken) {
    return jsonResponse({ error: "Not authorized to delete this comment" }, 403);
  }
  try {
    if (row.parent_id == null) {
      await db.prepare("DELETE FROM comments WHERE id = ? OR parent_id = ?").bind(id, id).run();
    } else {
      await db.prepare("DELETE FROM comments WHERE id = ?").bind(id).run();
    }
    return new Response(null, { status: 204 });
  } catch (e) {
    return jsonResponse({ error: "Failed to delete comment" }, 500);
  }
}
__name(onRequestDelete, "onRequestDelete");

// ../.wrangler/tmp/pages-rtfwdj/functionsRoutes-0.030875280107424796.mjs
var routes = [
  {
    routePath: "/api/comments",
    mountPath: "/api",
    method: "DELETE",
    middlewares: [],
    modules: [onRequestDelete]
  },
  {
    routePath: "/api/comments",
    mountPath: "/api",
    method: "GET",
    middlewares: [],
    modules: [onRequestGet]
  },
  {
    routePath: "/api/comments",
    mountPath: "/api",
    method: "PATCH",
    middlewares: [],
    modules: [onRequestPatch]
  },
  {
    routePath: "/api/comments",
    mountPath: "/api",
    method: "POST",
    middlewares: [],
    modules: [onRequestPost]
  },
  {
    routePath: "/api/comments",
    mountPath: "/api",
    method: "PUT",
    middlewares: [],
    modules: [onRequestPut]
  }
];

// ../../../../.npm/_npx/32026684e21afda6/node_modules/path-to-regexp/dist.es2015/index.js
function lexer(str) {
  var tokens = [];
  var i = 0;
  while (i < str.length) {
    var char = str[i];
    if (char === "*" || char === "+" || char === "?") {
      tokens.push({ type: "MODIFIER", index: i, value: str[i++] });
      continue;
    }
    if (char === "\\") {
      tokens.push({ type: "ESCAPED_CHAR", index: i++, value: str[i++] });
      continue;
    }
    if (char === "{") {
      tokens.push({ type: "OPEN", index: i, value: str[i++] });
      continue;
    }
    if (char === "}") {
      tokens.push({ type: "CLOSE", index: i, value: str[i++] });
      continue;
    }
    if (char === ":") {
      var name = "";
      var j = i + 1;
      while (j < str.length) {
        var code = str.charCodeAt(j);
        if (
          // `0-9`
          code >= 48 && code <= 57 || // `A-Z`
          code >= 65 && code <= 90 || // `a-z`
          code >= 97 && code <= 122 || // `_`
          code === 95
        ) {
          name += str[j++];
          continue;
        }
        break;
      }
      if (!name)
        throw new TypeError("Missing parameter name at ".concat(i));
      tokens.push({ type: "NAME", index: i, value: name });
      i = j;
      continue;
    }
    if (char === "(") {
      var count = 1;
      var pattern = "";
      var j = i + 1;
      if (str[j] === "?") {
        throw new TypeError('Pattern cannot start with "?" at '.concat(j));
      }
      while (j < str.length) {
        if (str[j] === "\\") {
          pattern += str[j++] + str[j++];
          continue;
        }
        if (str[j] === ")") {
          count--;
          if (count === 0) {
            j++;
            break;
          }
        } else if (str[j] === "(") {
          count++;
          if (str[j + 1] !== "?") {
            throw new TypeError("Capturing groups are not allowed at ".concat(j));
          }
        }
        pattern += str[j++];
      }
      if (count)
        throw new TypeError("Unbalanced pattern at ".concat(i));
      if (!pattern)
        throw new TypeError("Missing pattern at ".concat(i));
      tokens.push({ type: "PATTERN", index: i, value: pattern });
      i = j;
      continue;
    }
    tokens.push({ type: "CHAR", index: i, value: str[i++] });
  }
  tokens.push({ type: "END", index: i, value: "" });
  return tokens;
}
__name(lexer, "lexer");
function parse(str, options) {
  if (options === void 0) {
    options = {};
  }
  var tokens = lexer(str);
  var _a = options.prefixes, prefixes = _a === void 0 ? "./" : _a, _b = options.delimiter, delimiter = _b === void 0 ? "/#?" : _b;
  var result = [];
  var key = 0;
  var i = 0;
  var path = "";
  var tryConsume = /* @__PURE__ */ __name(function(type) {
    if (i < tokens.length && tokens[i].type === type)
      return tokens[i++].value;
  }, "tryConsume");
  var mustConsume = /* @__PURE__ */ __name(function(type) {
    var value2 = tryConsume(type);
    if (value2 !== void 0)
      return value2;
    var _a2 = tokens[i], nextType = _a2.type, index = _a2.index;
    throw new TypeError("Unexpected ".concat(nextType, " at ").concat(index, ", expected ").concat(type));
  }, "mustConsume");
  var consumeText = /* @__PURE__ */ __name(function() {
    var result2 = "";
    var value2;
    while (value2 = tryConsume("CHAR") || tryConsume("ESCAPED_CHAR")) {
      result2 += value2;
    }
    return result2;
  }, "consumeText");
  var isSafe = /* @__PURE__ */ __name(function(value2) {
    for (var _i = 0, delimiter_1 = delimiter; _i < delimiter_1.length; _i++) {
      var char2 = delimiter_1[_i];
      if (value2.indexOf(char2) > -1)
        return true;
    }
    return false;
  }, "isSafe");
  var safePattern = /* @__PURE__ */ __name(function(prefix2) {
    var prev = result[result.length - 1];
    var prevText = prefix2 || (prev && typeof prev === "string" ? prev : "");
    if (prev && !prevText) {
      throw new TypeError('Must have text between two parameters, missing text after "'.concat(prev.name, '"'));
    }
    if (!prevText || isSafe(prevText))
      return "[^".concat(escapeString(delimiter), "]+?");
    return "(?:(?!".concat(escapeString(prevText), ")[^").concat(escapeString(delimiter), "])+?");
  }, "safePattern");
  while (i < tokens.length) {
    var char = tryConsume("CHAR");
    var name = tryConsume("NAME");
    var pattern = tryConsume("PATTERN");
    if (name || pattern) {
      var prefix = char || "";
      if (prefixes.indexOf(prefix) === -1) {
        path += prefix;
        prefix = "";
      }
      if (path) {
        result.push(path);
        path = "";
      }
      result.push({
        name: name || key++,
        prefix,
        suffix: "",
        pattern: pattern || safePattern(prefix),
        modifier: tryConsume("MODIFIER") || ""
      });
      continue;
    }
    var value = char || tryConsume("ESCAPED_CHAR");
    if (value) {
      path += value;
      continue;
    }
    if (path) {
      result.push(path);
      path = "";
    }
    var open = tryConsume("OPEN");
    if (open) {
      var prefix = consumeText();
      var name_1 = tryConsume("NAME") || "";
      var pattern_1 = tryConsume("PATTERN") || "";
      var suffix = consumeText();
      mustConsume("CLOSE");
      result.push({
        name: name_1 || (pattern_1 ? key++ : ""),
        pattern: name_1 && !pattern_1 ? safePattern(prefix) : pattern_1,
        prefix,
        suffix,
        modifier: tryConsume("MODIFIER") || ""
      });
      continue;
    }
    mustConsume("END");
  }
  return result;
}
__name(parse, "parse");
function match(str, options) {
  var keys = [];
  var re = pathToRegexp(str, keys, options);
  return regexpToFunction(re, keys, options);
}
__name(match, "match");
function regexpToFunction(re, keys, options) {
  if (options === void 0) {
    options = {};
  }
  var _a = options.decode, decode = _a === void 0 ? function(x) {
    return x;
  } : _a;
  return function(pathname) {
    var m = re.exec(pathname);
    if (!m)
      return false;
    var path = m[0], index = m.index;
    var params = /* @__PURE__ */ Object.create(null);
    var _loop_1 = /* @__PURE__ */ __name(function(i2) {
      if (m[i2] === void 0)
        return "continue";
      var key = keys[i2 - 1];
      if (key.modifier === "*" || key.modifier === "+") {
        params[key.name] = m[i2].split(key.prefix + key.suffix).map(function(value) {
          return decode(value, key);
        });
      } else {
        params[key.name] = decode(m[i2], key);
      }
    }, "_loop_1");
    for (var i = 1; i < m.length; i++) {
      _loop_1(i);
    }
    return { path, index, params };
  };
}
__name(regexpToFunction, "regexpToFunction");
function escapeString(str) {
  return str.replace(/([.+*?=^!:${}()[\]|/\\])/g, "\\$1");
}
__name(escapeString, "escapeString");
function flags(options) {
  return options && options.sensitive ? "" : "i";
}
__name(flags, "flags");
function regexpToRegexp(path, keys) {
  if (!keys)
    return path;
  var groupsRegex = /\((?:\?<(.*?)>)?(?!\?)/g;
  var index = 0;
  var execResult = groupsRegex.exec(path.source);
  while (execResult) {
    keys.push({
      // Use parenthesized substring match if available, index otherwise
      name: execResult[1] || index++,
      prefix: "",
      suffix: "",
      modifier: "",
      pattern: ""
    });
    execResult = groupsRegex.exec(path.source);
  }
  return path;
}
__name(regexpToRegexp, "regexpToRegexp");
function arrayToRegexp(paths, keys, options) {
  var parts = paths.map(function(path) {
    return pathToRegexp(path, keys, options).source;
  });
  return new RegExp("(?:".concat(parts.join("|"), ")"), flags(options));
}
__name(arrayToRegexp, "arrayToRegexp");
function stringToRegexp(path, keys, options) {
  return tokensToRegexp(parse(path, options), keys, options);
}
__name(stringToRegexp, "stringToRegexp");
function tokensToRegexp(tokens, keys, options) {
  if (options === void 0) {
    options = {};
  }
  var _a = options.strict, strict = _a === void 0 ? false : _a, _b = options.start, start = _b === void 0 ? true : _b, _c = options.end, end = _c === void 0 ? true : _c, _d = options.encode, encode = _d === void 0 ? function(x) {
    return x;
  } : _d, _e = options.delimiter, delimiter = _e === void 0 ? "/#?" : _e, _f = options.endsWith, endsWith = _f === void 0 ? "" : _f;
  var endsWithRe = "[".concat(escapeString(endsWith), "]|$");
  var delimiterRe = "[".concat(escapeString(delimiter), "]");
  var route = start ? "^" : "";
  for (var _i = 0, tokens_1 = tokens; _i < tokens_1.length; _i++) {
    var token = tokens_1[_i];
    if (typeof token === "string") {
      route += escapeString(encode(token));
    } else {
      var prefix = escapeString(encode(token.prefix));
      var suffix = escapeString(encode(token.suffix));
      if (token.pattern) {
        if (keys)
          keys.push(token);
        if (prefix || suffix) {
          if (token.modifier === "+" || token.modifier === "*") {
            var mod = token.modifier === "*" ? "?" : "";
            route += "(?:".concat(prefix, "((?:").concat(token.pattern, ")(?:").concat(suffix).concat(prefix, "(?:").concat(token.pattern, "))*)").concat(suffix, ")").concat(mod);
          } else {
            route += "(?:".concat(prefix, "(").concat(token.pattern, ")").concat(suffix, ")").concat(token.modifier);
          }
        } else {
          if (token.modifier === "+" || token.modifier === "*") {
            throw new TypeError('Can not repeat "'.concat(token.name, '" without a prefix and suffix'));
          }
          route += "(".concat(token.pattern, ")").concat(token.modifier);
        }
      } else {
        route += "(?:".concat(prefix).concat(suffix, ")").concat(token.modifier);
      }
    }
  }
  if (end) {
    if (!strict)
      route += "".concat(delimiterRe, "?");
    route += !options.endsWith ? "$" : "(?=".concat(endsWithRe, ")");
  } else {
    var endToken = tokens[tokens.length - 1];
    var isEndDelimited = typeof endToken === "string" ? delimiterRe.indexOf(endToken[endToken.length - 1]) > -1 : endToken === void 0;
    if (!strict) {
      route += "(?:".concat(delimiterRe, "(?=").concat(endsWithRe, "))?");
    }
    if (!isEndDelimited) {
      route += "(?=".concat(delimiterRe, "|").concat(endsWithRe, ")");
    }
  }
  return new RegExp(route, flags(options));
}
__name(tokensToRegexp, "tokensToRegexp");
function pathToRegexp(path, keys, options) {
  if (path instanceof RegExp)
    return regexpToRegexp(path, keys);
  if (Array.isArray(path))
    return arrayToRegexp(path, keys, options);
  return stringToRegexp(path, keys, options);
}
__name(pathToRegexp, "pathToRegexp");

// ../../../../.npm/_npx/32026684e21afda6/node_modules/wrangler/templates/pages-template-worker.ts
var escapeRegex = /[.+?^${}()|[\]\\]/g;
function* executeRequest(request) {
  const requestPath = new URL(request.url).pathname;
  for (const route of [...routes].reverse()) {
    if (route.method && route.method !== request.method) {
      continue;
    }
    const routeMatcher = match(route.routePath.replace(escapeRegex, "\\$&"), {
      end: false
    });
    const mountMatcher = match(route.mountPath.replace(escapeRegex, "\\$&"), {
      end: false
    });
    const matchResult = routeMatcher(requestPath);
    const mountMatchResult = mountMatcher(requestPath);
    if (matchResult && mountMatchResult) {
      for (const handler of route.middlewares.flat()) {
        yield {
          handler,
          params: matchResult.params,
          path: mountMatchResult.path
        };
      }
    }
  }
  for (const route of routes) {
    if (route.method && route.method !== request.method) {
      continue;
    }
    const routeMatcher = match(route.routePath.replace(escapeRegex, "\\$&"), {
      end: true
    });
    const mountMatcher = match(route.mountPath.replace(escapeRegex, "\\$&"), {
      end: false
    });
    const matchResult = routeMatcher(requestPath);
    const mountMatchResult = mountMatcher(requestPath);
    if (matchResult && mountMatchResult && route.modules.length) {
      for (const handler of route.modules.flat()) {
        yield {
          handler,
          params: matchResult.params,
          path: matchResult.path
        };
      }
      break;
    }
  }
}
__name(executeRequest, "executeRequest");
var pages_template_worker_default = {
  async fetch(originalRequest, env, workerContext) {
    let request = originalRequest;
    const handlerIterator = executeRequest(request);
    let data = {};
    let isFailOpen = false;
    const next = /* @__PURE__ */ __name(async (input, init) => {
      if (input !== void 0) {
        let url = input;
        if (typeof input === "string") {
          url = new URL(input, request.url).toString();
        }
        request = new Request(url, init);
      }
      const result = handlerIterator.next();
      if (result.done === false) {
        const { handler, params, path } = result.value;
        const context = {
          request: new Request(request.clone()),
          functionPath: path,
          next,
          params,
          get data() {
            return data;
          },
          set data(value) {
            if (typeof value !== "object" || value === null) {
              throw new Error("context.data must be an object");
            }
            data = value;
          },
          env,
          waitUntil: workerContext.waitUntil.bind(workerContext),
          passThroughOnException: /* @__PURE__ */ __name(() => {
            isFailOpen = true;
          }, "passThroughOnException")
        };
        const response = await handler(context);
        if (!(response instanceof Response)) {
          throw new Error("Your Pages function should return a Response");
        }
        return cloneResponse(response);
      } else if ("ASSETS") {
        const response = await env["ASSETS"].fetch(request);
        return cloneResponse(response);
      } else {
        const response = await fetch(request);
        return cloneResponse(response);
      }
    }, "next");
    try {
      return await next();
    } catch (error) {
      if (isFailOpen) {
        const response = await env["ASSETS"].fetch(request);
        return cloneResponse(response);
      }
      throw error;
    }
  }
};
var cloneResponse = /* @__PURE__ */ __name((response) => (
  // https://fetch.spec.whatwg.org/#null-body-status
  new Response(
    [101, 204, 205, 304].includes(response.status) ? null : response.body,
    response
  )
), "cloneResponse");

// ../../../../.npm/_npx/32026684e21afda6/node_modules/wrangler/templates/middleware/middleware-ensure-req-body-drained.ts
var drainBody = /* @__PURE__ */ __name(async (request, env, _ctx, middlewareCtx) => {
  try {
    return await middlewareCtx.next(request, env);
  } finally {
    try {
      if (request.body !== null && !request.bodyUsed) {
        const reader = request.body.getReader();
        while (!(await reader.read()).done) {
        }
      }
    } catch (e) {
      console.error("Failed to drain the unused request body.", e);
    }
  }
}, "drainBody");
var middleware_ensure_req_body_drained_default = drainBody;

// ../../../../.npm/_npx/32026684e21afda6/node_modules/wrangler/templates/middleware/middleware-miniflare3-json-error.ts
function reduceError(e) {
  return {
    name: e?.name,
    message: e?.message ?? String(e),
    stack: e?.stack,
    cause: e?.cause === void 0 ? void 0 : reduceError(e.cause)
  };
}
__name(reduceError, "reduceError");
var jsonError = /* @__PURE__ */ __name(async (request, env, _ctx, middlewareCtx) => {
  try {
    return await middlewareCtx.next(request, env);
  } catch (e) {
    const error = reduceError(e);
    return Response.json(error, {
      status: 500,
      headers: { "MF-Experimental-Error-Stack": "true" }
    });
  }
}, "jsonError");
var middleware_miniflare3_json_error_default = jsonError;

// ../.wrangler/tmp/bundle-nRTNa3/middleware-insertion-facade.js
var __INTERNAL_WRANGLER_MIDDLEWARE__ = [
  middleware_ensure_req_body_drained_default,
  middleware_miniflare3_json_error_default
];
var middleware_insertion_facade_default = pages_template_worker_default;

// ../../../../.npm/_npx/32026684e21afda6/node_modules/wrangler/templates/middleware/common.ts
var __facade_middleware__ = [];
function __facade_register__(...args) {
  __facade_middleware__.push(...args.flat());
}
__name(__facade_register__, "__facade_register__");
function __facade_invokeChain__(request, env, ctx, dispatch, middlewareChain) {
  const [head, ...tail] = middlewareChain;
  const middlewareCtx = {
    dispatch,
    next(newRequest, newEnv) {
      return __facade_invokeChain__(newRequest, newEnv, ctx, dispatch, tail);
    }
  };
  return head(request, env, ctx, middlewareCtx);
}
__name(__facade_invokeChain__, "__facade_invokeChain__");
function __facade_invoke__(request, env, ctx, dispatch, finalMiddleware) {
  return __facade_invokeChain__(request, env, ctx, dispatch, [
    ...__facade_middleware__,
    finalMiddleware
  ]);
}
__name(__facade_invoke__, "__facade_invoke__");

// ../.wrangler/tmp/bundle-nRTNa3/middleware-loader.entry.ts
var __Facade_ScheduledController__ = class ___Facade_ScheduledController__ {
  constructor(scheduledTime, cron, noRetry) {
    this.scheduledTime = scheduledTime;
    this.cron = cron;
    this.#noRetry = noRetry;
  }
  static {
    __name(this, "__Facade_ScheduledController__");
  }
  #noRetry;
  noRetry() {
    if (!(this instanceof ___Facade_ScheduledController__)) {
      throw new TypeError("Illegal invocation");
    }
    this.#noRetry();
  }
};
function wrapExportedHandler(worker) {
  if (__INTERNAL_WRANGLER_MIDDLEWARE__ === void 0 || __INTERNAL_WRANGLER_MIDDLEWARE__.length === 0) {
    return worker;
  }
  for (const middleware of __INTERNAL_WRANGLER_MIDDLEWARE__) {
    __facade_register__(middleware);
  }
  const fetchDispatcher = /* @__PURE__ */ __name(function(request, env, ctx) {
    if (worker.fetch === void 0) {
      throw new Error("Handler does not export a fetch() function.");
    }
    return worker.fetch(request, env, ctx);
  }, "fetchDispatcher");
  return {
    ...worker,
    fetch(request, env, ctx) {
      const dispatcher = /* @__PURE__ */ __name(function(type, init) {
        if (type === "scheduled" && worker.scheduled !== void 0) {
          const controller = new __Facade_ScheduledController__(
            Date.now(),
            init.cron ?? "",
            () => {
            }
          );
          return worker.scheduled(controller, env, ctx);
        }
      }, "dispatcher");
      return __facade_invoke__(request, env, ctx, dispatcher, fetchDispatcher);
    }
  };
}
__name(wrapExportedHandler, "wrapExportedHandler");
function wrapWorkerEntrypoint(klass) {
  if (__INTERNAL_WRANGLER_MIDDLEWARE__ === void 0 || __INTERNAL_WRANGLER_MIDDLEWARE__.length === 0) {
    return klass;
  }
  for (const middleware of __INTERNAL_WRANGLER_MIDDLEWARE__) {
    __facade_register__(middleware);
  }
  return class extends klass {
    #fetchDispatcher = /* @__PURE__ */ __name((request, env, ctx) => {
      this.env = env;
      this.ctx = ctx;
      if (super.fetch === void 0) {
        throw new Error("Entrypoint class does not define a fetch() function.");
      }
      return super.fetch(request);
    }, "#fetchDispatcher");
    #dispatcher = /* @__PURE__ */ __name((type, init) => {
      if (type === "scheduled" && super.scheduled !== void 0) {
        const controller = new __Facade_ScheduledController__(
          Date.now(),
          init.cron ?? "",
          () => {
          }
        );
        return super.scheduled(controller);
      }
    }, "#dispatcher");
    fetch(request) {
      return __facade_invoke__(
        request,
        this.env,
        this.ctx,
        this.#dispatcher,
        this.#fetchDispatcher
      );
    }
  };
}
__name(wrapWorkerEntrypoint, "wrapWorkerEntrypoint");
var WRAPPED_ENTRY;
if (typeof middleware_insertion_facade_default === "object") {
  WRAPPED_ENTRY = wrapExportedHandler(middleware_insertion_facade_default);
} else if (typeof middleware_insertion_facade_default === "function") {
  WRAPPED_ENTRY = wrapWorkerEntrypoint(middleware_insertion_facade_default);
}
var middleware_loader_entry_default = WRAPPED_ENTRY;
export {
  __INTERNAL_WRANGLER_MIDDLEWARE__,
  middleware_loader_entry_default as default
};
//# sourceMappingURL=functionsWorker-0.1706297384969211.mjs.map
