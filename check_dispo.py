"""
check_dispo.py — Vérifie les disponibilités padel UCPA pour la semaine suivante
===============================================================================
- Appelle l'API weekly UCPA (sans authentification)
- Pour chaque jour Lu/Ma/Me/Je, compte les terrains disponibles à 7h
- Écrit le résultat dans dispo.json sur le repo GitHub via l'API
 
Usage : python check_dispo.py
Env   : GH_TOKEN, GH_REPO_OWNER, GH_REPO_NAME
"""
 
import os
import sys
import json
import base64
import logging
import requests
from datetime import datetime, timedelta, timezone
 
logging.basicConfig(level=logging.INFO, format="[DISPO] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("dispo")
 
# ── Constantes ─────────────────────────────────────────────────────────────────
BASE_URL    = "https://www.ucpa.com"
WORKSPACE   = "alpha_hp"
ESPACE_UUID = "area_1639603579_a4ec61b0-5ded-11ec-aab6-45fce5b83b3e"
DAYS        = ["Lundi", "Mardi", "Mercredi", "Jeudi"]
DAY_OFFSET  = {"Lundi": 0, "Mardi": 1, "Mercredi": 2, "Jeudi": 3}
 
GH_TOKEN      = os.environ.get("GH_TOKEN", "")
GH_REPO_OWNER = os.environ.get("GH_REPO_OWNER", "GClaudio64")
GH_REPO_NAME  = os.environ.get("GH_REPO_NAME", "padel-booker")
 
 
# ── Helpers ────────────────────────────────────────────────────────────────────
 
def get_next_week_dates():
    """Retourne un dict {jour_fr: datetime} pour la semaine suivante."""
    today = datetime.now()
    days_to_monday = (7 - today.weekday()) % 7
    if days_to_monday == 0:
        days_to_monday = 7
    next_monday = today + timedelta(days=days_to_monday)
    return {day: next_monday + timedelta(days=offset)
            for day, offset in DAY_OFFSET.items()}
 
 
def ts_paris_ms(dt, hour, minute=0):
    """Timestamp Unix ms pour une heure Paris (gère DST 2026)."""
    dst_change = datetime(2026, 3, 29, 2, 0)
    dt_with_time = datetime(dt.year, dt.month, dt.day, hour, minute)
    utc_offset = 2 if dt_with_time >= dst_change else 1
    dt_utc = dt_with_time - timedelta(hours=utc_offset)
    return int(dt_utc.replace(tzinfo=timezone.utc).timestamp() * 1000)
 
 
def fetch_weekly_planning(monday_date):
    """Appelle l'API weekly UCPA pour la semaine du lundi donné."""
    time_param = monday_date.strftime("%d-%m-%Y")
    url = (
        f"{BASE_URL}/sport-station/api/areas-offers/weekly/{WORKSPACE}"
        f"?reservationPeriod=1&espace={ESPACE_UUID}&time={time_param}"
        f"&__amp_source_origin=https://www.ucpa.com"
    )
    log.info(f"Appel weekly: {url}")
    r = requests.get(url, timeout=15, headers={
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/sport-station/paris-19/mon-terrain-padel",
        "AMP-Same-Origin": "true",
    })
    r.raise_for_status()
    return r.json()
 
 
def count_available_terrains(weekly_data, target_date):
    """
    À partir du planning hebdo, compte les terrains disponibles à 7h
    pour la date cible en appelant l'API session/products.
    """
    ts_start = ts_paris_ms(target_date, 7, 0)
    ts_end   = ts_paris_ms(target_date, 8, 0) - 1000
 
    # Extraire les codeActivite et codeCreneau du planning weekly
    slots = []
    if isinstance(weekly_data, dict):
        items = weekly_data.get("items", weekly_data.get("slots", []))
    elif isinstance(weekly_data, list):
        items = weekly_data
    else:
        items = []
 
    # Chercher les créneaux 7h du jour cible dans le planning
    target_str = target_date.strftime("%Y-%m-%d")
    code_activites_found = []
    code_creneaux_found  = []
 
    def search_slots(obj):
        if isinstance(obj, dict):
            jour = obj.get("jourCreneau", "") or obj.get("date", "")
            debut = obj.get("debutCreneau", "") or obj.get("start", "")
            if target_str in str(jour) and "07:00" in str(debut):
                ca = obj.get("codeActivite") or obj.get("activity_code")
                cc = obj.get("codeCreneau") or obj.get("slot_code")
                if ca and cc:
                    code_activites_found.append(str(ca))
                    code_creneaux_found.append(str(cc))
            for v in obj.values():
                search_slots(v)
        elif isinstance(obj, list):
            for item in obj:
                search_slots(item)
 
    search_slots(weekly_data)
 
    if code_activites_found:
        log.info(f"  Codes trouvés dans weekly: activités={code_activites_found}, créneaux={code_creneaux_found}")
        code_activites = ",".join(code_activites_found)
        code_creneaux  = ",".join(code_creneaux_found)
    else:
        # Fallback : utiliser les codes statiques connus
        log.info(f"  Codes non trouvés dans weekly, utilisation des codes statiques")
        code_activites = "103423129,103423206"
        code_creneaux  = "461643140,461646364"
 
    url = (
        f"{BASE_URL}/loisirs-reservation/api/info/session/products"
        f"/{code_activites}/{code_creneaux}/{ts_start}/{ts_end}/{WORKSPACE}"
    )
    log.info(f"  Session products: {url}")
 
    try:
        r = requests.get(url, timeout=15, headers={
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/sport-station/paris-19/mon-terrain-padel",
        })
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning(f"  Erreur session/products: {e}")
        return 0
 
    if not isinstance(data, list) or len(data) == 0:
        log.info(f"  Réponse vide")
        return 0
 
    sessions = data[0].get("sessions", [])
    count = sum(
        1 for s in sessions
        if s.get("placesDisponibles", 0) > 0 and s.get("statut", 1) == 0
    )
    log.info(f"  {count} terrain(s) disponible(s) sur {len(sessions)} session(s)")
    return count
 
 
# ── Écriture dispo.json sur GitHub ────────────────────────────────────────────
 
def write_dispo_json(dispo_data):
    """Écrit dispo.json sur le repo GitHub via l'API."""
    if not GH_TOKEN:
        log.warning("GH_TOKEN manquant — écriture locale uniquement")
        with open("dispo.json", "w") as f:
            json.dump(dispo_data, f, ensure_ascii=False, indent=2)
        return
 
    url = f"https://api.github.com/repos/{GH_REPO_OWNER}/{GH_REPO_NAME}/contents/dispo.json"
    headers = {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
 
    # Récupérer le SHA actuel si le fichier existe déjà
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
        log.info(f"✓ dispo.json mis à jour sur GitHub")
    else:
        log.error(f"Erreur écriture GitHub: {r.status_code} {r.text[:200]}")
        sys.exit(1)
 
 
# ── Main ───────────────────────────────────────────────────────────────────────
 
def main():
    dates = get_next_week_dates()
    monday = dates["Lundi"]
    log.info(f"Semaine du {monday.strftime('%d/%m/%Y')}")
 
    # Appel unique du planning hebdomadaire
    try:
        weekly = fetch_weekly_planning(monday)
    except Exception as e:
        log.error(f"Erreur fetch weekly: {e}")
        weekly = {}
 
    # Compter les dispos pour chaque jour
    result = {}
    for day in DAYS:
        dt = dates[day]
        log.info(f"Vérification {day} {dt.strftime('%d/%m/%Y')}...")
        count = count_available_terrains(weekly, dt)
        result[day] = {
            "date": dt.strftime("%d/%m"),
            "terrains": count,
        }
 
    # Construire le JSON final
    dispo_data = {
        "updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "semaine": f"{dates['Lundi'].strftime('%d/%m')} – {dates['Jeudi'].strftime('%d/%m')}",
        "jours": result,
    }
 
    log.info(f"Résultat: {json.dumps(dispo_data, ensure_ascii=False)}")
    write_dispo_json(dispo_data)
 
 
if __name__ == "__main__":
    main()
