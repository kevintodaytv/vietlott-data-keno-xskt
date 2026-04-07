<script lang="ts">
  import { onMount, onDestroy } from 'svelte';

  let megaData = {
    drawId: "SYNCING...",
    realWinningNumbers: [] as string[], // Dữ liệu thật từ kỳ trước
    aiPrediction: [] as string[],       // 6 số dự đoán cho kỳ tới
    confidence: 0,
    status: "CONNECTING"
  };

  let socket: WebSocket;

  onMount(() => {
    // Lắng nghe dòng chảy dữ liệu Vietlott từ Backend
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.hostname}:8000/stream/vietlott`;
    
    socket = new WebSocket(wsUrl);

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.action === "vietlott_update") {
          megaData = {
            drawId: data.draw_id,
            realWinningNumbers: data.winning_numbers,
            aiPrediction: data.ai_prediction, // VD: ['04', '12', '22', '28', '35', '41']
            confidence: data.confidence_score,
            status: "LIVE"
          };
        }
      } catch(e) {
        console.error("Lỗi parse WS Vietlott", e);
      }
    };
    
    socket.onclose = () => {
        megaData.status = "DISCONNECTED";
    };
  });

  onDestroy(() => {
    if (socket) socket.close();
  });
</script>

<div class="w-full bg-[#050202] border border-rose-500/20 rounded-[2rem] p-10 shadow-[0_0_80px_rgba(225,29,72,0.15)] relative mt-8">
  
  <!-- HEADER VIETLOTT -->
  <header class="flex justify-between items-center border-b border-rose-500/20 pb-6 mb-8">
    <div class="flex items-center gap-6">
      <div class="px-5 py-2 border rounded-full text-sm font-black tracking-widest uppercase {megaData.status === 'LIVE' ? 'bg-rose-500/10 border-rose-500/50 text-rose-500 shadow-[0_0_15px_rgba(225,29,72,0.3)]' : 'bg-slate-800 border-slate-600 text-slate-400 animate-pulse'}">
        🔥 MEGA 6/45 QUANTUM
      </div>
      <div class="text-slate-500 tracking-[0.2em] text-sm font-bold uppercase">
        KỲ QUAY <span class="text-white ml-2">#{megaData.drawId}</span>
      </div>
    </div>
    <div class="text-right">
      <div class="text-xs text-rose-500/70 tracking-widest uppercase font-bold mb-1">Độ tự tin AI</div>
      <div class="text-2xl font-black text-rose-500">{megaData.confidence}%</div>
    </div>
  </header>

  <!-- ALPHA POOL: BỘ 6 SỐ DỰ ĐOÁN -->
  <div class="mb-8">
    <h3 class="text-slate-400 text-xs tracking-[0.3em] uppercase mb-6">Tọa độ mục tiêu tiếp theo</h3>
    <div class="flex gap-4">
      {#if megaData.aiPrediction.length > 0}
        {#each megaData.aiPrediction as num}
          <div class="h-16 w-16 rounded-full flex items-center justify-center font-sans font-black text-2xl bg-gradient-to-br from-rose-400 to-rose-700 text-black shadow-[0_0_25px_rgba(225,29,72,0.6),inset_0_4px_8px_rgba(255,255,255,0.4)] border border-rose-300">
            {num}
          </div>
        {/each}
      {:else}
        <div class="text-rose-500/50 italic tracking-widest text-sm animate-pulse">
          ĐANG KHỞI CHẠY MCTS...
        </div>
      {/if}
    </div>
  </div>

</div>
