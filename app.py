import json
from io import BytesIO
import pdfkit
from flask import render_template, request, send_file

import os
os.environ["FLASK_RUN_FROM_CLI"] = "false"
os.environ["WATCHDOG_IGNORE_DIRECTORIES"] = "venv"

from dotenv import load_dotenv
import google.generativeai as genai
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import importlib

# ----------------------------
# Load environment variables
# ----------------------------
load_dotenv()

# ✅ Initialize Gemini API
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("models/gemini-2.5-flash-preview-09-2025")
    print("✅ Gemini client initialized successfully.")
else:
    print("⚠️  GEMINI_API_KEY not found. AI features will be disabled, but resume builder will work.")
    model = None

# ----------------------------
# Import helpers
# ----------------------------
from analyzer import analyze_resume, load_job_description, save_to_csv
from extract_text import extract_from_pdf, extract_from_docx
import pdf_report
print("📄 Using pdf_report from:", pdf_report.__file__)
importlib.reload(pdf_report)
from pdf_report import generate_pdf_report
print("📄 Using latest pdf_report from:", pdf_report.__file__)

# ----------------------------
# Flask Config
# ----------------------------
app = Flask(__name__)
app.secret_key = 'your_super_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ----------------------------
# Database Models
# ----------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    reports = db.relationship('AnalysisReport', backref='user', lazy=True)


class AnalysisReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    job_title = db.Column(db.String(200), nullable=True)
    technical_match = db.Column(db.Float, nullable=False)
    technical_matched_skills = db.Column(db.Text, nullable=True)
    technical_missing_skills = db.Column(db.Text, nullable=True)
    soft_match = db.Column(db.Float, nullable=False)
    soft_matched_skills = db.Column(db.Text, nullable=True)
    soft_missing_skills = db.Column(db.Text, nullable=True)


# ----------------------------
# Routes
# ----------------------------
@app.route('/')
def home():
    if 'username' in session:
        return render_template('index.html', logged_in=True, username=session['username'])
    return render_template('index.html', logged_in=False)


def validate_password_strength(password):
    """Validate password strength and return (is_valid, suggestions)"""
    suggestions = []
    
    if len(password) < 8:
        suggestions.append("Password must be at least 8 characters long")
    
    if not any(c.islower() for c in password):
        suggestions.append("Add lowercase letters")
    
    if not any(c.isupper() for c in password):
        suggestions.append("Add uppercase letters")
    
    if not any(c.isdigit() for c in password):
        suggestions.append("Add numbers")
    
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        suggestions.append("Add special characters (!@#$%^&*)")
    
    # Password is considered strong if it has at least 3 of the 5 requirements
    is_valid = len(suggestions) <= 2
    
    return is_valid, suggestions

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            flash("Username already exists.", "danger")
            return render_template('signup.html')

        # Validate password strength
        is_valid, suggestions = validate_password_strength(password)
        if not is_valid:
            flash(f"Weak password. Suggestions: {', '.join(suggestions)}", "danger")
            return render_template('signup.html')

        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
        new_user = User(username=username, password_hash=hashed_pw)
        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))
    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['username'] = username
            flash("Login successful!", "success")
            return redirect(url_for('home'))
        else:
            flash("Invalid username or password.", "danger")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))


@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        flash("Login required to view dashboard.", "danger")
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['username']).first()
    reports = AnalysisReport.query.filter_by(user_id=user.id).order_by(AnalysisReport.date_created.desc()).all()
    return render_template('dashboard.html', username=session['username'], reports=reports)


@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/help')
def help_page():
    return render_template('help.html')

# ----------------------------
# Chatbot Route (Gemini)
# ----------------------------
from flask import jsonify
import google.generativeai as genai

