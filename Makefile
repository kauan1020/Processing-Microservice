.PHONY: help env setup install test lint format run logs stop clean

help:
	@echo "Available commands:"
	@echo "  env          - Create .env file for local development"
	@echo "  setup        - Create .env file and setup local environment"
	@echo "  install      - Install Python dependencies"
	@echo "  test         - Run tests"
	@echo "  run          - Run the application locally"
	@echo "  docker-up    - Start docker-compose services"
	@echo "  docker-down  - Stop docker-compose services"
	@echo "  logs         - Show docker logs"
	@echo "  clean        - Clean up temporary files"

env:
	@echo "Creating .env file for local development..."
	@printf "%s\n" \
"# ===============================================" \
"# FIAP X Auth Service - Local Development" \
"# ===============================================" \
"" \
"# Application Settings" \
"APP_APP_NAME=FIAP X Authentication Service" \
"APP_APP_VERSION=1.0.0" \
"APP_DEBUG=true" \
"APP_HOST=0.0.0.0" \
"APP_PORT=8000" \
"APP_ENVIRONMENT=development" \
"APP_LOG_LEVEL=INFO" \
"APP_LOG_FORMAT=json" \
"APP_WORKERS=1" \
"" \
"# Database Settings" \
"DB_HOST=postgres" \
"DB_PORT=5432" \
"DB_NAME=fiap_x_auth" \
"DB_USER=postgres" \
"DB_PASSWORD=postgres123" \
"DB_POOL_SIZE=20" \
"DB_MAX_OVERFLOW=30" \
"DB_ECHO=false" \
"DB_POOL_PRE_PING=true" \
"DB_POOL_RECYCLE=3600" \
"DB_POOL_TIMEOUT=30" \
"" \
"# Redis Settings" \
"REDIS_HOST=redis" \
"REDIS_PORT=6379" \
"REDIS_PASSWORD=redis123" \
"REDIS_DB=0" \
"REDIS_MAX_CONNECTIONS=50" \
"REDIS_SOCKET_TIMEOUT=5" \
"REDIS_SOCKET_CONNECT_TIMEOUT=5" \
"" \
"# JWT Settings - CHANGE THESE IN PRODUCTION!" \
"JWT_SECRET_KEY=your-super-secret-jwt-key-minimum-32-characters-long-change-in-production" \
"JWT_ALGORITHM=HS256" \
"JWT_ISSUER=fiap-x-auth" \
"JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15" \
"JWT_REFRESH_TOKEN_EXPIRE_DAYS=30" \
"JWT_REMEMBER_ME_ACCESS_EXPIRE_MINUTES=30" \
"JWT_REMEMBER_ME_REFRESH_EXPIRE_DAYS=90" \
"" \
"# Security Settings" \
"SECURITY_BCRYPT_ROUNDS=12" \
"SECURITY_CHECK_COMPROMISED_PASSWORDS=false" \
"SECURITY_RATE_LIMIT_REQUESTS=100" \
"SECURITY_RATE_LIMIT_WINDOW=60" \
"SECURITY_CORS_ORIGINS=[\"*\"]" \
"SECURITY_CORS_METHODS=[\"GET\", \"POST\", \"PUT\", \"DELETE\"]" \
"SECURITY_CORS_HEADERS=[\"*\"]" \
"" \
"# ===============================================" \
"# SENSITIVE VARIABLES - FILL THESE OUT!" \
"# ===============================================" \
"# Email Configuration (Optional - for notifications)" \
"# NOTIFICATION_GMAIL_EMAIL=your-email@gmail.com" \
"# NOTIFICATION_GMAIL_APP_PASSWORD=your-16-char-app-password" \
"" \
"# Production Database (if connecting to external DB)" \
"# DB_HOST=your-production-db-host" \
"# DB_PASSWORD=your-secure-password" \
"" \
"# Production Redis (if using external Redis)" \
"# REDIS_HOST=your-redis-host" \
"# REDIS_PASSWORD=your-redis-password" \
> .env
	@echo " .env file created!"
	@echo ""
	@echo " IMPORTANT: Update sensitive variables in .env:"
	@echo "   - JWT_SECRET_KEY (for production)"
	@echo "   - DB_PASSWORD (if using external database)"
	@echo "   - REDIS_PASSWORD (if using external Redis)"
	@echo "   - Email settings (if enabling notifications)"


	@echo " .env file created!"
	@echo ""
	@echo " IMPORTANT: Update sensitive variables in .env:"
	@echo "   - JWT_SECRET_KEY (for production)"
	@echo "   - DB_PASSWORD (if using external database)"
	@echo "   - REDIS_PASSWORD (if using external Redis)"
	@echo "   - Email settings (if enabling notifications)"

setup: env
	@echo "Setting up local development environment..."
	@echo "1. Creating Python virtual environment..."
	python -m venv .venv
	@echo "2. Installing dependencies..."
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	@echo ""
	@echo "Setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "1. Activate virtual environment: source .venv/bin/activate"
	@echo "2. Start services: make docker-up"
	@echo "3. Run migrations: alembic upgrade head"
	@echo "4. Start application: make run"

install:
	pip install --upgrade pip
	pip install -r requirements.txt

test:
	pytest test/ -v --cov --cov-report=html --cov-report=term

run:
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

logs:
	docker-compose logs -f

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage