#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "==> Building React frontend production bundle..."
cd frontend
npm ci || npm install
npm run build
cd ..

echo "==> Installing Python backend dependencies..."
cd backend_py
pip install --upgrade pip
pip install -r requirements.txt
cd ..

echo "==> Build complete! ResQGrid is ready for deployment."
