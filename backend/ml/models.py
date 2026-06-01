import pickle
from datetime import datetime
from pathlib import Path
from typing import List
import numpy as np
from sklearn.cluster import KMeans
from sklearn.ensemble import GradientBoostingRegressor, IsolationForest, RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from config import ML_MODELS_DIR
from services.filters import ensure_utc


class MLModels:
    def __init__(self):
        # Resolve the trained model directory relative to backend root.
        models_path = Path(ML_MODELS_DIR)
        if not models_path.is_absolute():
            models_path = Path(__file__).resolve().parents[1] / models_path
        self.models_dir = models_path
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self.delay_model = None
        self.bottleneck_model = None
        self.risk_model = None
        self.review_wait_model = None
        self.contributor_kmeans = None
        self.scaler = None
    
    def train_delay_prediction(self, X: np.ndarray, y: np.ndarray) -> bool:
        """Train PR delay prediction model."""
        try:
            self.delay_model = GradientBoostingRegressor(n_estimators=100, random_state=42)
            self.delay_model.fit(X, y)
            saved = self._save_model(self.delay_model, "delay_model.pkl")
            if not saved:
                print("[ML WARNING] delay_model trained but failed to persist.", flush=True)
            return saved
        except Exception as exc:
            print(f"[ML ERROR] Error training delay model: {exc}", flush=True)
            self.delay_model = None
            return False
    
    def predict_delay(self, features: List[float]) -> float:
        """Predict PR merge delay in days."""
        if self.delay_model is None:
            self.delay_model = self._load_model("delay_model.pkl")
        
        if self.delay_model is None:
            return 0.0

        try:
            X = np.array(features).reshape(1, -1)
            return max(0, float(self.delay_model.predict(X)[0]))
        except Exception as exc:
            print(f"[ML ERROR] Delay prediction failed: {exc}", flush=True)
            return 0.0
    
    def train_bottleneck_detection(self, X: np.ndarray) -> bool:
        """Train bottleneck detection model."""
        try:
            self.bottleneck_model = IsolationForest(contamination=0.1, random_state=42)
            self.bottleneck_model.fit(X)
            saved = self._save_model(self.bottleneck_model, "bottleneck_model.pkl")
            if not saved:
                print("[ML WARNING] bottleneck_model trained but failed to persist.", flush=True)
            return saved
        except Exception as exc:
            print(f"[ML ERROR] Error training bottleneck model: {exc}", flush=True)
            self.bottleneck_model = None
            return False
    
    def predict_bottleneck(self, features: List[float]) -> float:
        """Predict bottleneck probability (0-1)."""
        if self.bottleneck_model is None:
            self.bottleneck_model = self._load_model("bottleneck_model.pkl")
        
        if self.bottleneck_model is None:
            return 0.0

        try:
            X = np.array(features).reshape(1, -1)
            anomaly_score = self.bottleneck_model.score_samples(X)[0]
            probability = 1 / (1 + np.exp(anomaly_score))
            return float(probability)
        except Exception as exc:
            print(f"[ML ERROR] Bottleneck prediction failed: {exc}", flush=True)
            return 0.0
    
    def train_risk_score(self, X: np.ndarray, y: np.ndarray) -> bool:
        """Train PR risk score model."""
        try:
            self.risk_model = LogisticRegression(random_state=42, max_iter=1000)
            self.risk_model.fit(X, y)
            saved = self._save_model(self.risk_model, "risk_model.pkl")
            if not saved:
                print("[ML WARNING] risk_model trained but failed to persist.", flush=True)
            return saved
        except Exception as exc:
            print(f"[ML ERROR] Error training risk model: {exc}", flush=True)
            self.risk_model = None
            return False
    
    def predict_risk(self, features: List[float]) -> float:
        """Predict PR risk score (0-1)."""
        if self.risk_model is None:
            self.risk_model = self._load_model("risk_model.pkl")
        
        if self.risk_model is None:
            return 0.0

        try:
            X = np.array(features).reshape(1, -1)
            return float(self.risk_model.predict_proba(X)[0][1])
        except Exception as exc:
            print(f"[ML ERROR] Risk prediction failed: {exc}", flush=True)
            return 0.0
    
    def train_review_wait_prediction(self, X: np.ndarray, y: np.ndarray) -> bool:
        """Train review wait time prediction model."""
        try:
            self.review_wait_model = RandomForestRegressor(n_estimators=100, random_state=42)
            self.review_wait_model.fit(X, y)
            saved = self._save_model(self.review_wait_model, "review_wait_model.pkl")
            if not saved:
                print("[ML WARNING] review_wait_model trained but failed to persist.", flush=True)
            return saved
        except Exception as exc:
            print(f"[ML ERROR] Error training review wait model: {exc}", flush=True)
            self.review_wait_model = None
            return False
    
    def predict_review_wait(self, features: List[float]) -> float:
        """Predict review wait time in hours."""
        if self.review_wait_model is None:
            self.review_wait_model = self._load_model("review_wait_model.pkl")
        
        if self.review_wait_model is None:
            return 0.0

        try:
            X = np.array(features).reshape(1, -1)
            return max(0, float(self.review_wait_model.predict(X)[0]))
        except Exception as exc:
            print(f"[ML ERROR] Review wait prediction failed: {exc}", flush=True)
            return 0.0
    
    def train_contributor_segmentation(self, X: np.ndarray, n_clusters: int = 3) -> bool:
        """Train contributor segmentation model."""
        try:
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            self.contributor_kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            self.contributor_kmeans.fit(X_scaled)
            saved_kmeans = self._save_model(self.contributor_kmeans, "contributor_kmeans.pkl")
            if not saved_kmeans:
                print("[ML WARNING] contributor_kmeans trained but failed to persist.", flush=True)
            saved_scaler = self._save_model(self.scaler, "scaler.pkl")
            if not saved_scaler:
                print("[ML WARNING] scaler trained but failed to persist.", flush=True)
            return saved_kmeans and saved_scaler
        except Exception as exc:
            print(f"[ML ERROR] Error training contributor segmentation: {exc}", flush=True)
            self.contributor_kmeans = None
            self.scaler = None
            return False
    
    def predict_contributor_segment(self, features: List[float]) -> int:
        """Predict contributor segment."""
        if self.contributor_kmeans is None:
            self.contributor_kmeans = self._load_model("contributor_kmeans.pkl")
        if self.scaler is None:
            self.scaler = self._load_model("scaler.pkl")
        
        if self.contributor_kmeans is None or self.scaler is None:
            print("[ML WARNING] Contributor segmentation models unavailable.", flush=True)
            return 0

        try:
            X = np.array(features).reshape(1, -1)
            X_scaled = self.scaler.transform(X)
            return int(self.contributor_kmeans.predict(X_scaled)[0])
        except Exception as exc:
            print(f"[ML ERROR] Contributor segment prediction failed: {exc}", flush=True)
            return 0
    
    def models_exist(self) -> bool:
        """Return True if all expected ML model files exist."""
        expected_files = [
            "delay_model.pkl",
            "bottleneck_model.pkl",
            "risk_model.pkl",
            "review_wait_model.pkl",
            "contributor_kmeans.pkl",
            "scaler.pkl",
        ]
        return all((self.models_dir / name).exists() for name in expected_files)

    async def train_from_db(self, db: AsyncSession, min_prs: int = 15, min_contributors: int = 3) -> dict:
        """Train or rebuild ML models from repository data in the database."""
        from database.models import Contributor, PullRequest, MLPrediction

        results = {
            "trained": False,
            "models": {},
            "summary": []
        }

        result = await db.execute(select(PullRequest))
        prs = result.scalars().all()
        if len(prs) < min_prs:
            results["summary"].append(
                f"Not enough PRs to train ML models (found {len(prs)}, need {min_prs})."
            )
            return results

        delay_features = []
        delay_labels = []
        bottleneck_features = []
        risk_features = []
        risk_labels = []
        review_wait_features = []
        review_wait_labels = []

        now = ensure_utc(datetime.utcnow())
        for pr in prs:
            if pr.created_at is None:
                continue

            prediction_result = await db.execute(
                select(MLPrediction)
                .where(MLPrediction.pr_id == pr.id)
                .order_by(MLPrediction.created_at.desc())
            )
            prediction = prediction_result.scalars().first()
            if prediction is None:
                continue

            age_days = max(0, (now - ensure_utc(pr.created_at)).days)
            files_changed = float(pr.files_changed or 0)
            commit_count = float(pr.commit_count or 0)
            review_count = float(pr.review_count or 0)
            lines_added = float(pr.lines_added or 0)
            lines_deleted = float(pr.lines_deleted or 0)
            comment_count = float(pr.comment_count or 0)
            wait_for_review_hours = float(pr.wait_for_review_hours or 0)
            review_duration_hours = float(pr.review_duration_hours or 0)

            if prediction.predicted_delay_days is not None:
                delay_features.append([
                    files_changed,
                    commit_count,
                    review_count,
                    lines_added,
                    lines_deleted,
                    review_count,
                ])
                delay_labels.append(float(prediction.predicted_delay_days))

            bottleneck_features.append([
                wait_for_review_hours,
                review_duration_hours,
                comment_count,
                commit_count,
                age_days,
            ])

            if prediction.risk_score is not None:
                risk_features.append([
                    comment_count,
                    review_count,
                    files_changed,
                    lines_added + lines_deleted,
                    0.5,
                ])
                risk_labels.append(1 if float(prediction.risk_score) >= 0.5 else 0)

            if prediction.predicted_review_wait is not None:
                review_wait_features.append([
                    review_count,
                    1.0,
                    files_changed,
                    0.0,
                    1.0,
                ])
                review_wait_labels.append(float(prediction.predicted_review_wait))

        if len(delay_features) >= min_prs:
            results["models"]["delay_prediction"] = self.train_delay_prediction(
                np.array(delay_features), np.array(delay_labels)
            )
        else:
            results["summary"].append("Delay prediction skipped: not enough training examples.")

        if len(bottleneck_features) >= min_prs:
            results["models"]["bottleneck_detection"] = self.train_bottleneck_detection(
                np.array(bottleneck_features)
            )
        else:
            results["summary"].append("Bottleneck detection skipped: not enough training examples.")

        if len(risk_features) >= min_prs:
            results["models"]["risk_score"] = self.train_risk_score(
                np.array(risk_features), np.array(risk_labels)
            )
        else:
            results["summary"].append("Risk score training skipped: not enough training examples.")

        if len(review_wait_features) >= min_prs:
            results["models"]["review_wait_prediction"] = self.train_review_wait_prediction(
                np.array(review_wait_features), np.array(review_wait_labels)
            )
        else:
            results["summary"].append("Review wait training skipped: not enough training examples.")

        contributors_result = await db.execute(select(Contributor))
        contributors = contributors_result.scalars().all()
        if len(contributors) >= min_contributors:
            contributor_features = [
                [
                    float(c.merged_prs or 0),
                    float(c.avg_cycle_time or 0),
                    float(c.avg_review_time or 0),
                    float(c.stale_pr_count or 0),
                ]
                for c in contributors
            ]
            results["models"]["contributor_segmentation"] = self.train_contributor_segmentation(
                np.array(contributor_features), n_clusters=min(5, len(contributors))
            )
        else:
            results["summary"].append(
                f"Contributor segmentation skipped: need at least {min_contributors} contributors, found {len(contributors)}."
            )

        trained_count = sum(1 for value in results["models"].values() if value)
        results["trained"] = trained_count > 0
        results["summary"].append(f"Trained {trained_count} model(s).")
        return results

    def _model_path(self, filename: str) -> Path:
        """Return absolute path for a trained model file."""
        return self.models_dir / filename

    def _save_model(self, model, filename: str) -> bool:
        """Save a trained model to disk with error handling."""
        path = self._model_path(filename)
        try:
            with open(path, 'wb') as f:
                pickle.dump(model, f)
            print(f"[ML] Model saved: {path}", flush=True)
            return True
        except Exception as exc:
            print(f"[ML ERROR] Failed to save model {filename}: {exc}", flush=True)
            return False

    def _load_model(self, filename: str):
        """Load a trained model from disk safely."""
        path = self._model_path(filename)
        if not path.exists():
            print(f"[ML] Model not found: {path}", flush=True)
            return None

        try:
            with open(path, 'rb') as f:
                model = pickle.load(f)
            print(f"[ML] Model loaded: {path}", flush=True)
            return model
        except Exception as exc:
            print(f"[ML ERROR] Failed to load model {filename}: {exc}", flush=True)
            return None
