"""Read-only inspection: prints control structure, never input values."""
import json
from playwright.sync_api import sync_playwright
from backend import URL

with sync_playwright() as pw:
    browser = None
    for channel in ('chrome', 'msedge'):
        try:
            browser = pw.chromium.launch(channel=channel, headless=False)
            break
        except Exception:
            pass
    if browser is None:
        print('BROWSER_UNAVAILABLE')
    else:
        try:
            page = browser.new_page()
            page.goto(URL, wait_until='domcontentloaded', timeout=30000)
            for frame in page.frames:
                print(json.dumps(frame.locator('input, button, iframe').evaluate_all('''nodes => nodes.map(n => ({
                    tag: n.tagName, type: n.getAttribute('type'), id: n.id,
                    name: n.getAttribute('name'), placeholder: n.getAttribute('placeholder'),
                    label: n.getAttribute('aria-label')
                }))'''), ensure_ascii=True))
        except Exception:
            print('INSPECTION_FAILED')
        finally:
            browser.close()
