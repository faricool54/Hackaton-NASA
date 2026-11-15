"""Production entry point; one worker owns the bounded archive executor."""

import os

import uvicorn


def main():
    if os.environ.get("ERRANTE_SEED_DIR"):
        from pathlib import Path

        from .bootstrap import seed_products
        from .settings import Settings

        seed_products(Path(os.environ["ERRANTE_SEED_DIR"]), Settings.from_env().data_dir)
    port = int(os.environ.get("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535")
    uvicorn.run("errante_api.main:app", host="0.0.0.0", port=port, workers=1, limit_concurrency=64)


if __name__ == "__main__":
    main()
