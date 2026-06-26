# Healthcare Patient Survey Analysis

An interactive Streamlit dashboard that explores HCAHPS (Hospital Consumer Assessment of Healthcare Providers and Systems) patient survey data across **619 hospitals** and **7 states**. The app surfaces care quality trends, response rate patterns, hospital benchmarks, and computed statistical insights through a series of filterable, drill-down charts.

---

## Features

| Section | What it shows |
|---|---|
| **Dataset Overview** | KPI metrics — total surveys, hospitals, best response rate, top city & state |
| **Surveys by Hospital** | Completed survey counts per hospital, switchable Bar / Scatter |
| **Response Rate by Measure** | Strip plot of response rate distribution across all HCAHPS measure IDs |
| **Top 3 Counties** | Counties with the highest average survey response rate |
| **Top 10 Hospitals** | Hospitals ranked by average survey response rate |
| **County & City Drill-down** | Treemap + bar chart — drill from state → county → city → hospital star rating |
| **Hospitals in Same City** | Cities sharing multiple hospitals, with contact detail lookup |
| **All Hospitals — Response Rate** | Every hospital's response rate with histogram, ranked bar, and full table |
| **Care Dimension Scores** | National average linear mean score (0–100) per HCAHPS care dimension |
| **Key Insights** | Computed correlations, KPI cards, and scatter plot — nurse communication vs. overall rating |

---

## Tech Stack

- **Python 3.12**
- **Streamlit** — interactive web app
- **Pandas** — data wrangling
- **Plotly Express** — interactive charts
- **Snowflake** — cloud data warehouse (star schema)
- **snowflake-sqlalchemy** — Snowflake connection via SQLAlchemy
- **Docker** — containerised deployment
- **AWS ECR + App Runner** — cloud hosting

---

## Project Structure

```
healthcare-patient-survey-analysis/
├── analysis.py                           # Main Streamlit app
├── etl.py                                # CSV → Snowflake star schema ETL
├── schema.sql                            # Snowflake DDL (CREATE OR REPLACE TABLE)
├── requirements.txt                      # Python dependencies
├── Dockerfile                            # Production container image
├── docker-compose.yml                    # Local container run (reads .env)
├── .env.example                          # Environment variable template
├── data/
│   └── Health Care_Patient_survey_source.csv
└── screenshots/                          # Chart previews
```

---

## Data Model

The flat source CSV is transformed into a **star schema** in Snowflake by running `etl.py`:

```
dim_county_details      dim_hospital_details    dim_measure_details    dim_survey_details
──────────────────      ────────────────────    ───────────────────    ──────────────────
county_id (PK)          hospital_id (PK)        measure_id (PK)        survey_id (PK)
county_name             county_id (FK)          measure_start_date     survey_question
state                   hospital_name           measure_end_date       survey_answer
city                    city                                           patient_survey_star_
zipcode                 location                                         rating_footnote

                        fact_survey_response
                        ────────────────────
                        county_id (FK)
                        hospital_id (FK)
                        measure_id (FK)
                        survey_id (FK)
                        no_completed_surveys
                        no_completed_surveys_footnote
                        survey_response_rate_percent
                        survey_response_footnote_percent
                        linear_mean_value
                        answer_percent
                        patient_survey_star_rating
```

---

## Getting Started

### 1. Clone the repo

```bash
git clone <repo-url>
cd healthcare-patient-survey-analysis
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Running the App

### Option A — Local CSV (no Snowflake required)

The app reads from the bundled CSV automatically when no Snowflake credentials are set:

```bash
streamlit run analysis.py
```

Opens at **http://localhost:8501**.

---

### Option B — Snowflake

#### Step 1: Configure credentials

```bash
cp .env.example .env
# Edit .env and fill in your Snowflake account details
```

`.env` fields:

| Variable | Example | Description |
|---|---|---|
| `SNOWFLAKE_ACCOUNT` | `xy12345.us-east-1` | Snowflake account identifier |
| `SNOWFLAKE_USER` | `my_user` | Snowflake username |
| `SNOWFLAKE_PASSWORD` | `••••••` | Snowflake password |
| `SNOWFLAKE_DATABASE` | `HCAHPS` | Target database |
| `SNOWFLAKE_WAREHOUSE` | `COMPUTE_WH` | Virtual warehouse |
| `SNOWFLAKE_SCHEMA` | `PUBLIC` | Schema (default: PUBLIC) |

#### Step 2: Run the ETL (once)

Loads the CSV into Snowflake, creating all five star schema tables:

```bash
export $(cat .env | grep -v '#' | xargs)
python etl.py
```

Expected output:
```
Loading CSV...
  34,999 rows
Connecting to Snowflake...
Applying schema...
Loading dimension tables...
  DIM_COUNTY_DETAILS: 624 rows loaded
  DIM_HOSPITAL_DETAILS: 700 rows loaded
  DIM_MEASURE_DETAILS: 50 rows loaded
  DIM_SURVEY_DETAILS: 83 rows loaded
Loading fact table...
  FACT_SURVEY_RESPONSE: 34,999 rows loaded
