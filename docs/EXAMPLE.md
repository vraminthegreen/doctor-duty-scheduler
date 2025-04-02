# 🧪 Example Schedule Setup

This document describes how to translate real-world constraints and preferences into entries in the input spreadsheet.  
The example below refers to the month **May 2025**.

Here is a sample list of duty constraints and preferences as they might be written by the person managing the scheduling:

**📅 Fixed assignments for early May (pre-filled in the schedule):**
- **May 1** – MD. Baker  
- **May 2** – MD. Foster  
- **May 3** – MD. Nelson  
- **May 4** – DO. Harris  

**📌 Flexible entries by specialists (manually added to the schedule):**
- **MD. Foster** – May 2, May 31  
- **PhD. Patel** – May 8  
- **MD. Baker** – May 1, May 15  

**🧑‍⚕️ Doctor-specific constraints and preferences:**

**Dr. Evans**  
• Cannot work: May 5, 23, 28, 29  
• Prefers duties during the last week of May  
• If assigned a weekend, prefers Sunday  
• Generally prefers fewer duties  

**Dr. Grant**  
• Cannot work: May 18  
• Wants 2 duties – one during the week, one on a weekend  

**PhD. Daniels**  
• Cannot work: last two Thursdays, May 5, May 24–25  
• Prefers: 2 weekday duties + 1 weekend  

**DO. Harris**  
• Cannot work: May 1–3, May 8–16  
• Prefers: May 19–20, May 26–27  
• Ideally 2 duties, 3 only if needed  

**Dr. Carter**  
• Cannot work: all Mondays; also May 2, May 10–11, May 24, May 28–30  
• Prefers: at least one Friday–Sunday block  
• Would like 3 duties  

**MD. Nelson**  
• No Tuesdays, and unavailable on May 18  

**Dr. Irving**  
• Cannot work: May 9–19 and May 22  
• Prefers 2 weekday duties  

**MD. Johnson**  
• Cannot work: May 12–14 and May 27  
• Prefers duties in the first half of May  
• Open to 3 duties  

**Dr. Adams**  
• Strongly prefers not to be scheduled (busy in ER)  

**Dr. King**  
• Cannot work: Mondays and May 8–21  
• Available: May 6 and any day after May 21  
• Prefers a weekend duty  

**PhD. Lewis**  
• Cannot work: May 26–30  
• Previously scheduled and was satisfied with: May 9, 14, 20  

**Dr. Owens**  
• Prefers to be scheduled on Fridays

## 🎯 Fixed Assignments

The following are fixed and must be respected:

| Date       | Doctor       | Type       |
|------------|--------------|------------|
| 01.05      | MD. Baker    | Yes        |
| 02.05      | MD. Foster   | Yes        |
| 03.05      | MD. Nelson   | Yes        |
| 04.05      | DO. Harris   | Yes        |
| 08.05      | PhD. Patel   | Willing    |
| 15.05      | MD. Baker    | Willing    |
| 31.05      | MD. Foster   | Willing    |

## 👤 Doctor-Specific Preferences

### Dr. Evans
- **Cannot work**: 5, 23, 28, 29 May → mark as "No"
- **Prefers**: last week of May → mark with "Willing" for 25–31 May
- **If weekend**: only Sunday → mark Saturdays as "No", Sundays as "Auto" or "Willing"
- **Fewer shifts preferred** → enable "Prefer Sparse Schedule"

### Dr. Grant
- **Cannot work**: 18 May → "No"
- **Wants 2 shifts total**, one weekday and one weekend → set "Preferred Shifts" to 2

### PhD. Daniels
- **Cannot work**: 5, 23, 30 May and last two Thursdays (16, 23 May) → "No"
- **Prefers**: 2 weekday shifts + 1 weekend → "Preferred Weekday Shifts" = 2, "Preferred Weekend Shifts" = 1

### DO. Harris
- **Cannot work**: 1–3, 8–16 May → "No"
- **Prefers**: 19, 20, 26, 27 May → "Willing"
- **Shifts**: ideally 2, but max 3 → Preferred = 2, Max = 3

### Dr. Carter
- **Cannot work**: all Mondays, 2, 10–11, 24, 28–30 May → "No"
- **Prefers**: at least one Fri–Sun combo → "Willing" on 3, 4, 17, 18, 24, 25 May
- **Wants 3 shifts** → "Preferred Shifts" = 3

### MD. Nelson
- **Cannot work**: all Tuesdays + 18 May → mark those as "No"

### Dr. Irving
- **Cannot work**: 9–19, 22 May → "No"
- **Prefers**: 2 weekday shifts → "Preferred Weekday Shifts" = 2

### MD. Johnson
- **Cannot work**: 12–14, 27 May → "No"
- **Prefers**: first 2 weeks of May → "Willing" on 1–14 May
- **Wants 3 shifts** → "Preferred Shifts" = 3

### Dr. Adams
- **Generally reluctant** → mark many cells as "Unwilling", enable "Prefer Sparse Schedule"

### Dr. King
- **Cannot work**: Mondays, 8–21 May → "No"
- **Prefers**: 6 and any date after 21 → mark 6 and 22–31 May as "Willing"
- **Wants weekend** → "Willing" on 24–26 May

### PhD. Lewis
- **Cannot work**: 26–30 May → "No"
- **Preferred previously**: 9, 14, 20 May → mark these as "Willing"

### Dr. Owens
- **Prefers Fridays** → mark all Fridays as "Willing"