# ---------- 1. IMPORTS ----------
import itertools                  # builds combinations of segment dimensions (for risk ranking)
import pandas as pd               # handles the data table (called a DataFrame)
import plotly.express as px       # makes interactive charts
import streamlit as st            # builds the web app (buttons, sliders, layout)
from scipy.stats import chi2_contingency   # statistical test: is a churn gap real or random noise?

# ---------- 2. PAGE SETUP ----------
# Must be the FIRST Streamlit command. "wide" uses the full screen width.
st.set_page_config(page_title="Bank Churn Dashboard", page_icon="🏦", layout="wide")
st.title("🏦 Bank Customer Churn Analytics")   # big title at the top
st.caption("Markets: France, Spain, Germany | Prepared by Kartik Kate")  # small grey text under the title

# ---------- 3. CONSTANTS (values we reuse) ----------
# Columns the app needs. If any is missing, we stop with a clear error.
REQUIRED_COLS = [
    "CustomerId", "CreditScore", "Geography", "Gender", "Age", "Tenure",
    "Balance", "NumOfProducts", "HasCrCard", "IsActiveMember",
    "EstimatedSalary", "Exited",
]

# Dimensions used by the segment filters, the risk ranking and the recommendations engine.
# Kept in one place so every feature stays in sync if you add/remove a segment later.
SEGMENT_DIMENSIONS = [
    "Geography", "Gender", "Age Segment", "Credit Band",
    "Tenure Group", "Balance Segment", "Activity Status",
]

# ---------- 4. HELPER FUNCTIONS ----------
# A function = a reusable block of code. We define them first, use them later.

@st.cache_data   # remembers the result so the CSV isn't re-read on every click
def load_data(source):
    """Read the CSV file (or the uploaded file) into a DataFrame."""
    return pd.read_csv(source)


def run_validation(df):
    """Step 1: validate fields. Returns {check name: True/False}.
    Covers both data-type consistency (binary columns, uniqueness) and plausibility
    (values that are the right type but outside a sane real-world range)."""
    return {
        "No missing values in required columns": df[REQUIRED_COLS].isna().sum().sum() == 0,
        "Exited contains only 0 or 1": df["Exited"].isin([0, 1]).all(),
        "HasCrCard contains only 0 or 1": df["HasCrCard"].isin([0, 1]).all(),
        "IsActiveMember contains only 0 or 1": df["IsActiveMember"].isin([0, 1]).all(),
        "CustomerId is unique (no duplicates)": df["CustomerId"].is_unique,
        "NumOfProducts is at least 1": (df["NumOfProducts"] >= 1).all(),
        "Geography is France / Spain / Germany": df["Geography"].isin(["France", "Spain", "Germany"]).all(),
        "Gender is Male or Female": df["Gender"].isin(["Male", "Female"]).all(),
        "Age is plausible (18-100)": df["Age"].between(18, 100).all(),
        "CreditScore is plausible (300-900)": df["CreditScore"].between(300, 900).all(),
        "Balance is not negative": (df["Balance"] >= 0).all(),
        "EstimatedSalary is not negative": (df["EstimatedSalary"] >= 0).all(),
    }


def prepare(df, hv_threshold):
    """Step 2: clean the data and create segment columns."""
    df = df.drop(columns=["Surname", "RowNumber"], errors="ignore")  # remove non-analytical columns (ignore if absent)
    df = df.copy()                                                   # work on a copy, keep the original safe

    # Readable text labels (easier on charts than 0/1)
    df["Customer Status"] = df["Exited"].map({1: "Churned", 0: "Retained"})
    df["Activity Status"] = df["IsActiveMember"].map({1: "Active", 0: "Inactive"})

    # pd.cut sorts numbers into bins; each bin includes its upper edge.
    # Bins: <30 = 18-29, 30–45 = 30-45, 46–60 = 46-60, 60+ = 61 and over.
    # A 60-year-old lands in "46–60" (the label includes 60), which matches the
    # Power BI Age_Segment column, so both tools report the same numbers.
    df["Age Segment"] = pd.cut(df["Age"], bins=[0, 29, 45, 60, 120],
                               labels=["<30", "30–45", "46–60", "60+"])
    # Credit score bands: Low <580, Medium 580-669, High 670+
    df["Credit Band"] = pd.cut(df["CreditScore"], bins=[0, 579, 669, 900],
                               labels=["Low", "Medium", "High"])
    # Tenure groups: New 0-2 yrs, Mid-term 3-6, Long-term 7+
    df["Tenure Group"] = pd.cut(df["Tenure"], bins=[-1, 2, 6, 100],
                                labels=["New", "Mid-term", "Long-term"])

    # Balance segments built step by step so the logic is easy to read
    df["Balance Segment"] = "Low-balance"                                     # start everyone as low
    df.loc[df["Balance"] == 0, "Balance Segment"] = "Zero-balance"            # exactly 0
    df.loc[df["Balance"] >= hv_threshold, "Balance Segment"] = "High-balance" # at/above slider value
    df["Balance Segment"] = pd.Categorical(                                   # fix the display order
        df["Balance Segment"],
        categories=["Zero-balance", "Low-balance", "High-balance"],
        ordered=True,
    )
    return df


