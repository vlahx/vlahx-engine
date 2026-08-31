# 📜 Reguli de Proiect și Colaborare — VlahX Core 2.0

Acest fișier definește regulile de lucru și standardele de dezvoltare pentru proiectul **VlahX Engine**. Fiecare sesiune de lucru (AI agent & om) va consulta și respecta aceste reguli.

---

## 🟢 1. Mediu de Dezvoltare Exclusiv (DEV vs MAIN) & Promovare Cod
- **Dezvoltare EXCLUSIV pe DEV (`dev.vlahx.org` / `/opt/devapp`)**:
  - Toată munca de dezvoltare, adăugare de funcționalități, refactorizare, depanare și modificare de cod se execută **EXCLUSIV în mediul DEV** (`dev.vlahx.org`, container `dev-vlahx`, director `/opt/devapp`).
  - În mediul STABLE / PROD (`vlahx.org` / `/opt/vlahx`) NU se modifică și NU se testează direct cod.
- **Protocol Strict de Promovare pe MAIN (`vlahx.org`)**:
  - Transferul sau promovarea modificărilor din DEV în PROD (`vlahx.org`) se realizează **EXCLUSIV DUPĂ ce utilizatorul a verificat și a aprobat manual** în interfață că totul este 100% OK.
  - Verificările automate de status HTTP 200 ale agentului NU sunt suficiente pentru a promova codul în producție! Este obligatorie confirmarea omului.
- **Întreabă când există orice dubiu**: Când ceva este ambiguu sau neclar, agentul va întreba utilizatorul înainte de a scrie sau executa modificări de cod.

---

## 🧩 2. Izolarea Plugin-urilor & Integritatea Nucleului Core (Modular Architecture)
- **REGULĂ STRICTĂ DE CORE & PROMISIUNE**: Este STRICT INTERZISĂ modificarea, cârpirea sau alterarea codului din Core — **inclusiv rutele `/admin` (`app/routers/admin.py`), șabloanele administrative (`app/templates/admin/`), `app/core/` și `app/utils/`** — pentru a rezolva probleme de plugin, artificii de backup sau reinstalări din repozitoriu. Astfel de modificări în core/admin sunt capcane care strică arhitectura pe termen lung.
- **Aprobat Special pentru Modificări în Core / Admin**: Codul din Core și din `/admin` poate fi modificat **EXCLUSIV cu aprobare specială din partea utilizatorului, în urma unei discuții prealabile explicite**.
- **Fără Modificări în Core pentru Plugin-uri**: Modificările, funcționalitățile noi, logica de tratare a erorilor și setările specifice unui plugin se scriu **STRICT în interiorul directorului acelui plugin** (`app/plugins/<plugin_name>/`) sau în serverul de repozitoriu (`vlahx-repo`). NU se modifică fișiere din core pentru a acomoda un plugin.
- **Instalare Exclusiv din Repozitoriu**: Instalarea și reinstalarea plugin-urilor se efectuează întotdeauna din repozitoriul oficial (`/admin/repo` / URL descărcare externă), NU din backup-uri locale, directoare provizorii sau artificii în core.
- **Fără Domenii Hardcodate în Cod**: VlahX Engine este o platformă generică CMS pentru orice utilizator. Este STRICT INTERZISĂ hardcodarea de domenii specifice (ex: `dev.vlahx.org`, `vlahx.org`) în codul sursă, în mesaje de alertă sau în șabloane HTML. Totul trebuie dezvoltat generic și configurabil.

---

## 📁 3. Regula Strictă de Organizare a Codului (`app/`)
- **Fără Fișiere în Afara `app/`**: Este STRICT INTERZISĂ crearea, scoaterea sau împrăștierea fișierelor/directoarelor de cod sursă în afara directorului `app/`.
- **Structură Izolată**:
  - Tot codul sursă al aplicației (`core`, `models`, `routers`, `plugins`, `templates`, `themes`, `utils`, `locales`) trăiește exclusiv în interiorul directorului `app/`.
  - Baza de date SQLite trăiește separat în directorul `db/`.
  - Rădăcina proiectului conține doar fișierele de configurare de bază (`main.py`, `run.py`, `Dockerfile`, `docker-compose.yml`, `requirements.txt`).

---

## 💻 4. Arhitectură & Mediu de Lucru pe Server (192.168.1.11 via SSH)
- **Sistem Dual Container pe Server (`192.168.1.11`)**:
  - 🟢 **Container STABLE / PROD (`vlahx`)**: Susține site-ul principal (`vlahx.org`) din directorul `/opt/vlahx`.
  - 🧪 **Container DEV (`dev-vlahx`)**: Susține mediul de dezvoltare (`dev.vlahx.org`) pe portul `8002` din directorul `/opt/devapp`.
- **Protocol de Conectare SSH**: `cari@192.168.1.11`
- **Stocare 4TB (`/mnt/4T`) & Backup Automat Zilnic**: Cron Job zilnic la 03:00 AM în `/mnt/4T/backups/vlahx.org/`.
- **Pauză pe Git Public**: NU se trimite cod pe Git public fără aprobare.

---

## 🎯 5. Fluxul de Lucru pe Task-uri
- **Centrare pe Task Curent**: Fiecare sesiune se concentrează pe un singur task din [`docs/TODO.md`](TODO.md).
- **Evidența Stării**: La începutul unui task, acesta se marchează ca `[in progress]`, iar la final ca `[x] Completed`.
- **Completare Incrementală**: Schimbările majore se fac în etape mici, ușor de testat și de urmărit.

---

## 🧪 6. Calitate și Testare
- **Verificare Obligatorie**: Modificările se testează pe `dev.vlahx.org` și se supun verificării utilizatorului.
- **Fără Patch-uri de Suprafață**: Erorile se rezolvă la cauză, nu prin ignorare/suprimare de excepții.
- **Conservarea API-urilor**: Se păstrează compatibilitatea înapoi pentru rutele API și plugin-uri.

---

## 🛡️ 7. Securitate și Siguranța Datelor
- **Protecție Date**: Nu se șterg baze de date de producție sau fișiere `.env` fără confirmare explicită.
- **Sanitizare**: Input-urile utilizatorilor și rutele API trebuie sanitizate și securizate contra XSS / CSRF / SQL Injection.

---

*Reguli create: 22 August 2026 | Actualizate conform directivelor utilizatorului: 26 August 2026*
