#!/usr/bin/env bash
# Telex Bootstrap Script for macOS / Linux
# Sets up the complete local development environment with zero Docker requirement.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "\033[1;36m==========================================================\033[0m"
echo -e "\033[1;36m               Telex Contributor Bootstrap                \033[0m"
echo -e "\033[1;36m==========================================================\033[0m"

# 1. Check Python version
echo -e "\n\033[1;33m[1/6] Checking Python installation...\033[0m"
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3.10+ is required but not installed." >&2
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo -e "\033[1;32mFound $PYTHON_VERSION\033[0m"

# 2. Check Node & npm
echo -e "\n\033[1;33m[2/6] Checking Node.js and npm...\033[0m"
if ! command -v node &> /dev/null; then
    echo "Error: Node.js 18+ is required but not installed." >&2
    exit 1
fi
NODE_VERSION=$(node --version)
echo -e "\033[1;32mFound Node $NODE_VERSION\033[0m"

# 3. Environment configuration (.env)
echo -e "\n\033[1;33m[3/6] Setting up environment variables (.env)...\033[0m"
ENV_PATH="$ROOT_DIR/.env"
ENV_EXAMPLE="$ROOT_DIR/.env.example"

if [ ! -f "$ENV_PATH" ]; then
    echo "Creating .env from .env.example with secure random secrets..."
    cp "$ENV_EXAMPLE" "$ENV_PATH"

    KEYS=$(python3 -c "import base64, secrets; print(f'{secrets.token_urlsafe(32)}|{base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()}')")
    JWT_SECRET=$(echo "$KEYS" | cut -d'|' -f1)
    ENC_KEY=$(echo "$KEYS" | cut -d'|' -f2)

    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|NEXTAUTH_SECRET=.*|NEXTAUTH_SECRET=$JWT_SECRET|" "$ENV_PATH"
        sed -i '' "s|TELEX_ENCRYPTION_KEY=.*|TELEX_ENCRYPTION_KEY=$ENC_KEY|" "$ENV_PATH"
        sed -i '' "s|DATABASE_URL=.*|DATABASE_URL=sqlite+aiosqlite:///telex_demo.db|" "$ENV_PATH"
    else
        sed -i "s|NEXTAUTH_SECRET=.*|NEXTAUTH_SECRET=$JWT_SECRET|" "$ENV_PATH"
        sed -i "s|TELEX_ENCRYPTION_KEY=.*|TELEX_ENCRYPTION_KEY=$ENC_KEY|" "$ENV_PATH"
        sed -i "s|DATABASE_URL=.*|DATABASE_URL=sqlite+aiosqlite:///telex_demo.db|" "$ENV_PATH"
    fi
    echo -e "\033[1;32mGenerated .env configured for local zero-Docker SQLite.\033[0m"
else
    echo -e "\033[1;32m.env already exists. Preserving existing configuration.\033[0m"
fi

# 4. Install Python dependencies
echo -e "\n\033[1;33m[4/6] Installing Python dependencies...\033[0m"
python3 -m pip install --upgrade pip
python3 -m pip install -r "$ROOT_DIR/apps/api/requirements.txt"
python3 -m pip install -e "$ROOT_DIR/packages/telex-core"
echo -e "\033[1;32mPython dependencies installed successfully.\033[0m"

# 5. Install Node dependencies
echo -e "\n\033[1;33m[5/6] Installing Node dependencies...\033[0m"
cd "$ROOT_DIR/apps/web"
npm install
cd "$ROOT_DIR"
echo -e "\033[1;32mNode dependencies installed successfully.\033[0m"

# 6. Initialize database and verify test suite
echo -e "\n\033[1;33m[6/6] Initializing database and running test suite...\033[0m"
python3 "$ROOT_DIR/scripts/seed_demo.py" --sqlite

echo -e "\n\033[1;33mRunning test verification...\033[0m"
python3 -m pytest "$ROOT_DIR/packages/telex-core/tests"

echo -e "\n\033[1;36m==========================================================\033[0m"
echo -e "\033[1;32m  Telex development environment ready! Run 'npm run dev'  \033[0m"
echo -e "\033[1;36m==========================================================\033[0m"
