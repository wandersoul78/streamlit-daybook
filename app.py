import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import pandas as pd
from fpdf import FPDF
import io
import time

# ---------------------------------------------------------------------------
# 1. Authentication & Google Sheets connection
# ---------------------------------------------------------------------------
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_resource
def get_gspread_client():
    creds_info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_resource
def get_workbook():
    client = get_gspread_client()
    return client.open_by_key(st.secrets["sheets"]["sheet_id"])


# ---------------------------------------------------------------------------
# 2. Sheet helpers — with batch writes & retry
# ---------------------------------------------------------------------------
def append_row(worksheet_name: str, row_data: list, retries: int = 2):
    for attempt in range(retries + 1):
        try:
            wb = get_workbook()
            ws = wb.worksheet(worksheet_name)
            ws.append_row(row_data, value_input_option="USER_ENTERED")
            return True
        except gspread.exceptions.APIError as e:
            if attempt < retries and "RATE_LIMIT" in str(e):
                time.sleep(2)
                continue
            st.error(f"Error writing to {worksheet_name}: {e}")
            return False
        except Exception as e:
            st.error(f"Error writing to {worksheet_name}: {e}")
            return False


def append_rows_batch(worksheet_name: str, rows: list[list], retries: int = 2):
    """Batch-append multiple rows in a single API call (much faster)."""
    for attempt in range(retries + 1):
        try:
            wb = get_workbook()
            ws = wb.worksheet(worksheet_name)
            ws.append_rows(rows, value_input_option="USER_ENTERED")
            return True
        except gspread.exceptions.APIError as e:
            if attempt < retries and "RATE_LIMIT" in str(e):
                time.sleep(2)
                continue
            st.error(f"Error writing to {worksheet_name}: {e}")
            return False
        except Exception as e:
            st.error(f"Error writing to {worksheet_name}: {e}")
            return False


@st.cache_data(ttl=120)
def read_all_rows(worksheet_name: str) -> list[dict]:
    try:
        wb = get_workbook()
        ws = wb.worksheet(worksheet_name)
        records = ws.get_all_records()
        return records if records else []
    except gspread.exceptions.WorksheetNotFound:
        return []
    except Exception as e:
        st.error(f"Error reading {worksheet_name}: {e}")
        return []


def read_all_values(worksheet_name: str) -> list[list]:
    """Return raw rows including header as list of lists."""
    try:
        wb = get_workbook()
        ws = wb.worksheet(worksheet_name)
        return ws.get_all_values()
    except Exception as e:
        st.error(f"Error reading {worksheet_name}: {e}")
        return []


def update_row(worksheet_name: str, row_index: int, row_data: list):
    """Update a row (1-indexed, row 1 = header)."""
    try:
        wb = get_workbook()
        ws = wb.worksheet(worksheet_name)
        for col_idx, value in enumerate(row_data, start=1):
            ws.update_cell(row_index, col_idx, value)
        return True
    except Exception as e:
        st.error(f"Error updating row in {worksheet_name}: {e}")
        return False


def delete_row(worksheet_name: str, row_index: int):
    """Delete a row (1-indexed)."""
    try:
        wb = get_workbook()
        ws = wb.worksheet(worksheet_name)
        ws.delete_rows(row_index)
        return True
    except Exception as e:
        st.error(f"Error deleting row in {worksheet_name}: {e}")
        return False


# ---------------------------------------------------------------------------
# 3. Master-data helpers
# ---------------------------------------------------------------------------
PARTIES_SHEET = "Parties"
ITEMS_SHEET = "Items"
DAYBOOK_SHEET = "Daybook"
OPENING_BAL_SHEET = "Opening Balances"

# Default seed data (migrated from the old hardcoded lists)
DEFAULT_PARTIES = [
    ("Devansh", "Purchase"), ("Raj", "Purchase"), ("Bhr", "Purchase"),
    ("Samyak", "Purchase"), ("Aci", "Purchase"),
    ("Radha", "Sale"), ("Pravesh", "Sale"), ("Rc", "Sale"),
    ("Mci", "Sale"), ("Jawaharji", "Sale"), ("Munishji", "Sale"),
    ("Sanjay", "Sale"), ("Narayan", "Sale"), ("Drum", "Sale"),
    ("Papa", "Payment"), ("Fact Exp", "Payment"), ("Home Exp", "Payment"),
    ("Gst", "Payment"), ("Ranjeet", "Payment"), ("Bhure", "Payment"),
    ("Raja", "Payment"), ("Mukesh", "Payment"), ("Rajender", "Payment"),
    ("Icici", "Bank"),
]

