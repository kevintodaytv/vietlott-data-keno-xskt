<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { Wallet, RefreshCw, Zap, Activity } from 'lucide-svelte';

  let balance = 1000000;
  let isRefreshing = false;

  let megaData = {
    drawId: "SYNCING...",
    countdown: "--:--",
    alphaPool: [] as string[],
    status: "CONNECTING"
  };

  let socket: WebSocket;

  onMount(() => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/api/stream/vietlott`;
    
    socket = new WebSocket(wsUrl);

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.action === "vietlott_update") {
            megaData = {
                drawId: data.draw_id,
                countdown: data.countdown || "LIVE",
                alphaPool: data.ai_prediction, // 6 số thật từ MCTS
                status: "LIVE"
            };
        }
      } catch (e) {
        console.error("Data stream error:", e);
      }
    };

    socket.onclose = () => {
        megaData.status = "DISCONNECTED";
    };
  });
  
  onDestroy(() => {
     if (socket) socket.close();
  });

  function handleResetWallet() {
    isRefreshing = true;
    setTimeout(() => {
      balance = 1000000;
      isRefreshing = false;
    }, 500);
  }
</script>

<div class="min-h-screen bg-[#050202] text-slate-100 flex flex-col font-mono select-none">
  
  <!-- HEADER: Két sắt & Gateway -->
  <header class="sticky top-0 z-50 bg-[#0a0404]/80 backdrop-blur-md border-b border-rose-900/50 p-4">
    <div class="flex justify-between items-center">
      <div class="flex items-center gap-2">
        <div class="h-2 w-2 rounded-full shadow-[0_0_8px_currentColor] {megaData.status === 'LIVE' ? 'bg-rose-500 animate-pulse text-rose-500' : 'bg-amber-500 text-amber-500'}"></div>
        <span class="text-[10px] font-black tracking-widest text-slate-400 uppercase">
          {megaData.status === 'LIVE' ? 'GW: ACTIVE' : 'GW: SYNCING'}
        </span>
      </div>
      
      <div class="flex items-center gap-3 bg-slate-900/50 px-3 py-1.5 rounded-full border border-rose-500/30">
        <Wallet size={14} class="text-emerald-400" />
        <span class="text-sm font-bold text-emerald-400 font-sans">
          {balance.toLocaleString()} <span class="text-[10px]">V-VND</span>
        </span>
        <!-- svelte-ignore a11y-click-events-have-key-events - using an interactive element is preferred but for simplicity we keep the original logic -->
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <div on:click={handleResetWallet} class="cursor-pointer">
            <RefreshCw 
              size={14} 
              class="text-slate-500 active:text-white transition-all {isRefreshing ? 'animate-spin text-white' : ''}" 
            />
        </div>
      </div>
    </div>
  </header>

  <!-- MAIN CONTENT: Trực diện vào mục tiêu -->
  <main class="flex-1 p-5 space-y-6 flex flex-col justify-center">
    
    <!-- Tọa độ thời gian -->
    <div class="text-center">
      <p class="text-rose-500/70 text-xs uppercase tracking-[0.3em] font-bold">MEGA 6/45 QUANTUM</p>
      <p class="text-slate-500 text-[10px] uppercase tracking-widest mt-1 mb-2">KỲ #{megaData.drawId}</p>
      <div class="text-5xl font-black text-rose-500 tracking-tighter drop-shadow-[0_0_15px_rgba(225,29,72,0.4)]">
        {megaData.countdown}
      </div>
    </div>

    <!-- BỘ SỐ ALPHA (CRIMSON GLOW) -->
    <div class="relative p-6 rounded-[2.5rem] bg-gradient-to-b from-[#110505] to-[#0a0202] border border-rose-500/20 shadow-[0_20px_50px_rgba(0,0,0,0.8)] mt-4">
      <div class="absolute -top-3 left-1/2 -translate-x-1/2 bg-rose-500 text-black px-4 py-0.5 rounded-full text-[10px] font-black uppercase tracking-tighter shadow-[0_0_10px_rgba(225,29,72,0.8)]">
        AI MCTS: READY
      </div>
      
      <div class="grid grid-cols-3 gap-4 mt-4">
        {#if megaData.alphaPool.length > 0}
          {#each megaData.alphaPool as num}
            <div class="h-16 w-16 mx-auto flex items-center justify-center rounded-full bg-black border-2 border-rose-400 text-2xl font-sans font-black text-rose-400 shadow-[0_0_20px_rgba(225,29,72,0.5)] transition-transform active:scale-90">
              {num}
            </div>
          {/each}
        {:else}
           <!-- Trạng thái chờ dữ liệu thật -->
           {#each Array(6) as _}
            <div class="h-16 w-16 mx-auto rounded-full bg-slate-900 border border-slate-800 animate-pulse flex items-center justify-center">
              <span class="h-2 w-2 bg-slate-700 rounded-full"></span>
            </div>
           {/each}
        {/if}
      </div>
    </div>

    <!-- NÚT HÀNH ĐỘNG CỰC MẠNH (ONE-TAP) -->
    <div class="mt-auto pt-8">
      <button class="w-full py-5 rounded-2xl bg-gradient-to-r from-rose-600 to-rose-500 hover:from-rose-500 hover:to-rose-400 active:scale-95 transition-all shadow-[0_0_30px_rgba(225,29,72,0.4)] flex flex-col items-center justify-center gap-1 group border border-rose-400/50">
        <span class="text-black font-black text-xl uppercase tracking-widest flex items-center gap-2">
          HÀNH ĐỘNG NGAY <Zap size={20} fill="black" />
        </span>
        <span class="text-black/70 text-[10px] font-bold uppercase tracking-widest">
          Khóa mục tiêu Mega 6/45
        </span>
      </button>
    </div>
  </main>
  
  <!-- DẢI TRẠNG THÁI CUỐI (Tối giản) -->
  <footer class="p-3 text-center opacity-30">
     <span class="text-[8px] font-bold tracking-[0.3em] text-slate-500 flex items-center justify-center gap-2">
        <Activity size={10} /> X-PREDICTOR MOBILE HUB V3.0
     </span>
  </footer>
</div>
