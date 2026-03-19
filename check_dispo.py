"""
check_dispo.py — Vérifie les disponibilités padel UCPA pour la semaine suivante
"""

import os, sys, json, base64, logging, requests
from datetime import datetime, timedelta, timezone
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

logging.basicConfig(level=logging.INFO, format="[DISPO] %(message)s",
                                        handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("dispo")

BASE_URL     = "https://www.ucpa.com"
WORKSPACE    = "alpha_hp"
ESPACE_UUID  = "area_1639603579_a4ec61b0-5ded-11ec-aab6-45fce5b83b3e"
PADEL_URL    = f"{BASE_URL}/sport-station/paris-19/mon-terrain-padel"
LOGIN_URL    = f"{BASE_URL}/af/sso/login?context=alpha"

DAYS       = ["Lundi", "Mardi", "Mercredi", "Jeudi"]
DAY_OFFSET = {"Lundi": 0, "Mardi": 1, "Mercredi": 2, "Jeudi": 3}

UCPA_EMAIL    = os.environ.get("UCPA_EMAIL", "")
UCPA_PASSWORD = os.environ.get("UCPA_PASSWORD", "")
GH_TOKEN      = os.environ.get("GH_TOKEN", "")
GH_REPO_OWNER = os.environ.get("GH_REPO_OWNER", "GClaudio64")
GH_REPO_NAME  = os.environ.get("GH_REPO_NAME", "padel-booker")


def get_next_week_dates():
        today = datetime.now()
        days_to_monday = (7 - today.weekday()) % 7
        if days_to_monday == 0:
                    days_to_monday = 7
                next_monday = today + timedelta(days=days_to_monday)
    return {day: next_monday + timedelta(days=offset)
                        for day, offset in DAY_OFFSET.items()}


def get_session_cookies():
        log.info("Login Playwright...")
    with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/124.0.0.0 Safari/537.36"))
                page = context.new_page()

        page.goto(PADEL_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
        try:
                        btn = page.locator("button:has-text('ACCEPTER')").first
                        if btn.is_visible(timeout=3000):
                                            btn.click()
                                            page.wait_for_timeout(1000)
        except PWTimeout:
                        pass

        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        try:
                        btn = page.locator("button:has-text('ACCEPTER')").first
                        if btn.is_visible(timeout=3000):
                                            btn.click()
                                            page.wait_for_timeout(500)
        except PWTimeout:
                        pass

        page.locator("input[id='email']").fill(UCPA_EMAIL)
        page.locator("input[type='password']").fill(UCPA_PASSWORD)
        page.locator("button[type='submit']").click()
        try:
                        page.wait_for_url("**/ucpa.com/**", timeout=20000)
except PWTimeout:
            pass
        page.wait_for_timeout(3000)

        if "mon-terrain-padel" not in page.url:
                        page.goto(PADEL_URL, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(3000)

        cookies = {c["name"]: c["value"] for c in context.cookies()}
        log.info(f"  {len(cookies)} cookies récupérés")
        browser.close()
    return cookies


def build_session(cookies):
        s = requests.Session()
    s.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Origin": BASE_URL,
                "Referer": PADEL_URL,
                "Accept": "application/json, text/plain, */*",
    })
    for name, value in cookies.items():
                s.cookies.set(name, value, domain=".ucpa.com")
            return s


def fetch_weekly_data(session, monday_date):
        """
            Appelle l'API weekly et extrait pour chaque créneau 07h00 :
                  - activity_codes + codes  (arrays parallèles)
                        - stock                   (nb terrains dispo, 0 / 1 / 2)

                            Structure API réelle :
                                  data.planner.columns[0..6].items[] ->
                                          { startTime, startDate, activity_codes[], codes[], stock, ... }
                                              """
    url = (f"{BASE_URL}/sport-station/api/areas-offers/weekly/{WORKSPACE}"
                      f"?reservationPeriod=1&espace={ESPACE_UUID}"
                      f"&time={monday_date.strftime('%d-%m-%Y')}"
                      f"&__amp_source_origin=https://www.ucpa.com")
    log.info(f"Weekly: {url}")

    r = session.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()

    results = {}  # date_key -> { codes_by_activity: {ac: cc}, stock: int }

    planner = data.get("planner", {})
    for column in planner.get("columns", []):
                for item in column.get("items", []):
                                if item.get("startTime") != "07h00":
                                                    continue

                                raw_date = item.get("startDate", "")
                                try:
                                                    dt = datetime.strptime(raw_date, "%d/%m/%Y")
                                                    date_key = dt.strftime("%Y-%m-%d")
except ValueError:
                log.warning(f"  Date invalide ignorée: {raw_date}")
                continue

            activity_codes = item.get("activity_codes", [])
            codes = item.get("codes", [])
            stock = item.get("stock", 0)

            codes_map = {}
            for ac, cc in zip(activity_codes, codes):
                                codes_map[str(ac)] = str(cc)

            results[date_key] = {
                                "codes_by_activity": codes_map,
                                "stock": int(stock),
            }
            log.info(f"  {date_key}: stock={stock}, codes={codes_map}")

    log.info(f"Weekly: {len(results)} jour(s) avec créneau 07h00")
    return results


def write_dispo_json(dispo_data):
        if not GH_TOKEN:
                    with open("dispo.json", "w") as f:
                                    json.dump(dispo_data, f, ensure_ascii=False, indent=2)
                                return

    url = (f"https://api.github.com/repos/{GH_REPO_OWNER}/"
                      f"{GH_REPO_NAME}/contents/dispo.json")
    headers = {
                "Authorization": f"Bearer {GH_TOKEN}",
                "Accept": "application/vnd.github+json",
    }

    sha = None
    try:
                r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
                        sha = r.json().get("sha")
except Exception:
        pass

    content = base64.b64encode(
                json.dumps(dispo_data, ensure_ascii=False, indent=2).encode()
    ).decode()
    body = {
                "message": f"Update dispo.json — {dispo_data['updated']}",
                "content": content,
    }
    if sha:
                body["sha"] = sha

    r = requests.put(url, headers=headers, json=body, timeout=15)
    if r.status_code in (200, 201):
                log.info("  dispo.json mis à jour sur GitHub")
else:
        log.error(f"Erreur GitHub: {r.status_code} {r.text[:200]}")
        sys.exit(1)


def main():
        dates = get_next_week_dates()
    monday = dates["Lundi"]
    log.info(f"Semaine du {monday.strftime('%d/%m/%Y')}")

    cookies = get_session_cookies()
    session = build_session(cookies)

    try:
                weekly_data = fetch_weekly_data(session, monday)
except Exception as e:
        log.error(f"Erreur weekly: {e}")
        weekly_data = {}

    result = {}
    for day in DAYS:
                dt = dates[day]
        date_key = dt.strftime("%Y-%m-%d")
        log.info(f"Vérification {day} {dt.strftime('%d/%m/%Y')}...")

        day_data = weekly_data.get(date_key)
        if day_data is not None:
                        terrains = day_data["stock"]
            log.info(f"  -> {terrains} terrain(s) dispo")
else:
                    log.warning(f"  {date_key}: pas trouvé dans weekly -> 0")
            terrains = 0

        result[day] = {
            "date": dt.strftime("%d/%m"),
            "terrains": terrains,
        }

    dispo_data = {
                "updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "semaine": (f"{dates['Lundi'].strftime('%d/%m')} "
                                        f"- {dates['Jeudi'].strftime('%d/%m')}"),
                "jours": result,
    }
    log.info(f"Résultat: {json.dumps(dispo_data, ensure_ascii=False)}")
    write_dispo_json(dispo_data)


if __name__ == "__main__":
        main()
