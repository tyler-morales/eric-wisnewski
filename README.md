# Eric Wisnewski

A forever-stable Hugo blog: no JavaScript frameworks, no CSS frameworks, no Node.js. Vanilla CSS and HTML only.

## Preview and build

- **Preview (dev):** `hugo server` — uses **http://localhost:1313/** so you stay local (no redirect to production).
- **Production build:** Run `./scripts/sync-uploaded-images.sh` then `hugo --gc --minify`. The sync copies CMS uploads from `assets/images/uploads/` to `static/images/uploads/` so featured and inline images resolve on the live site.

Deploy the `public/` directory to any static host (GitHub Pages, Netlify, Vercel, Cloudflare Pages). Set the build command to `./scripts/sync-uploaded-images.sh && hugo --gc --minify` in your host’s dashboard (or use the included `netlify.toml` if you use Netlify).

## Add a new post (without the CMS)

1. Create a new file under `content/posts/`, e.g. `content/posts/my-new-post.md`.
2. Add front matter at the top (include `slug` to match the filename):

   ```yaml
   ---
   title: "Your Post Title"
   slug: my-new-post
   date: 2025-02-26T00:00:00Z
   draft: false
   ---
   ```

3. Write your content below the front matter in Markdown.
4. Run `hugo` (or `hugo --gc --minify`) to rebuild. The new post will appear in the list and at its own URL.

## Images (CMS and Markdown)

- **Where to put images:** Images under `/images/uploads/` are served from `static/images/uploads/`. The CMS writes to `assets/images/uploads/`; the build script `scripts/sync-uploaded-images.sh` copies them into `static/images/uploads/` before Hugo runs, so featured and inline images work on the live site without manual copy.
- **In post body (rich-text):** The post Body in Pages CMS is a rich-text (WYSIWYG) field. Use the editor toolbar or slash commands (`/`) to add **links** and **inline images**; “insert image” uses the same media library (`assets/images/uploads/`). Body content is stored as HTML and rendered by Hugo (Goldmark with raw HTML enabled). Inline body images are output as `<img>` tags; the responsive picture/WebP pipeline applies to images inserted via Markdown syntax in non-CMS workflows.
- **Featured / share image:** Set the `image` field in the post’s front matter (e.g. in the CMS “Featured Image” or in the YAML as `image: /images/uploads/hero.jpg`). That URL is used for `og:image` and `twitter:image`; the file must exist in `static/images/uploads/`.
## Change the School Sheets or Map links

Edit `config/_default/hugo.toml`. Under `[params]` you’ll see:

- `school_sheets_csv_url` — CSV URL for the School Sheets data. The `/school-sheets/` page fetches this at build time and displays it in a table. Use **File > Share > Publish to web** in Google Sheets and choose **Comma-separated values (.csv)** to get a permanent URL, or use the export URL if the sheet is shared "Anyone with the link can view": `https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}`.
- `nav_school_sheets` — URL for the "School Sheets" link in the main nav (default: `/school-sheets/`).
- `nav_map` — URL for the "Map" link in the main nav (default: `/map/`)

Update these values and rebuild. Nav links are used in the site header; the CSV URL is read by Hugo's `resources.GetRemote` when building the School Sheets page.

## Editing content (Pages CMS)

Content and media are edited via **Pages CMS**. Eric signs in with **email** (magic link sent to his inbox; invite him by email in the CMS if needed). Maintainers can use GitHub at [https://app.pagescms.org/](https://app.pagescms.org/); open this repository and branch, and use the configured collections (Posts) and media (uploads). The post **Body** is a rich-text editor: you can format text (bold, italic, headings, lists, blockquotes, code), add links, and insert images from the media library. Type `/` in the body for slash commands. Configuration lives in `.pages.yml` at the repo root.

**If the Cloudflare build fails** with *"date front matter field is not a parsable date"*: Hugo requires a full RFC3339 date (with seconds and timezone). In the CMS, set **Publish Date** again and save so it writes e.g. `2026-02-26T10:25:00Z`. The `.pages.yml` date format is set to `yyyy-MM-dd'T'HH:mm:ss'Z'` for this.

**Images for og:image / build:** Featured and body images under `/images/uploads/` are served from `static/images/uploads/`. Run `./scripts/sync-uploaded-images.sh` before `hugo` (or use the full build command above) so CMS uploads are available in the built site.

## Tech notes

- CSS lives in `assets/css/style.css` and is fingerprinted on build so cache updates when you change styles.
- Comments are powered by Isso; configure the Isso server URL in `layouts/partials/isso.html` (`data-isso` and `src` on the script tag).
