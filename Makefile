# ════════════════════════════════════════════════════════════════
#   MAKEFILE — Alien-Nexus "Khai Hỏa" Command Center
#   Sử dụng:
#     make ignite    → Dọn sạch + Build + Chạy toàn bộ hệ thống
#     make clean     → Dọn container + image + volume
#     make audit     → Kích hoạt QA Sniper + Overlord Webhook
#     make logs      → Xem live log của tất cả services
# ════════════════════════════════════════════════════════════════

.PHONY: ignite clean audit logs status webhook-logs restart

# ── Màu sắc terminal ──────────────────────────────────────────
RED    := \033[31m
GREEN  := \033[32m
YELLOW := \033[33m
AMBER  := \033[33m
CYAN   := \033[36m
RESET  := \033[0m
BOLD   := \033[1m

# ══════════════════════════════════════════════════════════════
# 🔥 IGNITE — Khai hỏa toàn bộ hệ thống (ZERO CACHE)
# ══════════════════════════════════════════════════════════════
ignite: clean
	@echo "$(BOLD)$(AMBER)"
	@echo "╔═══════════════════════════════════════════════════╗"
	@echo "║  🔥 ALIEN-NEXUS — IGNITION SEQUENCE INITIATED    ║"
	@echo "║  Sạch sẽ tuyệt đối · Không Cache · Không Ngủ    ║"
	@echo "╚═══════════════════════════════════════════════════╝$(RESET)"
	@echo ""

	@echo "$(CYAN)[1/4] 🏗️  Build tất cả service song song (No Cache)...$(RESET)"
	docker-compose build --parallel --no-cache

	@echo "$(CYAN)[2/4] 🚀 Khởi động hệ thống...$(RESET)"
	docker-compose up -d --force-recreate

	@echo "$(CYAN)[3/4] ⏳ Chờ core_api Healthy (tối đa 60 giây)...$(RESET)"
	@timeout=60; \
	while [ $$timeout -gt 0 ]; do \
		status=$$(docker inspect --format='{{.State.Health.Status}}' core_api 2>/dev/null); \
		if [ "$$status" = "healthy" ]; then \
			echo "$(GREEN)✅ core_api ONLINE!$(RESET)"; \
			break; \
		fi; \
		echo "   ↳ Đợi... ($$timeout giây còn lại)"; \
		sleep 3; \
		timeout=$$((timeout - 3)); \
	done

	@echo "$(CYAN)[4/4] 🔍 Kích hoạt QA Sniper + Overlord Webhook...$(RESET)"
	@$(MAKE) audit || echo "$(YELLOW)⚠️  Audit chạy sau khi system ổn định.$(RESET)"

	@echo ""
	@echo "$(GREEN)$(BOLD)"
	@echo "╔═══════════════════════════════════════════════════╗"
	@echo "║  🌌 THE NEXUS IS ALIVE!                          ║"
	@echo "║  Frontend → http://localhost:3000                ║"
	@echo "║  Backend  → http://localhost:8000                ║"
	@echo "║  API Docs → http://localhost:8000/docs           ║"
	@echo "╚═══════════════════════════════════════════════════╝$(RESET)"

# ══════════════════════════════════════════════════════════════
# 🧹 CLEAN — Dọn triệt để (Container + Image + Volume cache)
# ══════════════════════════════════════════════════════════════
clean:
	@echo "$(RED)[OPS-AGENT] Dọn dẹp môi trường cũ...$(RESET)"
	-docker-compose down --remove-orphans --volumes 2>/dev/null || true
	-docker system prune -f 2>/dev/null || true
	@echo "$(GREEN)✅ Môi trường sạch sẽ hoàn toàn.$(RESET)"

# ══════════════════════════════════════════════════════════════
# 👁️  AUDIT — Kích QA Sniper + Overlord Webhook
# ══════════════════════════════════════════════════════════════
audit:
	@echo "$(CYAN)[QA SNIPER + OVERLORD] Bắt đầu kiểm toán...$(RESET)"
	curl -s -X POST http://localhost:8000/api/overlord/audit \
	     -H "Content-Type: application/json" | python3 -m json.tool || \
	echo "$(YELLOW)⚠️  Overlord chưa bật — audit thủ công bằng QA Sniper...$(RESET)"

# ══════════════════════════════════════════════════════════════
# ⚡ SIGUSR1 — Kích audit tức thì từ terminal
# ══════════════════════════════════════════════════════════════
signal:
	@echo "$(CYAN)⚡ Bắn SIGUSR1 vào core_api...$(RESET)"
	docker exec core_api kill -USR1 $$(docker exec core_api pgrep -f "uvicorn") 2>/dev/null || \
	echo "$(RED)❌ Không tìm thấy process uvicorn trong container.$(RESET)"

# ══════════════════════════════════════════════════════════════
# 📊 STATUS — Xem trạng thái tất cả services
# ══════════════════════════════════════════════════════════════
status:
	@echo "$(BOLD)$(AMBER)═══ ALIEN-NEXUS SERVICE STATUS ═══$(RESET)"
	@docker-compose ps
	@echo ""
	@echo "$(CYAN)🏓 Health Check:$(RESET)"
	@curl -s http://localhost:8000/api/health | python3 -m json.tool 2>/dev/null || echo "core_api offline"
	@echo ""
	@curl -s http://localhost:8000/api/vault  | python3 -m json.tool 2>/dev/null || echo "vault_memory offline"

# ══════════════════════════════════════════════════════════════
# 📋 LOGS — Live logs của tất cả services
# ══════════════════════════════════════════════════════════════
logs:
	docker-compose logs -f --tail=50

webhook-logs:
	docker-compose logs -f --tail=100 core_api | grep -E --color "OVERLORD|WEBHOOK|QA SNIPER|PHOENIX|HEARTBEAT"

# ══════════════════════════════════════════════════════════════
# 🔄 RESTART — Khởi động lại nhẹ (không rebuild)
# ══════════════════════════════════════════════════════════════
restart:
	@echo "$(CYAN)🔄 Restart tất cả services...$(RESET)"
	docker-compose restart
