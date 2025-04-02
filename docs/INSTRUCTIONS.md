# 📘 How to Use Doctor Duty Scheduler

This tool helps generate optimal duty schedules for medical teams based on preferences and constraints.

---

## 📝 Step 1: Prepare Your Spreadsheet

1. Use Google Sheets to create a worksheet based on the example template.

The worksheet must contain:

### Column headers (first row):
Start with a `Date` column, followed by names of doctors:

`Date | Doctor A | Doctor B | Doctor C | ...`

---

### Rows 2–9: Preferences and constraints

| Row Label                  | Description                                                   |
|----------------------------|---------------------------------------------------------------|
| Enabled                    | Whether the doctor is active in this schedule (TRUE/FALSE)    |
| Minimum Shifts             | Minimum number of shifts required                             |
| Preferred Shifts           | Target number of shifts (overall)                             |
| Maximum Shifts             | Upper limit of shifts                                         |
| Preferred Weekday Shifts   | Preferred number of weekday shifts                            |
| Preferred Weekend Shifts   | Preferred number of weekend shifts                            |
| Prefer Sparse Schedule     | TRUE if the doctor prefers shifts spaced apart                |
| Prefer Dense Schedule      | TRUE if the doctor prefers clustered shifts                   |

---

### Starting from row 10: Calendar entries

Each row must begin with a **date** (e.g. `2025-05-01`) followed by individual preferences per doctor:

- **No** → Doctor cannot work that day  
- **Unwilling** → Doctor prefers not to work; higher penalty  
- **Auto** → No preference  
- **Willing** → Doctor prefers to work; lower penalty  
- **Yes** → Doctor **must** work that day

---

> 💡 **Tips:**
> - You can copy one cell and paste into a selection to repeat it.
> - Use fill handle (drag down) to quickly extend values.
> - You can add empty rows to visually separate weeks — they’ll be ignored.

---

## 🔓 Step 2: Share Access with the App

Share your spreadsheet with the service account email (from credentials.json) with **Editor** permissions.
After uploading the credentials file in the app, the email address of the service account will be displayed automatically, so you can easily copy and use it.

---

## 🌐 Step 3: Open the App

If you’re reading this outside the app (e.g. on GitHub or in a downloaded file), launch the app here:
👉 [https://doctor-duty-scheduler.streamlit.app/](https://doctor-duty-scheduler.streamlit.app/)

If you’re already inside the app, just continue to the next step 🙂

---

## 🔐 Step 4: Authorize Google Sheets Access

1. Click **"Upload your `credentials.json`"**.
2. Upload a valid Google service account file.

> Where do I get it?
> - **Users:** Get it from the person who manages the system.
> - **Developers:** See [this guide](https://docs.streamlit.io/knowledge-base/tutorials/databases/gspread).

---

## 📂 Step 5: Select Spreadsheet and Worksheet

1. Select the spreadsheet from the dropdown list.
2. Pick the worksheet containing your scheduling data.
3. Sheets ending with `-sched` are output-only and skipped.

> ❓ **Can't find your spreadsheet?**
> Make sure it’s shared with the service account and appears in "My Drive".

---

## ⚙️ Step 6: Generate the Schedule

Press the **"Generate Schedule"** button.  
The app will run the optimizer and generate output sheets:

- `*-full-sched` → full matrix of dates × doctors (with `"Yes"` for assigned)
- `*-short-sched` → compact list of date + doctor on duty

---

## 📤 Outputs and Interpretation

Check the new output sheets created in your spreadsheet.  
If any errors occur, they’ll be displayed in the app.

---

## 🧠 Tips & Troubleshooting

- Avoid typos like `"TRUEE"` or `"Noo"` – they cause errors.
- Parameters can be left blank – defaults will apply.
- Dates must be in a consistent format (`YYYY-MM-DD` preferred).
- If the schedule fails, try temporarily disabling a doctor (set `"Enabled"` to FALSE) to debug constraints.

---

## 👤 About

Created by **Eryk Makowski**  
This tool is provided free of charge to support healthcare scheduling.

For feedback or help, contact the developer.