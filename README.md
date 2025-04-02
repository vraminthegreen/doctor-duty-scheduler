# 🩺 Doctor Duty Scheduler

This is a scheduling tool designed to generate optimal on-call duty rosters for medical teams using constraint-based optimization with **AMPL** and **HiGHS**.

Originally created for a neonatal hospital department in Poland, the tool helps automate the tedious process of planning doctor duties while respecting constraints such as rest periods, cost preferences, and shift frequency.

---

## ✨ Features

- Easy integration with **Google Sheets**
- Reads doctor preferences and constraints directly from spreadsheet
- Enforces limits like:
  - Minimum/maximum number of shifts
  - Rest days between duties
  - Preferred/avoided days
  - Weekend/weekday distribution
  - Dense vs. sparse scheduling preference
- Generates two output sheets:
  - ✅ **Full Schedule**: Matrix of dates × doctors
  - ✅ **Short Schedule**: Just who is on duty each day
- GUI built in **Streamlit** – runs in the browser!

---

## 🛠️ Technologies Used

- [AMPL](https://ampl.com/) (Community Edition)
- [HiGHS](https://highs.dev/)
- [Python 3.13+](https://www.python.org/)
- [Streamlit](https://streamlit.io/)
- [gspread](https://github.com/burnash/gspread) for Google Sheets API

---

// TODO: share the example spreadsheet
// TODO: DEMO section
// app link: https://doctor-duty-scheduler.streamlit.app
// TODO: debugging description (disabling doctors)
// TODO: author's mail
// TODO: constraints

## 📘 User Instructions

See full instructions here: [docs/INSTRUCTIONS.md](docs/INSTRUCTIONS.md)
Example: [docs/EXAMPLE.md](docs/EXAMPLE.md)

## 🚀 Getting Started (for Developers)

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/doctor-duty-scheduler.git
cd doctor-duty-scheduler
```

### 2. Create a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
# or if you want to use specific pythin version
python3 -m pip install -r requirements.txt
```

### 4. Run the App

```bash
streamlit run app.py
# or
python3 -m streamlit run app.py
```

---

## 🔐 Google Sheets Authorization

You need a `credentials.json` file from a Google Service Account with access to the spreadsheets.

📦 The app will prompt you to upload it.

Developers: [How to generate credentials](https://developers.google.com/workspace/guides/create-credentials)

---

## 👨‍⚕️ Author

Developed and maintained pro bono by **Eryk Makowski** 🇵🇱

---

## 🧪 License

This project is non-commercial and designed for internal hospital use. If you're interested in expanding or commercializing it, feel free to get in touch.

