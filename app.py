from flask import Flask, request, redirect, render_template, send_file, session, url_for
import os
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
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

def has_chatbot(url):
    """Check if a webpage contains chatbot elements or keywords."""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return False
        
        soup = BeautifulSoup(response.text, 'html.parser')
        html_content = response.text.lower()

        # Check keywords in raw HTML
        if any(keyword in html_content for keyword in CHATBOT_KEYWORDS):
            return True

        # Check specific elements in parsed HTML
        return any(soup.find_all(element) for element in CHATBOT_ELEMENTS)

    except requests.RequestException as e:
        logging.warning(f"Failed to check {url}: {e}")
        return False

def load_urls(file_path):
    """Load URLs from a CSV or Excel file."""
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, header=None)
        elif file_path.endswith('.xlsx'):
            df = pd.read_excel(file_path, header=None)
        else:
            raise ValueError("Unsupported file format. Use CSV or Excel.")
        
        return df[0].dropna().tolist()  # Remove empty values and return list
    except Exception as e:
        logging.error(f"Error loading file {file_path}: {e}")
        return []

def process_file(file_path):
    """Process URLs and return a list of those containing chatbots."""
    urls = load_urls(file_path)
    if not urls:
        return []
    
    chatbot_urls = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(has_chatbot, url): url for url in urls}

        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                if future.result():
                    chatbot_urls.append(url)
            except Exception as e:
                logging.error(f"Error processing {url}: {e}")

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
    """Handle file upload, process it, and display results."""
    if 'file' not in request.files:
        return redirect(request.url)

    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)

    # Save file temporarily
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)

    # Process URLs
    urls_with_chatbots = process_file(file_path)
    
    # Store results in session for display
    session['chatbot_urls'] = urls_with_chatbots

    # Save results to CSV
    output_file_path = os.path.join(app.config['OUTPUT_FOLDER'], 'urls_with_chatbots.csv')
    pd.DataFrame(urls_with_chatbots, columns=['URL']).to_csv(output_file_path, index=False)

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
