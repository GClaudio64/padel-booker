<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>🎾 Padel UCPA</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
      background: #0a1628;
      color: #fff;
      min-height: 100vh;
      padding: 32px 20px 40px;
    }
    .header { text-align: center; margin-bottom: 32px; }
    .header h1 { font-size: 1.8rem; font-weight: 700; letter-spacing: -0.5px; }
    .header p { color: #546e7a; font-size: 0.88rem; margin-top: 6px; }
    .card {
      background: #132033;
      border-radius: 18px;
      padding: 22px 18px;
      margin-bottom: 14px;
      border: 1px solid #1e3248;
    }
    .card-title {
      font-size: 0.78rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: #4fc3f7;
      margin-bottom: 16px;
    }
    .day-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .day-btn {
      padding: 16px 8px;
      border-radius: 14px;
      border: 2px solid #1e3248;
      background: #0a1628;
      color: #90a4ae;
      font-size: 1rem;
      font-weight: 600;
      cursor: pointer;
      text-align: center;
      transition: all 0.15s ease;
      user-select: none;
    }
    .day-btn .date-label {
      display: block;
      font-size: 0.72rem;
      font-weight: 400;
      color: #546e7a;
      margin-top: 4px;
    }
    .day-btn.selected {
      border-color: #29b6f6;
      background: #0d2438;
      color: #fff;
    }
    .day-btn.selected .date-label { color: #4fc3f7; }
    .day-btn:active { transform: scale(0.97); }

    .input-field {
      width: 100%;
      padding: 15px 16px;
      background: #0a1628;
      border: 1.5px solid #1e3248;
      border-radius: 13px;
      color: #fff;
      font-size: 1.05rem;
      outline: none;
      -webkit-appearance: none;
      letter-spacing: 1px;
    }
    .input-field:focus { border-color: #29b6f6; }
    .input-field::placeholder { color: #37474f; letter-spacing: 0; }

    /* Token config */
    .config-toggle {
      font-size: 0.78rem;
      color: #546e7a;
      text-align: center;
      margin-bottom: 10px;
      cursor: pointer;
      text-decoration: underline;
    }
    .token-section { display: none; }
    .token-section.visible { display: block; }

    .btn-main {
      width: 100%;
      padding: 17px;
      border-radius: 15px;
      border: none;
      background: linear-gradient(135deg, #0288d1 0%, #26c6da 100%);
      color: #fff;
      font-size: 1.1rem;
      font-weight: 700;
      cursor: pointer;
      margin-top: 6px;
      letter-spacing: 0.2px;
      transition: opacity 0.15s;
    }
    .btn-main:disabled { background: #1e3248; color: #37474f; cursor: not-allowed; }
    .btn-main:not(:disabled):active { opacity: 0.85; transform: scale(0.99); }

    .status {
      margin-top: 18px;
      padding: 16px;
      border-radius: 14px;
      font-size: 0.9rem;
      line-height: 1.7;
      text-align: center;
      font-weight: 500;
      display: none;
    }
    .status.loading { background: #0d2438; border: 1px solid #1e3248; color: #4fc3f7; }
    .status.success { background: #0a2e1a; border: 1px solid #2e7d32; color: #81c784; }
    .status.error   { background: #2e0a0a; border: 1px solid #7d2e2e; color: #ef9a9a; }
    .status.info    { background: #0d2438; border: 1px solid #1e3248; color: #90caf9; }

    .spinner {
      display: inline-block;
      width: 20px; height: 20px;
      border: 3px solid rgba(79,195,247,0.2);
      border-top-color: #4fc3f7;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      vertical-align: middle;
      margin-right: 8px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    .run-link {
      display: block;
      text-align: center;
      margin-top: 12px;
      color: #4fc3f7;
      font-size: 0.85rem;
      text-decoration: none;
    }
    .week-info {
      text-align: center;
      font-size: 0.8rem;
      color: #546e7a;
      margin-bottom: 20px;
    }
  </style>
</head>
<body>

<div class="header">
  <h1>🎾 Padel UCPA</h1>
  <p>Paris 19e · Créneau 7h–8h</p>
</div>

<p class="week-info" id="weekInfo">Semaine du <span id="weekRange">…</span></p>

<div class="card">
  <div class="card-title">1 · Choisis ton jour</div>
  <div class="day-grid" id="dayGrid"></div>
</div>

<div class="card">
  <div class="card-title">2 · Code egym Wellpass</div>
  <input class="input-field" type="text" id="wellpassCode"
    placeholder="Ton code du jour"
    autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false">
</div>

<!-- Token GitHub (caché par défaut, configuré une fois) -->
<p class="config-toggle" onclick="toggleToken()">⚙️ Config GitHub Token</p>
<div class="token-section" id="tokenSection">
  <div class="card">
    <div class="card-title">GitHub Personal Access Token</div>
    <input class="input-field" type="password" id="ghToken"
      placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
      autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false">
    <p style="font-size:0.75rem;color:#546e7a;margin-top:10px;">
      Saisi une fois, sauvegardé dans ton navigateur.
    </p>
  </div>
</div>

<button class="btn-main" id="reserveBtn" onclick="reserve()" disabled>
  Réserver
</button>

<div class="status" id="statusBox"></div>
<a class="run-link" id="runLink" href="#" target="_blank" style="display:none">
  Voir le log GitHub Actions →
</a>

<script>
  // ── Config ────────────────────────────────────────────────────────
  const REPO_OWNER = "g-fourcade"; // à remplacer par ton username GitHub
  const REPO_NAME  = "padel-booker";
  const WORKFLOW_ID = "padel_booker.yml";

  // ── Dates semaine prochaine ────────────────────────────────────────
  const DAYS = ["Lundi","Mardi","Mercredi","Jeudi"];
  function nextWeekDates() {
    const today = new Date();
    const dow = today.getDay(); // 0=dim
    const daysUntilMon = dow === 0 ? 1 : (8 - dow);
    const mon = new Date(today);
    mon.setDate(today.getDate() + daysUntilMon);
    return DAYS.map((name, i) => {
      const d = new Date(mon);
      d.setDate(mon.getDate() + i);
      return { name, date: d };
    });
  }
  function fmt(d) {
    return d.toLocaleDateString('fr-FR', { day:'2-digit', month:'2-digit' });
  }

  // ── Render ────────────────────────────────────────────────────────
  let selectedDay = null;
  const weekDays = nextWeekDates();

  // Week range header
  document.getElementById('weekRange').textContent =
    `${fmt(weekDays[0].date)} – ${fmt(weekDays[3].date)}`;

  // Day buttons
  const grid = document.getElementById('dayGrid');
  weekDays.forEach(({ name, date }) => {
    const btn = document.createElement('div');
    btn.className = 'day-btn';
    btn.id = 'btn_' + name;
    btn.innerHTML = `${name}<span class="date-label">${fmt(date)}</span>`;
    btn.onclick = () => selectDay(name);
    grid.appendChild(btn);
  });

  function selectDay(day) {
    document.querySelectorAll('.day-btn').forEach(b => b.classList.remove('selected'));
    document.getElementById('btn_' + day).classList.add('selected');
    selectedDay = day;
    checkReady();
  }

  document.getElementById('wellpassCode').addEventListener('input', checkReady);
  document.getElementById('ghToken') && document.getElementById('ghToken').addEventListener('input', () => {
    localStorage.setItem('gh_token', document.getElementById('ghToken').value.trim());
    checkReady();
  });

  // Load saved token
  window.addEventListener('load', () => {
    const saved = localStorage.getItem('gh_token');
    if (saved) document.getElementById('ghToken').value = saved;
    checkReady();
  });

  function getToken() {
    return (document.getElementById('ghToken').value || localStorage.getItem('gh_token') || '').trim();
  }

  function checkReady() {
    const code = document.getElementById('wellpassCode').value.trim();
    const token = getToken();
    document.getElementById('reserveBtn').disabled = !(selectedDay && code.length > 2 && token.length > 10);
  }

  function toggleToken() {
    const el = document.getElementById('tokenSection');
    el.classList.toggle('visible');
  }

  // ── Reserve ───────────────────────────────────────────────────────
  async function reserve() {
    const code  = document.getElementById('wellpassCode').value.trim();
    const token = getToken();
    if (!selectedDay || !code || !token) return;

    const btn = document.getElementById('reserveBtn');
    btn.disabled = true;

    showStatus('loading', '<span class="spinner"></span>Déclenchement de la réservation…');

    try {
      const resp = await fetch(
        `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/${WORKFLOW_ID}/dispatches`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            ref: 'main',
            inputs: {
              chosen_day: selectedDay,
              wellpass_code: code
            }
          })
        }
      );

      if (resp.status === 204) {
        showStatus('success', `✅ Réservation lancée pour <strong>${selectedDay} 7h–8h</strong> !<br><br>Le script tourne dans le cloud (~2 min).<br>Vérifie le résultat sur GitHub Actions.`);
        // Lien vers les runs
        const runUrl = `https://github.com/${REPO_OWNER}/${REPO_NAME}/actions/workflows/${WORKFLOW_ID}`;
        document.getElementById('runLink').href = runUrl;
        document.getElementById('runLink').style.display = 'block';
      } else {
        const err = await resp.json().catch(() => ({}));
        showStatus('error', `❌ Erreur ${resp.status}<br>${err.message || 'Vérifie ton token GitHub.'}`);
        btn.disabled = false;
      }
    } catch(e) {
      showStatus('error', `❌ Erreur réseau<br>${e.message}`);
      btn.disabled = false;
    }
  }

  function showStatus(type, html) {
    const box = document.getElementById('statusBox');
    box.className = 'status ' + type;
    box.innerHTML = html;
    box.style.display = 'block';
  }
</script>
</body>
</html>