def churn_table(data, column):
    """Churn rate + size + contribution for each group in one column."""
    t = data.groupby(column, observed=True)["Exited"].agg(
        Customers="count",   # how many customers in the group
        Churned="sum",       # how many left (Exited=1, so sum = count of leavers)
    ).reset_index()
    t[column] = t[column].astype(str)  # plain text labels for charts
    t["Churn Rate (%)"] = (t["Churned"] / t["Customers"] * 100).round(1)
    t["Share of Customers (%)"] = (t["Customers"] / t["Customers"].sum() * 100).round(1)
    total_churned = t["Churned"].sum()
    if total_churned > 0:   # avoid dividing by zero
        t["Share of Churners (%)"] = (t["Churned"] / total_churned * 100).round(1)
    else:
        t["Share of Churners (%)"] = 0.0
    return t


def churn_bar(data, column, title, overall_rate):
    """Bar chart of churn rate per group, with a dashed overall-average line."""
    t = churn_table(data, column)
    fig = px.bar(t, x=column, y="Churn Rate (%)", text="Churn Rate (%)",
                 hover_data=["Customers", "Churned"], title=title)
    fig.update_traces(texttemplate="%{text}%", textposition="outside")   # show value on bars
    fig.add_hline(y=overall_rate * 100, line_dash="dash",
                  annotation_text="Overall average",
                  annotation_position="top left")                        # moved off the bar labels
    fig.update_layout(yaxis_range=[0, max(t["Churn Rate (%)"].max() * 1.35, 5)])  # more headroom
    return fig


def heatmap(data, row, col, title):
    """Two-way churn table drawn as a colour grid (interaction analysis)."""
    pivot = data.pivot_table(index=row, columns=col, values="Exited",
                             aggfunc="mean", observed=True) * 100
    fig = px.imshow(pivot.round(1), text_auto=".1f", aspect="auto",
                    color_continuous_scale="Reds", title=title,
                    labels={"color": "Churn %"})
    return fig


