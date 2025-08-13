# Usar uma imagem base oficial do Python
FROM python:3.11-slim

# Definir o diretório de trabalho dentro do contentor
WORKDIR /app

# Copiar o ficheiro de requisitos para o contentor
COPY requirements.txt .

# Instalar as dependências do sistema necessárias para as bibliotecas geoespaciais
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo o resto do código do projeto para o contentor
COPY . .

# Comando padrão a ser executado quando o contentor iniciar
CMD ["python", "cria_grafo.py"]