import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

st.title("Healthcare Patient Survey Analysis")

pd.set_option('display.expand_frame_repr', False)

# --- Shared layout defaults ---
CHART_LAYOUT = dict(plot_bgcolor='white')

def style_hbar(fig, max_val, height=500, show_legend=False):
    """Apply standard horizontal-bar layout: reversed y-axis, padded x-range, white bg."""
    fig.update_traces(textposition='outside')
    fig.update_layout(
        xaxis=dict(range=[0, max_val * 1.2]),
        yaxis=dict(autorange='reversed'),
        height=height,
        showlegend=show_legend,
        **CHART_LAYOUT,
    )
    return fig


@st.cache_data
def load_data(path):
    return pd.read_csv(path)

df_raw   = load_data('data/Health Care_Patient_survey_source.csv')
df_clean = df_raw.dropna(subset=['Number of Completed Surveys'])

footnote_cols = [
    'Patient Survey Star Rating Footnote',
    'Answer Percent Footnote',
    'Number of Completed Surveys Footnote',
    'Survey Response Rate Percent Footnote',
]
df_clean = df_clean.drop(columns=footnote_cols)

for col in ['Number of Completed Surveys', 'Patient Survey Star Rating', 'Answer Percent', 'Linear Mean Value', 'Survey Response Rate Percent']:
    df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')

df_clean['Measure Start Date'] = pd.to_datetime(df_clean['Measure Start Date'], errors='coerce')
df_clean['Measure End Date']   = pd.to_datetime(df_clean['Measure End Date'],   errors='coerce')


# ----- Problem #1: Number of Surveys Completed by different Hospitals -----
# Each hospital row repeats the survey count per measure — take the unique value per hospital
surveys_by_hospital = (
    df_clean.groupby(['Provider ID', 'Hospital Name'])['Number of Completed Surveys']
    .first()
    .reset_index()
    .rename(columns={'Number of Completed Surveys': 'Completed Surveys'})
    .sort_values('Provider ID', ascending=True)
    .reset_index(drop=True)
)


# --- Metrics: basic data overview ---
st.subheader("Dataset Overview")

total_surveys   = int(df_clean['Number of Completed Surveys'].sum())
total_hospitals = df_clean['Provider ID'].nunique()

best_row      = df_clean.loc[df_clean['Survey Response Rate Percent'].idxmax()]
best_rate     = best_row['Survey Response Rate Percent']
best_hospital = best_row['Hospital Name']

surveys_by_city  = df_clean.groupby(['City', 'State'])['Number of Completed Surveys'].sum()
top_city, top_city_state = surveys_by_city.idxmax()
top_city_val = int(surveys_by_city.max())

surveys_by_state = df_clean.groupby('State')['Number of Completed Surveys'].sum()
top_state     = surveys_by_state.idxmax()
top_state_val = int(surveys_by_state.max())

col_total, col_hospitals, col_rate, col_city, col_state = st.columns(5)

col_total.metric("Total Surveys Completed", f"{total_surveys:,}")
col_hospitals.metric("Total Hospitals", total_hospitals)
col_rate.metric("Highest Response Rate", f"{best_rate:.0f}%", help=best_hospital)
col_city.metric("Most Responses — City", f"{top_city}, {top_city_state}", f"{top_city_val:,} surveys")
col_state.metric("Most Responses — State", top_state, f"{top_state_val:,} surveys")


# --- Sidebar controls ---
with st.sidebar:
    n_points   = st.slider("Data points", 20, 200, 20)
    chart_type = st.selectbox("Chart type", ["Bar", "Line", "Scatter"])
    show_data  = st.checkbox("Show raw data")

chart_fn = {'Bar': px.bar, 'Line': px.line, 'Scatter': px.scatter}[chart_type]
fig_surveys_by_hospital = chart_fn(
    surveys_by_hospital.head(n_points),
    y='Hospital Name',
    x='Completed Surveys',
    title='Number of Completed Surveys by different hospitals',
)
st.plotly_chart(fig_surveys_by_hospital)

if show_data:
    st.subheader("Raw Data")
    st.dataframe(surveys_by_hospital.head(n_points))

fig_surveys_by_state = px.bar(
    df_clean,
    x='State',
    y='Number of Completed Surveys',
    title='Number of Completed Surveys by State',
)
st.plotly_chart(fig_surveys_by_state)


# --- Problem #2: Survey Response Rate by Measure ID (per Hospital) ---
st.header("Survey Response Rate by Measure ID")

