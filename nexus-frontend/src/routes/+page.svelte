<script lang="ts">
  import { Canvas } from '@threlte/core';
  import QuantumSphere from '$lib/QuantumSphere.svelte';
  import CognitionGauge from '$lib/CognitionGauge.svelte';
  import VietlottHub from '$lib/VietlottHub.svelte';
  import MobileVietlottHub from '$lib/MobileVietlottHub.svelte';
  import MarketFlow from '$lib/MarketFlow.svelte';
  import AgentDNAChat from '$lib/AgentDNAChat.svelte';
  import NeuralCoreDashboard from '$lib/NeuralCoreDashboard.svelte';
import { onMount, onDestroy } from 'svelte';
  import { isWarRoomActive } from '$lib/store';

  // ─── WebSocket & Polling Timers (HMR Safe) ──────────────────────────────────
  let socket: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let pingTimer: ReturnType<typeof setInterval> | null = null;
  let clock: ReturnType<typeof setInterval> | null = null;
  let evolutionRefresh: ReturnType<typeof setInterval> | null = null;
  let httpPollTimer: ReturnType<typeof setTimeout> | null = null;
  let pollIntervalVar: ReturnType<typeof setInterval> | null = null;
  let isDestroyed = false; 
  let reconnectAttempts = 0;

  onDestroy(() => {
      // ─── HMR CLEANUP: Chạy TỰ ĐỘNG khi Vite reload để dập hết zombie timer/WS ──
      isDestroyed = true;
      wsOnline = false;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (httpPollTimer) clearTimeout(httpPollTimer);
      if (pollIntervalVar) clearInterval(pollIntervalVar);
      if (pingTimer) clearInterval(pingTimer);
      if (clock) clearInterval(clock);
      if (evolutionRefresh) clearInterval(evolutionRefresh);
      
      if (socket) {
          socket.onclose = null; // Tránh loop reconnect
          socket.onerror = null;
          socket.onmessage = null;
          socket.onopen = null;
          try { socket.close(1000, "Vite HMR Reload"); } catch (_) {}
          socket = null;
      }
      if (typeof window !== 'undefined' && (window as any).__keno_ws_cleanup) {
          delete (window as any).__keno_ws_cleanup;
      }
  });

  // ─── STATE ────────────────────────────────────────────────────────────────
  let isAnalyzing = false;
  let isSwarmActive = false;
  let predictionData: string[] | null = null;
  let confidenceLevel: number | null = null;
  let status: 'SECURE' | 'RED_ALERT' = 'SECURE';
  
  type AgentMessage = { agent: string, msg: string, time: string, color: string };
  let aiLogs: AgentMessage[] = [];
  let countdown = '00:00';
  let bootComplete = false;
  let bootLines: string[] = [];
  let showGrid = false;
  let activeSkill = -1;

  // ─── CONNECTION STATUS ────────────────────────────────────────────────
  let wsOnline = false;         // WebSocket có đang OPEN không
  let lastKnownDrawId: number | null = null; // Drew ID cuối cùng đã xử lý (cho HTTP polling)

  // ─── EVOLUTION SIDEBAR DRAWER ────────────────────────────────────────
  let showEvolutionPanel = false;
  function openEvolutionPanel() {
    showEvolutionPanel = true;
    if (evolutionLog.length === 0) fetchEvolutionData();
  }
  function closeEvolutionPanel() { showEvolutionPanel = false; }

  // ─── SETTINGS MODAL ──────────────────────────────────────────────
  let showSettings = false;

  // ─── TABS & TERRITORY STATE ───────────────────────────────────────────────
  let selectedRegion = 'KENO';
  let activeProvince = '';
  let sphereColor = '#06b6d4';
  let predictionMatrix: Record<string, string[]> | null = null;
  let heatmapData: Record<string, number> = {};
  let anchors: number[] = [];

  // ─── KENO STATE ───────────────────────────────────────────────────────────
  let kenoHits: number[] = [];
  let kenoMisses: number[] = [];
  let lastKenoAnchors: number[] = [];

  $: if (lastKenoAnchors && kenoLatestWinningNumbers) {
      kenoHits = lastKenoAnchors.filter(n => kenoLatestWinningNumbers.includes(n));
      kenoMisses = lastKenoAnchors.filter(n => !kenoLatestWinningNumbers.includes(n));
  }
  $: sortedKenoAnchors = [...kenoAnchors].sort((a,b) => a - b);

  function getKenoNumberClass(numTarget: number, hits: number[], anchors: number[]) {
      if (hits.includes(numTarget)) return "border-2 border-white text-white font-black scale-110 shadow-[0_0_20px_rgba(255,255,255,1),inset_0_0_15px_rgba(255,255,255,0.8)] z-10 bg-white/20";
      if (anchors.includes(numTarget)) return "border-2 border-yellow-400 text-yellow-400 font-bold scale-105 shadow-[0_0_15px_rgba(250,204,21,0.6),inset_0_0_8px_rgba(250,204,21,0.3)] z-10 bg-yellow-900/20";
      return "bg-[#0f0f13] text-slate-600 shadow-[inset_0_2px_5px_rgba(255,255,255,0.03),0_5px_15px_rgba(0,0,0,0.6)] border border-slate-800/60";
  }

  let kenoHeatmap: Record<number, number> = {};
  let kenoAnchors: number[] = [];
  let kenoNextDraw = '00:00:00';
  let kenoDrawCount = 0;
  let kenoLatestDraw: number | null = null;
  let kenoLatestWinningNumbers: number[] = [];

  // ─── KENO PHASE STATE ───────────────────────────────────────────────────
  $: kenoTimeSeconds = parseInt(kenoNextDraw.split(':')[0] || '0') * 60 + parseInt(kenoNextDraw.split(':')[1] || '0');
  $: kenoTimePhase = kenoTimeSeconds > 90 ? 'SAFE' : (kenoTimeSeconds > 30 ? 'WARNING' : 'DANGER');
  $: kenoPhaseColorText = kenoTimePhase === 'SAFE' ? 'text-cyan-400' : (kenoTimePhase === 'WARNING' ? 'text-amber-500' : 'text-red-500');
  $: kenoPhaseColor = kenoTimePhase === 'SAFE' ? 'text-cyan-400 border-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.3)]' : 
                      (kenoTimePhase === 'WARNING' ? 'text-amber-500 border-amber-500 shadow-[0_0_15px_rgba(245,158,11,0.5)]' : 
                      'text-red-500 border-red-500 animate-pulse shadow-[0_0_20px_rgba(239,68,68,0.8)]');
  $: kenoPhaseLabel = kenoTimePhase === 'SAFE' ? '✅ THỜI GIAN VÀO LỆNH' : 
                      (kenoTimePhase === 'WARNING' ? '⚠️ CHUẨN BỊ ĐÓNG VÉ' : 
                      '⛔ ĐÓNG VÉ - CHỜ XỔ SỐ');

  // ─── MARKET FLOW STATE ───────────────────────────────────────────────────
  let marketDataFlow = {
    chanLE: { pred: 'LẺ', confidence: 0, history: Array(10).fill('HÒA') },
    lonNho: { pred: 'LỚN', confidence: 0, history: Array(10).fill('HÒA') }
  };

  // ─── VIRTUAL WALLET STATE (server-managed) ───────────────────────────────
  let kenoWalletBalance = 1_000_000;
  let mfWalletBalance = 1_000_000;
  let mfTicketHistory: any[] = [];
  let latestMarketFlow: any = {};
  const autoBetEnabled = true; // ALWAYS ON — server tự bet không cần client
  type TicketRecord = {
    id: string;
    draw_id: number;
    numbers: number[];
    cost: number;
    status: 'PENDING' | 'WIN' | 'LOSS' | 'BREAK_EVEN';
    matches: number;
    profit: number;
    time: string;
  };
  let ticketHistory: TicketRecord[] = [];
  let isWalletLoaded = false;
  let isSyncingFromBackend = false;

  let showResultTicker = false;
  let tickerPnL = 0;

  // ─── USER SETTINGS STATE ─────────────────────────────────────────────────
  let userSettings = {
      masterToggle: true,
      soundEnabled: true,
      audioVolume: 50,
      winSound: 'beep_win',
      lossSound: 'beep_loss',
      breakEvenSound: 'beep_countdown',
      countdownSound: 'beep_countdown',
      autoBetEnabled: true,
      cbStopLoss: 3000000,
      cbTakeProfit: 5000000,
      cbCooldownFailLimit: 4,
      cbKellyFraction: 2.5,
      popupWinText: 'Tuyệt vời Sếp! Mẻ này cắn đậm',
      popupLossText: 'Lệch nhịp sới! Kỳ sau gỡ lại Sếp ơi',
      popupBreakEvenText: 'Hòa tiền! Chưa xi nhê',
      showFireworks: true,
      popupEnabled: true
  };
  let isSettingsLoaded = false;
  let lastSyncedSettings = '';

  $: if (isSettingsLoaded && typeof window !== 'undefined') {
      const currentSettings = JSON.stringify(userSettings);
      if (currentSettings !== lastSyncedSettings) {
          lastSyncedSettings = currentSettings;
          fetch('/api/settings/sync', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: currentSettings
          }).catch(err => console.error('Lỗi sync settings:', err));
      }
  }

  // ─── P&L ANALYTICS (reactive) ──────────────────────────────────────────
  $: settledTickets  = ticketHistory.filter(t => t.status !== 'PENDING');
  $: winTickets      = ticketHistory.filter(t => t.status === 'WIN').length;
  $: lossTickets     = ticketHistory.filter(t => t.status === 'LOSS').length;
  $: pendingCount    = ticketHistory.filter(t => t.status === 'PENDING').length;
  $: dailyPnL        = settledTickets.reduce((sum, t) => sum + (t.profit || 0), 0);
  $: winRate         = (winTickets + lossTickets) > 0
                         ? Math.round((winTickets / (winTickets + lossTickets)) * 100)
                         : 0;

  function clearTicketHistory() {
    ticketHistory = [];
    addLog('[VÍ ẢO] Đã xóa lịch sử vé (số dư giữ nguyên).', 'SYSTEM');
  }

  function clearWallet() {
    ticketHistory = [];
    kenoWalletBalance = 1_000_000;
    addLog('[VÍ ẢO] Đã xóa lịch sử vé và reset số dư về 1,000,000đ.', 'SYSTEM');
  }


  let lastSyncedWalletState = '';

  // Server là nguồn sự thật — chỉ lưu localStorage để UI không reset khi refresh
  $: if (isWalletLoaded && typeof window !== 'undefined') {
      localStorage.setItem('kenoWalletBalance', kenoWalletBalance.toString());
  }
  
  // ─── MARKET FLOW VIRTUAL WALLET ──────────────────────────────

  let isMarketWalletLoaded = false;
  let marketWalletBalance = 1_000_000;
  let lastSyncedMarketWalletState = '';
  type MarketTicketRecord = {
    id: string;
    draw_id: number;
    chanLe: string;
    lonNho: string;
    cost: number;
    status: 'PENDING' | 'WIN' | 'LOSS' | 'BREAK_EVEN';
    profit: number;
    time: string;
  };
  let marketTicketHistory: MarketTicketRecord[] = [];
  
  // Server là nguồn sự thật cho market wallet — chỉ lưu localStorage
  $: if (isMarketWalletLoaded && typeof window !== 'undefined') {
      localStorage.setItem('marketWalletBalance', marketWalletBalance.toString());
      localStorage.setItem('marketTicketHistory', JSON.stringify(marketTicketHistory));
  }
  
  $: marketSettledTickets  = marketTicketHistory.filter(t => t.status !== 'PENDING');
  $: marketWinTickets      = marketTicketHistory.filter(t => t.status === 'WIN').length;
  $: marketLossTickets     = marketTicketHistory.filter(t => t.status === 'LOSS').length;
  $: marketPendingCount    = marketTicketHistory.filter(t => t.status === 'PENDING').length;
  $: marketDailyPnL        = marketSettledTickets.reduce((sum, t) => sum + (t.profit || 0), 0);
  $: marketWinRate         = (marketWinTickets + marketLossTickets) > 0
                         ? Math.round((marketWinTickets / (marketWinTickets + marketLossTickets)) * 100)
                         : 0;

  function clearMarketTicketHistory() {
    marketTicketHistory = [];
    addLog('[VÍ ẢO MARKET] Đã xóa lịch sử vé (số dư giữ nguyên).', 'SYSTEM');
  }

  function clearMarketWallet() {
    marketTicketHistory = [];
    marketWalletBalance = 1_000_000;
    addLog('[VÍ ẢO MARKET FLOW] Đã xóa lịch sử vé và reset số dư về 1,000,000đ.', 'SYSTEM');
  }

  function marketValidatePendingTickets(latestDrawId: number, actualChanLe: string, actualLonNho: string) {
      let walletChanged = false;
      let roundHits = 0;
      let roundProfit = 0;
      let roundLoss = 0;
      marketTicketHistory = marketTicketHistory.map(ticket => {
          if (ticket.status === 'PENDING' && ticket.draw_id === latestDrawId) {
              let hits = 0;
              if (ticket.chanLe === actualChanLe) hits++;
              if (ticket.lonNho === actualLonNho) hits++;
              let status: 'WIN'|'LOSS'|'BREAK_EVEN' = hits === 2 ? 'WIN' : hits === 1 ? 'BREAK_EVEN' : 'LOSS';
              let profit = hits === 2 ? 20000 : hits === 1 ? 0 : -20000;
              marketWalletBalance += profit;
              walletChanged = true;
              if (profit > 0) { roundHits = hits; roundProfit += profit; }
              else if (profit < 0) { roundLoss += Math.abs(profit); }
              return { ...ticket, status, profit };
          }
          return ticket;
      });
      if (walletChanged) {
          const netPnL = roundProfit - roundLoss;
          
          if (netPnL < 0) {
              marketConsecutiveLossCount++;
              if (marketConsecutiveLossCount >= userSettings.cbCooldownFailLimit) {
                  marketCooldownRemaining = 5;
                  marketConsecutiveLossCount = 0;
                  addLog(`[CIRCUIT_BREAKER] KÍCH HOẠT COOL-DOWN! Thua ${userSettings.cbCooldownFailLimit} kỳ liên tiếp, Market Flow sẽ nghỉ 5 kỳ.`, 'SYSTEM');
              }
          } else if (netPnL > 0) {
              marketConsecutiveLossCount = 0;
          }

          // ── Log chi tiết Lãi/Lỗ ròng Market Flow ──────────────────────────
          if (roundProfit > 0 && roundHits > 0) {
              addLog(`[VÍ MARKET] 🎯 KỲ #${latestDrawId} — THẮNG! ${roundHits}/2 dự đoán đúng. +${roundProfit.toLocaleString('vi-VN')}đ (Lãi ròng: +${netPnL.toLocaleString('vi-VN')}đ)`, 'SCOUT');
              triggerWinCelebration(roundHits, roundProfit);
          } else if (roundLoss > 0) {
              addLog(`[VÍ MARKET] 💸 KỲ #${latestDrawId} — THUA. Thực tế: ${actualChanLe}/${actualLonNho}. Lỗ: -${roundLoss.toLocaleString('vi-VN')}đ | Số dư: ${marketWalletBalance.toLocaleString('vi-VN')}đ`, 'SYSTEM');
          } else {
              addLog(`[VÍ MARKET] KỲ #${latestDrawId} — HÒA (1/2 đúng). Không lãi không lỗ.`, 'SYSTEM');
          }
          // ── Tổng P&L phiên Market Flow ──────────────────────────────────
          const marketSessionPnL = marketTicketHistory
              .filter(t => t.status !== 'PENDING')
              .reduce((sum, t) => sum + (t.profit || 0), 0);
          const mSign = marketSessionPnL >= 0 ? '+' : '';
          addLog(`[VÍ MARKET] P&L Phiên: ${mSign}${marketSessionPnL.toLocaleString('vi-VN')}đ | Ví Market: ${marketWalletBalance.toLocaleString('vi-VN')}đ`, 'NEURAL');
      }
  }

  // ─── CIRCUIT BREAKER MODULE 3 ───
  let marketConsecutiveLossCount = 0;
  let marketCooldownRemaining = 0;

  function marketAutoBuyTicket(nextDrawId: number, predChanLe: string, predLonNho: string) {
      if (!autoBetEnabled) return;
      if (marketTicketHistory.some(t => t.draw_id === nextDrawId)) return;
      
      // COOL-DOWN
      if (marketCooldownRemaining > 0) {
          marketCooldownRemaining--;
          addLog(`[VÍ ẢO MARKET] CIRCUIT BREAKER: NGHỈ MÁT ${marketCooldownRemaining} KỲ.`, 'SYSTEM');
          return;
      }
      
      // TAKE PROFIT / STOP LOSS
      let profitMarket = marketWalletBalance - 1_000_000;
      if (profitMarket >= userSettings.cbTakeProfit) {
          addLog(`[CIRCUIT_BREAKER] TAKE PROFIT: CHỐT LÃI ${(userSettings.cbTakeProfit/1000000).toFixed(1)} TRIỆU (MARKET FLOW)! TẠM DỪNG.`, 'SYSTEM');
          return;
      }
      if (profitMarket <= -userSettings.cbStopLoss) {
          addLog(`[CIRCUIT_BREAKER] STOP LOSS: CHẠM ĐÁY ÂM ${(userSettings.cbStopLoss/1000000).toFixed(1)} TRIỆU (MARKET FLOW)! KHÓA TÍN HIỆU.`, 'SYSTEM');
          return;
      }
      
      // KELLY CRITERION: Fractional 1/4, max 10% max
      const kellyFrac = (typeof userSettings.cbKellyFraction === 'number' && !isNaN(userSettings.cbKellyFraction))
          ? userSettings.cbKellyFraction : 25;
      let betTarget = marketWalletBalance > 0 ? (marketWalletBalance * (kellyFrac / 100)) : 10000;
      let maxBet = marketWalletBalance > 0 ? (marketWalletBalance * 0.1) : 10000;
      let cost = Math.max(10000, Math.min(betTarget, maxBet));
      // MarketFlow bet can be arbitrary or multiple of 10000
      cost = Math.floor(cost / 10000) * 10000;
      if (isNaN(cost) || cost < 10000) cost = 10000;

      marketWalletBalance -= (cost * 2); // bet on both chanLe and lonNho

      const newTicket: MarketTicketRecord = {
          id: Math.random().toString(36).substr(2, 9),
          draw_id: nextDrawId, chanLe: predChanLe, lonNho: predLonNho,
          cost: cost * 2, status: 'PENDING', profit: 0,
          time: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
      };
      marketTicketHistory = [newTicket, ...marketTicketHistory];
  }

  const paytable = { 10: 2000000000, 9: 150000000, 8: 7400000, 7: 600000, 6: 100000, 5: 20000, 0: 50000 };

  let showWinTicker = false;
  let winTickerProfit = 0;
  let winTickerHits = 0;

  // ─── Audio Engine v2.0 — Web Audio API Primary + CDN Fallback ──
  // Web Audio: không cần CDN, hoạt động 100% offline
  let _audioCtx: AudioContext | null = null;
  function _getAudioCtx(): AudioContext | null {
      if (typeof window === 'undefined') return null;
      if (!_audioCtx || _audioCtx.state === 'closed') {
          _audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      if (_audioCtx.state === 'suspended') _audioCtx.resume();
      return _audioCtx;
  }

  // Phát âm thanh từ Web Audio API — không phụ thuộc CDN
  function playWebTone(preset: 'win' | 'loss' | 'break_even' | 'countdown' | 'jackpot') {
      const ctx = _getAudioCtx();
      if (!ctx) return;
      const vol = (userSettings.audioVolume ?? 80) / 100;

      type S = { freq: number; type: OscillatorType; start: number; dur: number; gain: number };
      const map: Record<string, S[]> = {
          win:        [{freq:523,type:'sine',start:0,dur:0.35,gain:0.35},{freq:659,type:'sine',start:0.15,dur:0.35,gain:0.35},{freq:784,type:'sine',start:0.30,dur:0.5,gain:0.4}],
          jackpot:    [{freq:523,type:'sine',start:0,dur:0.2,gain:0.4},{freq:659,type:'sine',start:0.1,dur:0.2,gain:0.4},{freq:784,type:'sine',start:0.2,dur:0.2,gain:0.4},{freq:1047,type:'sine',start:0.3,dur:0.6,gain:0.5}],
          loss:       [{freq:330,type:'sawtooth',start:0,dur:0.25,gain:0.2},{freq:196,type:'sawtooth',start:0.22,dur:0.35,gain:0.2}],
          break_even: [{freq:440,type:'sine',start:0,dur:0.15,gain:0.2},{freq:440,type:'sine',start:0.2,dur:0.15,gain:0.1}],
          countdown:  [{freq:880,type:'sine',start:0,dur:0.08,gain:0.18}],
      };
      const schedules: S[] = map[preset] ?? [];

      schedules.forEach(({ freq, type, start, dur, gain }) => {
          const osc  = ctx.createOscillator();
          const gNode = ctx.createGain();
          osc.connect(gNode); gNode.connect(ctx.destination);
          osc.frequency.value = freq;
          osc.type = type;
          const t0 = ctx.currentTime + start;
          gNode.gain.setValueAtTime(gain * vol, t0);
          gNode.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
          osc.start(t0); osc.stop(t0 + dur + 0.01);
      });
  }

  const DEFAULT_KHO_AM_THANH: Record<string, string> = {
      // WIN SOUNDS — CDN fallback (nếu user muốn dùng)
      anime_wow:     'https://www.myinstants.com/media/sounds/anime-wow-sound-effect.mp3',
      casino_jackpot:'https://www.myinstants.com/media/sounds/slotmachine.mp3',
      mario_coin:    'https://www.myinstants.com/media/sounds/super-mario-coin-sound.mp3',
      gta_passed:    'https://www.myinstants.com/media/sounds/gta-san-andreas-mission-complete-sound-hq.mp3',
      tada:          'https://www.myinstants.com/media/sounds/win31.mp3',
      // COUNTDOWN SOUNDS
      vine_boom:     'https://www.myinstants.com/media/sounds/vine-boom.mp3',
      ticking:       'https://www.myinstants.com/media/sounds/clock_ticking_edited-2.mp3',
      to_be_continued:'https://www.myinstants.com/media/sounds/untitled_1071.mp3',
      sigma:         'https://www.myinstants.com/media/sounds/erm-what-the-sigma_su7GnzC.mp3',
      jeopardy:      'https://www.myinstants.com/media/sounds/jeopardy-themelq.mp3',
      // WEB AUDIO TONES — hoạt động không cần mạng
      beep_win:      '__web_audio__win',
      beep_jackpot:  '__web_audio__jackpot',
      beep_loss:     '__web_audio__loss',
      beep_countdown:'__web_audio__countdown',
  };

  let customAmThanh: Record<string, string> = {}; // { 'key': 'blob:http...' }

  // ── IDB Wrapper ──
  const DB_NAME = 'SniperX_AudioDB';
  const STORE_NAME = 'custom_sounds';
  let hiddenFileInput: HTMLInputElement;
  let activeUploadKey: string | null = null;

  function initIDB(): Promise<IDBDatabase> {
      return new Promise((resolve, reject) => {
          const req = indexedDB.open(DB_NAME, 1);
          req.onupgradeneeded = (e: any) => {
              if (!e.target.result.objectStoreNames.contains(STORE_NAME)) {
                  e.target.result.createObjectStore(STORE_NAME);
              }
          };
          req.onsuccess = (e: any) => resolve(e.target.result);
          req.onerror = (e) => reject(e);
      });
  }

  async function loadCustomAudioFromDB() {
      if (typeof indexedDB === 'undefined') return;
      try {
          const db = await initIDB();
          const tx = db.transaction(STORE_NAME, 'readonly');
          const store = tx.objectStore(STORE_NAME);
          const req = store.getAllKeys();
          req.onsuccess = (e: any) => {
              const keys = e.target.result;
              keys.forEach((key: string) => {
                  const getReq = store.get(key);
                  getReq.onsuccess = (evt: any) => {
                      const file = evt.target.result;
                      if (file) {
                          customAmThanh[key] = URL.createObjectURL(file);
                      }
                  };
              });
              setTimeout(() => { customAmThanh = { ...customAmThanh }; }, 100);
          };
      } catch (err) {
          console.error('[IDB] Lỗi tải IDB:', err);
      }
  }

  async function saveCustomAudio(key: string, file: File) {
      if (typeof indexedDB === 'undefined') return;
      try {
          const db = await initIDB();
          const tx = db.transaction(STORE_NAME, 'readwrite');
          const store = tx.objectStore(STORE_NAME);
          store.put(file, key);
          
          tx.oncomplete = () => {
              if (customAmThanh[key]) URL.revokeObjectURL(customAmThanh[key]);
              customAmThanh[key] = URL.createObjectURL(file);
              customAmThanh = { ...customAmThanh };
              addLog(`[AUDIO] Đã lưu âm thanh tùy chỉnh cho ${key}`, 'SYSTEM');
              
              const url = customAmThanh[key];
              audioMap[key] = new (window as any).Audio(url);
              
              const isWin = ['gta_passed', 'anime_wow', 'casino_jackpot', 'mario_coin', 'tada'].includes(key);
              if (isWin) { userSettings.winSound = key; playAudioTone('win'); }
              else { userSettings.countdownSound = key; playAudioTone('countdown'); }
          };
      } catch (err) {
          console.error('[IDB] Lỗi lưu IDB:', err);
      }
  }

  async function deleteCustomAudio(key: string) {
      if (typeof indexedDB === 'undefined') return;
      try {
          const db = await initIDB();
          const tx = db.transaction(STORE_NAME, 'readwrite');
          const store = tx.objectStore(STORE_NAME);
          store.delete(key);
          tx.oncomplete = () => {
              if (customAmThanh[key]) URL.revokeObjectURL(customAmThanh[key]);
              delete customAmThanh[key];
              customAmThanh = { ...customAmThanh };
              addLog(`[AUDIO] Đã khôi phục mặc định cho ${key}`, 'SYSTEM');
              if (audioMap[key]) delete audioMap[key];
          };
      } catch (err) {
          console.error('[IDB] Lỗi xóa IDB:', err);
      }
  }

  function handleFileSelect(event: any) {
      const file = event.target.files[0];
      if (file && activeUploadKey) {
          saveCustomAudio(activeUploadKey, file);
      }
      activeUploadKey = null;
      event.target.value = '';
  }

  function triggerUpload(key: string) {
      activeUploadKey = key;
      if (hiddenFileInput) hiddenFileInput.click();
  }

  let audioMap: {[key: string]: HTMLAudioElement} = {};

  function playAudioTone(type: 'win' | 'countdown' | 'loss' | 'break_even') {
      if (!userSettings.masterToggle || !userSettings.soundEnabled) return;
      const soundType = type === 'win'     ? userSettings.winSound
                      : type === 'countdown' ? userSettings.countdownSound
                      : type === 'loss'    ? (userSettings.lossSound ?? 'beep_loss')
                      : (userSettings.breakEvenSound ?? 'beep_countdown');
      if (soundType === 'none') return;

      // Web Audio API tones — không cần CDN
      const url = customAmThanh[soundType] || DEFAULT_KHO_AM_THANH[soundType];
      if (url?.startsWith('__web_audio__')) {
          const preset = url.replace('__web_audio__', '') as any;
          playWebTone(preset);
          return;
      }

      if (url && typeof window !== 'undefined') {
          if (!audioMap[soundType]) {
              audioMap[soundType] = new (window as any).Audio(url);
          }
          const audio = audioMap[soundType];
          audio.volume = (userSettings.audioVolume ?? 80) / 100;
          audio.currentTime = 0;
          audio.play().catch(() => {
              // CDN thất bại → fallback Web Audio
              if (type === 'win') playWebTone('win');
              else if (type === 'countdown') playWebTone('countdown');
              else if (type === 'loss') playWebTone('loss');
              else playWebTone('break_even');
          });
      }
  }

  // ─── Screen flash state ─────────────────────────────────────────
  let screenFlash: 'win' | 'loss' | 'break_even' | null = null;
  function triggerScreenFlash(type: 'win' | 'loss' | 'break_even') {
      screenFlash = type;
      setTimeout(() => { screenFlash = null; }, 700);
  }

  function triggerWinCelebration(hits: number, profit: number) {
      if (!userSettings.masterToggle) return;
      winTickerHits = hits;
      winTickerProfit = profit;
      showWinTicker = true;

      if (profit > 0) {
          // WIN: chime + confetti + green flash
          playAudioTone(hits >= 8 ? 'win' : 'win');
          if (hits >= 8) playWebTone('jackpot');
          triggerScreenFlash('win');
          import('canvas-confetti').then((m) => {
              if (!userSettings.showFireworks) return;
              const confetti = m.default;
              const duration = hits >= 8 ? 4000 : 2500;
              const end = Date.now() + duration;
              const colors = hits >= 8
                  ? ['#ffd700', '#ff6b00', '#ffffff', '#00ff88']
                  : ['#ffd700', '#00ff00', '#ffffff'];
              (function frame() {
                  confetti({ particleCount: hits >= 8 ? 12 : 5, angle: 60,  spread: 55, origin: { x: 0 }, zIndex: 9999, colors });
                  confetti({ particleCount: hits >= 8 ? 12 : 5, angle: 120, spread: 55, origin: { x: 1 }, zIndex: 9999, colors });
                  if (Date.now() < end) requestAnimationFrame(frame);
              }());
          });
      } else if (profit < 0) {
          // LOSS: descending tone + red flash
          playAudioTone('loss');
          triggerScreenFlash('loss');
      } else {
          // BREAK_EVEN: subtle ping + yellow flash
          playAudioTone('break_even');
          triggerScreenFlash('break_even');
      }

      setTimeout(() => { showWinTicker = false; }, 5000);
  }

  function validatePendingTickets(latestDrawId: number, winningNumbers: number[]) {
      let walletChanged = false;
      let roundHits = 0;
      let roundProfit = 0;
      let roundLoss = 0;
      let ticketsSettled = 0;

      ticketHistory = ticketHistory.map(ticket => {
          if (ticket.status === 'PENDING' && ticket.draw_id === latestDrawId) {
              const matched = ticket.numbers.filter(n => winningNumbers.includes(n));
              const mCount = matched.length;
              const reward = paytable[mCount as keyof typeof paytable] || 0;
              const profit = reward - ticket.cost;
              kenoWalletBalance += reward;
              walletChanged = true;
              ticketsSettled++;
              
              if (profit > 0) {
                  roundProfit += profit;
                  roundHits = Math.max(roundHits, mCount);
              } else if (profit < 0) {
                  roundLoss += Math.abs(profit);
              }
              
              return {
                  ...ticket,
                  status: profit > 0 ? 'WIN' : (profit === 0 ? 'BREAK_EVEN' : 'LOSS'),
                  matches: mCount,
                  profit: profit
              };
          }
          return ticket;
      });
      
      if (walletChanged) {
          const netPnL = roundProfit - roundLoss;

          if (netPnL < 0) {
              kenoConsecutiveLossCount++;
              if (kenoConsecutiveLossCount >= 4) {
                  kenoCooldownRemaining = 5;
                  kenoConsecutiveLossCount = 0;
                  addLog('[CIRCUIT_BREAKER] KÍCH HOẠT COOL-DOWN! Thua 4 kỳ liên tiếp, Keno sẽ nghỉ 5 kỳ.', 'SYSTEM');
              }
          } else if (netPnL > 0) {
              kenoConsecutiveLossCount = 0;
          }

          // Kích hoạt UI Ticker
          tickerPnL = netPnL;
          showResultTicker = true;
          setTimeout(() => showResultTicker = false, 4500);

          // ── Log chi tiết Lãi/Lỗ ròng ──────────────────────────────────────
          if (roundProfit > 0 && roundHits > 0) {
              addLog(`[VÍ KENO] 🎯 KỲ #${latestDrawId} — TRÚNG MÁNH! ${roundHits} số khớp. Thưởng +${roundProfit.toLocaleString('vi-VN')}đ | Lãi ròng: +${netPnL.toLocaleString('vi-VN')}đ`, 'SCOUT');
              triggerWinCelebration(roundHits, roundProfit);
          } else if (roundLoss > 0) {
              addLog(`[VÍ KENO] 💸 KỲ #${latestDrawId} — MISS. Lỗ: -${roundLoss.toLocaleString('vi-VN')}đ | Số dư còn: ${kenoWalletBalance.toLocaleString('vi-VN')}đ`, 'SYSTEM');
              triggerWinCelebration(0, -roundLoss);
          } else {
              addLog(`[VÍ KENO] KỲ #${latestDrawId} — HÒA. Không lãi không lỗ.`, 'SYSTEM');
              triggerWinCelebration(0, 0);
          }
          // ── Tổng P&L phiên ngày (từ settledTickets) ──────────────────────
          const sessionPnL = ticketHistory
              .filter(t => t.status !== 'PENDING')
              .reduce((sum, t) => sum + (t.profit || 0), 0);
          const sessionSign = sessionPnL >= 0 ? '+' : '';
          addLog(`[VÍ KENO] P&L Phiên: ${sessionSign}${sessionPnL.toLocaleString('vi-VN')}đ | Ví: ${kenoWalletBalance.toLocaleString('vi-VN')}đ`, 'NEURAL');
      }
  }

  // ─── CIRCUIT BREAKER MODULE 3 ───
  let kenoConsecutiveLossCount = 0;
  let kenoCooldownRemaining = 0;

  function autoBuyTicket(targetDrawId: number, numbers: number[]) {
      if (!userSettings.autoBetEnabled || numbers.length === 0 || !userSettings.masterToggle) return;
      
      // PREVENT DUPLICATE TICKET FOR THE SAME DRAW
      const alreadyBought = ticketHistory.some(t => t.draw_id === targetDrawId && t.status === 'PENDING');
      if (alreadyBought) return;
      
      // COOL-DOWN
      if (kenoCooldownRemaining > 0) {
          kenoCooldownRemaining--;
          addLog(`[VÍ ẢO KENO] CIRCUIT BREAKER: NGHỈ MÁT ${kenoCooldownRemaining} KỲ.`, 'SYSTEM');
          return;
      }
      
      // TAKE PROFIT / STOP LOSS
      let profitKeno = kenoWalletBalance - 1_000_000;
      if (profitKeno >= 5_000_000) {
          addLog('[CIRCUIT_BREAKER] TAKE PROFIT: CHỐT LÃI 5 TRIỆU! DỪNG AUTO-BET.', 'SYSTEM');
          return;
      }
      if (profitKeno <= -3_000_000) {
          addLog('[CIRCUIT_BREAKER] STOP LOSS: CHẠM ĐÁY ÂM 3 TRIỆU! KHÓA TÍN HIỆU.', 'SYSTEM');
          return;
      }
      
      // GIÁ VÉ CỐ ĐỊNH 10.000đ/kỳ (theo cài đặt mặc định của Sếp)
      const cost = 10000;

      // Không deduct client-side — server auto-bet quản lý balance và broadcast WALLET_SYNC
      addLog(`[VÍ ẢO] Đã Auto-Buy vé #${targetDrawId} (-${cost.toLocaleString('vi-VN')}đ). Server đang xử lý...`);
  }

  
  // ─── ERROR HANDLING & ZERO-MOCK ───────────────────────────────────────────
  let statusMessage = "SYSTEM_READY: WAITING FOR INSTRUCTION";
  
  // ─── DRAGGABLE EVOLUTION TRIGGER ──────────────────────────────────────────
  let evoButtonTranslateX = 0; // translation in px
  let evoButtonTranslateY = 0; // translation in px
  let isDraggingEvo = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let origTranslateX = 0;
  let origTranslateY = 0;
  let didDrag = false;

  function onEvoPointerDown(e: PointerEvent) {
    const target = e.currentTarget as HTMLElement;
    target.setPointerCapture(e.pointerId);
    isDraggingEvo = true;
    didDrag = false;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
  }

  function onEvoPointerMove(e: PointerEvent) {
    if (!isDraggingEvo) return;
    const dx = e.clientX - dragStartX;
    const dy = e.clientY - dragStartY;
    if (Math.abs(dx) > 5 || Math.abs(dy) > 5) didDrag = true;
    evoButtonTranslateX = origTranslateX + dx;
    evoButtonTranslateY = origTranslateY + dy;
  }

  function onEvoPointerUp(e: PointerEvent) {
    if (!isDraggingEvo) return;
    const target = e.currentTarget as HTMLElement;
    target.releasePointerCapture(e.pointerId);
    isDraggingEvo = false;
    origTranslateX = evoButtonTranslateX;
    origTranslateY = evoButtonTranslateY;
  }

  function onEvoClick(e: MouseEvent) {
    if (didDrag) {
       e.preventDefault();
       e.stopPropagation();
       return;
    }
    openEvolutionPanel();
  }
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

  // ─── PREDICTIVE TELEMETRY — Mắt Thần ────────────────────────────────────
  const _SESSION_ID = 'boss_001';
  let _tabOpenTime = Date.now();

  function logUserAction(action: string, target: string, meta: Record<string, any> = {}) {
    // Fire-and-forget — không chặn UI
    fetch('/api/track_behavior', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: _SESSION_ID, action_type: action, target_name: target, ...meta })
    }).catch(() => {});
  }

  async function switchRegion(regionId: string) {
    // Log time spent on previous tab
    const timeSpent = Math.round((Date.now() - _tabOpenTime) / 1000);
    if (timeSpent > 3) logUserAction('LEAVE_TAB', selectedRegion, { time_spent_seconds: timeSpent });

    selectedRegion = regionId;
    _tabOpenTime = Date.now();
    logUserAction('OPEN_TAB', regionId);

    // reset results on tab switch
    heatmapData = {}; anchors = []; predictionMatrix = null;
    kenoHeatmap = {}; kenoAnchors = [];
    if (regionId !== 'VIETLOTT' && regionId !== 'KENO' && regionId !== 'MARKET_FLOW') {
      activeProvince = TUESDAY_SCHEDULE[regionId][0];
    }

    // Auto-fetch data for the newly selected tab
    triggerPrediction();
  }

  // ─── COUNTDOWN TIMER ──────────────────────────────────────────────────────
  function updateCountdown() {
    const now = new Date();
    let nextDraw = new Date(now);
    const h = now.getHours();
    const m = now.getMinutes();

    if (h > 21 || (h === 21 && m >= 55)) {
        nextDraw.setDate(now.getDate() + 1);
        nextDraw.setHours(6, 0, 0, 0); // Keno bắt đầu 06:00
    } else if (h < 6) {
        nextDraw.setHours(6, 0, 0, 0);
    } else {
        // Keno quay đều mỗi 10 phút!
        const nextMin = Math.ceil((m + 1e-9) / 10) * 10;
        if (nextMin === 60) {
            nextDraw.setHours(h + 1, 0, 0, 0);
        } else {
            nextDraw.setHours(h, nextMin, 0, 0);
        }
    }
    
    const diff = nextDraw.getTime() - now.getTime();
    if (diff < 0) return; // fail safe
    const remainM = Math.floor((diff % 3600000) / 60000);
    const remainS = Math.floor((diff % 60000) / 1000);
    
    countdown = `${String(remainM).padStart(2,'0')}:${String(remainS).padStart(2,'0')}`;
    kenoNextDraw = countdown;
  }

  // ─── TERMINAL LOG ─────────────────────────────────────────────────────────
  function addLog(msg: string, agent: 'SCOUT' | 'CORE' | 'NEURAL' | 'SYSTEM' = 'SYSTEM') {
    const ts = new Date().toISOString().substring(11, 19);
    let color = 'text-slate-400';
    if (agent === 'SCOUT') color = 'text-blue-400';
    if (agent === 'CORE') color = 'text-fuchsia-400';
    if (agent === 'NEURAL') color = 'text-emerald-400';
    
    aiLogs = [...aiLogs.slice(-15), { agent, msg, time: ts, color }];
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
    // Bắn tín hiệu USER_LOGIN để Boss Agent tiên đoán ngay lập tức
    setTimeout(() => logUserAction('USER_LOGIN', 'APP', {
      hour: new Date().getHours(),
      region: selectedRegion
    }), 1500);

    loadCustomAudioFromDB();
    if (typeof window !== 'undefined' && (window as any).__keno_ws_cleanup) {
        try { (window as any).__keno_ws_cleanup(); } catch(e) {}
    }
    updateCountdown();
    clock = setInterval(updateCountdown, 1000);

    // Fetch evolution data on mount
    fetchEvolutionData();
    // Refresh evolution log mỗi 5 phút
    evolutionRefresh = setInterval(fetchEvolutionData, 300000);

    // ─── WebSocket — dùng relative path (qua Vite proxy) ───────────
    // KHÔNG hardcode host:8888 → để vite proxy xử lý
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost     = window.location.host;          // giữ nguyên port vite (3333)
    const wsUrl      = `${wsProtocol}//${wsHost}/api/ws/keno`; // Nginx proxy → 8888

    function connectWS() {
        if (isDestroyed) return; // Ngăn reconnect zombie sau HMR
        
        // Dọn dẹp socket cũ nếu còn
        if (socket) {
            socket.onclose = null; // Tắt handler cũ để tránh trigger reconnect loop
            socket.onerror = null;
            try { socket.close(); } catch (_) {}
            socket = null;
        }
        
        socket = new WebSocket(wsUrl);
        
        socket.onopen = () => {
           if (isDestroyed) { socket?.close(); return; }
           console.log("[NEXUS-WS] Kết nối thành công!");
           wsOnline = true;
           reconnectAttempts = 0; // Reset khi kết nối thành công
           addLog("Kênh thời gian thực: ONLINE", "SYSTEM");
           
           // Heartbeat Ping mỗi 25s để giữ connection sống qua proxy/load balancer
           if (pingTimer) clearInterval(pingTimer);
           pingTimer = setInterval(() => {
               if (socket?.readyState === WebSocket.OPEN) {
                   socket.send('ping');
               }
           }, 25000);
        };
        
        socket.onmessage = (event) => {
            if (event.data === 'pong' || event.data === 'ping') return; // Bỏ qua heartbeat reply
            if (event.data === "NEW_DRAW_DETECTED") {
                addLog("[WS] TÍN HIỆU MỚI: ĐÃ CHUYỂN KỲ QUAY! ĐANG ĐỒNG BỘ...", "SCOUT");
                playAudioTone('countdown');
                if (status !== 'RED_ALERT') {
                    triggerPrediction(); // Auto Execute
                }
                return;
            }

            try {
                const parsed = JSON.parse(event.data);
                if (parsed.event === "SETTINGS_SYNC") {
                    if (JSON.stringify(userSettings) === JSON.stringify(parsed.payload)) return;
                    lastSyncedSettings = JSON.stringify(parsed.payload);
                    userSettings = parsed.payload;
                    addLog('[NEXUS] Đã đồng bộ Cài đặt từ thiết bị khác.', 'SYSTEM');
                } else if (parsed.event === "WALLET_SYNC") {
                    // Server là nguồn sự thật duy nhất — sync toàn bộ state
                    const p = parsed.payload;
                    if (typeof p.balance === 'number') kenoWalletBalance = p.balance;
                    if (Array.isArray(p.history) && p.history.length > 0) {
                        ticketHistory = p.history;
                    }
                    if (typeof p.mf_balance === 'number') { mfWalletBalance = p.mf_balance; marketWalletBalance = p.mf_balance; }
                    if (Array.isArray(p.mf_history) && p.mf_history.length > 0) {
                        mfTicketHistory = p.mf_history;
                    }
                    if (Array.isArray(p.anchors) && p.anchors.length > 0) kenoAnchors = p.anchors;
                    if (p.market_flow) latestMarketFlow = p.market_flow;
                    addLog(`[SERVER] Ví đồng bộ: Keno ${kenoWalletBalance.toLocaleString('vi-VN')}đ | MF ${(p.mf_balance??mfWalletBalance).toLocaleString('vi-VN')}đ`, 'SYSTEM');
                } else if (parsed.event === "EVOLUTION_CRITIQUE_COMPLETE") {
                    isCritiqueRunning = false;
                    addLog(`[ORBIS] Critique hoàn tất (${parsed.payload?.phase || '?'}). Đang refresh logs...`, "NEURAL");
                    fetchEvolutionData();
                } else if (parsed.event === "SWARM_SIMULATION_START") {
                    addLog(`[SWARM] 🌀 Đang họp hội đồng: ${parsed.reason || 'Sàn nổ loạn'}!`, "NEURAL");
                    isSwarmActive = true;
                } else if (parsed.event === "SWARM_SIMULATION_END") {
                    addLog(`[SWARM] Đã kết thúc phiên Debate lượng tử.`, "NEURAL");
                    isSwarmActive = false;
                } else if (parsed.event === "BOSS_ALERT") {
                    addLog(`[BOSS TỐI CAO] ${parsed.message}`, "NEURAL");
                    import('$lib/store').then(s => {
                        s.bossAgentResponse.set(parsed.message);
                    });
                    if (typeof window !== 'undefined' && window.speechSynthesis) {
                        const utterance = new SpeechSynthesisUtterance(parsed.message);
                        utterance.lang = 'vi-VN';
                        utterance.rate = 1.1;
                        utterance.pitch = 1.0;
                        window.speechSynthesis.speak(utterance);
                    }
                } else if (parsed.event === "ORBIS_PROACTIVE_PING" || parsed.type) {
                    const pingEvent = parsed.payload ? parsed.payload : parsed;
                    if (pingEvent.message && typeof showProactiveToast === "function") {
                        showProactiveToast({
                            type: pingEvent.type || "INFO",
                            priority: pingEvent.priority || "NORMAL",
                            message: pingEvent.message,
                            data: pingEvent.data || {},
                            ping_id: pingEvent.ping_id || Math.floor(1000 + Math.random() * 9000),
                            ts: new Date().toLocaleTimeString('vi-VN', {hour12: false})
                        });
                    }
                }
            } catch (e) {
                // Ignore non-JSON or parsing errors
            }
        };
        
        socket.onclose = (event) => {
            if (pingTimer) { clearInterval(pingTimer); pingTimer = null; }
            wsOnline = false;
            if (isDestroyed) return; // Không reconnect nếu đã destroy (HMR / unmount)
            
            // SMART RECONNECT: Exponential Backoff (Cơ chế lùi bước hàm mũ)
            let backoffDelay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
            reconnectAttempts++;
            
            addLog(`WS mất kết nối — đang reconnect sau ${(backoffDelay/1000).toFixed(1)}s (Thử lại lần ${reconnectAttempts})...`, "SYSTEM");
            if (reconnectTimer) clearTimeout(reconnectTimer);
            reconnectTimer = setTimeout(connectWS, backoffDelay);
        };
        
        socket.onerror = () => {
            socket?.close(); // Triggers onclose → reconnect tự động
        };
    }
    
    connectWS();

    // ─── HTTP POLLING FALLBACK ─────────────────────────────────────────────
    // Song song với WS — poll /api/latest mỗi 10s để bắt kỳ mới kể cả khi WS mất
    async function httpPollLatest() {
        if (isDestroyed) return;
        try {
            const res = await fetch('/api/latest');
            if (!res.ok) return;
            const d = await res.json();
            if (d.status !== 'SUCCESS' || !d.draw_id) return;

            const newId = parseInt(String(d.draw_id), 10);
            if (lastKnownDrawId === null) {
                // Lần đầu khởi động: Cần lấy dữ liệu ngay lập tức để nạp UI
                lastKnownDrawId = newId;
                addLog(`[SYSTEM] Đồng bộ dữ liệu khởi sinh Keno kỳ #${newId}...`, 'SYSTEM');
                triggerPrediction();
                return;
            }
            if (newId > lastKnownDrawId) {
                lastKnownDrawId = newId;
                // Chỉ trigger nếu WS đang offline (tránh duplicate với WS trigger)
                if (!wsOnline && status !== 'RED_ALERT') {
                    addLog(`[HTTP-POLL] Phát hiện kỳ mới #${newId} qua HTTP. Đang đồng bộ...`, 'SCOUT');
                    playAudioTone('countdown');
                    triggerPrediction();
                }
            }
        } catch (_) { /* bỏ qua lỗi poll */ }
    }

    // Chạy ngay lần đầu sau 2s, sau đó mỗi 10s
    httpPollTimer = setTimeout(() => {
        httpPollLatest();
        pollIntervalVar = setInterval(() => {
            if (isDestroyed) { clearInterval(pollIntervalVar!); return; }
            httpPollLatest();
        }, 10000);
    }, 2000);

    let bootI = 0;
    let boot: ReturnType<typeof setInterval>;
    boot = setInterval(() => {
      if (bootI < bootSequence.length) {
        bootLines = [...bootLines, bootSequence[bootI]];
        bootI++;
      } else {
        clearInterval(boot!);
        bootComplete = true; showGrid = true;
      }
    }, 60);

    // ── TẢI SETTINGS TỪ BACKEND ───────────────────────
    fetch('/api/settings').then(res => res.json()).then(data => {
        if (data.masterToggle !== undefined) {
            userSettings = data;
            lastSyncedSettings = JSON.stringify(data);
        }
        isSettingsLoaded = true;
    }).catch(err => {
        console.error('Settings fetch error:', err);
        isSettingsLoaded = true;
    });

    // ── TẢI TOÀN BỘ VÍ ẢO TỪ SERVER (Keno + MarketFlow) ──────────
    fetch('/api/wallet').then(res => res.json()).then(data => {
        kenoWalletBalance = data.balance ?? 1_000_000;
        ticketHistory     = data.history ?? [];
        mfWalletBalance   = data.mf_balance ?? 1_000_000;
        mfTicketHistory   = data.mf_history ?? [];
        addLog(`[VÍ SERVER] Keno: ${kenoWalletBalance.toLocaleString('vi-VN')}đ | MF: ${mfWalletBalance.toLocaleString('vi-VN')}đ | ${ticketHistory.length} vé`, 'SYSTEM');
        setTimeout(() => { isWalletLoaded = true; }, 100);
    }).catch(() => {
        kenoWalletBalance = 1_000_000;
        isWalletLoaded = true;
    });

    // ── TẢI LỊCH SỬ VÍ ẢO MARKET FLOW TỪ LOCALSTORAGE ──────────
    try {
        const savedMktBalance = localStorage.getItem('marketWalletBalance');
        const savedMktHistory = localStorage.getItem('marketTicketHistory');
        if (savedMktBalance !== null) marketWalletBalance = parseInt(savedMktBalance, 10) || 1_000_000;
        if (savedMktHistory !== null) marketTicketHistory = JSON.parse(savedMktHistory) || [];
        addLog('[VÍ ẢO MARKET] Đã khôi phục lịch sử từ localStorage.', 'SYSTEM');
    } catch(e) {
        marketWalletBalance = 1_000_000;
        marketTicketHistory = [];
    }
    setTimeout(() => { isMarketWalletLoaded = true; }, 150);

  });


  // ─── EVOLUTION PROTOCOL STATE ───────────────────────────────────────
  type EvolutionEntry = {
    id: number;
    timestamp: string;
    phase: string;
    strategy_name: string;
    confidence_score: number;
    win_rate: number;
    lesson_learned: string;
    draws_analyzed: number;
  };
  type ProactivePing = {
    type: string;
    priority: 'URGENT' | 'HIGH' | 'NORMAL';
    message: string;
    data: any;
    ping_id: number;
    ts: string;
  };
  type EvolutionKPIs = {
    evolution_count: number;
    lessons_stored: number;
    proactive_pings: number;
    proactive_pings_live: number;
    best_confidence_ever: number;
    critique_count: number;
    is_deep_learning_active: boolean;
  };

  let evolutionLog: EvolutionEntry[] = [];
  let evolutionKPIs: EvolutionKPIs = {
    evolution_count: 0, lessons_stored: 0, proactive_pings: 0,
    proactive_pings_live: 0, best_confidence_ever: 0,
    critique_count: 0, is_deep_learning_active: false,
  };
  let morningBrief: any = null;
  let proactiveToasts: Array<ProactivePing & { id: number; visible: boolean }> = [];
  let toastCounter = 0;
  let isEvolutionLoading = false;
  let isCritiqueRunning = false;

  function getPhaseColor(phase: string): string {
    if (phase === 'DEPLOY') return '#22d3ee';    // cyan
    if (phase === 'EVOLVE') return '#a855f7';    // purple
    if (phase === 'CRITIQUE') return '#f59e0b';  // amber
    if (phase === 'REJECT') return '#ef4444';    // red
    if (phase === 'DEEP_LEARNING') return '#6366f1'; // indigo
    if (phase === 'MORNING_BRIEF') return '#10b981'; // emerald
    if (phase === 'ANOMALY') return '#f97316';   // orange
    return '#64748b';
  }

  function getPriorityColor(priority: string, type: string = ''): string {
    if (type === 'MARKET_FLOW_ALERT') return '#f97316'; // Cam
    if (priority === 'URGENT') return '#ef4444';
    if (priority === 'HIGH') return '#f59e0b';
    return '#22d3ee';
  }

  function showProactiveToast(ping: ProactivePing) {
    const toast = { ...ping, id: toastCounter++, visible: true };
    proactiveToasts = [toast, ...proactiveToasts].slice(0, 5);
    // Auto-dismiss sau 8s (NORMAL) hoặc 15s (URGENT/HIGH)
    const delay = ping.priority === 'NORMAL' ? 8000 : 15000;
    setTimeout(() => {
      proactiveToasts = proactiveToasts.map(t => t.id === toast.id ? { ...t, visible: false } : t);
      setTimeout(() => {
        proactiveToasts = proactiveToasts.filter(t => t.id !== toast.id);
      }, 500);
    }, delay);
  }

  async function fetchEvolutionData() {
    isEvolutionLoading = true;
    try {
      const [logRes, kpiRes, briefRes] = await Promise.all([
        fetch('/api/evolution/log?limit=20'),
        fetch('/api/evolution/kpis'),
        fetch('/api/evolution/morning-brief'),
      ]);
      if (logRes.ok) {
        const d = await logRes.json();
        evolutionLog = d.logs || [];
      }
      if (kpiRes.ok) {
        const d = await kpiRes.json();
        evolutionKPIs = { ...evolutionKPIs, ...(d.kpis || {}) };
      }
      if (briefRes.ok) {
        const d = await briefRes.json();
        if (d.status === 'SUCCESS') morningBrief = d.brief;
      }
    } catch(e) {
      console.error('[EVOLUTION] fetch error', e);
    } finally {
      isEvolutionLoading = false;
    }
  }

  async function triggerManualCritique() {
    isCritiqueRunning = true;
    addLog('Kích hoạt Critique thủ công — Orbis đang phân tích...', 'NEURAL');
    try {
      const res = await fetch('/api/evolution/trigger-critique', { method: 'POST' });
      const d = await res.json();
      addLog(d.message || 'Critique đang chạy nền.', 'NEURAL');
    } catch(e) {
      addLog('Lỗi kích hoạt Critique.', 'SYSTEM');
    }
    // isCritiqueRunning sẽ được tắt khi nhận WS event EVOLUTION_CRITIQUE_COMPLETE
    setTimeout(() => { isCritiqueRunning = false; }, 30000);
  }

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
    logUserAction('CLICK_PREDICT', selectedRegion);
    isAnalyzing = true;
    predictionData = null;
    predictionMatrix = null;
    status = 'RED_ALERT';
    
    if (selectedRegion === 'VIETLOTT') {
      addLog('ĐANG XUYÊN TƯỜNG LỬA TRUYỀN TẢI...', 'SYSTEM');
    } else if (selectedRegion === 'KENO') {
      addLog('Tái lập lại tọa độ mạng Neuron. Vào chế độ OVERCLOCK.', 'CORE');
      setTimeout(() => addLog('Đang càn quét Vault (100 kỳ gần nhất)...', 'SCOUT'), 600);
    } else {
      addLog(`Kích hoạt Radar tại ${activeProvince.toUpperCase()}...`, 'SYSTEM');
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 90000);

    try {
      let res;
      if (selectedRegion === 'VIETLOTT') {
        res = await fetch('/api/ignite-prediction', { signal: controller.signal });
      } else if (selectedRegion === 'KENO') {
        res = await fetch('/api/ignite-keno', { signal: controller.signal });
      } else if (selectedRegion === 'MARKET_FLOW') {
        res = await fetch('/api/market-flow', { signal: controller.signal });
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
          addLog(`Khóa mẫu Thành công. Đã nạp ${realSamplesCount} Vector dữ liệu Keno.`, 'CORE');
          addLog(`Phối hợp xác thực kỳ #${data.latest_draw_id} trong chu trình ngầm...`, 'NEURAL');

          setTimeout(() => {
            if (kenoAnchors && kenoAnchors.length > 0) {
               lastKenoAnchors = [...kenoAnchors];
            }
            kenoHeatmap   = data.heatmap || {};
            kenoAnchors   = data.anchors || [];

            // Server tự validate + auto-buy mọi kỳ — frontend chỉ hiển thị
            // WALLET_SYNC event sẽ cập nhật balance/history/mf từ server

            kenoDrawCount = data.draw_count || 0;
            kenoLatestDraw = data.latest_draw_id || null;
            kenoLatestWinningNumbers = data.latest_winning_numbers || [];
            confidenceLevel = data.confidence;
            
            if (data.is_inverted) {
              addLog(`🔴 INVERSION MODE: Chuỗi thua dài — Đảo chiến lược sang SỐ LẠNH (Vùng Mù)!`, 'NEURAL');
            } else {
              addLog(`✅ HOLY GRAIL MODE [${data.brain_status || 'SCANNING'}]: Bám theo SỐ NÓNG.`, 'NEURAL');
            }
            addLog(`Tạo xong 10 Điểm Neo lượng tử. Mức độ tự tin: ${data.confidence}%`, 'NEURAL');
            isAnalyzing = false;
            status = 'SECURE';
          }, 800);
        } else if (selectedRegion === 'MARKET_FLOW') {
          statusMessage = `MARKET FLOW: SYNCHRONIZED | #${data.latest_draw_id}`;
          addLog(`Dòng chảy Market Flow cập nhật: kỳ #${data.latest_draw_id}`, 'CORE');
          setTimeout(() => {
            marketDataFlow = data.market_data;
            kenoLatestDraw = data.latest_draw_id;
            
            // Xử lý Ví Ảo Market Flow
            const actualChanLe = data.market_data.chanLE.history[data.market_data.chanLE.history.length - 1];
            const actualLonNho = data.market_data.lonNho.history[data.market_data.lonNho.history.length - 1];
            marketValidatePendingTickets(kenoLatestDraw, actualChanLe, actualLonNho);
            marketAutoBuyTicket(kenoLatestDraw + 1, data.market_data.chanLE.pred, data.market_data.lonNho.pred);

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

  <!-- RESULT SCREEN FLASH (WIN=green / LOSS=red / BREAK_EVEN=yellow) -->
  {#if screenFlash}
    <div class="fixed inset-0 z-[9998] pointer-events-none"
      style="animation: screenFlashAnim 0.7s ease-out forwards;
             background: {screenFlash === 'win' ? 'rgba(34,197,94,0.18)' : screenFlash === 'loss' ? 'rgba(239,68,68,0.22)' : 'rgba(234,179,8,0.15)'};
             border: 2px solid {screenFlash === 'win' ? '#22c55e' : screenFlash === 'loss' ? '#ef4444' : '#eab308'}44;"
      aria-hidden="true">
    </div>
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
          <span class="cd-label" class:text-amber-500={kenoTimePhase==='WARNING'} class:text-red-500={kenoTimePhase==='DANGER'}>NEXT_DRAW</span>
          <span class="cd-time {kenoPhaseColorText}" class:cd-red={status === 'RED_ALERT'}>{countdown}</span>
        </div>

        <div class="nav-right" style="display:flex; gap:12px; align-items:center;">
          <button on:click={() => { showSettings = true; logUserAction('OPEN_SETTINGS', 'SETTINGS_PANEL'); }} class="px-3 py-1 bg-cyan-900/30 border border-cyan-500/50 text-cyan-400 text-xs font-bold rounded hover:bg-cyan-500 hover:text-black transition-all">
            ⚙ SETTINGS
          </button>
          <!-- WS STATUS BADGE -->
          <span class="ws-badge" class:ws-online={wsOnline} class:ws-offline={!wsOnline} title={wsOnline ? 'WebSocket ONLINE' : 'WebSocket đang reconnect — HTTP fallback đang hoạt động'}>
            <span class="ws-dot"></span>
            {wsOnline ? 'LIVE' : 'HTTP↑'}
          </span>
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
          <button on:click={() => switchRegion('KENO')} class="glass-tab {selectedRegion === 'KENO' ? 'active-keno' : ''}">⚡ KENO 10'</button>
          <button on:click={() => switchRegion('MARKET_FLOW')} class="glass-tab {selectedRegion === 'MARKET_FLOW' ? 'active-keno' : ''}">🌊 MARKET FLOW</button>
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
      </header>

      <!-- TWO COLUMN LAYOUT FOR PC (CSS GRID) -->
      <div class="keno-main-grid w-full max-w-[1920px] mx-auto px-4 xl:px-10 pb-20">
        
        <!-- LEFT COLUMN -->
        <div class="left-col flex flex-col items-center xl:sticky xl:top-28 z-20 relative">

        <!-- KENO WIN/LOSS TICKER OVERLAY -->
        {#if showResultTicker && userSettings.popupEnabled}
          <div class="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 flex flex-col items-center pointer-events-none w-full text-center" style="animation: bounceIn 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);">
            
            <h2 class="text-5xl sm:text-7xl font-black {tickerPnL > 0 ? 'text-green-400 drop-shadow-[0_0_20px_#4ade80]' : (tickerPnL < 0 ? 'text-red-500 drop-shadow-[0_0_20px_#f87171]' : 'text-gray-400 drop-shadow-[0_0_15px_#9ca3af]')}" style="font-family: 'Space Mono', monospace;">
              {tickerPnL > 0 ? '✨ JACKPOT ✨' : (tickerPnL < 0 ? '☠️ LOSS ☠️' : '⚖️ HÒA')}
            </h2>
            
            <span class="text-3xl sm:text-5xl font-bold mt-2 {tickerPnL > 0 ? 'text-yellow-400 drop-shadow-[0_0_10px_#facc15]' : 'text-gray-300'}">
              {tickerPnL > 0 ? '+' : ''}{tickerPnL.toLocaleString('vi-VN')} đ
            </span>
            
            <span class="text-sm sm:text-lg bg-black/90 px-6 py-2 mt-4 rounded-full border {tickerPnL > 0 ? 'border-green-500/50 text-green-300 shadow-[0_0_15px_#22c55e]' : (tickerPnL < 0 ? 'border-red-500/50 text-red-300 shadow-[0_0_15px_#ef4444]' : 'border-gray-500/50 text-gray-300 border-dashed')} transition-all">
              {tickerPnL > 0 ? userSettings.popupWinText : (tickerPnL < 0 ? userSettings.popupLossText : userSettings.popupBreakEvenText)}
            </span>
          </div>
        {/if}

        <!-- ZERO-MOCK STATUS BAR ────────────────────────────────────── -->
        <div class="mb-4 text-center z-10 relative flex flex-col items-center gap-2">
          <span class="text-[10px] px-3 py-1.5 border rounded {hasCriticalError ? 'bg-red-500/20 text-red-500 border-red-500' : (realSamplesCount > 0 ? 'bg-green-500/20 text-green-400 border-green-500' : 'bg-cyan-500/20 text-cyan-400 border-cyan-500')} font-mono uppercase tracking-wider backdrop-blur-sm shadow-sm transition-all duration-300">
            {statusMessage}
          </span>

          <!-- SỐ KHỚP MATCH BAR — hiển thị khi KENO có kỳ gần nhất -->
          {#if selectedRegion === 'KENO' && kenoLatestDraw && lastKenoAnchors.length > 0}
            <div class="flex items-center gap-3 px-4 py-2 rounded-xl bg-black/60 border border-slate-700/50 backdrop-blur-sm">
              <div class="flex items-center gap-1.5">
                <span class="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Kỳ #{kenoLatestDraw} — Dự đoán khớp:</span>
                <div class="flex gap-1">
                  {#each Array(10) as _, i}
                    <div class="w-3 h-3 rounded-sm transition-all duration-300 {i < kenoHits.length ? 'bg-green-400 shadow-[0_0_6px_#4ade80]' : 'bg-slate-800 border border-slate-700'}"></div>
                  {/each}
                </div>
                <span class="text-base font-black {kenoHits.length >= 5 ? 'text-green-400' : kenoHits.length >= 3 ? 'text-amber-400' : 'text-red-400'} ml-1">
                  {kenoHits.length}/10
                </span>
              </div>
              {#if kenoHits.length > 0}
                <div class="flex gap-1 flex-wrap max-w-[160px]">
                  {#each kenoHits as n}
                    <span class="px-1.5 py-0.5 rounded text-[8px] font-black bg-green-500/20 text-green-300 border border-green-500/40">{n}</span>
                  {/each}
                </div>
              {/if}
              <span class="text-[8px] text-slate-600 ml-auto">vs vesoonline</span>
            </div>
          {/if}
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

        <!-- MULTI-AI CENTRAL LOG ─────────────────────────────────────── -->
        <div class="terminal-log !p-4 !bg-[#050508] border border-slate-800/60 rounded-xl" class:log-red={status === 'RED_ALERT'}>
          <div class="log-header mb-4 flex justify-between items-center border-b border-slate-800 pb-2">
             <div class="flex items-center gap-2">
                <span class="log-title text-cyan-400 font-bold uppercase tracking-widest text-[10px]">❖ MULTI-AI CENTRAL LOG</span>
                <span class="px-2 py-0.5 rounded bg-cyan-900/30 text-cyan-400 text-[8px] animate-pulse">LIVE NODE</span>
             </div>
             {#if isAnalyzing}
               <div class="flex gap-1 items-center">
                  <span class="w-1.5 h-1.5 rounded-full bg-fuchsia-500 animate-ping"></span>
                  <span class="text-[9px] text-slate-500 uppercase">Agents are communicating...</span>
               </div>
             {/if}
          </div>
          
          <div class="flex flex-col gap-2 h-[220px] overflow-y-auto custom-scrollbar pr-2 pt-1">
            {#each aiLogs as log}
              <div class="flex items-start gap-3 text-[10px] font-mono leading-relaxed">
                 <span class="text-slate-600 shrink-0">[{log.time}]</span>
                 <span class="px-1.5 py-0.5 rounded bg-black border border-slate-800 uppercase font-bold shrink-0 w-[60px] text-center {log.color} text-[8px] tracking-wider">{log.agent}</span>
                 <span class="text-slate-300">{log.msg}</span>
              </div>
            {/each}
          </div>
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

      </div> <!-- END LEFT COLUMN -->

      <!-- RIGHT COLUMN -->
      <div class="right-col flex flex-col items-start w-full">

      <!-- HEATMAP & ANCHORS (VIETLOTT) ───────────────────────── -->
      {#if selectedRegion === 'VIETLOTT'}
        <!-- CRIMSON HUB NEW INTEGRATION -->
        <div class="hidden md:block w-full max-w-4xl mx-auto mt-4 px-4">
           <VietlottHub />
        </div>
        <div class="block md:hidden w-full mx-auto max-w-[400px]">
           <MobileVietlottHub />
        </div>
      {/if}
      
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
      {#if !['VIETLOTT', 'KENO', 'MARKET_FLOW'].includes(selectedRegion) && predictionMatrix}
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
        <!-- padding-right: 60px tạo khoảng trống để thanh EVOLUTION (fixed right:0) không che wallet -->
        <div class="keno-content-grid w-full" style="padding-right: 60px; box-sizing: border-box;">
          
          <!-- WRAPPER: LÕI GRID CHÍNH & PREDICTION TAB -->
          <div class="flex flex-col gap-2 flex-1 min-w-0">

          <!-- LÕI GRID (TRÁI) -->
          <div class="keno-grid-panel bg-[#08080a] border border-emerald-500/10 rounded-[2rem] p-3 sm:p-5 lg:p-8 shadow-[0_0_80px_rgba(0,0,0,0.9)] w-full overflow-hidden">
          <!-- HEADER: KỲ QUAY & THỜI GIAN THẬT -->
          <header class="flex flex-col xl:flex-row justify-between items-center border-b border-emerald-500/20 pb-6 mb-10 gap-4 xl:gap-0 text-center xl:text-left">
            <div class="flex flex-col sm:flex-row items-center gap-3 sm:gap-6">
              <div class="px-5 py-2 border rounded-full text-xs sm:text-sm font-black tracking-widest uppercase transition-colors {(kenoLatestDraw && !isAnalyzing) ? 'bg-emerald-500/10 border-emerald-500/50 text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.2)]' : 'bg-amber-500/10 border-amber-500/50 text-amber-400 animate-pulse'}">
                ⚡ KENO OVERCLOCK
              </div>
              <div class="text-slate-500 tracking-[0.1em] sm:tracking-[0.2em] text-xs sm:text-sm uppercase font-bold inline-flex flex-wrap items-center justify-center gap-2">
                Kỳ quay <span class="text-white">#{kenoLatestDraw || 'SYNCING...'}</span>
              </div>
            </div>

            <div class="flex flex-col sm:flex-row items-center gap-2 sm:gap-4 mt-2 xl:mt-0">
              <div class="flex flex-col items-end">
                <span class="text-[10px] sm:text-xs text-slate-500 tracking-widest uppercase font-bold">Kỳ tiếp theo:</span>
                <span class="text-[8px] sm:text-[9px] px-2 py-0.5 mt-1 border bg-black/60 {kenoPhaseColor} font-bold rounded flex items-center justify-center transition-colors duration-500" style="letter-spacing: 0.05em; min-width: 140px;">
                  {kenoPhaseLabel}
                </span>
              </div>
              <span class="text-3xl sm:text-4xl font-black tracking-widest {kenoPhaseColorText} drop-shadow-[0_0_10px_currentColor] transition-colors duration-500" style="font-family: 'Space Mono', monospace;">
                {kenoNextDraw || '--:--'}
              </span>
            </div>
          </header>

          {#if Object.keys(kenoHeatmap).length > 0 || kenoHits.length > 0}
            <!-- LƯỚI GHI CHÚ V7.1 NEON MATRIX -->
            <div class="flex justify-center items-center gap-3 sm:gap-6 text-[8px] sm:text-[10px] mb-8 font-mono tracking-widest uppercase flex-wrap">
                 <span class="text-white flex items-center gap-2"><div class="w-3 h-3 rounded-full border-2 border-white shadow-[0_0_10px_rgba(255,255,255,0.8)]"></div> HITS (TRÚNG)</span>
                 <span class="text-yellow-400 flex items-center gap-2"><div class="w-3 h-3 rounded-full border-2 border-yellow-400 shadow-[0_0_10px_rgba(250,204,21,0.6)]"></div> MISS (GỢI Ý)</span>
            </div>

            <!-- MA TRẬN 80 SỐ -->
            {#key kenoAnchors.join(',') + kenoHits.join(',')}
            <div class="grid justify-center transition-opacity duration-500 {isAnalyzing ? 'opacity-20' : 'opacity-100'} mb-8 gap-[4px] sm:gap-[8px] lg:gap-[12px]" style="grid-template-columns: repeat(10, minmax(28px, 1fr)); place-items: center; width: 100%; max-width: 100%; overflow-x: auto; padding-bottom: 8px;">
              {#each Array(80) as _, idx}
                {@const num = idx + 1}
                <div
                  class="
                    w-7 h-7 sm:w-9 sm:h-9 lg:w-11 lg:h-11 rounded-full flex items-center justify-center shrink-0 transition-all duration-300
                    text-xs sm:text-base lg:text-xl font-black
                    {getKenoNumberClass(num, kenoHits, kenoAnchors)}
                  "
                  style="font-family: 'Space Mono', monospace;"
                >
                  <span>{num < 10 ? `0${num}` : num}</span>
                </div>
              {/each}
            </div>
            {/key}

            <!-- Removed PREDICTION TAB (Moved Outside) -->

            <div class="flex justify-between items-center border-t border-slate-800/50 pt-6">
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
          {/if}

          {#if Object.keys(kenoHeatmap).length === 0 && kenoHits.length === 0}
            <div class="flex flex-col items-center justify-center py-16 px-8 bg-[#08080a] rounded-2xl border border-slate-800 shadow-[inset_0_0_50px_rgba(0,0,0,0.8)] mt-6 min-h-[260px]">
              <div class="text-4xl mb-4 text-emerald-500/30 animate-pulse">⚡</div>
              <div class="text-slate-300 font-bold mb-2 tracking-widest uppercase text-base">SYNCING KENO DATA...</div>
              <div class="text-slate-400 text-sm text-center leading-relaxed font-sans mt-2">
                Đang thiết lập kết nối thời gian thực.<br>
                Chờ dữ liệu thật từ Server...
              </div>
            </div>
          {/if}
          </div> <!-- END LÕI GRID -->

          <!-- KENO PREDICTION TAB ĐỘC LẬP (NẰM DƯỚI GRID) -->
          {#if selectedRegion === 'KENO' && sortedKenoAnchors.length > 0}
            <!-- key={kenoLatestDraw} forces Svelte to re-render this block khi kỳ mới về -->
            {#key kenoLatestDraw}
            <div class="keno-prediction-panel mt-2 bg-[#050505] border-2 border-emerald-500/60 rounded-[2rem] p-6 lg:p-8 shadow-[0_0_40px_rgba(0,0,0,0.6)] w-full overflow-hidden relative">
              <div class="absolute inset-0 bg-gradient-to-r from-transparent via-emerald-900/10 to-transparent pointer-events-none"></div>
              
              <div class="text-xs sm:text-sm text-emerald-400 font-bold uppercase tracking-[0.3em] mb-6 drop-shadow-[0_0_8px_rgba(16,185,129,0.9)] flex justify-center items-center gap-3">
                <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                « DỰ ĐOÁN KỲ QUAY {kenoLatestDraw ? `#${kenoLatestDraw + 1}` : 'tiếp theo'} »
                <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              </div>
              
              <div class="flex flex-wrap items-center justify-center gap-4 sm:gap-6 relative z-10">
                {#each sortedKenoAnchors as num (num)}
                  <div class="
                    w-12 h-12 sm:w-16 sm:h-16 rounded-full flex justify-center items-center text-lg sm:text-2xl font-black transition-all duration-500 border-2
                    bg-transparent border-emerald-500/40 text-emerald-400
                  " style="font-family: 'Space Mono', monospace;">
                    {num < 10 ? `0${num}` : num}
                  </div>
                {/each}
              </div>
            </div>
            {/key}
          {/if}
          </div> <!-- END CỘT TRÁI -->

          <!-- KHU VỰC VÍ & LỊCH SỬ (PHẢI) - SIDEBAR -->
          <div class="keno-wallet-sidebar flex flex-col gap-4">

            <!-- ── WALLET BALANCE + DAILY STATS ──────────────────────── -->
            <div class="bg-[#08080a] border border-cyan-500/20 rounded-xl relative overflow-hidden">
              <div class="absolute inset-0 bg-gradient-to-br from-cyan-900/10 to-transparent pointer-events-none"></div>
              <!-- Wallet Header — centered title bar -->
              <div class="relative z-10 text-center px-4 pt-4 pb-3 border-b border-cyan-500/15">
                <p class="text-sm font-black text-cyan-400 uppercase tracking-[0.25em]">&#10022; VÍ ẢO KENO</p>
                <span class="inline-block mt-1.5 text-[9px] px-2 py-0.5 rounded border bg-emerald-500/15 border-emerald-500/60 text-emerald-400 font-bold tracking-wide animate-pulse">
                  ⚡ AUTO-BET: ON · 10k/kỳ
                </span>
              </div>

              <div class="relative z-10 px-5 pt-4 pb-5">
                <!-- Balance -->
                <div class="text-center mb-4">
                  <h2 class="text-4xl font-black text-cyan-400 tracking-tight tabular-nums">
                    {kenoWalletBalance.toLocaleString('vi-VN')}
                  </h2>
                  <span class="text-xs font-semibold text-slate-500 tracking-widest uppercase">VND</span>
                </div>

                <!-- Win / Loss / Pending / WinRate grid -->
                <div class="grid grid-cols-4 gap-0 border border-slate-800/60 rounded-lg overflow-hidden">
                  <div class="py-2.5 text-center">
                    <div class="text-emerald-400 font-black text-2xl leading-none tabular-nums">{winTickets}</div>
                    <div class="text-[9px] text-slate-500 uppercase tracking-wider mt-1">WIN</div>
                  </div>
                  <div class="border-l border-slate-800/60 py-2.5 text-center">
                    <div class="text-red-400 font-black text-2xl leading-none tabular-nums">{lossTickets}</div>
                    <div class="text-[9px] text-slate-500 uppercase tracking-wider mt-1">LOSS</div>
                  </div>
                  <div class="border-l border-slate-800/60 py-2.5 text-center">
                    <div class="text-amber-400 font-black text-2xl leading-none tabular-nums">{pendingCount}</div>
                    <div class="text-[9px] text-slate-500 uppercase tracking-wider mt-1">PENDING</div>
                  </div>
                  <div class="border-l border-slate-800/60 py-2.5 text-center">
                    <div class="{winRate >= 50 ? 'text-emerald-400' : 'text-slate-400'} font-black text-2xl leading-none tabular-nums">{winRate}%</div>
                    <div class="text-[9px] text-slate-500 uppercase tracking-wider mt-1">W-RATE</div>
                  </div>
                </div>

                <!-- Daily P&L -->
                <div class="flex items-center justify-between mt-3 pt-3 border-t border-slate-800/60">
                  <span class="text-[10px] text-slate-500 uppercase tracking-widest font-bold">P&L HÔM NAY</span>
                  <span class="text-lg font-black {dailyPnL >= 0 ? 'text-emerald-400 drop-shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'text-red-400 drop-shadow-[0_0_8px_rgba(239,68,68,0.5)]'}">
                    {dailyPnL >= 0 ? '+' : ''}{dailyPnL.toLocaleString('vi-VN')}&#x20AB;
                  </span>
                </div>
              </div>
            </div>

            <!-- ── TICKET HISTORY ────────────────────────────────── -->
            <div class="flex-1 bg-[#08080a] border border-slate-800/80 rounded-xl flex flex-col overflow-hidden" style="min-height:280px; max-height: calc(100vh - 340px);">

              <!-- Fixed header -->
              <div class="flex justify-between items-center px-4 py-3 border-b border-slate-800/60 shrink-0">
                <p class="text-xs font-black text-slate-300 uppercase tracking-[0.2em]">LỊCH SỬ VÉ <span class="text-slate-500 font-bold">({ticketHistory.length})</span></p>
                <button on:click={clearTicketHistory}
                  class="text-[10px] text-red-400/50 hover:text-red-400 transition-colors uppercase font-bold px-2 py-1 rounded hover:bg-red-400/10 whitespace-nowrap">
                  ✕ XÓA
                </button>
              </div>

              {#if ticketHistory.length === 0}
                <div class="flex-1 flex flex-col items-center justify-center text-slate-600 text-[11px] italic gap-2">
                  <span class="text-3xl opacity-20">🎫</span>
                  IGNITE PREDICTION để Auto-Buy vé đầu tiên.
                </div>
              {:else}
                <div class="overflow-y-auto custom-scrollbar flex-1 p-3 flex flex-col gap-2">
                  {#each ticketHistory as ticket (ticket.id)}
                    <div class="rounded-lg border p-3.5 transition-all
                      {ticket.status === 'WIN'
                        ? 'border-emerald-500/30 bg-emerald-950/20'
                        : ticket.status === 'PENDING'
                        ? 'border-amber-500/20 bg-amber-950/10'
                        : 'border-slate-800/50 bg-transparent'}">

                      <!-- Row 1: draw_id + result badge -->
                      <div class="flex justify-between items-center mb-2">
                        <!-- Kỳ quay + giờ -->
                        <div class="flex items-center gap-2">
                          <span class="text-[10px] font-mono text-slate-500">Kỳ</span>
                          <span class="text-xs font-black text-cyan-400 font-mono">#{ticket.draw_id}</span>
                          <span class="text-slate-700 mx-0.5">·</span>
                          <span class="text-[10px] text-slate-500">{ticket.time}</span>
                        </div>
                        <!-- Kết quả badge -->
                        <div>
                          {#if ticket.status === 'PENDING'}
                            <span class="text-[10px] bg-amber-500/20 text-amber-400 px-2.5 py-1 rounded uppercase tracking-widest animate-pulse font-bold">CHỜ</span>
                          {:else if ticket.status === 'WIN'}
                            <span class="text-[10px] bg-emerald-500/20 text-emerald-400 px-2.5 py-1 rounded font-black drop-shadow-[0_0_5px_rgba(16,185,129,0.5)]">+{ticket.profit.toLocaleString()}đ</span>
                          {:else if ticket.status === 'LOSS'}
                            <span class="text-[10px] bg-red-500/10 text-red-400/80 px-2.5 py-1 rounded font-bold">-{ticket.cost.toLocaleString()}đ</span>
                          {:else}
                            <span class="text-[10px] bg-slate-700/30 text-slate-400 px-2.5 py-1 rounded font-bold">HÒA</span>
                          {/if}
                        </div>
                      </div>

                      <div class="flex items-center justify-between mt-2">
                        <div class="flex items-center gap-2 flex-wrap flex-1">
                          {#each ticket.numbers as n}
                            <span class="text-sm font-bold w-8 h-8 flex items-center justify-center bg-black/50 rounded shrink-0 border {ticket.status !== 'PENDING' && kenoLatestWinningNumbers.includes(n) ? 'border-emerald-500 text-emerald-400 shadow-[inset_0_0_8px_rgba(16,185,129,0.5)]' : 'border-slate-700 text-slate-400'}">{n}</span>
                          {/each}
                        </div>
                        <div class="ml-4 pl-4 border-l border-slate-700 text-right min-w-[70px]">
                          {#if ticket.status === 'PENDING'}
                            <span class="text-xs text-slate-500 block">-10k VND</span>
                          {:else}
                            <span class="text-xs {ticket.status === 'WIN' ? 'text-emerald-500' : 'text-slate-500'} font-bold uppercase block">{ticket.matches}/10 HITS</span>
                          {/if}
                        </div>
                      </div>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          </div>
        </div>
      {/if}

      <!-- MARKET FLOW ─────────────────────────────────────────── -->
      {#if selectedRegion === 'MARKET_FLOW'}
        <div class="keno-content-grid w-full">
           <div class="keno-grid-panel flex-1 min-w-0">
             <MarketFlow 
               latestDrawId={kenoLatestDraw} 
               nextDrawCountdown={kenoNextDraw} 
               isAnalyzing={isAnalyzing} 
               isSwarmActive={isSwarmActive}
               marketData={marketDataFlow}
             />
           </div>

           <!-- MARKET FLOW WALLET SIDEBAR -->
           <div class="keno-wallet-sidebar flex flex-col gap-4 w-full xl:w-[320px]">
              <!-- ── WALLET BALANCE + DAILY STATS ──────────────────────── -->
              <div class="bg-[#08080a] border border-amber-500/20 rounded-xl relative overflow-hidden">
                <div class="absolute inset-0 bg-gradient-to-br from-amber-900/10 to-transparent pointer-events-none"></div>
                <!-- Wallet Header — centered title bar -->
                <div class="relative z-10 text-center px-4 pt-4 pb-3 border-b border-amber-500/15">
                  <p class="text-sm font-black text-amber-400 uppercase tracking-[0.25em]">&#10022; VÍ ẢO MARKET</p>
                  <span class="inline-block mt-1.5 text-[9px] px-2 py-0.5 rounded border bg-emerald-500/15 border-emerald-500/60 text-emerald-400 font-bold tracking-wide animate-pulse">
                    ⚡ AUTO-BET: ON · ~{Math.round(marketWalletBalance * 0.02 / 1000)}k/kỳ
                  </span>
                </div>

                <div class="relative z-10 px-5 pt-4 pb-5">
                  <!-- Balance -->
                  <div class="text-center mb-4">
                    <h2 class="text-4xl font-black text-amber-400 tracking-tight tabular-nums">
                      {marketWalletBalance.toLocaleString('vi-VN')}
                    </h2>
                    <span class="text-xs font-semibold text-slate-500 tracking-widest uppercase">VND</span>
                  </div>

                  <div class="grid grid-cols-4 gap-0 border border-slate-800/60 rounded-lg overflow-hidden">
                    <div class="py-2.5 text-center">
                      <div class="text-emerald-400 font-black text-2xl leading-none tabular-nums">{marketWinTickets}</div>
                      <div class="text-[9px] text-slate-500 uppercase tracking-wider mt-1">WIN</div>
                    </div>
                    <div class="border-l border-slate-800/60 py-2.5 text-center">
                      <div class="text-red-400 font-black text-2xl leading-none tabular-nums">{marketLossTickets}</div>
                      <div class="text-[9px] text-slate-500 uppercase tracking-wider mt-1">LOSS</div>
                    </div>
                    <div class="border-l border-slate-800/60 py-2.5 text-center">
                      <div class="text-cyan-400 font-black text-2xl leading-none tabular-nums">{marketPendingCount}</div>
                      <div class="text-[9px] text-slate-500 uppercase tracking-wider mt-1">PENDING</div>
                    </div>
                    <div class="border-l border-slate-800/60 py-2.5 text-center">
                      <div class="{marketWinRate >= 50 ? 'text-emerald-400' : 'text-slate-400'} font-black text-2xl leading-none tabular-nums">{marketWinRate}%</div>
                      <div class="text-[9px] text-slate-500 uppercase tracking-wider mt-1">W-RATE</div>
                    </div>
                  </div>

                  <div class="flex items-center justify-between mt-3 pt-3 border-t border-slate-800/60">
                    <span class="text-[10px] text-slate-500 uppercase tracking-widest font-bold">P&L HÔM NAY</span>
                    <span class="text-lg font-black {marketDailyPnL >= 0 ? 'text-emerald-400 drop-shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'text-red-400 drop-shadow-[0_0_8px_rgba(239,68,68,0.5)]'}">
                      {marketDailyPnL >= 0 ? '+' : ''}{marketDailyPnL.toLocaleString('vi-VN')}&#x20AB;
                    </span>
                  </div>
                </div>
              </div>

              <!-- ── TICKET HISTORY ────────────────────────────────── -->
              <div class="flex-1 bg-[#08080a] border border-slate-800/80 rounded-xl flex flex-col overflow-hidden" style="min-height:280px; max-height: calc(100vh - 340px);">
                <div class="flex justify-between items-center px-4 py-3 border-b border-slate-800/60 shrink-0">
                  <p class="text-xs font-black text-slate-300 uppercase tracking-[0.2em]">LỊCH SỬ VÉ <span class="text-slate-500 font-bold">({marketTicketHistory.length})</span></p>
                  <button on:click={clearMarketTicketHistory}
                    class="text-[10px] text-red-400/50 hover:text-red-400 transition-colors uppercase font-bold px-2 py-1 rounded hover:bg-red-400/10 whitespace-nowrap">
                    ✕ XÓA
                  </button>
                </div>

                {#if marketTicketHistory.length === 0}
                  <div class="flex-1 flex flex-col items-center justify-center text-slate-600 text-[11px] italic gap-2">
                    <span class="text-3xl opacity-20">🎫</span>
                    IGNITE PREDICTION để Auto-Buy vé đầu tiên.
                  </div>
                {:else}
                  <div class="overflow-y-auto custom-scrollbar flex-1 p-3 flex flex-col gap-2">
                    {#each marketTicketHistory as ticket (ticket.id)}
                      <div class="rounded-lg border p-3.5 transition-all
                        {ticket.status === 'WIN' ? 'border-emerald-500/30 bg-emerald-950/20'
                          : ticket.status === 'PENDING' ? 'border-cyan-500/20 bg-cyan-950/10'
                          : ticket.status === 'BREAK_EVEN' ? 'border-amber-500/30 bg-amber-950/20'
                          : 'border-slate-800/50 bg-transparent'}">

                        <div class="flex justify-between items-center mb-2">
                          <div class="flex items-center gap-2">
                            <span class="text-[10px] font-mono text-slate-500">Kỳ</span>
                            <span class="text-xs font-black text-amber-400 font-mono">#{ticket.draw_id}</span>
                            <span class="text-slate-700 mx-0.5">·</span>
                            <span class="text-[10px] text-slate-500">{ticket.time}</span>
                          </div>
                          <div>
                            {#if ticket.status === 'PENDING'}
                              <span class="text-[10px] bg-cyan-500/20 text-cyan-400 px-2.5 py-1 rounded uppercase tracking-widest animate-pulse font-bold">CHỜ</span>
                            {:else if ticket.status === 'WIN'}
                              <span class="text-[10px] bg-emerald-500/20 text-emerald-400 px-2.5 py-1 rounded font-black drop-shadow-[0_0_5px_rgba(16,185,129,0.5)]">+{ticket.profit.toLocaleString()}đ</span>
                            {:else if ticket.status === 'LOSS'}
                              <span class="text-[10px] bg-red-500/10 text-red-400/80 px-2.5 py-1 rounded font-bold">{ticket.profit.toLocaleString()}đ</span>
                            {:else}
                              <span class="text-[10px] bg-amber-500/20 text-amber-500 px-2.5 py-1 rounded font-black drop-shadow-[0_0_5px_rgba(245,158,11,0.5)]">HÒA</span>
                            {/if}
                          </div>
                        </div>

                        <div class="flex items-center justify-between mt-2">
                          <div class="flex items-center gap-2 flex-wrap flex-1">
                            <span class="px-2 py-1 bg-black rounded border border-slate-700 text-xs font-bold text-white">
                              {ticket.chanLe}
                            </span>
                            <span class="px-2 py-1 bg-black rounded border border-slate-700 text-xs font-bold text-white">
                              {ticket.lonNho}
                            </span>
                          </div>
                          <div class="ml-4 pl-4 border-l border-slate-700 text-right min-w-[70px]">
                            {#if ticket.status === 'PENDING'}
                              <span class="text-xs text-slate-500 block">-20k VND</span>
                            {:else}
                              <span class="text-xs {ticket.status === 'WIN' ? 'text-emerald-500' : ticket.status === 'LOSS' ? 'text-slate-500' : 'text-amber-500'} font-bold uppercase block">{ticket.status}</span>
                            {/if}
                          </div>
                        </div>
                      </div>
                    {/each}
                  </div>
                {/if}
              </div>
           </div>
        </div>
      {/if}

      <!-- INSTALLED SKILLS ─ HIDE IN KENO & MARKET_FLOW MODE ──────────────── -->
      {#if showGrid && selectedRegion !== 'KENO' && selectedRegion !== 'MARKET_FLOW'}
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
            <div class="step-title" style="font-size: 1rem;">Kích hoạt lệnh</div>
            <div class="step-desc" style="font-size: 0.85rem;">Nhấn IGNITE PREDICTION để Ghost Scraper Agent đột kích vào hệ thống XSKT realtime.</div>
          </div>
          <div class="step-card">
            <div class="step-num">02</div>
            <div class="step-title" style="font-size: 1rem;">Tự động quét</div>
            <div class="step-desc" style="font-size: 0.85rem;">Playwright mở Chrome thực, vượt Cloudflare, cào kết quả xổ số theo thời gian thực.</div>
          </div>
          <div class="step-card">
            <div class="step-num">03</div>
            <div class="step-title" style="font-size: 1rem;">Dự báo lượng tử</div>
            <div class="step-desc" style="font-size: 0.85rem;">GSB AI Engine phân tích pattern, xuất ra số dự báo với độ chính xác cao nhất.</div>
          </div>
        </div>
      </section>
      {/if}

      </div> <!-- END RIGHT COLUMN -->
      </div> <!-- END TWO COLUMN LAYOUT -->

      <!-- ═══════════════════════════════════════════════════════ -->
      <!-- FLOATING TRIGGER BUTTON — ∞ EVOLUTION                   -->
      <!-- ═══════════════════════════════════════════════════════ -->
      {#if bootComplete}
      <button
        on:pointerdown|preventDefault={onEvoPointerDown}
        on:pointermove|preventDefault={onEvoPointerMove}
        on:pointerup|preventDefault={onEvoPointerUp}
        on:click|preventDefault={onEvoClick}
        class="evolution-trigger {isDraggingEvo ? 'dragging' : ''}"
        style="transform: translateY(-50%) translate({evoButtonTranslateX}px, {evoButtonTranslateY}px)"
        aria-label="Open Evolution Panel"
        title="Evolution Chronicle & Cognition Gauge"
      >
        <span class="evo-trig-icon">∞</span>
        <span class="evo-trig-label">EVOLUTION</span>
      </button>
      {/if}

      {#if false}
      <section style="display:none">

        <!-- SECTION HEADER -->
        <div class="flex items-center gap-4 mb-8">
          <div class="h-px flex-1 bg-gradient-to-r from-transparent via-purple-500/40 to-transparent"></div>
          <span class="flex items-center gap-3 text-[11px] font-mono text-purple-400 tracking-[0.4em] uppercase">
            <span class="w-2 h-2 rounded-full bg-purple-500 animate-pulse shadow-[0_0_8px_rgba(168,85,247,0.8)]"></span>
            ✨ EVOLUTION CHRONICLE — COGNITIVE ROLL-UP LOG
          </span>
          <div class="h-px flex-1 bg-gradient-to-r from-transparent via-purple-500/40 to-transparent"></div>
        </div>

        <!-- KPI BAR -->
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          {#each [
            { label: 'EVOLUTIONS', value: evolutionKPIs.evolution_count, icon: '∞', color: '#a855f7', glow: 'rgba(168,85,247,0.4)' },
            { label: 'LESSONS', value: evolutionKPIs.lessons_stored, icon: '◊', color: '#22d3ee', glow: 'rgba(34,211,238,0.4)' },
            { label: 'ACTIVE PINGS', value: evolutionKPIs.proactive_pings_live, icon: '⚡', color: '#f59e0b', glow: 'rgba(245,158,11,0.4)' },
            { label: 'BEST CONF.', value: (evolutionKPIs.best_confidence_ever || 0) + '%', icon: '◎', color: '#10b981', glow: 'rgba(16,185,129,0.4)' },
            { label: 'CRITIQUES', value: evolutionKPIs.critique_count, icon: '◈', color: '#6366f1', glow: 'rgba(99,102,241,0.4)' },
            { label: 'MODE', value: evolutionKPIs.is_deep_learning_active ? 'DEEP-LRN' : 'COMBAT', icon: '▶', color: evolutionKPIs.is_deep_learning_active ? '#6366f1' : '#22d3ee', glow: 'rgba(34,211,238,0.3)' },
          ] as kpi}
          <div class="relative p-4 rounded-xl border overflow-hidden group cursor-default"
            style="background: rgba(5,5,8,0.95); border-color: {kpi.color}22; box-shadow: 0 0 20px {kpi.glow}20;">
            <div class="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300"
              style="background: radial-gradient(circle at 50% 0, {kpi.glow}15, transparent 70%);"></div>
            <div class="text-2xl font-black tracking-tighter relative z-10" style="color:{kpi.color}; text-shadow: 0 0 20px {kpi.glow}">
              {kpi.icon} {kpi.value ?? '—'}
            </div>
            <div class="text-[8px] text-slate-500 uppercase tracking-[0.25em] mt-1 relative z-10">{kpi.label}</div>
          </div>
          {/each}
        </div>

        <!-- MORNING BRIEF CARD (if exists) -->
        {#if morningBrief}
        <div class="relative mb-8 p-6 rounded-2xl border border-emerald-500/30 overflow-hidden"
          style="background: linear-gradient(135deg, rgba(16,185,129,0.06) 0%, rgba(5,5,8,0.98) 60%);">
          <div class="absolute inset-0 rounded-2xl" style="background: radial-gradient(circle at 20% 50%, rgba(16,185,129,0.07) 0%, transparent 60%), radial-gradient(circle at 80% 20%, rgba(16,185,129,0.05) 0%, transparent 50%);"></div>
          <div class="flex items-start gap-6 relative z-10">
            <div class="shrink-0 w-16 h-16 rounded-full border-2 border-emerald-500/40 flex items-center justify-center"
              style="background: rgba(16,185,129,0.1); box-shadow: 0 0 30px rgba(16,185,129,0.2);">
              <span class="text-3xl">☀️</span>
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-3 mb-3">
                <span class="text-[10px] font-mono text-emerald-400 uppercase tracking-[0.3em] font-bold">MORNING BRIEF — {morningBrief.date}</span>
                <span class="px-2 py-0.5 rounded-full text-[8px] bg-emerald-500/20 text-emerald-400 uppercase tracking-wider">Session #{morningBrief.session_id}</span>
              </div>
              <p class="text-sm text-slate-300 leading-relaxed mb-4 font-sans">{morningBrief.lesson_today}</p>
              <div class="flex flex-wrap gap-6 text-[10px] font-mono">
                <span class="text-slate-500">Win Rate: <span class="text-emerald-400 font-bold">{morningBrief.current_win_rate}%</span></span>
                <span class="text-slate-500">Strategy: <span class="text-white font-bold">{morningBrief.strategy}</span></span>
                <span class="text-slate-500">PnL: <span class="{(morningBrief.daily_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'} font-bold">{(morningBrief.daily_pnl || 0).toLocaleString()}₫</span></span>
                <span class="text-slate-500">Draws: <span class="text-purple-400 font-bold">{morningBrief.draws_analyzed}</span></span>
              </div>
            </div>
          </div>
        </div>
        {/if}

        <!-- TOP BAR: Trigger + Loading -->
        <div class="flex items-center justify-between mb-5">
          <span class="text-[10px] font-mono text-slate-500 uppercase tracking-[0.25em]">
            {isEvolutionLoading ? '⧗ Đang tải...' : `${evolutionLog.length} bài học gần nhất`}
          </span>
          <div class="flex gap-3">
            <button on:click={fetchEvolutionData}
              class="px-3 py-1.5 rounded border border-slate-700 text-slate-400 text-[9px] uppercase tracking-widest hover:border-purple-500/50 hover:text-purple-400 transition-colors font-bold">
              ↻ REFRESH
            </button>
            <button on:click={triggerManualCritique} disabled={isCritiqueRunning}
              class="px-4 py-1.5 rounded border text-[9px] uppercase tracking-widest font-bold transition-all
              {isCritiqueRunning
                ? 'border-purple-500/40 text-purple-400/60 animate-pulse cursor-not-allowed'
                : 'border-purple-500/60 text-purple-400 hover:bg-purple-500/10 hover:border-purple-400'}">
              {isCritiqueRunning ? '⧐ CRITIQUE RUNNING...' : '◈ TRIGGER CRITIQUE'}
            </button>
          </div>
        </div>

        <!-- EVOLUTION LOG TIMELINE -->
        {#if evolutionLog.length === 0}
          <div class="flex flex-col items-center justify-center p-16 rounded-2xl border border-slate-800/60" style="background: rgba(5,5,8,0.95);">
            <div class="text-4xl mb-4 text-purple-500/30 animate-pulse">∞</div>
            <div class="text-slate-500 text-sm text-center font-mono uppercase tracking-widest">
              {isEvolutionLoading ? 'Orbis đang tải bài học...' : 'Chưa có bài học nào. Chạy Trigger Critique để bắt đầu.'}
            </div>
          </div>
        {:else}
          <div class="relative">
            <!-- Timeline vertical line -->
            <div class="absolute left-[31px] top-0 bottom-0 w-px bg-gradient-to-b from-purple-500/40 via-purple-500/20 to-transparent"></div>

            <div class="flex flex-col gap-3">
              {#each evolutionLog as entry, i}
              <div class="relative flex gap-5 group">
                <!-- Phase dot -->
                <div class="shrink-0 w-16 flex flex-col items-center pt-1">
                  <div class="w-5 h-5 rounded-full border-2 flex items-center justify-center transition-transform group-hover:scale-125"
                    style="background: {getPhaseColor(entry.phase)}18; border-color: {getPhaseColor(entry.phase)}; box-shadow: 0 0 12px {getPhaseColor(entry.phase)}60;">
                  </div>
                </div>

                <!-- Entry card -->
                <div class="flex-1 p-4 rounded-xl border transition-all duration-300 group-hover:border-opacity-60 mb-1"
                  style="background: rgba(5,5,8,0.95); border-color: {getPhaseColor(entry.phase)}20; group-hover:border-color: {getPhaseColor(entry.phase)}50;">
                  <div class="flex items-center gap-3 mb-2 flex-wrap">
                    <!-- Phase badge -->
                    <span class="px-2.5 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-[0.2em] border"
                      style="color: {getPhaseColor(entry.phase)}; border-color: {getPhaseColor(entry.phase)}50; background: {getPhaseColor(entry.phase)}15;">
                      {entry.phase}
                    </span>
                    <!-- Strategy -->
                    <span class="text-[10px] text-white/70 font-mono">{entry.strategy_name}</span>
                    <!-- Spacer -->
                    <div class="flex-1"></div>
                    <!-- Metrics -->
                    <span class="text-[9px] font-mono text-slate-500">
                      WR: <span style="color:{getPhaseColor(entry.phase)}" class="font-bold">{entry.win_rate?.toFixed(1)}%</span>
                    </span>
                    <span class="text-[9px] font-mono text-slate-500">
                      CONF: <span style="color:{getPhaseColor(entry.phase)}" class="font-bold">{entry.confidence_score?.toFixed(1)}%</span>
                    </span>
                    <span class="text-[9px] font-mono text-slate-500">
                      Kỳ: <span class="text-slate-400">{entry.draws_analyzed}</span>
                    </span>
                    <!-- Timestamp -->
                    <span class="text-[9px] text-slate-600 font-mono">
                      {entry.timestamp ? new Date(entry.timestamp).toLocaleString('vi-VN', {hour:'2-digit',minute:'2-digit',day:'2-digit',month:'2-digit'}) : '—'}
                    </span>
                  </div>
                  <!-- Lesson -->
                  <p class="text-[11px] text-slate-400 leading-relaxed font-sans">{entry.lesson_learned}</p>
                </div>
              </div>
              {/each}
            </div>
          </div>
        {/if}

      </section>
      {/if}


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

  <!-- ═══════════════════════════════════════════════════════════════ -->
  <!-- EVOLUTION SIDEBAR DRAWER (slides in from right)               -->
  <!-- ═══════════════════════════════════════════════════════════════ -->
  {#if showEvolutionPanel}
    <!-- Backdrop -->
    <div
      class="evo-backdrop"
      on:click={closeEvolutionPanel}
      aria-hidden="true"
    ></div>

    <!-- Drawer Panel -->
    <aside class="evo-drawer" class:evo-drawer-open={showEvolutionPanel}>

      <!-- ── DRAWER HEADER ────────────────── -->
      <div class="evo-drawer-header">
        <div class="flex items-center gap-3">
          <span style="color:#a855f7; font-size:1.4rem;">∞</span>
          <div>
            <div class="text-[11px] font-bold text-purple-400 uppercase tracking-[0.3em]">EVOLUTION CHRONICLE</div>
            <div class="text-[9px] text-slate-500 tracking-widest uppercase">Cognitive Roll-Up · Orbis Protocol</div>
          </div>
        </div>
        <button on:click={closeEvolutionPanel} class="evo-close-btn" aria-label="Close">✕</button>
      </div>

      <!-- ── COGNITION GAUGE (embedded) ─────── -->
      <div class="evo-gauge-embed">
        <div class="text-[9px] text-slate-600 uppercase tracking-widest mb-2 font-bold">◈ COGNITION GAUGE</div>
        <div class="flex items-center gap-4">
          <div class="flex-1 h-2 rounded-full bg-slate-800 overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-700"
              style="width: {confidenceLevel ?? 0}%; background: linear-gradient(90deg, #a855f7, #22d3ee); box-shadow: 0 0 10px rgba(168,85,247,0.5);"
            ></div>
          </div>
          <span class="text-xl font-black {isAnalyzing ? 'animate-pulse text-purple-400' : 'text-white'}" style="font-family:'Space Mono',monospace; min-width:56px; text-align:right;">
            {confidenceLevel !== null ? confidenceLevel + '%' : '—'}
          </span>
        </div>
        {#if isAnalyzing}
          <div class="text-[9px] text-purple-400 mt-1 animate-pulse tracking-widest">ANALYZING...</div>
        {:else}
          <div class="text-[9px] text-slate-600 mt-1 tracking-widest">{confidenceLevel !== null ? 'OPTIMAL PATH FOUND' : 'AWAITING PREDICTION'}</div>
        {/if}
      </div>

      <!-- ── KPI BAR ─────────────────────── -->
      <div class="evo-kpi-grid">
        {#each [
          { label: 'EVOLUTIONS', value: evolutionKPIs.evolution_count, icon: '∞', color: '#a855f7' },
          { label: 'LESSONS', value: evolutionKPIs.lessons_stored, icon: '◊', color: '#22d3ee' },
          { label: 'PINGS', value: evolutionKPIs.proactive_pings_live, icon: '⚡', color: '#f59e0b' },
          { label: 'BEST CONF', value: (evolutionKPIs.best_confidence_ever || 0) + '%', icon: '◎', color: '#10b981' },
          { label: 'CRITIQUES', value: evolutionKPIs.critique_count, icon: '◈', color: '#6366f1' },
          { label: 'MODE', value: evolutionKPIs.is_deep_learning_active ? 'DEEP' : 'COMBAT', icon: '▶', color: evolutionKPIs.is_deep_learning_active ? '#6366f1' : '#22d3ee' },
        ] as kpi}
          <div class="evo-kpi-card" style="border-color:{kpi.color}22;">
            <div class="text-sm font-black" style="color:{kpi.color};">{kpi.icon} {kpi.value ?? '—'}</div>
            <div class="text-[8px] text-slate-600 uppercase tracking-[0.2em] mt-0.5">{kpi.label}</div>
          </div>
        {/each}
      </div>

      <!-- ── MORNING BRIEF ───────────────── -->
      {#if morningBrief}
      <div class="evo-brief">
        <div class="flex items-center gap-2 mb-2">
          <span>☀️</span>
          <span class="text-[9px] font-bold text-emerald-400 uppercase tracking-[0.25em]">MORNING BRIEF — {morningBrief.date}</span>
        </div>
        <p class="text-[11px] text-slate-300 leading-relaxed mb-3">{morningBrief.lesson_today}</p>
        <div class="flex flex-wrap gap-4 text-[9px] font-mono">
          <span class="text-slate-500">WR: <span class="text-emerald-400 font-bold">{morningBrief.current_win_rate}%</span></span>
          <span class="text-slate-500">PnL: <span class="{(morningBrief.daily_pnl||0)>=0?'text-emerald-400':'text-red-400'} font-bold">{(morningBrief.daily_pnl||0).toLocaleString()}₫</span></span>
          <span class="text-slate-500">Kỳ: <span class="text-purple-400 font-bold">{morningBrief.draws_analyzed}</span></span>
        </div>
      </div>
      {/if}

      <!-- ── ACTIONS ─────────────────────── -->
      <div class="flex gap-2 mb-4">
        <button on:click={fetchEvolutionData}
          class="flex-1 py-2 rounded border border-slate-700 text-slate-400 text-[9px] uppercase tracking-widest hover:border-purple-500/50 hover:text-purple-400 transition-colors font-bold">
          ↻ REFRESH
        </button>
        <button on:click={triggerManualCritique} disabled={isCritiqueRunning}
          class="flex-1 py-2 rounded border text-[9px] uppercase tracking-widest font-bold transition-all
          {isCritiqueRunning ? 'border-purple-500/40 text-purple-400/60 animate-pulse cursor-not-allowed' : 'border-purple-500/60 text-purple-400 hover:bg-purple-500/10 hover:border-purple-400'}">
          {isCritiqueRunning ? '⧐ RUNNING...' : '◈ CRITIQUE'}
        </button>
      </div>

      <!-- ── DIVIDER ─────────────────────── -->
      <div class="text-[9px] text-slate-600 uppercase tracking-[0.25em] mb-3 flex items-center gap-2">
        <div class="flex-1 h-px bg-slate-800"></div>
        {isEvolutionLoading ? '⧗ Đang tải...' : `${evolutionLog.length} bài học gần nhất`}
        <div class="flex-1 h-px bg-slate-800"></div>
      </div>

      <!-- ── EVOLUTION TIMELINE ──────────── -->
      <div class="evo-timeline-scroll">
        {#if evolutionLog.length === 0}
          <div class="flex flex-col items-center justify-center py-12">
            <div class="text-4xl text-purple-500/20 animate-pulse mb-3">∞</div>
            <div class="text-slate-600 text-[10px] font-mono uppercase tracking-widest text-center">
              {isEvolutionLoading ? 'Orbis đang tải...' : 'Chưa có bài học. Bấm CRITIQUE để bắt đầu.'}
            </div>
          </div>
        {:else}
          <div class="relative">
            <div class="absolute left-[19px] top-0 bottom-0 w-px bg-gradient-to-b from-purple-500/40 via-purple-500/15 to-transparent"></div>
            <div class="flex flex-col gap-2">
              {#each evolutionLog as entry}
              <div class="relative flex gap-4 group">
                <!-- Phase dot -->
                <div class="shrink-0 w-10 flex flex-col items-center pt-1">
                  <div class="w-4 h-4 rounded-full border-2 transition-transform group-hover:scale-125"
                    style="background:{getPhaseColor(entry.phase)}18; border-color:{getPhaseColor(entry.phase)}; box-shadow:0 0 8px {getPhaseColor(entry.phase)}60;">
                  </div>
                </div>
                <!-- Card -->
                <div class="flex-1 p-3 rounded-lg border mb-1 transition-all duration-200 group-hover:border-opacity-50"
                  style="background:rgba(5,5,8,0.98); border-color:{getPhaseColor(entry.phase)}18;">
                  <div class="flex items-center gap-2 mb-1.5 flex-wrap">
                    <span class="px-2 py-px rounded-full text-[8px] font-bold uppercase tracking-[0.2em] border"
                      style="color:{getPhaseColor(entry.phase)}; border-color:{getPhaseColor(entry.phase)}50; background:{getPhaseColor(entry.phase)}15;">
                      {entry.phase}
                    </span>
                    <span class="text-[9px] text-white/60 font-mono truncate flex-1">{entry.strategy_name}</span>
                    <span class="text-[8px] text-slate-600 font-mono shrink-0">
                      {entry.timestamp ? new Date(entry.timestamp).toLocaleString('vi-VN',{hour:'2-digit',minute:'2-digit',day:'2-digit',month:'2-digit'}) : '—'}
                    </span>
                  </div>
                  <div class="flex gap-3 text-[8px] font-mono text-slate-500 mb-1.5">
                    <span>WR: <span style="color:{getPhaseColor(entry.phase)}" class="font-bold">{entry.win_rate?.toFixed(1)}%</span></span>
                    <span>CONF: <span style="color:{getPhaseColor(entry.phase)}" class="font-bold">{entry.confidence_score?.toFixed(1)}%</span></span>
                    <span>KỲ: <span class="text-slate-400">{entry.draws_analyzed}</span></span>
                  </div>
                  <p class="text-[10px] text-slate-400 leading-relaxed">{entry.lesson_learned}</p>
                </div>
              </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>

    </aside>
  {/if}

  <!-- PROACTIVE TOAST OVERLAY ───────────────────────────────────── -->
  <div class="fixed top-6 right-6 z-[9999] flex flex-col gap-3 pointer-events-none" style="max-width: 420px;">
    {#each proactiveToasts as toast (toast.id)}
      <div
        class="pointer-events-auto relative p-4 rounded-2xl border backdrop-blur-xl overflow-hidden transition-all duration-500"
        style="
          background: linear-gradient(135deg, rgba(5,5,10,0.97) 0%, rgba(10,5,20,0.97) 100%);
          border-color: {getPriorityColor(toast.priority)}40;
          box-shadow: 0 0 30px {getPriorityColor(toast.priority)}25, 0 20px 60px rgba(0,0,0,0.8);
          opacity: {toast.visible ? 1 : 0};
          transform: translateX({toast.visible ? 0 : 60}px);
        "
      >
        <!-- Glow strip -->
        <div class="absolute top-0 left-0 right-0 h-[2px]" style="background: linear-gradient(90deg, transparent, {getPriorityColor(toast.priority)}, transparent);"></div>

        <!-- Header -->
        <div class="flex items-center gap-2 mb-2">
          <span class="w-2 h-2 rounded-full animate-pulse" style="background: {getPriorityColor(toast.priority, toast.type)}; box-shadow: 0 0 8px {getPriorityColor(toast.priority, toast.type)};"></span>
          <span class="text-[9px] font-mono uppercase tracking-[0.3em] font-bold" style="color: {getPriorityColor(toast.priority, toast.type)};">
            ORBIS PING #{toast.ping_id} · {toast.priority}
          </span>
          <div class="flex-1"></div>
          <span class="text-[8px] text-slate-600 font-mono">{toast.ts}</span>
          <button
            class="w-5 h-5 rounded flex items-center justify-center text-slate-600 hover:text-white hover:bg-white/10 transition-colors text-[10px]"
            on:click={() => { proactiveToasts = proactiveToasts.filter(t => t.id !== toast.id); }}>
            ✕
          </button>
        </div>

        <!-- Type tag -->
        <div class="mb-2">
          <span class="px-2 py-0.5 rounded text-[8px] font-bold uppercase tracking-widest border"
            style="color: {getPriorityColor(toast.priority, toast.type)}; border-color: {getPriorityColor(toast.priority, toast.type)}40; background: {getPriorityColor(toast.priority, toast.type)}12;">
            {toast.type}
          </span>
        </div>

        <!-- Message -->
        <p class="text-[11px] text-slate-300 leading-relaxed font-sans">{toast.message}</p>

        <!-- Bottom progress bar (auto-dismiss indicator) -->
        <div class="absolute bottom-0 left-0 right-0 h-[2px] bg-slate-800/60 overflow-hidden">
          <div class="h-full bg-gradient-to-r from-transparent to-current animate-shrink"
            style="color: {getPriorityColor(toast.priority, toast.type)}; animation-duration: {toast.priority === 'NORMAL' ? 8 : 15}s;"></div>
        </div>
      </div>
    {/each}
  </div>

</div>

<!-- ════ SETTINGS PANEL — FLAT MINIMAL ════════════════════════ -->
{#if showSettings}
<div
  class="fixed inset-0 z-[9000] flex items-start justify-end"
  style="background: rgba(0,0,0,0.6); backdrop-filter: blur(4px);"
  on:click|self={() => showSettings = false}
  role="dialog" aria-modal="true" aria-label="Cài đặt hệ thống"
>
  <!-- Slide-in panel from right -->
  <div class="h-full w-full max-w-sm flex flex-col" style="background:#050a0f; border-left: 1px solid rgba(34,211,238,0.15);">

    <!-- HEADER -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-white/5 flex-shrink-0">
      <span class="text-[11px] font-black text-cyan-400 uppercase tracking-[0.2em]">⚙ CÀI ĐẶT HỆ THỐNG</span>
      <button on:click={() => showSettings = false} class="text-slate-500 hover:text-white transition-colors text-lg leading-none px-1">✕</button>
    </div>

    <!-- BODY — scrollable -->
    <div class="flex-1 overflow-y-auto custom-scrollbar">

      <!-- ─── SECTION: HỆ THỐNG CỐT LÕI ─── -->
      <div class="px-4 pt-4 pb-1">
        <div class="text-[9px] uppercase tracking-[0.18em] font-bold text-cyan-500 border-l-2 border-cyan-500 pl-2 mb-2">Hệ Thống Cốt Lõi</div>
      </div>

      <!-- Master Toggle -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-white/5">
        <div>
          <div class="text-xs font-semibold text-white">Master Toggle</div>
          <div class="text-[10px] text-slate-500">Bật/tắt toàn bộ AI & Phân tích</div>
        </div>
        <button on:click={() => userSettings.masterToggle = !userSettings.masterToggle}
          class="flex-shrink-0 w-10 h-5 relative transition-colors duration-200 {userSettings.masterToggle ? 'bg-cyan-500' : 'bg-slate-700'}">
          <span class="absolute top-0.5 h-4 w-4 bg-white shadow transition-all duration-200 {userSettings.masterToggle ? 'left-5' : 'left-0.5'}"></span>
        </button>
      </div>

      <!-- Auto-Bet -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-white/5">
        <div>
          <div class="text-xs font-semibold text-white">Auto-Bet</div>
          <div class="text-[10px] text-slate-500">Tự động vào lệnh (10k Keno / 20k MF)</div>
        </div>
        <button on:click={() => userSettings.autoBetEnabled = !userSettings.autoBetEnabled}
          class="flex-shrink-0 w-10 h-5 relative transition-colors duration-200 {userSettings.autoBetEnabled ? 'bg-emerald-500' : 'bg-slate-700'}">
          <span class="absolute top-0.5 h-4 w-4 bg-white shadow transition-all duration-200 {userSettings.autoBetEnabled ? 'left-5' : 'left-0.5'}"></span>
        </button>
      </div>

      <!-- ─── SECTION: HIỆU ỨNG ─── -->
      <div class="px-4 pt-4 pb-1">
        <div class="text-[9px] uppercase tracking-[0.18em] font-bold text-fuchsia-400 border-l-2 border-fuchsia-500 pl-2 mb-2">Hiệu Ứng Trực Quan</div>
      </div>

      <!-- Popup Nhãn dán -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-white/5">
        <div>
          <div class="text-xs font-semibold text-white">Nhãn dán Kết quả</div>
          <div class="text-[10px] text-slate-500">Popup Lãi/Lỗ giữa màn hình</div>
        </div>
        <button on:click={() => userSettings.popupEnabled = !userSettings.popupEnabled}
          class="flex-shrink-0 w-10 h-5 relative transition-colors duration-200 {userSettings.popupEnabled ? 'bg-fuchsia-500' : 'bg-slate-700'}">
          <span class="absolute top-0.5 h-4 w-4 bg-white shadow transition-all duration-200 {userSettings.popupEnabled ? 'left-5' : 'left-0.5'}"></span>
        </button>
      </div>

      <!-- Fireworks -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-white/5">
        <div>
          <div class="text-xs font-semibold text-white">Pháo Hoa</div>
          <div class="text-[10px] text-slate-500">Bắn pháo hoa khi Jackpot/Thắng</div>
        </div>
        <button on:click={() => userSettings.showFireworks = !userSettings.showFireworks}
          class="flex-shrink-0 w-10 h-5 relative transition-colors duration-200 {userSettings.showFireworks ? 'bg-amber-500' : 'bg-slate-700'}">
          <span class="absolute top-0.5 h-4 w-4 bg-white shadow transition-all duration-200 {userSettings.showFireworks ? 'left-5' : 'left-0.5'}"></span>
        </button>
      </div>

      <!-- Custom Texts (popup nội dung) -->
      {#if userSettings.popupEnabled}
      <div class="px-4 py-3 border-b border-white/5 flex flex-col gap-2" style="background:rgba(0,0,0,0.3);">
        <div>
          <label class="text-[9px] text-slate-500 uppercase tracking-wider block mb-1">Lời bình THẮNG</label>
          <input type="text" bind:value={userSettings.popupWinText}
            class="w-full bg-transparent border-b border-green-500/30 py-1 text-xs text-green-400 outline-none focus:border-green-500 font-medium transition-all">
        </div>
        <div>
          <label class="text-[9px] text-slate-500 uppercase tracking-wider block mb-1">Lời bình THUA</label>
          <input type="text" bind:value={userSettings.popupLossText}
            class="w-full bg-transparent border-b border-red-500/30 py-1 text-xs text-red-400 outline-none focus:border-red-500 font-medium transition-all">
        </div>
        <div>
          <label class="text-[9px] text-slate-500 uppercase tracking-wider block mb-1">Lời bình HÒA</label>
          <input type="text" bind:value={userSettings.popupBreakEvenText}
            class="w-full bg-transparent border-b border-slate-600/30 py-1 text-xs text-slate-300 outline-none focus:border-slate-500 font-medium transition-all">
        </div>
      </div>
      {/if}

      <!-- ─── SECTION: ÂM THANH ─── -->
      <div class="px-4 pt-4 pb-1">
        <div class="flex items-center justify-between">
          <div class="text-[9px] uppercase tracking-[0.18em] font-bold text-amber-400 border-l-2 border-amber-500 pl-2">Âm Thanh Hệ Thống</div>
          <button on:click={() => userSettings.soundEnabled = !userSettings.soundEnabled}
            class="flex-shrink-0 w-8 h-4 relative transition-colors duration-200 {userSettings.soundEnabled ? 'bg-amber-500' : 'bg-slate-700'}">
            <span class="absolute top-[2px] h-3 w-3 bg-white shadow transition-all duration-200 {userSettings.soundEnabled ? 'left-[18px]' : 'left-0.5'}"></span>
          </button>
        </div>
      </div>

      {#if userSettings.soundEnabled}
      <!-- Volume -->
      <div class="px-4 py-3 border-b border-white/5">
        <div class="flex justify-between text-[10px] text-slate-400 mb-2">
          <span>Volume</span><span class="text-amber-400 font-mono">{userSettings.audioVolume}%</span>
        </div>
        <input type="range" min="0" max="100" step="5" bind:value={userSettings.audioVolume}
          class="w-full h-[2px] bg-slate-800 appearance-none cursor-pointer accent-amber-500">
      </div>

      <input type="file" accept="audio/*" class="hidden" bind:this={hiddenFileInput} on:change={handleFileSelect}>

      <!-- Win Sound -->
      <div class="px-4 py-3 border-b border-white/5">
        <div class="text-[9px] text-slate-500 uppercase tracking-wider mb-2">Win Sound</div>
        <div class="grid grid-cols-3 gap-1">
          {#each ['gta_passed', 'anime_wow', 'casino_jackpot', 'mario_coin', 'tada', 'none'] as snd}
            <div class="relative group">
              <button on:click={() => { userSettings.winSound = snd; setTimeout(() => playAudioTone('win'), 50); }}
                class="w-full py-1.5 px-1 text-[9px] font-bold uppercase border transition-all text-center truncate
                  {userSettings.winSound === snd ? 'border-amber-500 text-amber-300 bg-amber-500/10' : 'border-white/5 text-slate-500 hover:border-white/20 hover:text-slate-300'}">
                {snd.replace(/_/g,' ')}{#if customAmThanh[snd]}<span class="text-emerald-400"> ©</span>{/if}
              </button>
              {#if snd !== 'none'}
              <div class="absolute right-0 top-0 opacity-0 group-hover:opacity-100 transition-opacity flex gap-0.5 z-10 bg-black/90 p-0.5">
                <button on:click={() => triggerUpload(snd)} title="Upload" class="hover:text-amber-400 p-0.5 text-slate-400 text-[9px]">⬆</button>
                {#if customAmThanh[snd]}<button on:click={() => deleteCustomAudio(snd)} class="hover:text-red-400 p-0.5 text-slate-400 text-[9px]">✕</button>{/if}
              </div>
              {/if}
            </div>
          {/each}
        </div>
      </div>

      <!-- Alert Sound -->
      <div class="px-4 py-3 border-b border-white/5">
        <div class="text-[9px] text-slate-500 uppercase tracking-wider mb-2">Draw Alert</div>
        <div class="grid grid-cols-3 gap-1">
          {#each ['ticking', 'vine_boom', 'sigma', 'jeopardy', 'to_be_continued', 'none'] as snd}
            <div class="relative group">
              <button on:click={() => { userSettings.countdownSound = snd; setTimeout(() => playAudioTone('countdown'), 50); }}
                class="w-full py-1.5 px-1 text-[9px] font-bold uppercase border transition-all text-center truncate
                  {userSettings.countdownSound === snd ? 'border-amber-500 text-amber-300 bg-amber-500/10' : 'border-white/5 text-slate-500 hover:border-white/20 hover:text-slate-300'}">
                {snd.replace(/_/g,' ')}{#if customAmThanh[snd]}<span class="text-emerald-400"> ©</span>{/if}
              </button>
              {#if snd !== 'none'}
              <div class="absolute right-0 top-0 opacity-0 group-hover:opacity-100 transition-opacity flex gap-0.5 z-10 bg-black/90 p-0.5">
                <button on:click={() => triggerUpload(snd)} title="Upload" class="hover:text-amber-400 p-0.5 text-slate-400 text-[9px]">⬆</button>
                {#if customAmThanh[snd]}<button on:click={() => deleteCustomAudio(snd)} class="hover:text-red-400 p-0.5 text-slate-400 text-[9px]">✕</button>{/if}
              </div>
              {/if}
            </div>
          {/each}
        </div>
      </div>

      <!-- Loss Sound -->
      <div class="px-4 py-3 border-b border-white/5">
        <div class="text-[9px] text-slate-500 uppercase tracking-wider mb-2">Loss Sound</div>
        <div class="flex gap-1">
          {#each ['beep_loss', 'none'] as snd}
            <button on:click={() => { userSettings.lossSound = snd; if(snd!=='none') playAudioTone('loss'); }}
              class="flex-1 py-1.5 text-[9px] font-bold uppercase border transition-all
                {userSettings.lossSound === snd ? 'border-red-500 text-red-300 bg-red-500/10' : 'border-white/5 text-slate-500 hover:border-white/20'}">
              {snd === 'beep_loss' ? '🔔 Tone thua' : '🔇 Tắt'}
            </button>
          {/each}
        </div>
      </div>
      {/if}

      <!-- ─── SECTION: CIRCUIT BREAKER ─── -->
      <div class="px-4 pt-4 pb-1">
        <div class="text-[9px] uppercase tracking-[0.18em] font-bold text-emerald-400 border-l-2 border-emerald-500 pl-2 mb-2">Circuit Breaker — Rủi Ro</div>
      </div>

      <!-- Stop Loss -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-white/5">
        <div>
          <div class="text-xs font-semibold text-white">Stop Loss</div>
          <div class="text-[10px] text-slate-500">Dừng khi lỗ vượt ngưỡng</div>
        </div>
        <div class="flex items-center gap-1">
          <input type="number" min="100000" step="100000" bind:value={userSettings.cbStopLoss}
            class="w-24 bg-transparent border-b border-red-500/40 py-1 text-xs text-red-400 outline-none focus:border-red-500 text-right font-mono">
          <span class="text-[9px] text-slate-600">đ</span>
        </div>
      </div>

      <!-- Take Profit -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-white/5">
        <div>
          <div class="text-xs font-semibold text-white">Take Profit</div>
          <div class="text-[10px] text-slate-500">Chốt lãi khi đạt ngưỡng</div>
        </div>
        <div class="flex items-center gap-1">
          <input type="number" min="100000" step="100000" bind:value={userSettings.cbTakeProfit}
            class="w-24 bg-transparent border-b border-green-500/40 py-1 text-xs text-green-400 outline-none focus:border-green-500 text-right font-mono">
          <span class="text-[9px] text-slate-600">đ</span>
        </div>
      </div>

      <!-- Cooldown kỳ -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-white/5">
        <div>
          <div class="text-xs font-semibold text-white">Cool-down kỳ</div>
          <div class="text-[10px] text-slate-500">Nghỉ sau N kỳ thua liên tiếp</div>
        </div>
        <input type="number" min="1" max="10" bind:value={userSettings.cbCooldownFailLimit}
          class="w-14 bg-transparent border-b border-amber-500/40 py-1 text-xs text-amber-400 outline-none focus:border-amber-500 text-center font-mono">
      </div>

      <!-- Kelly Fraction -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-white/5">
        <div>
          <div class="text-xs font-semibold text-white">Kelly Fraction %</div>
          <div class="text-[10px] text-slate-500">% ví mỗi kỳ (Market Flow)</div>
        </div>
        <input type="number" min="0.5" max="10" step="0.5" bind:value={userSettings.cbKellyFraction}
          class="w-14 bg-transparent border-b border-cyan-500/40 py-1 text-xs text-cyan-400 outline-none focus:border-cyan-500 text-center font-mono">
      </div>

      <!-- ─── DANGER ZONE ─── -->
      <div class="px-4 pt-4 pb-1">
        <div class="text-[9px] uppercase tracking-[0.18em] font-bold text-red-500 border-l-2 border-red-600 pl-2 mb-2">⚠ Vùng Nguy Hiểm — Reset</div>
      </div>
      <div class="px-4 pb-6 flex gap-2">
        <button on:click={() => { clearWallet(); showSettings = false; }}
          class="flex-1 py-2 text-[10px] font-bold uppercase border border-red-600/40 text-red-400 hover:bg-red-600/10 transition-colors tracking-widest">
          Reset Keno
        </button>
        <button on:click={() => { clearMarketWallet(); showSettings = false; }}
          class="flex-1 py-2 text-[10px] font-bold uppercase border border-amber-600/40 text-amber-400 hover:bg-amber-600/10 transition-colors tracking-widest">
          Reset Market
        </button>
      </div>

    </div><!-- /body -->

    <!-- FOOTER -->
    <div class="flex items-center justify-between px-4 py-3 border-t border-white/5 flex-shrink-0">
      <span class="text-[9px] text-slate-600 uppercase tracking-widest">WS Sync Active</span>
      <button on:click={() => showSettings = false}
        class="px-5 py-1.5 text-[10px] font-black uppercase tracking-widest bg-cyan-500 text-black hover:bg-cyan-400 transition-colors">
        ĐÓNG
      </button>
    </div>

  </div>
</div>
{/if}

<!-- ══ AGENT DNA CHATBOT v2.0 (ALWAYS ON) ═════════════════════════ -->
<AgentDNAChat />
<!-- Legacy NeuralCoreDashboard kept for now, will be removed when Agent DNA is confirmed stable -->
<NeuralCoreDashboard />

<!-- War Room overlay effect -->
{#if $isWarRoomActive}
  <div class="war-room-overlay" aria-hidden="true"></div>
{/if}

<!-- ════════════════════════════════════════════════════════════ -->
<style>
  /* ── ROOT ──────────────────────────────────────────────────── */
  :global(body) {
    margin: 0;
    background: #050505;
    overflow-x: hidden;
    font-family: 'Exo 2', system-ui, sans-serif;
    color: #22d3ee;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
  }

  /* ── MAIN DASHBOARD GRID (Left sidebar | Right content) ────── */
  /* Mobile: stacked. XL+: 420px left col | flex-1 right col     */
  .keno-main-grid {
    display: flex;
    flex-direction: column;
    gap: 2rem;
    align-items: stretch;
  }
  .left-col  { width: 100%; }
  .right-col { width: 100%; }

  @media (min-width: 1280px) {
    .keno-main-grid {
      display: grid;
      grid-template-columns: 420px 1fr;
      grid-template-rows: 1fr;
      gap: 2rem;
      align-items: start;
    }
    .left-col  { min-width: 0; }
    .right-col { min-width: 0; }
  }

  /* ── KENO INNER GRID (80-ball matrix | Wallet sidebar) ─────── */
  /* Mobile: stacked. XL+: matrix takes flex-1 | wallet 380px    */
  .keno-content-grid {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    width: 100%;
  }
  .keno-grid-panel   { width: 100%; min-width: 0; }
  .keno-wallet-sidebar {
    width: 100%;
    min-width: 0;
  }

  @media (min-width: 1280px) {
    .keno-content-grid {
      display: grid;
      grid-template-columns: 1fr 380px;
      gap: 1.25rem;
      align-items: start;
    }
    .keno-wallet-sidebar {
      width: 380px;
      min-width: 320px;
      max-width: 420px;
    }
  }

  @media (min-width: 1536px) {
    .keno-content-grid {
      grid-template-columns: 1fr 420px;
    }
    .keno-wallet-sidebar {
      width: 420px;
      max-width: 460px;
    }
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

  /* ── WAR ROOM OVERLAY ────────────────────────────────────────── */
  .war-room-overlay {
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 8990;
    border: 2px solid rgba(239, 68, 68, 0.5);
    animation: war-pulse 1s ease-in-out infinite alternate;
    border-radius: 0;
    box-shadow:
      inset 0 0 80px rgba(239, 68, 68, 0.08),
      0 0 40px rgba(239, 68, 68, 0.15);
  }
  @keyframes war-pulse {
    from { border-color: rgba(239, 68, 68, 0.3); box-shadow: inset 0 0 40px rgba(239, 68, 68, 0.04); }
    to   { border-color: rgba(239, 68, 68, 0.7); box-shadow: inset 0 0 100px rgba(239, 68, 68, 0.12), 0 0 60px rgba(239, 68, 68, 0.2); }
  }

  /* ── CUSTOM ANIMATIONS ─────────────────────────────────────── */
  @keyframes screenFlashAnim {
    0%   { opacity: 1; }
    40%  { opacity: 0.8; }
    100% { opacity: 0; }
  }

  @keyframes bounceIn {
    0% { transform: scale(0.3) translate(-50%, -50%); transform-origin: left top; opacity: 0; }
    50% { transform: scale(1.05) translate(-50%, -50%); transform-origin: left top; opacity: 1; }
    70% { transform: scale(0.9) translate(-50%, -50%); transform-origin: left top; }
    100% { transform: scale(1) translate(-50%, -50%); transform-origin: left top; }
  }

  /* ══════════════════════════════════════════════════════════════
     EVOLUTION SIDEBAR DRAWER
  ══════════════════════════════════════════════════════════════ */

  /* Floating trigger button — fixed right side */
  .evolution-trigger {
    position: fixed;
    right: 0;
    top: 50%;
    z-index: 500;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    /* Thu gọn padding ngang để không che nội dung wallet (chỉ cần 26-28px total width) */
    padding: 12px 4px;
    background: linear-gradient(180deg, rgba(168,85,247,0.15) 0%, rgba(5,5,8,0.95) 100%);
    border: 1px solid rgba(168,85,247,0.35);
    border-right: none;
    border-radius: 10px 0 0 10px;
    cursor: grab;
    transition: background 0.3s, border-color 0.3s, box-shadow 0.3s;
    backdrop-filter: blur(10px);
    box-shadow: -4px 0 24px rgba(168,85,247,0.15);
    touch-action: none;
  }
  .evolution-trigger.dragging {
    cursor: grabbing;
    opacity: 0.9;
    box-shadow: 0 0 40px rgba(168,85,247,0.5);
    border: 1px solid rgba(168,85,247,0.8);
    transition: none; /* Stop transition while dragging */
  }
  .evolution-trigger:not(.dragging):hover {
    background: linear-gradient(180deg, rgba(168,85,247,0.28) 0%, rgba(10,5,20,0.97) 100%);
    border-color: rgba(168,85,247,0.6);
    box-shadow: -6px 0 32px rgba(168,85,247,0.3);
  }
  .evo-trig-icon {
    font-size: 1.3rem;
    color: #a855f7;
    text-shadow: 0 0 12px rgba(168,85,247,0.8);
    animation: pulse 2.5s infinite;
  }
  .evo-trig-label {
    font-size: 0.5rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    color: #a855f7;
    text-transform: uppercase;
    writing-mode: vertical-rl;
    text-orientation: mixed;
  }

  /* Backdrop */
  .evo-backdrop {
    position: fixed;
    inset: 0;
    z-index: 600;
    background: rgba(0,0,0,0.55);
    backdrop-filter: blur(2px);
    animation: fadeIn 0.25s ease;
  }
  @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

  /* Drawer panel */
  .evo-drawer {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: min(460px, 100vw);
    max-width: 100%;
    z-index: 700;
    display: flex;
    flex-direction: column;
    background: linear-gradient(160deg, rgba(10,5,20,0.98) 0%, rgba(5,5,8,0.99) 60%);
    border-left: 1px solid rgba(168,85,247,0.25);
    box-shadow: -12px 0 60px rgba(168,85,247,0.12), -4px 0 20px rgba(0,0,0,0.8);
    animation: slideInRight 0.3s cubic-bezier(0.32,0.72,0,1) forwards;
    overflow-y: auto;
    overflow-x: hidden;
    scrollbar-width: thin;
    scrollbar-color: rgba(168,85,247,0.3) transparent;
  }
  .evo-drawer::-webkit-scrollbar { width: 4px; }
  .evo-drawer::-webkit-scrollbar-track { background: transparent; }
  .evo-drawer::-webkit-scrollbar-thumb { background: rgba(168,85,247,0.3); border-radius: 2px; }

  @keyframes slideInRight {
    from { transform: translateX(100%); opacity: 0.5; }
    to   { transform: translateX(0);    opacity: 1; }
  }

  /* Drawer header */
  .evo-drawer-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.25rem;
    border-bottom: 1px solid rgba(168,85,247,0.15);
    background: linear-gradient(90deg, rgba(168,85,247,0.08) 0%, transparent 100%);
    shrink: 0;
    flex-shrink: 0;
  }
  .evo-close-btn {
    width: 28px; height: 28px;
    display: flex; align-items: center; justify-content: center;
    border-radius: 6px;
    border: 1px solid rgba(255,255,255,0.08);
    background: rgba(255,255,255,0.04);
    color: #64748b;
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.2s;
  }
  .evo-close-btn:hover { color: #fff; background: rgba(239,68,68,0.15); border-color: rgba(239,68,68,0.3); }

  /* Cognition gauge embed */
  .evo-gauge-embed {
    padding: 1rem 1.25rem;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    background: rgba(168,85,247,0.04);
    flex-shrink: 0;
  }

  /* KPI grid — 3 cols × 2 rows */
  .evo-kpi-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.5rem;
    padding: 0.875rem 1.25rem;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    flex-shrink: 0;
  }
  .evo-kpi-card {
    padding: 0.6rem 0.75rem;
    background: rgba(5,5,8,0.95);
    border: 1px solid;
    border-radius: 8px;
  }

  /* Morning brief */
  .evo-brief {
    margin: 0 1.25rem;
    margin-bottom: 0.75rem;
    padding: 0.875rem;
    border-radius: 10px;
    border: 1px solid rgba(16,185,129,0.2);
    background: linear-gradient(135deg, rgba(16,185,129,0.06) 0%, rgba(5,5,8,0.98) 70%);
    flex-shrink: 0;
  }

  /* Actions + divider area */
  .evo-drawer > .flex.gap-2 {
    padding: 0 1.25rem;
    margin-bottom: 0.5rem;
    flex-shrink: 0;
  }
  .evo-drawer > div.text-\[9px\] {
    padding: 0 1.25rem;
    flex-shrink: 0;
  }

  /* Scrollable timeline */
  .evo-timeline-scroll {
    padding: 0.5rem 1.25rem 2rem;
  }



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

  /* ── TOAST SHRINK ANIMATION ────────────────────────────────── */
  @keyframes shrink {
    from { width: 100%; }
    to   { width: 0%; }
  }
  .animate-shrink {
    animation: shrink linear forwards;
    background: currentColor;
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
  .cd-time       { font-size: 1.2rem; font-weight: 900; letter-spacing: 0.1em; transition: color 0.3s; }
  .cd-time.cd-red { color: #ef4444; animation: pulse 0.6s infinite; }

  .nav-right   { display: flex; align-items: center; gap: 1rem; }
  .sys-status  { display: flex; align-items: center; gap: 0.4rem; font-size: 0.65rem; color: #34d399; letter-spacing: 0.15em; transition: color 0.3s; }
  .sys-status.sys-red { color: #ef4444; }
  .status-dot  { width: 7px; height: 7px; border-radius: 50%; background: #34d399; box-shadow: 0 0 6px #34d399; animation: pulse 2s infinite; }
  .status-dot.dot-red { background: #ef4444; box-shadow: 0 0 10px #ef4444; animation: pulse 0.5s infinite; }

  .nav-cmd { font-size: 0.7rem; color: #0891b2; background: rgba(34,211,238,0.05); border: 1px solid rgba(34,211,238,0.15); border-radius: 4px; padding: 0.25rem 0.75rem; display: flex; gap: 0.35rem; }
  .cmd-sym { color: #34d399; }

  /* ── WS STATUS BADGE ──────────────────────────────────────────── */
  .ws-badge {
    display: flex; align-items: center; gap: 0.35rem;
    font-size: 0.6rem; font-weight: 700; letter-spacing: 0.2em;
    padding: 0.2rem 0.6rem; border-radius: 4px;
    border: 1px solid;
    transition: all 0.4s;
    cursor: default;
  }
  .ws-badge.ws-online {
    color: #22d3ee; border-color: rgba(34,211,238,0.4);
    background: rgba(34,211,238,0.08);
  }
  .ws-badge.ws-offline {
    color: #f59e0b; border-color: rgba(245,158,11,0.4);
    background: rgba(245,158,11,0.08);
    animation: pulse 1.2s infinite;
  }
  .ws-dot {
    width: 6px; height: 6px; border-radius: 50%;
  }
  .ws-online .ws-dot {
    background: #22d3ee; box-shadow: 0 0 6px #22d3ee;
    animation: pulse 2s infinite;
  }
  .ws-offline .ws-dot {
    background: #f59e0b; box-shadow: 0 0 6px #f59e0b;
    animation: pulse 0.8s infinite;
  }


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
    border-radius: 10px; overflow: hidden; width: 100%;
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
    width: 100%; margin-bottom: 1.75rem;
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
    .nav-cmd { display: none; }
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
  .keno-draw-id   { font-size: 0.75rem; color: #a78bfa; font-family: 'Space Mono', monospace; }
  .keno-stat      { font-size: 0.65rem; color: #7c3aed; letter-spacing: 0.08em; text-transform: uppercase; font-family: 'Exo 2', sans-serif; }
  .keno-countdown { font-size: 0.7rem; color: #c084fc; font-family: 'Space Mono', monospace; letter-spacing: 0.05em; }

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
    font-size: 0.65rem; font-weight: 700; font-family: 'Space Mono', monospace;
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
    font-size: 0.85rem; font-weight: 900; color: #fff; font-family: 'Space Mono', monospace;
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

