import os
import tempfile
import shutil
import sys
from datetime import datetime
from flask import Flask, request, render_template, send_file, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
import google.generativeai as genai
from io import BytesIO
import PyPDF2
from pdfminer.high_level import extract_text as extract_text_pdfminer
from docx import Document
import subprocess
import uuid
import re
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Ensure /Library/TeX/texbin is in PATH for pdflatex on macOS
tex_bin_path = "/Library/TeX/texbin"
if tex_bin_path not in os.environ.get("PATH", ""):
    os.environ["PATH"] = tex_bin_path + os.pathsep + os.environ.get("PATH", "")
print("PATH for pdflatex:", os.environ.get("PATH"))

import shutil
print("pdflatex path from Python:", shutil.which("pdflatex"))

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'md'}
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LATEX_TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'latex')

# Initialize the app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload
app.secret_key = os.urandom(24)

# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(LATEX_TEMPLATE_PATH, exist_ok=True)

# Initialize Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Check LaTeX installation
def check_latex_installation():
    import shutil
    pdflatex_path = shutil.which("pdflatex")
    if pdflatex_path:
        return True
    else:
        print("WARNING: pdflatex not found. PDF generation will not work.")
        return False

HAS_LATEX = check_latex_installation()

# Setup the Gemini model - correct names based on current API
models = {
    # Use descriptive keys likely matching UI dropdown, map to current API model IDs
    "Pro 1.5": "models/gemini-1.5-pro-latest", 
    # "pro_2_5": "gemini-pro", # Old/incorrect entry removed
    "Flash 1.5": "models/gemini-1.5-flash-latest" # Assuming flash also needs 'models/' prefix and '-latest'
}

# Set the default model to a valid, current one
current_model = "models/gemini-1.5-pro-latest"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(file_path):
    try:
        # Try with PyPDF2 first
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num in range(len(pdf_reader.pages)):
                text += pdf_reader.pages[page_num].extract_text()
        
        # If PyPDF2 didn't extract much text, try pdfminer
        if len(text.strip()) < 100:
            text = extract_text_pdfminer(file_path)
            
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return ""

def extract_text_from_docx(file_path):
    try:
        doc = Document(file_path)
        text = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
        return text
    except Exception as e:
        print(f"Error extracting text from DOCX: {e}")
        return ""

def extract_text_from_file(file_path):
    file_extension = file_path.rsplit('.', 1)[1].lower()
    
    if file_extension == 'pdf':
        return extract_text_from_pdf(file_path)
    elif file_extension == 'docx':
        return extract_text_from_docx(file_path)
    elif file_extension in ['txt', 'md']:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            return file.read()
    return ""

def generate_research_paper_structure(text, title=None):
    try:
        model = genai.GenerativeModel(current_model)
        prompt = f"""
        Your task is to transform the following text into a properly structured academic research paper in arXiv style. 
        The paper should include:
        
        1. Title: Create a compelling academic title if not specified
        2. Authors: List as 'Authors: [Extract or suggest authors]'
        3. Abstract: A concise summary of the paper
        4. Introduction: Background, motivation, and objectives
        5. Methodology/Approach: Research methods used
        6. Results: Key findings
        7. Discussion: Interpretation of results
        8. Conclusion: Summary of contributions and future work
        9. References: Citations formatted in academic style
        
        FORMAT YOUR RESPONSE AS STRUCTURED LATEX CODE that I can compile into a PDF.
        The LaTeX code should be complete, with proper document class, packages, etc.
        
        Here's the content to structure:
        {text}
        
        Title (if specified): {title if title else 'Generate an appropriate title'}
        """
        
        response = model.generate_content(prompt)
        # Escape the generated content before returning
        return escape_latex(response.text) 
    except Exception as e:
        print(f"Error generating content with Gemini: {e}", file=sys.stderr)
        # Escape the original text when using the fallback template
        escaped_fallback_text = escape_latex(text)
        # Return a basic LaTeX template using a RAW f-string
        return fr"""\documentclass[12pt,a4paper]{{article}}
\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage{{amsmath}}
\usepackage{{amsfonts}}
\usepackage{{amssymb}}
\usepackage{{graphicx}}
\usepackage{{booktabs}}
\usepackage{{url}}
\usepackage[colorlinks=true,urlcolor=blue,citecolor=blue,linkcolor=blue]{{hyperref}}
\usepackage[left=2.5cm,right=2.5cm,top=2.5cm,bottom=2.5cm]{{geometry}}
\usepackage{{natbib}}
\bibliographystyle{{plainnat}}

\title{{{title if title else 'Research Paper'}}}
\author{{Generated by Research Paper Service}}
\date{{\today}}

\begin{{document}}

\maketitle

\begin{{abstract}}
This is an automatically generated research paper from the provided content.
There was an error communicating with the AI service: {str(e)}
\end{{abstract}}

\section{{Content}}
{escaped_fallback_text}

\end{{document}}"""

