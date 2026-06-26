"""
ETL: flat HCAHPS CSV → Snowflake star schema

Required env vars:
    SNOWFLAKE_ACCOUNT    e.g. xy12345.us-east-1
    SNOWFLAKE_USER
    SNOWFLAKE_PASSWORD
    SNOWFLAKE_DATABASE
    SNOWFLAKE_WAREHOUSE
    SNOWFLAKE_SCHEMA     (optional, default PUBLIC)

Usage:
    python etl.py
"""

import os
import sys
import pandas as pd
import sqlalchemy as sa
from sqlalchemy import text

CSV_PATH = os.getenv("CSV_PATH", "data/Health Care_Patient_survey_source.csv")

NUMERIC_COLS = [
    "Answer Percent",
    "Linear Mean Value",
    "Patient Survey Star Rating",
    "Number of Completed Surveys",
    "Survey Response Rate Percent",
]


def snowflake_engine() -> sa.Engine:
    from snowflake.sqlalchemy import URL
    return sa.create_engine(URL(
        account   = os.environ["SNOWFLAKE_ACCOUNT"].lower(),
        user      = os.environ["SNOWFLAKE_USER"],
        password  = os.environ["SNOWFLAKE_PASSWORD"],
        database  = os.environ["SNOWFLAKE_DATABASE"],
        warehouse = os.environ["SNOWFLAKE_WAREHOUSE"],
        schema    = os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC"),
    ))


def load_csv() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH)
    df.replace("Not Applicable", pd.NA, inplace=True)
    # Only drop Answer Percent Footnote — the other footnotes go into dim/fact tables
    df.drop(columns=["Answer Percent Footnote"], errors="ignore", inplace=True)
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["Measure Start Date"] = pd.to_datetime(df["Measure Start Date"], errors="coerce")
    df["Measure End Date"]   = pd.to_datetime(df["Measure End Date"],   errors="coerce")
    return df


# ── Dimension builders ──────────────────────────────────────────────────────

def build_dim_county_details(df: pd.DataFrame) -> pd.DataFrame:
    """Unique (County Name, State, City, ZipCode) rows with a running sequence PK."""
    dim = (
        df[["County Name", "State", "City", "ZIP Code"]]
        .dropna(subset=["County Name"])
        .drop_duplicates()
        .reset_index(drop=True)
        .rename(columns={
            "County Name": "COUNTY_NAME",
            "State":       "STATE",
            "City":        "CITY",
            "ZIP Code":    "ZIPCODE",
        })
    )
    dim.insert(0, "COUNTY_ID", dim.index + 1)
    return dim


def build_dim_hospital_details(df: pd.DataFrame,
                                dim_county: pd.DataFrame) -> pd.DataFrame:
    """One row per hospital; FK to dim_county_details."""
    hospitals = (
        df[["Provider ID", "Hospital Name", "County Name", "City", "State", "ZIP Code", "Location"]]
        .drop_duplicates("Provider ID")
        .rename(columns={
            "Provider ID":   "HOSPITAL_ID",
            "Hospital Name": "HOSPITAL_NAME",
            "City":          "CITY",
            "Location":      "LOCATION",
        })
    )
    hospitals = hospitals.merge(
        dim_county[["COUNTY_ID", "COUNTY_NAME", "STATE", "CITY", "ZIPCODE"]],
        left_on=["County Name", "State", "CITY", "ZIP Code"],
        right_on=["COUNTY_NAME", "STATE", "CITY", "ZIPCODE"],
        how="left",
    )
    return hospitals[["HOSPITAL_ID", "COUNTY_ID", "HOSPITAL_NAME", "CITY", "LOCATION"]]


def build_dim_measure_details(df: pd.DataFrame) -> pd.DataFrame:
    """One row per Measure ID with its survey period dates."""
    return (
        df[["Measure ID", "Measure Start Date", "Measure End Date"]]
        .drop_duplicates("Measure ID")
        .rename(columns={
            "Measure ID":         "MEASURE_ID",
            "Measure Start Date": "MEASURE_START_DATE",
            "Measure End Date":   "MEASURE_END_DATE",
        })
    )


def build_dim_survey_details(df: pd.DataFrame) -> pd.DataFrame:
    """Unique (Question, Answer, Footnote) combinations with a running sequence PK."""
    dim = (
        df[["Question", "Answer Description", "Patient Survey Star Rating Footnote"]]
        .drop_duplicates()
        .reset_index(drop=True)
        .rename(columns={
            "Question":                            "SURVEY_QUESTION",
            "Answer Description":                  "SURVEY_ANSWER",
            "Patient Survey Star Rating Footnote": "PATIENT_SURVEY_STAR_RATING_FOOTNOTE",
        })
    )
    dim.insert(0, "SURVEY_ID", dim.index + 1)
    return dim


