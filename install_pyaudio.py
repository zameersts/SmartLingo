"""
install_pyaudio.py
------------------
Run this script with any Python 3.x to install PyAudio inside the
SmartLingo addon's own lib/ folder so NVDA can find it without
needing admin rights or modifying system Python.

Usage:
    python install_pyaudio.py
"""
import urllib.request, json, ssl, io, zipfile, os, sys

print("=== SmartLingo: PyAudio Installer ===\n")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Detect Python version for correct wheel
py_ver = f"cp{sys.version_info.major}{sys.version_info.minor}"
is_64  = sys.maxsize > 2**32
arch   = "win_amd64" if is_64 else "win32"
print(f"Detected Python: {py_ver}, Architecture: {arch}")

print("Fetching PyAudio info from PyPI...")
try:
    with urllib.request.urlopen("https://pypi.org/pypi/PyAudio/json", context=ctx, timeout=20) as r:
        data = json.loads(r.read())
except Exception as e:
    print(f"ERROR: Cannot reach PyPI: {e}")
    input("\nPress Enter to exit.")
    sys.exit(1)

# Search for a compatible wheel: exact match first, then any cp3x win
wheel_url = wheel_name = None

# Priority 1: exact version match
for f in data.get("urls", []):
    fn = f["filename"]
    if fn.endswith(".whl") and py_ver in fn and arch in fn:
        wheel_url = f["url"]
        wheel_name = fn
        break

# Priority 2: any cp3x windows wheel from any release
if not wheel_url:
    for ver in sorted(data.get("releases", {}), reverse=True):
        for f in data["releases"][ver]:
            fn = f["filename"]
            if fn.endswith(".whl") and "cp3" in fn and arch in fn:
                wheel_url = f["url"]
                wheel_name = fn
                break
        if wheel_url:
            break

# Priority 3: any windows wheel at all
if not wheel_url:
    for ver in sorted(data.get("releases", {}), reverse=True):
        for f in data["releases"][ver]:
            fn = f["filename"]
            if fn.endswith(".whl") and "win" in fn:
                wheel_url = f["url"]
                wheel_name = fn
                break
        if wheel_url:
            break

if not wheel_url:
    print("ERROR: No compatible PyAudio wheel found on PyPI.")
    input("\nPress Enter to exit.")
    sys.exit(1)

print(f"Found wheel: {wheel_name}")
print(f"URL: {wheel_url}\n")

print("Downloading...")
try:
    with urllib.request.urlopen(wheel_url, context=ctx, timeout=60) as r:
        wheel_bytes = r.read()
    print(f"Downloaded {len(wheel_bytes)//1024} KB")
except Exception as e:
    print(f"ERROR: Download failed: {e}")
    input("\nPress Enter to exit.")
    sys.exit(1)

# Install into addon lib/ folder
lib_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")
os.makedirs(lib_dir, exist_ok=True)
print(f"\nExtracting to: {lib_dir}")

try:
    with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as zf:
        names = zf.namelist()
        zf.extractall(lib_dir)
    print(f"Extracted {len(names)} files.")
except Exception as e:
    print(f"ERROR: Extraction failed: {e}")
    input("\nPress Enter to exit.")
    sys.exit(1)

print("\n=== SUCCESS! PyAudio installed. ===")
print("Now restart NVDA and try NVDA+Alt+V for voice input.")
input("\nPress Enter to exit.")
