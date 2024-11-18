import pandas as pd
from geopy.distance import geodesic
import streamlit as st
from io import BytesIO
import folium
from streamlit_folium import st_folium
from pyproj import Geod  # Import pyproj for geodesic calculations

# Set page configuration
st.set_page_config(
    page_title="Shipment Leg Enrichment Application",
    page_icon="🚚",
    layout="wide",
)

# Hide Streamlit's default menu and footer
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Title and Introduction
st.title("📦 Shipment Leg Enrichment Application")
st.write("""
This application allows you to upload your shipment data and enrich it with detailed journey legs based on the nearest ports. Follow the steps below to get started.
""")

# Sidebar for inputs
st.sidebar.header("User Inputs")

# Input for search radius
radius_km = st.sidebar.number_input(
    "Set Search Radius (in kilometers):",
    min_value=1,
    value=500,
    step=1,
    help="Set the search radius for finding the nearest ports."
)

# Shipment File Upload
shipment_file = st.sidebar.file_uploader(
    "Upload Shipment Excel File:",
    type=['xlsx', 'xls'],
    help="Upload an Excel file containing your shipment data."
)

# Read port data from 'ports.csv' in the project files
@st.cache_data
def load_ports_data():
    try:
        ports_df = pd.read_csv('ports.csv')
        # Clean column names and handle invalid data
        ports_df.columns = ports_df.columns.str.strip()
        # Convert Latitude and Longitude to numeric and drop invalid rows
        ports_df['Latitude'] = pd.to_numeric(ports_df['Latitude'], errors='coerce')
        ports_df['Longitude'] = pd.to_numeric(ports_df['Longitude'], errors='coerce')
        ports_df.dropna(subset=['Latitude', 'Longitude'], inplace=True)
        return ports_df
    except FileNotFoundError:
        st.error("The 'ports.csv' file was not found in the project directory.")
        return None

ports_df = load_ports_data()

