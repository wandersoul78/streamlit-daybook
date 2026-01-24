import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- Google Sheets Authentication ---
def authenticate_gsheets(sheet_id, worksheet_name):
    """
    Authenticate and return a specific worksheet in a Google Sheets document using its ID.
    """
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    creds_dict = dict(st.secrets["gcp_service_account"])  # Load from Streamlit Secrets
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    workbook = client.open_by_key(sheet_id)
    worksheet = workbook.worksheet(worksheet_name)
    return worksheet

# --- Add a new row function ---
def add_to_sheet(sheet, row_data):
    """
    Add a row to the next available row in the Google Sheet.
    """
    sheet.append_row(row_data, value_input_option="USER_ENTERED")

# --- Streamlit App ---
st.set_page_config(page_title="Data Entry", page_icon="📚")
st.title("📚 Data Entry")

st.sidebar.title("Menu")
menu = st.sidebar.radio("Select Action", ["Purchase", "Sale", "Payment/Receipt"])

# --- Google Sheets Setup ---
sheet_id = st.secrets["sheets"]["sheet_id"]  # Sheet ID from secrets
worksheet_name = "Daybook"
sheet = authenticate_gsheets(sheet_id, worksheet_name)

# --- Predefined Party Names ---
purchase_parties = ["Devansh", "Raj", "Bhr", "Samyak", "Aci"]
sale_parties = ["Radha", "Pravesh", "Rc", "Mci", "Jawaharji", "Munishji", "Sanjay", "Narayan", "Drum"]
additional_payment_parties = ["Papa", "Icici", "Fact Exp", "Home Exp", "Gst", "Ranjeet", "Bhure", "Raja", "Mukesh", "Rajender"]
bank_parties = ["Icici"]

# --- Predefined Items ---
purchase_items = ["Resin", "C1000", "C001", "Cpw", "DOP", "Dbp", "Tbls", "Dblp", "Ls", "St", "Op304", "Op318", "Lqd", "Eva", "GST", "Tin"]
sale_items = ["Ap25", "Ap50", "Ap5", "1800n", "Rbc","RBDbp", "Ap84", "L10", "L10dbp", "L20", "101n", "L2", "12dbp", "212n", "220n", "C3", "20n", "J20", "5dop","Dop12", "2n", "6n","115n","15n", "P94", "P90", "P02", "P23","P01", "Dt94","Dop-Al", "GST", "18n", "25s","Drm"]

# --- Menu Options ---
if menu == "Purchase":
    st.header("🛒 Purchase")
    date = st.date_input("Date", datetime.now())
    slip_no = st.text_input("Slip No.")
    party_name = st.selectbox("Party Name", purchase_parties)
    num_items = st.number_input("Number of Items", min_value=1, step=1, value=1)
    items = []

    for i in range(num_items):
        st.subheader(f"Item {i+1}")
        item_type = st.selectbox(f"Item Type {i+1}", purchase_items, key=f"item_type_{i}")
        quantity = st.number_input(f"Quantity {i+1} (kg)", min_value=0.0, step=0.1, key=f"qty_{i}")
        rate = st.number_input(f"Rate {i+1} (per kg)", min_value=0.0, step=0.1, key=f"rate_{i}")

        # GST and TCS
        gst_applied = st.checkbox(f"Apply GST for Item {i+1}", key=f"gst_{i}")
        

        adjusted_rate = rate
        if gst_applied:
            gst_percent = st.number_input(f"GST Percent for Item {i+1}", min_value=0.0, step=0.1, key=f"gst_percent_{i}")
            adjusted_rate += round(rate * gst_percent / 100, 2)
        

        amount = quantity * adjusted_rate
        items.append((item_type, quantity, rate, adjusted_rate, amount))

    if st.button("Add Purchase"):
        for item in items:
            item_type, quantity, rate, adjusted_rate, amount = item
            data = [
                date.strftime("%m-%d-%Y"),
                slip_no,
                "Purchase",
                party_name,
                item_type,
                quantity,
                adjusted_rate,
                amount,
            ]
            add_to_sheet(sheet, data)
        st.success("✅ Purchase added successfully!")

elif menu == "Sale":
    st.header("🛒 Sale")
    date = st.date_input("Date", datetime.now())
    slip_no = st.text_input("Slip No.")
    party_name = st.selectbox("Party Name", sale_parties)
    num_items = st.number_input("Number of Items", min_value=1, step=1, value=1)
    items = []

    for i in range(num_items):
        st.subheader(f"Item {i+1}")
        item_type = st.selectbox(f"Item Type {i+1}", sale_items, key=f"item_type_{i}")
        quantity = st.number_input(f"Quantity {i+1} (kg)", min_value=0.0, step=0.1, key=f"qty_{i}")
        rate = st.number_input(f"Rate {i+1} (per kg)", min_value=0.0, step=0.1, key=f"rate_{i}")

        gst_applied = st.checkbox(f"Apply GST for Item {i+1}", key=f"gst_{i}")
        

        adjusted_rate = rate
        if gst_applied:
            gst_percent = st.number_input(f"GST Percent for Item {i+1}", min_value=0.0, step=0.1, key=f"gst_percent_{i}")
            adjusted_rate += round(rate * gst_percent / 100, 2)
       

        amount = quantity * adjusted_rate
        items.append((item_type, quantity, rate, adjusted_rate, amount))

    if st.button("Add Sale"):
        for item in items:
            item_type, quantity, rate, adjusted_rate, amount = item
            data = [
                date.strftime("%m-%d-%Y"),
                slip_no,
                "Sale",
                party_name,
                item_type,
                quantity,
                adjusted_rate,
                amount,
            ]
            add_to_sheet(sheet, data)
        st.success("✅ Sale added successfully!")

elif menu == "Payment/Receipt":
    st.header("💳 Payment/Receipt")
    date = st.date_input("Date", datetime.now())
    reference = st.text_input("Reference")
    slip_no = st.selectbox("Type", ["Cash", "Bank"])
    combined_parties = sorted(set(purchase_parties + sale_parties + additional_payment_parties))
    party_name = st.selectbox("Party Name", combined_parties)
    voucher_type = st.selectbox("Voucher Type", ["Payment", "Receipt"])
    amount = st.number_input("Amount", min_value=0.0, step=0.1)
     # 👉 Show Bank selector only if Bank is chosen
    bank_name = None
    if slip_no == "Bank":
        bank_name = st.selectbox("Bank Name", bank_parties)
    if st.button("Add Voucher"):
        data = [
            date.strftime("%m-%d-%Y"),
            reference,
            voucher_type,
            party_name,
            slip_no,
            "", "", amount
        ]
        add_to_sheet(sheet, data)
        # ---- BANK ENTRY (reverse) ----
        if slip_no == "Bank":
            reverse_type = "Receipt" if voucher_type == "Payment" else "Payment"
            data = [
                date.strftime("%m-%d-%Y"),
                reference,
                reverse_type,
                bank_name,
                "Bank",
                "",
                "",
                amount
            ]
            add_to_sheet(sheet, data)
        st.success(f"✅ {voucher_type} added successfully!")









