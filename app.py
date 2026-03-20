import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import time
from datetime import datetime

# --- 1. SET PAGE CONFIG ---
st.set_page_config(page_title="Employee Manager Pro", layout="wide", page_icon="👥")

# --- 2. CUSTOM CSS FOR HEADER/FOOTER ---
st.markdown("""
    <style>
    .main-header {
        background-color: #4A90E2;
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 25px;
    }
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #f1f1f1;
        color: #555;
        text-align: center;
        padding: 10px;
        font-size: 12px;
        border-top: 1px solid #e7e7e7;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. GOOGLE SHEETS CONNECTION ---
# def init_connection():
#     try:
#         scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
#         creds = ServiceAccountCredentials.from_json_keyfile_name('creds.json', scope)
#         client = gspread.authorize(creds)
#         url = "https://docs.google.com/spreadsheets/d/1xBB9hIMimqE4gWyJ2YM24wADvK74SIUWLCz8T3lBCsQ"
#         return client.open_by_url(url).worksheet("Information")
#     except Exception as e:
#         st.error(f"Connection Error: {e}")
#         return None

def init_connection():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # Use secrets instead of a local file
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        url = "https://docs.google.com/spreadsheets/d/1xBB9hIMimqE4gWyJ2YM24wADvK74SIUWLCz8T3lBCsQ"
        return client.open_by_url(url).worksheet("Information")
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

with st.spinner("🔄 Syncing with Cloud Database..."):
    sheet = init_connection()

def get_data():
    if sheet:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        df.columns = [str(col).strip() for col in df.columns]
        return df
    return pd.DataFrame()

df = get_data()

# --- 4. SESSION STATE ---
if 'menu_choice' not in st.session_state:
    st.session_state.menu_choice = "View & Search"
if 'edit_target_id' not in st.session_state:
    st.session_state.edit_target_id = None

# --- 5. HEADER ---
st.markdown('<div class="main-header"><h1>Employee Management Portal</h1><p>Internal Database System v1.2</p></div>', unsafe_allow_html=True)

# --- 6. SIDEBAR & NAVIGATION ---
menu_options = ["View & Search", "Add New", "Update Record", "Delete Record"]
current_idx = menu_options.index(st.session_state.menu_choice)
choice = st.sidebar.selectbox("Navigation Menu", menu_options, index=current_idx)
st.session_state.menu_choice = choice

# --- 7. AUTO-ID GENERATOR ---
def generate_next_id(dataframe):
    if dataframe.empty or 'ID' not in dataframe.columns: return "EMP-001"
    try:
        last_id = str(dataframe['ID'].iloc[-1])
        return f"EMP-{int(last_id.split('-')[1]) + 1:03d}"
    except: return f"EMP-{len(dataframe) + 1:03d}"

# --- 8. MAIN APP LOGIC ---

# A. VIEW & SEARCH
if st.session_state.menu_choice == "View & Search":
    st.subheader("🔍 Real-time Employee Search")
    search_query = st.text_input("Filter by Name or ID", placeholder="Type here...")
    
    filtered_df = df[df['Fullname'].str.contains(search_query, case=False, na=False) | 
                     df['ID'].str.contains(search_query, case=False, na=False)] if search_query else df

    if 'delete_id' in st.session_state:
        st.error(f"⚠️ Confirm deletion of **{st.session_state.delete_id}**?")
        c1, c2, _ = st.columns([1, 1, 5])
        if c1.button("Yes, Delete", type="primary"):
            with st.spinner("Deleting..."):
                sheet.delete_rows(st.session_state.delete_idx)
                del st.session_state.delete_id
                st.rerun()
        if c2.button("Cancel"):
            del st.session_state.delete_id
            st.rerun()

    # Dashboard Table
    cols = st.columns([1, 2, 2, 2, 1, 1])
    headers = ["**ID**", "**Fullname**", "**Address**", "**Birthdate**", "**Edit**", "**Delete**"]
    for col, h in zip(cols, headers): col.write(h)
    st.divider()

    for i, row in filtered_df.iterrows():
        r_cols = st.columns([1, 2, 2, 2, 1, 1])
        r_cols[0].write(row['ID'])
        r_cols[1].write(row['Fullname'])
        r_cols[2].write(row['Address'])
        r_cols[3].write(str(row['Birthdate']))
        if r_cols[4].button("📝", key=f"ed_{row['ID']}"):
            st.session_state.edit_target_id = row['ID']
            st.session_state.menu_choice = "Update Record"
            st.rerun()
        if r_cols[5].button("🗑️", key=f"dl_{row['ID']}"):
            st.session_state.delete_id = row['ID']
            st.session_state.delete_idx = i + 2
            st.rerun()

# B. ADD NEW
elif st.session_state.menu_choice == "Add New":
    st.subheader("➕ Register New Member")
    next_id = generate_next_id(df)
    with st.form("add_form", clear_on_submit=True):
        st.info(f"Generated ID: **{next_id}**")
        name = st.text_input("Fullname")
        addr = st.text_area("Address")
        bday = st.date_input("Birthdate")
        if st.form_submit_button("Add Record"):
            if name:
                with st.spinner("Saving..."):
                    sheet.append_row([next_id, name, addr, str(bday)])
                    st.success(f"Successfully added {name}!")
                    time.sleep(1)
                    st.rerun()

# C. UPDATE RECORD
elif st.session_state.menu_choice == "Update Record":
    st.subheader("✏️ Edit Details")
    ids = df['ID'].tolist() if not df.empty else []
    if ids:
        def_idx = ids.index(st.session_state.edit_target_id) if st.session_state.edit_target_id in ids else 0
        selected_id = st.selectbox("Select ID", ids, index=def_idx)
        row_data = df[df['ID'] == selected_id].iloc[0]
        sheet_row = df.index[df['ID'] == selected_id].tolist()[0] + 2
        with st.form("update_form"):
            st.text_input("ID", value=selected_id, disabled=True)
            u_name = st.text_input("Fullname", value=str(row_data['Fullname']))
            u_addr = st.text_area("Address", value=str(row_data['Address']))
            u_bday = st.text_input("Birthdate", value=str(row_data['Birthdate']))
            up_col, can_col = st.columns([1, 1])
            if up_col.form_submit_button("Update"):
                with st.spinner("Updating..."):
                    sheet.update(f"B{sheet_row}:D{sheet_row}", [[u_name, u_addr, u_bday]])
                    st.session_state.edit_target_id = None
                    st.session_state.menu_choice = "View & Search"
                    st.success("Updated!")
                    time.sleep(1)
                    st.rerun()
            if can_col.form_submit_button("Back"):
                st.session_state.menu_choice = "View & Search"
                st.rerun()

# D. DELETE RECORD (Standalone)
elif st.session_state.menu_choice == "Delete Record":
    st.subheader("❌ Direct Deletion")
    if not df.empty:
        id_to_del = st.selectbox("Select ID", df['ID'].tolist())
        if st.button("Delete Permanently", type="primary"):
            idx = df.index[df['ID'] == id_to_del].tolist()[0]
            sheet.delete_rows(idx + 2)
            st.success("Record Removed.")
            time.sleep(1)
            st.rerun()

# --- 9. FOOTER ---
footer_html = f"""
    <div class="footer">
        <p>Employee Database System • Last Sync: {datetime.now().strftime('%H:%M:%S')} • Connected to Google Sheets API</p>
    </div>
"""
st.markdown(footer_html, unsafe_allow_html=True)