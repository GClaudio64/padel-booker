"""
padel_booker.py — Réservation automatique padel UCPA Paris 19e
==============================================================
Stratégie :
  1. Playwright (headless) pour le login UCPA → récupère les cookies de session
  2. requests Python pour tout le reste (API directe, robuste, sans DOM)

Usage : python padel_booker.py <Lundi|Mardi|Mercredi|Jeudi> <code_wellpass>
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta, timezone

import requests
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[UCPA] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("ucpa")

# ── Constantes (extraites du HAR, vérifiées) ───────────────────────────────────
WORKSPACE       = "alpha_hp"
BASE_URL        = "https://www.ucpa.com"
LOGIN_URL       = f"{BASE_URL}/af/sso/login?context=alpha"
PADEL_URL       = f"{BASE_URL}/sport-station/paris-19/mon-terrain-padel"
ESPACE_UUID     = "area_1639603579_a4ec61b0-5ded-11ec-aab6-45fce5b83b3e"
PRODUCT_UUID    = "product_1645613721_18d0c370-9497-11ec-a0dd-5f16fbdc0051"
HORANET_PRODUCT_CODE      = 700149552
HORANET_PRODUCT_REFERENCE = "01Y"
HORANET_PRODUCT_NAME      = "Terrain Padel Heures Creuses"

# Tarifs
TARIFF_WELLPASS = {
    "codeTariff": "488598973",
    "tariffCategoryCode": "487188051",
    "category": "Tarif EGYM Wellpass",
    "label": "Tarif EGYM Wellpass",
    "price": 5000,
    "negotiatedPrice": 45,
    "isGymlibTariff": True,
    "tva": 20,
}
TARIFF_PLEIN = {
    "codeTariff": "103154236",
    "tariffCategoryCode": "700149531",
    "negotiatedPrice": 45,
    "isGymlibTariff": False,
}

# Terrains (6 = fallback si 7 non dispo)
TERRAINS = {
    "7": {
        "codeActivite": 103423206,
        "codeCreneau": "461646364",
        "activity_uuid": "activity_1649421162_fc758fd0-b737-11ec-be09-672c744c9338",
        "activity_name": "Terrain 7 HC",
        "activity_code": "103423206",
        "nom_session": "Terrain 7 Padel HC",
    },
    "6": {
        "codeActivite": 103423129,
        "codeCreneau": "461643140",
        "activity_uuid": "activity_1649421034_afdb6c80-b737-11ec-af7d-0544f2ab95a5",
        "activity_name": "Terrain 6 HC",
        "activity_code": "103423129",
        "nom_session": "Terrain 6 Padel HC",
    },
}
PREFERRED_TERRAIN = "7"

# Jours cibles
DAY_OFFSET = {"Lundi": 0, "Mardi": 1, "Mercredi": 2, "Jeudi": 3}


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_target_date(chosen_day_fr: str) -> datetime:
    """Retourne la date de la SEMAINE SUIVANTE pour le jour donné."""
    today = datetime.now()
    days_to_monday = (7 - today.weekday()) % 7
    if days_to_monday == 0:
        days_to_monday = 7  # si on est lundi, aller au lundi d'après
    next_monday = today + timedelta(days=days_to_monday)
    return next_monday + timedelta(days=DAY_OFFSET[chosen_day_fr])


def ts_paris_ms(dt: datetime, hour: int, minute: int = 0) -> int:
    """
    Calcule le timestamp Unix en ms pour une date/heure en heure de Paris.
    Gère le passage à l'heure d'été (dernier dimanche de mars, 2h → 3h).
    En 2026 : 29 mars à 2h00.
    """
    dst_change = datetime(2026, 3, 29, 2, 0)
    dt_with_time = datetime(dt.year, dt.month, dt.day, hour, minute)
    utc_offset = 2 if dt_with_time >= dst_change else 1
    dt_utc = dt_with_time - timedelta(hours=utc_offset)
    return int(dt_utc.replace(tzinfo=timezone.utc).timestamp() * 1000)


def monday_of_week(dt: datetime) -> str:
    """Retourne le lundi de la semaine contenant dt, au format JJ-MM-AAAA."""
    monday = dt - timedelta(days=dt.weekday())
    return monday.strftime("%d-%m-%Y")


# ── Étape 1 : Login Playwright → cookies ──────────────────────────────────────

def get_session_cookies(email: str, password: str) -> dict:
    """
    Ouvre un navigateur headless, se connecte sur UCPA, navigue vers la page
    padel et retourne les cookies de session sous forme de dict {nom: valeur}.
    """
    log.info("Démarrage du navigateur (login)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        # ── Charger la page padel pour initialiser les cookies de domaine
        log.info("Initialisation du domaine ucpa.com...")
        page.goto(PADEL_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        # Accepter cookies si présents
        try:
            btn = page.locator("button:has-text('ACCEPTER')").first
            if btn.is_visible(timeout=3000):
                btn.click()
                page.wait_for_timeout(1000)
                log.info("Cookies acceptés.")
        except PWTimeout:
            pass

        # ── Page de login
        log.info("Navigation vers la page de login...")
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        # Accepter cookies sur la page login si réapparus
        try:
            btn = page.locator("button:has-text('ACCEPTER')").first
            if btn.is_visible(timeout=3000):
                btn.click()
                page.wait_for_timeout(1000)
        except PWTimeout:
            pass

        # Remplir les champs
        log.info("Saisie des identifiants...")
        page.locator("input[id='email']").fill(email)
        page.locator("input[type='password']").fill(password)
        page.locator("button[type='submit']").click()

        # Attendre la fin de la redirection post-login
        log.info("Attente de la redirection post-login...")
        try:
            page.wait_for_url("**/ucpa.com/**", timeout=20000)
        except PWTimeout:
            pass
        page.wait_for_timeout(3000)
        log.info(f"URL après login: {page.url}")

        # Si redirigé hors de la page padel, y revenir
        if "mon-terrain-padel" not in page.url:
            log.info("Retour sur la page padel...")
            page.goto(PADEL_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(4000)

        # Accepter cookies si réapparus
        try:
            btn = page.locator("button:has-text('ACCEPTER')").first
            if btn.is_visible(timeout=3000):
                btn.click()
                page.wait_for_timeout(1000)
        except PWTimeout:
            pass

        # ── Extraire les cookies
        all_cookies = context.cookies()
        cookie_dict = {c["name"]: c["value"] for c in all_cookies}
        log.info(f"Cookies récupérés: {len(cookie_dict)} cookies")

        # Vérifier qu'on est bien connecté
        if not any(k for k in cookie_dict if "auth" in k.lower() or "session" in k.lower() or "token" in k.lower()):
            # Essai moins strict : vérifier le texte de la page
            body = page.inner_text("body")
            if "déconnexion" not in body.lower() and "guillaume" not in body.lower():
                log.warning("Connexion incertaine (aucun cookie auth trouvé)")
            else:
                log.info("✓ Connexion confirmée via contenu page")
        else:
            log.info("✓ Connexion confirmée via cookies")

        page.screenshot(path="/tmp/ucpa_01_apres_login.png")
        browser.close()

    return cookie_dict


# ── Étape 2 : Session requests avec les cookies ────────────────────────────────

def build_session(cookies: dict) -> requests.Session:
    """Construit une session requests avec les cookies et headers standard."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Origin": BASE_URL,
        "Referer": PADEL_URL,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fr-FR,fr;q=0.9",
    })
    for name, value in cookies.items():
        s.cookies.set(name, value, domain=".ucpa.com")
    return s


