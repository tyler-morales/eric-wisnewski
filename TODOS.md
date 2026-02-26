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

## Later
- [ ] Set Isso server URL in `layouts/partials/isso.html` (replace `your-isso-domain.com` with your instance).
- [ ] Content is edited via Pages CMS (app.pagescms.org); ensure repo is connected and `.pages.yml` is present on the branch you use.

## Domain
- [x] Site domain set to **https://ericwisnewski.com** in `config/_default/hugo.toml` (baseURL). Canonical and og:url in `head.html` use it via `.Permalink`.
- [x] Dev stays local: `config/development/hugo.toml` overrides baseURL to `http://localhost:1313/` when running `hugo server` (no redirect to production).
- [ ] Add content at `/school-sheets/` and `/map/` or update `config/_default/hugo.toml` params to point to external URLs.
