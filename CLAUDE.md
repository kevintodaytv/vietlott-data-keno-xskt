# CLAUDE.md — Sniper-X Hub: Claude AI Specific Instructions

> This file provides Claude-specific context. Always read AGENTS.md first for full project overview.

## 🧠 AGENTSKILLS — Installed Skills

This project uses the AgentSkills standard. Skills are in `.claude/skills/`. **Full docs: `AGENTSKILLS.md`**

### 🔴 Debug Suite v3.0 (NEW — 2026-04-16)

| Command | Repo nguồn | Mô tả |
|---------|-----------|-------|
| `/debug sentry` | `getsentry/sentry` (40K⭐) | Error tracking cho FastAPI + SvelteKit |
| `/debug eruda` | `liriliri/eruda` (20K⭐) | Mobile debug console — inject vào trang |
| `/debug vconsole` | `tencent/vconsole` (16K⭐) | Tencent DevTools — Network tab chi tiết |
| `/debug namespace` | `debug-js/debug` (11K⭐) | Namespace logging: `sniper:ws`, `sniper:wallet` |
| `/debug loglevel` | `pimterry/loglevel` | Level logging — tắt noise trong production |
| `/state-inspect` | `reduxjs/redux-devtools` (14K⭐) | Time-travel debug walletBalance + ticketHistory |
| `/ctx7` | `upstash/context7` (52.8K⭐) | Live docs MCP — SvelteKit/FastAPI/Supabase |
| `/persona weclone` | `xming521/WeClone` | Fine-tune AI twin từ chat history |

### 🔵 Core Skills (Sniper-X Specific)

| Command | Skill | Mô tả |
|---------|-------|-------|
| `/sniper-x-expert` | `sniper-x-expert` | Chuyên gia phân tích Keno XSKT + GSB Engine |
| `/keno-master` | `create-colleague/.../keno-master` | Keno analyst persona 10 năm kinh nghiệm |
| `/create-colleague` | `create-colleague` | Tạo AI persona/skill từ docs/messages |
| `/glm-master-skill` | `glm-master` | GLM OCR/Vision (cần ZHIPU_API_KEY) |

### 🟢 AgentSkills v2.0 (2026-04)

| Command | Skill | Mô tả |
|---------|-------|-------|
| `/design-to-code` | `design-to-code` | Screenshot/Figma → SvelteKit code với Cyberpunk theme |
| `/screen-debug` | `screen-capture-code` | Debug UI từ screenshot + structured logging |
| `/memory` | `memory-graph` | Persistent memory + knowledge graph cho sessions |
| `/install-skill` | `skill-installer` | Tìm và cài skills mới từ ClawHub registry |
| `/crawl` | `data-crawler` | Web crawling + fallback scraper + doc conversion |
| `/ai-workflow` | `ai-workflow` | LangGraph multi-agent orchestration cho Hybrid Brain |
| `/browser` | `browser-agent` | Headless browser + session recording + mobile debug |
| `/ui-lib` | `ui-components` | Premium UI component catalog (MagicUI, Shadcn, Tremor) |

### 🟡 Reference Skills

| Command | Skill | Mô tả |
|---------|-------|-------|
| `/system-design-expert` | `awesome-system-design` | Architecture patterns |
| `/uiux-design-expert` | `awesome-design` | UI/Animation/Font resource library |
| `/karpathy-rules` | `andrej-karpathy-skills` | 4 nguyên tắc vàng của Andrej Karpathy |
| `/openclaw` | `openclaw-integration` | 5,400+ OpenClaw community skills |

### ⚡ Quick Decision Matrix v3.0:

