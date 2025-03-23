import streamlit as st
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import Processor

st.set_page_config(page_title="Doctor Duty Scheduler", page_icon="🩺")

# --- 1. Title and description ---
st.title("🩺 Doctor Duty Scheduler")
st.markdown("""
This tool helps create optimal on-call schedules for medical teams  
using constraint-based optimization powered by AMPL.  
Developed and maintained pro bono by **Eryk Makowski**.
""")

# --- 2. Upload credentials.json file ---
st.header("🔐 1. Authorize Google Sheets Access")
uploaded_file = st.file_uploader("Upload your `credentials.json` file", type="json")

with st.expander("ℹ️ Where do I get the `credentials.json` file?"):
    st.markdown("""
#### 👤 For users:
If you're an end user, you should receive a `credentials.json` file from your system administrator or the person who manages this tool.

#### 👨‍💻 For developers:
To generate your own `credentials.json` file:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Navigate to **API & Services > Credentials**
4. Click **Create Credentials > Service Account**
5. Complete the details, then go to the "Keys" tab and add a new key in JSON format
6. Download the file – this is your `credentials.json`

Make sure the service account has access to the target Google Sheets you want to read/write.
""")

gc = None
if uploaded_file:
    try:
        # Parse credentials and authorize client
        creds_dict = json.load(uploaded_file)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        gc = gspread.authorize(creds)
        st.success("✅ Authorization successful!")
    except Exception as e:
        st.error(f"Authorization failed: {e}")

# If authorized, list available spreadsheets
spreadsheet = None
worksheet = None
if gc:
    st.subheader("📄 2. Choose a Spreadsheet")
    try:
        spreadsheets = gc.openall()
        spreadsheet_names = [ss.title for ss in spreadsheets]
        selected_spreadsheet_name = st.selectbox("Select a spreadsheet", spreadsheet_names)

        if selected_spreadsheet_name:
            spreadsheet = next(ss for ss in spreadsheets if ss.title == selected_spreadsheet_name)

            st.subheader("🗂️ 3. Choose a Worksheet")
            worksheet_names = [ws.title for ws in spreadsheet.worksheets() if not ws.title.endswith("-sched")]            
            selected_worksheet_name = st.selectbox("Select a worksheet", worksheet_names)

            if selected_worksheet_name:
                worksheet = spreadsheet.worksheet(selected_worksheet_name)
                st.success(f"Selected: **{spreadsheet.title} → {worksheet.title}**")


                # --- GUZIK ---
                if st.button("🔁 4. Generate Schedule"):
                    with st.spinner("Generating schedule... this may take a few seconds..."):
                        try:
                            # Przechwytujemy output terminalowy (stdout)
                            from io import StringIO
                            import sys

                            old_stdout = sys.stdout
                            sys.stdout = mystdout = StringIO()

                            # Uruchamiamy przetwarzanie
                            date_labels, doctors, schedule = Processor.process_worksheet(worksheet)
                            Processor.export_schedule_to_full_sheet(spreadsheet, worksheet, date_labels, doctors, schedule)
                            Processor.export_schedule_to_short_sheet(spreadsheet, worksheet, date_labels, doctors, schedule)

                            # Przywracamy stdout
                            sys.stdout = old_stdout

                            # Wyświetlamy przechwycony output
                            st.success("✅ Schedule generated and exported successfully!")
                            with st.expander("📋 Output log"):
                                st.text(mystdout.getvalue())

                        except Exception as e:
                            sys.stdout = old_stdout  # upewniamy się że stdout wróci
                            st.error(f"Something went wrong: {e}")                

    except Exception as e:
        st.error(f"Could not load spreadsheets: {e}")

# --- 3. Help section: where to get credentials.json ---
