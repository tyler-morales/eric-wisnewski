# TODOS

## Done
- [x] First post rewritten as a simple, non-technical guide for Eric: how to use the blog, Pages CMS, adding/editing posts, images, and troubleshooting (no code).
- [x] Eric’s login: docs updated so Eric uses email (magic link) to sign in to Pages CMS, not GitHub; README and .pages.yml note invite-by-email for contributors.
- [x] Featured image in post body: single post template now renders `.Params.image` in the article (figure + img with alt, lazy load, focus-visible); CMS "Featured Image" appears on the live post page.
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
- [x] Pages CMS date field: use `options.format: "yyyy-MM-dd'T'HH:mm:ss'Z'"` so stored value is full RFC3339 (Hugo requires parsable date; missing seconds caused "date front matter field is not a parsable date" on Cloudflare).
- [x] Cloudflare build resource error: avoid referencing asset resources (resources.Get + Permalink/Fill) for og:image and render-image; use URL only and serve images from `static/images/uploads/` to avoid "Failed to publish Resource: open public: is a directory". Featured image copied to static so og:image URL resolves.
- [x] Nav links: `nav_school_sheets` and `nav_map` in `config/_default/hugo.toml` set to external Google Sheets and Google Maps URLs (header links open in same tab).
- [x] Map as internal route: clicking “Map” in nav goes to `/map/`; page uses `layouts/_default/map.html` with embedded Google Maps iframe (responsive wrapper in `assets/css/style.css`).
- [x] School Sheets as DB: `/school-sheets/` page fetches Google Sheet CSV via `resources.GetRemote`, parses with `transform.Unmarshal`, renders in `layouts/partials/school-sheets.html`; `school_sheets_csv_url` and `nav_school_sheets` in hugo.toml; minimal table styles in assets/css/style.css; README updated.
- [x] School Sheets table: removed Check column (visit flag); added search filter and column sorting (vanilla JS in layout, toolbar + sortable headers with aria-sort and focus states).
- [x] School and Map pages: added links to original files (Google Sheets view URL, Google Maps viewer URL) via `school_sheets_view_url` and `map_viewer_url` in hugo.toml; origin link styles with focus-visible for a11y.
- [x] School Sheets table responsive on mobile: card layout at max-width 640px (each row as labeled block via `data-label`); horizontal scroll with `-webkit-overflow-scrolling: touch` on larger viewports; thead hidden visually on mobile but kept for a11y.
- [x] School Sheets grade-column sort: Arena Rating, Fan Base, Campus sort by numeric grade (4.0 scale: A+=4.3 … F=0, N/A (A+)=4.3); `data-grade="true"` on those headers; `gradeToNumber()` in layout script; unparseable/blank → -Infinity so they sort to one end.
- [x] Home page post list: each blog entry shows featured image (`.Params.image`) when set; list images use uniform 16:9 aspect-ratio box with `object-fit: cover` so all thumbnails are the same size; list link is one block (image + title + date), a11y with `alt=""` on thumbnails (link text gives context).
- [x] Wizard emoji favicon: `static/favicon.svg` (🧙); linked in `layouts/partials/head.html` via `rel="icon"` type image/svg+xml.
- [x] Open Graph for share previews: `og:site_name` added; default `og:image` and `twitter:image` set to favicon.svg when post has no featured image so shared links always show title, description, and an image (per-post featured image still overrides). Note: some platforms (e.g. Facebook) prefer PNG/JPEG for og:image; if preview image is missing there, add `static/images/og-default.png` (e.g. 1200×630) and point default OG image to it.

## Later
- [ ] Re-evaluate custom upload tool (e.g. upload-image.html + Cloudflare function) if CMS uploads are unreliable.
- [ ] Set Isso server URL in `layouts/partials/isso.html` (replace `your-isso-domain.com` with your instance).
- [ ] Content is edited via Pages CMS (app.pagescms.org); ensure repo is connected and `.pages.yml` is present on the branch you use.
- [ ] Cloudflare Pages: if builds still fail with "module not found", ensure the **branch Cloudflare builds from** has the fix (no `theme = ''` in `config/_default/hugo.toml`). If Pages CMS pushes to a different branch, merge `main` into it or remove the theme line on that branch.
- [ ] Consider cache-bust or refresh note for Eric: when he updates the Google Sheet, a new deploy (or rebuild) is needed for the School Sheets page to show fresh data; optional: document or add a cache key hint in config.

## Domain
- [x] Site domain set to **https://ericwisnewski.com** in `config/_default/hugo.toml` (baseURL). Canonical and og:url in `head.html` use it via `.Permalink`.
- [x] Dev stays local: `config/development/hugo.toml` overrides baseURL to `http://localhost:1313/` when running `hugo server` (no redirect to production).
- [x] Stylesheet 403 fix: use `RelPermalink` for CSS in `baseof.html` so the asset is always same-origin (fixes 403 when page is served from www but link pointed to non-www).
- [x] ~~Add content at `/school-sheets/` and `/map/` or~~ update `config/_default/hugo.toml` params to point to external URLs (done: School Sheets points to Google URL; Map is now internal `/map/` page with embedded iframe).
