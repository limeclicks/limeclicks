from django import template

register = template.Library()

# Dictionary mapping country codes to Google domains
GOOGLE_DOMAINS = {
    'US': 'google.com',
    'GB': 'google.co.uk',
    'UK': 'google.co.uk',
    'CA': 'google.ca',
    'AU': 'google.com.au',
    'NZ': 'google.co.nz',
    'IE': 'google.ie',
    'ZA': 'google.co.za',
    
    # European countries
    'DE': 'google.de',
    'FR': 'google.fr',
    'ES': 'google.es',
    'IT': 'google.it',
    'NL': 'google.nl',
    'BE': 'google.be',
    'CH': 'google.ch',
    'AT': 'google.at',
    'SE': 'google.se',
    'NO': 'google.no',
    'DK': 'google.dk',
    'FI': 'google.fi',
    'PL': 'google.pl',
    'PT': 'google.pt',
    'GR': 'google.gr',
    'CZ': 'google.cz',
    'HU': 'google.hu',
    'RO': 'google.ro',
    'UA': 'google.com.ua',
    'RU': 'google.ru',
    'TR': 'google.com.tr',
    
    # Asian countries
    'IN': 'google.co.in',
    'CN': 'google.cn',
    'JP': 'google.co.jp',
    'KR': 'google.co.kr',
    'SG': 'google.com.sg',
    'HK': 'google.com.hk',
    'MY': 'google.com.my',
    'TH': 'google.co.th',
    'ID': 'google.co.id',
    'PH': 'google.com.ph',
    'VN': 'google.com.vn',
    'PK': 'google.com.pk',
    'BD': 'google.com.bd',
    
    # Middle East
    'AE': 'google.ae',
    'SA': 'google.com.sa',
    'IL': 'google.co.il',
    'EG': 'google.com.eg',
    
    # Americas
    'BR': 'google.com.br',
    'MX': 'google.com.mx',
    'AR': 'google.com.ar',
    'CL': 'google.cl',
    'CO': 'google.com.co',
    'PE': 'google.com.pe',
    'VE': 'google.co.ve',
    
    # Africa
    'NG': 'google.com.ng',
    'KE': 'google.co.ke',
}

# Dictionary mapping country codes to flag emojis
COUNTRY_FLAGS = {
    'US': '🇺🇸',  # United States
    'GB': '🇬🇧',  # Great Britain
    'UK': '🇬🇧',  # United Kingdom (alias)
    'CA': '🇨🇦',  # Canada
    'AU': '🇦🇺',  # Australia
    'NZ': '🇳🇿',  # New Zealand
    'IE': '🇮🇪',  # Ireland
    'ZA': '🇿🇦',  # South Africa
    
    # European countries
    'DE': '🇩🇪',  # Germany
    'FR': '🇫🇷',  # France
    'ES': '🇪🇸',  # Spain
    'IT': '🇮🇹',  # Italy
    'NL': '🇳🇱',  # Netherlands
    'BE': '🇧🇪',  # Belgium
    'CH': '🇨🇭',  # Switzerland
    'AT': '🇦🇹',  # Austria
    'SE': '🇸🇪',  # Sweden
    'NO': '🇳🇴',  # Norway
    'DK': '🇩🇰',  # Denmark
    'FI': '🇫🇮',  # Finland
    'PL': '🇵🇱',  # Poland
    'PT': '🇵🇹',  # Portugal
    'GR': '🇬🇷',  # Greece
    'CZ': '🇨🇿',  # Czech Republic
    'HU': '🇭🇺',  # Hungary
    'RO': '🇷🇴',  # Romania
    'UA': '🇺🇦',  # Ukraine
    'RU': '🇷🇺',  # Russia
    'TR': '🇹🇷',  # Turkey
    
    # Asian countries
    'IN': '🇮🇳',  # India
    'CN': '🇨🇳',  # China
    'JP': '🇯🇵',  # Japan
    'KR': '🇰🇷',  # South Korea
    'SG': '🇸🇬',  # Singapore
    'HK': '🇭🇰',  # Hong Kong
    'MY': '🇲🇾',  # Malaysia
    'TH': '🇹🇭',  # Thailand
    'ID': '🇮🇩',  # Indonesia
    'PH': '🇵🇭',  # Philippines
    'VN': '🇻🇳',  # Vietnam
    'PK': '🇵🇰',  # Pakistan
    'BD': '🇧🇩',  # Bangladesh
    
    # Middle East
    'AE': '🇦🇪',  # United Arab Emirates
    'SA': '🇸🇦',  # Saudi Arabia
    'IL': '🇮🇱',  # Israel
    'EG': '🇪🇬',  # Egypt
    
    # Americas
    'BR': '🇧🇷',  # Brazil
    'MX': '🇲🇽',  # Mexico
    'AR': '🇦🇷',  # Argentina
    'CL': '🇨🇱',  # Chile
    'CO': '🇨🇴',  # Colombia
    'PE': '🇵🇪',  # Peru
    'VE': '🇻🇪',  # Venezuela
    
    # Africa
    'NG': '🇳🇬',  # Nigeria
    'KE': '🇰🇪',  # Kenya
}

# Default flag for unknown countries
DEFAULT_FLAG = '🌍'


@register.filter
def google_domain(country_code):
    """
    Returns the Google domain for a given country code.
    
    Usage in template:
        {{ keyword.country|google_domain }}
    """
    if not country_code:
        return 'google.com'
    
    # Convert to uppercase and strip whitespace
    country_code = str(country_code).upper().strip()
    
    # Return the Google domain or default
    return GOOGLE_DOMAINS.get(country_code, 'google.com')


@register.filter
def country_flag(country_code):
    """
    Returns the flag emoji for a given country code.
    
    Usage in template:
        {{ keyword.country|country_flag }}
    """
    if not country_code:
        return DEFAULT_FLAG
    
    # Convert to uppercase and strip whitespace
    country_code = str(country_code).upper().strip()
    
    # Return the flag emoji or default
    return COUNTRY_FLAGS.get(country_code, DEFAULT_FLAG)


@register.filter
def country_with_flag(country_code):
    """
    Returns the country code with its flag emoji.
    
    Usage in template:
        {{ keyword.country|country_with_flag }}
    """
    if not country_code:
        return DEFAULT_FLAG
    
    flag = country_flag(country_code)
    return f"{flag} {country_code}"


@register.inclusion_tag('keywords/partials/country_badge.html')
def country_badge(country_code, css_class="badge badge-ghost"):
    """
    Renders a badge with country flag and code.
    
    Usage in template:
        {% country_badge keyword.country %}
        {% country_badge keyword.country "badge badge-primary" %}
    """
    return {
        'country_code': country_code,
        'flag': country_flag(country_code),
        'google_domain': google_domain(country_code),
        'css_class': css_class
    }