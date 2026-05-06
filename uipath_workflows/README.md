# UiPath Workflow Reference

This folder contains pseudo-code representations of how each Python automation in this toolkit would be implemented as a UiPath workflow (`.xaml`). The actual XAML files are not committed because they are XML-heavy and not human-readable, but the structure below maps directly to the activities a developer would drag onto the Designer canvas.

I built and maintain UiPath bots professionally. The Python implementations in this repo are educational reproductions of the same patterns — they run anywhere without an Orchestrator license and are easier to version-control and review.

---

## 1. Web Scraping Bot — `WebScraperWorkflow.xaml`

```
Sequence "Main"
├── Try
│   ├── Open Browser ("https://example.com")
│   │   └── Sequence
│   │       ├── Navigate To "/users"
│   │       ├── Get Text → strHtmlContent
│   │       ├── For Each row in DataExtractionScope
│   │       │   ├── Assign userId   = row("id")
│   │       │   ├── Assign userName = row("name")
│   │       │   └── Add Data Row → dtUsers
│   │       └── Write CSV (dtUsers, "output\users.csv")
│   └── Close Browser
└── Catch (System.Exception)
    ├── Log Message ("Bot failed: " + exception.Message, Level=Error)
    └── Send Outlook Mail ("RPA failure alert", body)
```

Key UiPath activities used: **Open Browser**, **Data Scraping (Extract Structured Data)**, **For Each Row**, **Build Data Table**, **Write CSV**, **Try Catch**, **Send Outlook Mail Message**.

---

## 2. Excel Consolidator Bot — `ExcelConsolidatorWorkflow.xaml`

```
Sequence "Main"
├── Assign strInputFolder = "C:\Inputs"
├── Build Data Table → dtMaster (columns: customer_id, transaction_date, amount, branch)
├── For Each File in Folder (strInputFolder, *.xlsx)
│   └── Sequence
│       ├── Excel Application Scope (CurrentFile.FullName)
│       │   ├── Read Range "Sheet1" → dtCurrent
│       │   ├── Filter Data Table (remove blanks)
│       │   └── Merge Data Table (dtMaster ← dtCurrent)
│       └── Log Message ("Processed: " + CurrentFile.Name)
├── Remove Data Row (duplicates on customer_id + transaction_date)
└── Excel Application Scope ("output\consolidated.xlsx")
    └── Write Range (dtMaster, "Sheet1", AddHeaders=True)
```

Key activities: **For Each File in Folder**, **Excel Application Scope**, **Read Range**, **Merge Data Table**, **Filter Data Table**, **Remove Duplicate Rows**, **Write Range**.

---

## 3. Report Generation Bot — `WeeklyReportWorkflow.xaml`

```
Sequence "Main"
├── Excel Application Scope ("output\consolidated.xlsx")
│   └── Read Range → dtSales
├── Word Application Scope (template "weekly_report_template.docx")
│   ├── Replace Text in Document ({{TOTAL_REVENUE}}, formatted total)
│   ├── Replace Text in Document ({{TRANSACTION_COUNT}}, ...)
│   ├── Insert Picture (chart_revenue.png)
│   ├── Insert Picture (chart_branch.png)
│   └── Save Document as PDF → "output\weekly_report.pdf"
└── Send Outlook Mail Message
    ├── To: "leadership@company.com"
    ├── Subject: "Weekly Sales Report — " + Now.ToString("yyyy-MM-dd")
    └── Attachment: "output\weekly_report.pdf"
```

Key activities: **Excel Application Scope**, **Word Application Scope**, **Replace Text in Document**, **Insert Picture**, **Save Document as PDF**, **Send Outlook Mail Message**.

---

## 4. CRM-ERP Sync Bot — `CrmErpSyncWorkflow.xaml`

```
Sequence "Main"
├── Connect to Database (CRM connection string)
│   └── Execute Query "SELECT * FROM customers WHERE updated_at >= @cutoff"
│       → dtCrmUpdates
├── Connect to Database (ERP connection string)
│   └── For Each Row in dtCrmUpdates
│       ├── Try
│       │   ├── Execute Non Query "SELECT 1 FROM customers WHERE customer_id=@id"
│       │   ├── If (rowExists)
│       │   │   ├── Then: Execute Non Query "UPDATE customers ..."
│       │   │   └── Else: Execute Non Query "INSERT INTO customers ..."
│       │   └── Increment intSuccessCount
│       └── Catch
│           ├── Log Message (level=Error, "Failed: " + row("customer_id"))
│           └── Increment intFailCount
└── Send Slack Message ("Sync complete: " + intSuccessCount + " ok, " + intFailCount + " fail")
```

Key activities: **Connect**, **Execute Query**, **Execute Non Query**, **For Each Row**, **Try Catch**, **Log Message**, **Send Slack Message**.

---

## REFramework alignment

All four workflows are designed to be wrapped in UiPath's REFramework (Robotic Enterprise Framework) — the standard pattern for production bots. The Python `BaseAutomation` class in `src/utils/base_automation.py` mirrors the four REFramework states:

| REFramework state | Python equivalent |
| ----------------- | ----------------- |
| Init              | `setup()`         |
| Get Transaction   | (custom per bot)  |
| Process           | `run()`           |
| End Process       | `teardown()` + `report()` |

This lets a developer who knows REFramework read the Python code and immediately recognize the structure.