if ports_df is not None:
    # Cache the map creation to prevent reloading
    @st.cache_resource
    def create_port_map(ports_df):
        # Display 10 random ports on a map using Folium
        random_ports_df = ports_df.sample(n=min(10, len(ports_df)))
        # Create a Folium map centered on the average coordinates of the ports
        average_lat = random_ports_df['Latitude'].mean()
        average_lon = random_ports_df['Longitude'].mean()
        port_map = folium.Map(location=[average_lat, average_lon], zoom_start=2)
        # Add port markers to the map
        for _, row in random_ports_df.iterrows():
            folium.Marker(
                location=[row['Latitude'], row['Longitude']],
                popup=f"{row['Port Name']} ({row['Port Code']})",
                tooltip=row['Port Name'],
                icon=folium.Icon(color='blue', icon='ship', prefix='fa')
            ).add_to(port_map)
        return port_map

    st.header("Port Locations")
    # Use the cached map
    port_map = create_port_map(ports_df)
    st_folium(port_map, width=700, height=450)

    # Process the shipment file if uploaded
    if shipment_file is not None:
        st.header("Shipment Data Processing")
        try:
            shipments_df = pd.read_excel(shipment_file)
            # Ensure required columns are present
            required_columns = [
                'Consignment ID', 'Origin', 'Origin Latitude', 'Origin Longitude',
                'Destination', 'Destination Latitude', 'Destination Longitude',
                'Load (Tons)', 'Customer Name', 'Vehicle Type', 'Date'
            ]
            missing_columns = [col for col in required_columns if col not in shipments_df.columns]
            if missing_columns:
                st.error(f"The following required columns are missing: {', '.join(missing_columns)}")
            else:
                # Convert coordinate columns to numeric
                coordinate_columns = ['Origin Latitude', 'Origin Longitude', 'Destination Latitude', 'Destination Longitude']
                for col in coordinate_columns:
                    shipments_df[col] = pd.to_numeric(shipments_df[col], errors='coerce')
                # Drop rows with invalid coordinates
                shipments_df.dropna(subset=coordinate_columns, inplace=True)
                if shipments_df.empty:
                    st.warning("No valid shipment data found after cleaning. Please check your file.")
                else:
                    # Process Shipments
                    if st.button("Process Shipments"):
                        with st.spinner('Processing your shipments...'):
                            enriched_shipments = []

                            def select_nearest_port(location_coords):
                                # Calculate distance from location to each port
                                ports_df['Distance'] = ports_df.apply(
                                    lambda row: geodesic(location_coords, (row['Latitude'], row['Longitude'])).km,
                                    axis=1
                                )
                                # Filter ports within the radius
                                nearby_ports = ports_df[ports_df['Distance'] <= radius_km].copy()
                                if nearby_ports.empty:
                                    return None
                                # Select the port with the minimum distance
                                nearest_port = nearby_ports.loc[nearby_ports['Distance'].idxmin()]
                                return nearest_port

                            for _, shipment in shipments_df.iterrows():
                                consignment_id = shipment['Consignment ID']
                                customer_name = shipment['Customer Name']
                                load_tons = shipment['Load (Tons)']
                                vehicle_type = shipment['Vehicle Type']
                                date = shipment['Date']

                                # Origin and destination coordinates
                                origin_coords = (shipment['Origin Latitude'], shipment['Origin Longitude'])
                                destination_coords = (shipment['Destination Latitude'], shipment['Destination Longitude'])

                                # Select nearest ports near origin and destination
                                origin_port = select_nearest_port(origin_coords)
                                destination_port = select_nearest_port(destination_coords)

                                if origin_port is None or destination_port is None:
                                    st.warning(f"No suitable ports found within {radius_km} km for shipment {consignment_id}. Skipping.")
                                    continue

                                # Create legs
                                legs = [
                                    {
                                        'ID': consignment_id,
                                        'Sequence': 1,
                                        'Origin': shipment['Origin'],
                                        'Destination': origin_port['Port Name'],
                                        'Origin Latitude': shipment['Origin Latitude'],
                                        'Origin Longitude': shipment['Origin Longitude'],
                                        'Destination Latitude': origin_port['Latitude'],
                                        'Destination Longitude': origin_port['Longitude'],
                                        'Load (Tons)': load_tons,
                                        'Mode': 'ROAD',
                                        'Vehicle Type': vehicle_type,
                                        'Customer Name': customer_name,
                                        'Date': date
                                    },
                                    {
                                        'ID': consignment_id,
                                        'Sequence': 2,
                                        'Origin': origin_port['Port Name'],
                                        'Destination': destination_port['Port Name'],
                                        'Origin Latitude': origin_port['Latitude'],
                                        'Origin Longitude': origin_port['Longitude'],
                                        'Destination Latitude': destination_port['Latitude'],
                                        'Destination Longitude': destination_port['Longitude'],
                                        'Load (Tons)': load_tons,
                                        'Mode': 'SEA',
                                        'Vehicle Type': None,
                                        'Customer Name': customer_name,
                                        'Date': date
                                    },
                                    {
                                        'ID': consignment_id,
                                        'Sequence': 3,
                                        'Origin': destination_port['Port Name'],
                                        'Destination': shipment['Destination'],
                                        'Origin Latitude': destination_port['Latitude'],
                                        'Origin Longitude': destination_port['Longitude'],
                                        'Destination Latitude': shipment['Destination Latitude'],
                                        'Destination Longitude': shipment['Destination Longitude'],
                                        'Load (Tons)': load_tons,
                                        'Mode': 'ROAD',
                                        'Vehicle Type': vehicle_type,
                                        'Customer Name': customer_name,
                                        'Date': date
                                    }
                                ]
                                enriched_shipments.extend(legs)

                            if enriched_shipments:
                                enriched_shipments_df = pd.DataFrame(enriched_shipments)
                                st.success("Shipments processed successfully!")
                                st.subheader("Enriched Shipment Data")
                                st.dataframe(enriched_shipments_df)

                                # Download button
                                def convert_df(df):
                                    output = BytesIO()
                                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                                        df.to_excel(writer, index=False, sheet_name='Enriched Shipments')
                                    processed_data = output.getvalue()
                                    return processed_data

                                excel_data = convert_df(enriched_shipments_df)
                                st.download_button(
                                    label="Download Enriched Data as Excel",
                                    data=excel_data,
                                    file_name='enriched_shipments.xlsx',
                                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                                )

                                # Visualization Section
                                st.subheader("Visualize Shipment Route")
                                shipment_ids = enriched_shipments_df['ID'].unique()
                                selected_id = st.selectbox("Select a Shipment ID to visualize:", shipment_ids)
                                if selected_id:
                                    selected_shipment = enriched_shipments_df[enriched_shipments_df['ID'] == selected_id]
                                    # Create a map centered at the average location of the shipment legs
                                    avg_lat = selected_shipment[['Origin Latitude', 'Destination Latitude']].mean().mean()
                                    avg_lon = selected_shipment[['Origin Longitude', 'Destination Longitude']].mean().mean()
                                    shipment_map = folium.Map(location=[avg_lat, avg_lon], zoom_start=4)
                                    geod = Geod(ellps="WGS84")  # Initialize Geod

                                    # Function to get geodesic line
                                    def get_geodesic_line(lat1, lon1, lat2, lon2, n_points=30):
                                        lons, lats = geod.npts(lon1, lat1, lon2, lat2, n_points)
                                        # Add start and end points
                                        lats = [lat1] + lats + [lat2]
                                        lons = [lon1] + lons + [lon2]
                                        return list(zip(lats, lons))

                                    # Add markers and curved lines for each leg
                                    for _, leg in selected_shipment.iterrows():
                                        origin = (leg['Origin Latitude'], leg['Origin Longitude'])
                                        destination = (leg['Destination Latitude'], leg['Destination Longitude'])
                                        mode = leg['Mode']
                                        # Set color based on mode
                                        if mode == 'SEA':
                                            color = 'darkblue'
                                        else:  # ROAD
                                            color = 'saddlebrown'
                                        # Generate geodesic line
                                        line = get_geodesic_line(origin[0], origin[1], destination[0], destination[1])
                                        # Add line
                                        folium.PolyLine(
                                            line,
                                            color=color,
                                            weight=5,
                                            opacity=0.8,
                                            tooltip=f"{mode} leg from {leg['Origin']} to {leg['Destination']}"
                                        ).add_to(shipment_map)
                                        # Add markers
                                        folium.Marker(
                                            location=origin,
                                            popup=leg['Origin'],
                                            icon=folium.Icon(color='green' if mode == 'ROAD' else 'blue')
                                        ).add_to(shipment_map)
                                        folium.Marker(
                                            location=destination,
                                            popup=leg['Destination'],
                                            icon=folium.Icon(color='green' if mode == 'ROAD' else 'blue')
                                        ).add_to(shipment_map)
                                    # Display the map
                                    st_folium(shipment_map, width=700, height=450)

                                    # Option to save the map
                                    map_html = shipment_map.get_root().render()
                                    st.download_button(
                                        label="Download Map as HTML",
                                        data=map_html,
                                        file_name=f'shipment_{selected_id}_map.html',
                                        mime='text/html'
                                    )
                            else:
                                st.warning("No shipments were processed. Please adjust the search radius or check your shipment data.")
        except Exception as e:
            st.error(f"An error occurred while processing the shipment file: {e}")
    else:
        st.info("Please upload a shipment Excel file to proceed.")
else:
    st.error("Port data could not be loaded. Please ensure 'ports.csv' is present in the project directory.")