def api_get(session: requests.Session, url: str, params: dict = None, label: str = "") -> dict:
    """GET avec retry × 2, raise si échec."""
    for attempt in range(2):
        try:
            r = session.get(url, params=params, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == 0:
                log.warning(f"GET {label} tentative 1 échouée ({e}), retry...")
                time.sleep(2)
            else:
                raise RuntimeError(f"GET {label} échoué: {e}") from e


def api_post(session: requests.Session, url: str, body: dict, label: str = "") -> dict:
    """POST JSON avec retry × 2, raise si échec."""
    for attempt in range(2):
        try:
            r = session.post(url, json=body, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == 0:
                log.warning(f"POST {label} tentative 1 échouée ({e}), retry...")
                time.sleep(2)
            else:
                raise RuntimeError(f"POST {label} échoué: {e}") from e


# ── Étape 3 : Récupérer les infos utilisateur ──────────────────────────────────

def get_user_info(session: requests.Session) -> dict:
    log.info("Récupération des infos utilisateur...")
    data = api_get(
        session,
        f"{BASE_URL}/loisirs-reservation/api/users/user",
        label="users/user",
    )
    if not data.get("success"):
        raise RuntimeError(f"Échec users/user: {data}")
    user = data["data"]
    log.info(f"✓ Connecté en tant que {user['firstname']} {user['lastname']} ({user['uuid']})")
    return user


# ── Étape 4 : Vérifier la disponibilité du créneau ────────────────────────────

def check_availability(session: requests.Session, target_date: datetime) -> dict:
    """
    Interroge l'API session/products pour la date cible à 7h.
    Retourne le terrain dispo (préférence terrain 7, sinon 6).
    Raise si aucun créneau disponible.
    """
    log.info(f"Vérification disponibilité pour le {target_date.strftime('%d/%m/%Y')} à 07:00...")

    ts_start = ts_paris_ms(target_date, 7, 0)
    ts_end   = ts_paris_ms(target_date, 8, 0) - 1000

    # Les deux terrains en parallèle
    code_activites = ",".join(str(t["codeActivite"]) for t in TERRAINS.values())
    code_creneaux  = ",".join(t["codeCreneau"] for t in TERRAINS.values())

    url = (
        f"{BASE_URL}/loisirs-reservation/api/info/session/products"
        f"/{code_activites}/{code_creneaux}/{ts_start}/{ts_end}/{WORKSPACE}"
    )
    data = api_get(session, url, label="session/products")
    log.info(f"Réponse API brute: {json.dumps(data)[:500]}")

    if not isinstance(data, list) or len(data) == 0:
        raise RuntimeError("Aucune session retournée par l'API")

    # Parser les sessions disponibles (placesDisponibles > 0)
    item = data[0]
    sessions = item.get("sessions", [])
    log.info(f"Sessions trouvées: {len(sessions)}")

    dispo = {}
    for s in sessions:
        nom = s.get("nomActivite", "")
        places = s.get("placesDisponibles", 0)
        statut = s.get("statut", 1)
        log.info(f"  {nom}: {places} place(s), statut={statut}")
        if places > 0 and statut == 0:
            for num, terrain in TERRAINS.items():
                if str(terrain["codeActivite"]) == str(s["codeActivite"]):
                    dispo[num] = {**terrain, "session_data": s}

    if not dispo:
        raise RuntimeError(
            f"Aucun créneau disponible le {target_date.strftime('%d/%m/%Y')} à 07:00"
        )

    # Choisir terrain préféré sinon premier disponible
    chosen_num = PREFERRED_TERRAIN if PREFERRED_TERRAIN in dispo else next(iter(dispo))
    chosen = dispo[chosen_num]
    log.info(f"✓ Terrain {chosen_num} disponible ({chosen['nom_session']})")
    return {"terrain": chosen, "terrain_num": chosen_num, "ts_start": ts_start, "ts_end": ts_end}


# ── Étape 5 : Valider le code Wellpass ─────────────────────────────────────────

def validate_wellpass(session: requests.Session, wellpass_code: str, user: dict,
                       ts_start: int, ts_end: int) -> None:
    log.info(f"Validation du code Wellpass {wellpass_code}...")
    url = f"{BASE_URL}/loisirs-reservation/api/users/gymlib/validate"
    params = {
        "code": wellpass_code,
        "customerUuid": user["uuid"],
        "workspace": WORKSPACE,
        "price": 45,
        "startTime": ts_start,
        "endTime": ts_end,
        "productUuid": PRODUCT_UUID,
        "gymlibAmount": 45,
    }
    data = api_get(session, url, params=params, label="gymlib/validate")
    if not data.get("success"):
        raise RuntimeError(f"Code Wellpass invalide ou refusé: {data}")
    log.info("✓ Code Wellpass validé")


# ── Étape 6 : Vérifier les documents requis ────────────────────────────────────

def check_required_documents(session: requests.Session, user: dict) -> dict:
    log.info("Vérification des documents requis...")
    url = f"{BASE_URL}/loisirs-reservation/api/users/required-documents/{WORKSPACE}"
    body = {
        "workspace": WORKSPACE,
        "participant": user["uuid"],
        "code_category_tarrif": TARIFF_WELLPASS["tariffCategoryCode"],
    }
    data = api_post(session, url, body, label="required-documents")
    log.info(f"✓ Documents: validInfo={data.get('validInfo')}, upload_documents={data.get('upload_documents')}")
    return data


# ── Étape 7 : Ajouter au panier ────────────────────────────────────────────────

def add_to_cart(session: requests.Session, user: dict, terrain: dict,
                ts_start: int, ts_end: int, wellpass_code: str,
                doc_info: dict) -> dict:
    log.info("Ajout au panier...")

    # Construction du participant avec le tarif Wellpass
    participant = {
        "uuid": user["uuid"],
        "horanet_id": user["horanet_id"],
        "firstname": user["firstname"],
        "lastname": user["lastname"],
        "gender": user["gender"],
        "email": user["email"],
        "mobilephone": user.get("mobilephone"),
        "street_number": user.get("street_number"),
        "street_name": user.get("street_name"),
        "address2": user.get("address2"),
        "zip_code": user.get("zip_code"),
        "town": user.get("town"),
        "country": user.get("country"),
        "emergency_contacts": user.get("emergency_contacts", []),
        "birth_date": user["birth_date"],
        "contexts": [{"value": "alpha", "label": "Loisir"}],
        "allowed_products": [],
        "licenses": user.get("licenses", []),
        "__typename": "Customer",
        "tariff": {
            "uuid": None,
            "promotions": [],
            "category": TARIFF_WELLPASS["category"],
            "price": TARIFF_WELLPASS["price"],
            "originalPrice": None,
            "tva": TARIFF_WELLPASS["tva"],
            "period": None,
            "priceCategory": None,
            "tariffCode": TARIFF_WELLPASS["codeTariff"],
            "tariffCategoryCode": TARIFF_WELLPASS["tariffCategoryCode"],
            "label": TARIFF_WELLPASS["label"],
            "conditions": None,
            "__typename": "HoranetTariff",
            "description": None,
            "codeTariff": TARIFF_WELLPASS["codeTariff"],
            "negotiatedPrice": TARIFF_WELLPASS["negotiatedPrice"],
            "isGymlibTariff": True,
            "tariffMaxAge": None,
            "index": 1,
            "gymlibCode": wellpass_code,
            "documents": {
                "workspace": doc_info["workspace"],
                "participant_uuid": doc_info["participant_uuid"],
                "code_category_tarrif": doc_info["code_category_tarrif"],
                "upload_documents": doc_info["upload_documents"],
                "validInfo": doc_info["validInfo"],
                "required_documents": doc_info.get("required_documents"),
            },
        },
        "period": None,
        "quantity": 1,
    }

    # Activité du terrain choisi
    activity = {
        "uuid": terrain["activity_uuid"],
        "activity_name": terrain["activity_name"],
        "activity_type": "TERRAIN",
        "activity_code": terrain["activity_code"],
        "tda_info": None,
        "tda_image": None,
        "tdaImageSEO": None,
        "__typename": "Activity",
    }

    # offerInfo (tarifs disponibles + options)
    offer_info = {
        "uuid": None,
        "sessionProRataAmount": None,
        "stock": None,
        "contremarque": False,
        "insuranceType": None,
        "firstRecurringSession": None,
        "sans_support": False,
        "tda_info": (
            "<p>La réservation est <strong>modifiable</strong> jusqu'à 48h avant la séance. "
            "Aucun remboursement ne pourra avoir lieu.</p>"
            "<p><strong>Pensez à apporter vos balles ou vous pouvez les acheter sur place.</strong></p>"
            "<p>  </p>"
        ),
        "payment_method": "c5",
        "cancelation": True,
        "workspace": WORKSPACE,
        "name": "Séance Unitaire",
        "isLoyaltyOffer": False,
        "loyaltyDuration": None,
        "productCategory": "Séance unitaire",
        "selectedHoranetTariffs": [
            {
                "description": None,
                "codeTariff": TARIFF_PLEIN["codeTariff"],
                "negotiatedPrice": TARIFF_PLEIN["negotiatedPrice"],
                "isGymlibTariff": False,
                "tariffMaxAge": None,
                "__typename": "HoranetTariff",
            },
            {
                "description": None,
                "codeTariff": TARIFF_WELLPASS["codeTariff"],
                "negotiatedPrice": TARIFF_WELLPASS["negotiatedPrice"],
                "isGymlibTariff": True,
                "tariffMaxAge": None,
                "__typename": "HoranetTariff",
            },
        ],
        "subscriptionDescription": None,
        "offer_type": None,
        "offerType": None,
        "isPension": None,
        "is_reservation": None,
        "optionsInfo": None,
        "options": [],
        "horanet_product": {
            "name": HORANET_PRODUCT_NAME,
            "horanet_product_code": HORANET_PRODUCT_CODE,
            "horanet_product_reference": HORANET_PRODUCT_REFERENCE,
            "__typename": "HoranetProduct",
        },
        "description": None,
        "detail": {
            "unit_sales": False,
            "pass": False,
            "first_purchase": False,
            "reloadable": False,
            "insurance": None,
            "stage": None,
            "stage1D": None,
            "license": None,
            "inscription": False,
            "reservation": True,
            "recurring": False,
            "isClubCard": None,
            "haveSessions": True,
            "activities": [activity],
            "lowest_price": "38.00",
            "lowest_price_promo": None,
            "isValid": None,
            "__typename": "OfferDetail",
        },
        "__typename": "DynamoOffer",
    }

    body = {
        "cartItem": {
            "workspace": WORKSPACE,
            "participants": [participant],
            "details": {
                "offerUuid": None,
                "stock": None,
                "sans_support": False,
                "contremarque": False,
                "tda_info": offer_info["tda_info"],
                "first_purchase": False,
                "horanet_product_name": HORANET_PRODUCT_NAME,
                "horanet_product_code": HORANET_PRODUCT_CODE,
                "horanet_product_reference": HORANET_PRODUCT_REFERENCE,
                "inscription": False,
                "pass": False,
                "product_image": (
                    "https://media.ucpa.com/t_UCPA_Vertical/"
                    "UCPA-SPORT-STATION/00099562-sport-station-meudon-padel.jpg"
                ),
                "recurring": False,
                "stage": None,
                "stage1D": None,
                "license": None,
                "reloadable": False,
                "reservation": True,
                "unit_sales": False,
                "product_name": "Terrain de Padel - Heures Creuses",
                "product_uuid": PRODUCT_UUID,
                "product_type": "Séance Unitaire",
                "cancelation": True,
                "offer_type": None,
                "isClubCard": None,
                "firstRecurringSession": None,
                "isLoyaltyOffer": False,
                "loyaltyDuration": None,
                "activities": [activity],
            },
            "session": {
                "name": terrain["nom_session"],
                "code": terrain["codeCreneau"],
                "start_time": ts_start,
                "end_time": ts_end,
                "last_time": 0,
            },
        },
        "user": user["uuid"],
        "offerInfo": offer_info,
        "product_uuid": PRODUCT_UUID,
        "isInternalSessions": False,
        "apiSource": "legacy",
    }

    url = f"{BASE_URL}/loisirs-reservation/api/users/shopping-cart"
    data = api_post(session, url, body, label="shopping-cart")

    result = data.get("addShoppingCartV3", {})
    if not result.get("success"):
        raise RuntimeError(f"Échec ajout panier: {data}")
    log.info("✓ Ajouté au panier")
    return data


# ── Étape 8 : Payer ────────────────────────────────────────────────────────────

def pay(session: requests.Session, user: dict) -> dict:
    log.info("Paiement (Wellpass)...")
    url = f"{BASE_URL}/loisirs-reservation/api/users/pay"
    body = {
        "user": user["uuid"],
        "workspace": WORKSPACE,
        "parceled": False,
        "promoAmount": None,
        "promoMetric": None,
        "promoCode": None,
        "promoMotive": None,
        "proRata": False,
    }
    data = api_post(session, url, body, label="users/pay")

    result = data.get("generatePaymentSession", {})
    if not result.get("success"):
        raise RuntimeError(f"Échec paiement: {data}")

    order_uuid = result["data"]["order_uuid"]
    is_gymlib  = result["data"].get("isGymlib", False)
    log.info(f"✓ Paiement accepté (gymlib={is_gymlib}), order_uuid={order_uuid}")
    return {"order_uuid": order_uuid, "data": result["data"]}


# ── Étape 9 : Vérifier la commande ────────────────────────────────────────────

def verify_order(session: requests.Session, order_uuid: str) -> dict:
    log.info(f"Vérification de la commande {order_uuid}...")
    url = f"{BASE_URL}/loisirs-reservation/api/info/order/{order_uuid}/{WORKSPACE}"
    data = api_get(session, url, label="info/order")

    order = data.get("order", {})
    status = order.get("status", "unknown")
    log.info(f"✓ Commande status: {status}")
    return order


# ── Orchestrateur principal ────────────────────────────────────────────────────

def run(chosen_day: str, wellpass_code: str) -> dict:
    email    = os.environ.get("UCPA_EMAIL", "")
    password = os.environ.get("UCPA_PASSWORD", "")

    if not email or not password:
        return {"success": False, "message": "UCPA_EMAIL ou UCPA_PASSWORD manquant"}
    if chosen_day not in DAY_OFFSET:
        return {"success": False, "message": f"Jour invalide: {chosen_day}. Valeurs: {list(DAY_OFFSET)}"}
    if not wellpass_code:
        return {"success": False, "message": "Code Wellpass manquant"}

    target_date = get_target_date(chosen_day)
    log.info(f"=== Réservation {chosen_day} {target_date.strftime('%d/%m/%Y')} 07:00-08:00 ===")

    try:
        # 1. Login
        cookies = get_session_cookies(email, password)
        session = build_session(cookies)

        # 2. Infos utilisateur (vérifie qu'on est bien connecté)
        user = get_user_info(session)

        # 3. Disponibilité
        avail = check_availability(session, target_date)
        terrain  = avail["terrain"]
        ts_start = avail["ts_start"]
        ts_end   = avail["ts_end"]

        # 4. Valider Wellpass
        validate_wellpass(session, wellpass_code, user, ts_start, ts_end)

        # 5. Documents
        doc_info = check_required_documents(session, user)

        # 6. Panier
        add_to_cart(session, user, terrain, ts_start, ts_end, wellpass_code, doc_info)

        # 7. Paiement
        pay_result = pay(session, user)
        order_uuid = pay_result["order_uuid"]

        # 8. Vérification commande
        order = verify_order(session, order_uuid)

        msg = (
            f"✅ Réservation confirmée ! "
            f"{chosen_day} {target_date.strftime('%d/%m/%Y')} 07:00-08:00 "
            f"— {terrain['nom_session']} "
            f"(commande {order_uuid})"
        )
        log.info(msg)
        return {"success": True, "message": msg, "order_uuid": order_uuid}

    except Exception as e:
        log.error(f"❌ Erreur: {e}")
        return {"success": False, "message": str(e)}


# ── Entrée ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    chosen_day    = sys.argv[1] if len(sys.argv) > 1 else "Lundi"
    wellpass_code = sys.argv[2] if len(sys.argv) > 2 else ""
    result = run(chosen_day, wellpass_code)
    print(json.dumps(result, ensure_ascii=False, indent=2))
