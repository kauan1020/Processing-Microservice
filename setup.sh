#!/bin/bash

echo "🚀 FIAP X Video Processing - Setup Automático"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    print_error "Docker não está rodando. Inicie o Docker e tente novamente."
    exit 1
fi

print_info "Docker está rodando ✅"

# Clean up any existing containers
print_info "Limpando containers existentes..."
docker-compose -f docker-compose.yaml down -v 2>/dev/null || true
docker system prune -f >/dev/null 2>&1

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    print_info "Criando arquivo .env..."
    cp .env.simple .env
else
    print_warning "Arquivo .env já existe, mantendo o atual"
fi

# Create necessary directories
print_info "Criando diretórios necessários..."
mkdir -p logs
mkdir -p alembic/versions

# Build images
print_info "Construindo imagens Docker..."
docker-compose -f docker-compose.yaml build --no-cache

if [ $? -ne 0 ]; then
    print_error "Falha ao construir as imagens"
    exit 1
fi

# Start infrastructure services first
print_info "Iniciando serviços de infraestrutura..."
docker-compose -f docker-compose.yaml up -d postgres redis zookeeper

# Wait for postgres to be ready
print_info "Aguardando PostgreSQL ficar pronto..."
timeout=60
count=0
while ! docker-compose -f docker-compose.yaml exec -T postgres pg_isready -U postgres -d video_processing >/dev/null 2>&1; do
    if [ $count -ge $timeout ]; then
        print_error "Timeout aguardando PostgreSQL"
        exit 1
    fi
    sleep 1
    count=$((count + 1))
done

print_info "PostgreSQL está pronto ✅"

# Wait for Redis to be ready
print_info "Aguardando Redis ficar pronto..."
timeout=30
count=0
while ! docker-compose -f docker-compose.yaml exec -T redis redis-cli ping >/dev/null 2>&1; do
    if [ $count -ge $timeout ]; then
        print_error "Timeout aguardando Redis"
        exit 1
    fi
    sleep 1
    count=$((count + 1))
done

print_info "Redis está pronto ✅"

# Start Kafka
print_info "Iniciando Kafka..."
docker-compose -f docker-compose.yaml up -d kafka

# Wait for Kafka to be ready (longer timeout for Kafka)
print_info "Aguardando Kafka ficar pronto (pode demorar até 2 minutos)..."
timeout=120
count=0
while ! docker-compose -f docker-compose.yaml exec -T kafka kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1; do
    if [ $count -ge $timeout ]; then
        print_warning "Kafka pode não estar pronto, mas continuando..."
        break
    fi
    sleep 2
    count=$((count + 2))
    if [ $((count % 20)) -eq 0 ]; then
        print_info "Ainda aguardando Kafka... ($count/$timeout segundos)"
    fi
done

print_info "Kafka está pronto (ou timeout atingido) ✅"

# Run database migrations
print_info "Executando migrações do banco de dados..."
docker-compose -f docker-compose.yaml run --rm db-migration

if [ $? -ne 0 ]; then
    print_warning "Migrações falharam, mas continuando..."
fi

# Start all services
print_info "Iniciando todos os serviços..."
docker-compose -f docker-compose.yaml up -d

# Wait a bit for services to start
sleep 10

# Check if API is responding
print_info "Verificando se a API está respondendo..."
for i in {1..30}; do
    if curl -f http://localhost:8001/health >/dev/null 2>&1; then
        print_info "API está respondendo ✅"
        break
    fi
    if [ $i -eq 30 ]; then
        print_warning "API pode não estar respondendo ainda"
    fi
    sleep 2
done

# Show status
echo ""
echo "📊 Status dos serviços:"
docker-compose -f docker-compose.yaml ps

echo ""
echo "🎉 Setup concluído!"
echo ""
echo "📝 Serviços disponíveis:"
echo "  🌐 API: http://localhost:8001"
echo "  📚 Documentação: http://localhost:8001/docs"
echo "  🔍 Kafka UI: http://localhost:8080 (admin/admin123)"
echo "  🗄️  PostgreSQL: localhost:5432 (postgres/password)"
echo "  🔴 Redis: localhost:6379"
echo ""
echo "🔧 Comandos úteis:"
echo "  📋 Ver logs: docker-compose -f docker-compose.yaml logs -f"
echo "  🛑 Parar tudo: docker-compose -f docker-compose.yaml down"
echo "  🧹 Limpar tudo: docker-compose -f docker-compose.yaml down -v && docker system prune -f"
echo "  ✅ Verificar saúde: curl http://localhost:8001/health"
echo ""

# Final health check
print_info "Executando verificação final de saúde..."
if curl -f http://localhost:8001/health >/dev/null 2>&1; then
    print_info "🎉 Tudo funcionando perfeitamente!"
else
    print_warning "⚠️  API pode não estar totalmente pronta ainda. Aguarde mais alguns segundos."
    echo ""
    echo "Para verificar logs:"
    echo "docker-compose -f docker-compose.yaml logs -f video-processing-api"
fi