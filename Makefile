run:
	@echo "Gerando .env sem credenciais do Gmail..."
	@echo "APP_NAME=FIAP X Video Processing Service" > .env
	@echo "APP_VERSION=1.0.0" >> .env
	@echo "APP_ENVIRONMENT=development" >> .env
	@echo "APP_DEBUG=true" >> .env
	@echo "APP_HOST=0.0.0.0" >> .env
	@echo "APP_PORT=8001" >> .env
	@echo "APP_WORKERS=1" >> .env
	@echo "" >> .env
	@echo "# Database Settings" >> .env
	@echo "DATABASE_HOST=fiap-x-video-processing-db" >> .env
	@echo "DATABASE_PORT=5432" >> .env
	@echo "DATABASE_NAME=video_processing" >> .env
	@echo "DATABASE_USER=postgres" >> .env
	@echo "DATABASE_PASSWORD=postgres123" >> .env
	@echo "DATABASE_ECHO=false" >> .env
	@echo "DATABASE_POOL_SIZE=10" >> .env
	@echo "DATABASE_MAX_OVERFLOW=20" >> .env
	@echo "DATABASE_POOL_TIMEOUT=30" >> .env
	@echo "DATABASE_POOL_RECYCLE=3600" >> .env
	@echo "" >> .env
	@echo "# Redis Settings" >> .env
	@echo "REDIS_HOST=fiap-x-video-processing-redis" >> .env
	@echo "REDIS_PORT=6379" >> .env
	@echo "REDIS_PASSWORD=" >> .env
	@echo "REDIS_DB=0" >> .env
	@echo "REDIS_MAX_CONNECTIONS=50" >> .env
	@echo "" >> .env
	@echo "# Kafka Settings" >> .env
	@echo "KAFKA_BOOTSTRAP_SERVERS=kafka:29092" >> .env
	@echo "KAFKA_EXTERNAL_PORT=9092" >> .env
	@echo "KAFKA_SECURITY_PROTOCOL=PLAINTEXT" >> .env
	@echo "KAFKA_SASL_MECHANISM=PLAIN" >> .env
	@echo "KAFKA_SASL_USERNAME=" >> .env
	@echo "KAFKA_SASL_PASSWORD=" >> .env
	@echo "KAFKA_TOPIC_VIDEO_JOBS=video_jobs" >> .env
	@echo "KAFKA_TOPIC_NOTIFICATIONS=notifications" >> .env
	@echo "KAFKA_TOPIC_PROCESSING=video_processing" >> .env
	@echo "KAFKA_TOPIC_SYSTEM_ALERTS=system_alerts" >> .env
	@echo "KAFKA_GROUP_ID=video_processing_group" >> .env
	@echo "KAFKA_AUTO_OFFSET_RESET=earliest" >> .env
	@echo "KAFKA_ENABLE_AUTO_COMMIT=false" >> .env
	@echo "KAFKA_SESSION_TIMEOUT_MS=30000" >> .env
	@echo "KAFKA_HEARTBEAT_INTERVAL_MS=10000" >> .env
	@echo "" >> .env
	@echo "# Auth Service Settings" >> .env
	@echo "AUTH_SERVICE_URL=http://fiap_x_auth_service:8000" >> .env
	@echo "AUTH_API_KEY=dev-auth-key-123" >> .env
	@echo "AUTH_VALIDATE_TOKEN_ENDPOINT=/auth/validate" >> .env
	@echo "AUTH_USER_INFO_ENDPOINT=/users/profile" >> .env
	@echo "AUTH_RETRY_ATTEMPTS=3" >> .env
	@echo "AUTH_CACHE_TTL_SECONDS=300" >> .env
	@echo "AUTH_TIMEOUT=30" >> .env
	@echo "" >> .env
	@echo "# User Service Settings" >> .env
	@echo "USER_SERVICE_SERVICE_URL=http://fiap_x_auth_service:8000" >> .env
	@echo "USER_SERVICE_TIMEOUT=30" >> .env
	@echo "USER_SERVICE_API_KEY=dev-user-service-key-123" >> .env
	@echo "USER_SERVICE_RETRY_ATTEMPTS=3" >> .env
	@echo "USER_SERVICE_CACHE_TTL_SECONDS=300" >> .env
	@echo "" >> .env
	@echo "# Notification Settings" >> .env
	@echo "NOTIFICATION_SERVICE_URL=http://localhost:8003" >> .env
	@echo "NOTIFICATION_API_KEY=dev-notification-key-123" >> .env
	@echo "NOTIFICATION_FROM_EMAIL=kauan.silva@advolve.ai" >> .env
	@echo "NOTIFICATION_FROM_NAME=FIAP X Video Processing" >> .env
	@echo "NOTIFICATION_ADMIN_EMAILS=kauan.silva@advolve.ai,support@fiapx.com" >> .env
	@echo "NOTIFICATION_RETRY_ATTEMPTS=3" >> .env
	@echo "NOTIFICATION_TIMEOUT=30" >> .env
	@echo "" >> .env
	@echo "# Processing Settings" >> .env
	@echo "PROCESSING_FFMPEG_PATH=ffmpeg" >> .env
	@echo "PROCESSING_FFPROBE_PATH=ffprobe" >> .env
	@echo "PROCESSING_MAX_FILE_SIZE_MB=500" >> .env
	@echo "PROCESSING_MAX_CONCURRENT_JOBS=4" >> .env
	@echo "PROCESSING_MAX_CONCURRENT_JOBS_PER_WORKER=2" >> .env
	@echo "PROCESSING_JOB_TIMEOUT_MINUTES=60" >> .env
	@echo "PROCESSING_TEMP_CLEANUP_HOURS=24" >> .env
	@echo "PROCESSING_RETRY_ATTEMPTS=3" >> .env
	@echo "PROCESSING_RETRY_DELAY_SECONDS=60" >> .env
	@echo "" >> .env
	@echo "# Storage Settings" >> .env
	@echo "STORAGE_BASE_PATH=/app/storage" >> .env
	@echo "STORAGE_VIDEO_PATH=/app/storage/videos" >> .env
	@echo "STORAGE_FRAMES_PATH=/app/storage/frames" >> .env
	@echo "STORAGE_ZIP_PATH=/app/storage/results" >> .env
	@echo "STORAGE_TEMP_PATH=/app/storage/temp" >> .env
	@echo "STORAGE_MAX_DISK_USAGE_PERCENT=85" >> .env
	@echo "STORAGE_CLEANUP_OLD_FILES_DAYS=30" >> .env
	@echo "" >> .env
	@echo "# CORS Settings" >> .env
	@echo "CORS_ALLOWED_ORIGINS=*" >> .env
	@echo "CORS_ALLOW_CREDENTIALS=true" >> .env
	@echo "CORS_ALLOWED_METHODS=*" >> .env
	@echo "CORS_ALLOWED_HEADERS=*" >> .env
	@echo "" >> .env
	@echo "# Kafka UI Settings" >> .env
	@echo "KAFKA_UI_PORT=8080" >> .env
	@echo "KAFKA_UI_USERNAME=admin" >> .env
	@echo "KAFKA_UI_PASSWORD=admin123" >> .env
	@echo "" >> .env

	@echo "Iniciando docker compose up..."
	docker compose up
