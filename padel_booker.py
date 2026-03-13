import os
import sys
import json
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

UCPA_URL = "https://www.ucpa.com/sport-station/paris-19/mon-terrain-padel"
LOGIN_URL = "https://www.ucpa.com/af/sso/login?context=alpha"
UCPA_EMAIL = os.environ.get("UCPA_EMAIL", "")
UCPA_PASSWORD = os.environ.get("UCPA_PASSWORD", "")
PARTICIPANT_FIRST = "Guillaume"
PARTICIPANT_LAST = "Fourcade"
TARGET_DAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi"]
TARGET_TIME = "07:00"
PREFERRED_COURT = "7"

def log(msg):
    print(f"[UCPA] {msg}", flush=True)

def run(wellpass_code, chosen_day):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context().new_page()

        log("Chargement de la page UCPA...")
        page.goto(UCPA_URL, wait_until="networkidle", timeout=30000)

        if page.locator("a:has-text('Login'), a:has-text('Se connecter')").count() > 0:
            log("Connexion en cours...")
            page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
            page.fill("input[type='email']", UCPA_EMAIL)
            page.fill("input[type='password']", UCPA_PASSWORD)
            page.click("button[type='submit']")
            page.wait_for_load_state("networkidle", timeout=20000)
            page.goto(UCPA_URL, wait_until="networkidle", timeout=30000)
            log("Connecte.")

        # Screenshot page initiale
        page.screenshot(path="/tmp/ucpa_01_initial.png")

        log("Navigation vers la semaine suivante...")
        try:
            next_btn = page.locator("button:has-text('›'), button:has-text('>'), [class*='next'], [aria-label*='suivant']").first
            next_btn.click()
            page.wait_for_timeout(3000)
        except Exception as e:
            log(f"Erreur navigation: {e}")

        page.screenshot(path="/tmp/ucpa_02_nextweek.png")
        log("Screenshot semaine suivante pris.")

        # Dump du contenu pour analyse
        content = page.inner_text("body")
        log("=== CONTENU PAGE ===")
        log(content[:3000])

        browser.close()
        return {"success": False, "message": "Analyse en cours - consultez les logs"}

if __name__ == "__main__":
    chosen_day = sys.argv[1] if len(sys.argv) > 1 else "Lundi"
    wellpass_code = sys.argv[2] if len(sys.argv) > 2 else "test"
    result = run(wellpass_code=wellpass_code, chosen_day=chosen_day)
    print(json.dumps(result, ensure_ascii=False, indent=2))
