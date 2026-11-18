# Metaclick : Macro

Windows desktop macro utility written in Python/Tkinter.

## Download the EXE
After a successful GitHub Actions build:
1. Open the **Actions** tab.
2. Select **Build Windows EXE**.
3. Open the latest successful run.
4. Download **Metaclick-Macro-Windows** under Artifacts.
5. Extract the ZIP and run **Metaclick Macro.exe**. Python is not required.

You can start a build manually from Actions → Build Windows EXE → Run workflow.

## Build locally
On Windows with Python 3.10+, run `build_exe.bat`.

Background input depends on the target application. Some games using DirectX, raw input, exclusive fullscreen, or anti-cheat may ignore window messages.
