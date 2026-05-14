import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

st.title("Healthcare Patient Survey Analysis")

pd.set_option('display.expand_frame_repr', False)

@st.cache_data
def load_data(path):
    return pd.read_csv(path)
# Read the data from the CSV file
df = load_data('data/Health Care_Patient_survey_source.csv')

# Clean the data by removing rows with missing values in the 'Number of Completed Surveys' column
df_clean = df.dropna(subset=['Number of Completed Surveys'])

# Drop footnote columns (long explanatory text, not analytical value) ──
footnote_cols = [
    'Patient Survey Star Rating Footnote',
    'Answer Percent Footnote',
    'Number of Completed Surveys Footnote',
    'Survey Response Rate Percent Footnote',
]
df_clean = df_clean.drop(columns=footnote_cols)

# Convert remaining numeric columns to proper types ──────────────────────
for col in ['Number of Completed Surveys','Patient Survey Star Rating', 'Answer Percent', 'Linear Mean Value', 'Survey Response Rate Percent']:
    df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')

# Convert date columns to datetime ──────────────────────────────────────
df_clean['Measure Start Date'] = pd.to_datetime(df_clean['Measure Start Date'], errors='coerce')
df_clean['Measure End Date']   = pd.to_datetime(df_clean['Measure End Date'],   errors='coerce')



# ----- Problem #1 Number of Surveys Completed by different Hospitals --
# Each hospital row repeats the survey count per measure — take the unique value per hospital
surveys_by_hospital = (
    df_clean.groupby(['Provider ID', 'Hospital Name'])['Number of Completed Surveys']
    .first()
    .reset_index()
    .rename(columns={'Number of Completed Surveys': 'Completed Surveys'})
    .sort_values('Provider ID', ascending=True)
    .reset_index(drop=True))


# --- Metrics: basic data overview ---
st.subheader("Dataset Overview")

total_surveys   = int(df_clean['Number of Completed Surveys'].sum())
total_hospitals = df_clean['Provider ID'].nunique()

best_idx      = df_clean['Survey Response Rate Percent'].idxmax()
best_rate     = df_clean.loc[best_idx, 'Survey Response Rate Percent']
best_hospital = df_clean.loc[best_idx, 'Hospital Name']

city_group  = df_clean.groupby(['City', 'State'])['Number of Completed Surveys'].sum()
top_city, top_city_state = city_group.idxmax()
top_city_val = int(city_group.max())

state_group   = df_clean.groupby('State')['Number of Completed Surveys'].sum()
top_state     = state_group.idxmax()
top_state_val = int(state_group.max())

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Total Surveys Completed", f"{total_surveys:,}")
col2.metric("Total Hospitals", total_hospitals)
col3.metric("Highest Response Rate", f"{best_rate:.0f}%", help=best_hospital)
col4.metric("Most Responses — City", f"{top_city}, {top_city_state}", f"{top_city_val:,} surveys")
col5.metric("Most Responses — State", top_state, f"{top_state_val:,} surveys")


# --- Sidebar controls ---
with st.sidebar:
    n_points = st.slider("Data points", 20, 200, 20)
    chart_type = st.selectbox("Chart type", ["Bar", "Line", "Scatter"])
    show_data = st.checkbox("Show raw data")

if chart_type == "Bar":
    fig = px.bar(surveys_by_hospital.head(n_points), y='Hospital Name', x='Completed Surveys', 
                 title='Number of Completed Surveys by different hospitals')
elif chart_type == "Line":
    fig = px.line(surveys_by_hospital.head(n_points), y='Hospital Name', x='Completed Surveys', 
                  title='Number of Completed Surveys by different hospitals')
else:
    fig = px.scatter(surveys_by_hospital.head(n_points), y='Hospital Name', x='Completed Surveys', 
                     title='Number of Completed Surveys by different hospitals')
st.plotly_chart(fig)

if show_data:
    st.subheader("Raw Data")
    st.dataframe(surveys_by_hospital.head(n_points))

# Create a bar chart to visualize the number of completed surveys by state
fig = px.bar(df_clean, x='State', y='Number of Completed Surveys', title='Number of Completed Surveys by State')
st.plotly_chart(fig)


