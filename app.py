import pandas as pd
from geopy.distance import geodesic
import streamlit as st
from io import BytesIO, StringIO

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

# Shipment File Upload
st.header("Upload Shipment Excel File")
shipment_file = st.file_uploader(
    "Drag and drop your shipment file here, or click to select",
    type=['xlsx', 'xls'],
    key='shipment'
)

# Port data as a CSV string with simplified columns
port_data_csv = """Port Code,Port Name,Latitude,Longitude
NLRTM,Rotterdam,51.9475,4.1427
CNSHG,Shanghai,31.2304,121.4737
DEBRV,Bremerhaven,53.5396,8.5809
USNYC,New York,40.7128,-74.0060
"""

# Read port data into a DataFrame
ports_df = pd.read_csv(StringIO(port_data_csv))

# Check if the shipment file is uploaded
if shipment_file is not None:
    process_button = st.button("Process Shipments")
else:
    st.info('Please upload the shipment Excel file to proceed.')
    process_button = False

if process_button:
    with st.spinner('Processing your shipments...'):
        shipments_df = pd.read_excel(shipment_file)

        def select_nearest_port(location_coords, ports_df, radius_km=500):
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
            origin_port = select_nearest_port(origin_coords, ports_df)
            destination_port = select_nearest_port(destination_coords, ports_df)

            if not origin_port or not destination_port:
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
