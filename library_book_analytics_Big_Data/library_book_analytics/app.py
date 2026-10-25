from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

try:
    from hdfs import InsecureClient
except ImportError:
    InsecureClient = None  # HDFS is optional for local development.


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_FILE = DATA_DIR / "library_records.csv"
DATA_DIR.mkdir(exist_ok=True)

REQUIRED_COLUMNS = [
    "record_id",
    "book_id",
    "book_title",
    "category",
    "student_id",
    "borrow_date",
]
HDFS_URL = os.getenv("HDFS_URL", "http://localhost:9870")
HDFS_USER = os.getenv("HDFS_USER", "hadoop")
HDFS_DIRECTORY = os.getenv("HDFS_DIRECTORY", "/library_book_analytics")


def read_dataset(source: str | Path | Any = DATA_FILE) -> pd.DataFrame:
    """Read and validate the library borrowing CSV."""
    frame = pd.read_csv(source, dtype=str, keep_default_na=False)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    frame = frame[REQUIRED_COLUMNS].copy()
    for column in REQUIRED_COLUMNS:
        frame[column] = frame[column].astype(str).str.strip()
        if frame[column].eq("").any():
            raise ValueError(f"Column '{column}' cannot contain blank values.")

    parsed_dates = pd.to_datetime(frame["borrow_date"], errors="coerce", format="mixed")
    if parsed_dates.isna().any():
        raise ValueError("Every borrow_date must be a valid date, such as 2026-01-05.")
    frame["borrow_date"] = parsed_dates.dt.strftime("%Y-%m-%d")
    return frame


def hdfs_client():
    if InsecureClient is None:
        return None
    return InsecureClient(HDFS_URL, user=HDFS_USER)


def build_analytics(frame: pd.DataFrame) -> dict[str, Any]:
    category_counts = frame["category"].value_counts().sort_index()
    monthly_counts = (
        pd.to_datetime(frame["borrow_date"])
        .dt.to_period("M")
        .value_counts()
        .sort_index()
    )
    popular = (
        frame.groupby(["book_id", "book_title"], as_index=False)
        .size()
        .rename(columns={"size": "borrow_count"})
        .sort_values(["borrow_count", "book_title"], ascending=[False, True])
    )

    return {
        "total_records": int(len(frame)),
        "unique_books": int(frame["book_id"].nunique()),
        "unique_students": int(frame["student_id"].nunique()),
        "unique_categories": int(frame["category"].nunique()),
        "categories": {
            "labels": category_counts.index.tolist(),
            "values": [int(value) for value in category_counts.tolist()],
        },
        "monthly": {
            "labels": [period.strftime("%b %Y") for period in monthly_counts.index],
            "values": [int(value) for value in monthly_counts.tolist()],
        },
        "popular_books": popular.to_dict(orient="records"),
        "records": frame.to_dict(orient="records"),
    }


@app.get("/")
def dashboard():
    return render_template("index.html")


@app.get("/api/analytics")
def analytics():
    try:
        return jsonify(build_analytics(read_dataset()))
    except (OSError, pd.errors.ParserError, ValueError) as error:
        app.logger.exception("Unable to build analytics")
        return jsonify(error=f"Could not read the library dataset: {error}"), 500


@app.get("/api/status")
def status():
    client = hdfs_client()
    if client is None:
        return jsonify(
            storage="Local CSV",
            hdfs_status="HDFS Python client is not installed",
            hdfs_directory=HDFS_DIRECTORY,
        )
    try:
        client.status(HDFS_DIRECTORY, strict=False)
        return jsonify(
            storage="Local CSV + HDFS available",
            hdfs_status=f"Connected to {HDFS_URL}",
            hdfs_directory=HDFS_DIRECTORY,
        )
    except Exception as error:  # HDFS is optional and may not be running.
        return jsonify(
            storage="Local CSV",
            hdfs_status=f"HDFS unavailable: {error}",
            hdfs_directory=HDFS_DIRECTORY,
        )


@app.post("/api/upload")
def upload_dataset():
    uploaded_file = request.files.get("file")
    if uploaded_file is None or not uploaded_file.filename:
        return jsonify(error="Choose a CSV file to upload."), 400
    if Path(secure_filename(uploaded_file.filename)).suffix.lower() != ".csv":
        return jsonify(error="Only CSV files are supported."), 400

    try:
        frame = read_dataset(uploaded_file.stream)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError, ValueError) as error:
        return jsonify(error=f"Invalid CSV: {error}"), 400

    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w", suffix=".csv", encoding="utf-8", newline="", delete=False,
            dir=DATA_DIR,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            frame.to_csv(temporary_file, index=False)
        temporary_path.replace(DATA_FILE)
    except OSError:
        app.logger.exception("Unable to save uploaded dataset")
        return jsonify(error="The uploaded dataset could not be saved."), 500
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)

    hdfs_saved = False
    client = hdfs_client()
    if client is not None:
        try:
            client.makedirs(HDFS_DIRECTORY)
            client.upload(f"{HDFS_DIRECTORY}/library_records.csv", str(DATA_FILE), overwrite=True)
            hdfs_saved = True
        except Exception:
            app.logger.exception("Dataset saved locally, but HDFS upload failed")

    return jsonify(
        message=f"Uploaded and analyzed {len(frame)} borrowing records.",
        records=len(frame),
        hdfs_saved=hdfs_saved,
    )


@app.get("/api/download")
def download_dataset():
    if not DATA_FILE.exists():
        return jsonify(error="The library dataset is not available."), 404
    return send_file(DATA_FILE, mimetype="text/csv", as_attachment=True, download_name="library_records.csv")


@app.errorhandler(413)
def file_too_large(_error):
    return jsonify(error="The CSV must be 10 MB or smaller."), 413


if __name__ == "__main__":
    app.run(debug=True)
