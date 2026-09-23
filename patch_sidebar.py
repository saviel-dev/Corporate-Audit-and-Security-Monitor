import sys, re

file_path = r'app\templates\base.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

if 'url_for(''main.ajustes'')' not in content:
    content = re.sub(r'<li>\s*<a[^>]*>\s*<i data-lucide="settings"></i> Ajustes.*?</a>\s*</li>', 
                     r'<li>\n          <a href="{{ url_for(\'main.ajustes\') }}" class="sidebar-link {% if request.endpoint == \'main.ajustes\' %}active{% endif %}">\n            <i data-lucide="settings"></i> Ajustes\n          </a>\n        </li>', 
                     content, flags=re.DOTALL)
                     
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched base.html sidebar")
else:
    print("Ajustes link already in base.html")
