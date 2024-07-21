import re
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
import requests
import time
from urllib.parse import urlparse, urljoin
from prettytable import PrettyTable
import textwrap
from colorama import init, Fore, Style

app = Flask(__name__)

# Initialize colorama
init(autoreset=True)


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


def check_labels(soup):
    fields = soup.find_all(['input', 'textarea', 'select'])
    report = {'errors': [], 'contrast_errors': [], 'alerts': [],
              'features': [], 'structural': [], 'elements': [], 'aria': []}

    for field in fields:
        field_id = field.get('id')
        label = None
        if field_id:
            label = soup.find('label', {'for': field_id})
        if not label:
            label = field.find_parent('label')

        parent = field.find_parent()
        has_aria_label = field.get('aria-label')
        surrounding_text = parent.get_text(strip=True) if parent else ''
        snippet = parent.prettify() if parent else str(field)

        suggestions = []
        group = 'elements'
        if not label and not has_aria_label:
            suggestions.append(
                'Add a label element associated with this field or an aria-label attribute.')
            group = 'errors'

        if surrounding_text and not has_aria_label:
            suggestions.append(
                'Consider providing additional context with aria-label or aria-describedby.')
            group = 'aria'

        if field.get('placeholder'):
            suggestions.append(
                'Do not use placeholder as a substitute for labels.')
            group = 'elements'

        if field.get('required'):
            suggestions.append(
                'Ensure the required field is clearly indicated.')
            group = 'structural'

        fieldset = field.find_parent('fieldset')
        if fieldset and not fieldset.find('legend'):
            suggestions.append(
                'Add a legend element to the fieldset to describe the group of related fields.')
            group = 'structural'

        form = field.find_parent('form')
        if form and not form.find('p'):
            suggestions.append(
                'Provide clear instructions and guidance for filling out the form.')
            group = 'features'

        if field.get('aria-invalid'):
            suggestions.append(
                'Ensure the form has proper error handling and messages.')
            group = 'alerts'

        report[group].append({
            'field': str(field),
            'hasLabel': bool(label) or bool(has_aria_label),
            'suggestions': suggestions,
            'snippet': snippet,
            'context': surrounding_text
        })

    return report


def check_contrast(soup):
    contrast_errors = []

    # Find all form elements
    form_elements = soup.find_all(
        ['input', 'textarea', 'select', 'label', 'fieldset'])

    for element in form_elements:
        style = element.get('style', '')

        color_match = re.search(
            r'color:\s*(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3}|rgba?\(\d+,\s*\d+,\s*\d+(?:,\s*\d+\.?\d*)?\))', style)
        background_match = re.search(
            r'background-color:\s*(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3}|rgba?\(\d+,\s*\d+,\s*\d+(?:,\s*\d+\.?\d*)?\))', style)

        if color_match and background_match:
            fg_color = color_match.group(1)
            bg_color = background_match.group(1)

            if fg_color.startswith('#'):
                fg_rgb = hex_to_rgb(fg_color)
            else:
                fg_rgb = tuple(map(int, re.findall(r'\d+', fg_color)))

            if bg_color.startswith('#'):
                bg_rgb = hex_to_rgb(bg_color)
            else:
                bg_rgb = tuple(map(int, re.findall(r'\d+', bg_color)))

            fg_luminance = rgb_to_luminance(fg_rgb)
            bg_luminance = rgb_to_luminance(bg_rgb)
            ratio = contrast_ratio(fg_luminance, bg_luminance)

            if ratio < 4.5:
                snippet = element.prettify()
                contrast_errors.append({
                    'element': str(element),
                    'description': f'Contrast ratio is {ratio:.2f}, which is below the recommended minimum of 4.5:1.',
                    'suggestions': ['Increase the contrast between text and background colors.'],
                    'snippet': snippet,
                    'context': element.get_text(strip=True)
                })

    return contrast_errors


def check_alerts(soup):
    alerts = []

    # Find form-related elements that might use ARIA roles for alerts
    form_elements = soup.find_all(
        ['input', 'textarea', 'select', 'fieldset', 'label'])

    for element in form_elements:
        # Check for alert elements related to the form fields
        alert_elements = element.find_all(attrs={"role": "alert"})
        aria_live_elements = element.find_all(
            attrs={"aria-live": ["assertive", "polite"]})

        for alert_element in alert_elements + aria_live_elements:
            suggestions = []
            snippet = alert_element.prettify()

            # Check if the alert element has tabindex for focus management
            if not alert_element.has_attr('tabindex'):
                suggestions.append(
                    'Ensure the alert element can receive focus by adding tabindex="0".')

            # Check if the ARIA role is appropriate
            if 'role' not in alert_element.attrs:
                suggestions.append(
                    'Add appropriate ARIA role to the alert element (e.g., role="alert").')

            alerts.append({
                'element': str(alert_element),
                'suggestions': suggestions,
                'snippet': snippet,
                'context': alert_element.get_text(strip=True)
            })

    return alerts


