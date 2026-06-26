-- Star schema for HCAHPS patient survey data (Snowflake)
-- Foreign keys are declared for documentation; Snowflake does not enforce them.

CREATE OR REPLACE TABLE dim_county_details (
    county_id   INT          NOT NULL PRIMARY KEY,
    county_name VARCHAR(100),
    state       VARCHAR(100),
    city        VARCHAR(100),
    zipcode     VARCHAR(10)
);

CREATE OR REPLACE TABLE dim_hospital_details (
    hospital_id   VARCHAR(10)  NOT NULL PRIMARY KEY,
    county_id     INT,
    hospital_name VARCHAR(200) NOT NULL,
    city          VARCHAR(100),
    location      VARCHAR(500),
    FOREIGN KEY (county_id) REFERENCES dim_county_details(county_id)
);

CREATE OR REPLACE TABLE dim_measure_details (
    measure_id         VARCHAR(60) NOT NULL PRIMARY KEY,
    measure_start_date DATE,
    measure_end_date   DATE
);

CREATE OR REPLACE TABLE dim_survey_details (
    survey_id                           INT  NOT NULL PRIMARY KEY,
    survey_question                     VARCHAR,
    survey_answer                       VARCHAR,
    patient_survey_star_rating_footnote VARCHAR
);

CREATE OR REPLACE TABLE fact_survey_response (
    county_id                        INT,
    hospital_id                      VARCHAR(10),
    measure_id                       VARCHAR(60),
    survey_id                        INT,
    no_completed_surveys             INT,
    no_completed_surveys_footnote    VARCHAR,
    survey_response_rate_percent     NUMBER(6, 2),
    survey_response_footnote_percent VARCHAR,
    linear_mean_value                NUMBER(6, 2),
    answer_percent                   NUMBER(6, 2),
    patient_survey_star_rating       NUMBER(3, 1),
    FOREIGN KEY (county_id)   REFERENCES dim_county_details(county_id),
    FOREIGN KEY (hospital_id) REFERENCES dim_hospital_details(hospital_id),
    FOREIGN KEY (measure_id)  REFERENCES dim_measure_details(measure_id),
    FOREIGN KEY (survey_id)   REFERENCES dim_survey_details(survey_id)
);
