# bark.spec -- PyInstaller build spec for Bark
# Build: pyinstaller bark.spec --clean
# Output: dist/Bark/Bark.exe

import glob
import os

block_cipher = None
spec_dir = os.path.dirname(os.path.abspath(SPECPATH))

# ---------------------------------------------------------------------------
# Binaries: CUDA DLLs + CTranslate2 + PortAudio
# ---------------------------------------------------------------------------
binaries = []

# Locate site-packages (works whether run from venv or system Python)
import site
_sp_dirs = site.getsitepackages()
venv_sp = None
for d in _sp_dirs:
    if os.path.isdir(d):
        venv_sp = d
        break
if venv_sp is None:
    venv_sp = os.path.join(spec_dir, ".venv", "Lib", "site-packages")

# NVIDIA CUDA libraries
nvidia_base = os.path.join(venv_sp, "nvidia")
for sub in ["cublas/bin", "cudnn/bin", "cuda_runtime/bin", "cufft/bin"]:
    full = os.path.join(nvidia_base, sub)
    if os.path.isdir(full):
        for dll in glob.glob(os.path.join(full, "*.dll")):
            binaries.append((dll, "."))

# CTranslate2 native DLLs
ct2_dir = os.path.join(venv_sp, "ctranslate2")
if os.path.isdir(ct2_dir):
    for dll in glob.glob(os.path.join(ct2_dir, "*.dll")):
        binaries.append((dll, "."))

# sounddevice / PortAudio
sd_dir = os.path.join(venv_sp, "_sounddevice_data", "portaudio-binaries")
if os.path.isdir(sd_dir):
    for dll in glob.glob(os.path.join(sd_dir, "*.dll")):
        binaries.append((dll, "_sounddevice_data/portaudio-binaries"))

# ---------------------------------------------------------------------------
# Data files: icons, VERSION, Silero VAD model
# ---------------------------------------------------------------------------
datas = [
    (os.path.join(spec_dir, "icon.ico"), "."),
    (os.path.join(spec_dir, "icon.png"), "."),
    (os.path.join(spec_dir, "VERSION"), "."),
]
# Silero VAD JIT model (pre-saved during build step)
vad_path = os.path.join(spec_dir, "silero_vad.jit")
if os.path.exists(vad_path):
    datas.append((vad_path, "."))

# ---------------------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------------------
hiddenimports = [
    "pynput.keyboard._win32",
    "pynput.mouse._win32",
    "numpy",
    "sounddevice",
    "PIL",
    "ctranslate2",
    "faster_whisper",
    "huggingface_hub",
]

# ---------------------------------------------------------------------------
# Excludes (size reduction -- strip unused PyTorch/Python modules)
# ---------------------------------------------------------------------------
excludes = [
    "torch.distributed",
    "torch.testing",
    "torch._dynamo",
    "torch.onnx",
    "torch.utils.tensorboard",
    "torch.profiler",
    "torchaudio",
    "torchvision",
    "matplotlib",
    "scipy",
    "pandas",
    "IPython",
    "notebook",
    "pytest",
    "setuptools",
    "pip",
    "tkinter.test",
]

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [os.path.join(spec_dir, "dictation.py")],
    pathex=[spec_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # onedir mode
    name="Bark",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # windowed app (no console)
    disable_windowed_traceback=False,
    icon=os.path.join(spec_dir, "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=["cublas*.dll", "cudnn*.dll", "cudart*.dll"],
    name="Bark",
)