def escape_latex(text):
    """Escapes LaTeX special characters in a given string, excluding backslash and braces.
    Also removes unsupported non-ASCII characters to prevent LaTeX errors.
    """
    if not isinstance(text, str):
        text = str(text) # Ensure text is string

    # 1. Remove potentially problematic non-ASCII characters first
    text = ''.join(c for c in text if 32 <= ord(c) < 127 or ord(c) >= 160)

    # 2. Define characters to escape (excluding backslash AND braces)
    conv = {
        # '\': r'\textbackslash{}', # REMOVED - Backslash should not be escaped here
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
    }
    # Create a regex from the keys of conv
    regex = re.compile('|'.join(re.escape(str(key)) for key in sorted(conv.keys(), key=len, reverse=True)))
    
    # Function to perform replacement using the dictionary
    def replace(match):
        return conv[match.group(0)]

    # Escape known special characters
    escaped_text = regex.sub(replace, text)

    # Filter out remaining non-ASCII characters that might cause issues
    # Keep ASCII characters (0-127) and allow escaped sequences generated above
    # This simplistic approach removes characters like emojis 🟢🔴 directly
    # A more sophisticated approach might try to map them, but removal is safer for compilation.
    filtered_text = ''.join(char for char in escaped_text if ord(char) < 128 or char in ['\\', '{', '}'])
    # We explicitly allow backslash, curly braces as they are part of valid LaTeX commands/escapes produced earlier
    # This check is basic and might need refinement depending on content
    
    # A refined filter that tries to preserve more while removing problematic high-Unicode chars:
    final_text = ""
    i = 0
    while i < len(escaped_text):
        char = escaped_text[i]
        if ord(char) < 128: # Keep standard ASCII
            final_text += char
            i += 1
        elif char == '\\' and i + 1 < len(escaped_text): # Check for known escape sequences
            # Look ahead for common LaTeX command patterns or escaped chars
            # Corrected line continuation and syntax
            match = (re.match(r"\\[a-zA-Z]+{}", escaped_text[i:]) or \
                   re.match(r"\\[&%$#_{}~^\"<>|]", escaped_text[i:]) or \
                   re.match(r"\\text[a-zA-Z]+{}", escaped_text[i:]))
            if match:
                sequence = match.group(0)
                final_text += sequence
                i += len(sequence)
            else: # Unknown backslash sequence, skip the backslash maybe?
                # Or just skip the char causing issues if it's high unicode
                i += 1 # Skip the backslash if it doesn't start a recognized sequence
        else: # Skip other non-ASCII characters (like emojis)
            i += 1
            
    #return filtered_text # Old simple filter
    return final_text


