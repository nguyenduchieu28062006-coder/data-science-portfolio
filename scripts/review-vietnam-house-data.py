"""Read public dataset metadata/statistics for source review only; never train.

Run: python scripts/review-vietnam-house-data.py
No listings are scraped, downloaded, cleaned, synthesized, or modified.
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DATASET = "tinixai/vietnam-real-estates"
SOURCES = {
    "metadata": f"https://huggingface.co/api/datasets/{DATASET}",
    "info": "https://datasets-server.huggingface.co/info?dataset=tinixai%2Fvietnam-real-estates",
    "statistics": "https://datasets-server.huggingface.co/statistics?dataset=tinixai%2Fvietnam-real-estates&config=default&split=train",
}


def fetch(url):
    with urlopen(url, timeout=30) as response:
        return response.read()


def main():
    raw = {key: fetch(url) for key, url in SOURCES.items()}
    metadata, info, statistics = (json.loads(raw[key]) for key in SOURCES)
    revision = metadata["sha"]
    readme_url = f"https://huggingface.co/datasets/{DATASET}/raw/{revision}/README.md"
    readme_raw = fetch(readme_url)
    readme = readme_raw.decode("utf-8")
    date_range = re.search(r"\*\*Time Range\*\*\s*\|\s*(\d{4}-\d{2}-\d{2})\s*→\s*(\d{4}-\d{2}-\d{2})", readme)
    if not date_range:
        raise RuntimeError("Dataset date range is missing; do not infer it from upload dates.")
    dataset_info = info["dataset_info"]["default"]
    rows = dataset_info["splits"]["train"]["num_examples"]
    if statistics.get("partial") or info.get("partial") or statistics["num_examples"] != rows:
        raise RuntimeError("Incomplete or inconsistent statistics; review manually.")
    fields = list(dataset_info["features"])
    stats = {
        column["column_name"]: {
            key: value for key, value in column["column_statistics"].items()
            if key in ("nan_count", "nan_proportion", "n_unique", "min", "max") or
            (key == "frequencies" and column["column_name"] in ("province_name", "property_type_name"))
        }
        for column in statistics["statistics"]
    }
    # Recheck upstream revision to avoid combining metadata from different releases.
    if json.loads(fetch(SOURCES["metadata"]))["sha"] != revision:
        raise RuntimeError("Dataset changed during review; rerun before using this evidence.")
    evidence = {
        "review_date_local": datetime.now(timezone(timedelta(hours=7))).date().isoformat(),
        "timezone": "Asia/Saigon",
        "stage": "source_review_only",
        "dataset": DATASET,
        "revision": revision,
        "repository_last_modified": metadata["lastModified"],
        "license_declared_by_publisher": metadata["cardData"]["license"],
        "data_start_date_declared_by_publisher": date_range[1],
        "data_end_date_declared_by_publisher": date_range[2],
        "dates_independently_scanned_from_all_listings": False,
        "raw_rows_reported_by_dataset_server": rows,
        "download_size_bytes": dataset_info["download_size"],
        "fields": fields,
        "column_statistics": stats,
        "missing_required_structured_fields": ["listing_type", "sale_or_rent", "currency", "price_period", "legal_status", "listing_id", "source_url", "latitude", "longitude"],
        "sources": {**SOURCES, "versioned_readme": readme_url},
        "response_sha256": {**{key: hashlib.sha256(value).hexdigest() for key, value in raw.items()}, "readme": hashlib.sha256(readme_raw).hexdigest()},
        "training_performed": False,
    }
    output = ROOT / "docs" / "vietnam-house-price-source-evidence.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence": str(output), "revision": revision, "rows": rows, "provinces": len(stats["province_name"]["frequencies"]), "property_types": stats["property_type_name"]["frequencies"], "date_source": "publisher README, not upload date"}, ensure_ascii=True))


if __name__ == "__main__":
    main()