response_rate_df = (
    df_clean[['Measure ID', 'Provider ID', 'Hospital Name', 'Survey Response Rate Percent']]
    .dropna(subset=['Survey Response Rate Percent'])
    .drop_duplicates()
)

# Order measure IDs by their mean response rate descending
measure_order = (
    response_rate_df.groupby('Measure ID')['Survey Response Rate Percent']
    .mean()
    .sort_values(ascending=False)
    .index.tolist()
)

# Sidebar filter: pick which measure IDs to show
with st.sidebar:
    st.markdown("---")
    st.subheader("Response Rate Chart")
    selected_measures = st.multiselect(
        "Filter Measure IDs",
        options=measure_order,
        default=measure_order[:10],
    )

filtered_response_df = response_rate_df[response_rate_df['Measure ID'].isin(selected_measures)]

fig_response_by_measure = px.strip(
    filtered_response_df,
    x='Survey Response Rate Percent',
    y='Measure ID',
    category_orders={'Measure ID': [m for m in measure_order if m in selected_measures]},
    hover_data=['Hospital Name', 'Provider ID'],
    title='Survey Response Rate (%) per Hospital by Measure ID',
    labels={
        'Survey Response Rate Percent': 'Response Rate (%)',
        'Measure ID': 'Measure ID',
    },
    color='Measure ID',
    stripmode='overlay',
)
fig_response_by_measure.update_traces(marker=dict(size=5, opacity=0.5))
fig_response_by_measure.update_layout(
    height=600,
    showlegend=False,
    xaxis=dict(title='Response Rate (%)', gridcolor='lightgrey'),
    yaxis=dict(title='Measure ID'),
    **CHART_LAYOUT,
)
st.plotly_chart(fig_response_by_measure, width='stretch')

# Summary stats table beneath the chart
st.subheader("Response Rate Summary by Measure ID")
response_rate_summary = (
    filtered_response_df.groupby('Measure ID')['Survey Response Rate Percent']
    .agg(Hospitals='count', Mean='mean', Median='median', Min='min', Max='max')
    .round(1)
    .loc[[m for m in measure_order if m in selected_measures]]
    .reset_index()
)
st.dataframe(response_rate_summary, width='stretch')


# --- Problem #3: Top 3 Counties with the Highest Survey Response Rate ---
st.header("Top 3 Counties by Survey Response Rate")

county_rate = (
    df_clean.dropna(subset=['Survey Response Rate Percent', 'County Name'])
    .groupby(['County Name', 'State'])['Survey Response Rate Percent']
    .mean()
    .reset_index()
    .rename(columns={'Survey Response Rate Percent': 'Avg Response Rate (%)'})
    .sort_values('Avg Response Rate (%)', ascending=False)
    .head(3)
    .reset_index(drop=True)
)
county_rate.index += 1  # rank starts at 1

fig_top_counties = px.bar(
    county_rate,
    x='County Name',
    y='Avg Response Rate (%)',
    color='State',
    text='Avg Response Rate (%)',
    title='Top 3 Counties — Average Survey Response Rate (%)',
    labels={'Avg Response Rate (%)': 'Avg Response Rate (%)'},
)
fig_top_counties.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
fig_top_counties.update_layout(
    yaxis=dict(range=[0, county_rate['Avg Response Rate (%)'].max() * 1.2]),
    showlegend=True,
    **CHART_LAYOUT,
)
st.plotly_chart(fig_top_counties, width='stretch')
st.dataframe(county_rate, width='stretch')


# --- Problem #4: Top 10 Hospitals with the Highest Survey Response Rate ---
st.header("Top 10 Hospitals by Survey Response Rate")

hospital_rate = (
    df_clean.dropna(subset=['Survey Response Rate Percent'])
    .groupby(['Provider ID', 'Hospital Name'])['Survey Response Rate Percent']
    .mean()
    .reset_index()
    .rename(columns={'Survey Response Rate Percent': 'Avg Response Rate (%)'})
    .sort_values('Avg Response Rate (%)', ascending=False)
    .head(10)
    .reset_index(drop=True)
)
hospital_rate.index += 1  # rank starts at 1

