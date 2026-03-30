import streamlit as st
import pandas as pd
import plotly.express as px
import folium
import requests
from io import BytesIO
from streamlit_folium import folium_static
from folium.plugins import HeatMap

# Set Page Config
st.set_page_config(page_title="Used Vehicle Market Analysis", layout="wide")

# --- DATA CONFIGURATION ---
# Your provided Google Drive File ID
FILE_ID = "17VhcD1SApY6M1escKpKloilcO3XAMeWK"

@st.cache_data(show_spinner="Downloading dataset from Google Drive...")
def load_data_from_drive(file_id):
    url = f'https://drive.google.com/uc?export=download&id={file_id}'
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        # Load the Parquet data
        df = pd.read_parquet(BytesIO(response.content))
        
        # 1. Immediate RAM Optimization: Drop columns not used in your visuals
        required_cols = ["manufacturer", "model", "year", "price", "lat", "long", 
                         "cylinders", "fuel", "drive", "type", "transmission"]
        df = df[required_cols]

        # 2. Memory Optimization: Downcast numbers
        df['price'] = pd.to_numeric(df['price'], downcast='float')
        df['year'] = pd.to_numeric(df['year'], downcast='integer')

        # 3. Memory Optimization: Convert strings to categories
        cat_cols = ["manufacturer", "fuel", "drive", "type", "transmission"]
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].astype('category')

        # 4. Final Clean
        df = df.dropna(subset=["manufacturer", "model", "year", "price", "lat", "long"])
        return df
    except Exception as e:
        st.error(f"Error loading data from Drive: {e}")
        return pd.DataFrame()

# Load the data automatically
df = load_data_from_drive(FILE_ID)

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("Navigation")
if not df.empty:
    page = st.sidebar.radio("Go to", [
        "Home", 
        "Models by Company",
        "Most Listed Vehicle Brands", 
        "Transmission vs Type", 
        "Manufacturer vs Drive", 
        "Brand-Specific Heatmap"
    ])
else:
    st.sidebar.error("Dataset could not be loaded. Check your File ID or sharing settings.")
    page = "Home"

# --- PAGES ---
if page == "Home":
    st.title("🚗 Used Vehicle Market Analysis Dashboard")
    st.markdown("---")
    st.markdown("### Welcome!")
    st.markdown("""
    Dive into insights from the used vehicle market across the US. 
    This dashboard lets you **explore car listings** with interactive maps, charts, and filters.
    """)
    
    if not df.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Listings", f"{len(df):,}")
        with col2:
            st.metric("Unique Brands", df['manufacturer'].nunique())
        with col3:
            st.metric("Unique Models", df['model'].nunique())

        st.markdown("---")
        st.markdown("### Dataset Preview")
        st.dataframe(df.head(10), use_container_width=True)

elif page == "Models by Company":
    st.subheader("Models by Manufacturer")
    if not df.empty:
        selected_brand = st.selectbox("Choose a Company:", sorted(df['manufacturer'].unique()))
        brand_df = df[df['manufacturer'] == selected_brand].dropna(subset=['model']).copy()
        brand_df['model'] = brand_df['model'].astype(str)

        search_query = st.text_input("Search for a specific model (optional):").lower()
        if search_query:
            brand_df = brand_df[brand_df['model'].str.lower().str.contains(search_query)]

        if not brand_df.empty:
            # Added observed=True for categorical data handling
            grouped = brand_df.groupby('model', observed=True).agg({
                'price': 'mean',
                'drive': lambda x: x.mode().iat[0] if not x.mode().empty else 'N/A',
                'type': lambda x: x.mode().iat[0] if not x.mode().empty else 'N/A',
                'transmission': lambda x: x.mode().iat[0] if not x.mode().empty else 'N/A',
                'fuel': lambda x: x.mode().iat[0] if not x.mode().empty else 'N/A',
                'cylinders': lambda x: x.mode().iat[0] if not x.mode().empty else 'N/A',
                'year': lambda x: int(x.median()) if not x.isnull().all() else 'N/A'
            }).reset_index()

            for _, row in grouped.iterrows():
                with st.expander(f"Model: {row['model']}"):
                    st.write(f"**Avg Price:** ${row['price']:,.2f} | **Median Year:** {row['year']}")
                    st.write(f"**Specs:** {row['drive']} drive, {row['type']} type, {row['transmission']} transmission")
                    st.write(f"**Engine:** {row['fuel']} fuel, {row['cylinders']} cylinders")
        else:
            st.warning("No models found.")

elif page == "Most Listed Vehicle Brands":
    st.subheader("Most Listed Vehicle Brands")
    if not df.empty:
        manufacturer_counts = df.manufacturer.value_counts().nlargest(10)
        fig_manu = px.pie(names=manufacturer_counts.index, values=manufacturer_counts.values, title="Top 10 Manufacturers")
        st.plotly_chart(fig_manu, use_container_width=True)

elif page == "Transmission vs Type":
    st.subheader("Transmission vs Type")
    if not df.empty:
        fig_trans_type = px.histogram(df, x="transmission", color="type", title="Transmission vs Type", barmode="group")
        st.plotly_chart(fig_trans_type, use_container_width=True)

elif page == "Manufacturer vs Drive":
    st.subheader("Manufacturer vs Drive")
    if not df.empty:
        fig_manufacturer_drive = px.bar(df, x="manufacturer", color="drive", title="Manufacturer vs Drive", barmode="group")
        st.plotly_chart(fig_manufacturer_drive, use_container_width=True)

elif page == "Brand-Specific Heatmap":
    st.subheader("Heatmap of Selected Brand")
    if not df.empty:
        selected_brand = st.selectbox("Select a Manufacturer:", sorted(df['manufacturer'].unique()))
        brand_df = df[df['manufacturer'] == selected_brand].dropna(subset=['lat', 'long'])

        if not brand_df.empty:
            # Average location for the map center
            avg_lat = brand_df['lat'].mean()
            avg_long = brand_df['long'].mean()
            
            map_brand_specific = folium.Map(location=[avg_lat, avg_long], zoom_start=5)
            # Limit points to 2000 for browser performance
            heat_data = brand_df[['lat', 'long']].head(2000).values.tolist()
            HeatMap(heat_data, min_opacity=0.3, radius=15, blur=10).add_to(map_brand_specific)
            folium_static(map_brand_specific)
        else:
            st.warning("No location data available for this manufacturer.")
