# Form Field Labeling Tool Documentation

## Overview

The Form Field Labeling Tool is a web-based application built with Flask that analyzes the accessibility of form fields in web pages. It checks for proper labeling of form fields, providing detailed reports and actionable suggestions for improving accessibility.

## Requirements

- Python
- Flask
- BeautifulSoup4
- Requests

## Installation

1. Clone the repository:

   ```bash
   git clone <repository_url>
   cd <repository_directory>
   ```

2. Install the required dependencies:
   ```bash
   pip install flask beautifulsoup4 requests
   ```

## Usage

To start the Flask application, run:

```bash
python app.py
```

The application will be available at `http://localhost:5000`.

## API Endpoints

### POST /check

Analyzes the provided HTML content or URL for form field labeling accessibility.

**Request Body:**

- `html` (string): The HTML content or URL to analyze.

**Response:**

- `200 OK`: A JSON array containing the analysis report for each form field.
- `400 Bad Request`: Error message if the HTML content cannot be fetched from the provided URL.

**Example Request:**

```json
{
  "html": "<html>...</html>"
}
```

**Example Response:**

```json
[
  {
    "field": "<input type=\"text\" id=\"name\" />",
    "hasLabel": false,
    "suggestions": [
      "Add a label element associated with this field or an aria-label attribute.",
      "Consider providing additional context with aria-label or aria-describedby."
    ],
    "snippet": "<div><label for=\"name\">Name:</label><input type=\"text\" id=\"name\" /></div>",
    "context": "Name:"
  }
]
```

To use `curl` to make a POST request to the `/check` endpoint of the Form Field Labeling Tool, you can use the following command:

### Example HTML Content

```bash
curl -X POST http://localhost:5000/check \
-H "Content-Type: application/json" \
-d '{"html": "<html><body><form><input type=\"text\" id=\"name\"><label for=\"name\">Name</label></form></body></html>"}'
```

### Example URL

If you want to analyze the HTML content of a web page given its URL, you can use the following command:

```bash
curl -X POST http://localhost:5000/check \
-H "Content-Type: application/json" \
-d '{"html": "http://example.com"}'
```

### Breakdown of the Command

- `curl -X POST http://localhost:5000/check`: Specifies a POST request to the `/check` endpoint.
- `-H "Content-Type: application/json"`: Sets the `Content-Type` header to `application/json` to indicate that the request body is in JSON format.
- `-d '{"html": "<html>...</html>"}'`: Provides the JSON data to be sent in the request body. Replace `<html>...</html>` with the actual HTML content or URL you want to analyze.

## Code Explanation

### Imports and Initialization

```python
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse, urljoin
import time

app = Flask(__name__)
```

- `Flask`: Web framework for building the application.
- `BeautifulSoup`: Library for parsing HTML and XML documents.
- `requests`: Library for making HTTP requests.
- `urlparse`, `urljoin`: Utilities for parsing and joining URLs.
- `time`: Utility for implementing rate limiting.

### Checking robots.txt

The function `is_allowed_by_robots(url, user_agent='AccessibilityAnalysisTool')` checks if the provided URL is allowed to be crawled by the tool, according to the site's `robots.txt`.

### Fetching HTML Content

The function `fetch_html_content(html_or_url)` fetches the HTML content from a URL or uses the provided HTML directly.

### Checking Form Field Labels

The function `check_labels(html)` analyzes the HTML content for form fields, checking for associated labels or aria attributes. It generates a report with suggestions for improving accessibility.

### Flask Route

The `/check` route accepts a POST request with HTML content or a URL. It uses `fetch_html_content` to get the HTML and `check_labels` to generate the accessibility report.

```python
@app.route('/check', methods=['POST'])
def check():
    html = request.json['html']
    html_content = fetch_html_content(html)
    if html_content is None:
        return jsonify({'error': 'Failed to fetch HTML content from the provided URL.'}), 400
    report = check_labels(html_content)
    return jsonify(report)
```

### Running the Application

The application is started with:

```python
if __name__ == '__main__':
    app.run(port=5000)
```

This runs the Flask app on port 5000.

## Conclusion

This documentation provides an overview of the Form Field Labeling Tool, including installation, usage, and code explanation. The tool helps improve web accessibility by analyzing form fields for proper labeling and providing actionable suggestions.