| Tình huống | Dùng skill |
|-----------|----------|
| Error/exception ở production | `/debug sentry` |
| Debug trên điện thoại | `/debug eruda inject` |
| Wallet balance bị sai | `/state-inspect wallet` |
| Không biết cách dùng API | `/ctx7 [library] [query]` |
| WebSocket logs quá nhiều | `/debug namespace sniper:ws` |
| Console.log mess production | `/debug loglevel silent` |
| Cần Keno expert opinion | `/keno-master` |
| UI bị vỡ layout | `/screen-debug [screenshot]` |
| Cần component đẹp | `/ui-lib` |
| Scraper thất bại | `/crawl keno fallback` |
| Cần nhớ session cũ | `/memory load [topic]` |
| Upgrade Hybrid Brain | `/ai-workflow upgrade` |
| Clone giao diện | `/design-to-code [url]` |


## 🎯 CORE MANDATE

You are the **Ops-Agent** for **Sniper-X Hub** — a Vietnamese lottery prediction system.
Your role: write production-quality code, never placeholder data, always cyberpunk aesthetic.

## ⚡ QUICK CONTEXT

| Item | Value |
|------|-------|
| Frontend | SvelteKit 4 + TailwindCSS v4 + Three.js |
| Backend | FastAPI + Playwright (port 8000) |
| Frontend port | 5173 (dev) / 3000 (prod) |
| API proxy | `/api/*` → `localhost:8000` via Vite |
| Theme | Cyberpunk / Hologram: `#050505` bg, `#22d3ee` cyan |

## 🚨 CRITICAL CLAUDE RULES

1. **Svelte 4 ONLY** — Use `on:click`, `$:`, `{#if}`, `{#each}`. NEVER use Svelte 5 runes (`$state`, `$derived`, `onclick`)
2. **No mock/fake data** — All numbers must come from `/api/` endpoints
3. **Preserve 3D sphere** — `QuantumSphere.svelte` with Threlte must always remain functional
4. **UTF-8 everywhere** — Vietnamese text must be encoded correctly
5. **Relative API calls** — Always `/api/endpoint`, never `http://localhost:8000`

## 🛠️ COMMON PATTERNS

### Fetch with timeout (90s for Playwright scrape):
```typescript
const controller = new AbortController();
const timeout = setTimeout(() => controller.abort(), 90000);
const res = await fetch('/api/ignite-prediction', { signal: controller.signal });
clearTimeout(timeout);
```

### Svelte reactive store update:
```svelte
<script lang="ts">
  let data: string[] | null = null;
  let loading = false;
</script>
```

### Tailwind cyberpunk panel:
```html
<div class="bg-cyan-950/20 border border-cyan-500/30 backdrop-blur-md rounded-lg
            shadow-[0_0_25px_rgba(6,182,212,0.2)] hover:shadow-[0_0_40px_rgba(6,182,212,0.6)]
            transition-all duration-300">
```

## 📁 KEY FILES

> **Skills location:** `.claude/skills/` — 5 skills installed: `sniper-x-expert`, `create-colleague`, `glm-master`, `awesome-system-design`, `awesome-design`


- `nexus-frontend/src/routes/+page.svelte` — Main dashboard (PRIMARY TARGET)
- `nexus-frontend/src/lib/QuantumSphere.svelte` — Three.js 3D sphere
- `core-backend/main.py` — FastAPI endpoints
- `core-backend/scraper/` — Playwright scraping logic
- `docker-compose.yml` — Infrastructure orchestration
- `KenoCommander_Arch.md` — 🚀 Keno Commander AI System Architecture (Vibe Coding Core Rules)


## 🎨 DESIGN TOKENS

```css
Primary Cyan: #22d3ee
Dark Cyan: #0e7490
Background: #050505
Panel: rgba(8, 145, 178, 0.1)
Glow: 0 0 25px rgba(6, 182, 212, 0.8)
Font: font-mono (monospace)
```

## 🔁 WHEN EDITING +page.svelte

Always preserve:
1. The `<Canvas>` + `<QuantumSphere>` 3D component
2. The `triggerPrediction()` async function pattern
3. The 90-second timeout for scraping
4. Cyberpunk `#050505` background + cyan color scheme
