# Shopping Chatbot Project

## Overview
The **Shopping Chatbot** is an intelligent assistant that helps users search for products, compare options, and receive recommendations through an interactive chat interface.  
The system fetches product data from APIs, processes it, and presents it in an easy-to-understand format.

## Features
- Search for products across multiple categories.
- Display product details including title, price, image, and link.
- Limit the number of displayed products per category.
- Generate AI responses summarizing product data.
- Store chat sessions with structured data for evaluation.

## Environment Variables
Create a `.env` file in the project root and add your API keys:

```env
SERPAPI_KEY=your_serpapi_key_here
GROQ_KEY=your_groq_key_here
```
# Create and activate virtual environment
python -m venv .venv
# On Windows
.venv\Scripts\activate
# On macOS/Linux
source .venv/bin/activate

# Install required packages
python -m pip install -r requirements.txt

# Start backend
uvicorn shopping_app:app --reload

# Start frontend
streamlit run app.py

# Run tests using Python
python shopping_app.py

# Run tests using pytest
pytest -v shopping_app.py
