import subprocess
import os
import sys
import time

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

time.sleep(2)
poll = proc.poll()
print(f"Poll result: {poll}")

if poll is not None:
    print("Process died. Error log:")
    print(proc.stderr.read())
else:
    print("Process is still running. Closing...")
    proc.terminate()
