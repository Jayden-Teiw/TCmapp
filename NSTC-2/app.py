import os
from flask import Flask, render_template, request, send_file, abort
import pandas as pd

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'csv'}

# Define allowed extensions for file uploads
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Route to serve the upload form
@app.route('/')
def index():
    prefixes = ['CP', 'NSC', 'NSE', 'NSL', 'NSS']  # Example prefixes
    years = list(range(2024, 2031))  # Example years
    return render_template('upload.html', prefixes=prefixes, years=years)

# Route to handle file uploads
@app.route('/upload_file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file part", 400
    
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400
    
    if file and allowed_file(file.filename):
        case_type = request.form['case_type']
        prefix = request.form['prefix']
        month = request.form['month']
        year = request.form['year']
        min_count = int(request.form['min_count'])

        filename = file.filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Read CSV file
        try:
            df = pd.read_csv(file_path)
        except UnicodeDecodeError:
            return "Error decoding file", 400

        # Process the CSV file as needed
        # Example processing (customize as per your requirements)
        processed_df = df  # Replace with actual processing logic
        output_csv = f"{prefix}_{case_type}_{year}_{month}.csv"
        output_html = f"{prefix}_{case_type}_{year}_{month}.html"

        # Save processed CSV and HTML
        processed_df.to_csv(os.path.join(app.config['UPLOAD_FOLDER'], output_csv), index=False)
        with open(os.path.join(app.config['UPLOAD_FOLDER'], output_html), 'w') as f:
            f.write(f"<html><body><h1>{case_type} Results</h1><p>Processed file: {output_csv}</p></body></html>")

        return render_template('result.html', case_type=case_type, output_html=output_html)
    else:
        return "Invalid file format", 400

# Route to view existing files
@app.route('/view_existing_files', methods=['POST'])
def view_existing_files():
    case_type = request.form['case_type_view']
    prefix = request.form['existing_prefix']
    month = request.form['existing_month']
    year = request.form['existing_year']

    # Define the expected HTML file name
    output_html = f"{prefix}_{case_type}_{year}_{month}.html"
    output_html_path = os.path.join(app.config['UPLOAD_FOLDER'], output_html)

    if os.path.exists(output_html_path):
        with open(output_html_path, 'r') as f:
            output_html_content = f.read()
        return render_template('result.html', content=output_html_content, case_type=case_type)
    else:
        return "File not found", 404

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)
