import streamlit as st
import pandas as pd
import plotly.express as px
import folium
import requests
from io import BytesIO
from streamlit_folium import folium_static
from folium.plugins import HeatMap

st.set_page_config(page_title="Used Vehicle Market Analysis", layout="wide")

# --- DATA CONFIGURATION ---
FILE_ID = "17VhcD1SApY6M1escKpKloilcO3XAMeWK"

@st.cache_data(show_spinner="Downloading Data from Cloud...")
def load_data_from_drive(id):
    # This URL handles the "Large File" confirmation from Google Drive
    def get_confirm_token(response):
        for key, value in response.cookies.items():
            if key.startswith('download_warning'):
                return value
        return None

    URL = "https://docs.google.com/uc?export=download"
    session = requests.Session()
    response = session.get(URL, params={'id': id}, stream=True)
    token = get_confirm_token(response)

    if token:
        params = {'id': id, 'confirm': token}
        response = session.get(URL, params=params, stream=True)
    
    try:
        # Read the parquet from the session response
        df = pd.read_parquet(BytesIO(response.content))
        
        # Immediate RAM Optimization
        required_cols = ["manufacturer", "model", "year", "price", "lat", "long", 
                         "cylinders", "fuel", "drive", "type", "transmission"]
        df = df[required_cols]

        # Downcasting and Categories
        df['price'] = pd.to_numeric(df['price'], downcast='float')
        df['year'] = pd.to_numeric(df['year'], downcast='integer')
        for col in ["manufacturer", "fuel", "drive", "type", "transmission"]:
            df[col] = df[col].astype('category')

        return df.dropna(subset=["manufacturer", "model", "year", "price", "lat", "long"])
    except Exception as e:
        st.error(f"Error parsing file: {e}. Ensure the file on Drive is a valid .parquet file.")
        return pd.DataFrame()

# Load data automatically
df = load_data_from_drive(FILE_ID)

# --- SIDEBAR NAVIGATION (NO UPLOADER) ---
st.sidebar.title("Navigation")

if not df.empty:
    page = st.sidebar.radio("Go to", [
        "Home", "Models by Company", "Most Listed Vehicle Brands", 
        "Transmission vs Type", "Manufacturer vs Drive", "Brand-Specific Heatmap"
    ])
else:
    page = "Home"
    st.sidebar.warning("Data loading failed.")

# --- PAGES ---
if page == "Home":
    st.title("🚗 Used Vehicle Market Analysis Dashboard")
    st.markdown("---")
    if not df.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Listings", f"{len(df):,}")
        col2.metric("Unique Brands", df['manufacturer'].nunique())
        col3.metric("Avg Price", f"${df['price'].mean():,.2f}")
        st.dataframe(df.head(10), use_container_width=True)
    else:
        st.error("Dataset not found. Check Drive permissions or ID.")

# [Rest of the visualization code from previous turns remains the same]

elif page == "Models by Company":
    st.subheader("Models by Manufacturer")
    if not df.empty:
        selected_brand = st.selectbox("Choose a Company:", sorted(df['manufacturer'].unique()))
        brand_df = df[df['manufacturer'] == selected_brand].dropna(subset=['model']).copy()
        
        search_query = st.text_input("Search for a model:").lower()
        if search_query:
            brand_df = brand_df[brand_df['model'].astype(str).str.lower().str.contains(search_query)]

        if not brand_df.empty:
            grouped = brand_df.groupby('model', observed=True).agg({
                'price': 'mean',
                'year': lambda x: int(x.median())
            }).reset_index()
            st.dataframe(grouped, use_container_width=True)

# ... (rest of your chart logic goes here, following the same pattern)

elif page == "Brand-Specific Heatmap":
    st.subheader("Heatmap of Selected Brand")
    if not df.empty:
        selected_brand = st.selectbox("Select a Manufacturer:", sorted(df['manufacturer'].unique()))
        brand_df = df[df['manufacturer'] == selected_brand].dropna(subset=['lat', 'long'])
        if not brand_df.empty:
            m = folium.Map(location=[brand_df['lat'].mean(), brand_df['long'].mean()], zoom_start=5)
            HeatMap(brand_df[['lat', 'long']].head(2000).values.tolist()).add_to(m)
            folium_static(m)
