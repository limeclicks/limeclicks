from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Q, Max, Min, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from .models import Tag, Keyword, KeywordTag
from .crawl_scheduler import CrawlScheduler
from common.utils import create_ajax_response, get_logger
from project.models import Project
import json

logger = get_logger(__name__)


@login_required
def keywords_list(request):
    """Display all projects with keyword statistics for the current user"""
    # Get filter parameters
    search_query = request.GET.get('search', '')
    
    # Get user's projects (owned and shared)
    user_projects = Project.objects.filter(
        Q(user=request.user) | Q(members=request.user)
    ).distinct()
    
    # Apply search filter to projects
    if search_query:
        user_projects = user_projects.filter(
            Q(domain__icontains=search_query) |
            Q(name__icontains=search_query)
        )
    
    # Get projects with keywords for display
    projects_with_keywords = []
    for project in user_projects:
        project_keywords = Keyword.objects.filter(project=project, archive=False)
        keyword_stats = project_keywords.aggregate(
            total_keywords=Count('id'),
            avg_rank=Avg('rank'),
            top10_count=Count('id', filter=Q(rank__lte=10, rank__gt=0)),
            improved_count=Count('id', filter=Q(rank_status='up')),
            declined_count=Count('id', filter=Q(rank_status='down')),
            not_ranking_count=Count('id', filter=Q(rank=0) | Q(rank__gt=100))
        )
        
        # Calculate health score
        total = keyword_stats['total_keywords'] or 0
        if total > 0:
            top10_percent = (keyword_stats['top10_count'] or 0) / total * 100
            if top10_percent >= 50:
                health_status = 'healthy'
            elif top10_percent >= 20:
                health_status = 'attention'
            else:
                health_status = 'critical'
        else:
            health_status = 'new'
        
        projects_with_keywords.append({
            'project': project,
            'stats': keyword_stats,
            'health_status': health_status,
            'recent_keywords': project_keywords.order_by('-created_at')[:5]
        })
    
    # Calculate overall statistics across all projects (owned and shared)
    all_keywords = Keyword.objects.filter(
        Q(project__user=request.user) | Q(project__members=request.user),
        archive=False
    ).distinct()
    total_keywords = all_keywords.count()
    top10_count = all_keywords.filter(rank__lte=10, rank__gt=0).count()
    improved_count = all_keywords.filter(rank_status='up').count()
    declined_count = all_keywords.filter(rank_status='down').count()
    not_ranking_count = all_keywords.filter(Q(rank=0) | Q(rank__gt=100)).count()
    
    # Pagination
    page_number = request.GET.get('page', 1)
    paginator = Paginator(projects_with_keywords, 12)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'projects_with_keywords': page_obj.object_list,
        'search_query': search_query,
        'total_projects': user_projects.count(),
        'total_keywords': total_keywords,
        'top10_count': top10_count,
        'improved_count': improved_count,
        'declined_count': declined_count,
        'not_ranking_count': not_ranking_count,
        'page_obj': page_obj,
        'has_next': page_obj.has_next(),
        'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
    }
    
    # Handle HTMX requests for partial updates
    if request.headers.get('HX-Request'):
        return render(request, 'keywords/partials/keyword_list_items.html', context)
    
    return render(request, 'keywords/list.html', context)


