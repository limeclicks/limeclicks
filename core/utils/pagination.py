"""
Pagination utilities
Centralized pagination helpers and mixins for views
"""

from typing import Dict, Any, Optional, Union
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import QuerySet
from django.http import HttpRequest
from django.shortcuts import render


def paginate_queryset(
    queryset: QuerySet,
    page: Union[int, str] = 1,
    per_page: int = 25,
    allow_empty_first_page: bool = True
) -> Paginator.page:
    """
    Paginate a queryset and return the page object.
    
    Args:
        queryset: The queryset to paginate
        page: Page number (1-indexed) or page string from request
        per_page: Number of items per page
        allow_empty_first_page: Whether to allow empty first page
        
    Returns:
        Page object with paginated results
        
    Example:
        page_obj = paginate_queryset(Keyword.objects.all(), request.GET.get('page'), 25)
    """
    paginator = Paginator(queryset, per_page, allow_empty_first_page=allow_empty_first_page)
    
    try:
        # Convert to int if string
        if isinstance(page, str):
            page = int(page) if page else 1
        page_obj = paginator.page(page)
    except (PageNotAnInteger, ValueError, TypeError):
        # If page is not an integer or invalid, deliver first page
        page_obj = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page of results
        page_obj = paginator.page(paginator.num_pages)
    
    return page_obj


def get_paginated_response(
    queryset: QuerySet,
    page: Union[int, str] = 1,
    per_page: int = 25,
    serializer_func: Optional[callable] = None
) -> Dict[str, Any]:
    """
    Get paginated response as a dictionary.
    Useful for API responses.
    
    Args:
        queryset: The queryset to paginate
        page: Page number
        per_page: Items per page
        serializer_func: Optional function to serialize each object
        
    Returns:
        Dictionary with pagination metadata and results
    """
    page_obj = paginate_queryset(queryset, page, per_page)
    
    # Serialize results if function provided
    if serializer_func:
        results = [serializer_func(obj) for obj in page_obj.object_list]
    else:
        results = list(page_obj.object_list.values()) if hasattr(page_obj.object_list, 'values') else list(page_obj.object_list)
    
    return {
        'results': results,
        'page': page_obj.number,
        'per_page': per_page,
        'total_pages': page_obj.paginator.num_pages,
        'total_items': page_obj.paginator.count,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
        'previous_page': page_obj.previous_page_number() if page_obj.has_previous() else None,
    }


class PaginationMixin:
    """
    Mixin for Django views to add pagination support.
    
    Usage in Class-Based Views:
        class MyListView(PaginationMixin, ListView):
            paginate_by = 25
            
    Usage in function views:
        Call get_paginated_context() to get pagination context
    """
    
    paginate_by = 25  # Default items per page
    page_kwarg = 'page'  # URL parameter for page number
    
    def get_paginate_by(self, queryset=None):
        """
        Get the number of items to paginate by.
        Can be overridden to provide dynamic pagination.
        """
        return self.paginate_by
    
    def get_page_number(self, request: HttpRequest) -> int:
        """
        Get the current page number from request.
        
        Args:
            request: HTTP request object
            
        Returns:
            Page number (defaults to 1)
        """
        page = request.GET.get(self.page_kwarg, 1)
        try:
            return int(page)
        except (TypeError, ValueError):
            return 1
    
    def paginate_queryset_mixin(self, queryset: QuerySet, request: HttpRequest):
        """
        Paginate a queryset for use in views.
        
        Args:
            queryset: Queryset to paginate
            request: HTTP request object
            
        Returns:
            Tuple of (paginator, page_obj, object_list, is_paginated)
        """
        page = self.get_page_number(request)
        per_page = self.get_paginate_by(queryset)
        
        if not per_page:
            return None, None, queryset, False
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginate_queryset(queryset, page, per_page)
        
        return paginator, page_obj, page_obj.object_list, True
    
    def get_paginated_context(
        self,
        queryset: QuerySet,
        request: HttpRequest,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Get context dict with pagination data.
        
        Args:
            queryset: Queryset to paginate
            request: HTTP request
            context: Existing context to update
            
        Returns:
            Context dictionary with pagination data
        """
        if context is None:
            context = {}
        
        page = self.get_page_number(request)
        per_page = self.get_paginate_by(queryset)
        
        page_obj = paginate_queryset(queryset, page, per_page)
        
        context.update({
            'paginator': page_obj.paginator,
            'page_obj': page_obj,
            'object_list': page_obj.object_list,
            'is_paginated': page_obj.paginator.num_pages > 1,
            'page_range': page_obj.paginator.page_range,
        })
        
        return context


def simple_paginate(request: HttpRequest, queryset: QuerySet, per_page: int = 25) -> Dict[str, Any]:
    """
    Simple pagination helper for function-based views.
    
    Args:
        request: HTTP request
        queryset: Queryset to paginate
        per_page: Items per page
        
    Returns:
        Context dict with page_obj and is_paginated
        
    Example:
        def my_view(request):
            keywords = Keyword.objects.all()
            context = simple_paginate(request, keywords, 25)
            return render(request, 'template.html', context)
    """
    page = request.GET.get('page', 1)
    page_obj = paginate_queryset(queryset, page, per_page)
    
    return {
        'page_obj': page_obj,
        'object_list': page_obj.object_list,
        'is_paginated': page_obj.paginator.num_pages > 1,
        'paginator': page_obj.paginator,
    }