def key_findings(data, overall_rate, hv_threshold, min_n=30, min_gap=2.0):
    """Write plain-English findings from the (filtered) data. Returns a list of text lines.
    min_n   = groups smaller than this are 'small' (rates swing wildly), reported separately
    min_gap = gaps smaller than this many percentage points are called 'no meaningful difference'
    """
    lines = []   # we collect sentences here, one per finding

    # Finding 1: headline numbers
    lines.append(f"**{int(data['Exited'].sum()):,}** of **{len(data):,}** customers churned "
                 f"(**{overall_rate * 100:.1f}%**).")

    dimensions = [("Geography", "Geography"), ("Gender", "Gender"), ("Age Segment", "Age"),
                  ("Tenure Group", "Tenure"), ("Credit Band", "Credit score"),
                  ("Balance Segment", "Balance"), ("Activity Status", "Engagement")]
    small_groups = []   # we collect small groups here and report them in one extra line

    for column, label in dimensions:
        t = churn_table(data, column)
        small = t[t["Customers"] < min_n]          # too few customers to trust the rate
        big = t[t["Customers"] >= min_n]           # large enough for a fair comparison
        for _, r in small.iterrows():              # remember each small group for later
            small_groups.append(f"{label} = {r[column]} (n={int(r['Customers'])}, "
                                f"{int(r['Churned'])} churned, {r['Churn Rate (%)']}%)")

        if len(big) >= 2:                          # compare only reliable groups
            hi = big.loc[big["Churn Rate (%)"].idxmax()]
            lo = big.loc[big["Churn Rate (%)"].idxmin()]
            gap = hi["Churn Rate (%)"] - lo["Churn Rate (%)"]
            if gap < min_gap:                      # tiny gap = probably just random variation
                lines.append(f"**{label}:** churn is similar across groups "
                             f"({lo['Churn Rate (%)']}% to {hi['Churn Rate (%)']}%), "
                             f"so no meaningful difference.")
            else:
                lines.append(
                    f"**{label}:** highest churn in **{hi[column]}** ({hi['Churn Rate (%)']}%), "
                    f"lowest in **{lo[column]}** ({lo['Churn Rate (%)']}%), a gap of {gap:.1f} points. "
                    f"{hi[column]} makes up {hi['Share of Customers (%)']}% of customers "
                    f"but {hi['Share of Churners (%)']}% of churners.")
        elif len(big) == 1:                        # only one reliable group, nothing to compare
            r = big.iloc[0]
            lines.append(f"**{label}:** only **{r[column]}** has enough customers in this selection "
                         f"({r['Churn Rate (%)']}% churn).")

    # Extra line for small groups: shown, but clearly flagged
    if small_groups:
        lines.append("**Small groups: (under " + str(min_n) + " customers)** "
                     + "; ".join(small_groups) + ". One or two customers can swing these rates a lot.")

    # Last finding: money at risk among high-value customers
    hv = data[data["Balance"] >= hv_threshold]
    hv_lost = hv[hv["Exited"] == 1]
    if len(hv) > 0:
        note = " (small sample, treat with caution)" if len(hv) < min_n else ""
        lines.append(f"**High-value customers** (balance ≥ €{hv_threshold:,.0f}): "
                     f"{len(hv_lost):,} of {len(hv):,} churned, taking "
                     f"**€{hv_lost['Balance'].sum():,.0f}** in balances{note}.")
    return lines


def findings_to_text(lines):
    """Turn the markdown-bold findings into a plain-text block for the TXT download."""
    return "\n".join("- " + line.replace("**", "") for line in lines)


def chi_square_test(data, column, alpha=0.05):
    """Chi-square test of independence: is this segment's churn gap a real pattern,
    or could it plausibly be random noise? Also returns Cramér's V, an effect-size
    measure (0 = no association, 1 = perfect association) — a result can be
    'statistically significant' and still be a weak practical driver."""
    contingency = pd.crosstab(data[column], data["Exited"])
    chi2, p_value, _, _ = chi2_contingency(contingency)
    n = contingency.sum().sum()
    k = min(contingency.shape) - 1
    cramers_v = (chi2 / (n * k)) ** 0.5 if k > 0 else 0.0
    return {"p_value": p_value, "significant": p_value < alpha, "cramers_v": cramers_v}


@st.cache_data   # 56 groupbys per call: cache so tab clicks / checkboxes don't recompute it
def risk_segment_ranking(data, dimensions, combo_sizes=(2, 3), min_n=100, top_n=5):
    """Combine 2-3 segment dimensions at a time (e.g. Geography + Age Segment + Activity
    Status) and rank the combinations: top N by churn rate, and top N by customers
    affected (churned count). Combinations below min_n customers are dropped: 100 is the
    floor for a segment big enough to target with its own campaign, and it keeps this ranking
    in line with the research paper and the Power BI Decomposition Tree."""
    rows = []
    for size in combo_sizes:
        for combo in itertools.combinations(dimensions, size):
            grouped = data.groupby(list(combo), observed=True)["Exited"].agg(
                Customers="count", Churned="sum"
            ).reset_index()
            grouped = grouped[grouped["Customers"] >= min_n]
            if grouped.empty:
                continue
            grouped["Churn Rate (%)"] = (grouped["Churned"] / grouped["Customers"] * 100).round(1)
            grouped["Segment"] = grouped.apply(
                lambda r: " + ".join(f"{c}={r[c]}" for c in combo), axis=1
            )
            rows.append(grouped[["Segment", "Customers", "Churned", "Churn Rate (%)"]])

    if not rows:
        empty = pd.DataFrame(columns=["Segment", "Customers", "Churned", "Churn Rate (%)"])
        return empty, empty

    combined = pd.concat(rows, ignore_index=True).drop_duplicates(subset=["Segment"])
    by_rate = combined.sort_values("Churn Rate (%)", ascending=False).head(top_n).reset_index(drop=True)
    by_impact = combined.sort_values("Churned", ascending=False).head(top_n).reset_index(drop=True)
    return by_rate, by_impact


