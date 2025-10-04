# orion/main.py
import warnings; warnings.filterwarnings("ignore")
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=True)

from core.runtime import clear_screen, boot, run_loop

def main():
    clear_screen()
    ctx = boot()
    if ctx:
        run_loop(ctx)

if __name__ == "__main__":
    main()