import streamlit as st
import pandas as pd
from datetime import date, timedelta

from db import init_db, load_transactions_df, insert_transaction, save_setting, load_setting
init_db()

st.set_page_config(page_title="Madbudget – løn til løn", layout="wide")
st.title("Madbudget – fra løn til løn")

def week_bins(pay_start: date, pay_end: date):
    rows, w, cur = [], 1, pay_start
    while cur <= pay_end:
        w_start = cur
        w_end = min(cur + timedelta(days=6), pay_end)
        rows.append(dict(week=w, start=w_start, end=w_end, n_days=(w_end - w_start).days + 1))
        cur = w_end + timedelta(days=1); w += 1
    return pd.DataFrame(rows)

# ---- Inputs (remember last values) ----
def end_of_period(d):
    nm = (d.replace(day=28) + timedelta(days=4)).replace(day=1)  # first of next month
    return nm - timedelta(days=1)

default_start = pd.to_datetime(load_setting("pay_start", f"{date.today().replace(day=1)}")).date()
default_end   = pd.to_datetime(load_setting("pay_end",   f"{end_of_period(date.today().replace(day=1))}")).date()
default_week  = int(load_setting("weekly_budget", 2500))

c0, c1, c2, c3 = st.columns([1.2,1.2,1,1])
with c0:
    pay_start = st.date_input("Lønperiode start", value=default_start)
with c1:
    pay_end = st.date_input("Næste løn (inkl.)", value=default_end)
with c2:
    weekly_budget = st.number_input("Ugebudget (kr)", min_value=0, value=default_week, step=50)
with c3:
    prorate = st.checkbox("Proportionér korte uger", value=True)

# persist settings
save_setting("pay_start", str(pay_start))
save_setting("pay_end",   str(pay_end))
save_setting("weekly_budget", int(weekly_budget))

weeks_df = week_bins(pay_start, pay_end)
weeks_df["week_budget"] = (weeks_df["n_days"]/7.0*weekly_budget if prorate else weekly_budget)

# ---- Add transaction form ----
st.subheader("Tilføj transaktion")
ta, tb, tc, td, te = st.columns([1.1,1.6,1.2,1.2,1.0])
with ta:  t_date = st.date_input("Dato", value=date.today(), key="tdate")
with tb:  t_text = st.text_input("Tekst", placeholder="Rema 1000 …", key="ttext")
with tc:  t_cat  = st.selectbox("Kategori", ["Dagligvarer","Takeaway","Restaurant","Husholdning","Andet"], key="tcat")
with td:  t_type = st.radio("Type", ["Forbrug","Indsætning"], horizontal=True, key="ttype")
with te:  t_amt  = st.number_input("Beløb", min_value=0.0, value=0.0, step=10.0, key="tamount")

if st.button("Tilføj"):
    if t_amt > 0 and t_text.strip():
        insert_transaction(
            str(pd.to_datetime(t_date).date()),
            t_text.strip(),
            t_cat,
            ("spend" if t_type == "Forbrug" else "topup"),
            float(t_amt)
        )
        st.success("Tilføjet.")
    else:
        st.warning("Angiv mindst beløb > 0 og en tekst.")

# ---- Load data & compute ----
tx = load_transactions_df()

# Keep only current period
if not tx.empty:
    tx_period = tx[(tx["date"] >= pay_start) & (tx["date"] <= pay_end)].copy()
else:
    tx_period = pd.DataFrame(columns=["id","date","text","category","type","amount"])

def date_to_week(d):
    row = weeks_df[(weeks_df["start"]<=d) & (d<=weeks_df["end"])]
    return int(row.iloc[0]["week"]) if not row.empty else None

if not tx_period.empty:
    tx_period["week"] = tx_period["date"].apply(date_to_week)

alloc = weeks_df.set_index("week")["week_budget"]
spend_by_week = (tx_period[tx_period["type"]=="spend"].groupby("week")["amount"].sum()
                 .reindex(alloc.index, fill_value=0.0))
topup_by_week = (tx_period[tx_period["type"]=="topup"].groupby("week")["amount"].sum()
                 .reindex(alloc.index, fill_value=0.0))
remaining = alloc + topup_by_week - spend_by_week

# ---- Output ----
st.markdown("---")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Tilbage i perioden", f"{remaining.sum():,.0f} kr".replace(",", "."))
k2.metric("Forbrug i perioden", f"{spend_by_week.sum():,.0f} kr".replace(",", "."))
k3.metric("Indsætninger i perioden", f"{topup_by_week.sum():,.0f} kr".replace(",", "."))
today = date.today()
days_left = (pay_end - max(today, pay_start)).days + 1 if today <= pay_end else 0
per_day_left = remaining.sum()/days_left if days_left>0 else 0
k4.metric("Forventet pr. dag (resten)", f"{per_day_left:,.0f} kr".replace(",", "."))

tab1, tab2 = st.tabs(["Uger", "Transaktioner"])
with tab1:
    out = weeks_df[["week","start","end","n_days"]].copy()
    out["Budget"]   = alloc.values
    out["Top-ups"]  = topup_by_week.values
    out["Forbrug"]  = spend_by_week.values
    out["Tilbage"]  = remaining.values
    out = out.rename(columns={"week":"Uge","start":"Start","end":"Slut","n_days":"Dage"})
    st.dataframe(out, use_container_width=True)

with tab2:
    st.dataframe(tx_period.sort_values("date", ascending=False), use_container_width=True)

st.caption("Bemærk: Beregningerne er vejledende. Sidste uge kan være kortere end 7 dage; brug proportionering for retfærdig fordeling.")