# Canned retention actions per segment, used by the Recommendations tab.
# "default" is used when a specific group isn't listed (e.g. a Credit Band value not covered).
ACTION_LIBRARY = {
    "Geography": {
        "default": "Launch a localized retention campaign, assign a regional relationship "
                   "manager, and review country-specific pricing or service gaps.",
    },
    "Gender": {
        "default": "Run a targeted engagement survey to understand drivers for this group; "
                   "review onboarding and communication differences by gender.",
    },
    "Age Segment": {
        "<30": "Offer digital-first engagement and starter-product incentives for younger customers.",
        "30–45": "Focus on relationship-building and cross-sell during peak earning years.",
        "46–60": "Provide retirement and wealth-planning outreach with dedicated advisor check-ins.",
        "60+": "Offer simplified service channels and loyalty recognition for senior customers.",
        "default": "Tailor outreach cadence to this age group's typical banking needs.",
    },
    "Credit Band": {
        "Low": "Offer proactive credit counseling and flexible product terms; add early-warning outreach.",
        "Medium": "Monitor for early churn signals and offer product bundling incentives.",
        "High": "Protect this segment with premium service tiers and preferential rates.",
        "default": "Align the servicing model to this credit band's risk and value profile.",
    },
    "Tenure Group": {
        "New": "Strengthen onboarding with a 90-day check-in call and a welcome incentive.",
        "Mid-term": "Deploy a loyalty milestone offer to deepen the relationship before it drifts.",
        "Long-term": "Launch a win-back / appreciation campaign for long-tenured customers showing disengagement.",
        "default": "Adjust engagement cadence to this tenure stage.",
    },
    "Balance Segment": {
        "Zero-balance": "Run a reactivation campaign with a starter product or cross-sell offer.",
        "Low-balance": "Encourage balance growth through goal-based savings nudges.",
        "High-balance": "Assign a premium relationship manager and offer a personalized financial review.",
        "default": "Tailor retention offers to this balance tier.",
    },
    "Activity Status": {
        "Inactive": "Trigger a dormant-account re-engagement campaign with a personalized reactivation offer.",
        "Active": "Maintain engagement with periodic value-add communication.",
        "default": "Adjust engagement based on activity level.",
    },
    "NumOfProducts": {
        "default": "Review cross-sell strategy for this product count — investigate whether "
                   "customers here are under- or over-exposed to risk, and adjust bundling.",
    },
}


def recommend_action(dimension, value):
    table = ACTION_LIBRARY.get(dimension, {})
    return table.get(str(value), table.get("default", "Investigate this segment and design a targeted retention offer."))


def generate_recommendations(data, overall_rate, min_n=30, min_gap=2.0):
    """For each dimension, find the highest-churn group (if it's reliably above the
    overall average) and attach a recommended action. Returns a list of dicts, sorted
    by churn rate, highest risk first."""
    dimensions = SEGMENT_DIMENSIONS + ["NumOfProducts"]
    recs = []
    for col in dimensions:
        t = churn_table(data, col)
        big = t[t["Customers"] >= min_n]
        if big.empty:
            continue
        hi = big.loc[big["Churn Rate (%)"].idxmax()]
        gap = hi["Churn Rate (%)"] - overall_rate * 100
        if gap >= min_gap:
            recs.append({
                "Dimension": col,
                "Segment": str(hi[col]),
                "Churn Rate (%)": hi["Churn Rate (%)"],
                "Customers Affected": int(hi["Customers"]),
                "Churned": int(hi["Churned"]),
                "Gap vs Average (pts)": round(gap, 1),
                "Recommended Action": recommend_action(col, hi[col]),
            })
    recs.sort(key=lambda r: r["Churn Rate (%)"], reverse=True)
    return recs