@login_required
def project_keywords(request, project_id):
    """Display all keywords for a specific project"""
    try:
        project = Project.objects.get(
            Q(id=project_id) & 
            (Q(user=request.user) | Q(members=request.user))
        )
    except Project.DoesNotExist:
        return redirect('keywords:list')
    
    # Get filter parameters
    search_query = request.GET.get('search', '')
    filter_status = request.GET.get('filter', 'all')
    per_page = int(request.GET.get('per_page', 50))  # Default to 50 per page
    country_filter = request.GET.get('country', '')
    tag_filter = request.GET.get('tag', '')
    rank_compare = request.GET.get('rank_compare', '')
    rank_value = request.GET.get('rank_value', '')
    rank_value2 = request.GET.get('rank_value2', '')
    
    # Get sort parameters
    sort_by = request.GET.get('sort', 'keyword')  # Default sort by keyword
    sort_order = request.GET.get('order', 'asc')  # Default ascending
    
    # Validate per_page value
    if per_page not in [50, 100, 250]:
        per_page = 50
    
    # Build queryset for keywords with tags prefetched
    keywords_qs = Keyword.objects.filter(
        project=project,
        archive=False
    ).prefetch_related('keyword_tags__tag')
    
    # Apply sorting
    if sort_by == 'keyword':
        if sort_order == 'desc':
            keywords_qs = keywords_qs.order_by('-keyword')
        else:
            keywords_qs = keywords_qs.order_by('keyword')
    elif sort_by == 'rank':
        # Sort by rank (NR/0 should come last)
        if sort_order == 'desc':
            keywords_qs = keywords_qs.extra(
                select={'rank_null': 'CASE WHEN rank = 0 OR rank > 100 THEN 1 ELSE 0 END'}
            ).order_by('rank_null', '-rank')
        else:
            keywords_qs = keywords_qs.extra(
                select={'rank_null': 'CASE WHEN rank = 0 OR rank > 100 THEN 1 ELSE 0 END'}
            ).order_by('rank_null', 'rank')
    elif sort_by == 'change':
        if sort_order == 'desc':
            keywords_qs = keywords_qs.order_by('-rank_diff_from_last_time')
        else:
            keywords_qs = keywords_qs.order_by('rank_diff_from_last_time')
    elif sort_by == 'last_checked':
        if sort_order == 'desc':
            keywords_qs = keywords_qs.order_by('-scraped_at')
        else:
            keywords_qs = keywords_qs.order_by('scraped_at')
    else:
        # Default sort
        keywords_qs = keywords_qs.order_by('-created_at')
    
    # Apply search filter
    if search_query:
        keywords_qs = keywords_qs.filter(
            keyword__icontains=search_query
        )
    
    # Apply country filter
    if country_filter:
        keywords_qs = keywords_qs.filter(country=country_filter)
    
    # Apply tag filter
    if tag_filter:
        keywords_qs = keywords_qs.filter(keyword_tags__tag_id=tag_filter)
    
    # Apply rank comparison filter
    if rank_compare and rank_value:
        try:
            rank_val = int(rank_value)
            if rank_compare == 'eq':
                keywords_qs = keywords_qs.filter(rank=rank_val)
            elif rank_compare == 'lt':
                keywords_qs = keywords_qs.filter(rank__lt=rank_val, rank__gt=0)
            elif rank_compare == 'gt':
                keywords_qs = keywords_qs.filter(rank__gt=rank_val)
            elif rank_compare == 'between' and rank_value2:
                rank_val2 = int(rank_value2)
                keywords_qs = keywords_qs.filter(rank__gte=rank_val, rank__lte=rank_val2)
        except ValueError:
            pass
    
    # Apply status filter
    if filter_status == 'top10':
        keywords_qs = keywords_qs.filter(rank__lte=10, rank__gt=0)
    elif filter_status == 'improved':
        keywords_qs = keywords_qs.filter(rank_status='up')
    elif filter_status == 'declined':
        keywords_qs = keywords_qs.filter(rank_status='down')
    elif filter_status == 'not_ranking':
        keywords_qs = keywords_qs.filter(Q(rank=0) | Q(rank__gt=100))
    
    # Calculate statistics
    keyword_stats = keywords_qs.aggregate(
        total_keywords=Count('id'),
        avg_rank=Avg('rank'),
        top10_count=Count('id', filter=Q(rank__lte=10, rank__gt=0)),
        improved_count=Count('id', filter=Q(rank_status='up')),
        declined_count=Count('id', filter=Q(rank_status='down')),
        not_ranking_count=Count('id', filter=Q(rank=0) | Q(rank__gt=100))
    )
    
    # Pagination
    page_number = request.GET.get('page', 1)
    paginator = Paginator(keywords_qs, per_page)
    page_obj = paginator.get_page(page_number)
    
    # Get available tags for filter dropdown
    available_tags = Tag.objects.filter(
        user=request.user,
        is_active=True
    ).annotate(
        keyword_count=Count('keyword_tags')
    ).filter(keyword_count__gt=0)
    
    # Get unique countries from keywords
    available_countries = Keyword.objects.filter(
        project=project,
        archive=False
    ).values_list('country', flat=True).distinct().order_by('country')
    
    context = {
        'project': project,
        'keywords': page_obj.object_list,
        'search_query': search_query,
        'filter_status': filter_status,
        'per_page': per_page,
        'country_filter': country_filter,
        'tag_filter': tag_filter,
        'rank_compare': rank_compare,
        'rank_value': rank_value,
        'rank_value2': rank_value2,
        'sort_by': sort_by,
        'sort_order': sort_order,
        'total_keywords': keyword_stats['total_keywords'] or 0,
        'top10_count': keyword_stats['top10_count'] or 0,
        'improved_count': keyword_stats['improved_count'] or 0,
        'declined_count': keyword_stats['declined_count'] or 0,
        'not_ranking_count': keyword_stats['not_ranking_count'] or 0,
        'avg_rank': keyword_stats['avg_rank'] or 0,
        'page_obj': page_obj,
        'has_next': page_obj.has_next(),
        'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
        'available_tags': available_tags,
        'available_countries': available_countries,
    }
    
    # Handle HTMX requests for partial updates
    if request.headers.get('HX-Request'):
        return render(request, 'keywords/partials/keywords_table.html', context)
    
    return render(request, 'keywords/project_detail.html', context)


@login_required
def add_keyword_modal(request):
    """Display modal for adding new keywords to a project"""
    user_projects = Project.objects.filter(
        Q(user=request.user) | Q(members=request.user)
    ).distinct()
    
    context = {
        'projects': user_projects,
    }
    return render(request, 'keywords/partials/add_keyword_modal.html', context)


