# TODOS

## Done
- [x] Image pipeline: `[imaging]` in hugo.toml; render hook `layouts/_default/_markup/render-image.html` (/images/uploads/ → responsive picture + WebP + lazy/async); featured image in head for og:image/twitter:image; Decap CMS config with media_folder assets/images/uploads.
- [x] Image render hook `layouts/_default/_markup/render-image.html`: /images/uploads/ → responsive picture (WebP + srcset 480/768/1024/1280); else simple img with lazy/async.
- [x] Forever-stable Hugo blog: hugo.toml, layouts (baseof, list, single, header, isso), static/css/style.css, first post.
- [x] README, .gitignore, a11y (semantic HTML, aria-label on nav, focus-visible in CSS).
- [x] Git tracking: init, remote `https://github.com/tyler-morales/eric-wisnewski.git`, initial commit pushed to `main`.
- [x] Robustness: CSS in assets with clamp() brand header, img/article rules, fingerprinting; head partial (OG/Twitter); hugo.toml description; Isso noscript fallback; README maintainer docs; netlify.toml build command.
- [x] Migrated from Decap CMS to Pages CMS: `.pages.yml` at repo root; content edited via https://app.pagescms.org/ (GitHub); removed `static/admin/` and `public/admin/`; added `slug` to post front matter and archetype for Pages CMS schema alignment.
- [x] Cloudflare Pages build fix: removed empty `theme = ''` from `config/_default/hugo.toml` so Hugo uses local layouts only (no theme module lookup).
- [x] Pages CMS rich-text body: Body field in `.pages.yml` set to `type: rich-text` (TipTap WYSIWYG: formatting, links, inline images from media library); Hugo `markup.goldmark.renderer.unsafe = true` in `config/_default/hugo.toml` so stored HTML renders.
- [x] Document 504 image-upload workaround: README + `.pages.yml` image field description + media `extensions` to discourage huge uploads.
- [x] Image upload tool: `/upload-image.html` compresses images in-browser and commits via Cloudflare Pages Function `functions/upload-image.js`; README documents Cloudflare env vars (GITHUB_TOKEN, UPLOAD_SECRET, etc.). Netlify function removed; use Cloudflare only.
- [x] Removed custom image upload tool and GitHub commit flow; CMS-only image uploads for now (until CMS behavior is tested).
- [x] Cloudflare build fix: `layouts/partials/head.html` only calls `.Fill` when the resource is an image (`.ResourceType "image"`), avoiding "this method is only available for image resources". README + `.pages.yml` document that Publish Date must save as ISO 8601 to avoid "date front matter field is not a parsable date".
- [x] Pages CMS image field aligned with docs: Featured Image uses `options.extensions: [jpg, jpeg, png, webp, gif]`; media config (input/output/extensions) already correct.
- [x] Pages CMS date field: added explicit `options.format: "yyyy-MM-dd'T'HH:mm"` for datetime (time: true) so stored value matches CMS docs and Hugo accepts it as ISO 8601–style.

## Later
- [ ] Re-evaluate custom upload tool (e.g. upload-image.html + Cloudflare function) if CMS uploads are unreliable.
- [ ] Set Isso server URL in `layouts/partials/isso.html` (replace `your-isso-domain.com` with your instance).
- [ ] Content is edited via Pages CMS (app.pagescms.org); ensure repo is connected and `.pages.yml` is present on the branch you use.
- [ ] Cloudflare Pages: if builds still fail with "module not found", ensure the **branch Cloudflare builds from** has the fix (no `theme = ''` in `config/_default/hugo.toml`). If Pages CMS pushes to a different branch, merge `main` into it or remove the theme line on that branch.

## Domain
- [x] Site domain set to **https://ericwisnewski.com** in `config/_default/hugo.toml` (baseURL). Canonical and og:url in `head.html` use it via `.Permalink`.
- [x] Dev stays local: `config/development/hugo.toml` overrides baseURL to `http://localhost:1313/` when running `hugo server` (no redirect to production).
- [x] Stylesheet 403 fix: use `RelPermalink` for CSS in `baseof.html` so the asset is always same-origin (fixes 403 when page is served from www but link pointed to non-www).
- [ ] Add content at `/school-sheets/` and `/map/` or update `config/_default/hugo.toml` params to point to external URLs.
