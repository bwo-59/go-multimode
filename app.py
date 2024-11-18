import pandas as pd
from geopy.distance import geodesic
import streamlit as st
from io import BytesIO
import folium
from streamlit_folium import st_folium

# Set page configuration
st.set_page_config(
    page_title="Shipment Leg Enrichment Application",
    page_icon="🚚",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Title and Introduction
st.title("Shipment Leg Enrichment Application")
st.write("Upload your shipment data to enrich it with detailed journey legs.")

# Read port data from 'ports.csv' in the project files
try:
    ports_df = pd.read_csv('ports.csv')
    st.write("Port DataFrame Columns:", ports_df.columns.tolist())
    st.write("First few rows of ports_df before cleaning:")
    st.dataframe(ports_df.head())

    # Clean the Latitude and Longitude columns
    ports_df['Latitude'] = pd.to_numeric(ports_df['Latitude'], errors='coerce')
    ports_df['Longitude'] = pd.to_numeric(ports_df['Longitude'], errors='coerce')

    # Drop rows with invalid Latitude or Longitude
    ports_df = ports_df.dropna(subset=['Latitude', 'Longitude'])

    # Check if ports_df is empty
    if ports_df.empty:
        st.error("No valid port data available after cleaning. Please check your 'ports.csv' file.")
        st.stop()

    st.write("Port DataFrame Columns after cleaning:", ports_df.columns.tolist())
    st.write("Number of rows in ports_df after cleaning:", len(ports_df))
    st.write("First few rows of ports_df after cleaning:")
    st.dataframe(ports_df.head())

except FileNotFoundError:
    st.error("The 'ports.csv' file was not found in the project directory.")
    st.stop()

# Display 10 random ports on a map using Folium
st.header("Port Locations")

num_ports = min(10, len(ports_df))
random_ports_df = ports_df.sample(n=num_ports)

# Check if random_ports_df is empty
if random_ports_df.empty:
    st.error("No ports available to display on the map.")
    st.stop()
else:
    st.write("Random Ports DataFrame Columns:", random_ports_df.columns.tolist())
    st.write("Number of rows in random_ports_df:", len(random_ports_df))
    st.dataframe(random_ports_df.head())

    # Create a Folium map centered on the average coordinates of the ports
    average_lat = random_ports_df['Latitude'].mean()
    average_lon = random_ports_df['Longitude'].mean()

    port_map = folium.Map(location=[average_lat, average_lon], zoom_start=2)

    # Add port markers to the map
    for index, row in random_ports_df.iterrows():
        folium.Marker(
            location=[row['Latitude'], row['Longitude']],
            popup=row['Port Name'],
            tooltip=row['Port Name'],
            icon=folium.Icon(color='blue', icon='ship', prefix='fa')
        ).add_to(port_map)

    # Display the map in Streamlit
    st_folium(port_map, width=700, height=450)

# Rest of your code...
