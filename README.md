# Video Processing Microservice

Microserviço para processamento de vídeos e extração de frames, desenvolvido seguindo os princípios de Clean Architecture.

## Funcionalidades

- Submissão de vídeos para processamento
- Extração de frames em intervalos configuráveis
- Processamento assíncrono com filas
- Notificações por email sobre status do processamento
- Download de resultados em formato ZIP
- Monitoramento e estatísticas de processamento
- Integração com serviços de usuário e autenticação

## Arquitetura

O projeto segue Clean Architecture com separação clara de responsabilidades:

```
├── domain/              # Entidades e regras de negócio
├── use_cases/           # Casos de uso da aplicação
├── interfaces/          # Contratos e interfaces
├── infra/              # Implementações de infraestrutura
│   ├── controllers/     # Controllers HTTP
│   ├── repositories/    # Repositórios de dados
│   ├── services/        # Serviços externos
│   ├── gateways/        # Gateways para outros serviços
│   └── routes/          # Rotas da API
└── tests/              # Testes unitários
```

## Tecnologias Utilizadas

- **Python 3.11+**
- **FastAPI** - Framework web
- **SQLAlchemy** - ORM para banco de dados
- **PostgreSQL** - Banco de dados principal
- **Kafka** - Sistema de mensageria
- **FFmpeg** - Processamento de vídeo
- **Redis** - Cache (opcional)
- **Docker** - Containerização
- **Pytest** - Framework de testes

## Pré-requisitos

- Python 3.11 ou superior
- PostgreSQL
- Kafka (opcional, com fallback para polling)
- FFmpeg
- Docker e Docker Compose (para ambiente de desenvolvimento)

## Subir a aplicação

### Ambiente Local

1. Clone o repositório:
```bash
git clone <repository-url>
cd video-processing-microservice
```

2. Crie um ambiente virtual:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate     # Windows
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Crie a network:
```bash
docker network create fiap_x_shared_network
```

5Run:
```bash
make run
```
Swagger estará em http://localhost:8001/docs
## Configuração

### Variáveis de Ambiente

```bash
# Banco de Dados
DATABASE_URL=postgresql://user:password@localhost:5432/video_processing

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_SECURITY_PROTOCOL=PLAINTEXT

# Processamento
FFMPEG_PATH=/usr/bin/ffmpeg
FFPROBE_PATH=/usr/bin/ffprobe
MAX_CONCURRENT_JOBS=4
MAX_FILE_SIZE_MB=500

# Armazenamento
STORAGE_BASE_PATH=./storage

# Notificações
GMAIL_EMAIL=your-email@gmail.com
GMAIL_APP_PASSWORD=your-app-password

# Serviços Externos
USER_SERVICE_URL=http://localhost:8002
AUTH_SERVICE_URL=http://localhost:8001
```

## API Endpoints

### Submissão de Vídeo
```http
POST /video-processing/submit
Content-Type: multipart/form-data

{
  "video_file": <file>,
  "extraction_fps": 1.0,
  "output_format": "png",
  "quality": 95
}
```

### Status do Job
```http
GET /video-processing/jobs/{job_id}/status
```

### Lista de Jobs do Usuário
```http
GET /video-processing/jobs?status_filter=completed&skip=0&limit=20
```

### Download de Resultados
```http
GET /video-processing/jobs/{job_id}/download
```

### Exclusão de Job
```http
DELETE /video-processing/jobs/{job_id}
```

### Health Check
```http
GET /video-processing/system/health
```

## Testes

### Executar Todos os Testes
```bash
pytest
```

### Executar com Cobertura
```bash
pytest --cov --cov-report=html
```

### Executar Testes Específicos
```bash
pytest tests/test_video_processing_controller.py
pytest tests/use_cases/
pytest -k "test_submit_video"
```