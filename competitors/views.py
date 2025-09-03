from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, View
from django.http import JsonResponse
from django.db.models import Q, Count, Avg, Case, When, IntegerField, Value, Prefetch
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from keywords.models import Keyword
from project.models import Project
from .models import Target, TargetKeywordRank
import json
from urllib.parse import urlparse


@method_decorator(login_required, name='dispatch')
class CompetitorKeywordsView(TemplateView):
    template_name = 'competitors/keywords.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get user's projects for the filter dropdown
        user_projects = Project.objects.filter(
            Q(user=self.request.user) | 
            Q(members=self.request.user)
        ).distinct()
        
        context['projects'] = user_projects
        context['selected_project_id'] = self.request.GET.get('project')
        
        return context


@method_decorator(login_required, name='dispatch')
class CompetitorKeywordsDataView(View):
    
    def get(self, request):
        # Get filter parameters
        search_query = request.GET.get('search', '')
        project_id = request.GET.get('project', '')
        page = request.GET.get('page', 1)
        per_page = int(request.GET.get('per_page', 50))
        
        # Base queryset - get all keywords user has access to
        keywords = Keyword.objects.filter(
            Q(project__user=request.user) |
            Q(project__members=request.user)
        ).filter(
            archive=False
        ).select_related('project').distinct()
        
        # Apply project filter
        if project_id:
            keywords = keywords.filter(project_id=project_id)
        
        # Apply search filter
        if search_query:
            keywords = keywords.filter(
                Q(keyword__icontains=search_query) |
                Q(project__domain__icontains=search_query)
            )
        
        # Order by rank (0 means not ranking, so put them last)
        keywords = keywords.annotate(
            rank_order=Case(
                When(rank=0, then=Value(10000)),
                default='rank',
                output_field=IntegerField(),
            )
        ).order_by('rank_order', 'keyword')
        
        # Paginate
        paginator = Paginator(keywords, per_page)
        
        try:
            keywords_page = paginator.page(page)
        except PageNotAnInteger:
            keywords_page = paginator.page(1)
        except EmptyPage:
            keywords_page = paginator.page(paginator.num_pages)
        
        # Format data for response
        keywords_data = []
        for keyword in keywords_page:
            # Parse ranking_pages data for top 3 competitors
            competitors = []
            if keyword.ranking_pages:
                for idx, page_data in enumerate(keyword.ranking_pages[:3]):
                    if isinstance(page_data, dict):
                        url = page_data.get('url', '')
                        position = page_data.get('position', idx + 1)
                    else:
                        # Handle old format if any
                        url = page_data if isinstance(page_data, str) else ''
                        position = idx + 1
                    
                    if url:
                        domain = self._extract_domain(url)
                        competitors.append({
                            'position': position,
                            'domain': domain,
                            'url': url
                        })
            
            # Fill empty slots if less than 3 competitors
            while len(competitors) < 3:
                competitors.append({
                    'position': len(competitors) + 1,
                    'domain': '-',
                    'url': ''
                })
            
            keywords_data.append({
                'id': keyword.id,
                'keyword': keyword.keyword,
                'project': keyword.project.domain,
                'project_id': keyword.project.id,
                'rank': keyword.rank if (keyword.rank > 0 and keyword.rank <= 100) else '-',
                'rank_status': keyword.rank_status,
                'rank_diff': keyword.rank_diff_from_last_time,
                'competitors': competitors,
                'country': keyword.country,
                'scraped_at': keyword.scraped_at.strftime('%Y-%m-%d %H:%M') if keyword.scraped_at else 'Never',
            })
        
        # Prepare pagination info
        pagination = {
            'current_page': keywords_page.number,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'per_page': per_page,
            'has_next': keywords_page.has_next(),
            'has_previous': keywords_page.has_previous(),
            'next_page': keywords_page.next_page_number() if keywords_page.has_next() else None,
            'previous_page': keywords_page.previous_page_number() if keywords_page.has_previous() else None,
            'page_range': list(paginator.get_elided_page_range(keywords_page.number, on_each_side=2, on_ends=1))
        }
        
        return JsonResponse({
            'success': True,
            'data': keywords_data,
            'pagination': pagination
        })
    
    def _extract_domain(self, url):
        """Extract domain from URL"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path
            # Remove www. prefix if present
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return url


@method_decorator(login_required, name='dispatch')
class TargetView(TemplateView):
    template_name = 'competitors/target_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get user's projects with targets count
        user_projects = Project.objects.filter(
            Q(user=self.request.user) | 
            Q(members=self.request.user)
        ).distinct().annotate(
            targets_count=Count('targets')
        ).prefetch_related(
            Prefetch('targets', queryset=Target.objects.all())
        )
        
        context['projects'] = user_projects
        return context


@login_required
@require_http_methods(["POST"])
def add_target(request, project_id):
    """Add a new target to a project"""
    project = get_object_or_404(Project, id=project_id)
    
    # Check permissions
    if project.user != request.user and not project.members.filter(id=request.user.id).exists():
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    domain = request.POST.get('domain', '').strip()
    name = request.POST.get('name', '').strip()
    
    if not domain:
        return JsonResponse({'success': False, 'error': 'Domain is required'})
    
    # Check if already at max targets
    if project.targets.count() >= 3:
        return JsonResponse({'success': False, 'error': 'Maximum 3 targets allowed per project'})
    
    try:
        target = Target.objects.create(
            project=project,
            domain=domain,
            name=name,
            created_by=request.user
        )
        return JsonResponse({
            'success': True, 
            'target': {
                'id': target.id,
                'domain': target.domain,
                'name': target.name
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def remove_target(request, target_id):
    """Remove a target"""
    target = get_object_or_404(Target, id=target_id)
    project = target.project
    
    # Check permissions
    if project.user != request.user and not project.members.filter(id=request.user.id).exists():
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    target.delete()
    return JsonResponse({'success': True})


@method_decorator(login_required, name='dispatch')
class TargetComparisonView(TemplateView):
    template_name = 'competitors/target_comparison.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project_id = kwargs.get('project_id')
        
        # Get project with targets
        project = get_object_or_404(
            Project.objects.prefetch_related('targets'),
            id=project_id
        )
        
        # Check permissions
        if project.user != self.request.user and not project.members.filter(id=self.request.user.id).exists():
            context['error'] = 'Permission denied'
            return context
        
        # Get pagination parameters
        page = self.request.GET.get('page', 1)
        per_page = int(self.request.GET.get('per_page', 50))
        search_query = self.request.GET.get('search', '')
        
        # Get keywords for this project
        keywords_qs = Keyword.objects.filter(
            project=project,
            archive=False
        ).select_related('project')
        
        # Apply search filter
        if search_query:
            keywords_qs = keywords_qs.filter(keyword__icontains=search_query)
        
        # Order by keyword name
        keywords_qs = keywords_qs.order_by('keyword')
        
        # Paginate
        paginator = Paginator(keywords_qs, per_page)
        try:
            keywords_page = paginator.page(page)
        except PageNotAnInteger:
            keywords_page = paginator.page(1)
        except EmptyPage:
            keywords_page = paginator.page(paginator.num_pages)
        
        # Get targets for this project
        targets = project.targets.all()[:3]  # Max 3 targets
        
        # Build comparison data
        comparison_data = []
        for keyword in keywords_page:
            row_data = {
                'keyword': keyword.keyword,
                'keyword_id': keyword.id,
                'project_rank': keyword.rank if keyword.rank > 0 and keyword.rank <= 100 else 'NR',
                'scraped_at': keyword.scraped_at,
                'target_ranks': []
            }
            
            # Get target ranks for this keyword
            for target in targets:
                target_rank = TargetKeywordRank.objects.filter(
                    target=target,
                    keyword=keyword
                ).first()
                
                if target_rank:
                    rank_value = target_rank.rank if target_rank.rank > 0 and target_rank.rank <= 100 else 'NR'
                else:
                    rank_value = 'NR'
                
                row_data['target_ranks'].append({
                    'domain': target.domain,
                    'rank': rank_value
                })
            
            comparison_data.append(row_data)
        
        context.update({
            'project': project,
            'targets': targets,
            'comparison_data': comparison_data,
            'keywords_page': keywords_page,
            'search_query': search_query,
            'per_page': per_page,
            'pagination': {
                'current_page': keywords_page.number,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'has_next': keywords_page.has_next(),
                'has_previous': keywords_page.has_previous(),
                'page_range': list(paginator.get_elided_page_range(keywords_page.number, on_each_side=2, on_ends=1))
            }
        })
        
        return context