# ---------- 5. SIDEBAR: LOAD DATA ----------
st.sidebar.header("📂 Data")
uploaded_file = st.sidebar.file_uploader("Upload churn CSV (optional)", type="csv")
# If a file was uploaded use it, otherwise look for this file next to new_main.py
source = uploaded_file if uploaded_file is not None else "European_Bank.csv"

try:
    raw_df = load_data(source)
except FileNotFoundError:
    st.error("European_Bank.csv not found. Put it in the same folder as new_main.py, or upload it in the sidebar.")
    st.stop()   # stop the app here, nothing below runs

missing = [c for c in REQUIRED_COLS if c not in raw_df.columns]
if missing:
    st.error(f"Dataset is missing these columns: {missing}")
    st.stop()

# Show validation results in a collapsible box
with st.sidebar.expander("✅ Data validation", expanded=False):
    for name, passed in run_validation(raw_df).items():
        st.write(("✅ " if passed else "❌ ") + name)

# ---------- 6. SIDEBAR: HIGH-VALUE DEFINITION ----------
# ONE definition of "high-value", used by KPIs, segments and Module 5.
st.sidebar.header("💎 High-value definition")
hv_threshold = st.sidebar.slider("High-value balance threshold (€)",
                                 min_value=50_000, max_value=250_000,
                                 value=100_000, step=10_000)

df = prepare(raw_df, hv_threshold)   # clean data + add segment columns

# ---------- 7. SIDEBAR: SEGMENT FILTERS ----------
st.sidebar.header("🎛️ Segment filters")

def multiselect_filter(label, column):
    """Create a multiselect box with all options picked by default."""
    if isinstance(df[column].dtype, pd.CategoricalDtype):
        options = list(df[column].cat.categories)   # keeps our custom order
    else:
        options = sorted(df[column].unique())       # alphabetical for plain text
    return st.sidebar.multiselect(label, options, default=options)

sel_geo = multiselect_filter("Geography", "Geography")
sel_gender = multiselect_filter("Gender", "Gender")
sel_age = multiselect_filter("Age segment", "Age Segment")
sel_credit = multiselect_filter("Credit band", "Credit Band")
sel_tenure = multiselect_filter("Tenure group", "Tenure Group")
sel_balance = multiselect_filter("Balance segment", "Balance Segment")
sel_activity = multiselect_filter("Activity status", "Activity Status")

# Keep only rows that match ALL filters (& means AND)
filtered = df[
    df["Geography"].isin(sel_geo)
    & df["Gender"].isin(sel_gender)
    & df["Age Segment"].isin(sel_age)
    & df["Credit Band"].isin(sel_credit)
    & df["Tenure Group"].isin(sel_tenure)
    & df["Balance Segment"].isin(sel_balance)
    & df["Activity Status"].isin(sel_activity)
]

# Safety: if filters remove everyone, warn and stop (prevents "nan%" errors)
if filtered.empty:
    st.warning("No customers match the selected filters. Widen your selection.")
    st.stop()

# ---------- 8. KPI CALCULATIONS (update with filters) ----------
overall_rate = filtered["Exited"].mean()   # mean of 0/1 column = share who left

# High-Value Churn Ratio: churn among customers at/above the threshold
hv_group = filtered[filtered["Balance"] >= hv_threshold]
hv_text = f"{hv_group['Exited'].mean() * 100:.1f}%" if len(hv_group) > 0 else "n/a"

# Geographic Risk Index: country churn / overall churn x 100 (100 = average)
geo_rates = filtered.groupby("Geography")["Exited"].mean()
geo_index = (geo_rates / overall_rate * 100) if overall_rate > 0 else geo_rates * 0
top_geo = geo_index.idxmax()   # country with the highest index

# Engagement Drop Indicator: inactive churn rate / active churn rate
act_rates = filtered.groupby("Activity Status")["Exited"].mean()
if "Active" in act_rates.index and "Inactive" in act_rates.index and act_rates["Active"] > 0:
    engagement_text = f"{act_rates['Inactive'] / act_rates['Active']:.2f}x"
else:
    engagement_text = "n/a"

# Computed ONCE per rerun and reused below (sidebar download + Tab 1, Tab 6 + Tab 7),
# instead of recalculating the same thing in several places.
findings = key_findings(filtered, overall_rate, hv_threshold)
by_rate, by_impact = risk_segment_ranking(filtered, SEGMENT_DIMENSIONS)