def check_features(soup):
    features = []

    # Check for form-specific features
    forms = soup.find_all('form')
    for form in forms:
        # Check for instructions or guidance
        instructions = form.find_all(['p', 'div', 'span'], text=True)
        if not instructions:
            snippet = form.prettify()
            features.append({
                'element': str(form),
                'description': 'Form is missing clear instructions or guidance for filling out the form.',
                'snippet': snippet,
                'context': form.get_text(strip=True)
            })

        # Check for fieldset and legend elements within the form
        fieldsets = form.find_all('fieldset')
        for fieldset in fieldsets:
            legend = fieldset.find('legend')
            if not legend:
                snippet = fieldset.prettify()
                features.append({
                    'element': str(fieldset),
                    'description': 'Fieldset is missing a <legend> element.',
                    'snippet': snippet,
                    'context': fieldset.get_text(strip=True)
                })

    return features


def check_structural(soup):
    structural = []

    # Form-related structure checks
    forms = soup.find_all('form')
    for form in forms:
        # Check for missing <fieldset> and <legend> in forms
        if not form.find('fieldset'):
            snippet = form.prettify()
            structural.append({
                'element': str(form),
                'description': 'Form is missing <fieldset> elements for grouping related fields.',
                'snippet': snippet,
                'context': form.get_text(strip=True)
            })

        fieldsets = form.find_all('fieldset')
        for fieldset in fieldsets:
            if not fieldset.find('legend'):
                snippet = fieldset.prettify()
                structural.append({
                    'element': str(fieldset),
                    'description': 'Fieldset is missing a <legend> element to describe the group of related fields.',
                    'snippet': snippet,
                    'context': fieldset.get_text(strip=True)
                })

        # Check for fields without labels or placeholders
        fields = form.find_all(['input', 'textarea', 'select'])
        for field in fields:
            if not (field.get('id') and form.find('label', {'for': field.get('id')})):
                snippet = field.prettify()
                structural.append({
                    'element': str(field),
                    'description': 'Form field is missing a label element associated with it.',
                    'snippet': snippet,
                    'context': field.get('placeholder') or ''
                })

    return structural


def check_elements(soup):
    elements = []

    buttons = soup.find_all('button')
    for button in buttons:
        if not (button.get_text(strip=True) or button.get('aria-label')):
            snippet = button.prettify()
            elements.append({
                'element': str(button),
                'description': 'Button does not have an accessible name.',
                'suggestions': ['Add visible text or aria-label to the button.'],
                'snippet': snippet,
                'context': button.get_text(strip=True)
            })

    links = soup.find_all('a', href=True)
    for link in links:
        if link['href'] == '#':
            snippet = link.prettify()
            elements.append({
                'element': str(link),
                'description': 'Link has href="#" which can cause accessibility issues.',
                'suggestions': ['Provide a valid URL or use a button element for actions.'],
                'snippet': snippet,
                'context': link.get_text(strip=True)
            })

    return elements


def check_aria(soup):
    aria_issues = []

    aria_elements = soup.find_all(attrs={"role": True, "aria-*": True})
    for element in aria_elements:
        suggestions = []
        snippet = element.prettify()

        if element.name == 'div' and element.get('role') in ['button', 'link']:
            suggestions.append(
                'Consider using a <button> or <a> element instead of a <div> with role="button" or role="link".')

        aria_issues.append({
            'element': str(element),
            'description': 'Found element with ARIA role or attributes.',
            'suggestions': suggestions,
            'snippet': snippet,
            'context': element.get_text(strip=True)
        })

    return aria_issues


@app.route('/check', methods=['GET', 'POST'])
def check():
    data = request.get_json()
    url = data.get('url')
    html = data.get('html')

    if not url and not html:
        return jsonify({'error': 'URL or HTML parameter is missing.'}), 400

    if url:
        html_content = fetch_html_content(url)
        if html_content is None:
            return jsonify({'error': 'Failed to fetch HTML content from the provided URL.'}), 400
    else:
        if html.startswith('"') and html.endswith('"'):
            html = '&' + html[1:-1] + '&'
        html_content = html

    soup = BeautifulSoup(html_content, 'html.parser')
    report = check_labels(soup)
    report['contrast_errors'] = check_contrast(soup)
    report['alerts'] = check_alerts(soup)
    report['features'] = check_features(soup)
    report['structural'] = check_structural(soup)
    report['elements'] = check_elements(soup)
    report['aria'] = check_aria(soup)
    summary = {group: len(report[group]) for group in report}

    print(Fore.GREEN + "\nHTML Content:\n" +
          textwrap.fill(html_content, width=80))
    print(Fore.CYAN + "\nAccessibility Report:\n")

    table = PrettyTable()
    table.field_names = ["Category", "Issues"]

    for category, issues in report.items():
        if isinstance(issues, list):
            issues_str_list = []
            for issue in issues:
                if isinstance(issue, dict):
                    issues_str_list.append(
                        "\n".join(f"{k}: {v}" for k, v in issue.items()))
                else:
                    issues_str_list.append(str(issue))
            issues_str = "\n".join(issues_str_list)
        elif isinstance(issues, dict):
            issues_str = "\n".join(f"{k}: {v}" for k, v in issues.items())
        else:
            issues_str = str(issues)
        table.add_row([Fore.YELLOW + category + Style.RESET_ALL, issues_str])

    print(table)

    return jsonify({'report': report, 'summary': summary})


if __name__ == '__main__':
    app.run(debug=True)
