# Invite a new author

They write in Pages CMS right away. Nothing they create is public until you uncheck **Draft**. No GitHub, no Cloudflare, no repo.

## Invite (now)

1. Get their **email** and **byline name**.
2. Open [Pages CMS](https://app.pagescms.org/) (GitHub sign-in). **Collaborators** → invite that email. A magic-link invite goes to their inbox.
3. **Authors** → New: Name, Slug (`firstname-lastname`), a one-line placeholder bio, **Draft on**. Leave the slug alone after this. The stub is so they can pick themselves as Author on posts; `/authors/<slug>/` stays unpublished.
4. Send the email below. Fill in `[NAME]` and the `/add-photos/` password. Do not send a live author URL yet — it 404s until you undraft them.

They can edit every collection (Posts, Grady’s Tour, Da Breakdown w Tad, Jer’s Prospect Profiles, Authors, Site updates). That is trust, not a permission system. The email tells them to write in **Posts** only — unless they are Tad (Da Breakdown w Tad) or Jeremy (Jer’s Prospect Profiles).

## Go live (later)

When you want them public (after any tab/UI work, or just on the main Posts list):

1. Do the site UI first (skip if they are staying on the home-page Posts list).
2. **Authors** → their profile → uncheck **Draft** → Save. Do this before any post, or bylines will not resolve.
3. Uncheck **Draft** on the posts that should go live and Save — or tell them to do that.

A dedicated nav tab per author (like Grady’s Tour) is separate work unless one already exists. Tad writes in **Da Breakdown w Tad**; Jeremy writes in **Jer’s Prospect Profiles**. Those nav tabs appear when the first post in that folder is undrafted and saved.

## Email (copy and paste)

Subject: You’re set up to write on Eric’s site

```
Hi [NAME],

You’re set up as a writer. You can start now. Nothing you save is public until we say so.

1. Sign in at https://app.pagescms.org/
   Use the same email this was sent to. You’ll get a sign-in link in your inbox — no password, no GitHub.

2. Add your bio and photo
   Open Authors, click your name, write a short Bio, add a Photo. Leave Draft checked.
   If the photo is from your phone, upload it at https://ericwisnewski.com/add-photos/ first (password: [ADD-PHOTOS PASSWORD]), wait until it says Saved, then pick it in the Photo field. Don’t upload big files in the CMS — that path fails.

3. Write a post
   Open Posts → New. Pick yourself as Author. Add a title, a slug (lowercase-with-hyphens), a date, and the body.
   Leave Draft checked. Hit Save. You can make as many drafts as you want.

When we’re ready to publish, we’ll tell you to uncheck Draft and Save. Don’t uncheck it before then. Don’t edit other people’s posts, Grady’s Tour, or Site updates.

If something breaks, email me.

Tyler
```

## Email for Jeremy (copy and paste)

Subject: You’re set up to write on Eric’s site

```
Hi Jeremy,

You’re set up as a writer. You can start now. Nothing you save is public until we say so.

1. Sign in at https://app.pagescms.org/
   Use jeremybryan123@gmail.com. You’ll get a sign-in link in your inbox — no password, no GitHub.

2. Add your bio and photo
   Open Authors, click Jeremy Bryan, write a short Bio, add a Photo. Leave Draft unchecked (your profile is already live so bylines work).
   If the photo is from your phone, upload it at https://ericwisnewski.com/add-photos/ first (password: [ADD-PHOTOS PASSWORD]), wait until it says Saved, then pick it in the Photo field. Don’t upload big files in the CMS — that path fails.

3. Write a post
   Open Jer’s Prospect Profiles → New. Pick yourself as Author. Add a title, a slug (lowercase-with-hyphens), a date, and the body.
   Leave Draft checked. Hit Save. You can make as many drafts as you want.
   Don’t write in Posts, Grady’s Tour, or Da Breakdown w Tad.

When you’re ready to publish, uncheck Draft and Save. That rebuilds the site and puts your tab plus the email checkbox on the live site. Don’t edit other people’s posts or Site updates.

If something breaks, email me.

Tyler
```
