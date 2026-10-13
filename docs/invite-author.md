# Invite a new author

Every new writer gets their own section, the same shape as **Jeremy On Tap** or **Da Breakdown w Tad**. They do not write in **Posts**. Nothing they save is public until **Draft** is unchecked. They do not need GitHub, Cloudflare, or the repo.

## Steps

1. **Author stub**, merged before they sign in. **Authors** → New: Name, Slug (`firstname-lastname`), a one-line placeholder bio, **Draft on**. Leave the slug alone. The stub is so they can pick themselves under Authors. `/authors/<slug>/` stays unpublished, so do not send that URL yet.
2. **Collaborators invite**, in the [Pages CMS](https://app.pagescms.org/) web UI (you sign in with GitHub). **Collaborators** → invite their email. A magic-link invite goes to their inbox.
3. **Welcome email** below. Fill in `[NAME]`, `[EMAIL]`, and `[COMMENTS PASSWORD]`. The comments password is Cloudflare `COMMENTS_ADMIN_SECRET`. Do not commit it.
4. They reply with a section name. You (with your assistant) build that section like Jeremy On Tap / Da Breakdown w Tad: a content folder, a Pages CMS collection, a permalink, and **one nav entry**. The nav list is `layouts/partials/nav-menu.html` — add one dict with `label`, `href` (trailing slash, same path as the folder), `section` (the content folder name), and `gated` true. `gated` keeps the tab off until the first post in that folder is published. Bold on the current tab and scrolling that tab into view apply to every entry there. Do not add a per-section check in `header.html`. Merge it, then send the **section ready** email below.
5. **Go live** later. **Authors** → their profile → uncheck **Draft** → Save, before any post, or bylines will not resolve. Then undraft the posts that should go live, or they do that from the welcome email.

They can edit every collection. That is trust, not a permission system. The email tells them to wait for their section and not use Posts. On a shared post, pick every writer under **Authors** and add a **Who wrote what** block per person.

Christian Pudlo (`cpudlo@outlook.com`) already writes in Grady’s Tour. That is the old exception. New writers do not join someone else’s section.

Phone photos that are too big for the CMS still go through [add-photos](https://ericwisnewski.com/add-photos/) (`UPLOAD_SECRET`). The welcome email does not include that password.

## Welcome email (copy and paste)

Subject: Welcome, [NAME] to ericwisnewski.com

```
Hi [NAME],

Welcome to ericwisnewski.com as a writer. I'm very excited Eric has brought you on the site.

Please follow the steps below in order and save this email for your reference.

STEP 1 (do this now): Reply with your section name
    You'll get your own section on the site. Reply to this email with what you'd like it called. (For reference, Tad's is "Da Breakdown w Tad" and Jeremy's is "Jeremy On Tap.")

STEP 2 (do this now): Sign in and set up your profile
    Sign in at https://app.pagescms.org/
    Use this email address ([EMAIL]) and choose "Continue with email." You'll get a sign-in link in your inbox. No password and no GitHub needed. Please don't sign in with GitHub, or saving won't work.
    Then open Authors, click your name, write a short Bio, and add a Photo. Leave Draft checked.

Please don't write any posts yet, not even drafts, and don't use the Posts section. Wait for my next email.

STEP 3 (after I email you that your section is ready): Write a post
    Your section will show up in the left menu of Pages CMS under the name you picked. Open it, then New. Pick yourself under Authors, add a title, a slug (lowercase-with-hyphens), a date, and the body. Leave Draft checked and hit Save. You can make as many drafts as you want.

STEP 4: Publish
    When you're ready to publish a post, uncheck Draft and Save. Don't uncheck it before then.

Managing comments
    You also have access to remove/edit comments from people.
    Go here to see comments on posts: https://ericwisnewski.com/admin/comments/
    Use this password to access comments: [COMMENTS PASSWORD]

If something breaks, email me and I will fix ASAP.

Welcome,
Tyler
```

## Section ready (copy and paste)

Send this after the section is merged. Fill in `[NAME]`, `[EMAIL]`, and `[SECTION NAME]`.

Subject: Your section is ready

```
Hi [NAME],

Your section is ready. It’s called [SECTION NAME].

Sign in at https://app.pagescms.org/ with [EMAIL] and choose "Continue with email." Don’t sign in with GitHub.

Open [SECTION NAME] in the left menu, then New. Pick yourself under Authors. Add a title, a slug (lowercase-with-hyphens), a date, and the body. Leave Draft checked and hit Save.

Don’t use the Posts section. Don’t uncheck Draft until you want the post public.

If something breaks, email me.

Tyler
```

## If they can’t save

A writer who signs into Pages CMS with GitHub instead of the email link can open the CMS but can’t save. Sign out, then use **Continue with email** on the invited address.
