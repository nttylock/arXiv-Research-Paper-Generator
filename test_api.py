import requests
import json
import os

# Configuration
API_URL = "http://localhost:8002"
TEST_FILE = "test_file.txt"

# Read test file content
with open(TEST_FILE, 'r') as f:
    text_content = f.read()

# Create session for maintaining cookies
session = requests.Session()

# Access the main page
print("Accessing main page...")
response = session.get(f"{API_URL}/")
if response.status_code == 200:
    print("Main page accessed successfully!")
else:
    print(f"Error accessing main page: {response.status_code}")
    exit(1)

# Send a request directly to the API to generate LaTeX
print("\nGenerating LaTeX content directly...")

# Create LaTeX content using the extracted text
latex_content = f"""
\\documentclass[12pt,a4paper]{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{amsmath}}
\\usepackage{{amsfonts}}
\\usepackage{{amssymb}}
\\usepackage{{graphicx}}
\\usepackage{{booktabs}}
\\usepackage{{url}}
\\usepackage[colorlinks=true,urlcolor=blue,citecolor=blue,linkcolor=blue]{{hyperref}}
\\usepackage[left=2.5cm,right=2.5cm,top=2.5cm,bottom=2.5cm]{{geometry}}
\\usepackage{{natbib}}
\\bibliographystyle{{plainnat}}

\\title{{Machine Learning for Quantum Computing}}
\\author{{AI Research Paper Generator}}
\\date{{\\today}}

\\begin{{document}}

\\maketitle

\\begin{{abstract}}
This document explores the intersection of machine learning and quantum computing, two rapidly evolving fields that have the potential to revolutionize computation. We examine how machine learning algorithms can be applied to quantum systems and how quantum computing can enhance machine learning capabilities.
\\end{{abstract}}

\\section{{Introduction}}
Quantum computing and machine learning represent two of the most promising technological paradigms of the 21st century. Quantum computing leverages quantum mechanical phenomena such as superposition and entanglement to perform computations that would be impractical or impossible on classical computers. Machine learning, on the other hand, enables computers to learn from data and improve their performance without explicit programming.

The integration of these fields has given rise to quantum machine learning, a nascent discipline that explores how quantum computing can accelerate machine learning algorithms and how machine learning can aid in quantum computing tasks.

\\section{{Quantum Computing Fundamentals}}
Quantum computers use quantum bits or qubits as their basic unit of information, unlike classical computers which use bits. While a classical bit can represent either 0 or 1, a qubit can exist in a superposition of both states simultaneously. This property, along with quantum entanglement, allows quantum computers to process vast amounts of information in parallel.

Quantum algorithms like Shor's algorithm for factoring large numbers and Grover's algorithm for searching unsorted databases demonstrate the potential of quantum computing to solve certain problems exponentially faster than classical computers.

\\section{{Machine Learning Approaches}}
Machine learning encompasses various approaches, including supervised learning, unsupervised learning, and reinforcement learning. These approaches enable systems to recognize patterns, classify data, make predictions, and optimize decision-making processes.

Deep learning, a subset of machine learning based on artificial neural networks, has achieved remarkable success in areas such as image recognition, natural language processing, and game playing.

\\section{{Quantum Machine Learning}}
Quantum machine learning investigates how quantum computing can enhance machine learning algorithms and vice versa. Quantum versions of classical machine learning algorithms, such as quantum support vector machines and quantum neural networks, aim to achieve quantum speedups.

\\section{{Challenges and Future Directions}}
Despite the promising potential, significant challenges remain. Quantum computers currently suffer from noise, decoherence, and limited qubit counts, which restrict their practical applications. Moreover, translating classical machine learning algorithms to quantum versions requires addressing fundamental differences between classical and quantum computation.

Future research directions include developing error-correction techniques for quantum computing, designing quantum-native machine learning algorithms, and exploring hybrid quantum-classical approaches that leverage the strengths of both paradigms.

\\section{{Conclusion}}
The integration of machine learning and quantum computing represents a frontier of computational innovation with far-reaching implications. As both fields continue to advance, their synergy promises to unlock new capabilities for solving complex problems across diverse domains, from materials science and drug discovery to optimization and artificial intelligence.

\\bibliography{{references}}

\\end{{document}}
"""

# Create a temporary session 
session_id = "test_session"
session_file = f"uploads/session_{session_id}.json"
session_data = {
    'latex_path': "uploads/test.tex",
    'original_text': text_content,
    'latex_content': latex_content
}

# Save the session file
os.makedirs("uploads", exist_ok=True)
with open(session_file, 'w') as f:
    json.dump(session_data, f)

# Save the LaTeX file
with open("uploads/test.tex", 'w') as f:
    f.write(latex_content)

print("\nSimulating LaTeX modification...")
instruction = "Add more details to the quantum machine learning section, specifically about applications in cryptography and drug discovery"
response = session.post(
    f"{API_URL}/api/modify_latex",
    json={"latex": latex_content, "instruction": instruction}
)

if response.status_code == 200:
    print("LaTeX modified successfully!")
    modified_latex = response.json().get("latex")
    
    # Save the modified LaTeX
    with open("uploads/modified_test.tex", 'w') as f:
        f.write(modified_latex)
    
    print("\nModified LaTeX saved to uploads/modified_test.tex")
else:
    print(f"Error modifying LaTeX: {response.status_code}")
    print(response.text)

print("\nTest completed!")