fig_top_hospitals = px.bar(
    hospital_rate,
    x='Avg Response Rate (%)',
    y='Hospital Name',
    text='Avg Response Rate (%)',
    orientation='h',
    title='Top 10 Hospitals — Average Survey Response Rate (%)',
    labels={'Avg Response Rate (%)': 'Avg Response Rate (%)'},
)
fig_top_hospitals.update_traces(texttemplate='%{text:.1f}%')
style_hbar(fig_top_hospitals, hospital_rate['Avg Response Rate (%)'].max())
st.plotly_chart(fig_top_hospitals, width='stretch')
st.dataframe(hospital_rate, width='stretch')


# --- Problem #5: County and City wise Hospital Rating — Drill-down Report ---
st.header("County & City wise Hospital Rating")

rating_df = (
    df_clean.dropna(subset=['Patient Survey Star Rating', 'County Name', 'City'])
    .groupby(['State', 'County Name', 'City', 'Hospital Name'])['Patient Survey Star Rating']
    .mean()
    .reset_index()
    .rename(columns={'Patient Survey Star Rating': 'Avg Star Rating'})
)
rating_df['Avg Star Rating'] = rating_df['Avg Star Rating'].round(2)

# Sidebar drill-down filters
with st.sidebar:
    st.markdown("---")
    st.subheader("Hospital Rating Drill-down")
    rating_states  = sorted(rating_df['State'].unique())
    selected_state = st.selectbox("State", rating_states)

    counties = sorted(rating_df[rating_df['State'] == selected_state]['County Name'].unique())
    selected_county = st.selectbox("County", counties)

    cities = sorted(
        rating_df[
            (rating_df['State'] == selected_state) &
            (rating_df['County Name'] == selected_county)
        ]['City'].unique()
    )
    selected_city = st.selectbox("City", ["All"] + cities)

# Filter based on sidebar selection
drilldown_df = rating_df[
    (rating_df['State'] == selected_state) &
    (rating_df['County Name'] == selected_county)
]
if selected_city != "All":
    drilldown_df = drilldown_df[drilldown_df['City'] == selected_city]

# Treemap — click to drill down: County → City → Hospital
fig_rating_treemap = px.treemap(
    drilldown_df,
    path=['County Name', 'City', 'Hospital Name'],
    values='Avg Star Rating',
    color='Avg Star Rating',
    color_continuous_scale='RdYlGn',
    range_color=[1, 5],
    title=f'Hospital Ratings — {selected_county} County, {selected_state}',
)
fig_rating_treemap.update_layout(height=550, margin=dict(t=50, l=10, r=10, b=10))
st.plotly_chart(fig_rating_treemap, width='stretch')

# Bar chart for filtered hospitals
drilldown_sorted = drilldown_df.sort_values('Avg Star Rating', ascending=True)
fig_rating_bar = px.bar(
    drilldown_sorted,
    x='Avg Star Rating',
    y='Hospital Name',
    color='City',
    orientation='h',
    text='Avg Star Rating',
    title='Hospital Star Ratings',
    labels={'Avg Star Rating': 'Avg Star Rating (1–5)'},
)
fig_rating_bar.update_traces(texttemplate='%{text:.2f}', textposition='outside')
fig_rating_bar.update_layout(
    xaxis=dict(range=[0, 6]),
    height=max(300, len(drilldown_sorted) * 35),
    showlegend=True,
    **CHART_LAYOUT,
)
st.plotly_chart(fig_rating_bar, width='stretch')
st.dataframe(drilldown_sorted.reset_index(drop=True), width='stretch')


# --- Problem #6: Hospitals in the Same City ---
st.header("Hospitals in the Same City")

# One row per hospital per city (deduplicate across measures)
city_hospitals = (
    df_clean[['State', 'City', 'Provider ID', 'Hospital Name']]
    .drop_duplicates()
    .groupby(['State', 'City'])
    .agg(Hospital_Count=('Hospital Name', 'count'),
         Hospitals=('Hospital Name', lambda x: ', '.join(sorted(x.unique()))))
    .reset_index()
    .query('Hospital_Count > 1')
    .sort_values('Hospital_Count', ascending=False)
    .reset_index(drop=True)
)

# Sidebar filters
with st.sidebar:
    st.markdown("---")
    st.subheader("Hospitals in Same City")
    same_city_state_opts = ["All"] + sorted(city_hospitals['State'].unique())
    same_city_state = st.selectbox("Filter by State", same_city_state_opts, key="same_city_state")

same_city_df = city_hospitals if same_city_state == "All" else city_hospitals[city_hospitals['State'] == same_city_state]

