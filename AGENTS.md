# 🧠 AGENTS.md — Sniper-X Hub AI Directive File
> Generated via autoskills-compatible manual setup | Version: 1.0.0

## 📌 PROJECT OVERVIEW: SNIPER-X HUB

**Mission**: Real-time AI-powered lottery prediction system for XSKT (Xổ Số Kiến Thiết) Vietnam.

**Codename**: Sniper-X / Alien-Nexus / X-Predictor Hub

**Architecture**: Full-stack autonomous prediction ecosystem with:
- **Frontend**: SvelteKit + Three.js + Tailwind CSS (Cyberpunk/Hologram aesthetic)
- **Backend**: FastAPI (Python) + Playwright scraping engine (Port: **8888**)
- **AI Engine**: GSB Engine (Ghost Scraper + Brain) with Redis queue worker model
- **Infrastructure**: Docker Compose — all services networked together
- **Data Sources**: Real-time Vietnamese lottery results (XSKT, Keno)

---

## 🗂️ MONOREPO STRUCTURE

```
XSKT/
├── nexus-frontend/          # SvelteKit frontend (Port: 5173 dev / 3000 prod)
│   ├── src/
│   │   ├── routes/
│   │   │   ├── +page.svelte     # Main landing/dashboard page
│   │   │   └── +layout.svelte   # Root layout
│   │   └── lib/
│   │       └── QuantumSphere.svelte  # Three.js 3D sphere component
│   ├── package.json
│   └── vite.config.ts
├── core-backend/            # FastAPI backend (Port: 8000)
│   ├── main.py              # FastAPI app entry point
│   ├── scraper/             # Playwright browser automation scrapers
│   └── inspect_selector.py  # CSS selector inspection utilities
├── modules/                 # Shared AI/prediction modules
├── infrastructure/          # Docker, nginx, reverse proxy configs
└── docker-compose.yml       # Orchestrates all services
```

---

## 🎯 AI AGENT RULES

### CRITICAL CONSTRAINTS — NEVER VIOLATE

1. **NO MOCK DATA** — All data must come from real-time scraping. Never hardcode fake numbers.
2. **CYBERPUNK AESTHETIC** — The UI MUST maintain Cyberpunk/Hologram theme:
   - Primary color: `cyan-400` / `#22d3ee`
   - Background: `#050505` (near-black)
   - Font: Monospace (`font-mono`)
   - Effects: Glows, scanlines, neon borders
3. **Vietnamese Lottery Context** — Numbers are XSKT results, not arbitrary data
4. **Proxy Pattern** — Frontend at port 3333 proxies `/api/*` to backend at port **8888** (Vite proxy config in `vite.config.ts`)

### TECH STACK RULES

#### Frontend (SvelteKit)
- Svelte 4 syntax (NOT Svelte 5 runes syntax — project uses `^4.2.15`)
- Use `on:click` not `onclick` (Svelte 4)
- TailwindCSS v4 with PostCSS — utility classes work
- Three.js via `@threlte/core` and `@threlte/extras`
- TypeScript strict mode

#### Backend (FastAPI + Python)
- Python 3.11+
- Playwright for browser automation (NOT requests/BeautifulSoup for JS-rendered pages)
- FastAPI with async/await patterns
- CORS enabled for localhost:5173

#### Scraping
- Target sites use anti-bot protection (Cloudflare) — use Playwright with full browser context
- Always handle Vietnamese encoding (UTF-8)
- Set timeouts: 90s for page loads on target XSKT sites

---

## 🔌 API ENDPOINTS

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/ignite-prediction` | Trigger scrape + AI prediction |
| GET | `/api/health` | Health check |
| GET | `/api/latest-results` | Latest lottery results |
| WebSocket | `/ws/stream` | Real-time data stream |

---

## 🐛 KNOWN ISSUES & SOLUTIONS

### Issue: `Internal Server Error` on prediction
**Root Cause**: Playwright timeout when Cloudflare blocks the scraper
**Solution**: Use extended timeout (90s), rotate user agents, add delay before scrape

### Issue: Vietnamese encoding broken
**Root Cause**: Response encoding not set to UTF-8
**Solution**: Always `response.encoding = 'utf-8'` in Python, `.decode('utf-8')` for bytes

### Issue: CORS errors from frontend
**Root Cause**: Direct fetch to port 8000 from browser
**Solution**: Always use `/api/` relative URLs — Vite proxy handles the forwarding

---

## 🚀 DEVELOPMENT COMMANDS

```bash
# Start frontend dev server
cd nexus-frontend && npm run dev

