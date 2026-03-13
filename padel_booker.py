import os
import sys
import json
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
        page = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()

        log("Chargement page UCPA...")
        page.goto(UCPA_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        page.screenshot(path="/tmp/ucpa_01_initial.png")

        log("Gestion des cookies...")
        try:
            accept_btn = page.locator("button:has-text('ACCEPTER'), button:has-text('Accepter'), button:has-text('Tout accepter')").first
            if accept_btn.count() > 0:
                accept_btn.click()
                page.wait_for_timeout(2000)
                log("Cookies acceptés.")
        except Exception as e:
            log(f"Pas de popup cookies: {e}")
        page.screenshot(path="/tmp/ucpa_02_after_cookies.png")

        log("Connexion au compte UCPA...")
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        page.screenshot(path="/tmp/ucpa_03_login_page.png")

        inputs = page.locator("input").all()
        log(f"Inputs sur page login: {len(inputs)}")
        for i, inp in enumerate(inputs):
            try:
                log(f"  [{i}] type={inp.get_attribute('type')} name={inp.get_attribute('name')} id={inp.get_attribute('id')} placeholder={inp.get_attribute('placeholder')}")
            except:
                pass

        try:
            email_selectors = [
                "input[type='email']",
                "input[name='email']",
                "input[name='username']",
                "input[name='login']",
                "input[id='email']",
                "input[placeholder*='mail']",
                "input[placeholder*='identifiant']",
            ]
            email_filled = False
            for sel in email_selectors:
                if page.locator(sel).count() > 0:
                    page.locator(sel).first.fill(UCPA_EMAIL)
                    log(f"Email rempli avec sélecteur: {sel}")
                    email_filled = True
                    break

            password_selectors = [
                "input[type='password']",
                "input[name='password']",
                "input[name='passwd']",
                "input[id='password']",
            ]
            password_filled = False
            for sel in password_selectors:
                if page.locator(sel).count() > 0:
                    page.locator(sel).first.fill(UCPA_PASSWORD)
                    log(f"Password rempli avec sélecteur: {sel}")
                    password_filled = True
                    break

            if email_filled and password_filled:
                page.screenshot(path="/tmp/ucpa_04_login_filled.png")
                submit_selectors = [
                    "button[type='submit']",
                    "input[type='submit']",
                    "button:has-text('Connexion')",
                    "button:has-text('Se connecter')",
                    "button:has-text('Valider')",
                ]
                for sel in submit_selectors:
                    if page.locator(sel).count() > 0:
                        page.locator(sel).first.click()
                        log(f"Submit cliqué: {sel}")
                        break
                page.wait_for_load_state("domcontentloaded", timeout=20000)
                page.wait_for_timeout(3000)
                log("Connexion soumise.")
            else:
                log(f"ERREUR: email_filled={email_filled}, password_filled={password_filled}")

        except Exception as e:
            log(f"Erreur login: {e}")

        page.screenshot(path="/tmp/ucpa_confirmation.png")
        log("Screenshot après login pris.")

        page.goto(UCPA_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(4000)
        page.screenshot(path="/tmp/ucpa_05_padel_loggedin.png")

        body_text = page.inner_text("body")
        if "Déconnexion" in body_text or "Mon Compte" in body_text:
            log("✅ Connecté avec succès !")
        else:
            log("⚠️ Pas connecté - vérifier les credentials")

        log("Navigation semaine suivante...")
        try:
            next_selectors = [
                "button.arrow--right",
                "button.arrow-next",
                "[class*='planner'] button:last-child",
                "button[aria-label*='suivant']",
                "button[aria-label*='next']",
                ".planning__nav button:last-child",
            ]
            clicked = False
            for sel in next_selectors:
                if page.locator(sel).count() > 0:
                    page.locator(sel).first.click()
                    log(f"Flèche cliquée: {sel}")
                    clicked = True
                    break

            if not clicked:
                buttons = page.locator("button").all()
                log(f"Boutons disponibles: {len(buttons)}")
                for i, btn in enumerate(buttons[:20]):
                    try:
                        log(f"  btn[{i}] text='{btn.inner_text().strip()[:50]}' class='{btn.get_attribute('class')}'")
                    except:
                        pass

            page.wait_for_timeout(3000)
            page.screenshot(path="/tmp/ucpa_06_next_week.png")
        except Exception as e:
            log(f"Erreur navigation: {e}")

        log("Analyse des créneaux 7h...")
        body_text = page.inner_text("body")
        reserver_btns = page.locator("a:has-text('RÉSERVER'), button:has-text('RÉSERVER'), a:has-text('Réserver')").all()
        log(f"Boutons RÉSERVER trouvés: {len(reserver_btns)}")

        log("=== EXTRAIT DU PLANNING ===")
        planning = page.locator("[class*='planner'], [class*='planning'], [class*='schedule'], [class*='calendar']").first
        if planning.count() > 0:
            log(planning.inner_text()[:2000])
        else:
            log("Planning non trouvé - dump body partiel:")
            log(body_text[2000:5000])

        browser.close()
        return {"success": False, "message": "Analyse étape 2 - voir logs et screenshots"}

if __name__ == "__main__":
    chosen_day = sys.argv[1] if len(sys.argv) > 1 else "Lundi"
    wellpass_code = sys.argv[2] if len(sys.argv) > 2 else "test"
    result = run(wellpass_code=wellpass_code, chosen_day=chosen_day)
    print(json.dumps(result, ensure_ascii=False, indent=2))
