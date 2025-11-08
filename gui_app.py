import tkinter as tk
from tkinter import filedialog, messagebox
from extract_text import extract_from_pdf, extract_from_docx
from analyzer import analyze_resume, load_job_description, save_to_csv

def upload_resume():
    file_path = filedialog.askopenfilename(filetypes=[("Documents", "*.pdf *.docx")])
    if not file_path:
        return None
    resume_label.config(text=f"Resume: {file_path}")
    return file_path

def upload_jd():
    file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
    if not file_path:
        return None
    jd_label.config(text=f"JD: {file_path}")
    return file_path

def run_analysis():
    resume_file = resume_label.cget("text").replace("Resume: ", "")
    jd_file = jd_label.cget("text").replace("JD: ", "")

    if not resume_file or "Resume:" in resume_file:
        messagebox.showerror("Error", "Please upload a Resume")
        return
    if not jd_file or "JD:" in jd_file:
        messagebox.showerror("Error", "Please upload a Job Description")
        return

    # Extract resume text
    if resume_file.endswith(".pdf"):
        resume_text = extract_from_pdf(resume_file)
    else:
        resume_text = extract_from_docx(resume_file)

    # Load JD
    jd_text = load_job_description(jd_file)

    # Analyze
    results = analyze_resume(resume_text, jd_text)
    save_to_csv(results)

    # Show results
    output.delete("1.0", tk.END)
    output.insert(tk.END, "📊 Resume Analysis Report\n\n")
    for category, data in results.items():
        output.insert(tk.END, f"🔹 {category.capitalize()} Skills:\n")
        output.insert(tk.END, f"Match %: {data['match_percent']}\n")
        output.insert(tk.END, f"Matched: {', '.join(data['matched']) if data['matched'] else 'None'}\n")
        output.insert(tk.END, f"Missing: {', '.join(data['missing']) if data['missing'] else 'None'}\n\n")

    messagebox.showinfo("Success", "✅ Analysis Complete! Report saved as analysis_report.csv")

# GUI Layout
root = tk.Tk()
root.title("Resume Analyzer")
root.geometry("600x500")

resume_btn = tk.Button(root, text="Upload Resume", command=upload_resume)
resume_btn.pack(pady=5)
resume_label = tk.Label(root, text="Resume: Not Selected")
resume_label.pack(pady=5)

jd_btn = tk.Button(root, text="Upload Job Description", command=upload_jd)
jd_btn.pack(pady=5)
jd_label = tk.Label(root, text="JD: Not Selected")
jd_label.pack(pady=5)

analyze_btn = tk.Button(root, text="Run Analysis", command=run_analysis, bg="green", fg="white")
analyze_btn.pack(pady=10)

output = tk.Text(root, height=15, width=70)
output.pack(pady=10)

root.mainloop()
