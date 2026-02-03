import streamlit as st
import pandas as pd
import sqlite3
from io import BytesIO
from datetime import datetime
import plotly.express as px

# --- 1. الإعدادات الأساسية ---
st.set_page_config(page_title="Steel Quality QC Pro", layout="wide", page_icon="🏗️")

# --- 2. محرك قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('factory_qc.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS production_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    date_only TEXT,
                    time_only TEXT,
                    shift TEXT,
                    operator TEXT,
                    inspector TEXT,
                    ccm TEXT,
                    heat TEXT,
                    grade TEXT,
                    strand TEXT,
                    rh REAL,
                    status TEXT,
                    d1 REAL,
                    d2 REAL
                )''')
    conn.commit()
    conn.close()

def save_data(results, shift, operator, inspector, ccm, heat, grade):
    conn = sqlite3.connect('factory_qc.db')
    c = conn.cursor()
    now = datetime.now()
    ts = now.strftime("%Y-%m-%d %H:%M:%S")
    dt = now.strftime("%Y-%m-%d")
    tm = now.strftime("%H:%M:%S")
    for r in results:
        if r['d1'] > 0:
            c.execute('''INSERT INTO production_logs 
                (timestamp, date_only, time_only, shift, operator, inspector, ccm, heat, grade, strand, rh, status, d1, d2)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (ts, dt, tm, shift, operator, inspector, ccm, heat, grade, r['strand'], r['rh'], r['status'], r['d1'], r['d2']))
    conn.commit()
    conn.close()

init_db()

# --- 3. واجهة المستخدم ---
if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 نظام الرقابة على الجودة")
    if st.text_input("كلمة مرور النظام:", type="password") == "1100":
        if st.button("دخول"): 
            st.session_state.auth = True
            st.rerun()
else:
    # الهيدر الاحترافي
    st.markdown(f"""
    <div style="background-color:#003366;padding:10px;border-radius:10px">
    <h1 style="color:white;text-align:center;">نظام إدارة جودة المربعات - CCM Quality Control</h1>
    <p style="color:white;text-align:center;">التاريخ: {datetime.now().strftime('%Y-%m-%d')} | الوقت: {datetime.now().strftime('%H:%M:%S')}</p>
    </div>
    """, unsafe_allow_html=True)

    t1, t2, t3 = st.tabs(["📝 تسجيل صبة جديدة", "📊 تحليل الأداء", "📂 الأرشيف"])

    with t1:
        with st.form("qc_form"):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                shift = st.selectbox("الوردية", ["أ (A)", "ب (B)", "ج (C)", "د (D)"])
                ccm = st.selectbox("الماكينة", ["CCM01", "CCM02"])
            with c2:
                operator = st.text_input("اسم عامل الصب")
                inspector = st.text_input("اسم المفتش")
            with c3:
                heat = st.text_input("رقم الصبة", placeholder="مثال: 20261234")
                grade = st.selectbox("رتبة الحديد", ["B500", "B500W", "B500G", "G40", "SAE1006", "SAE1008", "SAE1010", "SAE1010ENTP"])
            with c4:
                rh_limit = st.number_input("حد المعينية (mm)", value=8.0)
                side_size = st.text_input("المقاس (Side)", "130")

            st.markdown("---")
            input_cols = st.columns(5)
            strand_data = []
            for i in range(1, 6):
                with input_cols[i-1]:
                    st.subheader(f"Strand {i}")
                    d1 = st.number_input(f"D1", 0.0, key=f"d1_{i}")
                    d2 = st.number_input(f"D2", 0.0, key=f"d2_{i}")
                    calc_rh = round(abs(d1-d2), 2)
                    res_status = "PASS" if calc_rh <= rh_limit else "REJECT"
                    strand_data.append({'strand': f"S0{i}", 'd1': d1, 'd2': d2, 'rh': calc_rh, 'status': res_status})
                    if d1 > 0:
                        st.info(f"Rh: {calc_rh} - {res_status}")

            submit = st.form_submit_button("💾 حفظ الصبة في السجل الوقتي", use_container_width=True)
            if submit:
                if not operator or not heat:
                    st.error("⚠️ يرجى ملء البيانات الأساسية (رقم الصبة واسم العامل)")
                else:
                    save_data(strand_data, shift, operator, inspector, ccm, heat, grade)
                    st.success("✅ تم الحفظ بنجاح وتوثيق الوقت")
                    st.balloons()

    with t2:
        df = pd.read_sql_query("SELECT * FROM production_logs", sqlite3.connect('factory_qc.db'))
        if not df.empty:
            st.subheader("📊 إحصائيات الجودة الزمنية")
            # رسم بياني للوقت
            fig = px.scatter(df, x="time_only", y="rh", color="shift", size="rh", hover_data=['operator', 'heat'])
            fig.add_hline(y=rh_limit, line_color="red", line_dash="dash")
            st.plotly_chart(fig, use_container_width=True)
            
            # مقارنة العمال
            st.subheader("👷 أداء العمال (متوسط المعينية)")
            worker_perf = df.groupby('operator')['rh'].mean().sort_values().reset_index()
            st.plotly_chart(px.bar(worker_perf, x='operator', y='rh', color='rh'), use_container_width=True)
        else:
            st.warning("لا توجد بيانات للتحليل.")

    with t3:
        st.subheader("📂 السجل التاريخي الكامل")
        history = pd.read_sql_query("SELECT * FROM production_logs ORDER BY id DESC", sqlite3.connect('factory_qc.db'))
        st.dataframe(history, use_container_width=True)
        
        # تصدير إكسل
        towrite = BytesIO()
        history.to_excel(towrite, index=False, engine='xlsxwriter')
        st.download_button("📥 تحميل التقرير الشامل (Excel)", towrite.getvalue(), f"QC_Report_{datetime.now().strftime('%Y%m%d')}.xlsx")

# --- 4. التنبيهات الذكية ---
def check_alerts():
    conn = sqlite3.connect('factory_qc.db')
    df = pd.read_sql_query("SELECT strand, status FROM production_logs ORDER BY id DESC LIMIT 15", conn)
    conn.close()
    for s in [f"S0{i}" for i in range(1,6)]:
        s_data = df[df['strand'] == s]
        if len(s_data) >= 3 and all(s_data['status'].head(3) == 'REJECT'):
            st.sidebar.error(f"⚠️ خطر: الخيط {s} مرفوض لـ 3 مرات متتالية!")

if st.session_state.auth: check_alerts()