# Start backend (MUST use port 8888 — Vite proxy target)
cd core-backend && uvicorn main:app --host 0.0.0.0 --port 8888 --reload

# Start everything with Docker
docker-compose up -d

# Stop and clean
docker-compose down -v
```

---

## 🎨 DESIGN SYSTEM

### Colors
```css
--primary: #22d3ee;       /* cyan-400 */
--primary-dark: #0e7490;  /* cyan-700 */
--bg-base: #050505;        /* near-black */
--bg-panel: rgba(8, 145, 178, 0.1); /* cyan glass */
--text-primary: #22d3ee;
--text-dim: #0891b2;
--glow: 0 0 25px rgba(6, 182, 212, 0.8);
```

### Typography
- Headings: `font-mono uppercase tracking-widest`
- Body: `font-mono`
- Numbers: `font-black text-2xl`

### Component Patterns
- Borders: `border border-cyan-500/30`
- Glass panels: `bg-cyan-950/20 backdrop-blur-md`
- Hover glow: `hover:shadow-[0_0_40px_rgba(6,182,212,0.6)]`
- Animations: CSS keyframes, no external animation libraries

---

## 📡 DATA FLOW

```
XSKT Website
    ↓ (Playwright scrape)
FastAPI Backend (port 8000)
    ↓ (GSB AI Engine processes)
Redis Queue
    ↓ (Worker prediction)
FastAPI Response → /api/ignite-prediction
    ↓ (Vite proxy /api → :8000)
SvelteKit Frontend (port 5173)
    ↓ (Svelte reactive stores)
3D Visualization (Three.js sphere + Matrix grid)
```

---

## 🗄️ DATABASE — SUPABASE

**Source**: https://github.com/supabase/supabase

Dự án sử dụng **Supabase** làm database backend cho persistence layer.

### Setup
```bash
# Cài SDK Python
pip install "supabase>=2.4.0"

# Biến môi trường cần thiết (xem .env.example)
SUPABASE_URL=https://YOUR_PROJECT_ID.supabase.co
SUPABASE_ANON_KEY=YOUR_ANON_KEY
SUPABASE_SERVICE_KEY=YOUR_SERVICE_KEY
```

### Schema (core-backend/database/schema.sql)
| Table | Mục đích |
|-------|----------|
| `lottery_results` | Kết quả xổ số thực + dự đoán AI |
| `ai_training_metrics` | Metrics mỗi epoch training |
| `number_frequency` | Tần suất xuất hiện từng số |
| `prediction_sessions` | Lịch sử phiên dự đoán |

### Client Module (core-backend/database/)
```python
from database import save_lottery_result, get_recent_results
```

### Realtime
- Bảng `lottery_results` và `prediction_sessions` enable Realtime
- Subscribe qua `subscribe_to_results(callback)` trong background worker

### Rules
- Dùng **anon key** cho read operations từ frontend
- Dùng **service key** chỉ trong backend Python server
- Row Level Security (RLS) đã bật — xem schema.sql cho policies
- KHÔNG hardcode key vào source code — luôn đọc từ `os.getenv()`

---

## 🎨 DESIGN SYSTEM — AWESOME-DESIGN-MD

**Source**: https://github.com/VoltAgent/awesome-design-md

File `DESIGN.md` trong project root là design reference cho AI agents.
Được lấy từ bộ sưu tập `awesome-design-md` — format Supabase dark theme.

### Key Tokens (từ DESIGN.md)
```css
/* Backgrounds */
--bg-page:    #171717;
--bg-button:  #0f0f0f;

/* Brand Green (dùng sparingly) */
--green:      #3ecf8e;
--green-link: #00c573;
--green-border: rgba(62, 207, 142, 0.3);

/* Text */
--text-primary:   #fafafa;
--text-secondary: #b4b4b4;
--text-muted:     #898989;

/* Borders */
--border-subtle:   #242424;
--border-standard: #2e2e2e;
--border-prominent:#363636;
```

### Cách dùng với AI
Khi yêu cầu AI tạo UI mới, reference file này:
> "Build this component following DESIGN.md in project root"
