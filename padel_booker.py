import os
import sys
import json
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

UCPA_URL = "https://www.ucpa.com/sport-station/paris-19/mon-terrain-padel"
LOGIN_URL = "https://www.ucpa.com/af/sso/login?context=alpha"
UCPA_EMAIL = os.environ.get("UCPA_EMAIL", "")
UCPA_PASSWORD = os.environ.get("UCPA_PASSWORD", "")
PARTICIPANT = "Guillaume Fourcade"
PREFERRED_COURT = "7"

DAY_NAMES_FR = {
    "Lundi": "Monday", "Mardi": "Tuesday",
    "Mercredi": "Wednesday", "Jeudi": "Thursday"
}
MONTHS_EN = {
    1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",
    7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"
}

def log(msg):
    print(f"[UCPA] {msg}", flush=True)

def next_week_date(day_fr):
    today = datetime.today()
    days_until_monday = (7 - today.weekday()) % 7 or 7
    next_monday = today + timedelta(days=days_until_monday)
    offset = ["Lundi","Mardi","Mercredi","Jeudi"].index(day_fr)
    return next_monday + timedelta(days=offset)

def run(wellpass_code, chosen_day):
    target_date = next_week_date(chosen_day)
    day_en = DAY_NAMES_FR[chosen_day]
    month_en = MONTHS_EN[target_date.month]
    aria_label = f"{day_en}, {month_en} {target_date.day}, {target_date.year}"
    log(f"Cible: {chosen_day} {target_date.strftime('%d/%m/%Y')} → aria='{aria_label}'")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()

        # ── 1. Charger la page + accepter cookies ─────────────────────
        log("Chargement page UCPA...")
        page.goto(UCPA_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        try:
            page.locator("button:has-text('ACCEPTER')").first.click()
            page.wait_for_timeout(1000)
            log("Cookies acceptés.")
        except:
            pass

        # ── 2. Login ──────────────────────────────────────────────────
        log("Login...")
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        try:
            page.locator("button:has-text('ACCEPTER')").first.click()
            page.wait_for_timeout(500)
        except:
            pass
        page.locator("input[id='email']").fill(UCPA_EMAIL)
        page.locator("input[type='password']").fill(UCPA_PASSWORD)
        page.locator("button[type='submit']").click()
        page.wait_for_load_state("domcontentloaded", timeout=20000)
        page.wait_for_timeout(3000)
        log(f"URL après login: {page.url}")

        # ── 3. Retour page padel ──────────────────────────────────────
        page.goto(UCPA_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(4000)
        # Accepter cookies si réapparus
        try:
            page.locator("button:has-text('ACCEPTER')").first.click()
            page.wait_for_timeout(500)
        except:
            pass
        page.screenshot(path="/tmp/ucpa_01_padel.png")

        # ── 4. Cliquer sur la date dans le calendrier ─────────────────
        log(f"Clic sur date: {aria_label}")
        date_btn = page.locator(f"button[aria-label='{aria_label}']")
        if date_btn.count() == 0:
            log("❌ Date non trouvée dans le calendrier !")
            page.screenshot(path="/tmp/ucpa_confirmation.png")
            browser.close()
            return {"success": False, "message": f"Date {chosen_day} non disponible dans le calendrier."}

        date_btn.first.click()
        page.wait_for_timeout(3000)
        page.screenshot(path="/tmp/ucpa_02_after_date.png")
        log("Date cliquée.")

        # ── 5. Chercher les boutons RÉSERVER pour 7h ──────────────────
        log("Recherche créneaux 7h...")
        reserver_links = page.locator("a:has-text('RÉSERVER')").all()
        log(f"Boutons RÉSERVER trouvés: {len(reserver_links)}")

        # Dump contexte de chaque bouton RÉSERVER
        target_btn = None
        for i, lnk in enumerate(reserver_links):
            try:
                # Remonter pour trouver l'heure
                parent_text = lnk.locator("xpath=ancestor::li[1]").inner_text()
                log(f"  RÉSERVER[{i}]: {parent_text[:100]}")
                if "07:00" in parent_text or "7:00" in parent_text or "07h" in parent_text:
                    if target_btn is None:
                        target_btn = lnk
                        log(f"  → Créneau 7h trouvé !")
                    # Vérifier si terrain 7
                    if f"terrain {PREFERRED_COURT}" in parent_text.lower() or f"court {PREFERRED_COURT}" in parent_text.lower():
                        target_btn = lnk
                        log(f"  → Terrain {PREFERRED_COURT} sélectionné !")
            except Exception as e:
                log(f"  Erreur btn[{i}]: {e}")

        if target_btn is None:
            log("❌ Pas de créneau 7h trouvé.")
            page.screenshot(path="/tmp/ucpa_confirmation.png")
            browser.close()
            return {"success": False, "message": f"Pas de créneau 7h disponible le {chosen_day}."}

        # ── 6. Cliquer sur RÉSERVER ───────────────────────────────────
        log("Clic sur RÉSERVER...")
        target_btn.click()
        page.wait_for_load_state("domcontentloaded", timeout=20000)
        page.wait_for_timeout(3000)
        page.screenshot(path="/tmp/ucpa_03_reservation.png")
        log(f"URL après RÉSERVER: {page.url}")

        # ── 7. Renseigner participant si nécessaire ───────────────────
        try:
            participant_input = page.locator("input[placeholder*='participant'], input[placeholder*='nom'], input[name*='participant']").first
            if participant_input.count() > 0:
                participant_input.fill(PARTICIPANT)
                log(f"Participant renseigné: {PARTICIPANT}")
        except:
            pass

        # ── 8. Sélectionner tarif Wellpass ────────────────────────────
        log("Recherche option Wellpass...")
        try:
            wellpass_opt = page.locator("text=Wellpass, text=wellpass, text=egym").first
            if wellpass_opt.count() > 0:
                wellpass_opt.click()
                page.wait_for_timeout(1000)
                log("Option Wellpass cliquée.")
        except:
            pass

        # ── 9. Saisir le code Wellpass ────────────────────────────────
        log("Saisie code Wellpass...")
        try:
            code_input = page.locator("input[placeholder*='ode'], input[name*='code'], input[name*='voucher']").first
            if code_input.count() > 0:
                code_input.fill(wellpass_code)
                log(f"Code saisi.")
        except:
            pass

        page.screenshot(path="/tmp/ucpa_04_payment.png")

        # ── 10. Confirmer ─────────────────────────────────────────────
        log("Confirmation...")
        try:
            confirm_btn = page.locator("button:has-text('Confirmer'), button:has-text('Valider'), button:has-text('Payer')").first
            if confirm_btn.count() > 0:
                confirm_btn.click()
                page.wait_for_load_state("domcontentloaded", timeout=20000)
                page.wait_for_timeout(3000)
                log("Confirmation cliquée.")
        except:
            pass

        page.screenshot(path="/tmp/ucpa_confirmation.png")
        body = page.inner_text("body")
        log(f"URL finale: {page.url}")
        log(f"Body (500 chars): {body[:500]}")

        if any(w in body.lower() for w in ["confirmation", "confirmé", "merci", "réservation validée"]):
            log("✅ RÉSERVATION CONFIRMÉE !")
            result = {"success": True, "message": f"Réservation confirmée : {chosen_day} 7h00-8h00 !"}
        else:
            log("⚠️ Statut incertain - vérifier screenshot")
            result = {"success": False, "message": "Statut incertain - vérifiez sur ucpa.com"}

        browser.close()
        return result

if __name__ == "__main__":
    chosen_day = sys.argv[1] if len(sys.argv) > 1 else "Lundi"
    wellpass_code = sys.argv[2] if len(sys.argv) > 2 else "test"
    result = run(wellpass_code=wellpass_code, chosen_day=chosen_day)
    print(json.dumps(result, ensure_ascii=False, indent=2))
