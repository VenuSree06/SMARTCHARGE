import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path

# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="SMARTCHARGE | EV Analytics",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# 2. CUSTOM CSS
# =========================================================
st.markdown("""
<style>
.stApp { background-color: #F4F7FB; }

[data-testid="stSidebar"] { background-color: #142D4E; }
[data-testid="stSidebar"] * { color: white !important; }

/* Main-page descriptions/captions: readable on the light background */
.stApp [data-testid="stCaptionContainer"] p,
.stApp .subtitle {
    color: #2F855A !important;
    font-size: 15px;
}

.main-title {
    font-size: 34px;
    font-weight: 800;
    color: #142D4E;
}

.kpi-card {
    background: white;
    padding: 22px;
    border-radius: 14px;
    border-left: 5px solid #06B6D4;
    box-shadow: 0 3px 12px rgba(0,0,0,0.05);
}
.kpi-title { color: #64748B; font-size: 14px; }
.kpi-value { color: #142D4E; font-size: 27px; font-weight: 800; }

.section-title {
    color: #142D4E;
    font-size: 23px;
    font-weight: 700;
    margin-top: 20px;
}
.insight-card {
    background: white;
    padding: 18px;
    border-radius: 12px;
    margin-bottom: 12px;
    border-left: 4px solid #10B981;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.footer {
    text-align: center;
    color: #64748B;
    padding: 25px;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# 3. DATASET PATHS
# =========================================================
BASE_DIR = Path(__file__).resolve().parent

REGISTRATION_PATH = BASE_DIR / "datasets" / "processed" / "ev_registrations_cleaned.csv"
MAKER_PATH = BASE_DIR / "datasets" / "processed" / "ev_makers_cleaned.csv"
STATION_PATH = BASE_DIR / "datasets" / "processed" / "ev_stations_cleaned.csv"

# =========================================================
# 4. LOAD DATASETS
# =========================================================
@st.cache_data
def load_data():
    required_files = [REGISTRATION_PATH, MAKER_PATH, STATION_PATH]
    missing_files = [str(path) for path in required_files if not path.exists()]

    if missing_files:
        raise FileNotFoundError("Missing dataset files: " + ", ".join(missing_files))

    registrations = pd.read_csv(REGISTRATION_PATH)
    makers = pd.read_csv(MAKER_PATH)
    stations = pd.read_csv(STATION_PATH)

    registrations["Date"] = pd.to_datetime(
        registrations["Date"], errors="coerce", dayfirst=True
    )
    registrations = registrations.dropna(subset=["Date"]).copy()

    vehicle_columns = [
        col for col in registrations.columns
        if col not in ["Date", "Year", "Month", "Total_Registrations"]
    ]

    for col in vehicle_columns:
        registrations[col] = pd.to_numeric(
            registrations[col], errors="coerce"
        ).fillna(0)

    registrations["Total_Registrations"] = registrations[vehicle_columns].sum(axis=1)
    registrations["Year"] = registrations["Date"].dt.year
    registrations["Month"] = registrations["Date"].dt.month

    yearly = (
        registrations.groupby("Year")["Total_Registrations"]
        .sum().reset_index().sort_values("Year")
    )
    yearly["YoY_Growth_%"] = yearly["Total_Registrations"].pct_change() * 100

    categories = (
        registrations[vehicle_columns].sum().sort_values(ascending=False)
        .reset_index()
    )
    categories.columns = ["Vehicle_Category", "Total_Registrations"]

    # Standardize state text so the global filter works consistently.
    for frame in (makers, stations):
        if "State" in frame.columns:
            frame["State"] = frame["State"].astype("string").str.strip()
            frame.loc[frame["State"].isin(["", "nan", "None"]), "State"] = pd.NA

    return registrations, makers, stations, yearly, categories


# =========================================================
# 5. LOAD DATA SAFELY
# =========================================================
try:
    registrations, makers, stations, yearly, categories = load_data()
except Exception as error:
    st.error(f"Unable to load project datasets: {error}")
    st.stop()

# =========================================================
# 6. SIDEBAR NAVIGATION + GLOBAL STATE FILTER
# =========================================================
with st.sidebar:
    st.markdown("# ⚡ SMARTCHARGE")
    st.caption("Electric Vehicle Analytics Platform")
    st.markdown("---")

    (page) = st.radio(      

    "NAVIGATION",
    [
        "Dashboard Overview",
        "EV Registration Analytics",
        "Manufacturer Analytics",
        "Charging Infrastructure",
        "Geographical Analysis",
        "Business Insights",
        "Data Explorer"
    ]
)

    st.markdown("---")
    st.markdown("### ANALYTICS FILTER")
    all_states = sorted(set(
        makers["State"].dropna().astype(str).tolist()
        + stations["State"].dropna().astype(str).tolist()
    ))
    selected_state = st.selectbox(
        "Select State",
        ["All India"] + all_states,
        index=0,
        help="This filter updates manufacturer and charging-infrastructure analytics."
    )
    st.caption("Registration data is provided as an India-level dataset.")
    st.markdown("---")
    st.caption("SMARTCHARGE | 2026")

# Apply the selected state to the relevant datasets.
if selected_state == "All India":
    filtered_stations = stations.copy()
    filtered_makers = makers.copy()
else:
    filtered_stations = stations[stations["State"] == selected_state].copy()
    filtered_makers = makers[makers["State"] == selected_state].copy()

# =========================================================
# 7. REUSABLE FUNCTIONS
# =========================================================
def kpi_card(title, value):
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def section_heading(title, description=None):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if description:
        st.caption(description)


def show_chart(fig):
    fig.update_layout(
        template="plotly_white",
        height=420,
        margin=dict(l=20, r=20, t=55, b=25),
        title_font=dict(size=17, color="#142D4E"),
        font=dict(family="Arial", color="#334155")
    )
    st.plotly_chart(fig, use_container_width=True)


def empty_message(message="No records are available for the selected state."):
    st.info(message)


# =========================================================
# 8. FILTERED SUMMARIES AND COMMON CALCULATIONS
# =========================================================
total_registrations = int(registrations["Total_Registrations"].sum())
total_stations = filtered_stations["Station Name"].nunique()
total_makers = filtered_makers["EV Maker"].nunique()
total_states = filtered_stations["State"].nunique()

manufacturer_state = (
    filtered_makers.dropna(subset=["State"])
    .groupby("State")["EV Maker"].nunique()
    .reset_index(name="Total_Manufacturers")
    .sort_values("Total_Manufacturers", ascending=False)
)

state_stations = (
    filtered_stations.dropna(subset=["State"])
    .groupby("State")["Station Name"].nunique()
    .reset_index(name="Total_Charging_Stations")
    .sort_values("Total_Charging_Stations", ascending=False)
)

connector_distribution = (
    filtered_stations.assign(
        **{"Connector Type": filtered_stations["Connector Type"].fillna("Unknown")}
    )
    .groupby("Connector Type")["Station Name"].nunique()
    .reset_index(name="Total_Stations")
    .sort_values("Total_Stations", ascending=False)
)
connector_distribution.columns = ["Connector_Type", "Total_Stations"]

operator_distribution = (
    filtered_stations.assign(Operator=filtered_stations["Operator"].fillna("Unknown"))
    .groupby("Operator").size().reset_index(name="Total_Stations")
    .sort_values("Total_Stations", ascending=False)
)

usage_distribution = (
    filtered_stations.assign(Usage_Type=filtered_stations["Usage Type"].fillna("Unknown"))
    .groupby("Usage_Type").size().reset_index(name="Total_Stations")
    .sort_values("Total_Stations", ascending=False)
)

top_station_state = state_stations.iloc[0]["State"] if not state_stations.empty else "N/A"
top_vehicle = categories.iloc[0]["Vehicle_Category"] if not categories.empty else "N/A"

state_label = "All India" if selected_state == "All India" else selected_state

# =========================================================
# 9. DASHBOARD OVERVIEW
# =========================================================
if page == "Dashboard Overview":
    st.markdown('<div class="main-title">SMARTCHARGE Dashboard</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Electric Vehicle Adoption and Charging Infrastructure Analytics in India</div>',
        unsafe_allow_html=True
    )
    st.caption(f"Current infrastructure/manufacturer filter: {state_label}")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Total EV Registrations", f"{total_registrations:,}")
    with c2:
        kpi_card("Charging Stations", f"{total_stations:,}")
    with c3:
        kpi_card("EV Manufacturers", f"{total_makers:,}")
    with c4:
        kpi_card("States with Stations", f"{total_states:,}")

    section_heading(
        "EV Market and Infrastructure Overview",
        "Explore major trends across registrations, manufacturers and charging infrastructure."
    )

    col1, col2 = st.columns(2)
    with col1:
        show_chart(px.line(
            yearly, x="Year", y="Total_Registrations", markers=True,
            title="Year-wise EV Registration Trend"
        ))
    with col2:
        if not state_stations.empty:
            fig = px.bar(
                state_stations.head(10), x="Total_Charging_Stations", y="State",
                orientation="h", title="Top States by Charging Stations"
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            show_chart(fig)
        else:
            empty_message()

    col3, col4 = st.columns(2)
    with col3:
        fig = px.bar(
            categories.head(10), x="Total_Registrations", y="Vehicle_Category",
            orientation="h", title="Top EV Vehicle Categories"
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        show_chart(fig)
    with col4:
        if not usage_distribution.empty:
            show_chart(px.pie(
                usage_distribution, names="Usage_Type", values="Total_Stations",
                hole=0.55, title="Charging Station Usage Distribution"
            ))
        else:
            empty_message()

    if not connector_distribution.empty:
        show_chart(px.bar(
            connector_distribution.head(10), x="Connector_Type", y="Total_Stations",
            title="Charging Stations by Connector Type"
        ))
    else:
        empty_message()

    section_heading("Quick Data Summary")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Top EV Registration Categories**")
        st.dataframe(categories.head(5), use_container_width=True, hide_index=True)
    with col2:
        st.markdown("**Top Charging Station States**")
        st.dataframe(state_stations.head(5), use_container_width=True, hide_index=True)

# =========================================================
# 10. EV REGISTRATION ANALYTICS
# =========================================================
elif page == "EV Registration Analytics":
    st.markdown('<div class="main-title">EV Registration Analytics</div>', unsafe_allow_html=True)
    st.caption("Analyze historical EV adoption and vehicle-category trends.")
    st.info("The registration dataset contains India-level records, not state-wise records. The state filter does not change these registration charts.")

    col1, col2 = st.columns(2)
    with col1:
        kpi_card("Total Registrations", f"{total_registrations:,}")
    with col2:
        kpi_card("Vehicle Categories", str(len(categories)))

    section_heading("Year-wise EV Registration Trend")
    show_chart(px.line(
        yearly, x="Year", y="Total_Registrations", markers=True,
        title="India's EV Registration Trend"
    ))

    section_heading("Year-over-Year EV Registration Growth")
    growth_data = yearly.dropna(subset=["YoY_Growth_%"])
    if not growth_data.empty:
        show_chart(px.bar(
            growth_data, x="Year", y="YoY_Growth_%",
            title="Year-over-Year Registration Growth (%)"
        ))
    else:
        empty_message("Not enough yearly records to calculate year-over-year growth.")

    section_heading("EV Registrations by Vehicle Category")
    show_chart(px.bar(
        categories.sort_values("Total_Registrations"),
        x="Total_Registrations", y="Vehicle_Category",
        orientation="h", title="Vehicle Category Distribution"
    ))

    section_heading("Yearly Registration Data")
    st.dataframe(yearly, use_container_width=True, hide_index=True)

# =========================================================
# 11. MANUFACTURER ANALYTICS
# =========================================================
elif page == "Manufacturer Analytics":
    st.markdown('<div class="main-title">EV Manufacturer Analytics</div>', unsafe_allow_html=True)
    st.caption("Explore manufacturer locations and their distribution across states.")
    st.caption(f"Showing manufacturer records for: {state_label}")

    c1, c2 = st.columns(2)
    with c1:
        kpi_card("Unique EV Manufacturers", f"{total_makers:,}")
    with c2:
        kpi_card("States with Manufacturer Records", str(filtered_makers["State"].nunique()))

    section_heading("EV Manufacturer Distribution by State")
    if not manufacturer_state.empty:
        fig = px.bar(
            manufacturer_state, x="Total_Manufacturers", y="State",
            orientation="h", title="Number of EV Manufacturers by State"
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        show_chart(fig)
    else:
        empty_message()

    section_heading("Manufacturer Location Records")
    if not filtered_makers.empty:
        st.dataframe(
            filtered_makers.sort_values(["State", "EV Maker"]),
            use_container_width=True, hide_index=True
        )
    else:
        empty_message()

    st.info(
        "This dataset represents manufacturer location records. "
        "It does not measure vehicle sales or market share."
    )

# =========================================================
# 12. CHARGING INFRASTRUCTURE
# =========================================================
elif page == "Charging Infrastructure":
    st.markdown('<div class="main-title">Charging Infrastructure Analysis</div>', unsafe_allow_html=True)
    st.caption("Explore charging station availability, connectors, operators and usage.")
    st.caption(f"Showing charging infrastructure for: {state_label}")

    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Total Stations", f"{total_stations:,}")
    with c2:
        kpi_card("Connector Types", str(filtered_stations["Connector Type"].nunique()))
    with c3:
        kpi_card("Operators", str(filtered_stations["Operator"].nunique()))

    section_heading("Charging Stations by State")
    if not state_stations.empty:
        fig = px.bar(
            state_stations, x="Total_Charging_Stations", y="State",
            orientation="h", title="State-wise Charging Station Distribution"
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        show_chart(fig)
    else:
        empty_message()

    section_heading("Charging Stations by Connector Type")
    if not connector_distribution.empty:
        show_chart(px.bar(
            connector_distribution, x="Connector_Type", y="Total_Stations",
            title="Connector Type Distribution"
        ))
    else:
        empty_message()

    section_heading("Top 10 Charging Station Operators")
    if not operator_distribution.empty:
        fig = px.bar(
            operator_distribution.head(10).sort_values("Total_Stations"),
            x="Total_Stations", y="Operator", orientation="h",
            title="Top 10 EV Charging Station Operators"
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        show_chart(fig)
    else:
        empty_message()

    col1, col2 = st.columns(2)
    with col1:
        if not usage_distribution.empty:
            show_chart(px.bar(
                usage_distribution, x="Total_Stations", y="Usage_Type",
                orientation="h", title="Stations by Usage Type"
            ))
        else:
            empty_message()
    with col2:
        if not usage_distribution.empty:
            show_chart(px.pie(
                usage_distribution, names="Usage_Type", values="Total_Stations",
                hole=0.5, title="Usage Type Share"
            ))
        else:
            empty_message()

    section_heading("Charging Station Power Capacity")
    power_data = filtered_stations.dropna(subset=["Power (kW)"]).copy()
    if not power_data.empty:
        show_chart(px.histogram(
            power_data, x="Power (kW)", nbins=20,
            title="Distribution of Charging Station Power Capacity"
        ))
        st.write("Average charging power:", f"{power_data['Power (kW)'].mean():.2f} kW")
    else:
        st.warning("Power capacity information is unavailable for the selected filter.")

# =========================================================
# 13. GEOGRAPHICAL ANALYSIS
# =========================================================
elif page == "Geographical Analysis":
    st.markdown(

        '<div class="main-title">Geographical Analysis</div>',

        unsafe_allow_html=True

    )

    st.caption(

        "Explore the geographical distribution of EV charging stations."

    )

    st.caption(

        f"Showing geographical information for: {state_label}"

    )

    # Clean geographical coordinates

    map_data = filtered_stations.copy()

    map_data["Latitude"] = pd.to_numeric(

        map_data["Latitude"], errors="coerce"

    )

    map_data["Longitude"] = pd.to_numeric(

        map_data["Longitude"], errors="coerce"

    )

    map_data = map_data.dropna(

        subset=["Latitude", "Longitude"]

    ).copy()

    # Remove invalid geographical coordinates

    map_data = map_data[

        map_data["Latitude"].between(-90, 90)

        & map_data["Longitude"].between(-180, 180)

    ]

    # KPI Cards

    c1, c2, c3 = st.columns(3)
    with c1:

        kpi_card(

            "Charging Stations",

            f"{total_stations:,}"

        )

    with c2:

        kpi_card(

            "Cities Covered",

            f"{filtered_stations['City'].nunique():,}"

        )

    with c3:

        kpi_card(

            "Valid Map Locations",

            f"{len(map_data):,}"

        )

    # Interactive Geographical Map

    section_heading(

        "EV Charging Station Geographical Distribution",

        "Explore charging station locations across India."

    )

    if not map_data.empty:

        if selected_state == "All India":

            map_center = {

                "lat": 20.5937,

                "lon": 78.9629

            }

            map_zoom = 3.5

        else:

            map_center = {

                "lat": map_data["Latitude"].mean(),

                "lon": map_data["Longitude"].mean()

            }

            map_zoom = 5

        # Updated Plotly MapLibre function

        fig = px.scatter_map(

            map_data,

            lat="Latitude",

            lon="Longitude",

            hover_name="Station Name",

            hover_data=[

                "City",

                "State",

                "Operator",

                "Connector Type",

                "Power (kW)"

            ],

            color="State",

            center=map_center,

            zoom=map_zoom,

            height=650,

            map_style="open-street-map",

            title=f"EV Charging Station Locations — {state_label}"

        )

        fig.update_traces(

            marker=dict(size=10, opacity=0.75)

        )

        fig.update_layout(

            margin=dict(

                r=0,

                t=50,

                l=0,

                b=0

            ),

            legend_title_text="State"

        )

        st.plotly_chart(

            fig,

            use_container_width=True

        )

        st.success(

            f"Displaying {len(map_data):,} valid charging station locations."

        )

    else:

        st.warning(

            "No valid latitude and longitude records found for the selected state."

        )

    # City-wise Station Analysis

    section_heading(

        "Station Locations by City",

        "Number of charging stations available in each city and state."

    )
    city_data = (

        filtered_stations

        .groupby(["State", "City"])["Station Name"]

        .nunique()

        .reset_index(name="Total_Stations")

        .sort_values(

            "Total_Stations",

            ascending=False

        )

    )

    if not city_data.empty:

        st.dataframe(

            city_data,

            use_container_width=True,

            hide_index=True,

            height=450

        )

    else:

        empty_message()

    # Connector Analysis

    section_heading(

        "Connector Types in Selected Area"

    )

    if not connector_distribution.empty:

        show_chart(

            px.bar(

                connector_distribution,

                x="Connector_Type",

                y="Total_Stations",

                title=f"Connector Types — {state_label}"

            )

        )

    else:

        empty_message()

    # Operator Analysis

    section_heading(

        "Charging Operators in Selected Area"

    )

    if not operator_distribution.empty:

        fig = px.bar(

            operator_distribution.head(10).sort_values(

                "Total_Stations"

            ),

            x="Total_Stations",

            y="Operator",

            orientation="h",

            title=f"Charging Operators — {state_label}"

        )

        fig.update_layout(

            yaxis={"categoryorder": "total ascending"}

        )

        show_chart(fig)

    else:

        empty_message()

# =========================================================
# 14. BUSINESS INSIGHTS
# =========================================================
elif page == "Business Insights":
    st.markdown('<div class="main-title">Business Insights</div>', unsafe_allow_html=True)
    st.caption("Data-driven findings and recommendations from the SMARTCHARGE datasets.")
    st.caption(f"Infrastructure and manufacturer insights for: {state_label}")

    highest_year = yearly.loc[yearly["Total_Registrations"].idxmax()]
    growth_data = yearly.dropna(subset=["YoY_Growth_%"])
    highest_growth = (
        growth_data.loc[growth_data["YoY_Growth_%"].idxmax()]
        if not growth_data.empty else None
    )

    insights = [
        (
            "EV Registration Leadership",
            f"The highest annual EV registrations occurred in {int(highest_year['Year'])}, "
            f"with {int(highest_year['Total_Registrations']):,} registrations."
        ),
        (
            "Vehicle Category Dominance",
            f"{top_vehicle} is the leading vehicle category in the registration dataset."
        )
    ]

    if not state_stations.empty:
        top_station = state_stations.iloc[0]
        insights.append((
            "Charging Infrastructure Leader",
            f"{top_station['State']} has the highest number of charging stations "
            f"({int(top_station['Total_Charging_Stations'])})."
        ))
    else:
        insights.append(("Charging Infrastructure", "No charging station records are available for this selection."))

    if not manufacturer_state.empty:
        top_maker = manufacturer_state.iloc[0]
        insights.append((
            "Manufacturer Distribution",
            f"{top_maker['State']} has the highest number of unique manufacturer records "
            f"({int(top_maker['Total_Manufacturers'])})."
        ))

    if not connector_distribution.empty:
        top_connector = connector_distribution.iloc[0]
        insights.append((
            "Connector Preference",
            f"{top_connector['Connector_Type']} is the most frequently recorded connector type."
        ))

    if not operator_distribution.empty:
        top_operator = operator_distribution.iloc[0]
        insights.append((
            "Leading Charging Operator",
            f"{top_operator['Operator']} has the highest number of station records "
            f"({int(top_operator['Total_Stations'])})."
        ))

    if not usage_distribution.empty:
        top_usage = usage_distribution.iloc[0]
        insights.append((
            "Charging Usage Pattern",
            f"{top_usage['Usage_Type']} is the most common charging station usage type."
        ))

    for title, description in insights:
        st.markdown(
            f"""
            <div class="insight-card">
                <h4 style="color:#142D4E;">{title}</h4>
                <p style="color:#475569;">{description}</p>
            </div>
            """,
            unsafe_allow_html=True
        )

    if highest_growth is not None:
        st.markdown(
            f"""
            <div class="insight-card">
                <h4 style="color:#142D4E;">Highest Annual Growth</h4>
                <p style="color:#475569;">
                    The highest year-over-year growth was {highest_growth['YoY_Growth_%']:.2f}%
                    in {int(highest_growth['Year'])}.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

    section_heading("Business Recommendations")
    recommendations = [
        "Evaluate states with fewer charging stations to identify potential infrastructure expansion opportunities.",
        "Study the leading vehicle categories when planning EV-related services and charging facilities.",
        "Consider connector compatibility when selecting charging equipment.",
        "Use geographical station data to identify areas that may need additional charging facilities.",
        "Monitor yearly EV registration trends to support long-term infrastructure planning."
    ]
    for i, recommendation in enumerate(recommendations, 1):
        st.markdown(
            f"""
            <div style="
                color: #142D4E;
                background-color: #FFFFFF;
                padding: 14px 18px;
                margin-bottom: 10px;
                border-radius: 10px;
                border-left: 4px solid #06B6D4;
                font-size: 16px;
                line-height: 1.6;
                box-shadow: 0 2px 8px rgba(0,0,0,0.04);
            ">
                <span style="color: #06B6D4; font-weight: 800;">{i}.</span>
                <span style="color: #142D4E; font-weight: 500;">
                    {recommendation}
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )
    st.info(
        "Recommendations are potential business actions based on the observed dataset patterns. "
        "They are not proof of market demand."
    )

# =========================================================
# 15. DATA EXPLORER
# =========================================================
elif page == "Data Explorer":
    st.markdown('<div class="main-title">Data Explorer</div>', unsafe_allow_html=True)
    st.caption("Explore the original cleaned datasets used in this project.")

    dataset_name = st.selectbox(
        "Select Dataset",
        ["EV Registrations", "EV Manufacturers", "Charging Stations"]
    )

    dataset_map = {
        "EV Registrations": registrations,
        "EV Manufacturers": filtered_makers,
        "Charging Stations": filtered_stations
    }
    selected_data = dataset_map[dataset_name]

    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Total Records", f"{selected_data.shape[0]:,}")
    with c2:
        kpi_card("Total Columns", str(selected_data.shape[1]))
    with c3:
        kpi_card("Missing Values", f"{selected_data.isnull().sum().sum():,}")

    section_heading("Dataset Preview")
    st.dataframe(selected_data, use_container_width=True, hide_index=True)

    section_heading("Column Information")
    column_info = pd.DataFrame({
        "Column": selected_data.columns,
        "Data Type": selected_data.dtypes.astype(str).values,
        "Missing Values": selected_data.isnull().sum().values
    })
    st.dataframe(column_info, use_container_width=True, hide_index=True)

    csv = selected_data.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Dataset as CSV",
        data=csv,
        file_name=dataset_name.lower().replace(" ", "_") + ".csv",
        mime="text/csv"
    )


# =========================================================
# 16. FOOTER
# =========================================================
st.markdown("---")
st.markdown(
    """
    <div class="footer">
        ⚡ SMARTCHARGE | EV Analytics Platform<br>
        Built using Python, Pandas, Plotly and Streamlit
    </div>
    """,
    unsafe_allow_html=True
)
