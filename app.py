import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from io import BytesIO
from datetime import datetime
import plotly.express as px

# مكتبات الملصقات
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import mm
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing, renderPDF

# --- 1. الإعدادات والربط ---
st.set_page_config(page_title="Steel Quality Cloud", layout="wide", page_icon="☁️")

# ربط جوجل شيت (يجب وضع رابط الملف في secrets)
conn = st.connection("gsheets", type=GSheetsConnection)

def fetch_data():
    return conn.read(worksheet="production_logs", ttl="0")

def save_to_sheets(new_rows_df):
    existing_data = fetch_data()
    updated_df = pd.concat([existing_data, new_rows_df], ignore_index=True)
    conn.update(worksheet="production_logs", data=updated_df)

# --- 2. وظيفة توليد الملصق (نفس الكود السابق) ---
def generate_label_pdf(heat_no, grade, ccm, date_str, storage, b_count, s_len):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(100*mm, 100*mm))
    c.rect(2*mm, 2*mm, 96*mm, 96*mm)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(50*mm, 90*mm, "PRODUCTION & QC LABEL")
    c.setFont("Helvetica", 10)
    y = 75*mm
    lines = [f"Heat No: {heat_no}", f"Grade: {grade}", f"Storage: {storage}", 
             f"Billet Count: {b_count}", f"CCM: {ccm}", f"Date: {date_str}"]
    if s_len > 0: lines.append(f"Short Billet: {s_len} m")
    for line in lines:
        c.drawString(10*mm, y, line)
        y -= 7*mm
    qr_code = qr.QrCodeWidget(f"HEAT:{heat_no}|LOC:{storage}")
    bounds = qr_code.getBounds()
    width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
    d = Drawing(30*mm, 30*mm, transform=[30*mm/width, 0, 0, 30*mm/height, 0, 0])
    d.add(qr_code)
    renderPDF.draw(d, c, 35*mm, 5*mm)
    c.save()
    buffer.seek(0)
    return buffer

# --- 3. واجهة المستخدم ---
if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 الدخول للنظام السحابي")
    if st.text_input("كلمة المرور:", type="password") == "1100":
        if st.button("دخول"):
            st.session_state.auth = True
            st.rerun()
else:
    st.markdown(f'<div style="background-color:#004d40;padding:10px;border-radius:10px"><h2 style="color:white;text-align:center;">Cloud QC Management</h2></div>', unsafe_allow_html=True)

    t1, t2, t3 = st.tabs(["📝 إدخال جديد", "📊 لوحة التحكم", "🔍 البحث والأرشيف"])

    with t1:
        with st.form("main_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                heat = st.text_input("رقم الصبة")
                grade = st.selectbox("الرتبة", ["B500", "B500W", "SAE1006", "SAE1008"])
                ccm = st.selectbox("الماكينة", ["CCM01", "CCM02"])
            with col2:
                shift = st.selectbox("الوردية", ["A", "B", "C", "D"])
                operator = st.text_input("عامل الصب")
                area = st.selectbox("المنطقة", ["RM01", "RM02", "RM03", "SMS"])
            with col3:
                billet_count = st.number_input("العدد", value=40)
                box = st.selectbox("الصندوق", [f"Box {i}" for i in range(1, 9 if area=="SMS" else 5)])
                short_l = st.number_input("Short Billet (m)", value=0.0)

            st.divider()
            strand_cols = st.columns(5)
            entries = []
            for i in range(1, 6):
                with strand_cols[i-1]:
                    st.write(f"Strand {i}")
                    d1 = st.number_input(f"D1", key=f"d1_{i}", min_value=0.0)
                    d2 = st.number_input(f"D2", key=f"d2_{i}", min_value=0.0)
                    sample = st.checkbox(f"عينة", key=f"s_{i}")
                    s_no = st.text_input("ترتيب", key=f"sn_{i}") if sample else ""
                    rh = round(abs(d1-d2), 2)
                    status = "PASS" if rh <= 8.0 else "REJECT"
                    entries.append({"s": f"S0{i}", "d1": d1, "d2": d2, "rh": rh, "status": status, "sample": f"S{i}-#{s_no}" if sample else "None"})

            if st.form_submit_button("🚀 حفظ في السحاب + طباعة"):
                new_data = []
                now = datetime.now()
                for e in entries:
                    if e['d1'] > 0:
                        new_data.append({
                            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                            "date_only": now.strftime("%Y-%m-%d"),
                            "time_only": now.strftime("%H:%M:%S"),
                            "shift": shift, "operator": operator, "inspector": "Admin",
                            "ccm": ccm, "heat": heat, "grade": grade, "strand": e['s'],
                            "rh": e['rh'], "status": e['status'], "d1": e['d1'], "d2": e['d2'],
                            "billet_count": billet_count, "storage_loc": f"{area} ({box})",
                            "short_billet_length": short_l, "sample_info": e['sample']
                        })
                if new_data:
                    save_to_sheets(pd.DataFrame(new_data))
                    st.success("تم التزامن مع Google Sheets!")
                    label = generate_label_pdf(heat, grade, ccm, now.strftime("%Y-%m-%d"), f"{area} ({box})", billet_count, short_l)
                    st.download_button("🖨️ تحميل الملصق", label, f"{heat}.pdf")

    with t2:
        df = fetch_data()
        if not df.empty:
            st.plotly_chart(px.histogram(df, x="status", color="status", title="حالة الجودة الإجمالية"))
            st.plotly_chart(px.line(df, x="timestamp", y="rh", color="strand", title="تطور المعينية عبر الزمن"))

    with t3:
        df = fetch_data()
        search = st.text_input("🔍 ابحث برقم الصبة أو مكان التخزين:")
        if search:
            results = df[df['heat'].astype(str).str.contains(search) | df['storage_loc'].str.contains(search)]
            st.dataframe(results)
