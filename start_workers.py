import sys
import os
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR) 


def main():
    print("=== Worker start ===")
    base_path = BASE_DIR
    worker_paths = [
        ("region-Worker", os.path.join(base_path, "app/workers/verify_worker.py")),
        ("collection-Worker", os.path.join(base_path, "app/workers/collect_worker.py")),
        ("analyze-Worker", os.path.join(base_path, "app/workers/analyze_worker.py")),
        ("email-send-Worker", os.path.join(base_path, "app/workers/email_worker.py"))
     ]

    processes = []
    for name, path in worker_paths:
        try:
            p = subprocess.Popen([sys.executable, path])
            processes.append((name, p))
            print(f"✅ {name} start success (PID: {p.pid})")
            time.sleep(1)
        except Exception as e:
            print(f"❌ {name} start failed: {e}")

    print("\n=== Worker start finish ===")

    try:
        for name, p in processes:
            p.wait()
    except KeyboardInterrupt:
        print("\n=== stop all Worker ===")
        for name, p in processes:
            p.terminate()
            print(f"❌ {name} stopped")

if __name__ == "__main__":
    main()