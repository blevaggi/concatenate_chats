import streamlit as st
import pandas as pd
import re
import os
import io
import base64
import sys

st.set_page_config(
    page_title="Message Column Concatenator",
    page_icon="🤝",
    layout="wide"
)

def process_data(df):
    """
    Process a dataframe by concatenating Message_No columns into a single conversation column.
    Odd numbered messages are prefixed with "Bot: " and even numbered with "User: ".
    
    Args:
        df (pandas.DataFrame): DataFrame to process
    
    Returns:
        pandas.DataFrame: Processed DataFrame with the new Conversation column
        bool: Whether processing was performed
    """
    # Find all Message_No columns
    message_cols = [col for col in df.columns if re.match(r'Message_No_\d+', col)]
    
    if not message_cols:
        return df, False
    
    # Sort the columns by their number
    message_cols.sort(key=lambda x: int(x.split('_')[-1]))
    
    # Create the conversation column
    conversations = []
    
    for _, row in df.iterrows():
        convo_parts = []
        for i, col in enumerate(message_cols):
            message = row[col]
            # Skip empty messages
            if pd.notna(message) and str(message).strip():
                # Odd numbers (1, 3, 5...) are Bot, Even (2, 4, 6...) are User
                col_num = int(col.split('_')[-1])
                prefix = "Bot: " if col_num % 2 == 1 else "User: "
                convo_parts.append(f"{prefix}{message}")
        
        # Join all parts with newlines
        conversations.append('\n'.join(convo_parts) if convo_parts else "")
    
    # Find the position of the first Message_No column
    first_message_col = message_cols[0]
    insert_position = df.columns.get_loc(first_message_col)
    
    # Create a new dataframe with the columns rearranged
    new_columns = list(df.columns[:insert_position]) + ["Conversation"] + list(df.columns[insert_position:])
    new_df = df.copy()
    new_df["Conversation"] = conversations
    
    # Reorder columns to put Conversation in the right place
    return new_df[new_columns], True


def process_file(uploaded_file):
    """
    Process uploaded file based on file extension
    
    Args:
        uploaded_file: Streamlit UploadedFile object
    
    Returns:
        tuple: (processed_file_content, file_extension, success_message, original_df, processed_df)
    """
    filename = uploaded_file.name
    file_extension = os.path.splitext(filename)[1].lower()
    success_message = ""
    
    if file_extension in ['.xlsx', '.xls']:
        # For Excel files, process each sheet
        try:
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                xls = pd.ExcelFile(uploaded_file)
                sheets_processed = 0
                first_sheet_original = None
                first_sheet_processed = None
                
                for sheet_name in xls.sheet_names:
                    df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
                    
                    # Store first sheet for display
                    if first_sheet_original is None:
                        first_sheet_original = df.copy()
                    
                    processed_df, was_processed = process_data(df)
                    
                    # Store first processed sheet for display
                    if was_processed and first_sheet_processed is None:
                        first_sheet_processed = processed_df.copy()
                        
                    processed_df.to_excel(writer, sheet_name=sheet_name, index=False)
                    if was_processed:
                        sheets_processed += 1
                
                if sheets_processed > 0:
                    success_message = f"✅ Successfully processed {sheets_processed} sheet(s) in {filename}"
                else:
                    success_message = f"ℹ️ No Message_No columns found in any sheet of {filename}"
            
            excel_buffer.seek(0)
            return excel_buffer.getvalue(), file_extension, success_message, first_sheet_original, first_sheet_processed
        except Exception as e:
            return None, None, f"❌ Error processing Excel file: {str(e)}", None, None
        
    elif file_extension == '.csv':
        # For CSV files, process directly
        try:
            df = pd.read_csv(uploaded_file)
            processed_df, was_processed = process_data(df)
            
            if was_processed:
                success_message = f"✅ Successfully processed {filename}"
            else:
                success_message = f"ℹ️ No Message_No columns found in {filename}"
            
            csv_buffer = io.BytesIO()
            processed_df.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)
            return csv_buffer.getvalue(), file_extension, success_message, df, processed_df
        except Exception as e:
            return None, None, f"❌ Error processing CSV file: {str(e)}", None, None
    
    else:
        return None, None, f"❌ Unsupported file format: {file_extension}", None, None


def main():
    st.title("📊 Message Column Concatenator")
    
    st.markdown("""
    This app creates a new 'Conversation' column by combining all Message_No_{number} columns:
    
    - Odd-numbered messages (Message_No_1, Message_No_3, etc.) are labeled as 'Bot: '
    - Even-numbered messages (Message_No_2, Message_No_4, etc.) are labeled as 'User: '
    - Empty messages are ignored
    - The new column is placed to the left of the first Message_No column
    
    **Supported file formats:** Excel (.xlsx, .xls) and CSV (.csv)
    """)
    
    uploaded_file = st.file_uploader("Upload your file", type=["xlsx", "xls", "csv"])
    
    if uploaded_file is not None:
        with st.spinner(f"Processing {uploaded_file.name}..."):
            # Process the file
            processed_content, extension, message, original_df, processed_df = process_file(uploaded_file)
            
            # Display results
            if processed_content:
                st.success(message)
                
                # Create tabs for viewing before and after
                if original_df is not None and processed_df is not None:
                    tab1, tab2 = st.tabs(["Original Data Sample", "Processed Data Sample"])
                    with tab1:
                        st.dataframe(original_df.head(10))
                    with tab2:
                        st.dataframe(processed_df.head(10))
                
                # Set up the download button with Streamlit's built-in functionality
                new_filename = f"processed_{uploaded_file.name}"
                
                # Determine MIME type based on file extension
                mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                if extension == '.csv':
                    mime_type = "text/csv"
                elif extension == '.xls':
                    mime_type = "application/vnd.ms-excel"
                
                st.download_button(
                    label=f"Download processed file",
                    data=processed_content,
                    file_name=new_filename,
                    mime=mime_type,
                    key="download_button"
                )
                
                # Explain what was done
                if processed_df is not None and "Conversation" in processed_df.columns:
                    message_cols = [col for col in original_df.columns if re.match(r'Message_No_\d+', col)]
                    message_cols = sorted(message_cols, key=lambda x: int(x.split('_')[-1]))
                    st.markdown(f"""
                    **Processing Details:**
                    - Found {len(message_cols)} message columns: {', '.join(message_cols[:5])}{"..." if len(message_cols) > 5 else ""}
                    - Added new 'Conversation' column to the left of {message_cols[0]}
                    """)
            else:
                st.error(message)


if __name__ == "__main__":
    main()