# --- Problem #2: Survey Response Rate by Measure ID (per Hospital) ---
st.header("Survey Response Rate by Measure ID")

plot_df = (
    df_clean[['Measure ID', 'Provider ID', 'Hospital Name', 'Survey Response Rate Percent']]
    .dropna(subset=['Survey Response Rate Percent'])
    .drop_duplicates()
)

# Order measure IDs by their mean response rate descending
measure_order = (
    plot_df.groupby('Measure ID')['Survey Response Rate Percent']
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

filtered_df = plot_df[plot_df['Measure ID'].isin(selected_measures)]

fig2 = px.strip(
    filtered_df,
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

fig2.update_traces(marker=dict(size=5, opacity=0.5))
fig2.update_layout(
    height=600,
    showlegend=False,
    xaxis=dict(title='Response Rate (%)', gridcolor='lightgrey'),
    yaxis=dict(title='Measure ID'),
    plot_bgcolor='white',
)

st.plotly_chart(fig2, width='stretch')

# Summary stats table beneath the chart
st.subheader("Response Rate Summary by Measure ID")
summary = (
    filtered_df.groupby('Measure ID')['Survey Response Rate Percent']
    .agg(Hospitals='count', Mean='mean', Median='median', Min='min', Max='max')
    .round(1)
    .loc[[m for m in measure_order if m in selected_measures]]
    .reset_index()
)
st.dataframe(summary, width='stretch')


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

fig3 = px.bar(
    county_rate,
    x='County Name',
    y='Avg Response Rate (%)',
    color='State',
    text='Avg Response Rate (%)',
    title='Top 3 Counties — Average Survey Response Rate (%)',
    labels={'Avg Response Rate (%)': 'Avg Response Rate (%)'},
)
fig3.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
fig3.update_layout(
    yaxis=dict(range=[0, county_rate['Avg Response Rate (%)'].max() * 1.2]),
    plot_bgcolor='white',
    showlegend=True,
)

st.plotly_chart(fig3, width='stretch')
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

print(hospital_rate.head())

fig4 = px.bar(
    hospital_rate,
    x='Avg Response Rate (%)',
    y='Hospital Name',
    text='Avg Response Rate (%)',
    orientation='h',
    title='Top 10 Hospitals — Average Survey Response Rate (%)',
    labels={'Avg Response Rate (%)': 'Avg Response Rate (%)'},
)
fig4.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
fig4.update_layout(
    xaxis=dict(range=[0, hospital_rate['Avg Response Rate (%)'].max() * 1.2]),
    yaxis=dict(autorange='reversed'),
    plot_bgcolor='white',
    showlegend=False,
    height=500,
)

st.plotly_chart(fig4, width='stretch')
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
    states = sorted(rating_df['State'].unique())
    selected_state = st.selectbox("State", states)

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
fig5 = px.treemap(
    drilldown_df,
    path=['County Name', 'City', 'Hospital Name'],
    values='Avg Star Rating',
    color='Avg Star Rating',
    color_continuous_scale='RdYlGn',
    range_color=[1, 5],
    title=f'Hospital Ratings — {selected_county} County, {selected_state}',
)
fig5.update_layout(height=550, margin=dict(t=50, l=10, r=10, b=10))
st.plotly_chart(fig5, width='stretch')

# Bar chart for filtered hospitals
drilldown_sorted = drilldown_df.sort_values('Avg Star Rating', ascending=True)
fig6 = px.bar(
    drilldown_sorted,
    x='Avg Star Rating',
    y='Hospital Name',
    color='City',
    orientation='h',
    text='Avg Star Rating',
    title='Hospital Star Ratings',
    labels={'Avg Star Rating': 'Avg Star Rating (1–5)'},
)
fig6.update_traces(texttemplate='%{text:.2f}', textposition='outside')
fig6.update_layout(
    xaxis=dict(range=[0, 6]),
    plot_bgcolor='white',
    height=max(300, len(drilldown_sorted) * 35),
    showlegend=True,
)
st.plotly_chart(fig6, width='stretch')
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
    p6_states = ["All"] + sorted(city_hospitals['State'].unique())
    p6_state = st.selectbox("Filter by State", p6_states, key="p6_state")

p6_df = city_hospitals if p6_state == "All" else city_hospitals[city_hospitals['State'] == p6_state]

# Bar chart — top 20 cities by hospital count
top_cities = p6_df.head(20)
fig7 = px.bar(
    top_cities,
    x='Hospital_Count',
    y='City',
    color='State',
    orientation='h',
    text='Hospital_Count',
    title='Cities with the Most Hospitals (top 20)',
    labels={'Hospital_Count': 'Number of Hospitals', 'City': 'City'},
)
fig7.update_traces(textposition='outside')
fig7.update_layout(
    xaxis=dict(range=[0, top_cities['Hospital_Count'].max() * 1.2]),
    yaxis=dict(autorange='reversed'),
    plot_bgcolor='white',
    height=600,
    showlegend=True,
)
st.plotly_chart(fig7, width='stretch')

# City picker — see exact hospital list
p6_cities = sorted(p6_df['City'].unique())
selected_p6_city = st.selectbox("Select a city to see its hospitals", p6_cities)

city_row = p6_df[p6_df['City'] == selected_p6_city].iloc[0]
st.metric("Hospitals in " + selected_p6_city, int(city_row['Hospital_Count']))

city_detail = (
    df_clean[['Provider ID', 'Hospital Name', 'Address', 'Phone Number']]
    [df_clean['City'] == selected_p6_city]
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
    p7_states = ["All"] + sorted(all_hospital_rate['State'].unique())
    p7_state = st.selectbox("Filter by State", p7_states, key="p7_state")
    p7_sort = st.selectbox("Sort by", ["Response Rate (%) ↓", "Response Rate (%) ↑", "Hospital Name"], key="p7_sort")
    p7_n = st.slider("Hospitals to display in chart", 10, len(all_hospital_rate), 30, key="p7_n")

p7_df = all_hospital_rate if p7_state == "All" else all_hospital_rate[all_hospital_rate['State'] == p7_state]

if p7_sort == "Response Rate (%) ↑":
    p7_df = p7_df.sort_values('Response Rate (%)', ascending=True)
elif p7_sort == "Hospital Name":
    p7_df = p7_df.sort_values('Hospital Name')
else:
    p7_df = p7_df.sort_values('Response Rate (%)', ascending=False)

p7_df = p7_df.reset_index(drop=True)


# Distribution histogram of response rates
fig_hist = px.histogram(
    p7_df,
    x='Response Rate (%)',
    nbins=20,
    title='Distribution of Survey Response Rates Across All Hospitals',
    labels={'Response Rate (%)': 'Response Rate (%)', 'count': 'Number of Hospitals'},
    color_discrete_sequence=['steelblue'],
)
fig_hist.update_layout(plot_bgcolor='white', bargap=0.05)
st.plotly_chart(fig_hist, width='stretch')

# Bar chart for top N hospitals
chart_df = p7_df.head(p7_n)
fig_p7 = px.bar(
    chart_df,
    x='Response Rate (%)',
    y='Hospital Name',
    color='State',
    orientation='h',
    text='Response Rate (%)',
    hover_data=['City', 'State', 'Provider ID'],
    title=f'Survey Response Rate — Top {p7_n} Hospitals{"" if p7_state == "All" else f" in {p7_state}"}',
    labels={'Response Rate (%)': 'Response Rate (%)'},
)
fig_p7.update_traces(texttemplate='%{text:.0f}%', textposition='outside')
fig_p7.update_layout(
    xaxis=dict(range=[0, chart_df['Response Rate (%)'].max() * 1.2]),
    yaxis=dict(autorange='reversed'),
    plot_bgcolor='white',
    height=max(400, p7_n * 22),
    showlegend=True,
)
st.plotly_chart(fig_p7, width='stretch')

# Full sortable data table
st.subheader(f"All Hospitals — Response Rate Table ({len(p7_df)} hospitals)")
st.dataframe(p7_df.reset_index(drop=True), width='stretch')


