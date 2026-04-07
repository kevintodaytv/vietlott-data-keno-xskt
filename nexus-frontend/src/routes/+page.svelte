<script lang="ts">
  import { Canvas } from '@threlte/core';
  import QuantumSphere from '$lib/QuantumSphere.svelte';
  import CognitionGauge from '$lib/CognitionGauge.svelte';
  import { onMount } from 'svelte';

  // ─── STATE ────────────────────────────────────────────────────────────────
  let isAnalyzing = false;
  let predictionData: string[] | null = null;
  let confidenceLevel: number | null = null;
  let status: 'SECURE' | 'RED_ALERT' = 'SECURE';
  let terminalLogs: string[] = ['>> SYSTEM_IDLE: WAITING FOR COMMAND...'];
  let countdown = '00:00:00';
  let bootComplete = false;
  let bootLines: string[] = [];
  let showGrid = false;
  let activeSkill = -1;

  // ─── TABS & TERRITORY STATE ───────────────────────────────────────────────
  let selectedRegion = 'VIETLOTT';
  let activeProvince = '';
  let sphereColor = '#06b6d4';
  let predictionMatrix: Record<string, string[]> | null = null;
  let heatmapData: Record<string, number> = {};
  let anchors: number[] = [];

  // ─── KENO STATE ───────────────────────────────────────────────────────────
  let kenoHeatmap: Record<number, number> = {};
  let kenoAnchors: number[] = [];
  let kenoNextDraw = '00:00:00';
  let kenoDrawCount = 0;
  let kenoLatestDraw: number | null = null;
  let kenoLatestWinningNumbers: number[] = [];
  let kenoValidationData: { hit_count: number; win_rate: number; matching_numbers: number[]; reward?: number; profit?: number; profit_status?: string } | null = null;

  
  // ─── ERROR HANDLING & ZERO-MOCK ───────────────────────────────────────────
  let statusMessage = "SYSTEM_READY: WAITING FOR INSTRUCTION";
  let realSamplesCount = 0;
  let hasCriticalError = false;
  
  $: gridMax = selectedRegion === 'VIETLOTT' ? 45 : 99;
  $: gridCols = selectedRegion === 'VIETLOTT' ? 'grid-cols-9' : 'grid-cols-10';

  const TUESDAY_SCHEDULE: Record<string, string[]> = {
    "MB": ["Quảng Ninh"],
    "MT": ["Đắk Lắk", "Quảng Nam"],
    "MN": ["Bến Tre", "Vũng Tàu", "Bạc Liêu"]
  };

  const regionColors: Record<string, string> = {
    'MB':      '#ef4444', // Red
    'MT':      '#10b981', // Emerald
    'MN':      '#3b82f6', // Blue
    'VIETLOTT':'#06b6d4', // Cyan
    'KENO':    '#a855f7', // Purple — Neon Keno
  };

  $: {
    sphereColor = regionColors[selectedRegion] || '#06b6d4';
  }

  async function switchRegion(regionId: string) {
    selectedRegion = regionId;
    // reset results on tab switch
    heatmapData = {}; anchors = []; predictionMatrix = null;
    kenoHeatmap = {}; kenoAnchors = [];
    if (regionId !== 'VIETLOTT' && regionId !== 'KENO') {
      activeProvince = TUESDAY_SCHEDULE[regionId][0];
    }
  }

  // ─── COUNTDOWN TIMER ──────────────────────────────────────────────────────
  function updateCountdown() {
    const now = new Date();
    // XSKT Miền Nam kết quả lúc 16:15 và 18:00 mỗi ngày
    const draws = [{ h: 16, m: 15 }, { h: 18, m: 0 }];
    let minDiff = Infinity;
    for (const d of draws) {
      const draw = new Date(now);
      draw.setHours(d.h, d.m, 0, 0);
      if (draw <= now) draw.setDate(draw.getDate() + 1);
      const diff = draw.getTime() - now.getTime();
      if (diff < minDiff) minDiff = diff;
    }
    const h = Math.floor(minDiff / 3600000);
    const m = Math.floor((minDiff % 3600000) / 60000);
    const s = Math.floor((minDiff % 60000) / 1000);
    countdown = `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  }

  // ─── TERMINAL LOG ─────────────────────────────────────────────────────────
  function addLog(msg: string) {
    const ts = new Date().toISOString().substring(11, 19);
    terminalLogs = [...terminalLogs.slice(-6), `[${ts}] >> ${msg}`];
  }

  // ─── BOOT SEQUENCE ────────────────────────────────────────────────────────
  const bootSequence = [
    'KHỞI ĐỘNG SNIPER-X NEURAL CORE v6.0...',
    'Kết nối Ghost Scraper Agent... [OK]',
    'Kiểm tra kênh XSKT Miền Nam... [OK]',
    'Nạp ma trận dự báo lượng tử... [OK]',
    'QuantumSphere Module... [CALIBRATED]',
    'GSB AI Engine... [ONLINE]',
    'APEX COMMAND CENTER — SẴN SÀNG.',
  ];

  onMount(() => {
    updateCountdown();
    const clock = setInterval(updateCountdown, 1000);

    // Audio Context Setup for Alarm Sound
    const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
    function playAlarm() {
        if (audioCtx.state === 'suspended') audioCtx.resume();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.type = 'square';
        osc.frequency.setValueAtTime(800, audioCtx.currentTime);
        osc.frequency.setValueAtTime(600, audioCtx.currentTime + 0.1);
        gain.gain.setValueAtTime(0.05, audioCtx.currentTime);
        osc.start();
        setTimeout(() => osc.stop(), 300);
    }

    // WebSocket Configuration
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.hostname}:8000/ws/keno`;
    const socket = new WebSocket(wsUrl);
    socket.onmessage = (event) => {
        if (event.data === "NEW_DRAW_DETECTED") {
            addLog("📡 TÍN HIỆU MỚI TỪ MINH NGỌC: ĐANG TỰ ĐỘNG CẬP NHẬT...");
            playAlarm();
            if (status !== 'RED_ALERT') {
                triggerPrediction(); // Auto Execute
            }
        }
    };
    socket.onclose = () => {
        addLog("⚠️ MẤT KẾT NỐI WEBSOCKET BE. ĐANG THỬ KHÔI PHỤC NGẦM...");
    };

    let i = 0;
    const boot = setInterval(() => {
      if (i < bootSequence.length) {
        bootLines = [...bootLines, bootSequence[i]];
        i++;
      } else {
        clearInterval(boot);
        setTimeout(() => { bootComplete = true; showGrid = true; }, 500);
      }
    }, 280);

    return () => { clearInterval(clock); clearInterval(boot); };
  });

  // ─── SKILLS DATA ──────────────────────────────────────────────────────────
  const skills = [
    { name: 'SvelteKit',    tag: 'Frontend',    icon: '⬡', status: 'ACTIVE'   },
    { name: 'Three.js',     tag: '3D Engine',   icon: '◈', status: 'ACTIVE'   },
    { name: 'FastAPI',      tag: 'Backend',     icon: '⚡', status: 'ONLINE'   },
    { name: 'Playwright',   tag: 'Scraper',     icon: '🕷', status: 'STANDBY'  },
    { name: 'GSB Engine',   tag: 'AI Core',     icon: '🧠', status: 'ACTIVE'   },
    { name: 'TailwindCSS',  tag: 'Styling',     icon: '✦', status: 'ACTIVE'   },
    { name: 'TypeScript',   tag: 'Language',    icon: '⟨⟩', status: 'ACTIVE'  },
    { name: 'Docker',       tag: 'Infra',       icon: '◻', status: 'ONLINE'   },
    { name: 'Redis',        tag: 'Queue',       icon: '⏺', status: 'STANDBY'  },
    { name: 'XSKT Probe',   tag: 'Data Source', icon: '📡', status: 'SCANNING' },
    { name: 'Keno Probe',   tag: 'Data Source', icon: '📡', status: 'SCANNING' },
    { name: 'Quantum Pred', tag: 'AI',          icon: '∞', status: 'READY'    },
  ];

  // ─── IGNITE PREDICTION ────────────────────────────────────────────────────
  async function triggerPrediction() {
    isAnalyzing = true;
    predictionData = null;
    predictionMatrix = null;
    status = 'RED_ALERT';
    
    if (selectedRegion === 'VIETLOTT') {
      addLog('KÍCH HOẠT QUY TRÌNH TRUY XUẤT LƯỢNG TỬ...');
      addLog('ĐANG XUYÊN THỦNG TƯỜNG LỬA CLOUDFLARE...');
    } else if (selectedRegion === 'KENO') {
      addLog('⚡ KENO OVERCLOCK MODE — TRUY XUẤT THE VAULT...');
      addLog('🔮 ĐANG PHÂN TÍCH 80 SỐ LƯỢNG TỬ...');
    } else {
      addLog(`MỤC TIÊU: ${activeProvince.toUpperCase()}... INITIALIZING.`);
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 90000);

    try {
      let res;
      if (selectedRegion === 'VIETLOTT') {
        res = await fetch('/api/ignite-prediction', { signal: controller.signal });
      } else if (selectedRegion === 'KENO') {
        res = await fetch('/api/ignite-keno', { signal: controller.signal });
      } else {
        res = await fetch(`/api/nexus-predict?region=${selectedRegion}&province=${activeProvince}`, { signal: controller.signal });
      }
      clearTimeout(timeout);
      
      if (res.status === 404) {
        hasCriticalError = true;
        statusMessage = "CRITICAL_ERROR: NO REAL DATA FOUND IN SUPABASE. ZERO-MOCK POLICY ENFORCED.";
        addLog(statusMessage);
        isAnalyzing = false;
        status = 'SECURE';
        heatmapData = {};
        anchors = [];
        return;
      }
      
      const data = await res.json();

      if (data.status === 'SUCCESS') {
        hasCriticalError = false;
        realSamplesCount = data.data_points_used || 0;

        if (selectedRegion === 'KENO') {
          statusMessage = `KENO RADAR: ${realSamplesCount} KỲ THẬT | #${data.latest_draw_id}`;
          addLog(`✓ VAULT LOCK: ${realSamplesCount} KỲ KENO GIẢI MÃ XONG.`);
          setTimeout(() => {
            kenoHeatmap   = data.heatmap || {};
            kenoAnchors   = data.anchors || [];
            kenoNextDraw  = data.next_draw_countdown || '00:00:00';
            kenoDrawCount = data.draw_count || 0;
            kenoLatestDraw = data.latest_draw_id || null;
            kenoLatestWinningNumbers = data.latest_winning_numbers || [];
            kenoValidationData = data.validation || null;
            confidenceLevel = data.confidence;
            addLog(`🎯 ${kenoAnchors.length} KENO ANCHORS LOCKED. CONF: ${data.confidence}%`);
            isAnalyzing = false;
            status = 'SECURE';
          }, 800);
        } else {
          statusMessage = `ANALYZING ${realSamplesCount} REAL SAMPLES FROM THE VAULT.`;
          if (selectedRegion === 'VIETLOTT') {
             addLog('TRUY XUẤT THÀNH CÔNG. ĐANG GIẢI MÃ TỌA ĐỘ...');
          } else {
             addLog(`SCANNING TERRITORY: ${activeProvince.toUpperCase()}... DATA ACQUIRED.`);
          }
          setTimeout(() => {
            if (selectedRegion === 'VIETLOTT') {
              predictionData = data.ai_prediction;
              heatmapData = data.heatmap || {};
              anchors = data.anchors || [];
              addLog(`KHÓA MỤC TIÊU: ${data.ai_prediction?.length ?? 0} ĐIỂM NEO ĐÃ XÁC ĐỊNH.`);
            } else {
              predictionMatrix = data.prediction_matrix;
              addLog(`THẾ TRẬN KÍCH HOẠT: HIỂN THỊ MA TRẬN.`);
            }
            confidenceLevel = data.confidence;
            isAnalyzing = false;
            status = 'SECURE';
          }, 800);
        }
      } else {
        addLog(`LỖI AGENT: ${data.error || data.detail || 'PHẢN HỒI KHÔNG XÁC ĐỊNH.'}`);
        isAnalyzing = false;
        status = 'SECURE';
      }
    } catch (error: any) {
      clearTimeout(timeout);
      if (error.name === 'AbortError') {
        addLog('TIMEOUT (>90s): SCOUT BỊ TẮT KẾT NỐI. THỬ LẠI.');
      } else {
        addLog('LỖI CHÍ MẠNG: KHÔNG THỂ KẾT NỐI THE CORE.');
      }
      isAnalyzing = false;
      status = 'SECURE';
    }
  }

  function getStatusColor(s: string) {
    if (s === 'ACTIVE')   return '#22d3ee';
    if (s === 'ONLINE')   return '#34d399';
    if (s === 'STANDBY')  return '#f59e0b';
    if (s === 'SCANNING') return '#a78bfa';
    if (s === 'READY')    return '#f472b6';
    return '#22d3ee';
  }
