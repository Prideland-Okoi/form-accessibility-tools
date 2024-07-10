from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse, urljoin
import time

app = Flask(__name__)


def is_allowed_by_robots(url, user_agent='AccessibilityAnalysisTool'):
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    robots_url = urljoin(base_url, '/robots.txt')

    try:
        response = requests.get(robots_url)
        if response.status_code == 200:
            robots_txt = response.text
            lines = robots_txt.split('\n')
            user_agent_directives = False
            for line in lines:
                line = line.strip()
                if line.lower().startswith(f"user-agent: {user_agent.lower()}") or line.lower().startswith("user-agent: *"):
                    user_agent_directives = True
                elif user_agent_directives and line.lower().startswith('user-agent:'):
                    user_agent_directives = False
                if user_agent_directives and line.lower().startswith('disallow:'):
                    disallow_path = line[len('disallow:'):].strip()
                    disallow_url = urljoin(base_url, disallow_path)
                    if parsed_url.path.startswith(disallow_path):
                        return False
        return True
    except requests.RequestException:
        return False


def fetch_html_content(html_or_url):
    if html_or_url.startswith(('http://', 'https://')):
        if not is_allowed_by_robots(html_or_url):
            return None
        headers = {'User-Agent': 'AccessibilityAnalysisTool/1.0'}
        try:
            response = requests.get(html_or_url, headers=headers)
            response.raise_for_status()
            time.sleep(1)  # Rate limiting: sleep for 1 second between requests
            return response.text
        except requests.RequestException:
            return None
    return html_or_url


def check_labels(html):
    soup = BeautifulSoup(html, 'html.parser')
    fields = soup.find_all(['input', 'textarea', 'select'])
    report = []

    for field in fields:
        field_id = field.get('id')
        label = None
        if field_id:
            label = soup.find('label', {'for': field_id})
        if not label:
            label = field.find_parent('label')

        # Enhanced context and usability checks
        parent = field.find_parent()
        has_aria_label = field.get('aria-label')
        surrounding_text = parent.get_text(strip=True) if parent else ''

        snippet = parent.prettify() if parent else str(field)

        # Specific actionable suggestions
        suggestions = []
        if not label and not has_aria_label:
            suggestions.append(
                'Add a label element associated with this field or an aria-label attribute.')

        if surrounding_text and not has_aria_label:
            suggestions.append(
                'Consider providing additional context with aria-label or aria-describedby.')

        report.append({
            'field': str(field),
            'hasLabel': bool(label) or bool(has_aria_label),
            'suggestions': suggestions,
            'snippet': snippet,
            'context': surrounding_text
        })

    return report


@app.route('/check', methods=['POST'])
def check():
    html = request.json['html']
    html_content = fetch_html_content(html)
    if html_content is None:
        return jsonify({'error': 'Failed to fetch HTML content from the provided URL.'}), 400
    report = check_labels(html_content)
    return jsonify(report)


if __name__ == '__main__':
    app.run(port=5000)
