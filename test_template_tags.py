#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.template import Template, Context

# Test the template tag
template_string = """
{% load country_flags %}
Country: {{ country }}
Flag: {{ country|country_flag }}
Domain: {{ country|google_domain }}
With Flag: {{ country|country_with_flag }}
"""

template = Template(template_string)
context = Context({'country': 'US'})
output = template.render(context)

print("Template output:")
print(output)
print("\n" + "="*50 + "\n")

# Test with badge
template_string2 = """
{% load country_flags %}
Badge: {% country_badge country %}
"""

template2 = Template(template_string2)
context2 = Context({'country': 'US'})
output2 = template2.render(context2)

print("Badge output:")
print(output2)