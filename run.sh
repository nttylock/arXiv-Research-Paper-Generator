#!/bin/bash

# Activate the virtual environment
source venv/bin/activate

# Make sure the upload directory exists
mkdir -p uploads
mkdir -p templates/latex

# Run the application
python app.py