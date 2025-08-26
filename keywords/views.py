from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Q
from django.utils import timezone
from .models import Tag, Keyword, KeywordTag
from .crawl_scheduler import CrawlScheduler
from common.utils import create_ajax_response, get_logger

logger = get_logger(__name__)


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