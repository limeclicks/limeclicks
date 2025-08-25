from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Count
from .models import Tag, Keyword, KeywordTag


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