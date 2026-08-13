#!/bin/bash
# STAMP v1.4 Batch Computation — Server Deploy Script
# Run on server (192.168.31.218) after OS restore

set -e

echo "=== STAMP v1.4 Deployment ==="
cd ~/stamp-targeted-peptide-platform || {
    echo "Cloning fresh repo..."
    git clone https://github.com/skychueung/stamp-targeted-peptide-platform.git ~/stamp-targeted-peptide-platform
    cd ~/stamp-targeted-peptide-platform
}

echo "=== Pulling v1.4 ==="
git fetch origin
git checkout v1.4-batch-computation
git pull origin v1.4-batch-computation

echo "=== Backend Setup ==="
cd backend
python3 -m venv .venv || true
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Database Init ==="
python3 -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)" || true

echo "=== Stop existing backend ==="
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 2

echo "=== Start Backend ==="
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 2 > uvicorn.log 2>&1 &
echo "Backend PID: $!"

echo "=== Frontend Build ==="
cd ../
npm install
npm run build

echo "=== Restart nginx ==="
sudo docker rm -f stamp-nginx 2>/dev/null || true
sudo docker run -d --name stamp-nginx -p 8080:80 \
    -v $(pwd)/dist:/usr/share/nginx/html:ro \
    nginx:alpine

echo "=== Health Check ==="
sleep 3
curl -s http://localhost:8001/api/health | jq . || curl -s http://localhost:8001/api/health
curl -s http://localhost:8001/api/health/db | jq . || true

echo "=== Deploy Complete ==="
echo "Frontend: http://192.168.31.218:8080"
echo "Backend:  http://192.168.31.218:8001/api"
