"""
Domain utilities
Centralized domain cleaning and validation functions
"""

import re
from typing import Optional
from urllib.parse import urlparse


def clean_domain_string(domain: Optional[str]) -> str:
    """
    Clean a domain string - remove protocol, www, path, etc.
    This is the comprehensive version used throughout the application.
    
    Args:
        domain: Domain string to clean
        
    Returns:
        Cleaned domain string
        
    Examples:
        >>> clean_domain_string('https://www.example.com/path?query=1')
        'example.com'
        >>> clean_domain_string('WWW.EXAMPLE.COM:8080')
        'example.com'
    """
    if not domain:
        return domain or ''
        
    domain = str(domain).strip().lower()
    
    # Remove protocol (http://, https://, ftp://, etc.)
    if '://' in domain:
        domain = domain.split('://')[-1]
    
    # Remove www. prefix (case insensitive, already lowered)
    if domain.startswith('www.'):
        domain = domain[4:]
    
    # Remove everything after the domain (path, query string, hash)
    domain = domain.split('/')[0]
    domain = domain.split('?')[0]
    domain = domain.split('#')[0]
    
    # Remove port if present (but not for IPv6 addresses)
    if ':' in domain and '[' not in domain:
        domain = domain.split(':')[0]
    
    # Remove trailing dots
    domain = domain.rstrip('.')
    
    # Remove any remaining whitespace
    domain = domain.strip()
    
    return domain


def normalize_domain(domain: str) -> str:
    """
    Normalize a domain name for comparison.
    Similar to clean_domain_string but less aggressive.
    
    Args:
        domain: Domain to normalize
        
    Returns:
        Normalized domain
        
    Examples:
        >>> normalize_domain('HTTPS://Example.com/')
        'example.com'
    """
    if not domain:
        return ''
    
    # Convert to lowercase
    domain = domain.lower().strip()
    
    # Remove protocol using regex
    domain = re.sub(r'^[a-z]+://', '', domain)
    
    # Remove www prefix
    domain = re.sub(r'^www\.', '', domain, flags=re.IGNORECASE)
    
    # Remove trailing slash
    domain = domain.rstrip('/')
    
    # Remove port if present
    domain = re.sub(r':\d+$', '', domain)
    
    return domain


def is_valid_domain(domain: str) -> bool:
    """
    Validate if a string is a valid domain name.
    
    Args:
        domain: Domain string to validate
        
    Returns:
        True if valid domain, False otherwise
        
    Examples:
        >>> is_valid_domain('example.com')
        True
        >>> is_valid_domain('sub.example.co.uk')
        True
        >>> is_valid_domain('not a domain')
        False
    """
    if not domain:
        return False
    
    # Clean the domain first
    domain = clean_domain_string(domain)
    
    # Basic validation pattern
    # Allows subdomains, international domains, and various TLDs
    pattern = re.compile(
        r'^(?:[a-zA-Z0-9]'  # First character of domain
        r'(?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)'  # Subdomain(s)
        r'*[a-zA-Z0-9]'  # First character of main domain
        r'(?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'  # Main domain
        r'(?:\.[a-zA-Z]{2,})+$'  # TLD(s)
    )
    
    # Check basic pattern
    if not pattern.match(domain):
        # Try without subdomain requirement
        simple_pattern = re.compile(
            r'^[a-zA-Z0-9]'
            r'(?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'
            r'(?:\.[a-zA-Z]{2,})+$'
        )
        if not simple_pattern.match(domain):
            return False
    
    # Additional checks
    # - No consecutive dots
    # - No leading or trailing hyphens in labels
    # - Labels can't be longer than 63 characters
    labels = domain.split('.')
    for label in labels:
        if not label or len(label) > 63:
            return False
        if label.startswith('-') or label.endswith('-'):
            return False
        if '--' in label:
            # Some domains have double hyphens (like xn-- for IDN)
            if not label.startswith('xn--'):
                continue  # Allow it
    
    return True


def extract_domain_from_url(url: str) -> str:
    """
    Extract domain from a full URL.
    
    Args:
        url: Full URL
        
    Returns:
        Extracted and cleaned domain
        
    Examples:
        >>> extract_domain_from_url('https://www.example.com/path/to/page')
        'example.com'
    """
    try:
        # Add protocol if missing
        if not url.startswith(('http://', 'https://', 'ftp://')):
            url = 'http://' + url
        
        # Parse URL
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]
        
        # Clean and return
        return clean_domain_string(domain)
    except Exception:
        # Fallback to simple cleaning
        return clean_domain_string(url)


def compare_domains(domain1: str, domain2: str) -> bool:
    """
    Compare two domains for equality after normalization.
    
    Args:
        domain1: First domain
        domain2: Second domain
        
    Returns:
        True if domains are equivalent
        
    Examples:
        >>> compare_domains('https://www.example.com', 'EXAMPLE.COM')
        True
    """
    return clean_domain_string(domain1) == clean_domain_string(domain2)