DEFAULT_ITEMS = [
    ("Resin", "Purchase"), ("C1000", "Purchase"), ("C001", "Purchase"),
    ("Cpw", "Purchase"), ("DOP", "Purchase"), ("Dbp", "Purchase"),
    ("Tbls", "Purchase"), ("Dblp", "Purchase"), ("Ls", "Purchase"),
    ("St", "Purchase"), ("Op304", "Purchase"), ("Op318", "Purchase"),
    ("Lqd", "Purchase"), ("Eva", "Purchase"), ("GST", "Purchase"),
    ("Tin", "Purchase"),
    ("Ap25", "Sale"), ("Ap50", "Sale"), ("Ap5", "Sale"), ("1800n", "Sale"),
    ("Rbc", "Sale"), ("RBDbp", "Sale"), ("Ap84", "Sale"), ("L10", "Sale"),
    ("L10dbp", "Sale"), ("L20", "Sale"), ("101n", "Sale"), ("L2", "Sale"),
    ("12dbp", "Sale"), ("212n", "Sale"), ("220n", "Sale"), ("C3", "Sale"),
    ("20n", "Sale"), ("J20", "Sale"), ("5dop", "Sale"), ("Dop12", "Sale"),
    ("2n", "Sale"), ("6n", "Sale"), ("115n", "Sale"), ("15n", "Sale"),
    ("P94", "Sale"), ("P90", "Sale"), ("P02", "Sale"), ("P23", "Sale"),
    ("P01", "Sale"), ("Dt94", "Sale"), ("Dop-Al", "Sale"), ("GST", "Sale"),
    ("18n", "Sale"), ("25s", "Sale"), ("Drm", "Sale"),
]


def ensure_sheet_exists(sheet_name: str, headers: list[str]):
    """Create a worksheet tab if it doesn't exist yet."""
    wb = get_workbook()
    try:
        wb.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = wb.add_worksheet(title=sheet_name, rows=200, cols=len(headers))
        ws.append_row(headers, value_input_option="USER_ENTERED")


def _migrate_opening_balances_sheet():
    """Migrate old 3-column Opening Balances sheet to 4-column (with Date)."""
    try:
        wb = get_workbook()
        ws = wb.worksheet(OPENING_BAL_SHEET)
        header = ws.row_values(1)
        if header and "Date" not in header:
            all_vals = ws.get_all_values()
            default_date = date(date.today().year, 4, 1).strftime("%m-%d-%Y")
            new_rows = [["Party Name", "Date", "Debit", "Credit"]]
            for row in all_vals[1:]:
                if row and row[0]:
                    dr = row[1] if len(row) > 1 else 0
                    cr = row[2] if len(row) > 2 else 0
                    new_rows.append([row[0], default_date, dr, cr])
            ws.clear()
            ws.update(range_name="A1", values=new_rows, value_input_option="USER_ENTERED")
            read_all_rows.clear()
    except Exception:
        pass  # Don't crash app if migration fails


def seed_master_data():
    """One-time migration: populate Parties/Items sheets if they are empty."""
    ensure_sheet_exists(PARTIES_SHEET, ["Name", "Category"])
    ensure_sheet_exists(ITEMS_SHEET, ["Name", "Category"])
    ensure_sheet_exists(OPENING_BAL_SHEET, ["Party Name", "Date", "Debit", "Credit"])
    _migrate_opening_balances_sheet()

    if len(read_all_values(PARTIES_SHEET)) <= 1:
        wb = get_workbook()
        ws = wb.worksheet(PARTIES_SHEET)
        ws.append_rows([[n, c] for n, c in DEFAULT_PARTIES], value_input_option="USER_ENTERED")
        read_all_rows.clear()

    if len(read_all_values(ITEMS_SHEET)) <= 1:
        wb = get_workbook()
        ws = wb.worksheet(ITEMS_SHEET)
        ws.append_rows([[n, c] for n, c in DEFAULT_ITEMS], value_input_option="USER_ENTERED")
        read_all_rows.clear()


