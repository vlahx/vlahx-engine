## 📁 1. Regula Strictă de Organizare a Codului (`app/`)
- **Fără Fișiere în Afara `app/`**: Este STRICT INTERZISĂ crearea, scoaterea sau împrăștierea fișierelor/directoarelor de cod sursă în afara directorului `app/`.
- **Structură Izolată**:
  - Tot codul sursă al aplicației (`core`, `models`, `routers`, `plugins`, `templates`, `themes`, `utils`, `locales`) trăiește exclusiv în interiorul directorului `app/`.
  - Baza de date SQLite trăiește separat în directorul `db/`.
  - Rădăcina proiectului conține doar fișierele de configurare de bază (`main.py`, `run.py`, `Dockerfile`, `docker-compose.yml`, `requirements.txt`).
  
## 2. Regula de lucru la plugnuri si themes
- nu se depaseste directorul app/plugins pentru a scrie cod sub nici o forma. Vlahx Core 3.0.0 este capabil sa sustine orice fel si tip de plugin fara a copia fisiere in el
- tot ce este core va ramane neatins, aici nu se mai scrie cod
- intr-o tema noua sau intr-una nou instalata, fisierul .css al temei nu mai pleca in static, el suporta un merge din directorul themes in /app/static/css/themes.css.
- orice theme sau plugin sters sau dezinstalat nu va lasa veo urma in /app, in urma lui nu ramane decat baza de date specifica lui si creata separat in diectorul /db care daca e stearsa manual nu va afecta cu nimic aplicatia
