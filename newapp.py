import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# --- Google Sheets authentication using st.secrets ---
def authenticate_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    # Load credentials from st.secrets
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

def append_to_sheet(sheet_id, sheet_name, data):
    client = authenticate_google_sheet()
    workbook = client.open_by_key(sheet_id)  # Open workbook by Spreadsheet ID
    sheet = workbook.worksheet(sheet_name)  # Access the specified sheet
    sheet.append_row(data, value_input_option="USER_ENTERED")

# --- Streamlit App ---
st.title("")
st.sidebar.header("Input Details")

# Sale Items
sale_items = [
    "Ap25", "Ap50", "Ap5", "1800n", "Rbc", "Ap84", "L10", "L10dbp", 
    "L20", "101n", "L2", "12dbp", "212n", "220n", "C3", "20n", "J20", 
    "5dop", "2n", "6n", "P94", "P90", "P02", "P23", "Dt94", "18n", "25s", "P01", "D2", "D5"
]

# Inputs
input_date = st.sidebar.date_input("Date")
formatted_date = input_date.strftime("%m-%d-%Y")

grade = st.sidebar.selectbox("Grade", sale_items)
num_lots = st.sidebar.number_input("Number of Lots", min_value=1, step=1)

st.sidebar.subheader("Raw Material Quantities Per Lot")
resin_qty = st.sidebar.number_input("Resin Quantity in Kg", min_value=0.0, step=0.1)
mitti_qty = st.sidebar.number_input("Mitti Quantity in Kg", min_value=0.0, step=0.1)
cpw_qty = st.sidebar.number_input("CPW Quantity in Kg", min_value=0.0, step=0.1)
dop_qty = st.sidebar.number_input("Dop/Dbp Quantity in Kg", min_value=0.0, step=0.1)
chemical_qty = st.sidebar.number_input("Chemical Quantity in Kg", min_value=0.0, step=0.1)
other_qty = st.sidebar.number_input("Other Quantity in Kg", min_value=0.0, step=0.1)

output_weight = st.sidebar.number_input("Output Weight", min_value=0.0, step=0.1)

# Lot weight calculation
lot_weight = num_lots * (resin_qty + mitti_qty + cpw_qty + chemical_qty + dop_qty) + other_qty

# Display
st.subheader("Summary")
st.write(f"Date: {input_date}")
st.write(f"Grade: {grade}")
st.write(f"Number of Lots: {num_lots}")
st.write(f"Lot Weight: {lot_weight} Kg")
st.write(f"Output Weight: {output_weight} Kg")

# Spreadsheet ID and Sheet Name from secrets
sheet_id = st.secrets["sheets"]["sheet_id"]
sheet_name = "production"

# Save Data Button
if st.button("Save Data"):
    row_data = [
        formatted_date, grade, num_lots,
        resin_qty * num_lots,
        mitti_qty * num_lots,
        cpw_qty * num_lots,
        dop_qty * num_lots,
        chemical_qty * num_lots,
        other_qty,
        lot_weight,
        output_weight
    ]
    try:
        append_to_sheet(sheet_id, sheet_name, row_data)
        st.success(f"Data saved successfully to {sheet_name} in the specified workbook!")
    except Exception as e:
        st.error(f"An error occurred: {e}")

st.info("Double check the quantities before saving.")
