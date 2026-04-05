# =============================================================================
# Okamoey Trading Platform — Orchestration
# =============================================================================
#
#   make dev           Start dev environment (frontend:3100, gateway:8100)
#   make staging       Start staging environment (frontend:3000, gateway:8000)
#   make trading       Start trading-only environment (frontend:3200, gateway:8100)
#   make stop          Stop all containers
#   make build         Build all Docker images
#   make logs          Tail logs for all services
#   make status        Show running containers
#   make clean         Stop + remove containers, networks, orphans
#   make promote       Merge dev → staging (after commit)
#   make db-reset      Reset database (DESTRUCTIVE)
#
# =============================================================================

COMPOSE       := docker compose
COMPOSE_DEV   := $(COMPOSE) -p okamoey-dev -f docker-compose.dev.yml
REGISTRY      := ghcr.io/patrick-nii
VERSION       := $(shell git rev-parse --short HEAD 2>/dev/null || echo "latest")

.PHONY: dev staging trading stop build logs status clean promote db-reset push help

# ── Default ──────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  Okamoey v$(CURRENT_VERSION) — available commands:"
	@echo ""
	@echo "  Environments:"
	@echo "    make dev            Start dev env       (frontend:3100)"
	@echo "    make staging        Start staging env   (frontend:3000)"
	@echo "    make trading        Start trading env   (frontend:3200)"
	@echo "    make stop           Stop all containers"
	@echo "    make stop-dev       Stop dev only"
	@echo ""
	@echo "  Build & Deploy:"
	@echo "    make build          Build all images"
	@echo "    make push           Push images to registry"
	@echo "    make promote        Merge dev → staging"
	@echo "    make release        Release staging → main (production)"
	@echo ""
	@echo "  Versioning:"
	@echo "    make version        Show current version"
	@echo "    make patch          Bump patch  ($(CURRENT_VERSION) → fix)"
	@echo "    make minor          Bump minor  ($(CURRENT_VERSION) → feature)"
	@echo "    make major          Bump major  ($(CURRENT_VERSION) → breaking)"
	@echo ""
	@echo "  Monitoring:"
	@echo "    make status         Show running containers"
	@echo "    make logs           Tail all service logs"
	@echo "    make logs-auth      Tail auth-service"
	@echo "    make logs-frontend  Tail frontend"
	@echo ""
	@echo "  Maintenance:"
	@echo "    make clean          Stop + remove everything"
	@echo "    make db-reset       Reset database (DESTRUCTIVE)"
	@echo ""

# ── Environments ─────────────────────────────────────────────────────────────

dev: ## Start dev environment
	@echo "▸ Starting DEV environment (frontend:3100, gateway:8100)..."
	$(COMPOSE_DEV) up -d
	@echo "✓ Dev ready at http://localhost:3100"

staging: ## Start staging environment
	@echo "▸ Starting STAGING environment (frontend:3000, gateway:8000)..."
	$(COMPOSE) up -d
	@echo "✓ Staging ready at http://localhost:3000"

trading: ## Start trading-only environment on 3200 without the staging frontend
	@echo "▸ Starting TRADING environment (frontend:3200, gateway:8100)..."
	docker compose -p practical-swirles -f docker-compose.yml up -d \
		postgres redis auth-service portfolio-service market-data-service \
		trading-engine risk-service ml-service notification-service \
		mailing-service ai-agent-service news-service binance-proxy
	docker compose -p okamoey-dev -f docker-compose.yml -f docker-compose.dev.yml up -d --build gateway-dev frontend-trading
	@echo "✓ Trading ready at http://localhost:3200/crypto"

stop: ## Stop all containers (both environments)
	@echo "▸ Stopping all containers..."
	-$(COMPOSE_DEV) down 2>/dev/null
	$(COMPOSE) down
	@echo "✓ All stopped"

stop-dev: ## Stop dev only
	@echo "▸ Stopping DEV..."
	$(COMPOSE_DEV) down
	@echo "✓ Dev stopped"

# ── Build ────────────────────────────────────────────────────────────────────

build: ## Build all Docker images
	@echo "▸ Building all images..."
	$(COMPOSE) build
	@echo "✓ Build complete"

build-frontend: ## Build frontend only
	$(COMPOSE) build frontend

build-auth: ## Build auth-service only
	$(COMPOSE) build auth-service

build-gateway: ## Build gateway only
	$(COMPOSE) build gateway

# ── Registry ─────────────────────────────────────────────────────────────────

