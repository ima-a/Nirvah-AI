"""
scripts/train_dropout_model.py — Train the XGBoost dropout prediction model.

Generates synthetic data based on Kerala NFHS-5 published statistics
(or loads real NFHS-5 individual data if available).

Trains an XGBClassifier and saves model files to models/.

Run with:
    python scripts/train_dropout_model.py
"""

import sys
from pathlib import Path

# Ensure nirvaah-backend/ is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score
from xgboost import XGBClassifier
import joblib

MODELS_DIR = Path(__file__).parent.parent / "models"


def generate_synthetic_data(n=2000) -> pd.DataFrame:
    """
    Generate synthetic training data resembling Kerala NFHS-5 patterns.
    
    Each row represents one beneficiary with features that influence
    ANC dropout probability. The dropout label is generated using
    realistic Kerala risk factor weights.
    """
    np.random.seed(42)

    # --- Feature generation ---
    mother_age = np.random.uniform(18, 40, n)

    parity = np.random.choice(
        [0, 1, 2, 3],
        size=n,
        p=[0.35, 0.35, 0.20, 0.10]
    ).astype(float)

    gestational_age_first_anc = np.random.uniform(6, 20, n)

    hemoglobin = np.clip(
        np.random.normal(10.8, 1.4, n),
        5, 15
    )

    distance_to_phc_km = np.clip(
        np.random.exponential(4, n),
        0.5, 30
    )

    anc_visits_completed = np.random.choice(
        [0, 1, 2, 3, 4],
        size=n,
        p=[0.05, 0.15, 0.25, 0.30, 0.25]
    ).astype(float)

    ifa_tablets_total = np.clip(
        np.random.normal(60, 30, n),
        0, 90
    )

    scheme_enrolled = np.random.binomial(1, 0.55, n).astype(float)

    previous_institutional_delivery = np.random.binomial(1, 0.90, n).astype(float)

    bpl_card = np.random.binomial(1, 0.30, n).astype(float)

    # --- Dropout label logic ---
    # Base dropout probability: 0.20 (Kerala ANC4+ coverage is ~80%)
    dropout_prob = np.full(n, 0.20)

    # Risk factor adjustments
    dropout_prob += 0.15 * (hemoglobin < 10.0)
    dropout_prob += 0.12 * (distance_to_phc_km > 10)
    dropout_prob += 0.10 * (gestational_age_first_anc > 16)
    dropout_prob += 0.10 * (scheme_enrolled == 0)
    dropout_prob += 0.08 * (mother_age < 20)
    dropout_prob += 0.08 * (anc_visits_completed < 2)
    dropout_prob -= 0.05 * (previous_institutional_delivery == 1)

    # Clip to realistic range
    dropout_prob = np.clip(dropout_prob, 0.05, 0.85)

    # Generate binary labels
    dropout = np.random.binomial(1, dropout_prob)

    # Build DataFrame
    df = pd.DataFrame({
        "mother_age": mother_age,
        "parity": parity,
        "gestational_age_first_anc": gestational_age_first_anc,
        "hemoglobin": hemoglobin,
        "distance_to_phc_km": distance_to_phc_km,
        "anc_visits_completed": anc_visits_completed,
        "ifa_tablets_total": ifa_tablets_total,
        "scheme_enrolled": scheme_enrolled,
        "previous_institutional_delivery": previous_institutional_delivery,
        "bpl_card": bpl_card,
        "dropout": dropout
    })

    return df


def main():
    print("=" * 60)
    print("Nirvaah AI — Dropout Prediction Model Training")
    print("=" * 60)

    # Step 1: Generate synthetic data
    print("Generating 2000 synthetic training rows (Kerala NFHS-5 patterns)...")
    df = generate_synthetic_data(n=2000)

    dropout_rate = df["dropout"].mean()
    print(f"Dropout rate in synthetic data: {dropout_rate:.1%}")

    # Step 2: Split features and labels
    feature_columns = [
        "mother_age",
        "parity",
        "gestational_age_first_anc",
        "hemoglobin",
        "distance_to_phc_km",
        "anc_visits_completed",
        "ifa_tablets_total",
        "scheme_enrolled",
        "previous_institutional_delivery",
        "bpl_card"
    ]

    X = df[feature_columns]
    y = df["dropout"]

    # Step 3: Train/test split (80/20)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42
    )
    print(f"Training samples: {len(X_train)}, Test samples: {len(X_test)}")

    # Step 4: Train XGBoost model
    model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
        eval_metric="logloss",
        use_label_encoder=False
    )
    model.fit(X_train, y_train)
    print("XGBClassifier trained: n_estimators=100, max_depth=4")

    # Step 5: Evaluate on test set
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    accuracy = accuracy_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_proba)

    print(f"\nTest set accuracy: {accuracy:.4f}")
    print(f"Test set AUC:      {auc:.4f}")

    if accuracy > 0.70:
        print("✓ Accuracy target met (> 0.70)")
    else:
        print("✗ Accuracy below target (< 0.70)")

    if auc > 0.75:
        print("✓ AUC target met (> 0.75)")
    else:
        print("✗ AUC below target (< 0.75)")

    # Step 6: Save model and feature columns
    MODELS_DIR.mkdir(exist_ok=True)

    joblib.dump(model, MODELS_DIR / "dropout_model.pkl")
    print(f"\nModel saved to {MODELS_DIR / 'dropout_model.pkl'}")

    with open(MODELS_DIR / "dropout_feature_columns.json", "w") as f:
        json.dump(list(X_train.columns), f)
    print(f"Feature columns saved to {MODELS_DIR / 'dropout_feature_columns.json'}")

    # Step 7: Feature importance
    print("\nFeature importance:")
    for name, importance in sorted(
        zip(feature_columns, model.feature_importances_),
        key=lambda x: x[1],
        reverse=True
    ):
        print(f"  {name:40s} {importance:.4f}")

    print("\n" + "=" * 60)
    print("Training complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