def get_opening_balance(party_name: str, start_date: date) -> tuple[float, bool]:
    """Return stored opening balance for a party if its date <= start_date.

    Returns (balance, found) where balance = Debit - Credit.
    Only applied if the opening balance date falls on or before start_date.
    """
    rows = read_all_rows(OPENING_BAL_SHEET)
    for r in rows:
        if r.get("Party Name", "") == party_name:
            ob_date_str = r.get("Date", "")
            try:
                ob_date = datetime.strptime(ob_date_str, "%m-%d-%Y").date()
            except (ValueError, TypeError):
                ob_date = None
            if ob_date and ob_date > start_date:
                return 0.0, False
            dr = float(r.get("Debit", 0) or 0)
            cr = float(r.get("Credit", 0) or 0)
            return dr - cr, True
    return 0.0, False


@st.cache_data(ttl=300)
def get_parties(category: str = "") -> list[str]:
    rows = read_all_rows(PARTIES_SHEET)
    if category:
        return sorted({r["Name"] for r in rows if r.get("Category") == category})
    return sorted({r["Name"] for r in rows})


@st.cache_data(ttl=300)
def get_items(category: str = "") -> list[str]:
    rows = read_all_rows(ITEMS_SHEET)
    if category:
        return sorted({r["Name"] for r in rows if r.get("Category") == category})
    return sorted({r["Name"] for r in rows})

def calculate_party_balance(party: str, upto_date: date = None) -> float:
    """
    Calculate final balance for a party till a given date.
    If upto_date is None → calculates till today.
    Logic:
    Sale + Payment  → Debit
    Purchase + Receipt → Credit
    Balance = Debit - Credit
    """

    if upto_date is None:
        upto_date = date.today()

    rows = read_all_rows(DAYBOOK_SHEET)

    # Start with stored opening balance
    opening_balance, has_ob = get_opening_balance(party, upto_date)
    balance = opening_balance

    # Get OB date to skip earlier entries
    ob_date = None
    if has_ob:
        ob_rows = read_all_rows(OPENING_BAL_SHEET)
        for r in ob_rows:
            if r.get("Party Name", "") == party:
                try:
                    ob_date = datetime.strptime(r.get("Date", ""), "%m-%d-%Y").date()
                except:
                    pass
                break

    for r in rows:
        if r.get("Party Name", r.get("Party", "")) != party:
            continue

        try:
            d = datetime.strptime(r.get("Date", ""), "%m-%d-%Y").date()
        except:
            continue

        # Skip entries before OB date (already included)
        if ob_date and d < ob_date:
            continue

        if d > upto_date:
            continue

        vtype = r.get("Voucher Type", r.get("Type", ""))
        amt = float(r.get("Amount", 0) or 0)

        # YOUR REQUIRED LOGIC
        if vtype in ("Sale", "Payment"):
            balance += amt
        elif vtype in ("Purchase", "Receipt"):
            balance -= amt

    return balance


# ---------------------------------------------------------------------------
# 4. Unified Entry Form (Purchase / Sale)
# ---------------------------------------------------------------------------
def render_entry_form(entry_type: str):
    st.header(f"{entry_type} Entry")
    cat = entry_type

    date_val = st.date_input("Date", datetime.now(), key=f"{cat}_date")
    slip_no = st.text_input("Slip No.", key=f"{cat}_slip")
    parties = get_parties(cat)
    if not parties:
        st.warning(f"No parties found for category '{cat}'. Add them in Master Data.")
        return
    party_name = st.selectbox("Party Name", parties, key=f"{cat}_party")

    num_items = st.number_input("Number of Items", min_value=1, step=1, value=1, key=f"{cat}_num")
    items_list = get_items(cat)
    collected = []

    for i in range(int(num_items)):
        st.subheader(f"Item {i + 1}")
        if not items_list:
            st.warning("No items found. Add them in Master Data.")
            return
        item_type = st.selectbox(f"Item Type {i + 1}", items_list, key=f"{cat}_it_{i}")
        quantity = st.number_input(f"Quantity {i + 1} (kg)", min_value=0.0, step=0.1, key=f"{cat}_qty_{i}")
        rate = st.number_input(f"Rate {i + 1} (per kg)", min_value=0.0, step=0.1, key=f"{cat}_rate_{i}")

        gst_applied = st.checkbox(f"Apply GST for Item {i + 1}", key=f"{cat}_gst_{i}")

        adjusted_rate = rate
        if gst_applied:
            gst_pct = st.number_input(f"GST % for Item {i + 1}", min_value=0.0, step=0.1, key=f"{cat}_gstp_{i}")
            adjusted_rate += round(rate * gst_pct / 100, 2)

        amount = quantity * adjusted_rate
        collected.append((item_type, quantity, adjusted_rate, amount))

    if st.button(f"Add {entry_type}", key=f"{cat}_submit"):
        rows = []
        for item_type, quantity, adjusted_rate, amount in collected:
            rows.append([
                date_val.strftime("%m-%d-%Y"),
                slip_no,
                entry_type,
                party_name,
                item_type,
                quantity,
                adjusted_rate,
                amount,
            ])
        if append_rows_batch(DAYBOOK_SHEET, rows):
            st.success(f"{entry_type} entry added successfully!")
            read_all_rows.clear()


