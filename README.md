# Eric Wisnewski

A forever-stable Hugo blog: no JavaScript frameworks, no CSS frameworks, no Node.js. Vanilla CSS and HTML only.

## Preview and build

- **Preview (dev):** `hugo server` — uses **http://localhost:1313/** so you stay local (no redirect to production).
- **Production build:** Run `./scripts/sync-uploaded-images.sh` then `hugo --gc --minify`. The sync copies CMS uploads from `assets/images/uploads/` to `static/images/uploads/` so featured and inline images resolve on the live site.

This site is hosted on **Cloudflare Pages**. Set the build command to `./scripts/sync-uploaded-images.sh && hugo --gc --minify` in the Pages project. You can also deploy the `public/` directory to another static host if needed.

## Authors / contributors

Posts have an `author` front matter field that references a slug under `content/authors/` (e.g. `eric-wisnewski`, `grady-davis`). Each author file has `name`, `slug`, `bio`, and optional `image`. The single-post page shows a byline and an author bio block under the post; the home list shows the author name. Clicking an author name goes to `/authors/<slug>/` (photo, bio, then that author’s posts). The home page lists **all** published posts from **Posts** and **Grady’s Tour**, newest first.

**Grady’s Tour:** Travel posts live in `content/gradys-tour/` (CMS collection **Grady’s Tour**) and always publish at `/gradys-tour/<slug>/`. They also appear on the home page in chronological order with everyone else’s posts. Use **Posts** for Eric’s writing (`/posts/<slug>/`); do not put Grady’s travel posts there. `buildFuture = true` in `hugo.toml` so a CMS publish date that is a few minutes ahead of the Cloudflare build still goes live (otherwise Hugo omits the post and the URL falls through to the home page).

In **Pages CMS**, use the **Authors** collection to edit bios/photos, and set **Author** on each post. Invite contributors by email in Pages CMS so they can sign in with a magic link and write posts (pick themselves as Author).

Placeholder bios/images can be replaced anytime by editing the author files in the CMS or in `content/authors/`.

## Add a new post (without the CMS)

1. Create a new file under `content/posts/` (Eric / home page) or `content/gradys-tour/` (Grady’s travel posts), e.g. `content/posts/my-new-post.md`.
2. Add front matter at the top (include `slug` to match the filename and `author`):

   ```yaml
   ---
   title: "Your Post Title"
   slug: my-new-post
   author: eric-wisnewski
   date: 2025-02-26T00:00:00Z
   draft: false
   ---
   ```

3. Write your content below the front matter in Markdown.
4. Run `hugo` (or `hugo --gc --minify`) to rebuild. Home lists every published post (newest first) at `/`. Grady’s travel posts also appear on `/gradys-tour/` and at their own `/gradys-tour/<slug>/` URL. Author names link to `/authors/<slug>/`.

## Images (CMS and Markdown)

- **Where to put images:** Images under `/images/uploads/` are served from `static/images/uploads/`. The CMS writes to `assets/images/uploads/`; the build script `scripts/sync-uploaded-images.sh` copies them into `static/images/uploads/` before Hugo runs, so featured, gallery, and inline images work on the live site without manual copy.
- **Gallery (several at once):** Posts have a `gallery` front matter list. In Pages CMS, **Gallery** is an image field with `options.multiple` so the author can pick several photos from Photos in one upload, then remove any they do not want. Hugo renders that list as a grid via `layouts/partials/post-gallery.html`. Do not set `multiple` on Featured Image (`image` must stay a single path).
- **In post body (rich-text):** The post Body in Pages CMS is a rich-text (WYSIWYG) field. Use the editor toolbar or slash commands (`/`) to add **links** and **inline images**; “insert image” uses the same media library (`assets/images/uploads/`). Body content is stored as HTML and rendered by Hugo (Goldmark with raw HTML enabled). Inline body images are output as `<img>` tags; the responsive picture/WebP pipeline applies to images inserted via Markdown syntax in non-CMS workflows.
- **Featured / share image:** Set the `image` field in the post’s front matter (e.g. in the CMS “Featured Image” or in the YAML as `image: /images/uploads/hero.jpg`). That URL is used for `og:image` and `twitter:image`; the file must exist in `static/images/uploads/`.
## Change the School Sheets or Map links