push: build ## Build and push images to GitHub Container Registry
	@echo "▸ Tagging and pushing images ($(VERSION))..."
	docker tag practical-swirles-frontend:latest $(REGISTRY)/okamoey-frontend:$(VERSION)
	docker tag practical-swirles-gateway:latest $(REGISTRY)/okamoey-gateway:$(VERSION)
	docker tag practical-swirles-auth-service:latest $(REGISTRY)/okamoey-auth:$(VERSION)
	docker push $(REGISTRY)/okamoey-frontend:$(VERSION)
	docker push $(REGISTRY)/okamoey-gateway:$(VERSION)
	docker push $(REGISTRY)/okamoey-auth:$(VERSION)
	@echo "✓ Pushed to $(REGISTRY) with tag $(VERSION)"

# ── Logs ─────────────────────────────────────────────────────────────────────

logs: ## Tail all logs
	$(COMPOSE) logs -f --tail=50

logs-auth:
	$(COMPOSE) logs -f --tail=50 auth-service

logs-frontend:
	$(COMPOSE) logs -f --tail=50 frontend

logs-gateway:
	$(COMPOSE) logs -f --tail=50 gateway

logs-portfolio:
	$(COMPOSE) logs -f --tail=50 portfolio-service

# ── Status ───────────────────────────────────────────────────────────────────

status: ## Show container status
	@$(COMPOSE) ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# ── Git workflow ─────────────────────────────────────────────────────────────

promote: ## Merge dev into staging
	@echo "▸ Merging dev → staging..."
	@git -C . fetch . dev:staging 2>/dev/null || \
		(echo "  Switching to staging worktree..." && \
		 git -C .claude/worktrees/practical-swirles merge dev --no-edit)
	@echo "✓ Staging updated with dev changes"
	@echo "  Run 'make staging' to rebuild"

# ── Cleanup ──────────────────────────────────────────────────────────────────

clean: ## Stop and remove containers, networks, orphans
	@echo "▸ Cleaning up..."
	-$(COMPOSE_DEV) down --remove-orphans 2>/dev/null
	$(COMPOSE) down --remove-orphans
	@echo "✓ Clean"

db-reset: ## Reset database (DESTRUCTIVE — drops all data)
	@echo "⚠ This will DELETE all data in PostgreSQL and Redis!"
	@read -p "  Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ] || exit 1
	$(COMPOSE) down -v
	@echo "✓ Volumes removed. Run 'make staging' or 'make dev' to recreate."

# ── Versioning ──────────────────────────────────────────────────────────────
# Semantic versioning: MAJOR.MINOR.PATCH
# make patch  → 0.9.0 → 0.9.1  (bug fix)
# make minor  → 0.9.1 → 0.10.0 (new feature)
# make major  → 0.10.0 → 1.0.0 (breaking change)

CURRENT_VERSION := $(shell cat VERSION 2>/dev/null || echo "0.0.0")

version: ## Show current version
	@echo "Current version: v$(CURRENT_VERSION)"

patch: ## Bump patch version (0.9.0 → 0.9.1)
	@NEW=$$(echo "$(CURRENT_VERSION)" | awk -F. '{printf "%d.%d.%d", $$1, $$2, $$3+1}') && \
	echo "$$NEW" > VERSION && \
	echo "▸ Version bumped: v$(CURRENT_VERSION) → v$$NEW" && \
	git add VERSION && \
	git commit -m "chore: bump version to v$$NEW" && \
	git tag "v$$NEW" && \
	echo "✓ Tagged v$$NEW — push with: git push && git push --tags"

minor: ## Bump minor version (0.9.0 → 0.10.0)
	@NEW=$$(echo "$(CURRENT_VERSION)" | awk -F. '{printf "%d.%d.0", $$1, $$2+1}') && \
	echo "$$NEW" > VERSION && \
	echo "▸ Version bumped: v$(CURRENT_VERSION) → v$$NEW" && \
	git add VERSION && \
	git commit -m "chore: bump version to v$$NEW" && \
	git tag "v$$NEW" && \
	echo "✓ Tagged v$$NEW — push with: git push && git push --tags"

major: ## Bump major version (0.9.0 → 1.0.0)
	@NEW=$$(echo "$(CURRENT_VERSION)" | awk -F. '{printf "%d.0.0", $$1+1}') && \
	echo "$$NEW" > VERSION && \
	echo "▸ Version bumped: v$(CURRENT_VERSION) → v$$NEW" && \
	git add VERSION && \
	git commit -m "chore: bump version to v$$NEW" && \
	git tag "v$$NEW" && \
	echo "✓ Tagged v$$NEW — push with: git push && git push --tags"

release: ## Tag current version as release + promote to main
	@echo "▸ Releasing v$(CURRENT_VERSION) to production..."
	git tag -f "v$(CURRENT_VERSION)" && \
	git checkout main && \
	git merge staging --no-edit -m "release: v$(CURRENT_VERSION)" && \
	git push origin main --tags && \
	git checkout - && \
	echo "✓ Released v$(CURRENT_VERSION) to main"