import re # Add import for regex
def preprocess_markdown_to_latex(text):
    """Converts basic Markdown elements to LaTeX placeholders."""
    if not isinstance(text, str):
        text = str(text) # Ensure text is a string

    # 1. Replace double newlines (paragraph breaks) with a placeholder FIRST
    # Handles \n\n, \n \n, \n  \n etc.
    text = re.sub(r'\n\s*\n', '\n%%PARAGRAPH_BREAK%%\n', text)

    lines = text.split('\n')
    processed_lines = []
    in_itemize = False
    for line in lines:
        stripped_line = line.strip()

        # Handle lists first
        is_list_item = stripped_line.startswith(('-', '*')) and len(stripped_line) > 1 and stripped_line[1] == ' '
        is_empty_line = not stripped_line

        if is_list_item:
            item_content = stripped_line[2:].strip()
            # Apply inner markdown like bold FIRST
            item_content = re.sub(r'\*\*(.*?)\*\*', r'%%BOLD%%\1%%ENDBOLD%%', item_content)
            if not in_itemize:
                processed_lines.append("%%BEGIN_ITEMIZE%%")
                in_itemize = True
            processed_lines.append(f"%%ITEM%% {item_content}")
        else:
            # If we were in itemize and hit a non-empty, non-list line, close the list
            if in_itemize and not is_empty_line:
                processed_lines.append("%%END_ITEMIZE%%")
                in_itemize = False
            # If we were in itemize and hit an empty line, ALSO close the list (simplest approach)
            elif in_itemize and is_empty_line:
                 processed_lines.append("%%END_ITEMIZE%%")
                 in_itemize = False
                 # Add the empty line itself to preserve paragraph breaks
                 processed_lines.append("")
                 continue # Skip further processing for this empty line

            # Now process the non-list, non-empty line for other markdown
            # Only process if it wasn't an empty line that closed a list
            if not is_empty_line:
                current_line_processed = False
                if stripped_line.startswith('#'):
                    level = 0
                    while level < len(stripped_line) and stripped_line[level] == '#':
                        level += 1
                    title_content = stripped_line[level:].strip()
                    # Apply inner markdown like bold FIRST
                    title_content = re.sub(r'\*\*(.*?)\*\*', r'%%BOLD%%\1%%ENDBOLD%%', title_content)
                    sec_cmd = "%%PARAGRAPH%%" # Default
                    if level == 1: sec_cmd = "%%SECTION%%"
                    elif level == 2: sec_cmd = "%%SUBSECTION%%"
                    elif level == 3: sec_cmd = "%%SUBSUBSECTION%%"
                    processed_lines.append(f"{sec_cmd}{{{title_content}}}")
                    current_line_processed = True
                else:
                    # Regular line, just check for bold
                    processed_line = re.sub(r'\*\*(.*?)\*\*', r'%%BOLD%%\1%%ENDBOLD%%', line)
                    processed_lines.append(processed_line)
                    current_line_processed = True
            elif is_empty_line:
                 # Append empty lines if they are not closing a list
                 processed_lines.append("")


    # End itemize if the document ends with a list
    if in_itemize:
        processed_lines.append("%%END_ITEMIZE%%")

    return '\n'.join(processed_lines)

def finalize_latex_content(text):
    # Replace placeholders with actual LaTeX commands
    text = text.replace("%%BEGIN_ITEMIZE%%", r"\begin{itemize}")
    text = text.replace("%%END_ITEMIZE%%", r"\end{itemize}")
    text = text.replace("%%ITEM%%", r"\item")
    text = text.replace("%%SECTION%%", r"\section")
    text = text.replace("%%SUBSECTION%%", r"\subsection")
    text = text.replace("%%SUBSUBSECTION%%", r"\subsubsection")
    text = text.replace("%%PARAGRAPH%%", r"\paragraph")
    text = text.replace("%%BOLD%%", r"\textbf{") # Add opening brace
    text = text.replace("%%ENDBOLD%%", r"}")
    text = text.replace("%%PARAGRAPH_BREAK%%", "\n\n") # Add paragraph break replacement
    return text

# Define placeholders (use unlikely sequences)
PLACEHOLDERS = {
    "section_start":    "__SECSTART__",
    "section_end":      "__SECEND__",
    "subsection_start": "__SUBSECSTART__",
    "subsection_end":   "__SUBSECEND__",
    "bold_start":       "__BOLDSTART__",
    "bold_end":         "__BOLDEND__",
    "itemize_start":    "__ITEMIZESTART__", # New
    "itemize_end":      "__ITEMIZEEND__",   # New
    "item_start":       "__ITEMSTART__"     # New (no end needed for \item)
}