ETL complete.
```

#### Step 3: Run the app

```bash
export $(cat .env | grep -v '#' | xargs)
streamlit run analysis.py
```

The app detects the `SNOWFLAKE_*` env vars automatically and queries Snowflake instead of the local CSV.

> To force the local CSV even when Snowflake vars are set, add `USE_CSV=true` to your `.env`.

---

### Option C — Docker (local container)

Use this to test the containerised app locally before deploying to AWS.

#### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

#### Step 1: Configure credentials

```bash
cp .env.example .env
# Fill in your Snowflake credentials (or add USE_CSV=true to use local CSV)
```

#### Step 2: Build and run

```bash
docker compose up --build
```

This builds the image from `Dockerfile` and starts the app container. The `.env` file is passed in automatically via `docker-compose.yml`.

App available at **http://localhost:8501**.

#### Step 3: Verify it's working

```bash
# Check the container is running
docker ps

# View live logs
docker compose logs -f app

# Stop the container
docker compose down
```

#### Testing with local CSV inside Docker

Add `USE_CSV=true` to your `.env` — the CSV is bundled inside the image so no Snowflake connection is needed:

```bash
echo "USE_CSV=true" >> .env
docker compose up --build
```

---

### Option D — AWS App Runner (production)

Use this to deploy the containerised app publicly on AWS. The Snowflake database acts as the data source — no database setup is needed on AWS itself.

#### Prerequisites
- [AWS CLI](https://aws.amazon.com/cli/) installed and configured (`aws configure`)
- Docker Desktop running
- ETL already run against Snowflake (Option B, Step 2)

#### Step 1: Create an ECR repository and push the image

```bash
# Set your AWS region and account ID
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/hcahps-app

# Create the repository (first time only)
aws ecr create-repository --repository-name hcahps-app --region $AWS_REGION

# Authenticate Docker with ECR
aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin $ECR_REPO

# Build, tag, and push
docker build -t hcahps-app .
docker tag hcahps-app:latest $ECR_REPO:latest
docker push $ECR_REPO:latest
```

#### Step 2: Create the App Runner service

In the [AWS Console → App Runner](https://console.aws.amazon.com/apprunner):

1. Click **Create service**
2. **Source:** Container registry → Amazon ECR → select `hcahps-app:latest`
3. **Port:** `8501`
4. **Environment variables** — add all six:
   - `SNOWFLAKE_ACCOUNT`
   - `SNOWFLAKE_USER`
   - `SNOWFLAKE_PASSWORD`
   - `SNOWFLAKE_DATABASE`
   - `SNOWFLAKE_WAREHOUSE`
   - `SNOWFLAKE_SCHEMA`
5. Click **Create & deploy**

App Runner provides a public HTTPS URL once the deployment completes (typically 2–3 minutes).

#### Step 3: Update after code changes

```bash
docker build -t hcahps-app .
docker tag hcahps-app:latest $ECR_REPO:latest
docker push $ECR_REPO:latest
# App Runner auto-deploys on new image push if auto-deployment is enabled
```

---

## Data

The source file (`data/Health Care_Patient_survey_source.csv`) contains HCAHPS survey responses with the following key fields:

| Field | Description |
|---|---|
| `Provider ID` / `Hospital Name` | Hospital identifier |
| `Measure ID` / `Question` | Survey dimension (e.g. nurse communication, cleanliness) |
| `Answer Percent` | % of patients giving a particular answer |
| `Linear Mean Value` | Continuous score (0–100) for the measure — pre-computed by CMS |
| `Patient Survey Star Rating` | 1–5 star rating per dimension |
| `Survey Response Rate Percent` | % of eligible patients who returned the survey |
| `Number of Completed Surveys` | Raw survey count |

**Coverage:** 619 hospitals · 7 states (AK, AL, AR, AZ, CA, CO, CT) · ~35,000 rows

The 10 `_LINEAR_SCORE` measures (out of 50 unique measure IDs) are CMS-computed continuous conversions of percentage-based survey answers onto a 0–100 scale. The app filters for these when computing care dimension averages and correlations.

---

## Dashboard Preview

### Top 10 Hospitals by Survey Response Rate

> Animas Surgical Hospital leads with a **60% response rate** — more than 2.5× the national median of 23%.

![Top 10 Hospitals by Response Rate](screenshots/top10_hospitals_response_rate.png)

---

### Distribution of Response Rates Across All Hospitals

> Most hospitals cluster between **15–30%**, with a long right tail of high-engagement outliers.

![Response Rate Distribution](screenshots/response_rate_distribution.png)

---

### National Average Score by Care Dimension

> **Doctor Communication** and **Nurse Communication** score highest nationally (90+). **Communication about Medicines** and **Quietness** are the most common areas for improvement.

![Care Dimension Scores](screenshots/care_dimension_scores.png)

---

### Average Survey Response Rate by State

> **AK (Alaska)** leads all states in average response rate. **CA (California)**, with the largest number of hospitals in the dataset, sits below the national average.

![State Response Rate](screenshots/state_response_rate.png)

---

## Key Insights

- **Response rates are low overall** — the national median is 23%, meaning most hospitals hear back from fewer than 1 in 4 eligible patients.
- **Specialty / surgical hospitals dominate the top response rates** — smaller patient volumes make follow-up easier.
- **Nurse communication is the strongest predictor of overall hospital rating** (r = 0.88) and patient recommendation (r = 0.84) — computed live in the dashboard.
- **Care transition** is the second-strongest driver of patient recommendation, suggesting that post-discharge support matters as much as in-hospital care.
- **Quietness** is the most independent dimension — hospitals that score well on other dimensions don't necessarily score well on quietness.
