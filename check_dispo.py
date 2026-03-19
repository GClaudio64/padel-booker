"""
check_dispo.py — Vérifie les disponibilités padel UCPA pour la semaine suivante
"""

import os, sys, json, base64, logging, requests
from datetime import datetime, timedelta, timezone
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

logging.basicConfig(level=logging.INFO, format="[DISPO] %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("dispo")

BASE_URL      = "https://www.ucpa.com"
WORKSPACE     = "alpha_hp"
ESPACE_UUID   = "area_1639603579_a4ec61b0-5ded-11ec-aab6-45fce5b83b3e"
PADEL_URL     = f"{BASE_URL}/sport-station/paris-19/mon-terrain-padel"
LOGIN_URL     = f"{BASE_URL}/af/sso/login?context=alpha"
DAYS          = ["Lundi", "Mardi", "Mercredi", "Jeudi"]
DAY_OFFSET    = {"Lundi": 0, "Mardi": 1, "Mercredi": 2, "Jeudi": 3}

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
    return {day: next_monday + timedelta(days=offset) for day, offset in DAY_OFFSET.items()}

def ts_paris_ms(dt, hour, minute=0):
    dst_change = datetime(2026, 3, 29, 2, 0)
    dt_with_time = datetime(dt.year, dt.month, dt.day, hour, minute)
    utc_offset = 2 if dt_with_time >= dst_change else 1
    dt_utc = dt_with_time - timedelta(hours=utc_offset)
    return int(dt_utc.replace(tzinfo=timezone.utc).timestamp() * 1000)

def get_session_cookies():
    log.info("Login Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        page = context.new_page()
        page.goto(PADEL_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
        try:
            btn = page.locator("button:has-text('ACCEPTER')").first
            if btn.is_visible(timeout=3000): btn.click(); page.wait_for_timeout(1000)
        except PWTimeout: pass
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        try:
            btn = page.locator("button:has-text('ACCEPTER')").first
            if btn.is_visible(timeout=3000): btn.click(); page.wait_for_timeout(500)
        except PWTimeout: pass
        page.locator("input[id='email']").fill(UCPA_EMAIL)
        page.locator("input[type='password']").fill(UCPA_PASSWORD)
        page.locator("button[type='submit']").click()
        try: page.wait_for_url("**/ucpa.com/**", timeout=20000)
        except PWTimeout: pass
        page.wait_for_timeout(3000)
        if "mon-terrain-padel" not in page.url:
            page.goto(PADEL_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
        cookies = {c["name"]: c["value"] for c in context.cookies()}
        log.info(f"✓ {len(cookies)} cookies récupérés")
        browser.close()
    return cookies

def build_session(cookies):
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Origin": BASE_URL, "Referer": PADEL_URL, "Accept": "application/json, text/plain, */*"})
    for name, value in cookies.items():
        s.cookies.set(name, value, domain=".ucpa.com")
    return s

def fetch_weekly_codes(session, monday_date):
    url = (f"{BASE_URL}/sport-station/api/areas-offers/weekly/{WORKSPACE}"
           f"?reservationPeriod=1&espace={ESPACE_UUID}&time={monday_date.strftime('%d-%m-%Y')}"
           f"&__amp_source_origin=https://www.ucpa.com")
    log.info(f"Weekly: {url}")
    r = session.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()
    codes_by_day = {}
    def extract(obj):
        if isinstance(obj, dict):
            jour = str(obj.get("jourCreneau", "") or obj.get("date", ""))
            debut = str(obj.get("debutCreneau", "") or obj.get("start", ""))
            ca = obj.get("codeActivite")
            cc = obj.get("codeCreneau")
            if jour and "07:00" in debut and ca and cc:
                date_key = jour[:10]
                if date_key not in codes_by_day: codes_by_day[date_key] = {}
                codes_by_day[date_key][str(ca)] = str(cc)
            for v in obj.values(): extract(v)
        elif isinstance(obj, list):
            for item in obj: extract(item)
    extract(data)
    log.info(f"Codes extraits: {codes_by_day}")
    return codes_by_day

def count_terrains(session, target_date, codes_by_day):
    ts_start = ts_paris_ms(target_date, 7, 0)
    ts_end   = ts_paris_ms(target_date, 8, 0) - 1000
    date_key = target_date.strftime("%Y-%m-%d")
    if date_key in codes_by_day and codes_by_day[date_key]:
        codes = codes_by_day[date_key]
        code_activites = ",".join(codes.keys())
        code_creneaux  = ",".join(codes.values())
    else:
        code_activites = "103423129,103423206"
        code_creneaux  = "461643140,461646364"
        log.info(f"  {date_key}: fallback codes statiques")
    url = (f"{BASE_URL}/loisirs-reservation/api/info/session/products"
           f"/{code_activites}/{code_creneaux}/{ts_start}/{ts_end}/{WORKSPACE}")
    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning(f"  Erreur: {e}")
        return 0
    if not isinstance(data, list) or len(data) == 0: return 0
    sessions = data[0].get("sessions", [])
    count = sum(1 for s in sessions if s.get("placesDisponibles", 0) > 0 and s.get("statut", 1) == 0)
    log.info(f"  → {count} terrain(s) dispo")
    return count

def write_dispo_json(dispo_data):
    if not GH_TOKEN:
        with open("dispo.json", "w") as f: json.dump(dispo_data, f, ensure_ascii=False, indent=2)
        return
    url = f"https://api.github.com/repos/{GH_REPO_OWNER}/{GH_REPO_NAME}/contents/dispo.json"
    headers = {"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"}
    sha = None
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200: sha = r.json().get("sha")
    except Exception: pass
    content = base64.b64encode(json.dumps(dispo_data, ensure_ascii=False, indent=2).encode()).decode()
    body = {"message": f"Update dispo.json — {dispo_data['updated']}", "content": content}
    if sha: body["sha"] = sha
    r = requests.put(url, headers=headers, json=body, timeout=15)
    if r.status_code in (200, 201): log.info("✓ dispo.json mis à jour sur GitHub")
    else: log.error(f"Erreur GitHub: {r.status_code} {r.text[:200]}"); sys.exit(1)

def main():
    dates  = get_next_week_dates()
    monday = dates["Lundi"]
    log.info(f"Semaine du {monday.strftime('%d/%m/%Y')}")
    cookies = get_session_cookies()
    session = build_session(cookies)
    try: codes_by_day = fetch_weekly_codes(session, monday)
    except Exception as e: log.error(f"Erreur weekly: {e}"); codes_by_day = {}
    result = {}
    for day in DAYS:
        dt = dates[day]
        log.info(f"Vérification {day} {dt.strftime('%d/%m/%Y')}...")
        result[day] = {"date": dt.strftime("%d/%m"), "terrains": count_terrains(session, dt, codes_by_day)}
    dispo_data = {"updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                  "semaine": f"{dates['Lundi'].strftime('%d/%m')} – {dates['Jeudi'].strftime('%d/%m')}",
                  "jours": result}
    log.info(f"Résultat: {json.dumps(dispo_data, ensure_ascii=False)}")
    write_dispo_json(dispo_data)

if __name__ == "__main__":
    main()
