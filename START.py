#!/usr/bin/env python3
"""
InkForge — One-click launcher
Installs Flask if needed, then starts the server.
"""
import subprocess, sys, os, webbrowser, time

def install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

print("\n" + "="*52)
print("  ✦  InkForge — Web Novel Platform")
print("="*52)

# Install Flask if needed
try:
    import flask
    print("  ✓ Flask already installed")
except ImportError:
    print("  Installing Flask...")
    install("flask")
    install("werkzeug")
    print("  ✓ Flask installed")

print("  Starting server...")
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Open browser after a short delay
def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://localhost:5000")

import threading
threading.Thread(target=open_browser, daemon=True).start()

import runpy
runpy.run_path("app.py", run_name="__main__")
