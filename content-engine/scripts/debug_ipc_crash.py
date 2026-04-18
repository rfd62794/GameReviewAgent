import subprocess
import os
import sys
import time
import json

game_path = r"c:\Github\PyPongAI"
script_path = os.path.join(game_path, "main.py")

env = os.environ.copy()
env["PYPONGAI_AUTOMATION"] = "true"

print(f"Launching {script_path}...")
proc = subprocess.Popen(
    [sys.executable, script_path],
    cwd=game_path,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env
)

# Wait 3 seconds
time.sleep(3)
poll = proc.poll()
print(f"Poll result after 3s: {poll}")

if poll is None:
    print("Sending ping...")
    try:
        proc.stdin.write(json.dumps({"command": "ping"}) + "\n")
        proc.stdin.flush()
        print("Ping sent.")
        
        # Try to read stdout
        print("Reading stdout...")
        line = proc.stdout.readline()
        print(f"Stdout: {line}")
    except Exception as e:
        print(f"Error during ping: {e}")

time.sleep(2)
poll = proc.poll()
print(f"Final poll result: {poll}")

if poll is not None:
    print("Process died. Error log:")
    print(proc.stderr.read())
else:
    print("Process is still running. Closing...")
    proc.terminate()
