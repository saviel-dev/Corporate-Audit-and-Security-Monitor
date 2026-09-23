file_path = r'app\templates\base.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re

# Replace the disabled settings link with an active one
old = r'''<a href="#" class="nav-item disabled" id="nav-settings" data-tooltip="{{ _('Ajustes') }}">
          <i data-lucide="settings"></i>
          <span>{{ _('Ajustes') }}</span>
          <span class="nav-badge">{{ _('Pr.*?') }}</span>
        </a>'''

new = '''<a href="{{ url_for('main.ajustes') }}" class="nav-item {% if request.endpoint == 'main.ajustes' %}active{% endif %}" id="nav-settings" data-tooltip="{{ _('Ajustes') }}">
          <i data-lucide="settings"></i>
          <span>{{ _('Ajustes') }}</span>
        </a>'''

result = re.sub(old, new, content, flags=re.DOTALL)

if result != content:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(result)
    print('Patched sidebar link OK')
else:
    # Fallback - simpler replace
    old2 = '<a href="#" class="nav-item disabled" id="nav-settings"'
    new2 = '<a href="{{ url_for(\'main.ajustes\') }}" class="nav-item {% if request.endpoint == \'main.ajustes\' %}active{% endif %}" id="nav-settings"'
    content2 = content.replace(old2, new2)
    # Remove Proximo badge
    content2 = re.sub(r'<span class="nav-badge">.*?</span>', '', content2, flags=re.DOTALL)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content2)
    print('Fallback patch applied')
