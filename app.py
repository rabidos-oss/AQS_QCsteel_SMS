import streamlit as st
import pandas as pd
import sqlite3
from io import BytesIO
from datetime import datetime
import plotly.express as px

# --- 1. إعداد قاعدة البيانات المحلية ---
def init_db():
    conn = sqlite3.connect('local_qc_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (timestamp TEXT, heat TEXT, grade TEXT, ccm TEXT, shift TEXT, 
                  operator TEXT, storage TEXT, billet_count REAL, rh REAL, status TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- 2. واجهة المستخدم ---
st.set_page_config(page_title="Steel Quality Local", layout="wide")

if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 الدخول للنظام")
    if st.text_input("كلمة المرور:", type="password") == "1100":
        if st.button("دخول"):
            st.session_state.auth = True
            st.rerun()
else:
    st.title("🏗️ نظام إدارة الجودة - نسخة البيانات المحلية")
    t1, t2 = st.tabs(["📝 إدخال بيانات", "📊 الأرشيف والتصدير"])

    with t1:
        with st.form("input_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                heat = st.text_input("رقم الصبة")
                grade = st.selectbox("الرتبة", ["B500", "B500W", "SAE1006", "SAE1008"])
            with c2:
                shift = st.selectbox("الوردية", ["A", "B", "C", "D"])
                ccm = st.selectbox("الماكينة", ["CCM01", "CCM02"])
            with c3:
                billet_count = st.number_input("العدد", value=40)
                storage = st.text_input("مكان التخزين", "SMS-Box")

            st.divider()
            # إدخال مبسط للمقاسات
            d1 = st.number_input("D1 (mm)", value=0.0)
            d2 = st.number_input("D2 (mm)", value=0.0)
            
            if st.form_submit_button("حفظ البيانات"):
                rh = round(abs(d1-d2), 2)
                status = "PASS" if rh <= 8.0 else "REJECT"
                
                conn = sqlite3.connect('local_qc_data.db')
                c = conn.cursor()
                c.execute("INSERT INTO logs VALUES (?,?,?,?,?,?,?,?,?,?)",
                          (datetime.now().strftime("%Y-%m-%d %H:%M"), heat, grade, ccm, shift, "Operator", storage, billet_count, rh, status))
                conn.commit()
                conn.close()
                st.success(f"تم الحفظ بنجاح! الحالة: {status}")

    with t2:
        conn = sqlite3.connect('local_qc_data.db')
        df = pd.read_sql_query("SELECT * FROM logs ORDER BY timestamp DESC", conn)
        conn.close()

        if not df.empty:
            st.dataframe(df, use_container_width=True)
            
            # --- تصدير Excel ---
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='QC_Report')
            
            st.download_button(
                label="📥 تحميل السجل بصيغة Excel",
                data=output.getvalue(),
                file_name=f"QC_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            # رسم بياني بسيط
            st.plotly_chart(px.bar(df, x="heat", y="rh", color="status", title="تحليل المعينية للصبات"))
        else:
            st.info("لا توجد بيانات مسجلة بعد.")