# ---------- 9. SIDEBAR: DOWNLOADS ----------
# Placed after the KPI calculations above because it needs `filtered` and `findings`.
# Streamlit appends sidebar elements in the order the code runs, so this still renders
# in the sidebar even though it's defined here rather than earlier.
with st.sidebar.expander("⬇️ Downloads", expanded=False):
    st.download_button(
        "Filtered data (CSV)",
        filtered.to_csv(index=False),
        file_name="filtered_customers.csv",
    )
    st.download_button(
        "Key findings (TXT)",
        findings_to_text(findings),
        file_name="key_findings.txt",
    )

# ---------- 10. KPI CARDS ----------
c1, c2, c3, c4, c5 = st.columns(5)   # 5 side-by-side boxes
c1.metric("Customers (filtered)", f"{len(filtered):,}")
c2.metric("Overall Churn Rate", f"{overall_rate * 100:.1f}%")
c3.metric("High-Value Churn Ratio", hv_text)
c4.metric(f"Geographic Risk Index ({top_geo})", f"{geo_index[top_geo]:.0f}",
          help="Highest-risk country. 100 = average churn. Above 100 = riskier than average.")
c5.metric("Engagement Drop Indicator", engagement_text,
          help="How many times more likely inactive members are to churn vs active members.")

# ---------- 11. TABS (one per module) ----------
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "1 · Overall Summary", "2 · Geography", "3 · Age & Tenure",
    "4 · Segments & Demographics", "5 · High-Value Explorer",
    "6 · Risk Ranking & Stats", "7 · Recommendations",
])

# ===== TAB 1: OVERALL SUMMARY =====
with tab1:
    left, right = st.columns(2)
    with left:
        # Donut chart: churned vs retained
        status_counts = filtered["Customer Status"].value_counts().reset_index()
        status_counts.columns = ["Customer Status", "Customers"]
        fig = px.pie(status_counts, names="Customer Status", values="Customers",
                     hole=0.5, title="Churned vs Retained",
                     color="Customer Status",
                     color_discrete_map={"Churned": "#d62728", "Retained": "#1f77b4"})
        st.plotly_chart(fig, width="stretch")
    with right:
        # Average profile of churned vs retained customers
        st.subheader("Churned vs Retained profile (averages)")
        profile = filtered.groupby("Customer Status")[
            ["Age", "CreditScore", "Balance", "EstimatedSalary", "Tenure", "NumOfProducts"]
        ].mean().round(1).T   # .T flips rows and columns for easier reading
        st.dataframe(profile, width="stretch")

    st.markdown("---")
    # Key findings box (auto-written from the current filters)
    st.subheader("🔑 Key findings")
    for line in findings:
        st.markdown("- " + line)          # one bullet per finding
    st.caption("Auto-generated from the current filters. Small groups are flagged, and tiny gaps are "
               "called out as no real difference. These show patterns, not proven causes.")

# ===== TAB 2: GEOGRAPHY =====
with tab2:
    left, right = st.columns([2, 1])
    with left:
        st.plotly_chart(churn_bar(filtered, "Geography", "Churn rate by country", overall_rate),
                        width="stretch")
    with right:
        st.subheader("Country summary")
        st.dataframe(churn_table(filtered, "Geography"), width="stretch", hide_index=True)
    # Geography x Age interaction
    st.plotly_chart(heatmap(filtered, "Geography", "Age Segment", "Churn % — Geography × Age"),
                    width="stretch")

# ===== TAB 3: AGE & TENURE =====
with tab3:
    left, right = st.columns(2)
    with left:
        st.plotly_chart(churn_bar(filtered, "Age Segment", "Churn rate by age segment", overall_rate),
                        width="stretch")
    with right:
        st.plotly_chart(churn_bar(filtered, "Tenure Group", "Churn rate by tenure group", overall_rate),
                        width="stretch")
    with st.expander("See the numbers behind the charts"):
        st.dataframe(churn_table(filtered, "Age Segment"), hide_index=True)
        st.dataframe(churn_table(filtered, "Tenure Group"), hide_index=True)

