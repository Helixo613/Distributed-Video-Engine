#!/bin/bash
# Wrapper script to run the Streamlit app with robust settings

# Ensure we are in the project root
cd "$(dirname "$0")"

# Activate venv just in case, though we call python directly
source venv/bin/activate

# Set environment variables for stability
export STREAMLIT_SERVER_MAX_UPLOAD_SIZE=4096
export STREAMLIT_SERVER_Address=0.0.0.0

echo "Starting Distributed Video Engine..."
echo "Access the UI at: http://localhost:8501"

# Run streamlit
./venv/bin/python -m streamlit run demo_app.py
