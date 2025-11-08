import csv
from extract_text import extract_from_pdf, extract_from_docx

# ----------------------------
# Predefined Keyword Lists
# ----------------------------
def extract_keywords(jd_text):
    technical_skills = [
        # Programming Languages
        "java", "python", "c", "c++", "javascript", "typescript",
        # Web Technologies
        "html", "css", "react", "angular", "node.js", "spring boot", "flask",
        # Databases
        "mysql", "mongodb", "postgresql", "sqlite",
        # CS Core Subjects
        "data structures", "algorithms", "dbms", "os", "computer networks",
        # Tools
        "git", "github", "docker", "kubernetes", "jira", "postman", "api testing"
    ]
    soft_skills = [
        "communication", "teamwork", "leadership", "problem solving",
        "time management", "adaptability", "critical thinking",
        "collaboration", "creativity", "attention to detail"
    ]
    return {"technical": technical_skills, "soft": soft_skills}


# ----------------------------
# Load job description text
# ----------------------------
def load_job_description(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().lower()


# ----------------------------
# Analyze resume vs job description
# ----------------------------
def analyze_resume(file_path, jd_text=None):
    resume_text = ""

    if file_path.endswith(".pdf"):
        resume_text = extract_from_pdf(file_path)
    elif file_path.endswith(".docx"):
        resume_text = extract_from_docx(file_path)
    else:
        raise ValueError("Unsupported file format. Use .pdf or .docx")

    resume_text = resume_text.lower()
    if jd_text is None:
        jd_text = resume_text

    keywords = extract_keywords(jd_text)
    results = {}

    for category, words in keywords.items():
        matched = [kw for kw in words if kw in resume_text]
        missing = [kw for kw in words if kw not in resume_text]
        match_percent = (len(matched) / len(words)) * 100 if words else 0

        results[category] = {
            "matched": matched,
            "missing": missing,
            "match_percent": round(match_percent, 2)
        }

    return results


# ----------------------------
# Generate smart resume suggestions
# ----------------------------
def build_resume_suggestions(results):
    suggestions = []

    # --- Technical Skills ---
    if results['technical']['missing']:
        suggestions.append(
            "Consider adding or highlighting these technical skills: " +
            ", ".join(results['technical']['missing'][:8]) + "."
        )

    for skill in results['technical']['missing'][:5]:
        suggestions.append(f"Add a project or internship experience showing your work in {skill}.")

    # --- Soft Skills ---
    if results['soft']['missing']:
        suggestions.append(
            "Improve your resume by emphasizing soft skills such as " +
            ", ".join(results['soft']['missing'][:5]) + "."
        )

    for skill in results['soft']['missing'][:3]:
        suggestions.append(f"Include an example that demonstrates your {skill} skill.")

    # --- If everything matches ---
    if not results['technical']['missing'] and not results['soft']['missing']:
        suggestions.append(
            "Your resume already contains a strong mix of technical and soft skills. "
            "Consider tailoring your experience section for specific job roles."
        )

    return suggestions


# ----------------------------
# Save results to CSV
# ----------------------------
def save_to_csv(results, filename="analysis_report.csv"):
    with open(filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Category", "Match %", "Matched Skills", "Missing Skills"])
        for category, data in results.items():
            writer.writerow([
                category,
                data["match_percent"],
                ", ".join(data["matched"]),
                ", ".join(data["missing"])
            ])


# ----------------------------
# Standalone Testing
# ----------------------------
if __name__ == "__main__":
    resume_path = "sample_resume.pdf"
    jd_path = "job_description.txt"

    jd_text = load_job_description(jd_path)
    results = analyze_resume(resume_path, jd_text)

    print("\n📊 Resume Analysis Report:")
    for category, data in results.items():
        print(f"\n🔹 {category.capitalize()} Skills:")
        print("Match %:", data["match_percent"])
        print("Matched:", ", ".join(data["matched"]) or "None")
        print("Missing:", ", ".join(data["missing"]) or "None")

    from analyzer import build_resume_suggestions
    print("\n💡 Suggestions:")
    for s in build_resume_suggestions(results):
        print("-", s)
