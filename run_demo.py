import subprocess
import sys
import time
import os
import signal

def run_process(command, cwd=None, shell=False):
    print(f"Starting: {' '.join(command) if isinstance(command, list) else command}")
    return subprocess.Popen(
        command, 
        cwd=cwd, 
        shell=shell,
        # Create a new process group so we can kill the whole group later
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
    )

def kill_process_on_port(port):
    try:
        # Run netstat to find the PID
        output = subprocess.check_output(f"netstat -aon | findstr :{port}", shell=True).decode()
        for line in output.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 5 and f":{port}" in parts[1]:
                pid = parts[-1]
                print(f"Killing PID {pid} on port {port}...")
                subprocess.call(['taskkill', '/F', '/PID', pid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        pass # No process found

def main():
    print("="*60)
    print("  DISEASE OUTBREAK DETECTION SYSTEM - DEMO ENVIRONMENT")
    print("="*60)
    print("Starting all services... Press Ctrl+C to stop.")
    print("-" * 60)

    processes = []
    
    # Kill existing processes on ports to avoid conflicts
    if sys.platform == 'win32':
        ports = [8000, 8001, 3000]
        for p in ports:
            kill_process_on_port(p)
    
    try:
        # 1. Main Backend (Port 8000) - Run from backend dir to fix imports
        backend = run_process(
            [sys.executable, "-m", "uvicorn", "main:app", "--port", "8000", "--reload"],
            cwd=os.path.join(os.getcwd(), "backend")
        )
        processes.append(("Backend", backend))
        time.sleep(2) 

        # 2. ERP Simulator GUI (Port 8001)
        erp_gui = run_process(
            [sys.executable, "-m", "uvicorn", "mock_erp_gui.main:app", "--port", "8001", "--reload"],
            cwd=os.getcwd()
        )
        processes.append(("ERP GUI", erp_gui))

        # 3. Frontend (Port 3000)
        # npm run dev needs shell=True on Windows usually, or direct cmd execution
        frontend_cmd = ["npm", "run", "dev"]
        if sys.platform == 'win32':
             frontend_cmd = ["cmd", "/c", "npm", "run", "dev"]
             
        frontend = run_process(
            frontend_cmd,
            cwd=os.path.join(os.getcwd(), "frontend"),
            shell=False 
        )
        processes.append(("Frontend", frontend))

        print("-" * 60)
        print(">> Main App:      http://localhost:3000")
        print(">> Backend API:   http://localhost:8000")
        print(">> ERP Simulator: http://localhost:8001")
        print("-" * 60)
        print("System is running. Press Ctrl+C to shutdown.")

        # Keep alive
        while True:
            time.sleep(1)
            # Check if any died
            for name, p in processes:
                if p.poll() is not None:
                    print(f"Process {name} exited unexpectedly with code {p.returncode}")
                    raise KeyboardInterrupt

    except KeyboardInterrupt:
        print("\nStopping all services...")
    finally:
        for name, p in processes:
            if p.poll() is None:
                print(f"Terminating {name}...")
                if sys.platform == 'win32':
                    # Kill the process tree
                    subprocess.call(['taskkill', '/F', '/T', '/PID', str(p.pid)])
                else:
                    p.terminate()
        print("Shutdown complete.")

if __name__ == "__main__":
    main()
