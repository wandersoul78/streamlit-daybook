import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Google Sheets authentication
def authenticate_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('amazing-zephyr-446217-g0-b3478d3380a8.json', scope)
    client = gspread.authorize(creds)
    return client

def append_to_sheet(spreadsheet_id, sheet_name, data):
    client = authenticate_google_sheet()
    workbook = client.open_by_key(spreadsheet_id)  # Open workbook by Spreadsheet ID
    sheet = workbook.worksheet(sheet_name)  # Access the specified sheet
    sheet.append_row(row_data, value_input_option="USER_ENTERED")


# Streamlit app
st.title("")
st.sidebar.header("Input Details")

# User input
sale_items = [
    "Ap25", "Ap50", "Ap5", "1800n", "Rbc", "Ap84", "L10", "L10dbp", 
    "L20", "101n", "L2", "12dbp", "212n", "220n", "C3", "20n", "J20", 
    "5dop", "2n", "6n", "P94", "P90", "P02", "P23", "Dt94","18n","25s","P01","D2","D5"
]
# Date
input_date = st.sidebar.date_input("Date")
formatted_date = input_date.strftime("%m-%d-%Y")  

# Grade
grade = st.sidebar.selectbox("Grade",sale_items)

# Number of lots
num_lots = st.sidebar.number_input("Number of Lots", min_value=1, step=1)

# Raw material inputs
st.sidebar.subheader("Raw Material Quantities Per Lot")
resin_qty = st.sidebar.number_input("Resin Quantity in Kg", min_value=0.0, step=0.1)
mitti_qty = st.sidebar.number_input("Mitti Quantity in Kg", min_value=0.0, step=0.1)
cpw_qty = st.sidebar.number_input("CPW Quantity in Kg", min_value=0.0, step=0.1)
dop_qty = st.sidebar.number_input("Dop/Dbp Quantity in Kg", min_value=0.0, step=0.1)
chemical_qty = st.sidebar.number_input("Chemical Quantity in Kg", min_value=0.0, step=0.1)
other_qty = st.sidebar.number_input("Other Quantity in Kg", min_value=0.0, step=0.1)

# Output weight
output_weight = st.sidebar.number_input("Output Weight", min_value=0.0, step=0.1)

# Calculate lot weight
lot_weight = num_lots * (resin_qty + mitti_qty + cpw_qty + chemical_qty + dop_qty )+ other_qty

# Display calculated data
st.subheader("Summary")
st.write(f"Date: {input_date}")
st.write(f"Grade: {grade}")
st.write(f"Number of Lots: {num_lots}")
st.write(f"Lot Weight: {lot_weight} Kg")
st.write(f"Output Weight: {output_weight} Kg")

# Example Spreadsheet ID and Sheet Name
spreadsheet_id = "1PjGYnPurJgk89EaGRQaMxHbYaI5bpn4GbF3F4NnaCiI"  # Replace with your Spreadsheet ID
sheet_name = "production"  # Replace with your Sheet Name

# Save data to Google Sheet
if st.button("Save Data"):
    row_data = [
        formatted_date, grade, num_lots, resin_qty*num_lots, mitti_qty*num_lots, cpw_qty*num_lots,dop_qty*num_lots, chemical_qty*num_lots, other_qty, lot_weight, output_weight
    ]
    try:
        append_to_sheet(spreadsheet_id, sheet_name, row_data)
        st.success(f"Data saved successfully to {sheet_name} in the specified workbook!")
    except Exception as e:
        st.error(f"An error occurred: {e}")

# Note for Google Sheets API configuration
st.info("Double check the quantities before saving")
