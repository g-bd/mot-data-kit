# Publishing the page on the ministry site

Target: **https://mot-roundtbl.org.il/mot-metadata-kit/** — a real folder under `public_html/`, not a WordPress page.

The host force-redirects everything WordPress renders to `wp-login.php` for anonymous visitors. That gate is a PHP
plugin, so it only runs when WordPress handles the request; a real file in a real directory is served by Apache and
PHP never boots. `/sensor-sal/` and `/validation-viewer/` already work exactly this way.

Status (24/08/2026): the folder exists on the host and holds an empty `index.html`
(`curl -sIL …/mot-metadata-kit/index.html` → `200`, `Content-Type: text/html` **without** charset = Apache answered).

## Build the bundle

```bash
python site/build_site_bundle.py                 # → ../build/wp-upload/mot-metadata-kit/
python site/build_site_bundle.py --version 0.6.0 # a later release
```

```
.htaccess              3 directives + zip MIME + no-cache; LF endings, upload FIRST and alone
index.html             the Hebrew guide with two download buttons (relative links, slug-independent)
index_ascii.html       same page, every non-ASCII char as &#NNNN; — use only if RTL text garbles on paste
downloads/*.zip        the two release zips (~850 KB and ~89 KB — far below the host's ~8 MB upload cap)
```

## Upload order

1. `.htaccess` alone → load the URL. If the folder answers **500**, this host's `AllowOverride` excludes `Options`:
   delete the `Options -Indexes` line and re-upload. (File Manager hides dotfiles — enable "show hidden files".)
2. `index.html` — replaces the empty placeholder. **WP File Manager blocks drag-and-drop of `.html`** and fails
   silently: use **New File → `index.html` → Edit → paste → Save**, or upload over FTP/cPanel where no filter exists.
3. `downloads/` with both zips — ordinary binary uploads. Never upload a zip-of-zips and extract: the host's
   extractor writes entries without `mkdir -p`, so nested paths fail silently.

## Verify anonymously (never while logged into WordPress)

```bash
curl -sIL https://mot-roundtbl.org.il/mot-metadata-kit/
# want: 200 OK, Content-Type: text/html  with NO charset   → Apache served it, PHP never ran
curl -sIL https://mot-roundtbl.org.il/mot-metadata-kit/downloads/mot-metadata-kit-v0.5.0.zip
# want: 200, application/zip, sane Content-Length
```

`Location: …wp-login.php`, or `charset=UTF-8` on a 200, means WordPress answered — the folder is gone or the file
was never written. Then open the page in a private window.

## Each new version

Rebuild the bundle and replace `index.html` + the two zips. `.htaccess` stays. Claude Code users just run
`/plugin update mot-metadata-kit`.

Alternative now that the GitHub repo is public: keep only the page on the host and point the download buttons at
`https://github.com/g-bd/mot-metadata-kit/releases/latest` — nothing to re-upload per version, at the cost of depending
on GitHub.
