"""
scripts/train_anomaly_model.py — Train the Isolation Forest anomaly model.

Generates synthetic data (or loads real HMIS data from data/hmis_data.csv),
trains a StandardScaler + IsolationForest, and saves model files to models/.

Run with:
    cd nirvaah/nirvaah-backend
    python scripts/train_anomaly_model.py
"""

import sys
from pathlib import Path

# Ensure nirvaah-backend/ is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib

MODELS_DIR = Path(__file__).parent.parent / "models"
DATA_PATH = Path(__file__).parent.parent / "data" / "hmis_data.csv"

FEATURE_COLUMNS = [
    "records_per_day",
    "avg_records_per_hour",
    "stddev_bp_systolic",
    "stddev_hemoglobin",
    "unique_beneficiaries_ratio"
]


def generate_synthetic_data(n_normal=1000, n_anomalous=50) -> pd.DataFrame:
    """Generate synthetic training data resembling real ASHA submission patterns."""
    np.random.seed(42)

    # Normal rows
    normal = pd.DataFrame({
        "records_per_day": np.clip(np.random.normal(8, 3, n_normal), 1, 30),
        "avg_records_per_hour": np.clip(np.random.normal(1.2, 0.4, n_normal), 0.1, 5),
        "stddev_bp_systolic": np.clip(np.random.normal(12, 4, n_normal), 1, 40),
        "stddev_hemoglobin": np.clip(np.random.normal(1.2, 0.4, n_normal), 0.1, 5),
        "unique_beneficiaries_ratio": np.clip(np.random.normal(0.92, 0.06, n_normal), 0.5, 1.0),
    })

    # Obviously anomalous rows
    anomalous = pd.DataFrame({
        "records_per_day": np.random.uniform(25, 30, n_anomalous),
        "avg_records_per_hour": np.random.uniform(4, 5, n_anomalous),
        "stddev_bp_systolic": np.random.uniform(0.5, 1.0, n_anomalous),
        "stddev_hemoglobin": np.random.uniform(0.05, 0.1, n_anomalous),
        "unique_beneficiaries_ratio": np.random.uniform(0.3, 0.5, n_anomalous),
    })

    return pd.concat([normal, anomalous], ignore_index=True)


def main():
    print("=" * 60)
    print("Nirvaah AI — Anomaly Model Training")
    print("=" * 60)

    # Step 1: Load or generate data
    if DATA_PATH.exists():
        print(f"Loading real HMIS data from {DATA_PATH}")
        df = pd.read_csv(DATA_PATH)
        # Ensure required columns exist
        for col in FEATURE_COLUMNS:
            if col not in df.columns:
                print(f"WARNING: Column '{col}' missing, generating synthetic data instead")
                df = generate_synthetic_data()
                break
    else:
        print("No real data found — generating 1050 synthetic training rows")
        df = generate_synthetic_data()

    X = df[FEATURE_COLUMNS]
    print(f"Training samples: {len(X)}")

    # Step 2: Train StandardScaler
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Step 3: Train IsolationForest
    model = IsolationForest(
        contamination=0.05,   # expect ~5% anomalous
        random_state=42,      # reproducibility
        n_estimators=100
    )
    model.fit(X_scaled)
    print(f"IsolationForest trained: contamination=0.05, n_estimators=100")

    # Step 4: Save model files
    MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump(model, MODELS_DIR / "anomaly_model.pkl")
    joblib.dump(scaler, MODELS_DIR / "anomaly_scaler.pkl")
    with open(MODELS_DIR / "feature_columns.json", "w") as f:
        json.dump(FEATURE_COLUMNS, f)
    print(f"Model files saved to {MODELS_DIR}/")

    # Step 5: Sanity check — score the anomalous rows
    anomalous_X = X_scaled[-50:]  # last 50 rows are the injected anomalies
    predictions = model.predict(anomalous_X)
    anomaly_count = sum(1 for p in predictions if p == -1)
    print(f"\nSanity check: {anomaly_count}/50 injected anomalies detected as anomalous")

    scores = model.decision_function(anomalous_X)
    print(f"Anomaly scores range: [{scores.min():.4f}, {scores.max():.4f}]")
    print(f"Mean anomaly score: {scores.mean():.4f}")

    print("\n" + "=" * 60)
    print("Training complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
