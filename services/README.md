# Scrape.do Service Documentation

## Overview
The `ScrapeDoService` is a Django service wrapper for the [Scrape.do](https://scrape.do/documentation/) web scraping API. It provides a clean, reusable interface for web scraping with proper URL encoding, caching, retry logic, and support for various scraping options.

## Installation & Configuration

### 1. Environment Setup
Add your Scrape.do API key to your `.env` file:
```bash
SCRAPPER_API_KEY=your_api_key_here
```

### 2. Django Settings
The API key is automatically loaded from environment variables in `settings.py`:
```python
SCRAPPER_API_KEY = os.getenv('SCRAPPER_API_KEY')
```

## Usage Examples

### Basic Usage

```python
from services import ScrapeDoService

# Initialize the service
scraper = ScrapeDoService()  # Uses API key from settings

# Or with a custom API key
scraper = ScrapeDoService(api_key='custom_api_key')

# Simple scraping
result = scraper.scrape('https://example.com')

if result['success']:
    html_content = result['html']
    status_code = result['status_code']
    headers = result['headers']
```

### Using Singleton Pattern

```python
from services.scrape_do import get_scraper

# Get singleton instance
scraper = get_scraper()

# Use it anywhere in your app
result = scraper.scrape('https://example.com')
```

### Scraping with Country-Specific Location

```python
# Scrape as if from the United States
result = scraper.scrape(
    'https://example.com',
    country_code='us'  # Options: 'us', 'uk', 'de', 'fr', etc.
)

# Scrape as if from Germany
result = scraper.scrape(
    'https://example.com',
    country_code='de'
)
```

### JavaScript Rendering

```python
# Render JavaScript content
result = scraper.scrape(
    'https://example.com',
    render=True,  # Enable JS rendering
    wait_for=3000,  # Wait 3 seconds for JS to load
    block_resources=True  # Block images/CSS for faster loading
)
```

### Custom Headers

```python
# Add custom headers to the request
result = scraper.scrape(
    'https://example.com',
    custom_headers={
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://google.com',
        'X-Custom-Header': 'CustomValue'
    }
)
```

### Handling Special Characters in URLs

The service automatically handles URLs with special characters:

```python
# URLs with query parameters and special characters
urls_with_special = [
    'https://example.com/search?q=hello world&sort=price',
    'https://example.com/products?filter=price>100&category=electronics',
    'https://example.com/search?query=café+münchen',
    'https://api.example.com/data?param=value with spaces'
]

for url in urls_with_special:
    result = scraper.scrape(url)  # Automatically handled
```

### Batch Scraping

```python
# Scrape multiple URLs
urls = [
    'https://example1.com',
    'https://example2.com',
    'https://example3.com'
]

results = scraper.scrape_batch(urls, country_code='us')

for url, result in results.items():
    if result['success']:
        print(f"Successfully scraped {url}")
```

### Retry on Failure

```python
# Automatically retry failed requests
result = scraper.scrape_with_retry(
    'https://unreliable-site.com',
    max_retries=3  # Try up to 3 times
)
```

### Google Search Scraping

```python
# Basic Google search
search_results = scraper.scrape_google_search(
    query='Django web scraping tutorial',
    country_code='us',  # Proxy location for Scrape.do
    num_results=100     # Get up to 100 results (default)
)

# Advanced Google search with location and language
search_results = scraper.scrape_google_search(
    query='restaurants near me',
    gl='us',            # Google country for results (USA)
    hl='en',            # Interface language (English)
    num_results=100,    # Number of results
    safe='moderate'     # Safe search setting
)

# Search with exact location using UULE
search_results = scraper.scrape_google_search(
    query='pizza delivery',
    location='New York,New York,United States',
    use_exact_location=True,  # Enables UULE encoding
    gl='us',
    hl='en'
)

# Search in German from Germany
search_results = scraper.scrape_google_search(
    query='python programmierung',
    gl='de',            # German results
    hl='de',            # German interface
    country_code='de'   # German proxy
)

# Paginated search results
page2_results = scraper.scrape_google_search(
    query='machine learning',
    start=100,          # Start from result 100
    num_results=100     # Get next 100 results
)

# Scrape multiple pages at once
all_pages = scraper.scrape_google_search_pages(
    query='data science jobs',
    pages=3,                  # Get 3 pages
    results_per_page=100,     # 100 results per page
    gl='us',
    hl='en'
)
```

#### Google Search Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `query` | str | Search query (required) | `'python django'` |
| `country_code` | str | Scrape.do proxy location | `'us'`, `'uk'`, `'de'` |
| `num_results` | int | Number of results (default: 100) | `10`, `50`, `100` |
| `gl` | str | Google country for results | `'us'`, `'uk'`, `'de'` |
| `hl` | str | Interface language | `'en'`, `'es'`, `'fr'` |
| `location` | str | Location for UULE encoding | `'New York,New York,United States'` |
| `use_exact_location` | bool | Enable UULE location | `True`, `False` |
| `safe` | str | Safe search setting | `'active'`, `'moderate'`, `'off'` |
| `start` | int | Starting position for pagination | `0`, `100`, `200` |

#### UULE Location Encoding

The UULE parameter allows precise location targeting for Google searches:

```python
# Encode a location to UULE format
uule = scraper.encode_uule("New York,New York,United States")
# Returns: w+CAIQICI...

# Use in search
results = scraper.scrape_google_search(
    "coffee shops",
    location="San Francisco,California,United States",
    use_exact_location=True
)
```

Common location formats:
- `"City,State,Country"` - e.g., `"Austin,Texas,United States"`
- `"City,Country"` - e.g., `"London,United Kingdom"`
- `"City,Province,Country"` - e.g., `"Toronto,Ontario,Canada"`

### Caching

```python
# Enable caching (default behavior)
result = scraper.scrape('https://example.com', use_cache=True)

# Disable caching for fresh data
result = scraper.scrape('https://example.com', use_cache=False)

# Clear cache for a specific URL
scraper.clear_cache('https://example.com')
```

### API Usage Statistics

```python
# Get your API usage stats
usage = scraper.get_usage()
if usage:
    print(f"Requests made: {usage.get('requests_made')}")
    print(f"Requests limit: {usage.get('requests_limit')}")
```

## Integration in Django Views

### Example View

```python
from django.http import JsonResponse
from django.views import View
from services.scrape_do import get_scraper

class ScrapeView(View):
    def get(self, request):
        url = request.GET.get('url')
        country = request.GET.get('country', 'us')
        
        if not url:
            return JsonResponse({'error': 'URL parameter required'}, status=400)
        
        scraper = get_scraper()
        result = scraper.scrape(url, country_code=country)
        
        if result['success']:
            return JsonResponse({
                'html': result['html'],
                'status': result['status_code']
            })
        else:
            return JsonResponse({
                'error': result.get('error', 'Scraping failed')
            }, status=500)
```

### Example in Django Management Command

```python
from django.core.management.base import BaseCommand
from services.scrape_do import get_scraper

class Command(BaseCommand):
    help = 'Scrape competitor prices'
    
    def add_arguments(self, parser):
        parser.add_argument('urls', nargs='+', type=str)
    
    def handle(self, *args, **options):
        scraper = get_scraper()
        
        for url in options['urls']:
            self.stdout.write(f'Scraping {url}...')
            
            result = scraper.scrape_with_retry(url, max_retries=3)
            
            if result and result['success']:
                # Process the HTML content
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully scraped {url}')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'Failed to scrape {url}')
                )
```

### Example in Celery Task

```python
from celery import shared_task
from services.scrape_do import get_scraper

@shared_task
def scrape_website_task(url, country_code='us'):
    """Async task to scrape a website"""
    scraper = get_scraper()
    
    result = scraper.scrape(
        url,
        country_code=country_code,
        render=True,
        wait_for=2000
    )
    
    if result['success']:
        # Store in database or process further
        return {
            'status': 'success',
            'url': url,
            'content_length': len(result['html'])
        }
    else:
        return {
            'status': 'failed',
            'url': url,
            'error': result.get('error')
        }
```

## Response Format

All scraping methods return a dictionary with the following structure:

### Success Response
```python
{
    'html': '<html>...</html>',  # The scraped HTML content
    'status_code': 200,           # HTTP status code
    'headers': {...},             # Response headers
    'url': 'https://...',        # Final URL after redirects
    'success': True               # Success flag
}
```

### Error Response
```python
{
    'html': None,
    'status_code': 403,           # HTTP error code (if applicable)
    'error': 'Error message',     # Error description
    'success': False              # Success flag
}
```

## Best Practices

1. **Use Caching**: Enable caching for frequently accessed pages to reduce API calls
2. **Handle Errors**: Always check the `success` flag before processing results
3. **Respect Rate Limits**: Use the `get_usage()` method to monitor your API usage
4. **Use Country Codes**: Specify country codes for geo-specific content
5. **Batch Processing**: Use `scrape_batch()` for multiple URLs
6. **Retry Logic**: Use `scrape_with_retry()` for unreliable sites

## Testing

Run the tests:
```bash
python manage.py test services.tests
```

## Troubleshooting

### Common Issues

1. **API Key Not Found**
   ```python
   # Check if API key is loaded
   from django.conf import settings
   print(settings.SCRAPPER_API_KEY)
   ```

2. **Special Characters in URLs**
   - The service handles encoding automatically
   - Pass URLs as regular strings

3. **Timeout Issues**
   - Default timeout is 30 seconds
   - For slow sites, use JS rendering with appropriate wait time

4. **Cache Issues**
   - Clear cache if getting stale data: `scraper.clear_cache(url)`

## API Parameters Reference

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | str | The URL to scrape (required) |
| `country_code` | str | Country code for geo-location (e.g., 'us', 'uk') |
| `render` | bool | Enable JavaScript rendering |
| `wait_for` | int | Wait time in milliseconds for JS |
| `block_resources` | bool | Block images/CSS for faster scraping |
| `custom_headers` | dict | Additional HTTP headers |
| `use_cache` | bool | Use cached results (default: True) |

## Support

For Scrape.do API documentation: https://scrape.do/documentation/