@login_required
@require_http_methods(["POST"])
def add_keywords(request):
    """Add new keywords to a project with support for multiple countries and file uploads"""
    import csv
    import io
    
    project_id = request.POST.get('project_id')
    countries = request.POST.getlist('countries')  # Get multiple countries
    keywords_file = request.FILES.get('keywords_file')
    keywords_text = request.POST.get('keywords', '')
    tags_data = request.POST.get('tags', '[]')  # Get tags as JSON string
    
    if not project_id:
        return JsonResponse({'error': 'Project is required'}, status=400)
    
    if not countries:
        countries = ['US']  # Default to US if no country selected
    
    try:
        project = Project.objects.get(
            Q(id=project_id) & (Q(user=request.user) | Q(members=request.user))
        )
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found or access denied'}, status=404)
    
    # Parse keywords from file or text
    keywords_list = []
    
    if keywords_file:
        # Handle CSV/Excel file upload
        file_extension = keywords_file.name.split('.')[-1].lower()
        
        if file_extension == 'csv':
            # Read CSV file
            text_file = io.TextIOWrapper(keywords_file.file, encoding='utf-8')
            csv_reader = csv.reader(text_file)
            for row in csv_reader:
                if row and row[0].strip():
                    keyword = row[0].strip().lower()  # Normalize to lowercase
                    # Skip header if it exists
                    if keyword != 'keyword' and keyword not in keywords_list:
                        keywords_list.append(keyword)
        
        elif file_extension in ['xlsx', 'xls']:
            # Handle Excel files (requires openpyxl or xlrd)
            try:
                import openpyxl
                from io import BytesIO
                
                wb = openpyxl.load_workbook(BytesIO(keywords_file.read()))
                sheet = wb.active
                for row in sheet.iter_rows(values_only=True):
                    if row[0] and str(row[0]).strip():
                        keyword = str(row[0]).strip().lower()  # Normalize to lowercase
                        # Skip header if it exists
                        if keyword != 'keyword' and keyword not in keywords_list:
                            keywords_list.append(keyword)
            except ImportError:
                # If openpyxl is not installed, just read as text
                keywords_text = keywords_file.read().decode('utf-8', errors='ignore')
                keywords_list = [k.strip() for k in keywords_text.split('\n') if k.strip()]
    else:
        # Parse keywords from text (one per line) and normalize
        keywords_list = []
        for line in keywords_text.split('\n'):
            keyword = line.strip().lower()  # Normalize to lowercase and trim
            if keyword and keyword not in keywords_list:  # Remove duplicates
                keywords_list.append(keyword)
    
    if not keywords_list:
        return JsonResponse({'error': 'No keywords provided'}, status=400)
    
    # Parse tags data
    try:
        tags = json.loads(tags_data) if tags_data else []
    except json.JSONDecodeError:
        tags = []
    
    # Process tags - create new ones if needed
    tag_objects = []
    for tag_info in tags:
        if isinstance(tag_info, dict):
            tag_id = tag_info.get('id')
            tag_name = tag_info.get('name', '')
            tag_color = tag_info.get('color', '#6B7280')
            is_new = tag_info.get('isNew', False)
            
            # Skip empty tag names
            if not tag_name or not tag_name.strip():
                continue
            
            # Clean the tag name
            tag_name = tag_name.strip()
            
            if is_new or str(tag_id).startswith('new_'):
                # Create new tag
                tag, _ = Tag.objects.get_or_create(
                    user=request.user,
                    name=tag_name,
                    defaults={'color': tag_color}
                )
                tag_objects.append(tag)
            else:
                # Use existing tag
                try:
                    tag = Tag.objects.get(id=tag_id, user=request.user)
                    tag_objects.append(tag)
                except Tag.DoesNotExist:
                    pass
    
    added = []
    skipped = []
    total_created = 0
    created_keywords = []
    
    # Import the task
    from .tasks import fetch_keyword_serp_html
    
    # Create keywords for each country
    for keyword_text in keywords_list:
        for country in countries:
            keyword, created = Keyword.objects.get_or_create(
                project=project,
                keyword=keyword_text,
                country=country,
                defaults={
                    'crawl_interval_hours': 24,
                    'processing': True,  # Mark as processing for initial rank check
                    'crawl_priority': 'high',  # High priority for new keywords
                }
            )
            
            if created:
                total_created += 1
                created_keywords.append(keyword)
                # Schedule initial crawl with high priority
                keyword.schedule_next_crawl()
                keyword.save()
                
                # Trigger immediate rank check
                fetch_keyword_serp_html.delay(keyword.id)
                
                if keyword_text not in added:
                    added.append(keyword_text)
            else:
                if keyword_text not in skipped:
                    skipped.append(keyword_text)
            
            # Add tags to keyword (whether new or existing)
            for tag in tag_objects:
                KeywordTag.objects.get_or_create(
                    keyword=keyword,
                    tag=tag
                )
    
    # Return success response for HTMX
    if request.headers.get('HX-Request'):
        message = f'Added {total_created} keyword{"s" if total_created != 1 else ""}'
        if len(countries) > 1:
            message += f' across {len(countries)} countries'
        if skipped:
            message += f' ({len(skipped)} already existed)'
        
        response = JsonResponse({
            'success': True,
            'added': total_created,
            'skipped': len(skipped),
            'message': message
        })
        response['HX-Trigger'] = 'keywordsAdded'
        # Close the modal
        response['HX-Trigger-After-Settle'] = 'closeModal'
        return response
    
    return JsonResponse({
        'success': True,
        'added': added,
        'skipped': skipped,
        'total_created': total_created,
        'countries': countries,
        'message': f'Added {total_created} keywords across {len(countries)} countries'
    })