def build_fact(df: pd.DataFrame,
               dim_county: pd.DataFrame,
               dim_survey: pd.DataFrame) -> pd.DataFrame:
    """Join all dimension FKs onto each raw row."""
    fact = df.merge(
        dim_county[["COUNTY_ID", "COUNTY_NAME", "STATE", "CITY", "ZIPCODE"]],
        left_on=["County Name", "State", "City", "ZIP Code"],
        right_on=["COUNTY_NAME", "STATE", "CITY", "ZIPCODE"],
        how="left",
    )
    fact = fact.merge(
        dim_survey[["SURVEY_ID", "SURVEY_QUESTION", "SURVEY_ANSWER",
                    "PATIENT_SURVEY_STAR_RATING_FOOTNOTE"]],
        left_on=["Question", "Answer Description",
                 "Patient Survey Star Rating Footnote"],
        right_on=["SURVEY_QUESTION", "SURVEY_ANSWER",
                  "PATIENT_SURVEY_STAR_RATING_FOOTNOTE"],
        how="left",
    )
    return fact[[
        "COUNTY_ID",
        "Provider ID",
        "Measure ID",
        "SURVEY_ID",
        "Number of Completed Surveys",
        "Number of Completed Surveys Footnote",
        "Survey Response Rate Percent",
        "Survey Response Rate Percent Footnote",
        "Linear Mean Value",
        "Answer Percent",
        "Patient Survey Star Rating",
    ]].rename(columns={
        "Provider ID":                             "HOSPITAL_ID",
        "Measure ID":                              "MEASURE_ID",
        "Number of Completed Surveys":             "NO_COMPLETED_SURVEYS",
        "Number of Completed Surveys Footnote":    "NO_COMPLETED_SURVEYS_FOOTNOTE",
        "Survey Response Rate Percent":            "SURVEY_RESPONSE_RATE_PERCENT",
        "Survey Response Rate Percent Footnote":   "SURVEY_RESPONSE_FOOTNOTE_PERCENT",
        "Linear Mean Value":                       "LINEAR_MEAN_VALUE",
        "Answer Percent":                          "ANSWER_PERCENT",
        "Patient Survey Star Rating":              "PATIENT_SURVEY_STAR_RATING",
    })


# ── Load helpers ────────────────────────────────────────────────────────────

def truncate_and_load(df: pd.DataFrame, table: str, engine: sa.Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE IF EXISTS {table}"))
    df.to_sql(table.lower(), engine, if_exists="append", index=False,
              method="multi", chunksize=2000)
    print(f"  {table}: {len(df):,} rows loaded")


def run_schema(engine: sa.Engine) -> None:
    database = os.environ["SNOWFLAKE_DATABASE"]
    schema   = os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC")
    with open("schema.sql") as f:
        lines = [l for l in f if not l.strip().startswith("--")]
    statements = [s.strip() for s in "".join(lines).split(";") if s.strip()]
    with engine.begin() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {database}"))
        conn.execute(text(f"USE DATABASE {database}"))
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        conn.execute(text(f"USE SCHEMA {schema}"))
        for stmt in statements:
            conn.execute(text(stmt))


# ── Entry point ─────────────────────────────────────────────────────────────

def main() -> None:
    required = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD",
                "SNOWFLAKE_DATABASE", "SNOWFLAKE_WAREHOUSE"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"ERROR: missing env vars: {', '.join(missing)}")
        sys.exit(1)

    print("Loading CSV...")
    df = load_csv()
    print(f"  {len(df):,} rows")

    print("Connecting to Snowflake...")
    engine = snowflake_engine()

    print("Applying schema...")
    run_schema(engine)

    print("Building dimension tables...")
    dim_county   = build_dim_county_details(df)
    dim_hospital = build_dim_hospital_details(df, dim_county)
    dim_measure  = build_dim_measure_details(df)
    dim_survey   = build_dim_survey_details(df)
    fact         = build_fact(df, dim_county, dim_survey)

    print("Loading dimension tables...")
    truncate_and_load(dim_county,   "DIM_COUNTY_DETAILS",   engine)
    truncate_and_load(dim_hospital, "DIM_HOSPITAL_DETAILS", engine)
    truncate_and_load(dim_measure,  "DIM_MEASURE_DETAILS",  engine)
    truncate_and_load(dim_survey,   "DIM_SURVEY_DETAILS",   engine)

    print("Loading fact table...")
    truncate_and_load(fact, "FACT_SURVEY_RESPONSE", engine)

    print("ETL complete.")


if __name__ == "__main__":
    main()
