from flask import Flask, request, redirect, render_template, send_file, session, url_for
import os
import pandas as pd
import asyncio
import httpx
from bs4 import BeautifulSoup
import logging

# Configure Flask app
app = Flask(__name__)
app.secret_key = "supersecretkey"  # For session management
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'

# Ensure necessary directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Keywords and elements indicating chatbot presence
CHATBOT_KEYWORDS = {"inbox-chat", "chat-button", "chat_bubble", "chat_with_us"}
CHATBOT_ELEMENTS = {"chat-widget", "chatbot", "messenger-chat", "chat-bubble", "livechat", "chat-window"}

async def has_chatbot(url):
    """Asynchronously check if a webpage contains chatbot elements or keywords."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            if response.status_code != 200:
                return False
            
            soup = BeautifulSoup(response.text, 'html.parser')
            html_content = response.text.lower()

            # Check for chatbot keywords in raw HTML
            if any(keyword in html_content for keyword in CHATBOT_KEYWORDS):
                return True

            # Check for chatbot-specific elements in parsed HTML
            return any(soup.find_all(element) for element in CHATBOT_ELEMENTS)
    except httpx.RequestError as e:
        logging.warning(f"Failed to check {url}: {e}")
        return False

def load_urls(file_path):
    """Load URLs from a CSV or Excel file in chunks to handle large files efficiently."""
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, header=None, chunksize=100)
        elif file_path.endswith('.xlsx'):
            df = pd.read_excel(file_path, header=None, chunksize=100)
        else:
            raise ValueError("Unsupported file format. Use CSV or Excel.")
        
        urls = []
        for chunk in df:
            urls.extend(chunk[0].dropna().tolist())  # Collect URLs from chunks
        return urls
    except Exception as e:
        logging.error(f"Error loading file {file_path}: {e}")
        return []

async def process_file_async(file_path):
    """Process URLs asynchronously and return a list of those containing chatbots."""
    urls = load_urls(file_path)
    if not urls:
        return []
    
    # Run all URL checks asynchronously
    results = await asyncio.gather(*(has_chatbot(url) for url in urls))
    
    # Filter only URLs that contain chatbots
    chatbot_urls = [url for url, has_bot in zip(urls, results) if has_bot]
    return chatbot_urls

@app.route('/')
def index():
    """Render homepage."""
    return render_template('index.html')

@app.route('/upload.html')
def upload():
    """Render upload page."""
    return render_template('upload.html')

@app.route('/process_file', methods=['POST'])
def process_upload():
    """Handle file upload, process it asynchronously, and display results."""
    if 'file' not in request.files:
        return redirect(request.url)

    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)

    # Save file temporarily
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)

    # Process URLs asynchronously
    chatbot_urls = asyncio.run(process_file_async(file_path))
    
    # Store results in session for display
    session['chatbot_urls'] = chatbot_urls

    # Save results to CSV
    output_file_path = os.path.join(app.config['OUTPUT_FOLDER'], 'urls_with_chatbots.csv')
    pd.DataFrame(chatbot_urls, columns=['URL']).to_csv(output_file_path, index=False)

    return redirect(url_for('show_results'))

@app.route('/results')
def show_results():
    """Display results from session."""
    urls_with_chatbots = session.get('chatbot_urls', [])
    return render_template('results.html', urls=urls_with_chatbots)

@app.route('/output/urls_with_chatbots.csv')
def download_file():
    """Allow users to download the processed chatbot URLs."""
    output_file_path = os.path.join(app.config['OUTPUT_FOLDER'], 'urls_with_chatbots.csv')
    return send_file(output_file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
