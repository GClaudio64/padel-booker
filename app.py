# 🎾 UCPA Padel Booker

Réserve automatiquement ton terrain de padel à l'UCPA Paris 19e.

## Installation (une seule fois)

1. Assure-toi d'avoir **Python** installé sur ton PC
   - Si non : https://www.python.org/downloads/
   - ⚠️ Coche "Add Python to PATH" pendant l'installation

2. Double-clique sur **INSTALLER.bat**
   - Ça installe tout automatiquement (Flask, Playwright, Chromium)

## Utilisation chaque semaine

1. **Sur ton PC** : double-clique sur **LANCER_PADEL_BOOKER.bat**
   - Une fenêtre noire s'ouvre et affiche une adresse IP (ex: `http://192.168.1.X:5000`)

2. **Sur ton iPhone** : ouvre Safari et tape cette adresse

3. **Dans l'interface** :
   - Choisis ton jour (Lundi / Mardi / Mercredi / Jeudi)
   - Saisis ton code egym Wellpass du jour
   - Appuie sur **Réserver**
   - Le script réserve automatiquement et te confirme ✅

## Notes

- Ton PC doit être allumé et connecté au même WiFi que ton iPhone
- Le script se connecte automatiquement à ton compte UCPA
- Il privilégie le terrain 7 si les deux sont libres
- Le participant est automatiquement renseigné : Guillaume Fourcade

## Dépannage

- **"Erreur réseau"** → vérifie que le PC et l'iPhone sont sur le même WiFi
- **"Pas de terrain disponible"** → le créneau est complet pour ce jour
- **Statut incertain** → va vérifier manuellement sur ucpa.com