# Initialize Gemini (already imported above)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# ----------------------------
# Resume Analysis
# ----------------------------
@app.route('/analyze', methods=['POST'])
def analyze():
    if 'username' not in session:
        flash("You must be logged in to analyze a resume.", "danger")
        return redirect(url_for('login'))

    if 'resume' not in request.files or 'jd' not in request.files:
        flash("Please upload both resume and job description files.", "danger")
        return redirect(url_for('home'))

    resume_file = request.files['resume']
    jd_file = request.files['jd']

    if resume_file.filename == '' or jd_file.filename == '':
        flash("No file selected.", "danger")
        return redirect(url_for('home'))

    resume_path = os.path.join(UPLOAD_FOLDER, resume_file.filename)
    jd_path = os.path.join(UPLOAD_FOLDER, jd_file.filename)
    resume_file.save(resume_path)
    jd_file.save(jd_path)

    try:
        if resume_path.endswith(".pdf"):
            resume_text = extract_from_pdf(resume_path)
        else:
            resume_text = extract_from_docx(resume_path)
        jd_text = load_job_description(jd_path)
        results = analyze_resume(resume_path, jd_text)

        return render_template(
            "result.html",
            filename=resume_file.filename,
            result={
                "technical_match": results["technical"]["match_percent"],
                "technical_matched": results["technical"]["matched"],
                "technical_missing": results["technical"]["missing"],
                "soft_match": results["soft"]["match_percent"],
                "soft_matched": results["soft"]["matched"],
                "soft_missing": results["soft"]["missing"]
            }
        )

    except Exception as e:
        return f"<h3 style='color:red;text-align:center;'>Error: {str(e)}</h3>"

    finally:
        os.remove(resume_path)
        os.remove(jd_path)


# ----------------------------
# ATS Simulation (Gemini)
# ----------------------------
@app.route('/ats-simulation', methods=['POST'])
def ats_simulation():
    """Simulate ATS score using Google Gemini API."""
    import google.generativeai as genai

    if 'username' not in session:
        flash("You must be logged in to run ATS Simulation.", "danger")
        return redirect(url_for('login'))

    if 'resume' not in request.files or 'jd' not in request.files:
        flash("Please upload both resume and job description.", "danger")
        return redirect(url_for('home'))

    resume_file = request.files['resume']
    jd_file = request.files['jd']

    resume_path = os.path.join(UPLOAD_FOLDER, resume_file.filename)
    jd_path = os.path.join(UPLOAD_FOLDER, jd_file.filename)
    resume_file.save(resume_path)
    jd_file.save(jd_path)

    try:
        # ✅ Configure Gemini with your API key
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

        # ✅ Extract text
        if resume_path.endswith(".pdf"):
            resume_text = extract_from_pdf(resume_path)
        else:
            resume_text = extract_from_docx(resume_path)
        jd_text = load_job_description(jd_path)

        # ✅ Use Gemini for ATS scoring
        prompt = f"""
        You are an ATS (Applicant Tracking System) evaluator.
        Compare the following RESUME and JOB DESCRIPTION, and give a score (0-100)
        based on how well the resume matches the job requirements.
        Then briefly explain why in 2-3 lines.

        Resume:
        {resume_text[:3000]}

        Job Description:
        {jd_text[:1500]}

        Output format:
        ATS Score: XX%
        Summary: <short explanation>
        """

        model = genai.GenerativeModel("models/gemini-2.5-flash-preview-09-2025")

        response = model.generate_content(prompt)

        ats_result = response.text if hasattr(response, "text") else str(response)

        return render_template('ats_result.html', ats_result=ats_result)

    except Exception as e:
        flash(f"Error running ATS simulation: {e}", "danger")
        return redirect(url_for('home'))

    finally:
        os.remove(resume_path)
        os.remove(jd_path)

# ----------------------------
# Chatbot Route (Gemini)
# ----------------------------
from flask import jsonify
import google.generativeai as genai

