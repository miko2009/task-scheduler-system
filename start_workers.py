import sys
import os

# 添加项目根目录到Python路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)  # 用insert(0)优先搜索根目录
# 后续代码
import subprocess
import time

def main():
    print("=== 启动任务调度Worker ===")
    base_path = BASE_DIR
    # worker_paths = [
    #     ("地区验证Worker", os.path.join(base_path, "app/workers/verify_worker.py")),
    #     ("采集Worker", os.path.join(base_path, "app/workers/collect_worker.py")),
    #     ("数据分析Worker", os.path.join(base_path, "app/workers/analyze_worker.py"))
    # ]

    worker_paths = [
        ("数据分析Worker", os.path.join(base_path, "app/workers/analyze_worker.py"))
    ]

    processes = []
    for name, path in worker_paths:
        try:
            p = subprocess.Popen([sys.executable, path])
            processes.append((name, p))
            print(f"✅ {name} 启动成功 (PID: {p.pid})")
            time.sleep(1)
        except Exception as e:
            print(f"❌ {name} 启动失败: {e}")

    print("\n=== Worker全部启动完成 ===")
    print("按 Ctrl+C 停止所有Worker")

    try:
        for name, p in processes:
            p.wait()
    except KeyboardInterrupt:
        print("\n=== 停止所有Worker ===")
        for name, p in processes:
            p.terminate()
            print(f"❌ {name} 已停止")

if __name__ == "__main__":
    main()