import pdfplumber
import docx2txt

# Function to extract text from PDF
def extract_from_pdf(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

# Function to extract text from DOCX
def extract_from_docx(file_path):
    text = docx2txt.process(file_path)
    return text

# Test the functions
if __name__ == "__main__":
    # Change these paths to your sample files
    pdf_resume = "sample_resume.pdf"
    docx_resume = "sample_resume.docx"
    
    print("PDF Resume Text:\n", extract_from_pdf(pdf_resume))
    print("\nDOCX Resume Text:\n", extract_from_docx(docx_resume))
