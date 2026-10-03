"""Train Cleveland Logistic Regression and export browser-readable parameters.

Run: python train-health-model.py
Only the training partition is used to fit medians, scaler, and classifier.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import pandas as pd
import sklearn
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score, roc_auc_score,
    confusion_matrix, roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent
SOURCE_URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/processed.cleveland.data"
FEATURES = [
    "age", "sex", "cp", "trestbps", "chol", "fbs", "restecg",
    "thalach", "exang", "oldpeak", "slope", "ca", "thal",
]
CATEGORY_CODES = {
    "sex": [0, 1], "cp": [1, 2, 3, 4], "fbs": [0, 1],
    "restecg": [0, 1, 2], "exang": [0, 1], "slope": [1, 2, 3],
    "ca": [0, 1, 2, 3], "thal": [3, 6, 7],
}


def load_dataset(path):
    if not path.exists():
        print(f"Downloading the original processed Cleveland dataset: {SOURCE_URL}")
        with urlopen(SOURCE_URL, timeout=60) as response:
            raw = response.read()
        frame = pd.read_csv(io.BytesIO(raw), header=None, names=FEATURES + ["target"], na_values=["?"])
        if frame.shape != (303, 14):
            raise ValueError("Unexpected Cleveland dataset shape; expected 303 rows and 14 columns.")
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False, na_rep="?")
    frame = pd.read_csv(path, na_values=["?", "", "NA", "N/A", "None", "null", "nan"])
    if set(frame.columns) != set(FEATURES + ["target"]):
        raise ValueError("CSV must contain the 13 Cleveland features and target.")
    frame = frame[FEATURES + ["target"]].apply(pd.to_numeric, errors="raise")
    if frame["target"].isna().any() or not frame["target"].isin([0, 1, 2, 3, 4]).all():
        raise ValueError("Target must contain only 0–4, with no missing labels.")
    if np.isinf(frame.to_numpy()).any() or frame[FEATURES].isna().all().any():
        raise ValueError("Features must not contain infinity or entirely missing columns.")
    for feature, codes in CATEGORY_CODES.items():
        if not frame[feature].dropna().isin(codes).all():
            raise ValueError(f"Invalid original Cleveland coding for {feature}: expected {codes}.")
    return frame


def train(dataset_path, output_path):
    frame = load_dataset(dataset_path)
    x = frame[FEATURES]
    y = (frame["target"] > 0).astype(int)
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, random_state=42, stratify=y,
    )
    pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(random_state=42, max_iter=2000)),
    ])
    pipeline.fit(x_train, y_train)
    probability = pipeline.predict_proba(x_test)[:, 1]
    prediction = (probability >= 0.5).astype(int)
    metrics = {
        "accuracy": float(accuracy_score(y_test, prediction)),
        "precision": float(precision_score(y_test, prediction, zero_division=0)),
        "recall": float(recall_score(y_test, prediction, zero_division=0)),
        "f1": float(f1_score(y_test, prediction, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, probability)),
    }
    imputer = pipeline.named_steps["imputer"]
    scaler = pipeline.named_steps["scaler"]
    classifier = pipeline.named_steps["classifier"]
    # Check that exported arithmetic exactly matches sklearn, including missing input.
    verification = pd.concat([x_test, pd.DataFrame([[np.nan] * len(FEATURES)], columns=FEATURES)])
    filled = verification.fillna(dict(zip(FEATURES, imputer.statistics_))).to_numpy()
    linear = ((filled - scaler.mean_) / scaler.scale_) @ classifier.coef_[0] + classifier.intercept_[0]
    exported_probability = np.exp(-np.logaddexp(0, -linear))
    np.testing.assert_allclose(exported_probability, pipeline.predict_proba(verification)[:, 1], atol=1e-12, rtol=1e-12)
    model = {
        "schema_version": 1,
        "model": "Logistic Regression",
        "dataset": "UCI Cleveland Heart Disease",
        "features": FEATURES,
        "medians": dict(zip(FEATURES, imputer.statistics_.tolist())),
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "coefficients": classifier.coef_[0].tolist(),
        "intercept": float(classifier.intercept_[0]),
        "metrics": metrics,
        "threshold": 0.5,
        "positive_class": "Original target > 0",
        "category_codes": CATEGORY_CODES,
        "training": {
            "random_state": 42, "test_size": 0.2, "stratified": True,
            "rows": len(frame), "train_rows": len(x_train), "test_rows": len(x_test),
            "imputation": "Median fitted on training partition only",
            "sklearn_version": sklearn.__version__,
            "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        },
        "source": {
            "url": SOURCE_URL,
            "citation": "Janosi, Steinbrunn, Pfisterer & Detrano (1989). Heart Disease. UCI Machine Learning Repository.",
            "doi": "https://doi.org/10.24432/C52P4X",
            "license": "CC BY 4.0",
        },
    }
    model.update(evaluation_data(y_test, probability, model["threshold"]))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(model, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Trained on {len(x_train)} rows; evaluated on {len(x_test)} held-out rows.")
    for name, value in metrics.items():
        print(f"{name}: {value:.6f}")
    print(f"Exported: {output_path}")


def evaluation_data(labels, probability, threshold):
    fpr, tpr, _ = roc_curve(labels, probability)
    return {
        "confusion_matrix": confusion_matrix(labels, probability >= threshold, labels=[0, 1]).tolist(),
        "roc_curve": {"fpr": fpr.tolist(), "tpr": tpr.tolist()},
    }


def export_evaluation(dataset_path, output_path):
    """Add holdout charts from existing parameters without fitting any model."""
    model = json.loads(output_path.read_text(encoding="utf-8"))
    checksum = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    if checksum != model["training"]["dataset_sha256"]:
        raise ValueError("Dataset checksum differs from the model's original training data.")
    frame = load_dataset(dataset_path)
    features = model["features"]
    y = (frame["target"] > 0).astype(int)
    _, x_test, _, y_test = train_test_split(
        frame[features], y, test_size=model["training"]["test_size"],
        random_state=model["training"]["random_state"], stratify=y,
    )
    filled = x_test.fillna(model["medians"]).to_numpy()
    linear = ((filled - np.array(model["scaler_mean"])) / np.array(model["scaler_scale"])) @ np.array(model["coefficients"]) + model["intercept"]
    probability = np.exp(-np.logaddexp(0, -linear))
    predicted = probability >= model["threshold"]
    measured = {
        "accuracy": accuracy_score(y_test, predicted),
        "precision": precision_score(y_test, predicted, zero_division=0),
        "recall": recall_score(y_test, predicted, zero_division=0),
        "f1": f1_score(y_test, predicted, zero_division=0),
        "roc_auc": roc_auc_score(y_test, probability),
    }
    for name, value in measured.items():
        if not np.isclose(value, model["metrics"][name], rtol=0, atol=1e-12):
            raise ValueError(f"Holdout metric {name} does not match the existing model.")
    model.update(evaluation_data(y_test, probability, model["threshold"]))
    output_path.write_text(json.dumps(model, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print("Added confusion matrix and ROC from the existing model. No training performed.")
    print("Confusion matrix (rows = actual, columns = predicted):", model["confusion_matrix"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "heart.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "health-model.json")
    parser.add_argument("--evaluation-only", action="store_true", help="Add evaluation charts without retraining or changing model parameters.")
    args = parser.parse_args()
    if args.evaluation_only:
        export_evaluation(args.data, args.output)
    else:
        train(args.data, args.output)
