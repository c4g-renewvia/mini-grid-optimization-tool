# Determine the copy command and URL opener based on the OS
ifeq ($(OS),Windows_NT)
    CP := cmd /c copy
    URL_OPEN := cmd /c start ""
    WAIT := pause
else
    CP := cp
    URL_OPEN := 
    WAIT := read -p "Press Enter to continue..." dummy
endif

# Include .env at the top level
-include .env

# Pre-calculate missing variable flags
GOOGLE_MISSING := $(if $(strip $(NEXT_PUBLIC_GOOGLE_MAPS_API_KEY)),,1)

start_local:
	@$(MAKE) check_env
	@$(MAKE) .docker_down
	@$(MAKE) .run_docker
	@$(URL_OPEN) $(NEXTAUTH_URL)

run_docker:
	docker compose --profile local up -d --remove-orphans --build

.docker_down:
	docker compose --profile local down

.docker_prune:
	docker image prune


check_env:
ifeq ($(wildcard .env),)
	@echo "Initializing environment variables from example.env..."
	@$(CP) example.env .env
	@echo ".env file initialized."
else
	@echo ".env file already exists."
endif

	@echo "Environment check complete."


# --- Offline Mode -----------------------------------------------------------
# Run the tool with no Docker, no Postgres, no Google OAuth.
# Requires Node + Python + uv installed locally.

offline: offline_check_env offline_build_backend offline_start

offline_check_env:
	@test -f .env.local || pnpm run offline:init

offline_build_backend:
	@test -f backend/dist/minigrid-solver || (cd backend && bash build-solver.sh)

offline_start:
	@pnpm exec tsx scripts/start-offline.ts