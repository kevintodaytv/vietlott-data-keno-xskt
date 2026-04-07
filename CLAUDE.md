# CLAUDE.md — Sniper-X Hub: Claude AI Specific Instructions

> This file provides Claude-specific context. Always read AGENTS.md first for full project overview.

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

- `nexus-frontend/src/routes/+page.svelte` — Main dashboard (PRIMARY TARGET)
- `nexus-frontend/src/lib/QuantumSphere.svelte` — Three.js 3D sphere
- `core-backend/main.py` — FastAPI endpoints
- `core-backend/scraper/` — Playwright scraping logic
- `docker-compose.yml` — Infrastructure orchestration

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
