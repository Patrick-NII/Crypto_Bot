# =============================================================================
# Okamoey Trading Platform — Orchestration
# =============================================================================
#
#   make dev           Start dev environment (frontend:3100, gateway:8100)
#   make staging       Start staging environment (frontend:3000, gateway:8000)
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
COMPOSE_DEV   := $(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml
REGISTRY      := ghcr.io/patrick-nii
VERSION       := $(shell git rev-parse --short HEAD 2>/dev/null || echo "latest")

.PHONY: dev staging stop build logs status clean promote db-reset push help

# ── Default ──────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  Okamoey — available commands:"
	@echo ""
	@echo "  make dev            Start dev env       (frontend:3100)"
	@echo "  make staging        Start staging env   (frontend:3000)"
	@echo "  make stop           Stop all containers"
	@echo "  make build          Build all images"
	@echo "  make logs           Tail all service logs"
	@echo "  make logs-auth      Tail auth-service logs"
	@echo "  make logs-frontend  Tail frontend logs"
	@echo "  make status         Show running containers"
	@echo "  make clean          Stop + remove everything"
	@echo "  make promote        Merge dev → staging"
	@echo "  make push           Push images to registry"
	@echo "  make db-reset       Reset database (DESTRUCTIVE)"
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

stop: ## Stop all containers
	@echo "▸ Stopping all containers..."
	$(COMPOSE) down
	@echo "✓ All stopped"

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
	$(COMPOSE) down --remove-orphans
	@echo "✓ Clean"

db-reset: ## Reset database (DESTRUCTIVE — drops all data)
	@echo "⚠ This will DELETE all data in PostgreSQL and Redis!"
	@read -p "  Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ] || exit 1
	$(COMPOSE) down -v
	@echo "✓ Volumes removed. Run 'make staging' or 'make dev' to recreate."
