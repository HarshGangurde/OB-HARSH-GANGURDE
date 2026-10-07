import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime
import io

# --- UI Configuration --
st.set_page_config(page_title="Branch Loan Data Cleaner", layout="wide")
st.title("🏦 Smart Branch Data Cleaner")
st.markdown("Upload the branch register. The system will auto-format fields and organize the output into Clean, Review, and Full Data tabs.")

# --- Cleaning & Formatting Functions ---
def clean_branch(val):
    if pd.isna(val) or str(val).strip() == '': return "", "Missing branch"
    return str(val).strip().title(), ""

def clean_name(val):
    if pd.isna(val) or str(val).strip() == '': return "", "Missing customer name"
    return str(val).strip().title(), ""

def clean_amount(val):
    if pd.isna(val) or str(val).strip() == '': return "", "Missing amount"
    val_str = str(val).upper().replace(',', '').replace(' ', '')
    val_str = val_str.replace('₹', '').replace('RS.', '').replace('RS', '')
    
    if 'K' in val_str:
        val_str = val_str.replace('K', '000')
    try:
        num = float(val_str)
        formatted_amt = f"{num:,.0f}" 
        if num < 0: return formatted_amt, "Negative amount detected"
        return formatted_amt, ""
    except ValueError:
        return str(val), f"Invalid amount format: {val}"

def clean_phone(val):
    if pd.isna(val) or str(val).strip() == '': return "", "Missing phone"
    digits = re.sub(r'\D', '', str(val))
    
    if len(digits) == 12 and digits.startswith('91'):
        digits = digits[2:]
        
    if len(digits) == 10:
        return f"+91-{digits[:5]}-{digits[5:]}", ""
    return str(val), f"Invalid phone length ({len(digits)} digits)"

def clean_date(val):
    if pd.isna(val) or str(val).strip() == '': return "", "Missing date"
    try:
        parsed_date = pd.to_datetime(val, infer_datetime_format=True, errors='coerce')
        if pd.isna(parsed_date):
            return str(val), f"Invalid/Impossible date: {val}"
        if parsed_date > datetime.now():
            return parsed_date.strftime('%Y-%m-%d'), "Future date detected"
        return parsed_date.strftime('%Y-%m-%d'), ""
    except Exception:
        return str(val), "Date format error"

def clean_status(val):
    if pd.isna(val) or str(val).strip() == '': return "", "Missing status"
    val_clean = str(val).strip().upper()
    if val_clean == 'ACTIVE': return 'Active', ""
    if val_clean == 'CLOSED': return 'Closed', ""
    if val_clean == 'NPA': return 'NPA', ""
    return str(val).title(), f"Unknown status: {val}"

# --- Main Processing Engine ---
uploaded_file = st.file_uploader("Upload Loan Register (Excel/CSV)", type=["xlsx", "xls", "csv"])

if uploaded_file:
    # 1. Load Data
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Error reading file: {e}")
        st.stop()

    col_mapping = {
        'Branch': 'branch', 'Customer Name': 'customer_name', 
        'Loan Amt': 'loan_amount', 'Loan Date': 'loan_date', 
        'Phone No': 'phone', 'Status': 'status', 'Notes': 'original_notes'
    }
    df = df.rename(columns=lambda x: col_mapping.get(x.strip(), x.strip().lower()))

    for col in ['branch', 'customer_name', 'loan_amount', 'loan_date', 'phone', 'status', 'original_notes']:
        if col not in df.columns:
            df[col] = ""

    cleaned_data = []
    
    # 2. Process Data
    for index, row in df.iterrows():
        flags = []
        
        branch, branch_flag = clean_branch(row['branch'])
        if branch_flag: flags.append(branch_flag)
        
        name, name_flag = clean_name(row['customer_name'])
        if name_flag: flags.append(name_flag)

        amt, amt_flag = clean_amount(row['loan_amount'])
        if amt_flag: flags.append(amt_flag)

        phone, phone_flag = clean_phone(row['phone'])
        if phone_flag: flags.append(phone_flag)

        date, date_flag = clean_date(row['loan_date'])
        if date_flag: flags.append(date_flag)

        status, status_flag = clean_status(row['status'])
        if status_flag: flags.append(status_flag)
        
        orig_notes = str(row['original_notes']).strip()
        if orig_notes == 'nan' or pd.isna(row['original_notes']): orig_notes = ""
        
        sys_flags = " | ".join(flags)
        
        if sys_flags and orig_notes:
            final_notes = f"System Flags: {sys_flags} || Original Note: {orig_notes}"
        elif sys_flags:
            final_notes = f"System Flags: {sys_flags}"
        elif orig_notes:
            final_notes = f"Original Note: {orig_notes}"
        else:
            final_notes = "Clean Entry"

        cleaned_data.append({
            'Branch': branch,
            'Customer Name': name,
            'Loan Amt': amt,
            'Phone No': phone,
            'Loan Date': date,
            'Status': status,
            'Notes / Analysis': final_notes,
            '_is_clean': len(flags) == 0
        })

    out_df = pd.DataFrame(cleaned_data)

    # 3. Duplicate Detection (By Phone)
    valid_phones = out_df[out_df['Phone No'] != '']
    valid_phones = valid_phones[valid_phones['Phone No'].str.startswith('+91', na=False)] 
    dup_phones = valid_phones[valid_phones.duplicated(subset=['Phone No'], keep=False)]
    
    for idx in dup_phones.index:
        out_df.at[idx, '_is_clean'] = False
        curr_notes = out_df.at[idx, 'Notes / Analysis']
        dup_msg = "System Flag: Duplicate Phone Number detected"
        if curr_notes == "Clean Entry":
            out_df.at[idx, 'Notes / Analysis'] = dup_msg
        else:
            out_df.at[idx, 'Notes / Analysis'] = f"{dup_msg} || {curr_notes}"

    # --- Segregate Data ---
    full_df = out_df.drop(columns=['_is_clean'])
    clean_df = out_df[out_df['_is_clean'] == True].drop(columns=['_is_clean'])
    review_df = out_df[out_df['_is_clean'] == False].drop(columns=['_is_clean'])

    # --- UI Display ---
    st.subheader("Data Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Rows", len(out_df))
    col2.metric("Clean Rows ✅", len(clean_df))
    col3.metric("Requires Review ⚠️", len(review_df))

    # Added third tab here
    tab1, tab2, tab3 = st.tabs(["✅ Clean Data", "⚠️ Requires Review", "📊 Full Data (Combined)"])
    
    with tab1:
        st.dataframe(clean_df, use_container_width=True)
    with tab2:
        st.dataframe(review_df, use_container_width=True)
    with tab3:
        st.dataframe(full_df, use_container_width=True)

    # --- Multi-Tab Excel Export ---
    st.markdown("### 📥 Download Formatted Excel")
    
    # Create an in-memory Excel file with THREE tabs
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        clean_df.to_excel(writer, sheet_name='Clean Data', index=False)
        review_df.to_excel(writer, sheet_name='Requires Review', index=False)
        full_df.to_excel(writer, sheet_name='Full Data', index=False)
    
    st.download_button(
        label="Download Multi-Tab Excel File (Clean, Review & Full Data)",
        data=buffer.getvalue(),
        file_name="Processed_Loan_Register.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