</script>

<!-- ════════════════════════════════════════════════════════════ -->
<!--  SNIPER-X HUB — v6.0 APEX COMMAND CENTER                   -->
<!-- ════════════════════════════════════════════════════════════ -->
<div class="app-root" class:red-alert={status === 'RED_ALERT'} style="display:flex;flex-direction:column;align-items:center;overflow-x:hidden;">

  <!-- SCANLINES -->
  <div class="scanlines" aria-hidden="true"></div>

  <!-- RED ALERT BORDER FLASH -->
  {#if status === 'RED_ALERT'}
    <div class="alert-border" aria-hidden="true"></div>
  {/if}

  <!-- ─── PHASE 1: BOOT TERMINAL ─────────────────────────────── -->
  {#if !bootComplete}
    <div class="boot-screen">
      <div class="boot-header">
        <span class="boot-logo">◈ SNIPER-X APEX v6.0</span>
        <span class="boot-ver">NEURAL CORE // INITIALIZING</span>
      </div>
      <div class="terminal-window">
        {#each bootLines as line, i}
          <div class="terminal-line" style="animation-delay:{i*0.04}s">
            <span class="t-prompt">$</span>
            <span class="t-text">{line}</span>
            {#if i === bootLines.length - 1}
              <span class="t-cursor">▋</span>
            {/if}
          </div>
        {/each}
      </div>
      <div class="boot-progress">
        <div class="boot-bar" style="width:{Math.round((bootLines.length/bootSequence.length)*100)}%"></div>
      </div>
    </div>
  {/if}

  <!-- ─── PHASE 2: MAIN DASHBOARD ────────────────────────────── -->
  {#if bootComplete}
    <div class="dashboard" class:visible={bootComplete}>

      <!-- TOP NAV ───────────────────────────────────────────── -->
      <nav class="top-nav" class:nav-red={status === 'RED_ALERT'}>
        <div class="nav-logo">
          <span class="logo-icon">◈</span>
          <span class="logo-text">SNIPER-X HUB</span>
          <span class="logo-ver">v6.0</span>
        </div>

        <div class="nav-countdown">
          <span class="cd-label">NEXT_DRAW</span>
          <span class="cd-time" class:cd-red={status === 'RED_ALERT'}>{countdown}</span>
        </div>

        <div class="nav-right">
          <span class="sys-status" class:sys-red={status === 'RED_ALERT'}>
            <span class="status-dot" class:dot-red={status === 'RED_ALERT'}></span>
            {status === 'RED_ALERT' ? 'WAR_ZONE' : 'SECURE'}
          </span>
          <span class="nav-cmd">
            <span class="cmd-sym">$</span> npx sniper-x --predict
          </span>
        </div>
      </nav>

      <!-- HERO ──────────────────────────────────────────────── -->
      <header class="hero">
        <div class="hero-eyebrow">VIETNAMESE LOTTERY AI ENGINE</div>
        <h1 class="hero-title">
          <span class="ht-main">SNIPER-X</span>
          <span class="ht-sub">HUB</span>
        </h1>
        <p class="hero-desc">
          Hệ thống tiên đoán xổ số thời gian thực.<br>
          Tự động quét · Phân tích AI · Dự báo lượng tử.
        </p>

        <!-- TAB NAVIGATION ──────────────────────────────────────── -->
        <div class="flex justify-center flex-wrap gap-3 mb-8 mt-4 z-10 relative">
          <button on:click={() => switchRegion('VIETLOTT')} class="glass-tab {selectedRegion === 'VIETLOTT' ? 'active-vietlott' : ''}">VIETLOTT</button>
          <button on:click={() => switchRegion('MB')} class="glass-tab {selectedRegion === 'MB' ? 'active-mb' : ''}">MIỀN BẮC</button>
          <button on:click={() => switchRegion('MT')} class="glass-tab {selectedRegion === 'MT' ? 'active-mt' : ''}">MIỀN TRUNG</button>
          <button on:click={() => switchRegion('MN')} class="glass-tab {selectedRegion === 'MN' ? 'active-mn' : ''}">MIỀN NAM</button>
          <button on:click={() => switchRegion('KENO')} class="glass-tab {selectedRegion === 'KENO' ? 'active-keno' : ''}">⚡ KENO 10'</button>
        </div>

        {#if selectedRegion !== 'VIETLOTT' && selectedRegion !== 'KENO'}
        <div class="flex justify-center flex-wrap gap-3 animate-slide-down z-10 relative mb-8">
          {#each TUESDAY_SCHEDULE[selectedRegion] || [] as prov}
            <button 
              on:click={() => activeProvince = prov}
              class="px-3 py-1 text-[10px] uppercase rounded border transition-all {activeProvince === prov ? 'bg-white text-black border-white' : 'border-white/20 text-white/50 hover:border-white/50'}"
            >
              {prov}
            </button>
          {/each}
        </div>
        {/if}

        <!-- ZERO-MOCK STATUS BAR ────────────────────────────────────── -->
        <div class="mb-6 text-center z-10 relative">
          <span class="text-[10px] px-3 py-1.5 border rounded {hasCriticalError ? 'bg-red-500/20 text-red-500 border-red-500' : (realSamplesCount > 0 ? 'bg-green-500/20 text-green-400 border-green-500' : 'bg-cyan-500/20 text-cyan-400 border-cyan-500')} font-mono uppercase tracking-wider backdrop-blur-sm shadow-sm transition-all duration-300">
            {statusMessage}
          </span>
        </div>

        <!-- COMMAND BOX ──────────────────────────────────────── -->
        <div class="command-box">
          <div class="cmd-bar">
            <div class="cmd-dots">
              <span class="dot d-red"></span>
              <span class="dot d-yellow"></span>
              <span class="dot d-green"></span>
            </div>
            <span class="cmd-file">sniper-x.sh</span>
          </div>
          <div class="cmd-body">
            <span class="c-sym">$</span>
            <span class="c-main">npx sniper-x</span>
            <span class="c-blink">▋</span>
          </div>
          <div class="cmd-out">
            <span class="o-ok">✔</span> Phát hiện: XSKT Miền Nam · Miền Bắc · Keno<br>
            <span class="o-ok">✔</span> GSB Engine: Loaded (Quantum Mode v6.0)<br>
            <span class="o-arr">→</span> Sẵn sàng dự báo...
          </div>
        </div>

        <!-- TERMINAL LOG ─────────────────────────────────────── -->
        <div class="terminal-log" class:log-red={status === 'RED_ALERT'}>
          <div class="log-header">
            <span class="log-title">◈ MISSION_LOG</span>
            {#if isAnalyzing}
              <div class="log-progress">
                <div class="log-bar"></div>
              </div>
            {/if}
          </div>
          {#each terminalLogs as log}
            <div class="log-line">{log}</div>
          {/each}
        </div>

        <!-- IGNITE BUTTON ────────────────────────────────────── -->
        <button
          on:click={triggerPrediction}
          disabled={isAnalyzing}
          class="ignite-btn"
          class:btn-red={status === 'RED_ALERT'}
          id="ignite-btn"
        >
          {#if isAnalyzing}
            <span class="btn-spin">⟳</span> ANALYZING...
          {:else}
            <span class="btn-ico">⚡</span> IGNITE PREDICTION
          {/if}
        </button>
      </header>

      <!-- 3D QUANTUM SPHERE ─────────────────────────────────── -->
      <section class="sphere-section" style="--glow-color: {sphereColor};width:100%;max-width:900px;align-self:center;">
        <div class="sphere-label">
          <span class="sphere-tag">QUANTUM MATRIX</span>
          <span class="sphere-pulse" class:sp-active={isAnalyzing} style="background-color: {sphereColor}; box-shadow: 0 0 10px {sphereColor}"></span>
        </div>
        <div class="sphere-wrap">
          <Canvas>
            <QuantumSphere isLive={isAnalyzing} color={sphereColor} />
          </Canvas>
        </div>
      </section>

      <!-- HEATMAP & ANCHORS (VIETLOTT) ───────────────────────── -->
      {#if selectedRegion === 'VIETLOTT' && Object.keys(heatmapData).length > 0}
        <div class="space-y-12 mt-12 z-10 relative" style="width:100%;max-width:900px;align-self:center;">
          <section class="glass-panel p-6 border-t border-cyan-500/30">
            <div class="flex justify-between items-center mb-6">
              <h3 class="text-[10px] font-mono text-cyan-400 tracking-[0.3em]">❖ {selectedRegion} RADAR SCANNER</h3>
              <span class="text-[8px] text-gray-500 uppercase">Range: 00 - {gridMax}</span>
            </div>
            
            <div class="grid {gridCols} gap-1.5 mx-auto" style="width:fit-content;">
              {#each Array(gridMax + 1) as _, i}
                {@const num = i + (selectedRegion === 'VIETLOTT' ? 1 : 0)}
                {#if num <= gridMax}
                  <div 
                    class="h-9 flex items-center justify-center border border-white/5 transition-all duration-500 relative group"
                    style="background: rgba(6, 182, 212, {(heatmapData[num] || 0) / 100}); box-shadow: {(heatmapData[num] || 0) > 40 ? 'inset 0 0 15px rgba(6, 182, 212, 0.5)' : 'none'}"
                  >
                    <span class="text-[9px] {(heatmapData[num] || 0) > 20 ? 'text-white font-bold' : 'text-gray-600'}">{num}</span>
                    
                    {#if anchors.includes(num)}
                       <div class="absolute inset-0 border border-yellow-500 animate-pulse shadow-[0_0_10px_rgba(234,179,8,0.5)]"></div>
                    {/if}

                    <div class="absolute -top-8 hidden group-hover:block bg-black text-cyan-400 px-2 py-1 rounded border border-cyan-500 text-[8px] z-50">
                      CONF: {heatmapData[num] || 0}%
                    </div>
                  </div>
                {/if}
              {/each}
            </div>
          </section>

          <section class="text-center pb-8 w-full max-w-4xl mx-auto">
            <div class="inline-block px-4 py-1 border border-yellow-500/50 text-yellow-500 text-[10px] mb-8 animate-pulse">
              TARGETS ACQUIRED: QUANTUM ANCHORS DETECTED
            </div>
            
            <div class="results-container gap-6">
              {#each anchors as anchor}
                <div class="relative w-16 h-16">
                  <div class="absolute inset-0 border-2 border-cyan-500 rounded-full animate-spin-slow opacity-30"></div>
                  <div class="absolute inset-0 border border-cyan-400 rounded-full blur-sm animate-pulse"></div>
                  
                  <div class="relative w-full h-full flex items-center justify-center text-2xl font-black text-white bg-black rounded-full border-2 border-cyan-400 shadow-[0_0_25px_rgba(6,182,212,0.8)]">
                    {anchor.toString().padStart(2, '0')}
                  </div>
                </div>
              {/each}
            </div>
          </section>
        </div>
      {/if}

      <!-- MATRIX XSKT ────────────────────────────────────────── -->
      {#if selectedRegion !== 'VIETLOTT' && predictionMatrix}
      <section class="results-section">
        <div class="xskt-matrix grid grid-cols-12 gap-2 mt-4 p-6 border-t-2 relative z-10 max-w-4xl mx-auto glass-panel" style="border-color: {sphereColor}; box-shadow: 0 -5px 30px {sphereColor}33">
          <div class="col-span-12 flex justify-between mb-4">
            <span class="text-xs opacity-50 text-white">❖ ĐÀI: {activeProvince.toUpperCase()}</span>
            <span class="text-xs text-red-500 font-bold animate-pulse">● LIVE 16:15</span>
          </div>

          <div class="col-span-3 text-sm font-mono opacity-60 text-white flex items-center justify-end pr-4 border-r border-white/10">ĐẶC BIỆT</div>
          <div class="col-span-9 text-4xl font-black text-yellow-400 drop-shadow-xl tracking-widest flex items-center pl-4 py-2">
            {predictionMatrix['DB'] ? predictionMatrix['DB'][0] : '---'}
          </div>

          {#each ['G1', 'G2', 'G3', 'G4', 'G5', 'G6', 'G7', 'G8'] as g}
            {#if predictionMatrix[g]}
              <div class="col-span-3 text-[10px] opacity-40 font-mono text-white flex items-center justify-end pr-4 border-r border-white/10 pt-2">{g}</div>
              <div class="col-span-9 flex flex-wrap gap-4 pt-2 pl-4">
                {#each predictionMatrix[g] as num}
                  <span class="text-lg text-white font-bold tracking-widest">{num}</span>
                {/each}
              </div>
            {/if}
          {/each}
        </div>
      </section>
      {/if}

      <!-- KENO 80-BALL HEATMAP ─────────────────────────────────── -->
      {#if selectedRegion === 'KENO'}
        <div class="w-full max-w-6xl bg-[#08080a] border border-emerald-500/10 rounded-[2rem] p-10 shadow-[0_0_120px_rgba(0,0,0,1)] relative" style="align-self:center;">
          
          <!-- HEADER: KỲ QUAY & THỜI GIAN THẬT -->
          <header class="flex justify-between items-center border-b border-emerald-500/20 pb-6 mb-10">
            <div class="flex items-center gap-6">
              <div class="px-5 py-2 border rounded-full text-sm font-black tracking-widest uppercase transition-colors {(kenoLatestDraw && !isAnalyzing) ? 'bg-emerald-500/10 border-emerald-500/50 text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.2)]' : 'bg-amber-500/10 border-amber-500/50 text-amber-400 animate-pulse'}">
                ⚡ KENO OVERCLOCK
              </div>
              <div class="text-slate-500 tracking-[0.2em] text-sm uppercase font-bold">
                Kỳ quay <span class="text-white ml-2">#{kenoLatestDraw || 'SYNCING...'}</span>
              </div>
            </div>

            <div class="flex items-center gap-4">
              <span class="text-xs text-slate-500 tracking-widest uppercase font-bold">Kỳ tiếp:</span>
              <span class="text-4xl font-black tracking-widest {(kenoNextDraw.startsWith('00:00:') && parseInt(kenoNextDraw.split(':')[2]) < 30) ? 'text-red-500 animate-bounce drop-shadow-[0_0_10px_rgba(239,68,68,0.5)]' : 'text-emerald-400 drop-shadow-[0_0_10px_rgba(16,185,129,0.5)]'}" style="font-family: 'Orbitron', sans-serif;">
                {kenoNextDraw || '--:--'}
              </span>
            </div>
          </header>

          {#if Object.keys(kenoHeatmap).length > 0}
            <!-- MA TRẬN 80 SỐ -->
            <div class="grid grid-cols-10 gap-5 transition-opacity duration-500 {isAnalyzing ? 'opacity-20' : 'opacity-100'} mb-12">
              {#each Array(80) as _, idx}
                {@const num = idx + 1}
                {@const isTarget = kenoAnchors.includes(num)}
                <div
                  class="
                    relative h-16 w-16 rounded-full flex items-center justify-center transition-all duration-300 mx-auto
                    font-black text-2xl tracking-tighter
                    {isTarget 
                      ? 'bg-gradient-to-br from-emerald-300 to-emerald-600 text-[#020203] z-10 scale-110 shadow-[0_0_30px_rgba(16,185,129,0.7),inset_0_4px_10px_rgba(255,255,255,0.5)] border border-emerald-200' 
                      : 'bg-[#0f0f13] text-slate-600 shadow-[inset_0_2px_5px_rgba(255,255,255,0.03),0_5px_15px_rgba(0,0,0,0.6)] border border-slate-800/60'
                    }
                  "
                  style="font-family: 'Orbitron', sans-serif; {isTarget ? `text-shadow: 0px 2px 4px rgba(255,255,255,0.3); animation: float 3s ease-in-out infinite ${(num * 0.1).toFixed(1)}s;` : ''}"
                >
                  {num < 10 ? `0${num}` : num}
                </div>
              {/each}
            </div>

            <!-- FOOTER -->
            <div class="mt-12 flex justify-between items-center border-t border-slate-800/50 pt-6">
              <div class="flex items-center gap-2">
                <span class="h-2 w-2 bg-emerald-500 rounded-full animate-ping"></span>
                <span class="text-[10px] text-slate-500 uppercase tracking-[0.2em] font-bold">
                  NGUỒN DỮ LIỆU: TRỰC TIẾP MINH NGỌC
                </span>
              </div>
              <div class="text-[10px] text-emerald-500/50 uppercase tracking-[0.3em] font-bold">
                ZERO MOCK DATA PROTOCOL
              </div>
            </div>

            <!-- MISSION YIELD / PROFIT VALIDATION -->
            {#if kenoValidationData}
            <div class="mt-8 p-6 bg-[#08080a] border border-emerald-500/20 rounded-xl relative overflow-hidden">
                <div class="flex justify-between items-center relative z-10">
                    <div>
                        <p class="text-[10px] font-sans font-bold text-emerald-600/80 uppercase tracking-widest">❖ MISSION YIELD / TIER 10</p>
                        <h2 class="text-4xl font-black {kenoValidationData.profit !== undefined && kenoValidationData.profit > 0 ? 'text-emerald-400' : 'text-slate-300'} drop-shadow-[0_0_15px_rgba(16,185,129,0.3)]">
                            {kenoValidationData.profit && kenoValidationData.profit > 0 ? '+' : ''}{(kenoValidationData.profit || 0).toLocaleString()} <span class="text-sm font-normal text-slate-500">VND</span>
                        </h2>
                    </div>
                    
                    <div class="text-right">
                        <p class="text-[10px] font-sans font-bold text-emerald-600/80 uppercase">Hit Rate</p>
                        <p class="text-3xl font-black text-emerald-400 drop-shadow-[0_0_10px_rgba(16,185,129,0.5)]">{kenoValidationData.hit_count} / 10</p>
                    </div>
                </div>

                <div class="mt-6 w-full h-1.5 bg-[#121214] rounded-full overflow-hidden relative z-10 shadow-inner border border-white/5">
                    <div class="h-full bg-gradient-to-r from-emerald-600 to-emerald-400 shadow-[0_0_15px_rgba(16,185,129,1)] transition-all duration-1000 ease-out" 
                         style="width: {(kenoValidationData.hit_count / 10) * 100}%"></div>
                </div>
            </div>
            {/if}

          {:else}
            <div class="flex flex-col items-center justify-center p-12 bg-[#08080a] rounded-2xl border border-slate-800 shadow-[inset_0_0_50px_rgba(0,0,0,0.8)]">
              <div class="text-4xl mb-4 text-emerald-500/30 animate-pulse">⚡</div>
              <div class="text-slate-300 font-bold mb-2 tracking-widest uppercase text-lg">SYNCING KENO DATA...</div>
              <div class="text-slate-500 text-sm text-center leading-relaxed font-sans mt-2">
                Đang thiết lập kết nối thời gian thực.<br>
                Chờ dữ liệu thật từ Server...
              </div>
            </div>
          {/if}
        </div>
      {/if}

      <!-- INSTALLED SKILLS ─ 4-COL MATRIX GRID ──────────────── -->
      {#if showGrid}
        <section class="skills-section" style="width:100%;max-width:1100px;align-self:center;box-sizing:border-box;">
          <div class="section-hdr">
            <span class="sec-tag">INSTALLED SKILLS</span>
            <span class="sec-line"></span>
            <span class="sec-count">{skills.length} modules · auto-detected</span>
          </div>
          <p class="sec-desc">
            Công nghệ được phát hiện tự động và cài đặt bởi <code>autoskills</code>
          </p>
          <!-- 4-column grid — 2 cols on mobile -->
          <div class="skills-grid-4col" id="skills-grid">
            {#each skills as sk, i}
              <div
                class="skill-card"
                class:sk-hover={activeSkill === i}
                on:mouseenter={() => activeSkill = i}
                on:mouseleave={() => activeSkill = -1}
                style="animation-delay:{i * 0.04}s"
                role="button"
                tabindex="0"
              >
                <div class="sk-icon">{sk.icon}</div>
                <div class="sk-info">
                  <div class="sk-name">{sk.name}</div>
                  <div class="sk-tag">{sk.tag}</div>
                </div>
                <div class="sk-status" style="color:{getStatusColor(sk.status)}">
                  <span class="sk-dot" style="background:{getStatusColor(sk.status)}"></span>
                  {sk.status}
                </div>
              </div>
            {/each}
          </div>
        </section>
      {/if}

      <!-- HOW IT WORKS ─────────────────────────────────────── -->
      <section class="how-section" style="width:100%;max-width:1100px;align-self:center;box-sizing:border-box;">
        <div class="section-hdr">
          <span class="sec-tag">HOW IT WORKS</span>
          <span class="sec-line"></span>
        </div>
        <!-- 3 cột ngang — dòng chảy dữ liệu logic trái → phải -->
        <div class="steps-grid-3col">
          <div class="step-card">
            <div class="step-num">01</div>
            <div class="step-title">Kích hoạt lệnh</div>
            <div class="step-desc">Nhấn IGNITE PREDICTION để Ghost Scraper Agent đột kích vào hệ thống XSKT realtime.</div>
          </div>
          <div class="step-card">
            <div class="step-num">02</div>
            <div class="step-title">Tự động quét</div>
            <div class="step-desc">Playwright mở Chrome thực, vượt Cloudflare, cào kết quả xổ số theo thời gian thực.</div>
          </div>
          <div class="step-card">
            <div class="step-num">03</div>
            <div class="step-title">Dự báo lượng tử</div>
            <div class="step-desc">GSB AI Engine phân tích pattern, xuất ra số dự báo với độ chính xác cao nhất.</div>
          </div>
        </div>
      </section>

      <!-- FOOTER ───────────────────────────────────────────── -->
      <footer class="site-footer" style="width:100%;align-self:stretch;box-sizing:border-box;">
        <div class="footer-inner">
          <span class="f-brand">◈ SNIPER-X HUB v6.0</span>
          <span class="f-sep">//</span>
          <span class="f-text">Powered by GSB Engine + autoskills</span>
          <a href="https://github.com/midudev/autoskills" target="_blank" rel="noreferrer" class="f-link">
            github ↗
          </a>
        </div>
      </footer>

    </div>
  {/if}

  <!-- AI COGNITION GAUGE -->
  {#if bootComplete}
    <CognitionGauge confidence={confidenceLevel} {isAnalyzing} />
  {/if}

</div>

<!-- ════════════════════════════════════════════════════════════ -->
<style>
  /* ── ROOT ──────────────────────────────────────────────────── */
  :global(body) {
    margin: 0;
    background: #050505;
    overflow-x: hidden;
    font-family: 'Courier New', monospace;
    color: #22d3ee;
  }

  .app-root {
    min-height: 100vh;
    background: #050505;
    position: relative;
    transition: background 0.4s;
    display: flex;
    flex-direction: column;
    align-items: center;
    overflow-x: hidden;
  }
  .app-root.red-alert { background: #0a0202; }

  /* ── SCANLINES ─────────────────────────────────────────────── */
  .scanlines {
    position: fixed; inset: 0;
    pointer-events: none; z-index: 9999;
    background: repeating-linear-gradient(
      0deg, transparent, transparent 2px,
      rgba(0,255,255,0.012) 2px, rgba(0,255,255,0.012) 4px
    );
  }

  /* ── RED ALERT BORDER ──────────────────────────────────────── */
  .alert-border {
    position: fixed; inset: 0;
    pointer-events: none; z-index: 9998;
    box-shadow: inset 0 0 60px rgba(239,68,68,0.35);
    border: 2px solid rgba(239,68,68,0.6);
    animation: alertFlash 0.8s ease-in-out infinite alternate;
  }
  @keyframes alertFlash {
    from { border-color: rgba(239,68,68,0.3); box-shadow: inset 0 0 40px rgba(239,68,68,0.2); }
    to   { border-color: rgba(239,68,68,0.8); box-shadow: inset 0 0 80px rgba(239,68,68,0.5); }
  }

  /* ── BOOT SCREEN ───────────────────────────────────────────── */
  .boot-screen {
    min-height: 100vh;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    padding: 2rem; background: #050505;
  }

  .boot-header {
    display: flex; justify-content: space-between; align-items: center;
    width: 100%; max-width: 640px;
    margin-bottom: 1.5rem;
    border-bottom: 1px solid rgba(34,211,238,0.2);
    padding-bottom: 0.75rem;
  }
  .boot-logo { font-size: 0.9rem; font-weight: 700; color: #22d3ee; letter-spacing: 0.15em; }
  .boot-ver  { font-size: 0.7rem; color: #0891b2; letter-spacing: 0.1em; }

  .terminal-window {
    width: 100%; max-width: 640px;
    background: rgba(0,0,0,0.7);
    border: 1px solid rgba(34,211,238,0.2);
    border-radius: 8px; padding: 1.5rem; min-height: 200px;
  }

  .terminal-line {
    display: flex; gap: 0.5rem; margin-bottom: 0.35rem;
    font-size: 0.82rem; line-height: 1.5;
    opacity: 0; animation: lineIn 0.25s ease forwards;
  }
  @keyframes lineIn {
    from { opacity: 0; transform: translateX(-6px); }
    to   { opacity: 1; transform: translateX(0); }
  }
  .t-prompt { color: #34d399; flex-shrink: 0; }
  .t-text   { color: #22d3ee; }
  .t-cursor { color: #22d3ee; animation: blink 0.8s step-end infinite; }

  .boot-progress {
    width: 100%; max-width: 640px; height: 2px;
    background: rgba(34,211,238,0.1); margin-top: 0.75rem; border-radius: 1px;
  }
  .boot-bar {
    height: 100%; background: #22d3ee;
    box-shadow: 0 0 8px #22d3ee;
    transition: width 0.3s ease;
  }

  /* ── DASHBOARD ─────────────────────────────────────────────── */
  .dashboard {
    opacity: 0; transition: opacity 0.8s ease;
    width: 100%; display: flex; flex-direction: column; align-items: center;
  }
  .dashboard.visible { opacity: 1; }

  /* ── NAV ───────────────────────────────────────────────────── */
  .top-nav {
    display: flex; align-items: center; justify-content: space-between; gap: 1rem;
    padding: 0.85rem 2rem;
    border-bottom: 1px solid rgba(34,211,238,0.15);
    background: rgba(5,5,5,0.92); backdrop-filter: blur(12px);
    position: sticky; top: 0; z-index: 100;
    transition: border-color 0.3s;
    width: 100%; /* Full width sticky nav */
    align-self: stretch; /* Stretch trong flex parent */
    box-sizing: border-box;
  }
  .top-nav.nav-red { border-bottom-color: rgba(239,68,68,0.4); }

  .nav-logo    { display: flex; align-items: center; gap: 0.5rem; }
  .logo-icon   { font-size: 1.1rem; color: #22d3ee; }
  .logo-text   { font-size: 0.8rem; font-weight: 700; letter-spacing: 0.2em; color: #22d3ee; text-transform: uppercase; }
  .logo-ver    { font-size: 0.6rem; color: #0891b2; border: 1px solid rgba(34,211,238,0.2); border-radius: 3px; padding: 0.1em 0.4em; }

  .nav-countdown { display: flex; flex-direction: column; align-items: center; gap: 0.1rem; }
  .cd-label      { font-size: 0.55rem; color: #0891b2; letter-spacing: 0.2em; text-transform: uppercase; }
  .cd-time       { font-size: 1.2rem; font-weight: 900; color: #fff; letter-spacing: 0.1em; transition: color 0.3s; }
  .cd-time.cd-red { color: #ef4444; animation: pulse 0.6s infinite; }

  .nav-right   { display: flex; align-items: center; gap: 1rem; }
  .sys-status  { display: flex; align-items: center; gap: 0.4rem; font-size: 0.65rem; color: #34d399; letter-spacing: 0.15em; transition: color 0.3s; }
  .sys-status.sys-red { color: #ef4444; }
  .status-dot  { width: 7px; height: 7px; border-radius: 50%; background: #34d399; box-shadow: 0 0 6px #34d399; animation: pulse 2s infinite; }
  .status-dot.dot-red { background: #ef4444; box-shadow: 0 0 10px #ef4444; animation: pulse 0.5s infinite; }

  .nav-cmd { font-size: 0.7rem; color: #0891b2; background: rgba(34,211,238,0.05); border: 1px solid rgba(34,211,238,0.15); border-radius: 4px; padding: 0.25rem 0.75rem; display: flex; gap: 0.35rem; }
  .cmd-sym { color: #34d399; }

  /* ── HERO ──────────────────────────────────────────────────── */
  .hero {
    display: flex; flex-direction: column; align-items: center;
    text-align: center; padding: 4rem 1.5rem 2rem;
    position: relative;
    width: 100%; max-width: 860px;
    align-self: center;
  }
  .hero::before {
    content: ''; position: absolute; inset: 0;
    background: radial-gradient(ellipse at center, rgba(34,211,238,0.05) 0%, transparent 65%);
    pointer-events: none;
  }

  .hero-eyebrow { font-size: 0.65rem; letter-spacing: 0.35em; color: #0891b2; text-transform: uppercase; margin-bottom: 1rem; }

  .hero-title { margin: 0 0 1.2rem; display: flex; flex-direction: column; line-height: 1; }
  .ht-main {
    font-size: clamp(3rem, 10vw, 7rem); font-weight: 900; letter-spacing: 0.05em;
    color: #22d3ee; text-transform: uppercase;
    text-shadow: 0 0 40px rgba(34,211,238,0.5), 0 0 80px rgba(34,211,238,0.2);
  }
  .ht-sub {
    font-size: clamp(2.5rem, 8vw, 5.5rem); font-weight: 900;
    color: transparent; -webkit-text-stroke: 1.5px #22d3ee;
    text-transform: uppercase; letter-spacing: 0.1em;
    text-shadow: 0 0 20px rgba(34,211,238,0.25);
  }

  .hero-desc { font-size: 0.85rem; color: #0891b2; line-height: 1.8; max-width: 440px; margin-bottom: 2rem; letter-spacing: 0.04em; }

  /* ── COMMAND BOX ───────────────────────────────────────────── */
  .command-box {
    background: rgba(0,0,0,0.65); border: 1px solid rgba(34,211,238,0.22);
    border-radius: 10px; overflow: hidden; width: 100%; max-width: 500px;
    margin-bottom: 1.5rem; text-align: left;
  }
  .cmd-bar {
    display: flex; align-items: center; gap: 0.6rem;
    background: rgba(34,211,238,0.04); border-bottom: 1px solid rgba(34,211,238,0.12);
    padding: 0.5rem 1rem;
  }
  .cmd-dots    { display: flex; gap: 0.4rem; }
  .dot         { width: 10px; height: 10px; border-radius: 50%; }
  .d-red       { background: #ef4444; }
  .d-yellow    { background: #f59e0b; }
  .d-green     { background: #22c55e; }
  .cmd-file    { font-size: 0.7rem; color: #0891b2; margin-left: auto; }
  .cmd-body    { display: flex; align-items: center; gap: 0.5rem; padding: 0.8rem 1rem; font-size: 1rem; }
  .c-sym       { color: #34d399; }
  .c-main      { color: #22d3ee; font-weight: 700; }
  .c-blink     { color: #22d3ee; animation: blink 0.8s step-end infinite; }
  .cmd-out     { padding: 0 1rem 0.8rem; font-size: 0.75rem; line-height: 1.8; color: #0891b2; border-top: 1px solid rgba(34,211,238,0.07); padding-top: 0.5rem; }
  .o-ok        { color: #34d399; }
  .o-arr       { color: #22d3ee; }

  /* ── TERMINAL LOG ──────────────────────────────────────────── */
  .terminal-log {
    width: 100%; max-width: 500px; margin-bottom: 1.75rem;
    background: rgba(0,0,0,0.7); border: 1px solid rgba(34,211,238,0.2);
    border-radius: 6px; overflow: hidden; text-align: left;
    transition: border-color 0.3s, box-shadow 0.3s;
  }
  .terminal-log.log-red {
    border-color: rgba(239,68,68,0.5);
    box-shadow: 0 0 20px rgba(239,68,68,0.15);
  }

  .log-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0.4rem 0.75rem;
    border-bottom: 1px solid rgba(34,211,238,0.1);
    background: rgba(34,211,238,0.03);
  }
  .log-title { font-size: 0.6rem; letter-spacing: 0.2em; color: #0891b2; }

  .log-progress {
    flex: 1; max-width: 120px; height: 2px;
    background: rgba(34,211,238,0.1); border-radius: 1px; overflow: hidden;
  }
  .log-bar {
    height: 100%; width: 40%; background: #22d3ee;
    box-shadow: 0 0 6px #22d3ee;
    animation: scanProgress 1.2s linear infinite;
  }
  @keyframes scanProgress {
    0%   { transform: translateX(-100%); }
    100% { transform: translateX(400%); }
  }

  .log-line {
    font-size: 0.72rem; color: #22d3ee; line-height: 1.6;
    padding: 0.15rem 0.75rem;
    animation: lineIn 0.2s ease;
  }
  .log-line:first-of-type { padding-top: 0.4rem; }
  .log-line:last-child     { padding-bottom: 0.4rem; }

  /* ── IGNITE BUTTON ─────────────────────────────────────────── */
  .ignite-btn {
    display: flex; align-items: center; gap: 0.6rem;
    padding: 0.9rem 2.5rem;
    background: rgba(34,211,238,0.07); border: 1.5px solid rgba(34,211,238,0.4);
    border-radius: 5px; color: #22d3ee; font-family: inherit;
    font-size: 0.88rem; font-weight: 700; letter-spacing: 0.15em;
    text-transform: uppercase; cursor: pointer;
    transition: all 0.2s ease; position: relative; overflow: hidden;
    margin-bottom: 0;
  }
  .ignite-btn::before {
    content: ''; position: absolute; inset: 0;
    background: linear-gradient(135deg, transparent 40%, rgba(34,211,238,0.08));
    opacity: 0; transition: opacity 0.2s;
  }
  .ignite-btn:hover:not(:disabled) {
    background: rgba(34,211,238,0.14); border-color: #22d3ee;
    box-shadow: 0 0 30px rgba(34,211,238,0.4);
    transform: translateY(-1px);
  }
  .ignite-btn:hover:not(:disabled)::before { opacity: 1; }
  .ignite-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  .ignite-btn.btn-red {
    border-color: rgba(239,68,68,0.7); color: #ef4444;
    background: rgba(239,68,68,0.07);
    box-shadow: 0 0 20px rgba(239,68,68,0.2);
  }

  .btn-ico  { font-size: 1rem; }
  .btn-spin { font-size: 1rem; animation: spin 1s linear infinite; display: inline-block; }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ── SPHERE ────────────────────────────────────────────────── */
  .sphere-section {
    position: relative; padding: 2rem 0;
    display: flex; flex-direction: column; align-items: center;
  }
  .sphere-label { display: flex; align-items: center; justify-content: center; gap: 0.75rem; margin-bottom: 0.5rem; }
  .sphere-tag   { font-size: 0.6rem; letter-spacing: 0.3em; color: #0891b2; text-transform: uppercase; }
  .sphere-pulse { width: 6px; height: 6px; border-radius: 50%; background: #22d3ee; opacity: 0.4; transition: all 0.3s; }
  .sphere-pulse.sp-active { opacity: 1; box-shadow: 0 0 14px #22d3ee; animation: pulse 0.7s infinite; }
  .sphere-wrap  { width: 100%; max-width: 600px; height: 420px; position: relative; }

  /* ── TABS ─────────── */
  .glass-tab {
    padding: 0.5rem 1.25rem; font-size: 0.75rem; color: rgba(255,255,255,0.6);
    border-bottom: 2px solid transparent; text-transform: uppercase; letter-spacing: 0.1em;
    cursor: pointer; transition: all 0.3s; font-family: monospace;
  }
  .glass-tab:hover { color: rgba(255,255,255,0.9); }
  .active-vietlott { color: #06b6d4; border-bottom-color: #06b6d4; text-shadow: 0 0 10px #06b6d4; }
  .active-mb { color: #ef4444; border-bottom-color: #ef4444; text-shadow: 0 0 10px #ef4444; }
  .active-mt { color: #10b981; border-bottom-color: #10b981; text-shadow: 0 0 10px #10b981; }
  .active-mn { color: #3b82f6; border-bottom-color: #3b82f6; text-shadow: 0 0 10px #3b82f6; }

  .glass-panel {
    background: rgba(0,0,0,0.6); backdrop-filter: blur(8px);
    box-shadow: 0 10px 30px rgba(0,0,0,0.5); border-radius: 8px;
    margin-left: auto; margin-right: auto;
    width: 100%; max-width: 820px;
  }


  /* ── NEON BALLS ────────────────────────────────────────────── */
  .results-section {
    max-width: 900px; margin: 0 auto; padding: 1.5rem;
  }
  .results-hdr {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 1.25rem;
  }
  .r-title { font-size: 0.75rem; letter-spacing: 0.2em; color: #22d3ee; text-transform: uppercase; }
  .r-badge { font-size: 0.65rem; color: #0891b2; border: 1px solid rgba(34,211,238,0.2); border-radius: 4px; padding: 0.2rem 0.6rem; }

  .neon-balls {
    display: flex; flex-wrap: wrap; gap: 0.8rem; justify-content: center;
  }

  .neon-ball {
    width: 64px; height: 64px;
    border-radius: 50%;
    border: 2px solid #22d3ee;
    display: flex; align-items: center; justify-content: center;
    background: rgba(34,211,238,0.08);
    box-shadow: 0 0 20px rgba(34,211,238,0.6), inset 0 0 15px rgba(34,211,238,0.1);
    opacity: 0;
    animation: ballBounce 0.55s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
    cursor: pointer; transition: transform 0.15s;
  }
  .neon-ball:hover {
    transform: scale(1.15);
    box-shadow: 0 0 35px rgba(34,211,238,0.9), inset 0 0 20px rgba(34,211,238,0.2);
  }
  @keyframes ballBounce {
    0%   { opacity: 0; transform: scale(0.2) translateY(20px); }
    70%  { opacity: 1; transform: scale(1.12) translateY(-4px); }
    100% { opacity: 1; transform: scale(1) translateY(0); }
  }

  .ball-num { font-size: 1.35rem; font-weight: 900; color: #22d3ee; letter-spacing: -0.02em; }

  /* ── SKILLS ────────────────────────────────────────────────── */
  .skills-section { max-width: 1000px; width: 100%; margin: 2rem auto; padding: 1.5rem; align-self: center; box-sizing: border-box; }
  .section-hdr { display: flex; align-items: center; gap: 1rem; margin-bottom: 0.75rem; }
  .sec-tag  { font-size: 0.6rem; letter-spacing: 0.3em; color: #0891b2; text-transform: uppercase; white-space: nowrap; }
  .sec-line { flex: 1; height: 1px; background: rgba(34,211,238,0.12); }
  .sec-count{ font-size: 0.6rem; color: #0891b2; white-space: nowrap; }
  .sec-desc { font-size: 0.75rem; color: #0891b2; margin-bottom: 1.25rem; }
  .sec-desc code {
    background: rgba(34,211,238,0.1); border: 1px solid rgba(34,211,238,0.2);
    border-radius: 3px; padding: 0.1em 0.4em; color: #22d3ee;
  }

  .skills-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 0.5rem;
  }
  .skill-card {
    display: flex; align-items: center; gap: 0.65rem;
    padding: 0.65rem 0.9rem; background: rgba(0,0,0,0.45);
    border: 1px solid rgba(34,211,238,0.12); border-radius: 5px;
    cursor: pointer; transition: all 0.2s ease;
    opacity: 0; animation: cardIn 0.35s ease forwards;
  }
  .skill-card:hover, .skill-card.sk-hover {
    border-color: rgba(34,211,238,0.35); background: rgba(34,211,238,0.05);
    box-shadow: 0 0 16px rgba(34,211,238,0.08);
  }
  @keyframes cardIn {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .sk-icon  { font-size: 1rem; color: #22d3ee; width: 22px; text-align: center; flex-shrink: 0; }
  .sk-info  { flex: 1; min-width: 0; }
  .sk-name  { font-size: 0.8rem; font-weight: 700; color: #22d3ee; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .sk-tag   { font-size: 0.6rem; color: #0891b2; letter-spacing: 0.08em; text-transform: uppercase; }
  .sk-status{ display: flex; align-items: center; gap: 0.3rem; font-size: 0.58rem; letter-spacing: 0.08em; flex-shrink: 0; }
  .sk-dot   { width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; }

  /* ── HOW IT WORKS ──────────────────────────────────────────── */
  .how-section { max-width: 900px; width: 100%; margin: 0 auto; padding: 1.5rem 1.5rem 4rem; align-self: center; box-sizing: border-box; }

  .steps-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 0.85rem; margin-top: 1.25rem;
  }
  .step-card {
    background: rgba(0,0,0,0.4); border: 1px solid rgba(34,211,238,0.12);
    border-radius: 7px; padding: 1.4rem; transition: all 0.2s;
  }
  .step-card:hover { border-color: rgba(34,211,238,0.3); transform: translateY(-2px); box-shadow: 0 6px 24px rgba(34,211,238,0.07); }
  .step-num   { font-size: 2rem; font-weight: 900; color: rgba(34,211,238,0.18); margin-bottom: 0.4rem; line-height: 1; }
  .step-title { font-size: 0.82rem; font-weight: 700; color: #22d3ee; margin-bottom: 0.4rem; letter-spacing: 0.05em; text-transform: uppercase; }
  .step-desc  { font-size: 0.74rem; color: #0891b2; line-height: 1.6; }

  /* ── FOOTER ────────────────────────────────────────────────── */
  .site-footer { border-top: 1px solid rgba(34,211,238,0.08); padding: 1.2rem; width: 100%; align-self: stretch; box-sizing: border-box; }
  .footer-inner { display: flex; align-items: center; justify-content: center; gap: 0.85rem; font-size: 0.7rem; flex-wrap: wrap; }
  .f-brand { color: #22d3ee; font-weight: 700; letter-spacing: 0.1em; }
  .f-sep   { color: rgba(34,211,238,0.25); }
  .f-text  { color: #0891b2; }
  .f-link  { color: #22d3ee; text-decoration: none; border: 1px solid rgba(34,211,238,0.2); border-radius: 3px; padding: 0.2rem 0.55rem; transition: all 0.2s; }
  .f-link:hover { background: rgba(34,211,238,0.08); border-color: rgba(34,211,238,0.45); }

  /* ── SHARED KEYFRAMES ──────────────────────────────────────── */
  @keyframes blink { 50% { opacity: 0; } }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }

  /* ── RESPONSIVE ────────────────────────────────────────────── */
  @media (max-width: 640px) {
    .nav-cmd, .nav-countdown { display: none; }
    .ht-main { font-size: clamp(2.5rem, 18vw, 4rem); }
    .sphere-wrap { height: 280px; }
    .skills-grid { grid-template-columns: 1fr; }
    .steps-grid  { grid-template-columns: 1fr; }
    .neon-ball   { width: 54px; height: 54px; }
  }

  /* ── NẮN TRỤC TRUNG TÂM (V9.0) ────────────────────────────── */
  .results-container {
    display: flex;
    justify-content: center;
    align-items: center;
    flex-wrap: wrap;
    width: 100%;
    gap: 1.5rem;
  }

  /* ── SKILLS GRID 4-COL MATRIX ──────────────────────────────── */
  .skills-grid-4col {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.5rem;
    margin-top: 0.75rem;
  }
  @media (max-width: 900px) { .skills-grid-4col { grid-template-columns: repeat(2, 1fr); } }
  @media (max-width: 480px) { .skills-grid-4col { grid-template-columns: 1fr; } }

  /* ── HOW IT WORKS 3-COL ────────────────────────────────────── */
  .steps-grid-3col {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.85rem;
    margin-top: 1.25rem;
  }
  @media (max-width: 640px) { .steps-grid-3col { grid-template-columns: 1fr; } }

  /* ── KENO TAB ───────────────────────────────────────────────── */
  .glass-tab.active-keno {
    background: rgba(168,85,247,0.2);
    border-color: #a855f7;
    color: #a855f7;
    box-shadow: 0 0 20px rgba(168,85,247,0.35);
  }

  /* ── KENO PANEL ─────────────────────────────────────────────── */
  .keno-panel {
    margin: 1.5rem auto;
    padding: 1.5rem;
    background: rgba(88, 28, 135, 0.08);
    border: 1px solid rgba(168,85,247,0.2);
    border-radius: 12px;
    box-shadow: 0 0 40px rgba(168,85,247,0.1);
  }

  .keno-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 1.25rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid rgba(168,85,247,0.2);
    flex-wrap: wrap; gap: 0.5rem;
  }
  .keno-header-left  { display: flex; align-items: center; gap: 0.75rem; }
  .keno-header-right { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
  .keno-badge {
    font-size: 0.7rem; font-weight: 700; letter-spacing: 0.15em;
    color: #c084fc; background: rgba(168,85,247,0.15);
    border: 1px solid rgba(168,85,247,0.35); border-radius: 4px;
    padding: 0.2rem 0.65rem;
  }
  .keno-draw-id   { font-size: 0.7rem; color: #a78bfa; font-family: monospace; }
  .keno-stat      { font-size: 0.62rem; color: #7c3aed; letter-spacing: 0.08em; text-transform: uppercase; }
  .keno-countdown { font-size: 0.65rem; color: #c084fc; font-family: monospace; letter-spacing: 0.05em; }

  .keno-radar-label {
    font-size: 0.6rem; letter-spacing: 0.25em; text-transform: uppercase;
    color: rgba(168,85,247,0.5); margin-bottom: 0.75rem;
  }

  /* 10-column grid = 80 cells */
  .keno-grid {
    display: grid;
    grid-template-columns: repeat(10, 1fr);
    gap: 3px;
    padding: 0.5rem;
    background: rgba(0,0,0,0.3);
    border: 1px solid rgba(168,85,247,0.12);
    border-radius: 8px;
  }
  .keno-cell {
    aspect-ratio: 1;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.6rem; font-weight: 700; font-family: monospace;
    border: 1px solid rgba(168,85,247,0.08);
    border-radius: 3px; cursor: default; position: relative;
    color: rgba(255,255,255,0.6);
    transition: all 0.2s;
    min-height: 32px;
  }
  .keno-cell:hover { border-color: rgba(168,85,247,0.4); color: #fff; }
  .keno-cell.keno-anchor {
    color: #fff; font-weight: 900;
  }
  .keno-anchor-dot {
    position: absolute; top: 2px; right: 2px;
    width: 4px; height: 4px; border-radius: 50%;
    background: #c084fc;
    box-shadow: 0 0 6px rgba(192,132,252,0.9);
  }

  /* ── KENO ANCHOR BALLS ──────────────────────────────────────── */
  .keno-anchors-section { margin-top: 1.25rem; }
  .keno-anchors-label {
    font-size: 0.62rem; letter-spacing: 0.2em; text-transform: uppercase;
    color: #c084fc; margin-bottom: 0.75rem;
  }
  .keno-anchors-row {
    display: flex; flex-wrap: wrap; gap: 0.6rem; justify-content: center;
  }
  .keno-anchor-ball {
    width: 48px; height: 48px; border-radius: 50%; position: relative;
    display: flex; align-items: center; justify-content: center;
    background: radial-gradient(circle at 38% 35%, rgba(168,85,247,0.6), rgba(88,28,135,0.9));
    box-shadow: 0 0 18px rgba(168,85,247,0.6), inset 0 1px 2px rgba(255,255,255,0.2);
  }
  .keno-anchor-ring {
    position: absolute; inset: -3px; border-radius: 50%;
    border: 2px solid rgba(168,85,247,0.5);
    animation: kenoPulse 2s ease-in-out infinite;
  }
  @keyframes kenoPulse {
    0%,100% { opacity: 1; transform: scale(1); }
    50%      { opacity: 0.4; transform: scale(1.08); }
  }
  .keno-anchor-num {
    font-size: 0.78rem; font-weight: 900; color: #fff; font-family: monospace;
    text-shadow: 0 0 8px rgba(192,132,252,0.8);
  }

  /* ── KENO EMPTY STATE ───────────────────────────────────────── */
  .keno-empty {
    text-align: center; padding: 3rem 1rem;
    display: flex; flex-direction: column; align-items: center; gap: 0.75rem;
  }
  .keno-empty-icon  { font-size: 2.5rem; opacity: 0.3; }
  .keno-empty-title { font-size: 0.8rem; font-weight: 700; letter-spacing: 0.2em; color: #7c3aed; }
  .keno-empty-desc  { font-size: 0.72rem; color: rgba(168,85,247,0.5); line-height: 1.7; max-width: 420px; }
  .keno-empty-desc code { color: #a855f7; }
  .keno-empty-desc strong { color: #c084fc; }

  @keyframes float {
    0% { transform: translateY(0px) scale(1.1); }
    50% { transform: translateY(-5px) scale(1.15); }
    100% { transform: translateY(0px) scale(1.1); }
  }
</style>
