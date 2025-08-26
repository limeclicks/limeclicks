import logging
from typing import Dict, Any, Optional, List
from django.http import JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import QuerySet
from functools import wraps
import time


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with consistent configuration"""
    return logging.getLogger(name)


def create_ajax_response(success: bool, message: str = '', data: Optional[Dict] = None) -> JsonResponse:
    """
    Create a standardized AJAX response
    
    Args:
        success: Whether the operation was successful
        message: Optional message to include
        data: Optional data dictionary to include
    
    Returns:
        JsonResponse with standardized format
    """
    response_data = {
        'success': success,
        'message': message
    }
    
    if data is not None:
        response_data['data'] = data
    
    return JsonResponse(response_data)


def paginate_queryset(queryset: QuerySet, page: int = 1, per_page: int = 25) -> Dict[str, Any]:
    """
    Paginate a queryset and return pagination metadata
    
    Args:
        queryset: The queryset to paginate
        page: Page number (1-indexed)
        per_page: Number of items per page
    
    Returns:
        Dictionary with paginated results and metadata
    """
    paginator = Paginator(queryset, per_page)
    
    try:
        paginated = paginator.page(page)
    except PageNotAnInteger:
        paginated = paginator.page(1)
    except EmptyPage:
        paginated = paginator.page(paginator.num_pages)
    
    return {
        'results': list(paginated.object_list),
        'page': paginated.number,
        'per_page': per_page,
        'total_pages': paginator.num_pages,
        'total_items': paginator.count,
        'has_next': paginated.has_next(),
        'has_previous': paginated.has_previous(),
        'next_page': paginated.next_page_number() if paginated.has_next() else None,
        'previous_page': paginated.previous_page_number() if paginated.has_previous() else None
    }


def chunk_list(items: List, chunk_size: int = 100):
    """
    Split a list into chunks of specified size
    
    Args:
        items: List to chunk
        chunk_size: Size of each chunk
    
    Yields:
        Chunks of the list
    """
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]


def safe_get(dictionary: Dict, *keys, default=None):
    """
    Safely get a nested value from a dictionary
    
    Args:
        dictionary: The dictionary to search
        *keys: Keys to traverse
        default: Default value if key not found
    
    Returns:
        The value or default
    """
    for key in keys:
        try:
            dictionary = dictionary[key]
        except (KeyError, TypeError, AttributeError):
            return default
    return dictionary


def format_duration(seconds: Optional[float]) -> str:
    """
    Format duration in seconds to human-readable string
    
    Args:
        seconds: Duration in seconds
    
    Returns:
        Formatted string (e.g., "2h 30m", "45s", "3d 2h")
    """
    if seconds is None:
        return '-'
    
    seconds = int(seconds)
    
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s" if secs else f"{minutes}m"
    elif seconds < 86400:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h {mins}m" if mins else f"{hours}h"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}d {hours}h" if hours else f"{days}d"


def format_bytes(bytes_value: int) -> str:
    """
    Format bytes to human-readable string
    
    Args:
        bytes_value: Number of bytes
    
    Returns:
        Formatted string (e.g., "1.5 MB", "823 KB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def timing_decorator(func):
    """
    Decorator to measure and log function execution time
    
    Usage:
        @timing_decorator
        def my_function():
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        duration = end_time - start_time
        logger = get_logger(func.__module__)
        logger.info(f"{func.__name__} took {duration:.3f} seconds")
        
        return result
    return wrapper


def batch_process(items: List, process_func, batch_size: int = 100, logger=None):
    """
    Process items in batches with progress logging
    
    Args:
        items: List of items to process
        process_func: Function to process each batch
        batch_size: Size of each batch
        logger: Optional logger instance
    
    Returns:
        List of results from each batch
    """
    if not logger:
        logger = get_logger(__name__)
    
    results = []
    total = len(items)
    processed = 0
    
    for batch in chunk_list(items, batch_size):
        try:
            result = process_func(batch)
            results.append(result)
            processed += len(batch)
            logger.info(f"Processed {processed}/{total} items ({processed*100//total}%)")
        except Exception as e:
            logger.error(f"Error processing batch: {str(e)}")
            results.append(None)
    
    return results


def normalize_domain(domain: str) -> str:
    """
    Normalize a domain name by removing protocol, www, and trailing slashes
    
    Args:
        domain: Domain to normalize
    
    Returns:
        Normalized domain
    """
    import re
    
    # Convert to lowercase first
    domain = domain.lower()
    
    # Remove protocol
    domain = re.sub(r'^https?://', '', domain)
    
    # Remove www
    domain = re.sub(r'^www\.', '', domain, flags=re.IGNORECASE)
    
    # Remove trailing slash
    domain = domain.rstrip('/')
    
    # Remove port if present
    domain = re.sub(r':\d+$', '', domain)
    
    return domain


def is_valid_email(email: str) -> bool:
    """
    Validate email address format
    
    Args:
        email: Email address to validate
    
    Returns:
        True if valid, False otherwise
    """
    import re
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def generate_unique_filename(original_filename: str, prefix: str = '') -> str:
    """
    Generate a unique filename with timestamp
    
    Args:
        original_filename: Original filename
        prefix: Optional prefix to add
    
    Returns:
        Unique filename
    """
    import os
    from datetime import datetime
    
    name, ext = os.path.splitext(original_filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if prefix:
        return f"{prefix}_{name}_{timestamp}{ext}"
    return f"{name}_{timestamp}{ext}"