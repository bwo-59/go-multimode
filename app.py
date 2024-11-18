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
except FileNotFoundError:
    st.error("The 'ports.csv' file was not found in the project directory.")
    st.stop()

# Display 10 random ports on a map using Folium
st.header("Port Locations")
random_ports_df = ports_df.sample(n=10)

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
st_data = st_folium(port_map, width=700, height=450)

# Shipment File Upload
st.header("Upload Shipment Excel File")
shipment_file = st.file_uploader(
    "Drag and drop your shipment file here, or click to select",
    type=['xlsx', 'xls'],
    key='shipment'
)

# Input for radius
st.header("Set Search Radius (in kilometers)")
radius_km = st.number_input(
    "Enter the search radius (default is 500 km):",
    min_value=1,
    value=500,
    step=1
)

# Check if the shipment file is uploaded
if shipment_file is not None:
    process_button = st.button("Process Shipments")
else:
    st.info('Please upload the shipment Excel file to proceed.')
    process_button = False

if process_button:
    with st.spinner('Processing your shipments...'):
        # Read shipment data
        try:
            shipments_df = pd.read_excel(shipment_file)
        except Exception as e:
            st.error(f"Error reading the shipment file: {e}")
            st.stop()

        # Check if all required columns are present
        required_columns = [
            'Consignment ID', 'Origin', 'Origin Latitude', 'Origin Longitude',
            'Destination', 'Destination Latitude', 'Destination Longitude',
            'Load (Tons)', 'Customer Name', 'Vehicle Type', 'Date'
        ]

        missing_columns = [col for col in required_columns if col not in shipments_df.columns]

        if missing_columns:
            st.error(f"The following required columns are missing from the shipment data: {', '.join(missing_columns)}")
            st.stop()

        def select_nearest_port(location_coords, ports_df, radius_km):
            # Calculate distance from location to each port
            ports_df['Distance'] = ports_df.apply(
                lambda row: geodesic(location_coords, (row['Latitude'], row['Longitude'])).km,
                axis=1
            )
            # Filter ports within the radius
            nearby_ports = ports_df[ports_df['Distance'] <= radius_km].copy()

            if nearby_ports.empty:
                return None  # No port found within the radius

            # Select the port with the minimum distance
            nearest_port = nearby_ports.loc[nearby_ports['Distance'].idxmin()]
            return nearest_port

        enriched_shipments = []

        for index, shipment in shipments_df.iterrows():
            consignment_id = shipment['Consignment ID']
            customer_name = shipment['Customer Name']
            load_tons = shipment['Load (Tons)']
            vehicle_type = shipment['Vehicle Type']
            date = shipment['Date']

            # Origin and destination coordinates
            origin_coords = (shipment['Origin Latitude'], shipment['Origin Longitude'])
            destination_coords = (shipment['Destination Latitude'], shipment['Destination Longitude'])

            # Select nearest ports near origin and destination
            origin_port = select_nearest_port(origin_coords, ports_df, radius_km)
            destination_port = select_nearest_port(destination_coords, ports_df, radius_km)

            if origin_port is None or destination_port is None:
                st.warning(f"No suitable ports found for shipment {consignment_id}. Skipping.")
                continue  # Skip shipments without suitable ports

            # Create legs
            legs = []

            # Leg 1: Road transport from origin to origin port
            legs.append({
                'ID': consignment_id,
                'Sequence': 1,
                'Origin': shipment['Origin'],
                'Destination': origin_port['Port Name'],
                'Load (Tons)': load_tons,
                'Mode': 'ROAD',
                'Vehicle Type': vehicle_type,
                'Customer Name': customer_name,
                'Date': date
            })

            # Leg 2: Sea transport from origin port to destination port
            legs.append({
                'ID': consignment_id,
                'Sequence': 2,
                'Origin': origin_port['Port Name'],
                'Destination': destination_port['Port Name'],
                'Load (Tons)': load_tons,
                'Mode': 'SEA',
                'Vehicle Type': None,
                'Customer Name': customer_name,
                'Date': date
            })

            # Leg 3: Road transport from destination port to final destination
            legs.append({
                'ID': consignment_id,
                'Sequence': 3,
                'Origin': destination_port['Port Name'],
                'Destination': shipment['Destination'],
                'Load (Tons)': load_tons,
                'Mode': 'ROAD',
                'Vehicle Type': vehicle_type,
                'Customer Name': customer_name,
                'Date': date
            })

            enriched_shipments.extend(legs)

        enriched_shipments_df = pd.DataFrame(enriched_shipments)

        st.header("Enriched Shipment Data")
        st.dataframe(enriched_shipments_df)

        st.header("Download Enriched Data")
        towrite = BytesIO()
        enriched_shipments_df.to_excel(towrite, index=False, engine='openpyxl')
        towrite.seek(0)
        st.download_button(
            label="Download Excel File",
            data=towrite,
            file_name='enriched_shipment_data.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
