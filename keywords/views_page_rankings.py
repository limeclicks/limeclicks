"""
Views for Page Rankings - showing which pages rank for how many keywords
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.db.models import Q, Count, Avg, F, Value, CharField
from django.db.models.functions import Concat
from django.core.paginator import Paginator
from .models import Keyword, Rank
from project.models import Project
from urllib.parse import urlparse
import json


@method_decorator(login_required, name='dispatch')
class PageRankingsView(TemplateView):
    """Main view for page rankings analysis"""
    template_name = 'keywords/page_rankings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get user's projects for filter
        user_projects = Project.objects.filter(
            Q(user=self.request.user) | 
            Q(members=self.request.user)
        ).distinct()
        
        context['projects'] = user_projects
        context['selected_project_id'] = self.request.GET.get('project')
        
        return context


@login_required
def page_rankings_data(request):
    """HTMX endpoint for page rankings data with pagination and filtering"""
    
    # Get filter parameters
    project_id = request.GET.get('project', '')
    search_query = request.GET.get('search', '')
    page = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 50))
    
    # Base queryset - get all keywords user has access to
    keywords = Keyword.objects.filter(
        Q(project__user=request.user) |
        Q(project__members=request.user)
    ).filter(
        archive=False,
        rank__gt=0,
        rank__lte=100
    ).select_related('project').distinct()
    
    # Apply project filter
    if project_id:
        keywords = keywords.filter(project_id=project_id)
    
    # Apply search filter
    if search_query:
        keywords = keywords.filter(
            Q(rank_url__icontains=search_query) |
            Q(keyword__icontains=search_query)
        )
    
    # Group by page URL and get counts
    page_data = {}
    for keyword in keywords:
        if keyword.rank_url:
            # Clean up the URL for grouping
            page_url = keyword.rank_url.strip()
            
            if page_url not in page_data:
                page_data[page_url] = {
                    'url': page_url,
                    'project': keyword.project.domain,
                    'project_id': keyword.project.id,
                    'keywords': [],
                    'total_keywords': 0,
                    'avg_position': 0,
                    'avg_cpc': 0,
                    'total_traffic': 0,
                    'best_keyword': None,
                    'best_position': 101
                }
            
            # Add keyword details
            page_data[page_url]['keywords'].append({
                'id': keyword.id,
                'keyword': keyword.keyword,
                'rank': keyword.rank,
                'rank_diff': keyword.rank_diff_from_last_time,
                'cpc': 0,  # CPC field doesn't exist in current model
                'search_volume': 0,  # search_volume field doesn't exist in current model
                'traffic': 0,  # traffic field doesn't exist in current model
                'country': keyword.country
            })
            
            page_data[page_url]['total_keywords'] += 1
            page_data[page_url]['total_traffic'] += 0  # traffic field doesn't exist
            
            # Track best ranking keyword
            if keyword.rank < page_data[page_url]['best_position']:
                page_data[page_url]['best_position'] = keyword.rank
                page_data[page_url]['best_keyword'] = keyword.keyword
    
    # Calculate averages
    for url, data in page_data.items():
        if data['keywords']:
            data['avg_position'] = round(
                sum(k['rank'] for k in data['keywords']) / len(data['keywords']), 1
            )
            data['avg_cpc'] = 0  # CPC not available in current model
    
    # Convert to list and sort by total keywords
    pages_list = list(page_data.values())
    pages_list.sort(key=lambda x: x['total_keywords'], reverse=True)
    
    # Paginate
    paginator = Paginator(pages_list, per_page)
    
    try:
        pages = paginator.page(page)
    except:
        pages = paginator.page(1)
    
    # Format response
    pages_data = []
    total_keywords_sum = 0
    position_sum = 0
    
    for page_item in pages:
        # Extract page title from URL (last part)
        url_parts = page_item['url'].rstrip('/').split('/')
        page_title = url_parts[-1] if url_parts else 'Homepage'
        if page_title:
            # Clean up the title
            page_title = page_title.replace('-', ' ').replace('_', ' ').title()
        else:
            page_title = 'Homepage'
        
        pages_data.append({
            'url': page_item['url'],
            'page_title': page_title,
            'project': page_item['project'],
            'project_id': page_item['project_id'],
            'total_keywords': page_item['total_keywords'],
            'avg_position': page_item['avg_position'],
            'avg_cpc': page_item['avg_cpc'],
            'total_traffic': page_item['total_traffic'],
            'best_keyword': page_item['best_keyword'],
            'best_position': page_item['best_position']
        })
        
        # Calculate totals for metrics
        total_keywords_sum += page_item['total_keywords']
        position_sum += page_item['avg_position']
    
    # Calculate overall metrics
    avg_position = round(position_sum / len(pages_data), 1) if pages_data else 0
    
    # Format numbers for display
    def format_number(num):
        if num >= 1000000:
            return f"{num/1000000:.1f}M"
        elif num >= 1000:
            return f"{num/1000:.1f}K"
        return str(int(num))
    
    # Prepare pagination info
    # Generate elided page range (with ellipsis)
    page_range = []
    for page_num in paginator.get_elided_page_range(pages.number, on_each_side=2, on_ends=1):
        # Check if it's an ellipsis (not an integer)
        if not isinstance(page_num, int):
            page_range.append('...')
        else:
            page_range.append(page_num)
    
    pagination = {
        'current_page': pages.number,
        'total_pages': paginator.num_pages,
        'total_items': paginator.count,
        'per_page': per_page,
        'has_next': pages.has_next(),
        'has_previous': pages.has_previous(),
        'next_page': pages.next_page_number() if pages.has_next() else None,
        'previous_page': pages.previous_page_number() if pages.has_previous() else None,
        'page_range': page_range
    }
    
    context = {
        'pages': pages_data,
        'pagination': pagination,
        'total_pages': len(pages_data),
        'total_keywords': format_number(total_keywords_sum),
        'avg_position': avg_position,
        'request': request
    }
    
    return render(request, 'keywords/partials/page_rankings_list.html', context)


@login_required  
def page_keywords_detail(request):
    """HTMX endpoint for detailed keywords of a specific page"""
    
    page_url = request.GET.get('url', '')
    project_id = request.GET.get('project_id', '')
    
    if not page_url:
        return render(request, 'keywords/partials/page_keywords_detail.html', {
            'keywords': [],
            'error': 'URL parameter required'
        })
    
    # Get all keywords for this page
    keywords = Keyword.objects.filter(
        Q(project__user=request.user) |
        Q(project__members=request.user)
    ).filter(
        rank_url=page_url,
        archive=False,
        rank__gt=0,
        rank__lte=100
    ).select_related('project')
    
    if project_id:
        keywords = keywords.filter(project_id=project_id)
    
    # Order by rank
    keywords = keywords.order_by('rank')
    
    # Format keyword data
    keywords_data = []
    for keyword in keywords:
        # Determine rank change icon
        if keyword.rank_diff_from_last_time > 0:
            rank_change = f"↓ {keyword.rank_diff_from_last_time}"
            rank_change_class = "negative"
        elif keyword.rank_diff_from_last_time < 0:
            rank_change = f"↑ {abs(keyword.rank_diff_from_last_time)}"
            rank_change_class = "positive"
        else:
            rank_change = "-"
            rank_change_class = "neutral"
        
        keywords_data.append({
            'id': keyword.id,
            'keyword': keyword.keyword,
            'rank': keyword.rank,
            'rank_change': rank_change,
            'rank_change_class': rank_change_class,
            'search_engine': 'Google',  # Assuming Google for now
            'country': keyword.country.upper() if keyword.country else 'US',
            'search_volume': 0,  # search_volume field doesn't exist in current model
            'cpc': 0,  # CPC not available in current model
            'traffic': 0  # traffic field doesn't exist in current model
        })
    
    # Extract page title
    url_parts = page_url.rstrip('/').split('/')
    page_title = url_parts[-1] if url_parts else 'Homepage'
    if page_title:
        page_title = page_title.replace('-', ' ').replace('_', ' ').title()
    else:
        page_title = 'Homepage'
    
    context = {
        'page_url': page_url,
        'page_title': page_title,
        'total_keywords': len(keywords_data),
        'keywords': keywords_data
    }
    
    return render(request, 'keywords/partials/page_keywords_detail.html', context)