@login_required
def user_tags(request):
    """Display all tags for the current user"""
    tags = Tag.objects.filter(
        user=request.user,
        is_active=True
    ).annotate(
        keyword_count=Count('keyword_tags')
    ).order_by('name')
    
    context = {
        'tags': tags,
        'total_tags': tags.count(),
    }
    return render(request, 'keywords/user_tags.html', context)


@login_required
@require_http_methods(["GET"])
def api_user_tags(request):
    """API endpoint to get user's tags as JSON"""
    tags = Tag.objects.filter(
        user=request.user,
        is_active=True
    ).annotate(
        count=Count('keyword_tags')
    ).values('id', 'name', 'slug', 'color', 'description', 'count')
    
    return JsonResponse({
        'tags': list(tags),
        'count': len(tags)
    })


@login_required
def api_tags(request):
    """Simple API endpoint to get user's tags for autocomplete"""
    tags = Tag.objects.filter(
        user=request.user,
        is_active=True
    ).annotate(
        count=Count('keyword_tags')
    ).values('id', 'name', 'color', 'count')
    
    return JsonResponse(list(tags), safe=False)


@login_required
@require_http_methods(["POST"])
def api_create_tag(request):
    """API endpoint to create a new tag for the user"""
    name = request.POST.get('name')
    color = request.POST.get('color', '#6B7280')
    description = request.POST.get('description', '')
    
    # Validate that name is not empty or whitespace only
    if not name or not name.strip():
        return JsonResponse({'error': 'Tag name cannot be empty'}, status=400)
    
    # Clean the name
    name = name.strip()
    
    # Check if tag already exists for this user
    if Tag.objects.filter(user=request.user, name=name).exists():
        return JsonResponse({'error': 'Tag already exists'}, status=400)
    
    tag = Tag.objects.create(
        user=request.user,
        name=name,
        color=color,
        description=description
    )
    
    return JsonResponse({
        'id': tag.id,
        'name': tag.name,
        'slug': tag.slug,
        'color': tag.color,
        'description': tag.description
    })


@login_required
def keywords_by_tag(request, tag_slug):
    """Display keywords for a specific tag owned by the user"""
    tag = get_object_or_404(Tag, user=request.user, slug=tag_slug)
    
    keyword_tags = KeywordTag.objects.filter(tag=tag).select_related(
        'keyword',
        'keyword__project'
    )
    
    # Filter to only show keywords from user's projects
    keywords = []
    for kt in keyword_tags:
        if kt.keyword.project.user == request.user:
            keywords.append(kt.keyword)
    
    context = {
        'tag': tag,
        'keywords': keywords,
        'keyword_count': len(keywords)
    }
    
    return render(request, 'keywords/tag_keywords.html', context)


@login_required
@require_http_methods(["POST"])
def api_tag_keyword(request):
    """API endpoint to add a tag to a keyword"""
    keyword_id = request.POST.get('keyword_id')
    tag_id = request.POST.get('tag_id')
    
    if not keyword_id or not tag_id:
        return JsonResponse({'error': 'keyword_id and tag_id are required'}, status=400)
    
    # Get keyword and ensure user owns the project
    try:
        keyword = Keyword.objects.get(
            Q(id=keyword_id) &
            (Q(project__user=request.user) | Q(project__members=request.user))
        )
    except Keyword.DoesNotExist:
        return JsonResponse({'error': 'Keyword not found or access denied'}, status=404)
    
    # Get tag and ensure user owns it
    try:
        tag = Tag.objects.get(
            id=tag_id,
            user=request.user
        )
    except Tag.DoesNotExist:
        return JsonResponse({'error': 'Tag not found'}, status=404)
    
    # Create the association
    keyword_tag, created = KeywordTag.objects.get_or_create(
        keyword=keyword,
        tag=tag
    )
    
    return JsonResponse({
        'success': True,
        'created': created,
        'message': 'Tag added successfully' if created else 'Tag already exists for this keyword'
    })


@login_required
@require_http_methods(["DELETE"])
def api_untag_keyword(request, keyword_id, tag_id):
    """API endpoint to remove a tag from a keyword"""
    # Get keyword and ensure user owns the project
    try:
        keyword = Keyword.objects.get(
            Q(id=keyword_id) &
            (Q(project__user=request.user) | Q(project__members=request.user))
        )
    except Keyword.DoesNotExist:
        return JsonResponse({'error': 'Keyword not found or access denied'}, status=404)
    
    # Get tag and ensure user owns it
    try:
        tag = Tag.objects.get(
            id=tag_id,
            user=request.user
        )
    except Tag.DoesNotExist:
        return JsonResponse({'error': 'Tag not found'}, status=404)
    
    # Delete the association
    deleted_count, _ = KeywordTag.objects.filter(
        keyword=keyword,
        tag=tag
    ).delete()
    
    return JsonResponse({
        'success': True,
        'deleted': deleted_count > 0,
        'message': 'Tag removed successfully' if deleted_count > 0 else 'Tag was not associated with this keyword'
    })