# Bar chart — top 20 cities by hospital count
top_cities = same_city_df.head(20)
fig_same_city = px.bar(
    top_cities,
    x='Hospital_Count',
    y='City',
    color='State',
    orientation='h',
    text='Hospital_Count',
    title='Cities with the Most Hospitals (top 20)',
    labels={'Hospital_Count': 'Number of Hospitals', 'City': 'City'},
)
style_hbar(fig_same_city, top_cities['Hospital_Count'].max(), height=600, show_legend=True)
st.plotly_chart(fig_same_city, width='stretch')

# City picker — see exact hospital list
same_city_cities    = sorted(same_city_df['City'].unique())
selected_city_detail = st.selectbox("Select a city to see its hospitals", same_city_cities)

city_row = same_city_df[same_city_df['City'] == selected_city_detail].iloc[0]
st.metric("Hospitals in " + selected_city_detail, int(city_row['Hospital_Count']))

city_detail = (
    df_clean[['Provider ID', 'Hospital Name', 'Address', 'Phone Number']]
    [df_clean['City'] == selected_city_detail]
    .drop_duplicates(subset=['Provider ID'])
    .reset_index(drop=True)
)
st.dataframe(city_detail, width='stretch')


# --- Problem #7: Total Survey Response Rate by All Hospitals ---
st.header("Total Survey Response Rate by All Hospitals")

all_hospital_rate = (
    df_clean.dropna(subset=['Survey Response Rate Percent'])
    .groupby(['Provider ID', 'Hospital Name', 'City', 'State'])['Survey Response Rate Percent']
    .first()
    .reset_index()
    .rename(columns={'Survey Response Rate Percent': 'Response Rate (%)'})
    .sort_values('Response Rate (%)', ascending=False)
    .reset_index(drop=True)
)

# Sidebar controls for this section
with st.sidebar:
    st.markdown("---")
    st.subheader("All Hospitals — Response Rate")
    all_rate_state_opts = ["All"] + sorted(all_hospital_rate['State'].unique())
    all_rate_state = st.selectbox("Filter by State", all_rate_state_opts, key="all_rate_state")
    all_rate_sort  = st.selectbox("Sort by", ["Response Rate (%) ↓", "Response Rate (%) ↑", "Hospital Name"], key="all_rate_sort")
    all_rate_n     = st.slider("Hospitals to display in chart", 10, len(all_hospital_rate), 30, key="all_rate_n")

all_rate_df = all_hospital_rate if all_rate_state == "All" else all_hospital_rate[all_hospital_rate['State'] == all_rate_state]

if all_rate_sort == "Response Rate (%) ↑":
    all_rate_df = all_rate_df.sort_values('Response Rate (%)', ascending=True)
elif all_rate_sort == "Hospital Name":
    all_rate_df = all_rate_df.sort_values('Hospital Name')
else:
    all_rate_df = all_rate_df.sort_values('Response Rate (%)', ascending=False)

all_rate_df = all_rate_df.reset_index(drop=True)

# Distribution histogram of response rates
fig_response_dist = px.histogram(
    all_rate_df,
    x='Response Rate (%)',
    nbins=20,
    title='Distribution of Survey Response Rates Across All Hospitals',
    labels={'Response Rate (%)': 'Response Rate (%)', 'count': 'Number of Hospitals'},
    color_discrete_sequence=['steelblue'],
)
fig_response_dist.update_layout(bargap=0.05, **CHART_LAYOUT)
st.plotly_chart(fig_response_dist, width='stretch')

# Bar chart for top N hospitals
all_rate_chart_df = all_rate_df.head(all_rate_n)
fig_all_rate = px.bar(
    all_rate_chart_df,
    x='Response Rate (%)',
    y='Hospital Name',
    color='State',
    orientation='h',
    text='Response Rate (%)',
    hover_data=['City', 'State', 'Provider ID'],
    title=f'Survey Response Rate — Top {all_rate_n} Hospitals{"" if all_rate_state == "All" else f" in {all_rate_state}"}',
    labels={'Response Rate (%)': 'Response Rate (%)'},
)
fig_all_rate.update_traces(texttemplate='%{text:.0f}%')
style_hbar(fig_all_rate, all_rate_chart_df['Response Rate (%)'].max(), height=max(400, all_rate_n * 22), show_legend=True)
st.plotly_chart(fig_all_rate, width='stretch')

# Full sortable data table
st.subheader(f"All Hospitals — Response Rate Table ({len(all_rate_df)} hospitals)")
st.dataframe(all_rate_df.reset_index(drop=True), width='stretch')
