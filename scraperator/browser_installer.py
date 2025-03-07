import subprocess
import sys
from typing import Optional
import os
from logorator import Logger


def install_browser(browser_type: str) -> bool:
    try:
        Logger.note(f"Installing Playwright browser: {browser_type}")

        # Create a more visible message for users
        print(f"\n[Scraperator] Installing {browser_type} browser (first-time setup)")
        print("[Scraperator] This may take a few minutes...")

        # Run playwright install command
        subprocess.check_call([
                sys.executable, "-m", "playwright", "install", browser_type
        ])

        print(f"[Scraperator] Successfully installed {browser_type} browser.")
        return True

    except subprocess.CalledProcessError as e:
        Logger.note(f"Browser installation failed with exit code {e.returncode}")
        print(f"\n[Scraperator] Failed to install {browser_type} browser. Error code: {e.returncode}")

        if os.name == 'posix' and os.geteuid() != 0:
            print("[Scraperator] You may need to run with sudo privileges.")
            print(f"[Scraperator] Try: sudo playwright install {browser_type}")
        else:
            print("[Scraperator] You may need administrator privileges.")
            print(f"[Scraperator] Try running: playwright install {browser_type}")

        return False

    except Exception as e:
        Logger.note(f"Unexpected error during browser installation: {str(e)}")
        print(f"\n[Scraperator] An unexpected error occurred: {str(e)}")
        print(f"[Scraperator] Please run 'playwright install {browser_type}' manually.")
        return False