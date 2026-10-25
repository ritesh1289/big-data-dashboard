# Library Book Usage Analytics

A Flask dashboard for analyzing fictional library borrowing activity. It calculates book popularity, category counts, monthly borrowing trends, and unique student counts from a CSV file. CSV upload/download is supported, and uploads can optionally be copied to Hadoop HDFS.

## Features

- Summary cards for borrowing records, distinct books, students, and categories
- Category and monthly trend charts
- Popular book ranking and searchable borrowing history
- CSV validation and dataset upload/download
- Optional HDFS storage integration with graceful local-only operation

## Project structure

```text
library_book_analytics/
├── app.py
├── requirements.txt
├── README.md
├── data/library_records.csv
├── templates/index.html
└── static/
    ├── style.css
    └── script.js
```

## Run locally

Python 3.10 or newer is recommended.

1. From this directory, create and activate a virtual environment.
2. Install packages: `pip install -r requirements.txt`.
3. Start the development server: `python app.py`.
4. Visit `http://127.0.0.1:5000`.

The dashboard uses `data/library_records.csv`. The included 20 borrowing records are fictional and contain no real student information.

## CSV format

Uploads must include these columns (extra columns are ignored):

`record_id, book_id, book_title, category, student_id, borrow_date`

All fields must be nonempty, and `borrow_date` must contain a valid date. Maximum upload size is 10 MB. A successfully validated upload replaces the local CSV dataset.

## Optional HDFS

The dashboard works without Hadoop and reports local CSV storage. To enable HDFS uploads, make sure the NameNode WebHDFS endpoint is reachable, then configure these environment variables as needed:

- `HDFS_URL` — defaults to `http://localhost:9870`
- `HDFS_USER` — defaults to `hadoop`
- `HDFS_DIRECTORY` — defaults to `/library_book_analytics`

Uploaded datasets are copied to `<HDFS_DIRECTORY>/library_records.csv`. The `hdfs` Python package is installed by the requirements file; no HDFS server is included with this project.

> This sample dashboard includes student IDs from fictional records only. Do not upload identifiable borrower data to an unsecured development server.
