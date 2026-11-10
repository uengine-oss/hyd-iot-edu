from pathlib import Path
from app.utils.workflow import main

if __name__ == "__main__":
    raise SystemExit(main(Path(__file__).resolve().parent))
