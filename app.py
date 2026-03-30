import streamlit as st
import pandas as pd
from io import BytesIO

st.title("Recon Tool")

# File uploader for the first Excel sheet
uploaded_file1 = st.file_uploader("Upload first Excel sheet", type=['xlsx', 'xls', 'csv'])

# File uploader for the second Excel sheet
uploaded_file2 = st.file_uploader("Upload second Excel sheet", type=['xlsx', 'xls', 'csv'])

df1 = None
df2 = None

if uploaded_file1 is not None:
    st.write("First file uploaded successfully!")
    # Process the file based on type
    if uploaded_file1.name.endswith('.csv'):
        df1 = pd.read_csv(uploaded_file1)
    else:
        # For Excel files, show sheet selector
        excel_file = pd.ExcelFile(uploaded_file1)
        sheet_names = excel_file.sheet_names
        selected_sheet1 = st.selectbox("Select sheet from first file:", sheet_names, key="sheet1")
        df1 = pd.read_excel(uploaded_file1, sheet_name=selected_sheet1)
    st.dataframe(df1.head())

if uploaded_file2 is not None:
    st.write("Second file uploaded successfully!")
    # Process the file based on type
    if uploaded_file2.name.endswith('.csv'):
        df2 = pd.read_csv(uploaded_file2)
    else:
        # For Excel files, show sheet selector
        excel_file = pd.ExcelFile(uploaded_file2)
        sheet_names = excel_file.sheet_names
        selected_sheet2 = st.selectbox("Select sheet from second file:", sheet_names, key="sheet2")
        df2 = pd.read_excel(uploaded_file2, sheet_name=selected_sheet2)
    st.dataframe(df2.head())

# Comparison section
if df1 is not None and df2 is not None:
    st.header("Data Comparison")
    
    # Select account column
    common_columns = list(set(df1.columns) & set(df2.columns))
    if not common_columns:
        st.error("No common columns found between the two files.")
    else:
        account_col = st.selectbox("Select the account column:", common_columns, key="account_col")
        
        # Column mapping
        df1_cols = [c for c in df1.columns if c != account_col]
        df2_cols = [c for c in df2.columns if c != account_col]

        # Columns to compare
        st.subheader("Select columns to compare")
        compare_cols = st.multiselect("Choose File 1 columns to include in diff", df1_cols, default=df1_cols)

        # Dynamic mapping for selected columns only
        st.subheader("Column Mapping")
        mappings = {}
        for col1 in compare_cols:
            # Automatically map if column name exists in File 2
            if col1 in df2_cols:
                mappings[col1] = col1
                st.info(f"✓ '{col1}' automatically mapped to '{col1}' (File 2)")
            else:
                # For non-matching columns, use "account" as default
                default_idx = 0
                if "account" in df2_cols:
                    default_idx = df2_cols.index("account")
                mapped_col2 = st.selectbox(
                    f"Map '{col1}' from File 1 to:", 
                    df2_cols, 
                    index=default_idx,
                    key=f"map_{col1}"
                )
                mappings[col1] = mapped_col2

        # Show active mapping table (after selection)
        if compare_cols:
            active_map = pd.DataFrame([
                {'File1 Column': col1, 'File2 Column': mappings[col1]}
                for col1 in compare_cols
            ])
            st.subheader("Active Mapping")
            st.dataframe(active_map)

        # Merge dataframes on account column
        merged = pd.merge(df1, df2, on=account_col, suffixes=('_file1', '_file2'), how='outer')
        
        # Find accounts unique to each file
        accounts_file1 = set(df1[account_col])
        accounts_file2 = set(df2[account_col])
        only_in_file1 = list(accounts_file1 - accounts_file2)
        only_in_file2 = list(accounts_file2 - accounts_file1)
        
        unique_accounts = []
        for acc in only_in_file1:
            unique_accounts.append({'Account': acc, 'Source': 'Only in File 1'})
        for acc in only_in_file2:
            unique_accounts.append({'Account': acc, 'Source': 'Only in File 2'})
        
        if unique_accounts:
            unique_df = pd.DataFrame(unique_accounts)
            st.subheader("Unique Accounts")
            st.dataframe(unique_df)
        
        # Find differences per column
        column_diffs = {}
        for col1 in compare_cols:
            column_diffs[col1] = []
        
        for idx, row in merged.iterrows():
            account = row[account_col]
            # Only process accounts present in both files
            if account in only_in_file1 or account in only_in_file2:
                continue
            for col1 in compare_cols:
                col2 = mappings[col1]
                val1 = row.get(f'{col1}_file1')
                val2 = row.get(f'{col2}_file2')
                if pd.isna(val1) and pd.isna(val2):
                    continue
                if val1 != val2:
                    diff_val = ''
                    try:
                        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                            diff_val = val1 - val2
                    except:
                        pass
                    column_diffs[col1].append({
                        'Account': account,
                        f"{col1}_file1": val1,
                        f"{col2}_file2": val2,
                        'Difference': diff_val
                    })
        
        # Display and prepare for download
        has_diffs = False
        
        # First, check if there's any content to write
        has_content = bool(unique_accounts) or any(column_diffs.values())
        
        if has_content:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                if unique_accounts:
                    unique_df.to_excel(writer, index=False, sheet_name='Unique Accounts')
                for col1, data in column_diffs.items():
                    if data:
                        has_diffs = True
                        col_df = pd.DataFrame(data)
                        st.subheader(f"Differences in Column: {col1} (mapped to {mappings[col1]})")
                        st.dataframe(col_df)
                        col_df.to_excel(writer, index=False, sheet_name=col1[:31])  # Sheet name limit
                
                # Autosize columns in all sheets
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    for column in worksheet.columns:
                        max_length = 0
                        column_letter = column[0].column_letter
                        for cell in column:
                            try:
                                if cell.value and len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_width = min(max_length + 2, 50)  # Cap width at 50
                        worksheet.column_dimensions[column_letter].width = adjusted_width
            
            output.seek(0)
            st.download_button(
                label="Download Comparison Report",
                data=output,
                file_name="comparison_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.success("No differences or unique accounts found between the two files.")