def modify_with_gemini(text, instruction):
    try:
        model = genai.GenerativeModel(current_model)
        # Добавить проверку на простоту инструкции? Или всегда добавлять указание?
        # Пока добавим указание всегда:
        prompt = f"""
        You are working with a LaTeX document for a research paper. 
        Your task is to modify it ONLY according to the following instruction, PRESERVING ALL OTHER CONTENT EXACTLY AS IT IS:

        Instruction: {instruction}

        Here is the current LaTeX content:
        ```latex
        {text}
        ```

        Provide the complete modified LaTeX document. IMPORTANT: Make ONLY the change specified in the instruction. Do NOT summarize, shorten, rephrase, or alter any other part of the document unless explicitly asked to.
        """

        # Configure generation to allow for potentially large output
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=8192
        )

        response = model.generate_content(
            prompt, 
            generation_config=generation_config
        )
        # Log the response from Gemini for debugging
        print("--- Gemini Response Start ---", file=sys.stderr)
        print(response.text, file=sys.stderr)
        print("--- Gemini Response End ---", file=sys.stderr)
        return response.text
    except Exception as e:
        print(f"Error modifying content with Gemini: {e}", file=sys.stderr)
        return text

def compile_latex_to_pdf(latex_content, output_dir):
    if not HAS_LATEX:
        # Save the LaTeX content to a file and return None to indicate PDF generation failed
        # The content should already be escaped at this point.
        temp_file_path = os.path.join(output_dir, f"latex_content_{uuid.uuid4()}.tex")
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(latex_content) # Write the original, pre-escaped content
        print("LaTeX not found. Saved .tex content only.", file=sys.stderr)
        return None
    
    # Create unique ID for this compilation
    compilation_id = str(uuid.uuid4())
    temp_dir = os.path.join(output_dir, compilation_id)
    os.makedirs(temp_dir, exist_ok=True)
    
    # Create main LaTeX file
    latex_file_path = os.path.join(temp_dir, "paper.tex")
    with open(latex_file_path, "w", encoding="utf-8") as latex_file:
        print("--- Writing to paper.tex: ---")
        print(latex_content)
        print("--- End of paper.tex content ---")
        latex_file.write(latex_content) # Write the original, pre-escaped content
    
    # Create bibliography file if references are detected
    # Note: We might need to be careful if bib_content also needs escaping?
    # Assuming bib_content is already properly formatted .bib data for now.
    if "\\bibliography{references}" in latex_content or "\\addbibresource" in latex_content:
        # Placeholder for bib generation logic - ensure it produces valid .bib
        # bib_content = generate_bibliography_from_latex(latex_content) # Pass escaped content?
        bib_file_path = os.path.join(temp_dir, "references.bib")
        # Create an empty bib file for now if logic isn't implemented
        # to avoid BibTeX errors if file is expected but missing.
        if not os.path.exists(bib_file_path):
             with open(bib_file_path, "w", encoding="utf-8") as bib_file:
                 bib_file.write("% Empty bib file created by Flask app\n")
    
    # Change to the temp directory
    original_dir = os.getcwd()
    os.chdir(temp_dir)
    
    try:
        # Run pdflatex, bibtex, and pdflatex again for proper citations
        subprocess.run(["pdflatex", "-interaction=nonstopmode", "paper.tex"], check=True)
        
        # Check if bib file exists before running bibtex
        if os.path.exists(os.path.join(temp_dir, "references.bib")) and ("\\bibliography{references}" in latex_content or "\\addbibresource" in latex_content):
            # Attempt to run bibtex, but catch errors if .aux is missing etc.
            try:
                subprocess.run(["bibtex", "paper"], check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as bib_e:
                print(f"BibTeX warning/error: {bib_e.stderr}", file=sys.stderr)
                # Continue compilation even if bibtex fails, might just miss citations
            subprocess.run(["pdflatex", "-interaction=nonstopmode", "paper.tex"], check=True)
        
        # Run one more time to resolve references
        subprocess.run(["pdflatex", "-interaction=nonstopmode", "paper.tex"], check=True)
        
        # Check if the PDF was created
        pdf_path = os.path.join(temp_dir, "paper.pdf")
        if os.path.exists(pdf_path):
            return pdf_path
        else:
            return None
    except subprocess.CalledProcessError as e:
        print(f"LaTeX compilation error: {e}", file=sys.stderr)
        return None
    finally:
        # Change back to the original directory
        os.chdir(original_dir)

def generate_bibliography_from_latex(latex_content):
    try:
        model = genai.GenerativeModel(current_model)
        
        # Extract citation commands
        citation_pattern = r'\\cite\{([^}]+)\}'
        citations = re.findall(citation_pattern, latex_content)
        
        # Flatten and make unique
        citation_keys = []
        for cite in citations:
            for key in cite.split(','):
                citation_keys.append(key.strip())
        
        citation_keys = list(set(citation_keys))
        
        if not citation_keys:
            # Default bibliography with sample entries
            return """
    @article{sample1,
    title={Sample Article Title},
    author={Author, A. and Author, B.},
    journal={Journal of Examples},
    volume={1},
    number={1},
    pages={1--10},
    year={2025}
    }

    @book{sample2,
    title={Sample Book Title},
    author={Author, C.},
    publisher={Sample Publisher},
    year={2024},
    address={City, Country}
    }
    """
        
        prompt = f"""
        Generate a BibTeX bibliography (.bib file) for the following citation keys found in a LaTeX document:
        {', '.join(citation_keys)}
        
        Create realistic and academic-appropriate BibTeX entries for each citation key. Make up appropriate information for each entry.
        Format your response as valid BibTeX content only, no explanations.
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating bibliography with Gemini: {e}", file=sys.stderr)
        # Return a basic bibliography
        return "\n".join([f"@article{{{key},\n  title={{Reference for {key}}},\n  author={{Author}},\n  journal={{Journal}},\n  year={{2025}}\n}}" for key in citation_keys])

@app.route('/')
def index():
    return render_template('index.html', models=models, current_model=current_model, has_latex=HAS_LATEX)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        session_id = str(uuid.uuid4())
        session_dir = os.path.join(UPLOAD_FOLDER, session_id)
        os.makedirs(session_dir, exist_ok=True)
        file_path = os.path.join(session_dir, filename)
        file.save(file_path)

        # --- Extract text based on file type --- 
        extracted_text = extract_text_from_file(file_path)
        if extracted_text is None:
            flash('Could not extract text from file.')
            return redirect(request.url)

        # --- Process text to preserve paragraphs --- 
        # 1. Preprocess Markdown to placeholders
        text_with_placeholders = preprocess_markdown_to_latex(extracted_text)
        # 2. Replace placeholders with final LaTeX commands
        text_with_commands = finalize_latex_content(text_with_placeholders)
        # 3. Escape LaTeX special characters *around* the commands
        final_body_text = escape_latex(text_with_commands)
        
        # Use provided title or default to filename
        title = request.form.get('title', '') # Get title from form
        authors = request.form.get('authors', '') # Get authors from form
        final_title = title if title else filename
        # Escape title and authors separately
        escaped_title = escape_latex(final_title)
        escaped_authors = escape_latex(authors)

        # --- Format the final LaTeX document --- 
        latex_template = r"""\documentclass[12pt,a4paper]{{article}}
\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage{{amsmath}}
\usepackage{{amsfonts}}
\usepackage{{amssymb}}
\usepackage{{graphicx}}
\usepackage{{booktabs}}
\usepackage{{url}}
\usepackage[colorlinks=true,urlcolor=blue,citecolor=blue,linkcolor=blue]{{hyperref}}
\usepackage[left=2.5cm,right=2.5cm,top=2.5cm,bottom=2.5cm]{{geometry}}
% Removed bibliography packages for simplicity in direct text conversion

\title{{{title}}}
\author{{{authors}}}
\date{{\today}}

\begin{{document}}

\maketitle

{body}

\end{{document}}"""

        # Populate the template using an f-string or .format()
        # Using f-string here for interpolation into the defined template holes
        latex_content = latex_template.format(
            title=escaped_title, 
            authors=escaped_authors, 
            body=final_body_text # Body is already escaped and finalized
        )

        # --- Save session data --- 
        session_data = {
            'latex_path': file_path,
            'original_text': extracted_text,
            'latex_content': latex_content
        }
        
        # In a real application, we would store this in a database or session
        # For simplicity, we're storing it in a file
        session_file = os.path.join(session_dir, f"{session_id}_session.json")
        import json
        with open(session_file, 'w') as f:
            json.dump(session_data, f)
        
        return redirect(url_for('edit_paper', session_id=session_id))
    
    flash('File type not allowed')
    return redirect(url_for('index'))

@app.route('/edit/<session_id>', methods=['GET', 'POST'])
def edit_paper(session_id):
    # Load the session data
    import json
    session_file_path = os.path.join(app.config['UPLOAD_FOLDER'], session_id, f"{session_id}_session.json")
    
    if not os.path.exists(session_file_path):
        flash('Session not found')
        return redirect(url_for('index'))
    
    with open(session_file_path, 'r') as f:
        session_data = json.load(f)
    
    if request.method == 'POST':
        # Handle the edit form submission
        latex_content = request.form.get('latex_content', '')
        instruction = request.form.get('instruction', '')
        
        if instruction:
            # Modify the latex using Gemini
            print(f"--- Attempting to modify with Gemini. Instruction: [{instruction}] ---", file=sys.stderr)
            latex_content = modify_with_gemini(latex_content, instruction)
        
        # Update the session data
        session_data['latex_content'] = latex_content
        with open(session_file_path, 'w') as f:
            json.dump(session_data, f)
        
        # Compile to PDF if requested
        if 'compile_pdf' in request.form:
            if not HAS_LATEX:
                flash('LaTeX (pdflatex) is not installed. Please install LaTeX to generate PDFs.', 'error')
                return render_template('edit.html', 
                                     session_id=session_id, 
                                     latex_content=session_data['latex_content'],
                                     models=models,
                                     current_model=current_model,
                                     has_latex=HAS_LATEX)
            
            pdf_path = compile_latex_to_pdf(latex_content, app.config['UPLOAD_FOLDER'])
            if pdf_path:
                return send_file(pdf_path, as_attachment=True, download_name='research_paper.pdf')
            else:
                flash('Error compiling LaTeX to PDF')
    
    # GET request: Load existing data
    print(f"--- [GET /edit] Processing session_id: {session_id} ---", file=sys.stderr) # Log session ID on GET
    file_exists = os.path.exists(session_file_path)
    print(f"--- [GET /edit] Checking exists for {session_file_path}: {file_exists} ---", file=sys.stderr) # Log file existence check on GET
    
    if not file_exists:
        flash('Session expired or invalid.')
        return redirect(url_for('index'))
    
    return render_template('edit.html', 
                          session_id=session_id, 
                          latex_content=session_data['latex_content'],
                          models=models, 
                          current_model=current_model,
                          has_latex=HAS_LATEX)

@app.route('/compile/<session_id>', methods=['POST'])
def compile_latex_route(session_id):
    print(f"--- [POST /compile] Received request for session_id: {session_id} ---", file=sys.stderr)
    session_file_path = os.path.join(app.config['UPLOAD_FOLDER'], session_id, f"{session_id}_session.json")
    
    if not os.path.exists(session_file_path):
        print(f"--- [POST /compile] Error: Session file not found for {session_id} ---", file=sys.stderr)
        return jsonify({'error': 'Session not found'}), 404

    # Check if LaTeX is installed
    if not HAS_LATEX:
        print(f"--- [POST /compile] Error: LaTeX (pdflatex) is not installed. ---", file=sys.stderr)
        return jsonify({'error': 'LaTeX (pdflatex) is not installed. Please install LaTeX to generate PDFs.'}), 500

    # --- START: Removed unnecessary text processing ---
    # The content from the form should be the complete, potentially modified LaTeX document
    # It should already have necessary parts escaped from previous steps (upload/Gemini)
    # Do NOT re-process or re-escape the entire document here.
    raw_latex_content = request.form['latex_content'] 
    processed_latex_content = raw_latex_content # Use the content directly
    # --- END: Removed unnecessary text processing ---
    
    # Create a temporary directory for compilation
    temp_dir = tempfile.mkdtemp()
    latex_file_path = os.path.join(temp_dir, 'paper.tex')
    pdf_file_path = os.path.join(temp_dir, 'paper.pdf')
    log_path = os.path.join(temp_dir, 'paper.log') # Define log path
    
    success = False
    log_output = ""

    try:
        # Write the PROCESSED LaTeX content to the .tex file
        with open(latex_file_path, 'w', encoding='utf-8') as f:
            f.write(processed_latex_content)
        
        print(f"--- [POST /compile] Wrote processed LaTeX to {latex_file_path} ---", file=sys.stderr)
        
        # --- START: Adapted pdflatex calls --- 
        # Run pdflatex compilation steps within the temporary directory
        try:
            # First pass
            cmd = ['pdflatex', '-interaction=nonstopmode', 'paper.tex']
            print(f"--- [POST /compile] Running command: {' '.join(cmd)} in {temp_dir} ---", file=sys.stderr)
            result = subprocess.run(cmd, cwd=temp_dir, check=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            log_output += result.stdout + "\n" + result.stderr + "\n"
            
            # Second pass (often needed for references, TOC, etc.)
            print(f"--- [POST /compile] Running command: {' '.join(cmd)} in {temp_dir} (2nd pass) ---", file=sys.stderr)
            result = subprocess.run(cmd, cwd=temp_dir, check=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            log_output += result.stdout + "\n" + result.stderr

            # Check if PDF exists after compilation
            if os.path.exists(pdf_file_path):
                success = True
                print(f"--- [POST /compile] Compilation successful (PDF found) for {session_id} ---", file=sys.stderr)
            else:
                 print(f"--- [POST /compile] Compilation seemingly finished but PDF not found for {session_id} ---", file=sys.stderr)

        except subprocess.CalledProcessError as e:
            print(f"--- [POST /compile] LaTeX compilation failed for {session_id} with CalledProcessError: {e} ---", file=sys.stderr)
            log_output += e.stdout + "\n" + e.stderr if e.stdout else ""
            log_output += e.stderr if e.stderr else ""
            # Try to read log file even if process failed
            if os.path.exists(log_path):
                try:
                    with open(log_path, 'r', encoding='utf-8', errors='ignore') as log_file:
                        log_output += "\n--- Log File Content ---\n" + log_file.read()
                except Exception as log_read_e:
                    print(f"--- [POST /compile] Error reading log file {log_path}: {log_read_e} ---", file=sys.stderr)            
        except Exception as e:
            # Catch other potential errors during subprocess execution
            print(f"--- [POST /compile] Unexpected error during pdflatex execution: {e} ---", file=sys.stderr)
            log_output += f"\nUnexpected Python error during compilation: {e}"
        # --- END: Adapted pdflatex calls --- 

        if success:
            return send_file(pdf_file_path, as_attachment=True, download_name=f'{session_id}_paper.pdf')
        else:
            print(f"--- [POST /compile] Returning compilation failure response for {session_id} ---", file=sys.stderr)
            # Ensure log_output has content, provide default if empty after errors
            if not log_output and os.path.exists(log_path):
                 try:
                    with open(log_path, 'r', encoding='utf-8', errors='ignore') as log_file:
                        log_output = "--- Log File Content ---\n" + log_file.read()
                 except Exception as log_read_e:
                     log_output = "Compilation failed. Error reading log file." 
                     print(f"--- [POST /compile] Error reading log file {log_path} on failure: {log_read_e} ---", file=sys.stderr)            
            elif not log_output:
                log_output = "Compilation failed. No specific log output captured."
                
            # Truncate log if too long to avoid large JSON response
            max_log_length = 5000 
            if len(log_output) > max_log_length:
                log_output = log_output[-max_log_length:] + "\n... (log truncated)"
                
            return jsonify({'error': 'LaTeX compilation failed', 'log': log_output}), 500
            
    except Exception as e:
        # Catch errors during file writing or other steps before compilation
        print(f"--- [POST /compile] Outer exception before/after compilation for {session_id}: {e} ---", file=sys.stderr)
        # Log traceback for debugging server-side
        import traceback
        traceback.print_exc(file=sys.stderr) 
        return jsonify({'error': f'An unexpected error occurred: {e}'}), 500
    finally:
        # Clean up the temporary directory
        try:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                print(f"--- [POST /compile] Cleaned up temp directory: {temp_dir} ---", file=sys.stderr)
        except Exception as e:
            print(f"Error cleaning up temp directory {temp_dir}: {e}", file=sys.stderr)

@app.route('/set_model', methods=['POST'])
def set_model():
    global current_model
    model_key = request.form.get('model')
    if model_key in models:
        current_model = models[model_key]
        flash(f'Model switched to {model_key}')
    return redirect(request.referrer or url_for('index'))

@app.route('/api/modify_latex', methods=['POST'])
def api_modify_latex():
    import json # Add this import
    print("--- Entered api_modify_latex ---", file=sys.stderr) # Add this line for debugging
    data = request.get_json()
    session_id = data.get('session_id')
    latex_content = data.get('latex_content')
    instruction = data.get('instruction')

    print(f"--- Received session_id: {session_id} ---", file=sys.stderr) # Log received session_id

    if not all([session_id, latex_content, instruction]):
        return jsonify({'error': 'Missing data'}), 400

    session_file_path = os.path.join(app.config['UPLOAD_FOLDER'], session_id, f"{session_id}_session.json")
    print(f"--- Checking for session file at: {session_file_path} ---", file=sys.stderr) # Log the path being checked

    if not os.path.exists(session_file_path):
        return jsonify({'error': 'Session not found'}), 404

    try:
        # Modify the content using Gemini
        modified_latex = modify_with_gemini(latex_content, instruction)

        # --- Add saving logic here ---
        try:
            with open(session_file_path, 'r') as f:
                session_data = json.load(f)
            
            session_data['latex_content'] = modified_latex # Update the content
            
            with open(session_file_path, 'w') as f:
                json.dump(session_data, f, indent=4) # Save it back
            print(f"--- Successfully updated session file {session_id} with Gemini modifications ---", file=sys.stderr)
            
        except Exception as e:
            print(f"Error updating session file {session_id} after Gemini modification: {e}", file=sys.stderr)
            # Decide if we should still return the modified content or an error
            # For now, let's still return it to the client, but log the save error
            # return jsonify({'error': f'Could not save modified content: {e}'}), 500
        # --- End saving logic ---
        
        # Return the modified content to update the editor
        return jsonify({'latex_content': modified_latex})

    except Exception as e:
        print(f"Error in api_modify_latex during Gemini call: {e}", file=sys.stderr)
        # Return the original content or an error message
        # Returning original content might be less confusing for the user than an empty editor
        return jsonify({'error': f'Error modifying content with Gemini: {e}', 'latex_content': latex_content}), 500 

@app.route('/download_latex/<session_id>', methods=['GET'])
def download_latex(session_id):
    # Load the session data
    import json
    session_file = os.path.join(app.config['UPLOAD_FOLDER'], session_id, f"{session_id}_session.json")
    
    if not os.path.exists(session_file):
        flash('Session not found')
        return redirect(url_for('index'))
    
    with open(session_file, 'r') as f:
        session_data = json.load(f)
    
    # Create a temp file for the LaTeX content
    temp_latex_file = os.path.join(app.config['UPLOAD_FOLDER'], f"download_{session_id}.tex")
    with open(temp_latex_file, 'w', encoding='utf-8') as f:
        f.write(session_data['latex_content'])
    
    return send_file(temp_latex_file, as_attachment=True, download_name='research_paper.tex')

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image part'}), 400
    
    file = request.files['image']
    
    if file.filename == '':
        return jsonify({'error': 'No selected image'}), 400
    
    if file:
        filename = secure_filename(file.filename)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], f"img_{uuid.uuid4()}_{filename}")
        file.save(image_path)
        
        # Generate LaTeX code to include the image using RAW f-string with DOUBLE CURLY BRACES for literals
        # Note: {image_path} and {filename.split('.')[0]} are variables, keep single braces
        latex_code = fr"""\begin{{figure}}[ht]
\centering
\includegraphics[width=0.8\textwidth]{{{image_path}}}
\caption{{Caption for this image}}
\label{{fig:{filename.split('.')[0]}}}
\end{{figure}}"""
        
        return jsonify({
            'success': True,
            'latex_code': latex_code,
            'image_path': image_path
        })
    
    return jsonify({'error': 'Error uploading image'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8002, debug=True)