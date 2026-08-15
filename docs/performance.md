# Performance

Rules and settings that keep the intranet deployment fast. Measured against a
2,119-asset database.

---

## 1. Never reference an external host from a template

This is the single biggest thing that can make the site feel broken. The
Parliament intranet has no dependable route to the public internet, so a
`<link>` to `fonts.googleapis.com` or a `<script src>` to `unpkg.com` does not
fail fast — it **hangs** until the browser's connection attempt times out.
A stylesheet in `<head>` is render-blocking, so the user stares at a blank page
for the duration, on every page load, no matter how fast the server responded.

Everything is vendored under `static/vendor/` instead:

| Asset | File |
|-------|------|
| Inter + JetBrains Mono | `vendor/fonts.css` + `vendor/fonts/*.woff2` |
| htmx 2.0.4 | `vendor/htmx-2.0.4.min.js` |
| Chart.js 4.4.0 | `vendor/chart-4.4.0.umd.min.js` |
| SortableJS 1.15.6 | `vendor/sortable-1.15.6.min.js` |

Both font families are variable fonts, so one `.woff2` per subset (latin,
latin-ext) covers every weight — 189 KB total. Regenerate with
`docker compose exec web python scripts/fetch_fonts.py`.

**When adding a library, download it into `static/vendor/` and reference it
with `{% static %}`. Never paste a CDN URL.** Strip any trailing
`//# sourceMappingURL=` comment: `ManifestStaticFilesStorage` treats the
missing `.map` as a hard error and `collectstatic` will fail the deploy.

## 2. Paginate every list view

`asset_list` rendered every asset in one page. At ~2.6 KB of HTML per row,
2,119 assets is a **5.2 MB** document; at the 5,000-asset target it is ~12 MB.
Paginated at 50/page it is 164 KB (≈30 KB gzipped).

Use `config.pagination.parse_per_page` / `strip_params` and render controls
with `{% include "partials/pagination.html" %}`, matching the reports app.
Page size lives in `?per_page=` (25/50/100) so links stay bookmarkable.

## 3. Per-request overhead

- **`CONN_MAX_AGE=600`** — without it every request pays a fresh TCP connect
  and auth handshake to Postgres before its first query. `CONN_HEALTH_CHECKS`
  discards connections the server closed.
- **Cached template loader** (production only) — templates are parsed once per
  worker instead of re-read from disk on every render.
- **`config.permissions._group_names`** — the role predicates are called
  repeatedly per request (access decorator, then `role_context` for template
  flags). Group names are memoised on the user instance, turning what was six
  queries into one. Any new predicate must go through this helper.
- **Sidebar alert badge** — cached in Redis, invalidated by the
  `InactiveHolderAlert` post_save/post_delete signal in `assignments/signals.py`.
- **Sessions** — `cached_db`: reads come from Redis, writes still persist to
  Postgres, so a Redis restart does not sign everybody out. This matters
  because `SESSION_SAVE_EVERY_REQUEST` is on for the 30-minute idle timeout.

Aggregate instead of looping counts — the dashboard uses one `GROUP BY status`
rather than seven `COUNT` round trips.

## 4. Serving

- **nginx gzip** is on for HTML/CSS/JS/JSON (~5x on HTML pages). woff2 is
  deliberately excluded: it is already compressed.
- **`ManifestStaticFilesStorage`** hashes static filenames, which is what makes
  the `expires 30d, immutable` header on `/static/` safe. Without it a deploy
  leaves browsers on month-old CSS. `config.storage` subclasses it with
  `manifest_strict = False` so one unreferenced file degrades that file's
  caching instead of 500-ing the whole page.
- **gunicorn `gthread`, 3 workers x 4 threads.** The old 3 sync workers meant
  only 3 requests could be in flight at once, so a single slow PDF or Excel
  export blocked a third of the site. Each thread holds its own persistent DB
  connection, so 12 slots = up to 12 Postgres connections.
- **Celery `--concurrency=2`.** Prefork otherwise forks one child per CPU core
  — on a 20-core host that is 20 idle Django processes holding ~1 GB, to run
  two scheduled tasks a day. Capping it took the worker from 1,071 MB to
  159 MB.

Idle footprint of the whole stack after these changes: **≈575 MB**
(web 228, celery 159, celery-beat 107, db 56, nginx 15, redis 9).

## 5. Redis databases

| DB | Use |
|----|-----|
| 0 | Celery broker (`REDIS_URL`) |
| 1 | Django cache + sessions (`CACHE_URL`) |

Keep them separate so a broker purge never wipes sessions.
