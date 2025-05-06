# arXiv Research Paper Generator

A web service that transforms text from any document (including PDFs) into professionally formatted research papers in arXiv style.

## Features

- **File Upload**: Upload text files, PDFs, DOCXs, and markdown files
- **Text Extraction**: Automatically extracts text from various file formats
- **AI Formatting**: Uses Gemini AI to structure content into a research paper format
- **LaTeX Generation**: Produces complete LaTeX code for academic documents
- **PDF Compilation**: Compiles LaTeX to publication-ready PDFs
- **AI Assistance**: Modify, expand, or improve sections with Gemini AI
- **Model Selection**: Switch between Gemini Pro 2.5 and Flash models

## Technical Overview

- **Backend**: Flask (Python)
- **Text Processing**: PyPDF2, pdfminer.six, python-docx
- **AI Integration**: Google Generative AI (Gemini)
- **PDF Generation**: LaTeX with pdflatex/bibtex
- **Frontend**: Bootstrap 5, Ace Editor

## Installation

To set up and run this application locally, follow these steps:

### 1. System Dependencies

Ensure the following system-level software is installed:

*   **Python 3.7+**:
    Make sure you have a compatible version of Python installed. You can download it from [python.org](https://www.python.org/) or install it using your system's package manager.

*   **TeX Live (for pdflatex)**:
    The application uses `pdflatex` to compile LaTeX documents into PDFs. `pdflatex` is part of the TeX Live distribution.
    *   **On Debian/Ubuntu:**
        ```bash
        sudo apt-get update
        sudo apt-get install texlive-full
        ```
        *(Alternatively, for a more minimal installation, you can try `texlive-latex-base`, `texlive-fonts-recommended`, and `texlive-latex-extra`. However, `texlive-full` is recommended to avoid missing package issues.)*
    *   **On Fedora/CentOS/RHEL:**
        ```bash
        sudo dnf update # or yum update
        sudo dnf install texlive-scheme-full # or yum install texlive-scheme-full
        ```
    *   **On macOS (using MacTeX):**
        Download and install MacTeX from [tug.org/mactex](https://tug.org/mactex/).

    After installation, verify `pdflatex` is available by running:
    ```bash
    pdflatex --version
    ```

### 2. Clone the Repository
```bash
git clone <your-repository-url>
cd <repository-name>
```
*(Replace `<your-repository-url>` and `<repository-name>` accordingly)*

### 3. Install Python Dependencies
Install the required Python packages using pip:
```bash
pip install -r requirements.txt
```

### 4. Set Up API Key
Set up your Gemini API key. You can either:
*   Hardcode it in `app.py` (not recommended for production).
*   Set it as an environment variable named `GEMINI_API_KEY`. Create a `.env` file in the project root with the following content:
    ```
    GEMINI_API_KEY=your_actual_api_key_here
    ```

### 5. Run the Application
```bash
python app.py
```
Or, for production, you might use gunicorn (ensure it's in your `requirements.txt`):
```bash
gunicorn --bind 0.0.0.0:8002 app:app
```

## Usage

1. Access the web interface at http://localhost:8002
2. Upload a document containing your text content
3. The system will process the text and generate LaTeX code
4. Edit the LaTeX code directly or use AI to improve specific sections
5. Compile to PDF and download

## Testing the API Directly

You can test the API directly using the provided test script:

```bash
python test_api.py
```

This will:
1. Create a sample LaTeX document
2. Send a request to the API to modify the LaTeX with Gemini
3. Save the modified LaTeX file

## Future Development

- Integration with additional LLM services
- Enhanced bibliography management
- Template selection for different academic styles
- Real-time collaborative editing
- Citation management
- Image extraction and handling

## License

MIT