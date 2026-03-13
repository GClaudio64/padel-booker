import os
import sys
import json
from playwright.sync_api import sync_playwright

UCPA_URL = "https://www.ucpa.com/sport-station/paris-19/mon-terrain-padel"
LOGIN_URL = "https://www.ucpa.com/af/sso/login?context=alpha&redirect=https://www.ucpa.com/sport-station/paris-19/mon-terrain-padel"
UCPA_EMAIL = os.environ.get("UCPA_EMAIL", "")
UCPA_PASSWORD = os.environ.get("UCPA_PASSWORD", "")
TARGET_DAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi"]
PREFERRED_COURT = "7"

def log(msg):
    print(f"[UCPA] {msg}", flush=True)

def run(wellpass_code, chosen_day):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()

        # ── 1. Cookies ────────────────────────────────────────────────
        log("Chargement page UCPA...")
        page.goto(UCPA_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        try:
            btn = page.locator("button:has-text('ACCEPTER')").first
            if btn.count() > 0:
                btn.click()
                page.wait_for_timeout(1000)
                log("Cookies acceptés.")
        except:
            pass

        # ── 2. Login avec redirect direct vers la page padel ──────────
        log("Login...")
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        page.locator("input[id='email']").fill(UCPA_EMAIL)
        page.locator("input[type='password']").fill(UCPA_PASSWORD)
        page.screenshot(path="/tmp/ucpa_01_before_submit.png")
        page.locator("button[type='submit']").click()
        page.wait_for_load_state("domcontentloaded", timeout=20000)
        page.wait_for_timeout(4000)
        page.screenshot(path="/tmp/ucpa_02_after_login.png")

        current_url = page.url
        log(f"URL après login: {current_url}")

        # Si redirigé ailleurs, forcer la page padel
        if "mon-terrain-padel" not in current_url:
            log("Redirection vers page padel...")
            page.goto(UCPA_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(4000)

        page.screenshot(path="/tmp/ucpa_03_padel_page.png")

        body = page.inner_text("body")
        if "Déconnexion" in body or "espace" in body.lower():
            log("✅ Connecté !")
        else:
            log("⚠️ Connexion incertaine")

        # ── 3. Naviguer semaine suivante ──────────────────────────────
        log("Navigation semaine suivante...")
        # Lister TOUS les boutons pour trouver la flèche
        buttons = page.locator("button").all()
        log(f"Total boutons: {len(buttons)}")
        for i, btn in enumerate(buttons):
            try:
                txt = btn.inner_text().strip()
                cls = btn.get_attribute("class") or ""
                aria = btn.get_attribute("aria-label") or ""
                if txt or "arrow" in cls.lower() or "next" in cls.lower() or "suivant" in aria.lower() or "›" in txt or ">" in txt:
                    log(f"  btn[{i}] txt='{txt[:30]}' class='{cls[:50]}' aria='{aria}'")
            except:
                pass

        page.screenshot(path="/tmp/ucpa_confirmation.png")
        browser.close()
        return {"success": False, "message": "Analyse navigation - voir logs"}

if __name__ == "__main__":
    chosen_day = sys.argv[1] if len(sys.argv) > 1 else "Lundi"
    wellpass_code = sys.argv[2] if len(sys.argv) > 2 else "test"
    result = run(wellpass_code=wellpass_code, chosen_day=chosen_day)
    print(json.dumps(result, ensure_ascii=False, indent=2))