# ---------------------------------------------------------------------------
# 5. Payment / Receipt Form
# ---------------------------------------------------------------------------
def render_payment_receipt():
    st.header("Payment / Receipt Entry")

    date_val = st.date_input("Date", datetime.now(), key="pr_date")
    reference = st.text_input("Reference", key="pr_ref")
    mode = st.selectbox("Type", ["Cash", "Bank"], key="pr_mode")

    all_parties = sorted(
        set(get_parties("Purchase") + get_parties("Sale") + get_parties("Payment") + get_parties("Bank"))
    )
    if not all_parties:
        st.warning("No parties found. Add them in Master Data.")
        return
    party_name = st.selectbox("Party Name", all_parties, key="pr_party")
    voucher_type = st.selectbox("Voucher Type", ["Payment", "Receipt"], key="pr_vtype")
    amount = st.number_input("Amount", min_value=0.0, step=0.1, key="pr_amt")

    bank_name = None
    if mode == "Bank":
        bank_parties = get_parties("Bank")
        if bank_parties:
            bank_name = st.selectbox("Bank Name", bank_parties, key="pr_bank")
        else:
            st.warning("No bank parties found. Add one in Master Data with category 'Bank'.")

    if st.button("Add Voucher", key="pr_submit"):
        rows = [[date_val.strftime("%m-%d-%Y"), reference, voucher_type, party_name, mode, 0, 0, amount]]
        if mode == "Bank" and bank_name:
            reverse = "Receipt" if voucher_type == "Payment" else "Payment"
            rows.append([date_val.strftime("%m-%d-%Y"), reference, reverse, bank_name, "Bank", 0, 0, amount])
        if append_rows_batch(DAYBOOK_SHEET, rows):
            st.success(f"{voucher_type} entry added successfully!")
            read_all_rows.clear()


