import streamlit as st
import pandas as pd
import sqlite3
from io import BytesIO
from datetime import datetime
import plotly.express as px

# مكتبات توليد الـ PDF والملصقات
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import mm
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

# --- 1. الإعدادات الأساسية ---
st.set_page_config(page_title="Steel Quality QC Pro", layout="wide", page_icon="🏗️")

# --- 2. محرك قاعدة البيانات ---
def init_db():
    with sqlite3.connect('factory_qc.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS production_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT, date_only TEXT, time_only TEXT,
                        shift TEXT, operator TEXT, inspector TEXT,
                        ccm TEXT, heat TEXT, grade TEXT, strand TEXT,
                        rh REAL, status TEXT, d1 REAL, d2 REAL,
                        billet_count INTEGER, storage_loc TEXT,
                        short_billet_length REAL, sample_info TEXT
                    )''')
        conn.commit()

def save_data(results, shift, operator, inspector, ccm, heat, grade, b_count, storage, short_l):
    with sqlite3.connect('factory_qc.db') as conn:
        c = conn.cursor()
        now = datetime.now()
        for r in results:
            if r['d1'] > 0:
                c.execute('''INSERT INTO production_logs 
                    (timestamp, date_only, time_only, shift, operator, inspector, ccm, heat, grade, 
                    strand, rh, status, d1, d2, billet_count, storage_loc, short_billet_length, sample_info)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (now.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"),
                     shift, operator, inspector, ccm, heat, grade, r['strand'], r['rh'], r['status'], 
                     r['d1'], r['d2'], b_count, storage, short_l, r['sample']))
        conn.commit()

# --- 3. وظيفة توليد ملصق PDF ---
def generate_label_pdf(heat_no, grade, ccm, date_str, storage, b_count, s_len):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(100*mm, 100*mm))
    c.rect(2*mm, 2*mm, 96*mm, 96*mm)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(50*mm, 90*mm, "PRODUCTION & QC LABEL")
    
    c.setFont("Helvetica", 11)
    y = 75*mm
    lines = [f"Heat No: {heat_no}", f"Grade: {grade}", f"Storage: {storage}", 
             f"Billet Count: {b_count}", f"CCM: {ccm}", f"Date: {date_str}"]
    if s_len > 0: lines.append(f"Short Billet: {s_len} m")
    
    for line in lines:
        c.drawString(10*mm, y, line)
        y -= 7*mm
        
    qr_code = qr.QrCodeWidget(f"HEAT:{heat_no}|LOC:{storage}|GRADE:{grade}")
    bounds = qr_code.getBounds()
    width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
    d = Drawing(30*mm, 30*mm, transform=[30*mm/width, 0, 0, 30*mm/height, 0, 0])
    d.add(qr_code)
    renderPDF.draw(d, c, 35*mm, 5*mm)
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

init_db()

