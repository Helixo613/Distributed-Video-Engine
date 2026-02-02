# Windows Setup & Compatibility Guide

The Distributed Video Engine is designed to be cross-platform, but since it relies on system-level tools like FFmpeg, Windows users need to perform a few specific setup steps.

## 1. Install FFmpeg on Windows

Unlike Linux (`apt install ffmpeg`), Windows does not come with FFmpeg.

1.  **Download:** Go to [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) and download the **"ffmpeg-git-full.7z"** release.
2.  **Extract:** Unzip the folder to a permanent location (e.g., `C:\ffmpeg`).
3.  **Add to PATH (Critical):**
    *   Search for **"Edit the system environment variables"** in the Start Menu.
    *   Click **"Environment Variables"**.
    *   Under "System variables", find **"Path"** and click **"Edit"**.
    *   Click **"New"** and add the path to the `bin` folder (e.g., `C:\ffmpeg\bin`).
    *   Click **OK** on all dialogs.
4.  **Verify:** Open a *new* PowerShell or Command Prompt and run:
    ```powershell
    ffmpeg -version
    ```

## 2. Python Environment Differences

The commands to set up Python differ slightly between Bash (WSL) and PowerShell (Windows).

**Step 1: Create Virtual Environment**
```powershell
python -m venv venv
```

**Step 2: Activate Virtual Environment**
*   **WSL/Linux:** `source venv/bin/activate`
*   **Windows (PowerShell):** `.\venv\Scripts\Activate`
    *   *Note:* If you get a permission error, run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` first.

**Step 3: Install Dependencies**
```powershell
pip install -r requirements.txt
```

## 3. Code Compatibility Notes

The core engine (`src/render_engine.py`) is written using `pathlib` and `os.path`, so it automatically handles the difference between Linux (`/`) and Windows (`\`) file paths.

**Potential Pitfalls:**
*   **Multiprocessing:** Windows uses "spawn" instead of "fork". The code already includes the required `if __name__ == "__main__":` block, which is mandatory on Windows. **Do not remove it.**
*   **File Permissions:** Windows file locking is stricter. If the engine crashes, a temporary file might remain "locked" by a zombie process. If this happens, verify no `ffmpeg.exe` processes are stuck in Task Manager.

## 4. Running the Engine

Use `python` instead of `python3` (usually):

```powershell
python src/render_engine.py --sweep
```

```