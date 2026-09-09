# 📝 VlahX Engine — Development TODO & Roadmap

## 🚀 Desktop Node & Cloudflare Tunnel (`vlahx.exe`)

Concept: Transform orice PC/Laptop cu Windows într-un server web Plug & Play gata de producție, fără cunoștințe de Linux, Docker, IP public fix sau port forwarding pe router.

### 🎯 1. Auto-Detect & Portable Python (`vlahx.exe`)
- [ ] Verificare dacă Python 3.11+ este instalat în `PATH` pe Windows.
- [ ] Dacă lipsește, descarcă automat `python-3.11.x-embed-amd64.zip` (Python portabil fără installer).
- [ ] Creare `.venv` și instalare automată dependențe din `requirements.txt`.
- [ ] Pornire server Uvicorn (`python run.py`).

### 🌐 2. Cloudflare Tunnels Integration (`cloudflared`)
- [ ] Trecere peste orice router/CGNAT/ADSL fără port forwarding sau IP public.
- [ ] Descarcă executabilul oficial `cloudflared.exe` la prima pornire.
- [ ] Câmp în Admin Settings pentru `CLOUDFLARE_TUNNEL_TOKEN`.
- [ ] Pornire tunel securizat cu HTTPS automat furnizat de Cloudflare.

### 🛠️ 3. Windows Tray / Service
- [ ] Opțiune de auto-start la pornirea Windows.
- [ ] Indicator de stare în sistem (Local Port & Domeniu Public).