# ===== TAB 4: SEGMENTS & DEMOGRAPHICS =====
with tab4:
    # ---- Gender breakdown (single version: table + metric cards + grouped bar) ----
    st.subheader("Gender breakdown")
    gender_tbl = churn_table(filtered, "Gender")
    st.dataframe(gender_tbl, hide_index=True, width="stretch")

    gcols = st.columns(len(gender_tbl))
    for col, (_, row) in zip(gcols, gender_tbl.iterrows()):
        col.metric(f"{row['Gender']} customers", f"{int(row['Customers']):,}",
                   f"{int(row['Churned']):,} churned ({row['Churn Rate (%)']}%)",
                   delta_color="off")   # "off" = grey text, no green/red arrow

    fig = px.bar(filtered.groupby(["Gender", "Customer Status"]).size().reset_index(name="Customers"),
                 x="Gender", y="Customers", color="Customer Status", barmode="group", text="Customers",
                 title="Customers by gender: retained vs churned",
                 color_discrete_map={"Churned": "#d62728", "Retained": "#1f77b4"})
    st.plotly_chart(fig, width="stretch")
    st.markdown("---")

    # 2x2 grid of charts
    a, b = st.columns(2)
    with a:
        st.plotly_chart(churn_bar(filtered, "Gender", "Churn by gender", overall_rate), width="stretch")
    with b:
        st.plotly_chart(churn_bar(filtered, "Credit Band", "Churn by credit band", overall_rate), width="stretch")
    c, d = st.columns(2)
    with c:
        st.plotly_chart(churn_bar(filtered, "Balance Segment", "Churn by balance segment", overall_rate), width="stretch")
    with d:
        st.plotly_chart(churn_bar(filtered, "Activity Status", "Churn by activity status", overall_rate), width="stretch")

    # NumOfProducts: a strong churn signal in this dataset that had no chart before
    st.plotly_chart(churn_bar(filtered, "NumOfProducts", "Churn by number of products", overall_rate), width="stretch")

    # Financial stability vs churn
    st.plotly_chart(heatmap(filtered, "Credit Band", "Balance Segment",
                            "Churn % — Credit band × Balance segment"),
                    width="stretch")

    # Contribution analysis: which segment makes up most of the churn?
    st.subheader("Churn contribution by segment size")
    dim_options = {
        "Geography": "Geography", "Gender": "Gender", "Age Segment": "Age Segment",
        "Credit Band": "Credit Band", "Tenure Group": "Tenure Group",
        "Balance Segment": "Balance Segment", "Activity Status": "Activity Status",
        "Number of Products": "NumOfProducts",
    }
    chosen = st.selectbox("Choose a dimension", list(dim_options.keys()))
    st.caption("If 'Share of Churners' is higher than 'Share of Customers', the segment over-contributes to churn.")
    st.dataframe(churn_table(filtered, dim_options[chosen]), hide_index=True, width="stretch")

# ===== TAB 5: HIGH-VALUE EXPLORER =====
with tab5:
    hv = filtered[filtered["Balance"] >= hv_threshold]   # high-value customers
    hv_churned = hv[hv["Exited"] == 1]                   # those who left

    if hv.empty:
        st.info("No high-value customers in the current selection. Lower the threshold or widen the filters.")
    else:
        st.write(f"High-value = balance of **€{hv_threshold:,.0f}** or more (change in sidebar).")

        # Revenue risk: balance lost, plus an editable assumption for revenue
        revenue_pct = st.number_input("Assumed annual revenue earned on balances (%)",
                                      min_value=0.0, max_value=10.0, value=2.0, step=0.5,
                                      help="Assumption only. Replace with your bank's real margin.")
        balance_lost = hv_churned["Balance"].sum()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("High-value customers", f"{len(hv):,}")
        m2.metric("High-value churned", f"{len(hv_churned):,}")
        m3.metric("Balance lost to churn", f"€{balance_lost:,.0f}")
        m4.metric("Est. annual revenue at risk", f"€{balance_lost * revenue_pct / 100:,.0f}")

        # Salary vs balance scatter, coloured by churn status
        fig = px.scatter(hv, x="EstimatedSalary", y="Balance", color="Customer Status",
                         hover_data=["CustomerId", "Age", "Geography"], opacity=0.6,
                         title="Salary vs balance (high-value customers)",
                         color_discrete_map={"Churned": "#d62728", "Retained": "#1f77b4"})
        st.plotly_chart(fig, width="stretch")

        # Compare salary and balance patterns
        st.subheader("Salary vs balance: churned vs retained (averages)")
        st.dataframe(hv.groupby("Customer Status")[["EstimatedSalary", "Balance"]].mean().round(0))

        # Drill-down: list of churned high-value customers
        if st.checkbox("Show churned high-value customers (drill-down)"):
            drill = hv_churned[["CustomerId", "Geography", "Gender", "Age", "CreditScore",
                                "Balance", "EstimatedSalary"]].sort_values("Balance", ascending=False)
            st.dataframe(drill, hide_index=True, width="stretch")
            st.download_button("Download this list (CSV)", drill.to_csv(index=False),
                               file_name="high_value_churners.csv")