Edit `config/_default/hugo.toml`. Under `[params]` you’ll see:

- `school_sheets_csv_url` — CSV URL for the School Sheets data. The `/school-sheets/` page fetches this at build time and displays it in a table. Use **File > Share > Publish to web** in Google Sheets and choose **Comma-separated values (.csv)** to get a permanent URL, or use the export URL if the sheet is shared "Anyone with the link can view": `https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}`.
- `nav_school_sheets` — URL for the "School Sheets" / "List of College Stadiums" link in the main nav (default: `/school-sheets/`).
- `nav_map` — URL for the "Map" link in the main nav (default: `/map/`)
- `nav_gradys_tour` — URL for the "Grady's Tour" link in the main nav (default: `/gradys-tour/`)

Update these values and rebuild. Nav links are used in the site header; the CSV URL is read by Hugo's `resources.GetRemote` when building the School Sheets page.

## Editing content (Pages CMS)

Content and media are edited via **Pages CMS**. Eric signs in with **email** (magic link sent to his inbox; invite him by email in the CMS if needed). Maintainers can use GitHub at [https://app.pagescms.org/](https://app.pagescms.org/); open this repository and branch, and use the configured collections (**Posts** for the home page, **Grady’s Tour** for travel posts, **Site updates** for the footer Updates log) and media (uploads). The post **Gallery** field accepts several photos at once; **Body** is a rich-text editor (format text, links, slash commands). Configuration lives in `.pages.yml` at the repo root.

**If the Cloudflare build fails** with *"date front matter field is not a parsable date"*: Hugo requires a full RFC3339 date (with seconds and timezone). In the CMS, set **Publish Date** again and save so it writes e.g. `2026-02-26T10:25:00Z`. The `.pages.yml` date format is set to `yyyy-MM-dd'T'HH:mm:ss'Z'` for this.

**If a new Grady’s Tour post is missing from `/gradys-tour/`:** Confirm it lives in `content/gradys-tour/` with `draft: false`. A publish date still in the future used to drop the post from the Hugo build; `buildFuture = true` keeps those posts in the output. Missing URLs on Cloudflare Pages fall through to the home page, which looks like the post “isn’t there.”

**Images for og:image / build:** Featured, gallery, and body images under `/images/uploads/` are served from `static/images/uploads/`. Run `./scripts/sync-uploaded-images.sh` before `hugo` (or use the full build command above) so CMS uploads are available in the built site.

## Analytics (Umami)

Privacy-friendly page views via [Umami Cloud](https://cloud.umami.is) (alternative to Cloudflare Web Analytics). The tracking script is injected from `layouts/partials/head.html` only when `hugo.IsProduction` and `params.umami_website_id` are set (so `hugo server` does not count local visits).

1. Sign up at [cloud.umami.is](https://cloud.umami.is) and add a website with domain `ericwisnewski.com`.
2. Copy the **Website ID** (UUID) from the Umami dashboard (Settings → Tracking code / website details).
3. In `config/_default/hugo.toml` under `[params]`, set:
   ```toml
   umami_website_id = 'YOUR-WEBSITE-UUID'
   umami_script_url = 'https://cloud.umami.is/script.js'
   ```
4. Deploy. Stats appear in the Umami dashboard after a few page views on the live site.

Self-hosted Umami: point `umami_script_url` at your instance’s `/script.js` and use that instance’s website ID.

## Comments

Comments are stored in **Cloudflare D1** and served by a **Pages Function** at `/api/comments` (GET list, POST new, PUT edit, DELETE). Threaded replies (one level) and author edit/delete (via localStorage token) are supported. The widget is in `layouts/partials/comments.html` and loads `static/js/comments.js`. **Cloudflare Turnstile** protects comment and reply submissions; the site key is in Hugo config and the secret is a Cloudflare env var.

To enable comments:

1. Create a D1 database (e.g. `blog-comments`) in the Cloudflare dashboard (Workers & Pages → D1) or run `npx wrangler d1 create blog-comments` and note the `database_id`.
2. Run the schema and migrations: `npx wrangler d1 execute blog-comments --remote --file=./migrations/0000_initial_comments.sql`, then `0001_comments_v2.sql`, then `0002_comments_allow.sql`, then `0003_relocate_gradys_tour_comment_urls.sql`, then `0004_newsletter.sql` (or run the SQL in the D1 dashboard).
3. Bind the database to your Pages project: in the dashboard go to your Pages project → Settings → Functions → Bindings → D1, add binding name `COMMENTS_DB` and select the database. Or add the binding to `wrangler.toml` (replace `<DATABASE_ID>` in `wrangler.toml` with your database id) and deploy with the config file as source of truth.
4. **Turnstile (captcha):** In [Cloudflare Dashboard → Turnstile](https://dash.cloudflare.com/?to=/:account/turnstile) create a widget and get the **site key** and **secret key**. Set the site key in `config/_default/hugo.toml` under `[params]` as `turnstile_site_key = "your-site-key"`. Add the **secret key** as a Cloudflare Pages secret: Settings → Environment variables → **TURNSTILE_SECRET_KEY** (encrypted). If `TURNSTILE_SECRET_KEY` is not set, the API skips verification (useful for local dev without a widget).
5. **Remove comments:** There is no public Flag button. Open **`/admin/comments/`**, enter `COMMENTS_ADMIN_SECRET`, click **Unlock**, then **Delete** (or **Edit**). Set that secret in Cloudflare Pages → Environment variables (e.g. `openssl rand -hex 32`) and share it with Eric/Grady; never commit it. The how-to on that page is the site-facing guide.

**If comments return 500:** Verify all five migrations have been run against the production D1 database and that the Pages D1 binding uses that database (see step 2 and 3 above). Check Functions logs in the Cloudflare dashboard for the underlying error.

**Grady’s Tour comment URLs:** Travel posts live at `/gradys-tour/<slug>/`. Comments posted when those pages still lived under `/posts/gradys-tour/<slug>/` are looked up under both paths, so they show on the live post. The admin comment list rewrites those old paths so the heading link goes to `/gradys-tour/<slug>/` instead of a missing `/posts/...` URL (which was falling through to the home page). `static/_redirects` 301s `/posts/gradys-tour/*` to the live URLs. After deploy, run migration `0003_relocate_gradys_tour_comment_urls.sql` so stored rows match the live paths (the lookup still works if that migration has not been run yet).

**Local dev with comments:** Build with the development config so the Turnstile test key is used (widget loads on localhost): `hugo --environment development`, then `npx wrangler pages dev ./public --d1 COMMENTS_DB=<database_id>`. Copy `.dev.vars.example` to `.dev.vars`; the example includes the optional Turnstile test secret so verification passes in dev. If `TURNSTILE_SECRET_KEY` is unset, the API skips verification. For admin delete locally, set `COMMENTS_ADMIN_SECRET` in `.dev.vars` (project root, same directory as `wrangler.toml`); uncomment the line and restart `wrangler pages dev` after changing `.dev.vars`. If you see "Admin secret not configured on server", the variable was not loaded—check the name and restart the dev server. If the comments list stays on "Loading…", the API may be unreachable (e.g. wrong origin); the UI now shows an error in the list when the fetch fails.

## Newsletter (per-type email alerts)

Subscribers can opt into **Eric’s blog** (`posts`), **Grady’s Tour** (`gradys-tour`), or both. Signups live in the same **Cloudflare D1** database as comments. Double opt-in and new-post emails go through **[Resend](https://resend.com)** via `/api/subscribe` and `/api/newsletter`. The form appears on the home page, Grady’s Tour list, and post pages when `newsletter_enabled = true` in `config/_default/hugo.toml`.

If someone submits an address that is already confirmed for the lists they checked, the form stays as they left it and tells them they are already subscribed (no extra confirmation email). Broken or expired confirm links go to `/subscribe/invalid/` instead of saying the person is confirmed. New-post emails include an **Unsubscribe or manage email preferences** link to `/subscribe/manage/?token=…`, where they can turn Eric’s blog and Grady’s Tour on or off. Mail-client one-click unsubscribe (`List-Unsubscribe`) still drops that list immediately.

**Cloudflare Pages secrets (Production):**

| Name | Notes |
| --- | --- |
| `RESEND_API_KEY` | From Resend → API Keys (`re_...`) |
| `NEWSLETTER_DISPATCH_SECRET` | e.g. `openssl rand -hex 32` |
| `NEWSLETTER_FROM_EMAIL` | Optional. Default `hello@ericwisnewski.com` (confirm + dispatch) |
| `TURNSTILE_SECRET_KEY` | Same as comments (subscribe uses Turnstile) |
| `NEWSLETTER_POSTAL_ADDRESS` | Physical mailing address in new-post footers (CAN-SPAM) |
| `NEWSLETTER_SITE_ORIGIN` | Optional. Pin confirm/unsubscribe links to `https://ericwisnewski.com` |

**GitHub:** repo → Settings → Secrets → Actions → `NEWSLETTER_DISPATCH_SECRET` (same value as Cloudflare). The workflow `.github/workflows/newsletter-dispatch.yml` POSTs `/api/newsletter` every 20 minutes.

**Go-live:** verify `ericwisnewski.com` in Resend, run migration `0004` on D1, set secrets above (including postal address), deploy. First dispatch run **seeds** existing RSS items without emailing; only new posts email after that. Feeds: `/posts/index.xml` and `/gradys-tour/index.xml` (not home `/index.xml`).

## Add photos (`/add-photos/`)

Authors add images on **`/add-photos/`**, not through Pages CMS (CMS uploads fail around 4.5 MB). The page compresses photos in the browser and a Pages Function commits them to `assets/images/uploads/`.

Cloudflare Pages → project `eric-wisnewski` → **Settings → Variables and secrets** (Production):

| Name | Notes |
| --- | --- |
| `GOOGLE_CLIENT_ID` | Google OAuth Web client ID |
| `GOOGLE_CLIENT_SECRET` | Encrypt |
| `UPLOAD_SECRET` | Password for `/add-photos/`. Encrypt |
| `GITHUB_TOKEN` | Fine-grained PAT: Contents **Read and write** on this repo. Encrypt |
| `GITHUB_REPO` | Optional. Default `tyler-morales/eric-wisnewski` |
| `GITHUB_BRANCH` | Optional. Default `main` |

Google Cloud: Photos Picker API on, OAuth consent (External, test users under **Audience**), redirect `https://ericwisnewski.com/add-photos/`.

After upload, attach files in Pages CMS Gallery / Featured Image / Body.

## Footer

Every page includes a short footer from `layouts/partials/footer.html` (wired in `layouts/_default/baseof.html`): copyright, [Updates](/updates/) (plain-language notes when the site gets better), a [Privacy](/privacy/) page, and “Send comments or questions to the webmaster, Tyler Morales” linking to [tylermorales.pro](https://tylermorales.pro). Name and URL are `builder_name` and `builder_url` in `config/_default/hugo.toml`.

**Updates log:** `/updates/` is footer-only (not in the main nav). Notes live in `content/updates/` and are grouped by month on one page. They are not blog posts, have no comments, and do not appear on the home page. In Pages CMS the collection is **Site updates**. Write for readers, not developers. Add a note when something on the site changes for the better.

## Tech notes

- CSS lives in `assets/css/style.css` and is fingerprinted on build so cache updates when you change styles.