# ---------------------------------------------------------------------------
# 6. Party Ledger
# ---------------------------------------------------------------------------
def render_party_ledger():
    st.header("Party Ledger")

    all_parties = sorted(set(get_parties()))
    if not all_parties:
        st.info("No parties found.")
        return
    party = st.selectbox("Select Party", all_parties, key="led_party")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From", date(date.today().year, 4, 1), key="led_from")
    with col2:
        end_date = st.date_input("To", date.today(), key="led_to")

    if st.button("Load Ledger", key="led_load"):
        rows = read_all_rows(DAYBOOK_SHEET)
        # Start with stored opening balance (only if its date <= start_date)
        stored_bal, has_ob = get_opening_balance(party, start_date)
        opening_balance = stored_bal

        # Get the opening balance date to skip daybook entries before it
        ob_date = None
        if has_ob:
            ob_rows = read_all_rows(OPENING_BAL_SHEET)
            for r in ob_rows:
                if r.get("Party Name", "") == party:
                    try:
                        ob_date = datetime.strptime(r.get("Date", ""), "%m-%d-%Y").date()
                    except (ValueError, TypeError):
                        pass
                    break

        records = []
        for r in rows:
            if r.get("Party Name", r.get("Party", "")) != party:
                continue
            raw_date = r.get("Date", "")
            try:
                d = datetime.strptime(raw_date, "%m-%d-%Y").date()
            except (ValueError, TypeError):
                continue

            # Skip transactions on or before the opening balance date
            # (they are already included in the stored balance)
            if ob_date and d < ob_date:
                continue

            vtype = r.get("Voucher Type", r.get("Type", ""))
            amt = float(r.get("Amount", 0) or 0)
            debit = amt if vtype in ("Sale", "Payment") else 0.0
            credit = amt if vtype in ("Purchase", "Receipt") else 0.0

            # Transactions between OB date and start date add to opening balance
            if d < start_date:
                opening_balance += debit - credit
                continue

            if d > end_date:
                continue

            item = r.get("Item", "")
            qty = r.get("Quantity", r.get("Qty", ""))
            rate = r.get("Rate", "")
            slip = r.get("Slip No.", r.get("Slip No", r.get("Reference", "")))

            records.append({
                "Date": raw_date, "Slip": slip, "Type": vtype,
                "Item": item, "Qty": qty, "Rate": rate,
                "Debit": debit, "Credit": credit,
            })

        # Build dataframe with opening balance row
        if opening_balance != 0 or records:
            ob_dr = opening_balance if opening_balance > 0 else 0.0
            ob_cr = abs(opening_balance) if opening_balance < 0 else 0.0
            opening_row = {
                "Date": "", "Slip": "", "Type": "Opening Balance",
                "Item": "", "Qty": "", "Rate": "",
                "Debit": ob_dr, "Credit": ob_cr,
            }
            df = pd.DataFrame([opening_row] + records)
            # Running balance: start from opening, then cumulative sum of net movements
            running = 0.0
            balances = []

            for _, row in df.iterrows():
                running += float(row["Debit"]) - float(row["Credit"])
                balances.append(running)

            df["Balance"] = balances

            st.session_state["ledger_df"] = df
            st.session_state["ledger_party"] = party
            st.session_state["ledger_range"] = f"{start_date} to {end_date}"
        else:
            st.info("No entries found for the selected party.")
            return

    if "ledger_df" in st.session_state:
        df = st.session_state["ledger_df"]
        st.dataframe(df, use_container_width=True)

        totals = df[["Debit", "Credit"]].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Debit", f"{totals['Debit']:,.2f}")
        c2.metric("Total Credit", f"{totals['Credit']:,.2f}")
        c3.metric("Net Balance", f"{df['Balance'].iloc[-1]:,.2f}")

        pdf_bytes = generate_ledger_pdf(
            df,
            st.session_state["ledger_party"],
            st.session_state["ledger_range"],
        )
        st.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name=f"Ledger_{st.session_state['ledger_party']}.pdf",
            mime="application/pdf",
        )