@login_required
def api_keyword_status(request, keyword_id):
    """
    Get current status of a keyword (rank, processing state, last checked)
    """
    try:
        keyword = Keyword.objects.get(
            Q(id=keyword_id) &
            (Q(project__user=request.user) | Q(project__members=request.user))
        )
        
        # Calculate best rank from history
        from .models import Rank
        ranks_with_data = Rank.objects.filter(
            keyword=keyword,
            rank__gt=0,
            rank__lte=100
        ).values_list('rank', flat=True)
        
        best_rank = min(ranks_with_data) if ranks_with_data else (keyword.rank if 0 < keyword.rank <= 100 else 0)
        
        return create_ajax_response(
            success=True,
            data={
                'keyword_id': keyword.id,
                'keyword': keyword.keyword,
                'rank': keyword.rank,
                'best_rank': best_rank,
                'rank_change': keyword.rank_diff_from_last_time,
                'rank_status': keyword.rank_status,
                'processing': keyword.processing,
                'scraped_at': keyword.scraped_at.isoformat() if keyword.scraped_at else None,
                'last_checked': keyword.scraped_at.strftime('%Y-%m-%d %H:%M:%S') if keyword.scraped_at else 'Never',
                'time_since': keyword.scraped_at.strftime('%Y-%m-%d %H:%M') if keyword.scraped_at else 'Never'
            }
        )
    except Keyword.DoesNotExist:
        return create_ajax_response(
            success=False,
            message="Keyword not found"
        )
    except Exception as e:
        logger.error(f"Error getting keyword status {keyword_id}: {e}")
        return create_ajax_response(
            success=False,
            message=str(e)
        )

@login_required
@require_http_methods(["POST"])
def api_force_crawl(request, keyword_id):
    """
    Force crawl a keyword immediately (with rate limiting)
    
    User can only force crawl once per hour per keyword
    """
    try:
        # Get keyword and ensure user owns it
        keyword = Keyword.objects.get(
            Q(id=keyword_id) &
            (Q(project__user=request.user) | Q(project__members=request.user))
        )
        
        # Check if force crawl is allowed
        if not keyword.can_force_crawl():
            time_until_allowed = 60 - ((timezone.now() - keyword.last_force_crawl_at).total_seconds() / 60)
            return create_ajax_response(
                success=False,
                message=f"Please wait {int(time_until_allowed)} minutes before force crawling again",
                data={'minutes_remaining': int(time_until_allowed)}
            )
        
        # Perform force crawl
        scheduler = CrawlScheduler()
        if scheduler.force_crawl_keyword(keyword):
            return create_ajax_response(
                success=True,
                message="Force crawl initiated successfully",
                data={
                    'keyword_id': keyword.id,
                    'keyword': keyword.keyword,
                    'crawl_priority': keyword.crawl_priority,
                    'force_crawl_count': keyword.force_crawl_count + 1
                }
            )
        else:
            return create_ajax_response(
                success=False,
                message="Unable to initiate force crawl. Please try again later."
            )
            
    except Keyword.DoesNotExist:
        return create_ajax_response(
            success=False,
            message="Keyword not found or you don't have permission"
        )
    except Exception as e:
        logger.error(f"Error force crawling keyword {keyword_id}: {e}")
        return create_ajax_response(
            success=False,
            message=str(e)
        )


@login_required
@require_http_methods(["GET"])
def api_rank_serp(request, rank_id):
    """Get SERP data for a specific historical rank"""
    try:
        from .models import Rank
        from services.r2_storage import get_r2_service
        from urllib.parse import urlparse
        
        # Get the rank and ensure user owns it
        rank = Rank.objects.select_related('keyword__project').get(
            id=rank_id,
            keyword__project__user=request.user
        )
        
        if not rank.search_results_file:
            return create_ajax_response(
                success=False,
                message="No SERP data available for this rank"
            )
        
        # Load SERP data from R2
        r2_service = get_r2_service()
        search_data = r2_service.download_json(rank.search_results_file)
        
        if not search_data:
            return create_ajax_response(
                success=False,
                message="Failed to load SERP data"
            )
        
        # Parse the data
        if 'results' in search_data and isinstance(search_data['results'], dict):
            results_data = search_data['results']
        else:
            results_data = search_data
        
        # Process organic results
        serp_results = []
        organic_results = results_data.get('organic_results', [])
        for i, result in enumerate(organic_results):
            is_own_site = False
            url = result.get('url') or result.get('link', '#')
            if url and url != '#':
                result_domain = urlparse(url).netloc
                is_own_site = (result_domain == rank.keyword.project.domain or 
                             result_domain == f'www.{rank.keyword.project.domain}' or
                             f'www.{result_domain}' == rank.keyword.project.domain)
            
            serp_results.append({
                'position': result.get('position', i + 1),
                'url': url,
                'title': result.get('title', f'Result {i + 1}'),
                'snippet': result.get('description') or result.get('snippet', ''),
                'is_own_site': is_own_site,
            })
        
        # Process local pack
        local_pack_results = []
        local_pack = results_data.get('local_pack', {})
        if isinstance(local_pack, dict) and 'places' in local_pack:
            for place in local_pack['places'][:3]:
                if isinstance(place, dict):
                    title = place.get('title') or place.get('name', '')
                    reviews = place.get('reviews', 0)
                    if isinstance(reviews, str) and reviews.startswith('('):
                        reviews = reviews.strip('()')
                    
                    local_pack_results.append({
                        'title': title,
                        'rating': place.get('rating', 0),
                        'reviews': reviews,
                        'address': place.get('address', ''),
                    })
        
        return create_ajax_response(
            success=True,
            message="",
            data={
                'rank_id': rank.id,
                'position': rank.rank,
                'created_at': rank.created_at.isoformat(),
                'serp_results': serp_results,
                'local_pack': local_pack_results,
                'total_results': len(serp_results)
            }
        )
        
    except Rank.DoesNotExist:
        return create_ajax_response(
            success=False,
            message="Rank not found or you don't have permission"
        )
    except Exception as e:
        logger.error(f"Error fetching SERP data for rank {rank_id}: {e}")
        return create_ajax_response(
            success=False,
            message="Failed to load SERP data"
        )


