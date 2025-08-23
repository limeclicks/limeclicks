from django import forms
from .models import Project
import re


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['domain', 'title', 'active']
        widgets = {
            'domain': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'domain.com',
                'required': True
            }),
            'title': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Auto-generated if left blank'
            }),
            'active': forms.CheckboxInput(attrs={
                'class': 'checkbox'
            })
        }
    
    def clean_domain(self):
        domain = self.cleaned_data.get('domain')
        if domain:
            # Remove http:// or https:// if present
            domain = domain.lower().strip()
            domain = re.sub(r'^https?://', '', domain)
            
            # Remove trailing slash if present
            domain = domain.rstrip('/')
            
            # Remove www. prefix if present
            domain = re.sub(r'^www\.', '', domain)
            
            # Validate domain format - must have at least one dot for proper domain/subdomain
            # Reject localhost and single words
            if '.' not in domain:
                raise forms.ValidationError('Please enter a valid domain or subdomain name (must contain at least one dot).')
            
            # Check for invalid characters
            if not re.match(r'^[a-zA-Z0-9.-]+$', domain):
                raise forms.ValidationError('Domain name contains invalid characters. Only letters, numbers, dots, and hyphens are allowed.')
            
            # Validate proper domain format
            domain_pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
            if not re.match(domain_pattern, domain):
                raise forms.ValidationError('Please enter a valid domain or subdomain name.')
            
            # Additional validations
            if domain.startswith('.') or domain.endswith('.'):
                raise forms.ValidationError('Domain cannot start or end with a dot.')
            
            if '..' in domain:
                raise forms.ValidationError('Domain cannot contain consecutive dots.')
            
            if domain.startswith('-') or domain.endswith('-'):
                raise forms.ValidationError('Domain cannot start or end with a hyphen.')
            
            return domain
        return domain