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

logger = get_logger(__name__)


@login_required
def keywords_list(request):
    """Display all projects with keyword statistics for the current user"""
    # Get filter parameters
    search_query = request.GET.get('search', '')
    
    # Get user's projects
    user_projects = Project.objects.filter(user=request.user)
    
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
    
    # Calculate overall statistics across all projects
    all_keywords = Keyword.objects.filter(project__user=request.user, archive=False)
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
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        return redirect('keywords:list')
    
    # Get filter parameters
    search_query = request.GET.get('search', '')
    filter_status = request.GET.get('filter', 'all')
    
    # Build queryset for keywords
    keywords_qs = Keyword.objects.filter(
        project=project,
        archive=False
    ).order_by('-created_at')
    
    # Apply search filter
    if search_query:
        keywords_qs = keywords_qs.filter(
            keyword__icontains=search_query
        )
    
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
    paginator = Paginator(keywords_qs, 20)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'project': project,
        'keywords': page_obj.object_list,
        'search_query': search_query,
        'filter_status': filter_status,
        'total_keywords': keyword_stats['total_keywords'] or 0,
        'top10_count': keyword_stats['top10_count'] or 0,
        'improved_count': keyword_stats['improved_count'] or 0,
        'declined_count': keyword_stats['declined_count'] or 0,
        'not_ranking_count': keyword_stats['not_ranking_count'] or 0,
        'avg_rank': keyword_stats['avg_rank'] or 0,
        'page_obj': page_obj,
        'has_next': page_obj.has_next(),
        'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
    }
    
    # Handle HTMX requests for partial updates
    if request.headers.get('HX-Request'):
        return render(request, 'keywords/partials/keywords_table.html', context)
    
    return render(request, 'keywords/project_detail.html', context)


@login_required
def add_keyword_modal(request):
    """Display modal for adding new keywords to a project"""
    user_projects = Project.objects.filter(user=request.user)
    
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
    
    if not project_id:
        return JsonResponse({'error': 'Project is required'}, status=400)
    
    if not countries:
        countries = ['US']  # Default to US if no country selected
    
    try:
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)
    
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
    
    added = []
    skipped = []
    total_created = 0
    
    # Create keywords for each country
    for keyword_text in keywords_list:
        for country in countries:
            keyword, created = Keyword.objects.get_or_create(
                project=project,
                keyword=keyword_text,
                country=country,
                defaults={
                    'crawl_interval_hours': 24,
                }
            )
            
            if created:
                total_created += 1
                # Schedule initial crawl
                keyword.schedule_next_crawl()
                if keyword_text not in added:
                    added.append(keyword_text)
            else:
                if keyword_text not in skipped:
                    skipped.append(keyword_text)
    
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
    ).values('id', 'name', 'slug', 'color', 'description')
    
    return JsonResponse({
        'tags': list(tags),
        'count': len(tags)
    })


@login_required
@require_http_methods(["POST"])
def api_create_tag(request):
    """API endpoint to create a new tag for the user"""
    name = request.POST.get('name')
    color = request.POST.get('color', '#6B7280')
    description = request.POST.get('description', '')
    
    if not name:
        return JsonResponse({'error': 'Name is required'}, status=400)
    
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
            id=keyword_id,
            project__user=request.user
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
            id=keyword_id,
            project__user=request.user
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
@require_http_methods(["POST"])
def api_force_crawl(request, keyword_id):
    """
    Force crawl a keyword immediately (with rate limiting)
    
    User can only force crawl once per hour per keyword
    """
    try:
        # Get keyword and ensure user owns it
        keyword = Keyword.objects.get(
            id=keyword_id,
            project__user=request.user
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
def api_crawl_status(request, keyword_id):
    """Get the crawl status and schedule for a keyword"""
    try:
        keyword = Keyword.objects.get(
            id=keyword_id,
            project__user=request.user
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