@login_required
@require_http_methods(["GET"])
def api_crawl_status(request, keyword_id):
    """Get the crawl status and schedule for a keyword"""
    try:
        keyword = Keyword.objects.get(
            Q(id=keyword_id) &
            (Q(project__user=request.user) | Q(project__members=request.user))
        )
        
        now = timezone.now()
        
        # Calculate time until next crawl
        time_until_crawl = None
        if keyword.next_crawl_at:
            delta = keyword.next_crawl_at - now
            time_until_crawl = max(0, delta.total_seconds())
        
        # Calculate time until force crawl allowed
        time_until_force = 0
        if keyword.last_force_crawl_at:
            delta = (keyword.last_force_crawl_at + timezone.timedelta(hours=1)) - now
            time_until_force = max(0, delta.total_seconds())
        
        return create_ajax_response(
            success=True,
            message="",
            data={
                'keyword_id': keyword.id,
                'keyword': keyword.keyword,
                'crawl_priority': keyword.crawl_priority,
                'processing': keyword.processing,
                'scraped_at': keyword.scraped_at.isoformat() if keyword.scraped_at else None,
                'next_crawl_at': keyword.next_crawl_at.isoformat() if keyword.next_crawl_at else None,
                'can_force_crawl': keyword.can_force_crawl(),
                'force_crawl_count': keyword.force_crawl_count,
                'time_until_crawl': time_until_crawl,
                'time_until_force': time_until_force,
                'crawl_interval_hours': keyword.crawl_interval_hours,
                'should_crawl': keyword.should_crawl()
            }
        )
        
    except Keyword.DoesNotExist:
        return create_ajax_response(
            success=False,
            message="Keyword not found or you don't have permission"
        )