# ---------------------------------------------------------------------------
# 7. PDF Export
# ---------------------------------------------------------------------------
def generate_ledger_pdf(df: pd.DataFrame, party: str, date_range: str) -> bytes:
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"Party Ledger: {party}", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Period: {date_range}", ln=True, align="C")
    pdf.ln(4)

    cols = list(df.columns)
    col_widths = {
        "Date": 26, "Slip": 22, "Type": 22, "Item": 28,
        "Qty": 20, "Rate": 22, "Debit": 28, "Credit": 28, "Balance": 30,
    }
    pdf.set_font("Helvetica", "B", 9)
    for c in cols:
        w = col_widths.get(c, 25)
        pdf.cell(w, 7, c, border=1, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    for _, row in df.iterrows():
        for c in cols:
            w = col_widths.get(c, 25)
            val = row[c]
            text = f"{val:,.2f}" if isinstance(val, float) else str(val)
            pdf.cell(w, 6, text, border=1, align="R" if isinstance(val, float) else "L")
        pdf.ln()

    pdf.set_font("Helvetica", "B", 9)
    for c in cols:
        w = col_widths.get(c, 25)
        if c == "Debit":
            pdf.cell(w, 7, f"{df['Debit'].sum():,.2f}", border=1, align="R")
        elif c == "Credit":
            pdf.cell(w, 7, f"{df['Credit'].sum():,.2f}", border=1, align="R")
        elif c == "Balance":
            pdf.cell(w, 7, f"{df['Balance'].iloc[-1]:,.2f}", border=1, align="R")
        elif c == "Date":
            pdf.cell(w, 7, "TOTAL", border=1, align="C")
        else:
            pdf.cell(w, 7, "", border=1)
    pdf.ln()

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 8. Dashboard
# ---------------------------------------------------------------------------
def render_dashboard():
    st.header("Dashboard")
    rows = read_all_rows(DAYBOOK_SHEET)
    if not rows:
        st.info("No data in Daybook yet.")
        return

    df = pd.DataFrame(rows)
    col_map = {col: col.strip() for col in df.columns}
    df.rename(columns=col_map, inplace=True)

    type_col = None
    for candidate in ("Voucher Type", "Type", "type"):
        if candidate in df.columns:
            type_col = candidate
            break
    amt_col = None
    for candidate in ("Amount", "amount"):
        if candidate in df.columns:
            amt_col = candidate
            break
    party_col = None
    for candidate in ("Party Name", "Party", "party"):
        if candidate in df.columns:
            party_col = candidate
            break

    if not type_col or not amt_col:
        st.warning("Daybook columns not recognised. Expected 'Voucher Type' and 'Amount'.")
        return

    df[amt_col] = pd.to_numeric(df[amt_col], errors="coerce").fillna(0)
 

    if party_col:
        st.subheader("Outstanding Balances")

        all_parties = sorted(set(df[party_col]))

        final_summary = []

        for party in all_parties:
            bal = calculate_party_balance(party)
            if abs(bal) > 0.01:
                final_summary.append({
                    "Party": party,
                    "Balance": bal
                })

        if final_summary:
            summary_df = pd.DataFrame(final_summary).sort_values("Balance", ascending=False)
            st.dataframe(summary_df, use_container_width=True)
        else:
            st.info("No outstanding balances.")


# ---------------------------------------------------------------------------
# 9. Master Data Management
# ---------------------------------------------------------------------------
def render_master_data():
    st.header("Master Data")
    tab1, tab2, tab3 = st.tabs(["Parties", "Items", "Opening Balances"])

    with tab1:
        _master_data_tab(PARTIES_SHEET, "Party", ["Name", "Category"],
                         category_options=["Purchase", "Sale", "Payment", "Bank"])
    with tab2:
        _master_data_tab(ITEMS_SHEET, "Item", ["Name", "Category"],
                         category_options=["Purchase", "Sale"])
    with tab3:
        _opening_balances_tab()


def _master_data_tab(sheet_name: str, label: str, headers: list[str],
                     category_options: list[str]):
    all_vals = read_all_values(sheet_name)
    if len(all_vals) <= 1:
        st.info(f"No {label.lower()}s found.")
        data_rows = []
    else:
        data_rows = all_vals[1:]

    if data_rows:
        st.subheader(f"Existing {label}s")
        for idx, row in enumerate(data_rows):
            row_num = idx + 2
            cols = st.columns([3, 2, 1, 1])
            cols[0].write(row[0] if len(row) > 0 else "")
            cols[1].write(row[1] if len(row) > 1 else "")
            if cols[2].button("Edit", key=f"{sheet_name}_edit_{idx}"):
                st.session_state[f"{sheet_name}_editing"] = row_num
            if cols[3].button("Del", key=f"{sheet_name}_del_{idx}"):
                if delete_row(sheet_name, row_num):
                    st.success(f"{label} deleted.")
                    read_all_rows.clear()
                    get_parties.clear()
                    get_items.clear()
                    st.rerun()

    editing_key = f"{sheet_name}_editing"
    if editing_key in st.session_state:
        row_num = st.session_state[editing_key]
        st.subheader(f"Edit {label}")
        current = all_vals[row_num - 1] if row_num - 1 < len(all_vals) else ["", ""]
        new_name = st.text_input("Name", value=current[0] if len(current) > 0 else "", key=f"{sheet_name}_ename")
        cat_idx = category_options.index(current[1]) if len(current) > 1 and current[1] in category_options else 0
        new_cat = st.selectbox("Category", category_options, index=cat_idx, key=f"{sheet_name}_ecat")
        c1, c2 = st.columns(2)
        if c1.button("Save", key=f"{sheet_name}_esave"):
            if update_row(sheet_name, row_num, [new_name, new_cat]):
                st.success(f"{label} updated.")
                del st.session_state[editing_key]
                read_all_rows.clear()
                get_parties.clear()
                get_items.clear()
                st.rerun()
        if c2.button("Cancel", key=f"{sheet_name}_ecancel"):
            del st.session_state[editing_key]
            st.rerun()

    st.subheader(f"Add {label}")
    new_name = st.text_input(f"New {label} Name", key=f"{sheet_name}_new_name")
    new_cat = st.selectbox(f"{label} Category", category_options, key=f"{sheet_name}_new_cat")
    if st.button(f"Add {label}", key=f"{sheet_name}_add"):
        if new_name.strip():
            if append_row(sheet_name, [new_name.strip(), new_cat]):
                st.success(f"{label} '{new_name.strip()}' added.")
                read_all_rows.clear()
                get_parties.clear()
                get_items.clear()
                st.rerun()
        else:
            st.warning("Name cannot be empty.")


def _opening_balances_tab():
    """Manage opening balances per party in a separate sheet."""
    all_vals = read_all_values(OPENING_BAL_SHEET)
    data_rows = all_vals[1:] if len(all_vals) > 1 else []

    # Build a lookup of existing parties with opening balances
    existing = {}
    for idx, row in enumerate(data_rows):
        name = row[0] if len(row) > 0 else ""
        if name:
            existing[name] = idx

    # Show existing opening balances
    if data_rows:
        st.subheader("Current Opening Balances")
        display = []
        for row in data_rows:
            name = row[0] if len(row) > 0 else ""
            ob_date = row[1] if len(row) > 1 else ""
            dr = float(row[2]) if len(row) > 2 and row[2] else 0.0
            cr = float(row[3]) if len(row) > 3 and row[3] else 0.0
            bal = dr - cr
            bal_type = "Dr" if bal >= 0 else "Cr"
            display.append({
                "Party Name": name,
                "Date": ob_date,
                "Debit": dr,
                "Credit": cr,
                "Balance": f"{abs(bal):,.2f} {bal_type}",
            })
        st.dataframe(pd.DataFrame(display), use_container_width=True)

    # Edit / Add opening balance
    st.subheader("Set Opening Balance")
    all_parties = sorted(set(get_parties()))
    if not all_parties:
        st.info("No parties found. Add parties first.")
        return

    party = st.selectbox("Party", all_parties, key="ob_party")

    # Pre-fill if party already has an opening balance
    prefill_date = date(date.today().year, 4, 1)
    prefill_dr, prefill_cr = 0.0, 0.0
    if party in existing:
        row = data_rows[existing[party]]
        try:
            prefill_date = datetime.strptime(row[1], "%m-%d-%Y").date() if len(row) > 1 and row[1] else prefill_date
        except (ValueError, TypeError):
            pass
        prefill_dr = float(row[2]) if len(row) > 2 and row[2] else 0.0
        prefill_cr = float(row[3]) if len(row) > 3 and row[3] else 0.0

    ob_date = st.date_input("Balance as on date", value=prefill_date, key="ob_date",
                            help="Transactions before this date are assumed included in this balance")
    col1, col2 = st.columns(2)
    with col1:
        debit = st.number_input("Debit (they owe you)", min_value=0.0, step=0.1,
                                value=prefill_dr, key="ob_dr")
    with col2:
        credit = st.number_input("Credit (you owe them)", min_value=0.0, step=0.1,
                                 value=prefill_cr, key="ob_cr")

    if st.button("Save Opening Balance", key="ob_save"):
        date_str = ob_date.strftime("%m-%d-%Y")
        if party in existing:
            row_num = existing[party] + 2
            if update_row(OPENING_BAL_SHEET, row_num, [party, date_str, debit, credit]):
                st.success(f"Opening balance updated for {party} as on {ob_date}.")
                read_all_rows.clear()
                st.rerun()
        else:
            if append_row(OPENING_BAL_SHEET, [party, date_str, debit, credit]):
                st.success(f"Opening balance saved for {party} as on {ob_date}.")
                read_all_rows.clear()
                st.rerun()

    # Delete option
    if data_rows:
        st.subheader("Remove Opening Balance")
        del_party = st.selectbox("Select party to remove", list(existing.keys()), key="ob_del_party")
        if st.button("Remove", key="ob_del"):
            row_num = existing[del_party] + 2
            if delete_row(OPENING_BAL_SHEET, row_num):
                st.success(f"Opening balance removed for {del_party}.")
                read_all_rows.clear()
                st.rerun()


# ---------------------------------------------------------------------------
# 10. Main App
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="ERP Data Entry", layout="wide")

    if "seeded" not in st.session_state:
        seed_master_data()
        st.session_state["seeded"] = True

    st.sidebar.title("Menu")
    menu = st.sidebar.radio(
        "Select Page",
        ["Dashboard", "Purchase Entry", "Sale Entry", "Payment/Receipt Entry",
         "Party Ledger", "Master Data"],
    )

    if menu == "Dashboard":
        render_dashboard()
    elif menu == "Purchase Entry":
        render_entry_form("Purchase")
    elif menu == "Sale Entry":
        render_entry_form("Sale")
    elif menu == "Payment/Receipt Entry":
        render_payment_receipt()
    elif menu == "Party Ledger":
        render_party_ledger()
    elif menu == "Master Data":
        render_master_data()


if __name__ == "__main__":
    main()







