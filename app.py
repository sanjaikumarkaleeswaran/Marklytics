import streamlit as st
import pandas as pd
import numpy as np
import io
import os
import plotly.express as px
import plotly.graph_objects as go
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# ----------------------------
# Next-Gen Multi-Exam Student Dashboard
# ----------------------------
st.set_page_config(page_title="Next-Gen Student Analysis", layout="wide")
st.title("🚀 Multi-Exam Student Dashboard")
st.write("Upload multiple CSV/Excel files for different exams. The app will generate dashboards and batch PDF reports.")

# ----------------------------
# Sidebar
# ----------------------------
pass_mark = st.sidebar.number_input("Pass Mark", min_value=0, max_value=100, value=40)
top_n_students = st.sidebar.slider("Top N Students", 1, 50, 5)

# ----------------------------
# File Upload
# ----------------------------
uploaded_files = st.file_uploader("Upload Multiple Exam Files", type=["csv", "xls", "xlsx"], accept_multiple_files=True)

# ----------------------------
# Helper Functions
# ----------------------------
@st.cache_data
def convert_to_excel(df):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Results")
    buffer.seek(0)
    return buffer

def assign_grade(percent):
    if percent >= 90: return 'A+'
    elif percent >= 80: return 'A'
    elif percent >= 70: return 'B+'
    elif percent >= 60: return 'B'
    elif percent >= 50: return 'C'
    else: return 'F'

def generate_pdf(student_name, student_marks, total, avg, grade, exam_name, filepath):
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter
    c.setFont("Helvetica-Bold", 16)
    c.drawString(150, height-50, f"Report Card - {student_name}")
    c.setFont("Helvetica", 12)
    c.drawString(50, height-100, f"Exam: {exam_name}")
    c.drawString(50, height-120, f"Total Marks: {total}")
    c.drawString(50, height-140, f"Average: {avg:.2f}")
    c.drawString(50, height-160, f"Grade: {grade}")
    c.drawString(50, height-190, "Marks:")
    y = height-210
    for subj, mark in student_marks.items():
        c.drawString(60, y, f"{subj}: {mark}")
        y -= 20
    c.showPage()
    c.save()

# ----------------------------
# Main Logic
# ----------------------------
if uploaded_files:
    exam_data = {}
    for file in uploaded_files:
        if file.name.endswith(".csv"):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        exam_name = file.name.split('.')[0]
        exam_data[exam_name] = df

    # Select Exam
    selected_exam = st.selectbox("Select Exam to Analyze", list(exam_data.keys()))
    df = exam_data[selected_exam]

    # Numeric Columns
    marks_df = df.select_dtypes(include=[np.number])
    if marks_df.empty:
        st.error("❌ No numeric columns detected in this exam.")
        st.stop()

    students = df.index.tolist() if df.index.is_unique else list(range(len(df)))
    subjects = marks_df.columns.tolist()

    # Calculations
    total_marks = marks_df.sum(axis=1)
    avg_marks = marks_df.mean(axis=1)
    percentiles = marks_df.rank(pct=True, axis=0).mean(axis=1)*100
    grades = percentiles.apply(assign_grade)
    pass_fail = marks_df.applymap(lambda x: "✅" if x >= pass_mark else "❌")
    avg_by_subject = marks_df.mean(axis=0)

    # ----------------------------
    # Tabs
    # ----------------------------
    tabs = st.tabs(["Class Overview", "Student Report", "Batch PDF Reports", "Download Excel"])

    # ---------- Class Overview ----------
    with tabs[0]:
        st.header("📊 Class Overview")

        # Average per subject
        fig_avg = px.bar(
            x=subjects, y=avg_by_subject.values,
            labels={"x":"Subjects", "y":"Average Marks"},
            title="Average Marks per Subject", text=avg_by_subject.values
        )
        st.plotly_chart(fig_avg, use_container_width=True)

        # Heatmap
        fig_heat = px.imshow(
            marks_df, text_auto=True, aspect="auto",
            color_continuous_scale="Blues", title="Heatmap of Student Marks"
        )
        st.plotly_chart(fig_heat, use_container_width=True)

        # Pass/Fail per subject
        fig_pf = go.Figure()
        fig_pf.add_trace(go.Bar(name="Pass", x=subjects, y=(marks_df >= pass_mark).sum().values, marker_color="green"))
        fig_pf.add_trace(go.Bar(name="Fail", x=subjects, y=(marks_df < pass_mark).sum().values, marker_color="red"))
        fig_pf.update_layout(barmode="stack", title="Pass/Fail per Subject")
        st.plotly_chart(fig_pf, use_container_width=True)

        st.subheader("Top Subjects")
        st.table(avg_by_subject.sort_values(ascending=False).head(5).round(2))
        st.subheader("Difficult Subjects")
        st.table(avg_by_subject.sort_values(ascending=True).head(5).round(2))

    # ---------- Student Report ----------
    with tabs[1]:
        st.header("📝 Student Report Card")
        selected_student = st.selectbox("Select Student", students)
        if selected_student is not None:
            student_marks = marks_df.loc[selected_student] if selected_student in marks_df.index else marks_df.iloc[selected_student]
            total = total_marks[selected_student]
            avg = avg_marks[selected_student]
            grade = grades[selected_student]

            # Radar Chart
            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(
                r=student_marks.values,
                theta=subjects,
                fill='toself',
                name=str(selected_student)
            ))
            fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0,100])), showlegend=True, title=f"{selected_student} Performance Radar")
            st.plotly_chart(fig_radar, use_container_width=True)

            st.table(pd.DataFrame({
                "Marks": student_marks,
                "Pass/Fail": pass_fail.loc[selected_student] if selected_student in pass_fail.index else pass_fail.iloc[selected_student]
            }))
            st.info(f"Total: {total} | Average: {avg:.2f} | Grade: {grade}")

    # ---------- Batch PDF Reports ----------
    with tabs[2]:
        st.header("📄 Generate PDF Report Cards for All Students")
        pdf_folder = "pdf_reports"
        os.makedirs(pdf_folder, exist_ok=True)
        for student in students:
            student_marks = marks_df.loc[student] if student in marks_df.index else marks_df.iloc[student]
            total = total_marks[student]
            avg = avg_marks[student]
            grade = grades[student]
            filepath = os.path.join(pdf_folder, f"{student}_{selected_exam}.pdf")
            generate_pdf(str(student), student_marks.to_dict(), total, avg, grade, selected_exam, filepath)
        st.success(f"✅ PDF reports generated for all students in folder: {pdf_folder}")

    # ---------- Download Excel ----------
    with tabs[3]:
        st.header("💾 Download Class Excel Rankings")
        excel_df = pd.DataFrame({
            "Student": students,
            "Total": total_marks,
            "Average": avg_marks.round(2),
            "Grade": grades
        })
        st.download_button(
            "Download Excel",
            data=convert_to_excel(excel_df),
            file_name=f"{selected_exam}_rankings.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
    st.info("👆 Upload at least one CSV/Excel file to start analysis.")