# ===== TAB 6: RISK RANKING & STATS =====
with tab6:
    st.subheader("🏆 Risk-segment ranking (combined dimensions)")
    st.caption("Combines 2-3 segment dimensions (e.g. Geography + Age Segment + Activity Status) "
               "and ranks the combinations. Groups under 100 customers are excluded as too small to target on their own.")
    r1, r2 = st.columns(2)
    with r1:
        st.markdown("**Top 5 by churn rate**")
        st.dataframe(by_rate, hide_index=True, width="stretch")
    with r2:
        st.markdown("**Top 5 by customers affected (churned count)**")
        st.dataframe(by_impact, hide_index=True, width="stretch")

    st.markdown("---")
    st.subheader("📐 Statistical significance (optional)")
    st.caption("Chi-square test: is this segment's churn gap a real pattern, or could it be random "
               "noise? This is the standard way to back a claim with a number instead of a gut feel — "
               "worth having even as a beginner, since 'how do you know the difference is real' is a "
               "common follow-up question in analyst interviews.")
    run_stats = st.checkbox("Run chi-square tests on segment dimensions", value=False)
    if run_stats:
        stat_rows = []
        # NumOfProducts is included too: it is the strongest single churn driver in this dataset
        for col in SEGMENT_DIMENSIONS + ["NumOfProducts"]:
            result = chi_square_test(filtered, col)
            stat_rows.append({
                "Dimension": col,
                "p-value": "< 0.0001" if result["p_value"] < 0.0001 else f"{result['p_value']:.4f}",
                "Significant (p<0.05)": "Yes" if result["significant"] else "No",
                "Effect size (Cramér's V)": round(result["cramers_v"], 3),
            })
        st.dataframe(pd.DataFrame(stat_rows), hide_index=True, width="stretch")
        st.caption("p < 0.05 means this segment's churn difference is very unlikely to be random. "
                   "Cramér's V shows how strong the association is: under ~0.1 is weak, 0.1-0.3 "
                   "moderate, above 0.3 strong. A result can be statistically significant and still "
                   "be a weak practical driver — check both numbers, not just the p-value.")

# ===== TAB 7: RECOMMENDATIONS =====
with tab7:
    st.subheader("🎯 Retention recommendations")
    st.caption("Auto-generated from the current filters: for each dimension, the highest-churn group "
               "(with enough customers to trust the rate) gets a suggested action.")

    recs = generate_recommendations(filtered, overall_rate)
    if not recs:
        st.info("No segment is meaningfully above the overall churn rate with the current filters.")
    else:
        for r in recs:
            with st.container(border=True):
                left, right = st.columns([1, 2])
                with left:
                    st.metric(f"{r['Dimension']}: {r['Segment']}", f"{r['Churn Rate (%)']}%",
                              f"+{r['Gap vs Average (pts)']} pts vs average", delta_color="inverse")
                    st.caption(f"{r['Customers Affected']:,} customers, {r['Churned']:,} churned")
                with right:
                    st.markdown(f"**Recommended action:** {r['Recommended Action']}")

    st.markdown("---")
    st.subheader("🔗 Priority: top combined risk segment")
    if not by_rate.empty:   # reuses the ranking computed once above
        top = by_rate.iloc[0]
        st.warning(
            f"**{top['Segment']}** — {top['Churn Rate (%)']}% churn across "
            f"{int(top['Customers']):,} customers ({int(top['Churned']):,} churned). "
            "This combination stacks multiple risk factors — prioritize a cross-functional "
            "retention effort here before running single-dimension campaigns."
        )
    else:
        st.info("Not enough customers in any combined segment (with current filters) to rank reliably.")
