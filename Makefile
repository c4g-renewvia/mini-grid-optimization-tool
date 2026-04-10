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
VAPID_MISSING := $(if $(strip $(NEXT_PUBLIC_VAPID_PUBLIC_KEY)),,1)
GOOGLE_MISSING := $(if $(and $(strip $(AUTH_GOOGLE_ID)),$(strip $(AUTH_GOOGLE_SECRET)),$(strip $(NEXT_PUBLIC_GOOGLE_MAPS_API_KEY))),,1)



start_local:
	@$(MAKE) check_env
	@$(MAKE) .docker_down
	@$(MAKE) run_docker
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

ifeq ($(VAPID_MISSING),1)
	@echo "NEXT_PUBLIC_VAPID_PUBLIC_KEY is not set in .env."
	@echo "Please update .env file with the generated VAPID public key."
	@echo "Opening VAPID generator..."
	@$(WAIT)
	@$(URL_OPEN) "https://knock.app/tools/vapid-key-generator"
endif
ifeq ($(GOOGLE_MISSING),1)
	@echo "One or more Google environment variables are missing (AUTH_GOOGLE_ID, AUTH_GOOGLE_SECRET, or NEXT_PUBLIC_GOOGLE_MAPS_API_KEY)."
	@echo "Please update .env file with the Google environment variables."
	@echo "Opening Google Cloud Console..."
	@$(WAIT)
	@$(URL_OPEN) "https://console.cloud.google.com/"
endif
	@echo "Environment check complete."