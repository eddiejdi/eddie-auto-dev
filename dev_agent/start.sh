#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
streamlit run streamlit_app.py --server.port 8502 --server.address 0.0.0.0
