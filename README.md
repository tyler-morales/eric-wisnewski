# Eric Wisnewski

A forever-stable Hugo blog: no JavaScript frameworks, no CSS frameworks, no Node.js. Vanilla CSS and HTML only.

## Preview and build

- **Preview (dev):** `hugo server` — uses **http://localhost:1313/** so you stay local (no redirect to production).
- **Production build:** `hugo --gc --minify` (use this for deployment; `--gc` removes unused files, `--minify` strips whitespace)

Deploy the `public/` directory to any static host (GitHub Pages, Netlify, Vercel, Cloudflare Pages). Set the build command to `hugo --gc --minify` in your host’s dashboard (or use the included `netlify.toml` if you use Netlify).

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

- **Where to upload:** In Pages CMS, images are stored under `assets/images/uploads/`. This path is required so Hugo can process them (resize, WebP, fingerprint). Do not put CMS uploads in `static/`.
- **In post body (rich-text):** The post Body in Pages CMS is a rich-text (WYSIWYG) field. Use the editor toolbar or slash commands (`/`) to add **links** and **inline images**; “insert image” uses the same media library (`assets/images/uploads/`). Body content is stored as HTML and rendered by Hugo (Goldmark with raw HTML enabled). Inline body images are output as `<img>` tags; the responsive picture/WebP pipeline applies to images inserted via Markdown syntax in non-CMS workflows.
- **Featured / share image:** Set the `image` field in the post’s front matter (e.g. in the CMS “Featured Image” or in the YAML as `image: /images/uploads/hero.jpg`). That image is used for `og:image` and `twitter:image` when sharing the post, and is resized to 1200×630 for social cards.

## Change the School Sheets or Map links

Edit `config/_default/hugo.toml`. Under `[params]` you’ll see:

- `nav_school_sheets` — URL for the “School Sheets” link in the main nav (default: `/school-sheets/`)
- `nav_map` — URL for the “Map” link in the main nav (default: `/map/`)

Update these values and rebuild. They’re used in the site header navigation.

## Editing content (Pages CMS)

Content and media are edited via **Pages CMS**. Sign in with GitHub at [https://app.pagescms.org/](https://app.pagescms.org/), open this repository and branch, and use the configured collections (Posts) and media (uploads). The post **Body** is a rich-text editor: you can format text (bold, italic, headings, lists, blockquotes, code), add links, and insert images from the media library. Type `/` in the body for slash commands. Configuration lives in `.pages.yml` at the repo root.

## Tech notes

- CSS lives in `assets/css/style.css` and is fingerprinted on build so cache updates when you change styles.
- Comments are powered by Isso; configure the Isso server URL in `layouts/partials/isso.html` (`data-isso` and `src` on the script tag).