# --- 4. واجهة المستخدم ---
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 نظام الرقابة على الجودة")
    pwd = st.text_input("كلمة مرور النظام:", type="password")
    if st.button("دخول"):
        if pwd == "1100":
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("❌ كلمة المرور خاطئة")
else:
    st.markdown(f"""<div style="background-color:#003366;padding:10px;border-radius:10px">
    <h1 style="color:white;text-align:center;margin:0;">CCM Quality Control Pro</h1>
    <p style="color:white;text-align:center;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p></div>""", unsafe_allow_html=True)

    t1, t2, t3 = st.tabs(["📝 تسجيل صبة", "📊 التحليل", "📂 الأرشيف والبحث"])

    with t1:
        with st.form("qc_form", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                shift = st.selectbox("الوردية", ["أ (A)", "ب (B)", "ج (C)", "د (D)"])
                ccm = st.selectbox("الماكينة", ["CCM01", "CCM02"])
                heat = st.text_input("رقم الصبة")
            with c2:
                operator = st.text_input("عامل الصب")
                inspector = st.text_input("المفتش")
                grade = st.selectbox("الرتبة", ["B500", "B500W", "SAE1006", "SAE1008", "SAE1010"])
            with c3:
                area = st.selectbox("منطقة التخزين", ["RM01", "RM02", "RM03", "SMS"])
                boxes = [f"Box {i}" for i in range(1, 9 if area=="SMS" else 5)]
                box = st.selectbox("رقم الصندوق", boxes)
                storage_loc = f"{area} ({box})"
            with c4:
                billet_count = st.number_input("عدد البيلت", min_value=1, value=40)
                rh_limit = st.number_input("حد المعينية (mm)", value=8.0)
                short_len = st.number_input("طول Short Billet", value=0.0)

            st.markdown("---")
            input_cols = st.columns(5)
            strand_results = []
            for i in range(1, 6):
                with input_cols[i-1]:
                    st.subheader(f"Strand {i}")
                    d1 = st.number_input(f"D1-S{i}", 0.0)
                    d2 = st.number_input(f"D2-S{i}", 0.0)
                    has_sample = st.checkbox(f"عينة S{i}")
                    s_info = st.text_input(f"ترتيبها", key=f"s_val_{i}") if has_sample else ""
                    
                    calc_rh = round(abs(d1 - d2), 2)
                    status = "PASS" if calc_rh <= rh_limit else "REJECT"
                    strand_results.append({
                        'strand': f"S0{i}", 
                        'd1': d1, 
                        'd2': d2, 
                        'rh': calc_rh, 
                        'status': status, 
                        'sample': f"S{i}-#{s_info}" if has_sample else "None"
                    })
                    if d1 > 0:
                        st.markdown(f"**Rh: {calc_rh}** ({status})")

            submitted = st.form_submit_button("💾 حفظ الصبة وتوليد الملصق", use_container_width=True)

        # خارج الـ form
        if submitted:
            if not heat or not operator:
                st.error("⚠️ بيانات ناقصة! (رقم الصبة أو اسم العامل مطلوب)")
            else:
                save_data(strand_results, shift, operator, inspector, ccm, heat, grade, billet_count, storage_loc, short_len)
                st.success(f"✅ تم حفظ الصبة {heat} بنجاح")
                
                pdf_buffer = generate_label_pdf(
                    heat, grade, ccm, datetime.now().strftime('%Y-%m-%d'),
                    storage_loc, billet_count, short_len
                )
                st.session_state['new_label_pdf'] = pdf_buffer
                st.session_state['new_heat'] = heat

        if 'new_label_pdf' in st.session_state:
            st.download_button(
                label=f"🖨️ تحميل ملصق الصبة الجديدة ({st.session_state['new_heat']})",
                data=st.session_state['new_label_pdf'],
                file_name=f"Label_{st.session_state['new_heat']}.pdf",
                mime="application/pdf",
                key="download_new_label"
            )

    with t2:
        with sqlite3.connect('factory_qc.db') as conn:
            df = pd.read_sql_query("SELECT * FROM production_logs", conn)
        if not df.empty:
            st.plotly_chart(px.scatter(df, x="time_only", y="rh", color="status", title="توزيع المعينية الزمني"), use_container_width=True)
            st.plotly_chart(px.bar(df.groupby('operator')['rh'].mean().reset_index(), x='operator', y='rh', title="أداء العمال"), use_container_width=True)

    with t3:
        with sqlite3.connect('factory_qc.db') as conn:
            history = pd.read_sql_query("SELECT * FROM production_logs ORDER BY id DESC", conn)
        
        if not history.empty:
            search = st.text_input("🔎 ابحث برقم الصبة أو مكان التخزين:")
            filtered = history[
                history['heat'].astype(str).str.contains(search, case=False) |
                history['storage_loc'].str.contains(search, case=False)
            ]
            st.dataframe(filtered, use_container_width=True)
            
            if not filtered.empty:
                st.markdown("---")
                sel_heat = st.selectbox("إعادة طباعة صبة:", options=filtered['heat'].unique(), key="reprint_select")
                
                if sel_heat:
                    h_data = history[history['heat'] == sel_heat].iloc[0]
                    
                    if st.button(f"📄 توليد ملصق للصبة {sel_heat}", key=f"gen_{sel_heat}"):
                        reprint_pdf = generate_label_pdf(
                            h_data['heat'], h_data['grade'], h_data['ccm'],
                            h_data['date_only'], h_data['storage_loc'],
                            h_data['billet_count'], h_data['short_billet_length']
                        )
                        st.session_state['reprint_pdf'] = reprint_pdf
                        st.session_state['reprint_heat'] = sel_heat
                        st.success(f"تم توليد ملصق {sel_heat}")

                if 'reprint_pdf' in st.session_state:
                    st.download_button(
                        label=f"⬇️ تحميل ملصق {st.session_state['reprint_heat']}",
                        data=st.session_state['reprint_pdf'],
                        file_name=f"Label_{st.session_state['reprint_heat']}.pdf",
                        mime="application/pdf",
                        key="download_reprint_label"
                    )