# Initialize Gemini client
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get("message", "").strip()

        if not user_message:
            return jsonify({"reply": "Please type a message."})

        # ✅ Create a concise system-style prompt for Gemini
        prompt = f"""
        You are SkillSync, a concise and professional AI assistant that helps users with resume improvement,
        job suggestions, and interview tips.

        RULES:
        - Keep answers under **3 sentences**.
        - Be direct, professional, and structured.
        - No emojis, no markdown tables, no headings.
        - If asked for examples, give at most **3 short examples**.
        - Avoid unnecessary details or long explanations.

        User: {user_message}
        """

        # Use Gemini model for chatbot
        model = genai.GenerativeModel("models/gemini-2.5-flash-preview-09-2025")
        response = model.generate_content(prompt)

        bot_reply = response.text.strip() if hasattr(response, "text") else str(response)

        # ✅ Optional: Trim very long replies to stay concise
        if len(bot_reply.split()) > 50:
            bot_reply = " ".join(bot_reply.split()[:50]) + "..."

        return jsonify({"reply": bot_reply})

    except Exception as e:
        print("❌ Chatbot error:", e)
        return jsonify({"reply": f"Error: {str(e)}"})
from flask import jsonify
import google.generativeai as genai
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# ----------------------------
# 1️⃣ Auto Resume Generator
# ----------------------------
# @app.route('/generate-resume', methods=['POST'])
# def generate_resume():
#     details = request.form.get("details", "")
#     template = request.form.get("template", "modern")

#     if not details:
#         flash("Please enter your details to generate a resume.", "danger")
#         return redirect(url_for('home'))

#     prompt = f"""
#     Create a professional resume using this information:
#     {details}
#     Format it in {template} style with clean headings: 
#     Name, Contact, Objective, Education, Experience, Skills.
#     Keep it ATS-friendly.
#     """

#     model = genai.GenerativeModel("models/gemini-2.5-flash-preview-09-2025")
#     response = model.generate_content(prompt)
#     resume_text = response.text.strip()

#     # Generate PDF
#     output_path = os.path.join(UPLOAD_FOLDER, f"AI_Resume_{template}.pdf")
#     c = canvas.Canvas(output_path, pagesize=letter)
#     c.setFont("Helvetica", 11)
#     y = 750
#     for line in resume_text.split('\n'):
#         c.drawString(50, y, line[:100])
#         y -= 15
#         if y < 50:
#             c.showPage()
#             y = 750
#     c.save()

#     return send_file(output_path, as_attachment=True)


# ----------------------------
# 2️⃣ AI Summary Writer
# ----------------------------
@app.route('/generate-summary', methods=['POST'])
def generate_summary():
    summary_input = request.form.get("summary_input", "")
    if not summary_input:
        flash("Please enter some key points.", "danger")
        return redirect(url_for('home'))

    prompt = f"""
    Write a professional and concise 'About Me' summary 
    (max 4 sentences) based on these points:
    {summary_input}
    """

    model = genai.GenerativeModel("models/gemini-2.5-flash-preview-09-2025")
    response = model.generate_content(prompt)
    result = response.text.strip()

    return render_template("summary_result.html", summary=result)


# ----------------------------
# Bullet Point Enhancer Route
# ----------------------------
@app.route('/enhance-bullets', methods=['POST'])
def enhance_bullets():
    """Enhances resume bullet points using Gemini AI."""
    try:
        user_text = request.form.get("bullets", "").strip()
        if not user_text:
            flash("Please enter some bullet points.", "danger")
            return redirect(url_for('home'))

        # Gemini API prompt
        prompt = f"""
        You are a professional resume writer.
        Rewrite the following resume bullet points to sound more impactful,
        concise, and results-oriented. 
        Keep each bullet short and action-driven.

        Original Bullets:
        {user_text}

        Format output as a list of improved bullet points.
        """

        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("models/gemini-2.5-flash-preview-09-2025")
        response = model.generate_content(prompt)

        enhanced_text = response.text if hasattr(response, "text") else str(response)

        # Render the result page
        return render_template("enhance_result.html", enhanced_text=enhanced_text)

    except Exception as e:
        flash(f"Error enhancing bullets: {str(e)}", "danger")
        return redirect(url_for('home'))

import pdfkit
from io import BytesIO

import pdfkit
from io import BytesIO

from flask import request, send_file, jsonify
from io import BytesIO
import pdfkit
import json

