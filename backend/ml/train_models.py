import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio
from dotenv import load_dotenv
load_dotenv()

from database.database import init_db, async_session_maker
from ml.models import MLModels
from services.data_processor import DataProcessor


def parse_args():
    parser = argparse.ArgumentParser(
        description="Train ML models from repository data stored in the database."
    )
    parser.add_argument(
        "--min-prs",
        type=int,
        default=15,
        help="Minimum number of PR examples required to train each model."
    )
    parser.add_argument(
        "--min-contributors",
        type=int,
        default=3,
        help="Minimum number of contributors required for contributor segmentation training."
    )
    parser.add_argument(
        "--models-dir",
        type=str,
        default=None,
        help="Optional path to the trained models directory. If provided, overrides the default path."
    )
    return parser.parse_args()


async def main_async():
    args = parse_args()

    # Ensure database tables exist before training.
    await init_db()

    if args.models_dir:
        models_dir = Path(args.models_dir).expanduser().resolve()
        models_dir.mkdir(parents=True, exist_ok=True)
        print(f"Using override trained models directory: {models_dir}")
    else:
        models_dir = None

    ml_models = MLModels()
    if models_dir is not None:
        ml_models.models_dir = models_dir

    print("Starting ML training from database...")

    async with async_session_maker() as db:
        try:
            result = await ml_models.train_from_db(
                db,
                min_prs=args.min_prs,
                min_contributors=args.min_contributors,
            )
            print("Training summary:")
            for line in result.get("summary", []):
                print(f"  - {line}")

            print("Persisted model files:")
            for item in sorted(ml_models.models_dir.glob("*.pkl")):
                print(f"  - {item.name}")

            if result.get("trained"):
                print("Refreshing stored ML predictions for existing PRs...")
                processor = DataProcessor(db)
                refreshed = await processor.refresh_ml_predictions(only_open_prs=False)
                print(f"Refreshed ML predictions for {refreshed} PR(s)")
            else:
                print("No models were trained. Check data availability and retry.")
        except Exception as exc:
            print(f"[ERROR] Training failed: {exc}")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main_async())
