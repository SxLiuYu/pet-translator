# Pet Translator Deployment Script for Beijing Server
# Usage: bash deploy_server.sh

set -e

echo "===== 毛孩子翻译官 部署脚本 ====="

# 1. Clone or update code
if [ ! -d "pet-translator" ]; then
    echo "[1/6] Cloning code..."
    git clone https://github.com/SxLiuYu/pet-translator.git
    cd pet-translator
else
    echo "[1/6] Updating code..."
    cd pet-translator
    git pull origin master
fi

# 2. Download YAMNet model
echo "[2/6] Downloading YAMNet model..."
python scripts/download_yamnet.py

# 3. Configure environment
echo "[3/6] Configuring environment..."
if [ ! -f ".env" ]; then
    cp .env.example .env
fi

# 4. Install dependencies
echo "[4/6] Installing dependencies..."
cd server
pip install -r requirements.txt

# 5. Run tests
echo "[5/6] Running tests..."
cd ..
python -m pytest tests/ -v

# 6. Start service
echo "[6/6] Starting service..."
docker-compose up -d

echo "===== Deployment complete! ====="
echo "Visit http://localhost:8000/docs for API docs"