@app.route('/generate-template-pdf', methods=['POST'])
def generate_template_pdf():
    import json
    from io import BytesIO
    import pdfkit

    # Receive data
    if request.is_json:
        payload = request.get_json()
    else:
        payload = request.form.to_dict(flat=True)

    # Helper to normalize lists
    def normalize(value):
        if not value:
            return []
        if isinstance(value, str):
            try:
                return json.loads(value)
            except:
                # split by newlines or commas
                if '\n' in value:
                    return [v.strip() for v in value.split('\n') if v.strip()]
                if ',' in value:
                    return [v.strip() for v in value.split(',') if v.strip()]
                return [value.strip()]
        return value

    # Normalize all user-entered lists
    skills = normalize(payload.get('skills'))
    experience = normalize(payload.get('experience'))
    education = normalize(payload.get('education'))
    projects = normalize(payload.get('projects'))
    awards = normalize(payload.get('awards'))
    languages = normalize(payload.get('languages'))
    certifications = normalize(payload.get('certifications'))

    html = render_template(
        f"resume_templates/{payload.get('template', 'modern')}.html",
        name=payload.get('name', ''),
        email=payload.get('email', ''),
        phone=payload.get('phone', ''),
        linkedin=payload.get('linkedin', ''),
        summary=payload.get('summary', ''),
        skills=skills,
        experience=experience,
        education=education,
        projects=projects,
        awards=awards,
        languages=languages,
        certifications=certifications
    )

    # Generate PDF with color preservation options
    try:
        config = pdfkit.configuration(
            wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
        )
        # Options to preserve colors and styling
        options = {
            'page-size': 'Letter',
            'margin-top': '0.5in',
            'margin-right': '0.5in',
            'margin-bottom': '0.5in',
            'margin-left': '0.5in',
            'encoding': "UTF-8",
            'no-outline': None,
            'enable-local-file-access': None,
            'print-media-type': None,  # Use print media queries (preserves colors)
            'disable-smart-shrinking': None,
            # Ensure colors are preserved (wkhtmltopdf preserves colors by default)
            # The key is using print-media-type and ensuring CSS colors are properly defined
        }
        pdf = pdfkit.from_string(html, False, configuration=config, options=options)
    except Exception as e:
        print("❌ PDF Generation Error:", e)
        return {"error": str(e)}, 500

    buf = BytesIO(pdf)
    buf.seek(0)
    filename = f"{payload.get('name', 'resume')}.pdf"
    return send_file(buf, as_attachment=True, download_name=filename, mimetype='application/pdf')

@app.route('/api/generate-bullets', methods=['POST'])
def api_generate_bullets():
    if not api_key or not model:
        return jsonify({"error": "AI features require GEMINI_API_KEY. Please add it to your .env file."}), 503
    
    # expects JSON: {"title":"Cashier", "industry":"Retail", "level":"entry"}
    data = request.get_json() or {}
    title = data.get("title","")
    industry = data.get("industry","")
    level = data.get("level","mid")
    # prompt for Gemini (keep short)
    prompt = f"Write 6 concise resume bullet points for a {level} {title} in {industry}. Include measurable outcomes when possible. Keep each bullet under 18 words."
    response = model.generate_content(prompt)
    bullets = response.text.strip() if hasattr(response, "text") else str(response)
    return jsonify({"bullets": bullets.splitlines()})
@app.route('/api/rewrite-bullet', methods=['POST'])
def api_rewrite_bullet():
    if not api_key or not model:
        return jsonify({"error": "AI features require GEMINI_API_KEY. Please add it to your .env file."}), 503
    
    data = request.get_json() or {}
    bullet = data.get("bullet","")
    prompt = f"Rewrite this resume bullet to be more results-oriented and concise (max 18 words):\n\n{bullet}"
    response = model.generate_content(prompt)
    new_bullet = response.text.strip() if hasattr(response, "text") else str(response)
    return jsonify({"bullet": new_bullet})

