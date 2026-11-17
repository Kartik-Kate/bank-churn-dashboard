# 🏦 Customer Segmentation & Churn Pattern Analytics in European Banking

An interactive Streamlit dashboard that analyses customer churn across **10,000 retail banking customers** in **France, Germany and Spain**. It shows where churn concentrates, how strongly each customer attribute drives it, and what retention actions follow from it.

🔗 **Live app:** `https://bank-churn-dashboard-muiq5siwkfobmxgd7vwhwk.streamlit.app/`

---

## 📌 Table of Contents

- [Project Overview](#-project-overview)
- [Problem Statement](#-problem-statement)
- [Key Findings](#-key-findings)
- [Features](#-features)
- [Dataset](#-dataset)
- [Segmentation Design](#-segmentation-design)
- [KPIs](#-kpis)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Installation & Setup](#-installation--setup)
- [How to Use](#-how-to-use)
- [Limitations](#-limitations)
- [Author](#-author)

---

## 📖 Project Overview

Customer churn is one of the largest hidden costs in retail banking. Banks usually track an overall churn rate, but that single number hides *which* customers leave and *why*. This project applies segmentation-driven analytics to answer:

- Which customer groups are most likely to churn?
- How does churn differ across countries, age groups and financial profiles?
- Is churn concentrated among high-value or low-value customers?

The project has three deliverables: this Streamlit dashboard, a Power BI report, and a research paper with an executive summary.

## ❗ Problem Statement

Without structured analytics, churn management stays generic, reactive and inefficient. This project identifies high-risk segments, explains geographic and demographic differences, and quantifies the financial profile of churned customers so retention effort can be targeted.

## 🔍 Key Findings

| Metric | Result |
|---|---|
| Overall churn rate | **20.37%** (2,037 of 10,000) |
| Highest-churn country | **Germany, 32.44%** (Geographic Risk Index 159) |
| Highest-churn age group | **46–60, 51.12%** (about 7x the under-30 rate) |
| Inactive vs active members | **26.85% vs 14.27%** (1.88x) |
| High-value customers (balance ≥ €100,000) | **25.23%** churn |
| Estimated revenue at risk | **€3.19M** (assumes a 2% margin) |
| Riskiest combined segment | Age 46–60 + Inactive + Germany: **80.8%** churn (276 customers) |
| Strongest statistical driver | Number of Products (Cramér's V = 0.39), then Age (0.35) |

> Customers with 3 or 4 products churn at 82.7% and 100%. This should be verified against source data before acting on it (see [Limitations](#-limitations)).

## ✨ Features

The dashboard has seven tabs:

1. **Overall Summary:** churned vs retained split, average profile comparison, auto-generated key findings.
2. **Geography:** churn by country, country summary table, Geography × Age heatmap.
3. **Age & Tenure:** churn by age segment and tenure group.
4. **Segments & Demographics:** gender, credit band, balance segment, activity status, number of products, and churn contribution by segment.
5. **High-Value Explorer:** adjustable balance threshold, balance lost to churn, revenue-at-risk estimate with an editable margin, salary vs balance scatter, and a downloadable list of churned high-value customers.
6. **Risk Ranking & Stats:** top 2–3 factor segment combinations, plus chi-square tests with Cramér's V effect sizes.
7. **Recommendations:** suggested retention action for the highest-churn group in each dimension.

**User capabilities**
- Sidebar filters for all seven segment dimensions, with KPIs updating live.
- Adjustable high-value balance threshold.
- Built-in data validation (12 checks) and optional CSV upload.
- Downloads for the filtered data and the key findings.

## 📂 Dataset

`European_Bank.csv` contains 10,000 customer records with no missing values or duplicate IDs.

| Column | Description |
|---|---|
| CustomerId | Unique customer identifier |
| Surname | Customer surname (dropped during cleaning) |
| CreditScore | Customer creditworthiness (350–850) |
| Geography | France, Spain or Germany |
| Gender | Male / Female |
| Age | Customer age (18–92) |
| Tenure | Years with the bank (0–10) |
| Balance | Account balance (EUR) |
| NumOfProducts | Number of bank products (1–4) |
| HasCrCard | Credit card ownership (0/1) |
| IsActiveMember | Activity indicator (0/1) |
| EstimatedSalary | Estimated annual salary (EUR) |
| Exited | Churn indicator, the target (1 = churned) |

The file also has a constant `Year` column (2025), which is not used in the analysis.

## 🧩 Segmentation Design

| Dimension | Segments |
|---|---|
| Geography | France, Spain, Germany |
| Age Segment | <30, 30–45, 46–60, 60+ |
| Credit Band | Low (<580), Medium (580–669), High (670+) |
| Tenure Group | New (0–2 yrs), Mid-term (3–6), Long-term (7+) |
| Balance Segment | Zero-balance, Low-balance, High-balance (≥ €100,000 by default) |
| Activity Status | Active, Inactive |

## 📊 KPIs

- **Overall Churn Rate:** share of customers who exited.
- **Segment Churn Rate:** churn % within each segment.
- **High-Value Churn Ratio:** churn among customers above the balance threshold.
- **Geographic Risk Index:** a country's churn rate ÷ overall churn × 100 (100 = average).
- **Engagement Drop Indicator:** inactive churn rate ÷ active churn rate.

## 🛠 Tech Stack

| Layer | Tool | Purpose |
|---|---|---|
| Language | Python 3 | Core development |
| Data processing | pandas | Cleaning, validation, segmentation, aggregation |
| Statistics | SciPy | Chi-square tests, Cramér's V |
| Visualisation | Plotly Express | Interactive charts and heatmaps |
| Web app | Streamlit | Dashboard UI, filters, tabs |
| BI report | Microsoft Power BI | Companion report with Key Influencers and Decomposition Tree |
| Hosting | Streamlit Community Cloud + GitHub | Live deployment |

## 📁 Project Structure

```
bank-churn-dashboard/
├── new_main.py          # Streamlit application
├── European_Bank.csv    # Dataset
├── requirements.txt     # Python dependencies
└── README.md            # Project documentation
```

## ⚙️ Installation & Setup

**1. Clone the repository**

```bash
git clone https://github.com/<your-username>/bank-churn-dashboard.git
cd bank-churn-dashboard
```

**2. (Optional) Create a virtual environment**

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Run the app**

```bash
streamlit run new_main.py
```

The app opens at `http://localhost:8501`. Keep `European_Bank.csv` in the same folder as `new_main.py`, or upload it from the sidebar.

## 🚀 How to Use

1. Use the **sidebar filters** to narrow the customer base; every KPI and chart updates.
2. Move the **high-value threshold** slider to redefine "high-value" customers.
3. Browse the **seven tabs** for each analysis module.
4. Tick **"Run chi-square tests"** in the Risk Ranking tab to see statistical significance.
5. Open **Recommendations** for suggested retention actions.
6. Use the **Downloads** section in the sidebar to export the filtered data or findings.

## ⚠️ Limitations

- The data is a single snapshot with no transaction history, so it shows who churned, not the behaviour that preceded it.
- The 100% churn at 4 products (and 82.7% at 3) comes from small groups and may reflect a process artefact rather than customer preference.
- The €3.19M revenue figure uses an assumed 2% margin, not the bank's actual margin.
- Findings show association, not causation.
- Only three European markets are covered; results may not generalise elsewhere.

## 👤 Author

**Kartik Kate**
Contact: `kartikkate1418@gmail.com`

---

*Built as part of the Customer Segmentation & Churn Pattern Analytics in European Banking project.*
