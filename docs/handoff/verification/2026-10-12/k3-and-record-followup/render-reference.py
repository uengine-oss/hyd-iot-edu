"""Render the preserved local comparison without HTTP, service changes, or writes to product data."""
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

from playwright.sync_api import sync_playwright

V = Path(__file__).resolve().parent
HTML = V/'reference-comparison.html'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ('src', 'href'):
            if key in attrs:
                link = attrs[key]
                split = urlsplit(link)
                assert not split.scheme and not split.netloc, link
                target = (V/unquote(split.path)).resolve()
                assert target.is_file(), target
                self.assets.append({'tag': tag, 'attribute': key, 'link': link,
                                    'resolved': str(target), 'exists': True, 'sha256': sha(target)})

links = Links()
links.feed(HTML.read_text(encoding='utf-8'))
errors, console, external = [], [], []
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: console.append({'type': m.type, 'text': m.text}))
    def route(r):
        if urlsplit(r.request.url).scheme in ('http', 'https'):
            external.append(r.request.url)
            r.abort()
        else:
            r.continue_()
    page.route('**/*', route)
    page.goto(HTML.as_uri(), wait_until='load')
    page.evaluate('document.fonts.ready')
    loaded = page.locator('img').evaluate_all('(imgs)=>imgs.map(i=>({src:i.getAttribute("src"),complete:i.complete,naturalWidth:i.naturalWidth,naturalHeight:i.naturalHeight}))')
    assert all(i['complete'] and i['naturalWidth'] > 0 for i in loaded), loaded
    assert not errors and not console and not external, (errors, console, external)
    page.screenshot(path=str(V/'reference-side-by-side.png'), full_page=True)
    dimensions = page.evaluate('({width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight})')
    browser.close()
data = {'created_utc': datetime.now(timezone.utc).isoformat(),
        'method': 'Local file Chromium render of preserved comparison and images. '
                  'No API/HTTP, new case execution, or user visual approval.',
        'html': {'file': HTML.name, 'sha256': sha(HTML)},
        'assets': links.assets, 'images_loaded': loaded,
        'viewport': {'width': 1920, 'height': 1080}, 'document': dimensions,
        'pageerrors': errors, 'console': console, 'external_requests': external,
        'screenshot': {'file': 'reference-side-by-side.png', 'sha256': sha(V/'reference-side-by-side.png')},
        'driver_sha256': sha(Path(__file__)), 'passed': True}
(V/'reference-render-metadata.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'passed': True, 'images': len(loaded), 'links': len(links.assets),
                  'console': len(console), 'pageerrors': len(errors), 'document': dimensions}, ensure_ascii=False))