@app.route('/api/suggest-skills', methods=['POST'])
def api_suggest_skills():
    if not api_key or not model:
        return jsonify({"error": "AI features require GEMINI_API_KEY. Please add it to your .env file."}), 503
    
    data = request.get_json() or {}
    summary = data.get("summary", "")
    experience = data.get("experience", "")
    
    prompt = f"""Based on the following resume information, suggest 8-12 relevant technical and professional skills as a comma-separated list.
    
    Summary: {summary}
    Experience: {experience}
    
    Return only a comma-separated list of skills, no explanations or additional text."""
    
    try:
        response = model.generate_content(prompt)
        skills_text = response.text.strip() if hasattr(response, "text") else str(response)
        # Clean up the response - remove any markdown, bullets, or extra formatting
        skills_text = skills_text.replace('*', '').replace('-', '').replace('•', '').strip()
        skills_list = [s.strip() for s in skills_text.split(',') if s.strip()]
        return jsonify({"skills": skills_list})
    except Exception as e:
        print(f"❌ Error suggesting skills: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/preview', methods=['POST'])
def preview():
    data = request.get_json() or {}
    # normalize lists:
    skills = data.get('skills') or []
    experience = data.get('experience') or []
    education = data.get('education') or []
    projects = data.get('projects') or []
    awards = data.get('awards') or []
    languages = data.get('languages') or []
    certifications = data.get('certifications') or []
    html = render_template(
        f"resume_templates/{data.get('template','modern')}.html",
        name=data.get('name',''),
        email=data.get('email',''),
        phone=data.get('phone',''),
        linkedin=data.get('linkedin',''),
        summary=data.get('summary',''),
        skills=skills,
        experience=experience,
        education=education,
        projects=projects,
        awards=awards,
        languages=languages,
        certifications=certifications
    )
    return html

@app.route('/resume-editor')
def resume_editor():
    return render_template('resume_editor.html')

@app.route('/resume-builder', methods=['POST'])
def resume_builder():
    print("🧩 /resume-builder route HIT ✅")
    """Handles resume builder suggestions and generates a PDF suggestion report."""
    if 'username' not in session:
        flash("You must be logged in to use the Resume Builder.", "danger")
        return redirect(url_for('login'))

    if 'resume' not in request.files or 'jd' not in request.files:
        flash("Please upload both resume and job description.", "danger")
        return redirect(url_for('home'))

    resume_file = request.files['resume']
    jd_file = request.files['jd']

    if resume_file.filename == '' or jd_file.filename == '':
        flash("No file selected.", "danger")
        return redirect(url_for('home'))

    resume_path = os.path.join(UPLOAD_FOLDER, resume_file.filename)
    jd_path = os.path.join(UPLOAD_FOLDER, jd_file.filename)
    resume_file.save(resume_path)
    jd_file.save(jd_path)

    try:
        jd_text = load_job_description(jd_path)
        results = analyze_resume(resume_path, jd_text)
        from analyzer import build_resume_suggestions
        suggestions = build_resume_suggestions(results)

        # ✅ Generate PDF Suggestion Report
        output_path = os.path.join(UPLOAD_FOLDER, f"{resume_file.filename}_suggestions.pdf")

        generate_pdf_report(
            filename=resume_file.filename,
            technical_match=results["technical"]["match_percent"],
            technical_matched=results["technical"]["matched"],
            technical_missing=results["technical"]["missing"],
            output_path=output_path,
            soft_match=results["soft"]["match_percent"],
            soft_matched=results["soft"]["matched"],
            soft_missing=results["soft"]["missing"]
        )

        flash("✅ Suggestion report generated successfully!", "success")
        return send_file(output_path, as_attachment=True)

    except Exception as e:
        flash(f"Error generating suggestion report: {e}", "danger")
        return redirect(url_for('home'))

    finally:
        os.remove(resume_path)
        os.remove(jd_path)

# ----------------------------
# Run App
# ----------------------------

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render assigns a PORT env variable
    app.run(host="0.0.0.0", port=port, debug=False)
