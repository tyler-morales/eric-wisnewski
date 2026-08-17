-- Relocate Grady's Tour comment keys from /posts/gradys-tour/<slug>/ to /gradys-tour/<slug>/.
-- Safe to re-run: rows already on the live prefix are unchanged.
UPDATE comments
SET url = rtrim('/gradys-tour/' || substr(url, length('/posts/gradys-tour/') + 1), '/') || '/'
WHERE url LIKE '/posts/gradys-tour/%';

UPDATE comments
SET url = '/gradys-tour/how-to-use-this-blog/'
WHERE url IN ('/posts/gradys-how-to-use-this-blog', '/posts/gradys-how-to-use-this-blog/');
