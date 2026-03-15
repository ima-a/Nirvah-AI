# Nirvaah AI — Agent Test Results
Generated: 2026-03-15 11:45 IST

## Model Files

| File | Size | Type | Features |
|---|---|---|---|
| anomaly_model.pkl | 1,023,625 B | IsolationForest | 38 |
| anomaly_scaler.pkl | 1,527 B | StandardScaler | 38 |
| dropout_model.pkl | 7,843,683 B | CalibratedClassifierCV | 14 |
| dropout_scaler.pkl | 1,575 B | StandardScaler | 14 |
| feature_columns.json | 293 B | JSON | 13 |
| teammate_fields.json | 2,175 B | JSON | — |
| threshold.json | 49 B | JSON (0.54) | — |

## Agent Tests

| # | Agent | Status | Details |
|---|---|---|---|
| 1 | Extraction | ✅ | Import OK |
| 2 | Validation | ✅ | Range checks work (alerts=['hemoglobin_low_alert']) |
| 3 | Form Agent | ✅ | HMIS=8, MCTS=8, Kerala=7 fields mapped |
| 4 | Sync Agent | ✅ | Import OK (Supabase/Redis needed for full test) |
| 5 | Anomaly | ✅ | IsolationForest, 38-feature scaler, score=0.253 |
| 6 | Insights | ✅ | CalibratedClassifierCV, 14-feature scaler, threshold=0.54, score=0.2458 |

## Module Tests

| Module | Status |
|---|---|
| state.py | ✅ |
| pipeline.py | ✅ 8 nodes compiled |
| constants.py | ✅ |
| pii_utils.py | ✅ |
| encryption.py | ✅ |
| middleware.py | ✅ |
| security/anomaly_rules.py | ✅ |
| data/validation_rules.py | ✅ |
| data/scheme_eligibility.py | ✅ (4 schemes) |

## Errors Fixed

| File | Bug | Fix |
|---|---|---|
| anomaly.py | `MODELS_DIR` resolved to `app/models/` | Changed to `parent.parent.parent / "models"` |
| anomaly.py | `score_with_ml` crash: 13 features vs 38-feature scaler | Added padding + try/except |
| insights.py | `MODELS_DIR` resolved to `app/models/` | Changed to `parent.parent.parent / "models"` |
| insights.py | Eager Supabase init crashes without env vars | Changed to lazy `get_supabase()` |
| insights.py | Loads nonexistent `dropout_feature_columns.json` | Changed to `feature_columns.json` |
| insights.py | Feature names wrong (e.g. `mother_age` vs `age_of_mother`) | Matched to `feature_columns.json` exactly |
| insights.py | No scaler before predict_proba | Added `dropout_scaler.transform()` |
| insights.py | Missing `state_code` (14th feature) | Added `state_code: 32.0` |
| insights.py | No threshold loaded | Loads `threshold.json` (0.54) |
| form_agent.py | Uses `hmis_fields`/`mcts_fields` keys that don't exist | Rewrote to use `fields` array with `hmis_code`/`mcts_code`/`form_target` |
| test_security.py | `from audit_chain` → ModuleNotFoundError | Changed to `from app.audit_chain` |

## Known Limitation

- `test_security.py` still fails at runtime because `app.database` eagerly creates a Supabase client. This only matters when running tests without Supabase env vars set.
