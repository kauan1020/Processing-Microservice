#!/bin/bash

set -e

AWS_REGION="us-east-1"
ACCOUNT_ID="720049726178"
REPOSITORY="fiap-x-dev-video-service"
IMAGE_TAG="latest"

echo "🔧 Buildando a imagem localmente..."
docker build -t ${REPOSITORY}:${IMAGE_TAG} .

echo "🔑 Logando no AWS ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

echo "🏷️ Taggeando a imagem..."
docker tag ${REPOSITORY}:${IMAGE_TAG} ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPOSITORY}:${IMAGE_TAG}

echo "🚀 Enviando a imagem para o ECR..."
docker push ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPOSITORY}:${IMAGE_TAG}

echo "✅ Deploy concluído com sucesso!"