@login_required  
@require_http_methods(["GET"])
def api_crawl_queue(request):
    """Get the current crawl queue for user's keywords"""
    try:
        # Get user's keywords that are queued or processing
        keywords = Keyword.objects.filter(
            project__user=request.user
        ).filter(
            Q(processing=True) | Q(next_crawl_at__lte=timezone.now())
        ).order_by(
            '-crawl_priority',
            'next_crawl_at'
        )[:20]  # Limit to 20 for performance
        
        queue_data = []
        for kw in keywords:
            queue_data.append({
                'id': kw.id,
                'keyword': kw.keyword,
                'project': kw.project.domain,
                'priority': kw.crawl_priority,
                'processing': kw.processing,
                'next_crawl_at': kw.next_crawl_at.isoformat() if kw.next_crawl_at else None,
                'scraped_at': kw.scraped_at.isoformat() if kw.scraped_at else None,
            })
        
        return create_ajax_response(
            success=True,
            message="",
            data={
                'queue': queue_data,
                'total': len(queue_data)
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching crawl queue: {e}")
        return create_ajax_response(
            success=False,
            message="Error fetching crawl queue"
        )


@login_required
def keyword_updates_sse(request, project_id):
    """Server-Sent Events endpoint for real-time keyword rank updates"""
    from django.http import StreamingHttpResponse
    import time
    
    try:
        project = Project.objects.get(
            Q(id=project_id) & (Q(user=request.user) | Q(members=request.user))
        )
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found or access denied'}, status=404)
    
    def event_stream():
        """Generate SSE events for keyword updates"""
        last_check = timezone.now()
        
        while True:
            # Check for updated keywords
            updated_keywords = Keyword.objects.filter(
                project=project,
                updated_at__gt=last_check,
                archive=False
            ).prefetch_related('keyword_tags__tag')
            
            for keyword in updated_keywords:
                # Send update event
                data = {
                    'id': keyword.id,
                    'keyword': keyword.keyword,
                    'rank': keyword.rank,
                    'rank_status': keyword.rank_status,
                    'rank_diff': keyword.rank_diff_from_last_time,
                    'rank_url': keyword.rank_url,
                    'processing': keyword.processing,
                    'scraped_at': keyword.scraped_at.isoformat() if keyword.scraped_at else None,
                    'country': keyword.country,
                }
                
                yield f"data: {json.dumps(data)}\n\n"
            
            # Also check for processing status changes
            processing_keywords = Keyword.objects.filter(
                project=project,
                processing=True,
                archive=False
            )
            
            for keyword in processing_keywords:
                data = {
                    'id': keyword.id,
                    'processing': True,
                    'status': 'checking'
                }
                yield f"data: {json.dumps(data)}\n\n"
            
            last_check = timezone.now()
            time.sleep(2)  # Check every 2 seconds
    
    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@login_required
def keyword_detail(request, keyword_id):
    """Display detailed information for a specific keyword"""
    try:
        keyword = Keyword.objects.select_related('project').get(
            Q(id=keyword_id) &
            (Q(project__user=request.user) | Q(project__members=request.user))
        )
    except Keyword.DoesNotExist:
        return redirect('keywords:list')
    
    # Get ranking history (last 30 entries)
    from .models import Rank
    ranking_history = list(Rank.objects.filter(
        keyword=keyword
    ).order_by('-created_at')[:30])
    
    # Get the most recent rank with search results
    latest_rank = Rank.objects.filter(
        keyword=keyword
    ).order_by('-created_at').first()
    
    # Calculate rank changes
    for i, history in enumerate(ranking_history):
        if i < len(ranking_history) - 1:
            prev_rank = ranking_history[i + 1].rank
            curr_rank = history.rank
            if prev_rank > 0 and curr_rank > 0:
                history.rank_change = prev_rank - curr_rank  # Positive means improvement
            else:
                history.rank_change = 0
        else:
            history.rank_change = 0
    
    # Prepare chart data
    chart_dates = []
    chart_ranks = []
    
    if ranking_history:
        for history in reversed(ranking_history):
            chart_dates.append(history.created_at.strftime('%b %d'))
            # Use 101 for NR (not ranking) to show it at the bottom of chart
            chart_ranks.append(history.rank if history.rank > 0 else 101)
    else:
        # If no history, show current rank as a single point
        from datetime import datetime
        chart_dates = [datetime.now().strftime('%b %d')]
        chart_ranks = [keyword.rank if keyword.rank > 0 else 101]
    
    # Get SERP results from R2 storage if available
    serp_results = []
    local_pack_results = []
    
    if latest_rank and latest_rank.search_results_file:
        try:
            from services.r2_storage import get_r2_service
            r2_service = get_r2_service()
            
            # Download the JSON results from R2
            search_data = r2_service.download_json(latest_rank.search_results_file)
            
            if search_data:
                # Handle nested structure - results might be under 'results' key
                if 'results' in search_data and isinstance(search_data['results'], dict):
                    results_data = search_data['results']
                else:
                    results_data = search_data
                
                # Process ALL organic results (not limited to 10)
                organic_results = results_data.get('organic_results', [])
                for i, result in enumerate(organic_results):
                    # Skip results without valid URLs (these are likely special results)
                    url = result.get('url') or result.get('link', '')
                    if not url or url == '#' or url.startswith('#'):
                        # Skip this result as it's likely a special result
                        continue
                    
                    # Check if this result is from our project domain
                    is_own_site = False
                    if url:
                        from urllib.parse import urlparse
                        result_domain = urlparse(url).netloc
                        is_own_site = (result_domain == keyword.project.domain or 
                                     result_domain == f'www.{keyword.project.domain}' or
                                     f'www.{result_domain}' == keyword.project.domain)
                    
                    serp_result = {
                        'position': result.get('position', i + 1),
                        'url': url,
                        'title': result.get('title', f'Result {i + 1}'),
                        'snippet': result.get('description') or result.get('snippet', ''),
                        'is_own_site': is_own_site,
                        'domain': result.get('domain', ''),
                        'result_type': result.get('result_type', 'organic'),
                    }
                    serp_results.append(serp_result)
                
                # Process local pack results
                local_pack = results_data.get('local_pack', results_data.get('local_results', {}))
                if isinstance(local_pack, list):
                    # Direct list of local results
                    places_to_process = local_pack[:3]
                elif isinstance(local_pack, dict) and 'places' in local_pack:
                    # Nested under 'places' key
                    places_to_process = local_pack['places'][:3]
                else:
                    places_to_process = []
                
                for place in places_to_process:
                    if isinstance(place, dict):
                        # Handle both 'title' and 'name' fields
                        title = place.get('title') or place.get('name', '')
                        
                        # Parse reviews if it's in format "(18)"
                        reviews = place.get('reviews', 0)
                        if isinstance(reviews, str) and reviews.startswith('('):
                            reviews = reviews.strip('()')
                            
                        local_result = {
                            'title': title,
                            'position': place.get('position', 0),
                            'rating': place.get('rating', 0),
                            'reviews': reviews,
                            'type': place.get('type', ''),
                            'address': place.get('address', ''),
                            'phone': place.get('phone', ''),
                            'website': place.get('website', ''),
                        }
                        local_pack_results.append(local_result)
                        
        except Exception as e:
            logger.error(f"Error loading SERP results from R2: {e}")
            # Fall back to ranking_pages if R2 fails
            if hasattr(keyword, 'ranking_pages') and keyword.ranking_pages:
                for i, page in enumerate(keyword.ranking_pages[:10]):
                    if isinstance(page, dict):
                        serp_result = {
                            'position': page.get('position', i + 1),
                            'url': page.get('url', '#'),
                            'title': page.get('title', f'Result {i + 1}'),
                            'snippet': page.get('description', ''),
                            'is_own_site': False,
                        }
                        serp_results.append(serp_result)
    
    # If no R2 data, fall back to ranking_pages
    elif hasattr(keyword, 'ranking_pages') and keyword.ranking_pages:
        for i, page in enumerate(keyword.ranking_pages[:10]):
            if isinstance(page, dict):
                serp_result = {
                    'position': page.get('position', i + 1),
                    'url': page.get('url', '#'),
                    'title': page.get('title', f'Result {i + 1}'),
                    'snippet': page.get('description', ''),
                    'is_own_site': False,
                }
                serp_results.append(serp_result)
    
    # Calculate statistics
    ranks_with_data = [h.rank for h in ranking_history if h.rank > 0 and h.rank <= 100]
    
    # If no history, use current rank only if it's valid (1-100)
    if not ranks_with_data and keyword.rank > 0 and keyword.rank <= 100:
        ranks_with_data = [keyword.rank]
    
    # Set best_rank, worst_rank, and avg_rank to 0 if no valid ranking data (will show as NR)
    if ranks_with_data:
        best_rank = min(ranks_with_data)
        worst_rank = max(ranks_with_data)
        avg_rank = sum(ranks_with_data) / len(ranks_with_data)
    else:
        best_rank = 0  # Will display as NR in template
        worst_rank = 0  # Will display as NR in template
        avg_rank = 0   # Will display as NR in template
    
    # Get competitor analysis from SERP results
    competitors = []
    competitor_domains = {}  # Track domains and their best positions
    
    if serp_results:
        from urllib.parse import urlparse
        for result in serp_results:
            if result['url'] and result['url'] != '#':
                domain = urlparse(result['url']).netloc
                # Skip our own domain and empty domains
                if domain and domain != keyword.project.domain and domain != f'www.{keyword.project.domain}':
                    # Track the best (lowest) position for each domain
                    if domain not in competitor_domains or result['position'] < competitor_domains[domain]['position']:
                        competitor_domains[domain] = {
                            'domain': domain,
                            'position': result['position'],
                            'url': result['url'],
                            'title': result['title'],
                            'snippet': result.get('snippet', '')[:100],
                            'count': competitor_domains.get(domain, {}).get('count', 0) + 1
                        }
                    else:
                        # Increment count if domain appears multiple times
                        competitor_domains[domain]['count'] = competitor_domains.get(domain, {}).get('count', 0) + 1
        
        # Convert to list and sort by position
        competitors = sorted(competitor_domains.values(), key=lambda x: x['position'])[:20]
    
    # Debug logging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Keyword detail for: {keyword.keyword}")
    logger.info(f"SERP results count: {len(serp_results)}")
    logger.info(f"Ranking history count: {len(ranking_history)}")
    logger.info(f"Competitors count: {len(competitors)}")
    
    context = {
        'keyword': keyword,
        'project': keyword.project,
        'ranking_history': ranking_history,
        'chart_dates': json.dumps(chart_dates) if chart_dates else '[]',
        'chart_ranks': json.dumps(chart_ranks) if chart_ranks else '[]',
        'serp_results': serp_results,
        'local_pack_results': local_pack_results,
        'competitors': competitors,  # All competitors, already limited to top 20 in processing
        'best_rank': best_rank if best_rank else 0,
        'worst_rank': worst_rank if worst_rank else 0,
        'avg_rank': int(avg_rank) if avg_rank else 0,
        'total_checks': len(ranking_history),
        'latest_rank': latest_rank,
    }
    
    return render(request, 'keywords/keyword_detail.html', context)


@login_required
@require_http_methods(["POST"])
def api_delete_keyword(request, keyword_id):
    """Delete a keyword and all its associated data"""
    try:
        # Get the keyword and verify ownership
        keyword = get_object_or_404(
            Keyword,
            Q(id=keyword_id) &
            (Q(project__user=request.user) | Q(project__members=request.user))
        )
        
        # Store keyword text for the response message
        keyword_text = keyword.keyword
        project = keyword.project
        
        # Delete the keyword (this will cascade delete all related data)
        keyword.delete()
        
        # Log the deletion
        logger.info(f"User {request.user.id} deleted keyword '{keyword_text}' from project {project.id}")
        
        return JsonResponse({
            'success': True,
            'message': f'Keyword "{keyword_text}" has been deleted successfully.'
        })
    except Keyword.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Keyword not found or you do not have permission to delete it.'
        }, status=404)
    except Exception as e:
        logger.error(f"Error deleting keyword {keyword_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while deleting the keyword. Please try again.'
        }, status=500)