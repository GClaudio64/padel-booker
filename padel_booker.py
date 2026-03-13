import os
import sys
import json
from playwright.sync_api import sync_playwright

UCPA_URL = "https://www.ucpa.com/sport-station/paris-19/mon-terrain-padel"
LOGIN_URL = "https://www.ucpa.com/af/sso/login?context=alpha"
UCPA_EMAIL = os.environ.get("UCPA_EMAIL", "")
UCPA_PASSWORD = os.environ.get("UCPA_PASSWORD", "")

def log(msg):
    print(f"[UCPA] {msg}", flush=True)

def run(wellpass_code, chosen_day):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()

        log("Chargement page UCPA...")
        page.goto(UCPA_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        page.screenshot(path="/tmp/ucpa_confirmation.png")
        log("Screenshot initial pris.")

        # Dump HTML pour analyser la structure de login
        html = page.content()
        log("=== HTML (premiers 2000 chars) ===")
        log(html[:2000])

        # Chercher tous les inputs
        inputs = page.locator("input").all()
        log(f"=== {len(inputs)} INPUT(S) TROUVÉS ===")
        for i, inp in enumerate(inputs):
            try:
                t = inp.get_attribute("type") or "?"
                n = inp.get_attribute("name") or "?"
                p2 = inp.get_attribute("placeholder") or "?"
                log(f"  input[{i}] type={t} name={n} placeholder={p2}")
            except:
                pass

        # Chercher liens de login
        links = page.locator("a").all()
        log(f"=== LIENS ===")
        for lnk in links[:20]:
            try:
                log(f"  {lnk.inner_text().strip()} -> {lnk.get_attribute('href')}")
            except:
                pass

        browser.close()
        return {"success": False, "message": "Analyse - voir logs"}

if __name__ == "__main__":
    chosen_day = sys.argv[1] if len(sys.argv) > 1 else "Lundi"
    wellpass_code = sys.argv[2] if len(sys.argv) > 2 else "test"
    result = run(wellpass_code=wellpass_code, chosen_day=chosen_day)
    print(json.dumps(result, ensure_ascii=False, indent=2))
