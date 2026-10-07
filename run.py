import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend_py"
FRONTEND_DIR = ROOT / "frontend"


def python_bin_for_venv() -> Path:
    if sys.platform.startswith("win"):
        return BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    return BACKEND_DIR / ".venv" / "bin" / "python"


def ensure_backend_env() -> Path:
    python_bin = python_bin_for_venv()
    if not python_bin.exists():
        subprocess.run([sys.executable, "-m", "venv", str(BACKEND_DIR / ".venv")], check=True)
        python_bin = python_bin_for_venv()
    if not python_bin.exists():
        raise FileNotFoundError(f"Could not create Python environment at {python_bin}")
    subprocess.run([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run([str(python_bin), "-m", "pip", "install", "-r", str(BACKEND_DIR / "requirements.txt")], check=True)
    return python_bin


def ensure_frontend_deps() -> None:
    npm_cmd = shutil.which("npm") or shutil.which("npm.cmd") or "npm"
    if not (FRONTEND_DIR / "node_modules").exists():
        subprocess.run([npm_cmd, "install"], cwd=FRONTEND_DIR, check=True)
    return npm_cmd


def find_available_port(start_port: int, host: str = "127.0.0.1", max_tries: int = 20) -> int:
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"Could not find an available port starting at {start_port}")


def start_process(command, cwd: Path, name: str, env=None):
    print(f"Starting {name} in {cwd}...")
    proc = subprocess.Popen(command, cwd=str(cwd), stdout=None, stderr=None, env=env)
    return proc


backend_proc = None
frontend_proc = None

try:
    backend_python = ensure_backend_env()
    npm_cmd = ensure_frontend_deps()
    backend_port = find_available_port(8000)
    frontend_port = find_available_port(5173)
    frontend_env = os.environ.copy()
    frontend_env["VITE_API_URL"] = f"http://127.0.0.1:{backend_port}"
    frontend_env["VITE_WS_URL"] = f"ws://127.0.0.1:{backend_port}/ws/live"
    frontend_env["VITE_PROXY_TARGET"] = f"http://127.0.0.1:{backend_port}"
    frontend_env["VITE_FRONTEND_PORT"] = str(frontend_port)

    backend_proc = start_process(
        [str(backend_python), "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(backend_port)],
        BACKEND_DIR,
        "backend",
        env=os.environ.copy(),
    )

    time.sleep(3)
    frontend_proc = start_process(
        [npm_cmd, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(frontend_port)],
        FRONTEND_DIR,
        "frontend",
        env=frontend_env,
    )

    print("\nResQGrid is running.")
    print(f"API: http://127.0.0.1:{backend_port}")
    print(f"Frontend: http://127.0.0.1:{frontend_port}")
    print("Press Ctrl+C to stop both services.\n")

    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopping ResQGrid...")
finally:
    for proc in [frontend_proc, backend_proc]:
        if proc and proc.poll() is None:
            if sys.platform.startswith("win"):
                proc.terminate()
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                if sys.platform.startswith("win"):
                    proc.kill()
                else:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    print("Stopped.")
