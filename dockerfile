# Usa uma versão leve e oficial do Python
FROM python:3.11-slim

# Define a pasta de trabalho dentro do contêiner
WORKDIR /app

# Copia a lista de compras primeiro (para o Docker instalar mais rápido)
COPY requirements.txt .

# Instala as bibliotecas (discord.py, Pillow, numpy, python-dotenv)
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o resto do seu código para dentro do contêiner
COPY . .

# O comando que o Docker vai rodar para ligar o bot
CMD ["python", "Bot.py"]