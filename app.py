from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import re

app = Flask(__name__)

TARGET_PATTERNS = [
    r'mediafire\.com/(?:file|download)/', r'drive\.google\.com/file/d/', 
    r'mega\.nz/(?:file|folder)/', r'dropbox\.com/s/', 
    r'sfile\.(?:mobi|co)/[a-zA-Z0-9_-]{4,}', r'\.(?:zip|rar|apk)(?:\?.*)?$'
]
AD_DOMAINS = ["popads.net", "adsterra.com", "doubleclick.net", "propellerads.com", "google-analytics.com", "googlesyndication.com", "histats.com"]

def run_bypass(safelink_url):
    final_target_url = None
    with sync_playwright() as p:
        # headless=True wajib karena ini jalan di server (tanpa layar)
        browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled', '--no-sandbox'])
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()
        
        opened_pages = []
        context.on("page", lambda new_page: opened_pages.append(new_page))

        def intercept_route(route):
            if any(ad in route.request.url for ad in AD_DOMAINS): route.abort()
            else: route.continue_()
        page.route("**/*", intercept_route)

        page.add_init_script("""
            window.__shared_urls = [];
            navigator.share = async function(data) { if (data && data.url) window.__shared_urls.push(data.url); return true; };
            const originalWindowOpen = window.open;
            window.open = function(url, target, features) { if(url) window.__shared_urls.push(url); return null; };
            const originalSetTimeout = window.setTimeout;
            window.setTimeout = function(cb, ms) { return originalSetTimeout(cb, ms > 1000 ? 10 : ms); };
            const originalSetInterval = window.setInterval;
            window.setInterval = function(cb, ms) { return originalSetInterval(cb, ms > 1000 ? 10 : ms); };
        """)

        try:
            page.goto(safelink_url, wait_until="domcontentloaded", timeout=30000)
        except:
            pass

        selectors_to_click = [
            'button:has-text("Aku bukan robot")', 'img[alt="Aku bukan robot"]', '#btn-st',
            'button:has-text("Get Link")', 'a:has-text("Get Link")',
            'button:has-text("Go to file")', 'a:has-text("Go to file")',
            'button:has-text("Go to Link")', 'a:has-text("Go to Link")',
            'button:text-is("Open")', 'a:text-is("Open")',
            'button:text-is("Next")', 'a:text-is("Next")',
            'button:text-is("Continue")', 'a:text-is("Continue")'
        ]

        for i in range(40):
            if final_target_url or page.is_closed(): break
            
            try:
                if any(re.search(pat, page.url, re.IGNORECASE) for pat in TARGET_PATTERNS):
                    if not re.search(r'sfile\.(?:mobi|co)/(?:login|register|contact|tos|page)', page.url, re.IGNORECASE):
                        final_target_url = page.url
                        break
            except: pass

            try:
                shared = page.evaluate("window.__shared_urls")
                if shared:
                    for s in shared:
                        if any(re.search(pat, s, re.IGNORECASE) for pat in TARGET_PATTERNS):
                            final_target_url = s
                            break
            except: pass
            if final_target_url: break

            for p in opened_pages.copy():
                try:
                    if not p.is_closed():
                        url = p.url
                        if any(re.search(pat, url, re.IGNORECASE) for pat in TARGET_PATTERNS):
                            final_target_url = url
                            break
                        else:
                            p.close()
                            opened_pages.remove(p)
                    else:
                        opened_pages.remove(p)
                except: pass
            if final_target_url: break

            clicked = False
            for sel in selectors_to_click:
                try:
                    if page.is_closed(): break
                    elements = page.locator(sel)
                    if elements.count() > 0:
                        for idx in range(elements.count()):
                            el = elements.nth(idx)
                            if el.is_visible():
                                el.scroll_into_view_if_needed()
                                page.mouse.wheel(0, 100)
                                page.mouse.wheel(0, -100)
                                el.evaluate("node => node.click()") 
                                clicked = True
                                try: page.wait_for_timeout(2000) 
                                except: pass
                                break
                except: continue
                if clicked: break

            try:
                if not page.is_closed(): page.wait_for_timeout(2000)
            except: break

        try: browser.close()
        except: pass
        return final_target_url

@app.route('/api/bypass', methods=['GET'])
def api_bypass():
    url = request.args.get('url')
    if not url:
        return jsonify({"status": False, "message": "Parameter URL tidak ditemukan"}), 400
    
    result = run_bypass(url)
    if result:
        return jsonify({"status": True, "result": result})
    else:
        return jsonify({"status": False, "message": "Gagal menemukan URL asli"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
