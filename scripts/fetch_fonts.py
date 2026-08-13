"""
Vendor Inter + JetBrains Mono from Google Fonts into static/vendor/.

The deployment is a Parliament intranet box with no reliable outbound internet,
so every page must serve its own fonts. Run this only when a new weight is
needed; the downloaded files are committed.

    docker compose exec web python scripts/fetch_fonts.py
"""

import pathlib
import re
import urllib.request

BASE = pathlib.Path(__file__).resolve().parent.parent
OUT = BASE / "static" / "vendor" / "fonts"

# Google Fonts serves woff2 only to browsers that advertise support.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# Both families are variable fonts, so one file covers the whole weight range —
# asking for discrete weights just downloads the same file five times over.
CSS_URL = (
    "https://fonts.googleapis.com/css2"
    "?family=Inter:wght@100..900"
    "&family=JetBrains+Mono:wght@100..800"
    "&display=swap"
)

# The UI is English-only; skipping cyrillic/greek/vietnamese keeps the payload small.
SUBSETS = ("latin", "latin-ext")


def get(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60
    ).read()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    css = get(CSS_URL).decode("utf-8")

    # Each face is preceded by a /* subset */ comment naming its unicode-range.
    blocks = re.findall(r"/\*\s*([\w\-\[\]]+)\s*\*/\s*(@font-face\s*\{[^}]*\})", css)
    rules = []
    for subset, block in blocks:
        if subset not in SUBSETS:
            continue
        url = re.search(r"url\((https://[^)]+\.woff2)\)", block)
        family = re.search(r"font-family:\s*'([^']+)'", block)
        if not (url and family):
            continue

        name = f"{family.group(1).replace(' ', '')}-{subset}.woff2"
        dest = OUT / name
        if not dest.exists():
            data = get(url.group(1))
            dest.write_bytes(data)
            print(f"  {name}  {len(data):,} bytes")
        rules.append(block.replace(url.group(1), f"fonts/{name}"))

    header = (
        "/* Self-hosted Inter + JetBrains Mono (latin, latin-ext subsets).\n"
        "   Vendored from Google Fonts so no page blocks on an outbound request\n"
        "   the intranet cannot make. Regenerate with scripts/fetch_fonts.py. */\n\n"
    )
    (OUT.parent / "fonts.css").write_text(header + "\n".join(rules) + "\n", encoding="utf-8")
    print(f"\n{len(rules)} @font-face rules -> static/vendor/fonts.css")


if __name__ == "__main__":
    main()
