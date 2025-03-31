import streamlit as st
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import Processor
from io import StringIO
import sys
import os
from amplpy import AMPL, modules


def TitleDescription() :
    st.set_page_config(page_title="Doctor Duty Scheduler", page_icon="🩺")

    # --- 1. Title and description ---
    st.title("🩺 Doctor Duty Scheduler")
    st.markdown("""
    This tool helps create optimal on-call schedules for medical teams  
    using constraint-based optimization powered by AMPL.  
    Developed and maintained pro bono by **Eryk Makowski**.
    """)
    

def GetCredentials() :
    gc = None
    user_email = None
    if "gc" not in st.session_state:
        st.session_state["gc"] = None
        st.session_state["user_email"] = None

    if st.session_state["gc"] is None:
        st.header("🔐 1. Authorize Google Sheets Access")
        uploaded_file = st.file_uploader("Upload your `credentials.json` file", type="json")

        with st.expander("ℹ️ Where do I get the `credentials.json` file?"):
            st.markdown("""
    **For users:** You should receive the file from your admin.

    **For developers:**
    1. Visit [Google Cloud Console](https://console.cloud.google.com/)
    2. Create a project or use existing
    3. Go to **API & Services > Credentials**
    4. Create a Service Account
    5. Under **Keys**, create a JSON key
    6. Download it – this is your `credentials.json`
    """)

        if uploaded_file:
            try:
                creds_dict = json.load(uploaded_file)
                creds = ServiceAccountCredentials.from_json_keyfile_dict(
                    creds_dict,
                    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                )
                gc = gspread.authorize(creds)
                st.session_state["gc"] = gc
                st.session_state["user_email"] = creds_dict.get("client_email", "<unknown>")
                st.success("✅ Authorization successful!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Authorization failed: {e}")

    else:
        gc = st.session_state["gc"]
        user_email = st.session_state["user_email"]
    return gc, user_email

# def Authorize() :
#     scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
#     creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
#     client = gspread.authorize(creds)
#     return client

def ChooseWorksheet( gc, user_email ) :
    st.header("📄 2. Choose Spreadsheet")
    try:
        with st.expander("❓ I don't see my spreadsheet or worksheet – what now?"):
            st.markdown(f"""
If your spreadsheet is missing, make sure it is **shared** with your service account: {user_email} and has at least **Editor** access.
""")
        spreadsheets = gc.openall()
        spreadsheets = [s for s in spreadsheets if not s.title.endswith("-sched")]
        spreadsheet_titles = [s.title for s in spreadsheets]
        selected_title = st.selectbox("Select a spreadsheet from the list below:", [""] + spreadsheet_titles)

        if selected_title:
            st.header("📄 3. Choose Worksheet")
            spreadsheet = next(s for s in spreadsheets if s.title == selected_title)
            worksheet_titles = [ws.title for ws in spreadsheet.worksheets() if not ws.title.endswith("-sched")]
            selected_worksheet_name = st.selectbox("Select a worksheet from the list below:", worksheet_titles)

            if selected_worksheet_name:
                worksheet = spreadsheet.worksheet(selected_worksheet_name)
                st.success(f"Selected: **{spreadsheet.title} → {worksheet.title}**")
                return spreadsheet, worksheet
    except Exception as e:
        st.error(f"❌ Failed to list spreadsheets: {e}")
    return None, None

def GenerateScheduleButtonWithAction( spreadsheet, worksheet ) :
    if not st.button("🔁 4. Generate Schedule") :
        return
    with st.spinner("Generating schedule... this may take a few seconds..."):
        try:
            # Przechwytujemy output terminalowy (stdout)

            old_stdout = sys.stdout
            sys.stdout = mystdout = StringIO()

            # Uruchamiamy przetwarzanie
            processor = Processor.Processor()
            processor.process_worksheet( spreadsheet, worksheet )
            processor.export_schedule_to_full_sheet()
            processor.export_schedule_to_short_sheet()

            # Przywracamy stdout
            sys.stdout = old_stdout

            # Wyświetlamy przechwycony output
            st.success("✅ Schedule generated and exported successfully!")
            with st.expander("📋 Output log"):
                st.text(mystdout.getvalue())

        except Exception as e:
            sys.stdout = old_stdout  # upewniamy się że stdout wróci
            st.error(f"Something went wrong: {e}")                

# st.markdown("{}".format(st.secrets["ampl_lic"].split('\n')[0]))

if "ampl_lic" in st.secrets:
    os.makedirs(".ampl", exist_ok=True)
    with open(".ampl/ampl.lic", "w") as f:
        f.write(st.secrets["ampl_lic"])
        os.environ["AMPL_LICENSE_FILE"] = os.path.abspath(".ampl/ampl.lic")
        modules.activate(st.secrets["ampl_lic"])
        # st.markdown("AMPL configured")


TitleDescription()
gc, user_email = GetCredentials() # this will rerun if credentials are wrong
if gc != None :
    spreadsheet, worksheet = ChooseWorksheet( gc, user_email )
    if spreadsheet != None :
        GenerateScheduleButtonWithAction( spreadsheet, worksheet )
