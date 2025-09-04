from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count
from django.contrib.auth import get_user_model
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action, display
from .models import Keyword, Rank, Tag, KeywordTag

User = get_user_model()


class KeywordTagInline(TabularInline):
    model = KeywordTag
    extra = 1
    verbose_name = 'Tag'
    verbose_name_plural = 'Tags'
    autocomplete_fields = ['tag']
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Limit tags to current user's tags or project owner's tags"""
        if db_field.name == "tag":
            # Get the keyword's project owner if available
            if hasattr(request, '_obj_') and request._obj_:
                project_owner = request._obj_.project.user
                kwargs["queryset"] = Tag.objects.filter(user=project_owner, is_active=True)
            elif not request.user.is_superuser:
                kwargs["queryset"] = Tag.objects.filter(user=request.user, is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class RankInline(TabularInline):
    model = Rank
    extra = 0
    readonly_fields = ['rank', 'is_organic', 'created_at']
    fields = ['rank', 'is_organic', 'has_map_result', 'has_video_result', 'has_image_result', 'created_at']
    ordering = ['-created_at']
    can_delete = False
    max_num = 10  # Show only last 10 ranks
    verbose_name = 'Rank History'
    verbose_name_plural = 'Rank History (Last 10)'



@admin.register(Keyword)
class KeywordAdmin(ModelAdmin):
    # Warn unfold config
    warn_unsaved_form = True
    compressed_fields = True
    
    # Inlines
    inlines = [KeywordTagInline, RankInline]
    
    # List display with custom methods
    list_display = [
        'display_keyword',
        'display_project', 
        'display_rank_with_change',
        'display_impact',
        'display_tags',
        'display_status',
        'display_last_scraped',
        'created_at'
    ]
    
    # Enhanced filters
    list_filter = [
        'rank_status',
        'impact',
        'processing',
        'archive',
        'country',
        ('project', admin.RelatedOnlyFieldListFilter),
        ('keyword_tags__tag', admin.RelatedOnlyFieldListFilter),
        'created_at',
        'scraped_at',
    ]
    
    # Search
    search_fields = ['keyword', 'project__domain', 'rank_url']
    
    # Read only fields
    readonly_fields = [
        'created_at', 
        'updated_at', 
        'scraped_at',
        'rank_diff_from_last_time',
        'initial_rank',
        'highest_rank',
        'display_rank_history_chart'
    ]
    
    # Ordering
    ordering = ['-created_at']
    
    # Per page
    list_per_page = 50
    
    # Date hierarchy
    date_hierarchy = 'created_at'
    
    # Actions
    actions = ['mark_as_archived', 'mark_as_active', 'force_rescrape', 'export_to_csv']
    
    # Fieldsets with better organization
    fieldsets = (
        ('🔍 Keyword Information', {
            'fields': ('project', 'keyword', 'country', 'location'),
            'classes': ('collapse-open',),
        }),
        ('📊 Current Ranking', {
            'fields': (
                ('rank', 'rank_status'),
                ('rank_diff_from_last_time', 'impact'),
                'rank_url',
                'display_rank_history_chart',
            ),
            'classes': ('collapse-open',),
        }),
        ('📈 Historical Data', {
            'fields': (
                ('initial_rank', 'highest_rank'),
                'on_map',
                'number_of_results',
            ),
            'classes': ('collapse',),
        }),
        ('🤖 Scraping Information', {
            'fields': (
                'scraped_at',
                'scrape_do_at',
                'processing',
                ('success_api_hit_count', 'failed_api_hit_count'),
                'last_error_message',
            ),
            'classes': ('collapse',),
        }),
        ('⚙️ Management', {
            'fields': ('archive',),
            'classes': ('collapse',),
        }),
        ('🕐 Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'project'
        ).prefetch_related(
            'keyword_tags__tag',
            'ranks'
        ).annotate(
            tag_count=Count('keyword_tags')
        )
    
    def get_form(self, request, obj=None, **kwargs):
        """Store object on request for inline access"""
        request._obj_ = obj
        return super().get_form(request, obj, **kwargs)
    
    @display(description='Keyword', ordering='keyword')
    def display_keyword(self, obj):
        return format_html(
            '<div style="font-weight: 500;">{}</div>'
            '<div style="color: #6b7280; font-size: 0.875rem;">{}</div>',
            obj.keyword,
            obj.location or obj.country
        )
    
    @display(description='Project', ordering='project__domain')
    def display_project(self, obj):
        url = reverse('admin:project_project_change', args=[obj.project.pk])
        return format_html(
            '<a href="{}" style="color: #0ea5e9; text-decoration: none;">{}</a>',
            url,
            obj.project.domain
        )
    
    @display(description='Rank', ordering='rank')
    def display_rank_with_change(self, obj):
        if obj.rank == 0 or obj.rank == 101:
            # Not ranked - show as Not ranked
            return format_html(
                '<span style="color: #6b7280;">Not ranked</span>'
            )
        
        # Determine color based on rank
        if obj.rank <= 3:
            color = '#10b981'  # Green
        elif obj.rank <= 10:
            color = '#3b82f6'  # Blue
        elif obj.rank <= 30:
            color = '#f59e0b'  # Yellow
        elif obj.rank <= 50:
            color = '#8b5cf6'  # Purple
        elif obj.rank <= 100:
            color = '#6b7280'  # Gray
        else:
            color = '#ef4444'  # Red for >100
        
        # Build change indicator
        change_html = ''
        if obj.rank_diff_from_last_time != 0:
            if obj.rank_diff_from_last_time > 0:
                # Positive means improvement (rank decreased)
                change_html = format_html(
                    ' <span style="color: #10b981;">↑{}</span>',
                    obj.rank_diff_from_last_time
                )
            else:
                # Negative means decline (rank increased)
                change_html = format_html(
                    ' <span style="color: #ef4444;">↓{}</span>',
                    abs(obj.rank_diff_from_last_time)
                )
        
        return format_html(
            '<span style="color: {}; font-weight: 600;">#{}</span>{}',
            color,
            obj.rank,
            change_html
        )
    
    @display(description='Impact', ordering='impact')
    def display_impact(self, obj):
        colors = {
            'high': '#ef4444',
            'medium': '#f59e0b',
            'low': '#3b82f6',
            'no': '#6b7280',
        }
        
        icons = {
            'high': '🔴',
            'medium': '🟡',
            'low': '🔵',
            'no': '⚪',
        }
        
        return format_html(
            '<span style="color: {};">{} {}</span>',
            colors.get(obj.impact, '#6b7280'),
            icons.get(obj.impact, ''),
            obj.get_impact_display()
        )
    
    @display(description='Tags')
    def display_tags(self, obj):
        tags = obj.keyword_tags.all()[:3]  # Show first 3 tags
        if not tags:
            return '-'
        
        tag_html = []
        for kt in tags:
            tag = kt.tag
            tag_html.append(format_html(
                '<span style="background-color: {}; color: white; padding: 2px 8px; '
                'border-radius: 4px; font-size: 0.75rem; margin-right: 4px;">{}</span>',
                tag.color,
                tag.name
            ))
        
        if obj.keyword_tags.count() > 3:
            tag_html.append(format_html(
                '<span style="color: #6b7280; font-size: 0.75rem;">+{} more</span>',
                obj.keyword_tags.count() - 3
            ))
        
        return format_html(''.join(tag_html))
    
    @display(description='Status')
    def display_status(self, obj):
        status_html = []
        
        if obj.processing:
            status_html.append(
                '<span style="background-color: #fbbf24; color: #78350f; '
                'padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;">Processing</span>'
            )
        
        if obj.archive:
            status_html.append(
                '<span style="background-color: #6b7280; color: white; '
                'padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;">Archived</span>'
            )
        
        if obj.rank_status == 'new':
            status_html.append(
                '<span style="background-color: #10b981; color: white; '
                'padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;">New</span>'
            )
        
        return format_html(' '.join(status_html)) if status_html else '-'
    
    @display(description='Last Scraped', ordering='scraped_at')
    def display_last_scraped(self, obj):
        if not obj.scraped_at:
            return format_html('<span style="color: #ef4444;">Never</span>')
        
        # Calculate time difference
        now = timezone.now()
        diff = now - obj.scraped_at
        
        if diff.days > 1:
            time_str = f"{diff.days} days ago"
            color = '#ef4444' if diff.days > 7 else '#f59e0b'
        elif diff.days == 1:
            time_str = "Yesterday"
            color = '#f59e0b'
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            time_str = f"{hours} hour{'s' if hours > 1 else ''} ago"
            color = '#3b82f6'
        else:
            minutes = diff.seconds // 60
            time_str = f"{minutes} min ago" if minutes > 0 else "Just now"
            color = '#10b981'
        
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            time_str
        )
    
    @display(description='Rank History')
    def display_rank_history_chart(self, obj):
        """Display a simple ASCII chart of rank history"""
        ranks = obj.ranks.order_by('-created_at')[:20]
        if not ranks:
            return "No rank history available"
        
        chart_html = '<div style="font-family: monospace; line-height: 1.2;">'
        chart_html += '<strong>Recent Rank Trend (newest → oldest):</strong><br>'
        
        for rank in ranks:
            bar_length = max(1, 30 - rank.rank) if rank.rank > 0 else 0
            bar = '█' * bar_length
            chart_html += f'{rank.created_at.strftime("%m/%d")} #{rank.rank:3d} {bar}<br>'
        
        chart_html += '</div>'
        return format_html(chart_html)
    
    # Custom actions
    @action(description="Archive selected keywords")
    def mark_as_archived(self, request, queryset):
        count = queryset.update(archive=True, processing=False)
        self.message_user(request, f"{count} keywords archived.")
    
    @action(description="Activate selected keywords")
    def mark_as_active(self, request, queryset):
        count = queryset.update(archive=False)
        self.message_user(request, f"{count} keywords activated.")
    
    @action(description="Force re-scrape")
    def force_rescrape(self, request, queryset):
        count = queryset.update(scraped_at=None, processing=False)
        self.message_user(request, f"{count} keywords marked for re-scraping.")
    
    @action(description="Export to CSV")
    def export_to_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="keywords.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Keyword', 'Project', 'Country', 'Rank', 'Status', 
            'Impact', 'Initial Rank', 'Highest Rank', 'Last Scraped'
        ])
        
        for obj in queryset:
            writer.writerow([
                obj.keyword,
                obj.project.domain,
                obj.country,
                obj.rank,
                obj.rank_status,
                obj.impact,
                obj.initial_rank,
                obj.highest_rank,
                obj.scraped_at.strftime('%Y-%m-%d %H:%M') if obj.scraped_at else 'Never'
            ])
        
        return response


@admin.register(Rank)
class RankAdmin(ModelAdmin):
    list_display = [
        'display_keyword_info',
        'display_rank_badge',
        'display_serp_features',
        'created_at'
    ]
    
    list_filter = [
        'is_organic',
        'has_map_result',
        'has_video_result',
        'has_image_result',
        ('keyword__project', admin.RelatedOnlyFieldListFilter),
        'created_at',
    ]
    
    search_fields = ['keyword__keyword', 'keyword__project__domain']
    readonly_fields = ['created_at', 'display_json_preview']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    list_per_page = 100
    
    fieldsets = (
        ('🔍 Keyword', {
            'fields': ('keyword',),
            'classes': ('collapse-open',),
        }),
        ('📊 Ranking Information', {
            'fields': ('rank', 'is_organic'),
            'classes': ('collapse-open',),
        }),
        ('🎯 SERP Features', {
            'fields': ('has_map_result', 'has_video_result', 'has_image_result'),
            'classes': ('collapse-open',),
        }),
        ('📁 Data Files', {
            'fields': ('search_results_file', 'display_json_preview'),
            'classes': ('collapse',),
        }),
        ('🕐 Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('keyword', 'keyword__project')
    
    @display(description='Keyword', ordering='keyword__keyword')
    def display_keyword_info(self, obj):
        url = reverse('admin:keywords_keyword_change', args=[obj.keyword.pk])
        return format_html(
            '<a href="{}" style="color: #0ea5e9; text-decoration: none;">'
            '<strong>{}</strong></a><br>'
            '<span style="color: #6b7280; font-size: 0.875rem;">{}</span>',
            url,
            obj.keyword.keyword,
            obj.keyword.project.domain
        )
    
    @display(description='Rank', ordering='rank')
    def display_rank_badge(self, obj):
        if obj.rank == 0 or obj.rank == 101:
            return format_html(
                '<span style="color: #6b7280;">Not ranked</span>'
            )
        
        # Determine color based on rank
        if obj.rank <= 3:
            color = '#10b981'  # Green
            emoji = '🥇' if obj.rank == 1 else '🥈' if obj.rank == 2 else '🥉'
        elif obj.rank <= 10:
            color = '#3b82f6'  # Blue
            emoji = '🔵'
        elif obj.rank <= 30:
            color = '#f59e0b'  # Yellow
            emoji = '🟡'
        elif obj.rank <= 50:
            color = '#8b5cf6'  # Purple
            emoji = '🟣'
        elif obj.rank <= 100:
            color = '#6b7280'  # Gray
            emoji = '⚪'
        else:
            color = '#ef4444'  # Red
            emoji = '🔴'
        
        type_badge = format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; margin-left: 8px;">{}</span>',
            '#10b981' if obj.is_organic else '#f59e0b',
            'Organic' if obj.is_organic else 'Paid'
        )
        
        rank_display = '&gt;100' if obj.rank > 100 else f'#{obj.rank}'
        
        return format_html(
            '{} <span style="color: {}; font-weight: 600;">{}</span>{}',
            emoji,
            color,
            rank_display,
            type_badge
        )
    
    @display(description='SERP Features')
    def display_serp_features(self, obj):
        features = []
        
        if obj.has_map_result:
            features.append('📍 Map')
        if obj.has_video_result:
            features.append('🎥 Video')
        if obj.has_image_result:
            features.append('🖼️ Image')
        
        return format_html(' '.join(features)) if features else '-'
    
    @display(description='JSON Preview')
    def display_json_preview(self, obj):
        if not obj.search_results_file:
            return "No JSON file available"
        
        return format_html(
            '<div style="background-color: #f3f4f6; padding: 8px; border-radius: 4px; '
            'font-family: monospace; font-size: 0.75rem;">'
            '<strong>File:</strong> {}<br>'
            '<a href="#" onclick="alert(\'View full JSON in R2 storage\'); return false;" '
            'style="color: #0ea5e9;">View Full JSON →</a>'
            '</div>',
            obj.search_results_file
        )


@admin.register(Tag)
class TagAdmin(ModelAdmin):
    list_display = [
        'display_tag_name',
        'display_user',
        'slug',
        'is_active',
        'display_keyword_count',
        'created_at'
    ]
    
    list_filter = [
        'is_active',
        ('user', admin.RelatedOnlyFieldListFilter),
        'created_at',
    ]
    
    search_fields = ['name', 'slug', 'user__email', 'user__username']
    autocomplete_fields = ['user']
    readonly_fields = ['slug', 'created_at', 'updated_at', 'display_keywords_preview']
    ordering = ['name']
    list_per_page = 50
    
    fieldsets = (
        ('👤 Owner', {
            'fields': ('user',),
            'classes': ('collapse-open',),
        }),
        ('🏷️ Tag Information', {
            'fields': ('name', 'slug', 'color', 'description'),
            'classes': ('collapse-open',),
        }),
        ('⚙️ Settings', {
            'fields': ('is_active',),
            'classes': ('collapse-open',),
        }),
        ('📊 Usage', {
            'fields': ('display_keywords_preview',),
            'classes': ('collapse-open',),
        }),
        ('🕐 Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('user').annotate(
            keyword_count=Count('keyword_tags')
        )
        # Non-superusers only see their own tags
        if not request.user.is_superuser:
            qs = qs.filter(user=request.user)
        return qs
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Limit user field to current user for non-superusers"""
        if db_field.name == "user" and not request.user.is_superuser:
            kwargs["queryset"] = User.objects.filter(pk=request.user.pk)
            kwargs["initial"] = request.user
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def save_model(self, request, obj, form, change):
        """Auto-assign current user if not superuser"""
        if not change and not request.user.is_superuser:
            obj.user = request.user
        super().save_model(request, obj, form, change)
    
    @display(description='User', ordering='user__email')
    def display_user(self, obj):
        return format_html(
            '<span style="color: #6b7280;">{}</span>',
            obj.user.email if obj.user else 'No user'
        )
    
    @display(description='Tag', ordering='name')
    def display_tag_name(self, obj):
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 4px 12px; border-radius: 6px; font-weight: 500;">{}</span>',
            obj.color,
            obj.name
        )
    
    @display(description='Keywords', ordering='keyword_count')
    def display_keyword_count(self, obj):
        count = obj.keyword_tags.count()
        if count == 0:
            return format_html('<span style="color: #6b7280;">0 keywords</span>')
        
        url = reverse('admin:keywords_keyword_changelist') + f'?keyword_tags__tag__id__exact={obj.pk}'
        return format_html(
            '<a href="{}" style="color: #0ea5e9; text-decoration: none;">'
            '{} keyword{}</a>',
            url,
            count,
            's' if count != 1 else ''
        )
    
    @display(description='Keywords Using This Tag')
    def display_keywords_preview(self, obj):
        keywords = obj.keyword_tags.select_related('keyword', 'keyword__project').all()[:10]
        if not keywords:
            return "No keywords using this tag"
        
        keyword_list = []
        for kt in keywords:
            keyword = kt.keyword
            url = reverse('admin:keywords_keyword_change', args=[keyword.pk])
            keyword_list.append(format_html(
                '<li><a href="{}" style="color: #0ea5e9;">{}</a> '
                '<span style="color: #6b7280;">({}, Rank: #{})</span></li>',
                url,
                keyword.keyword,
                keyword.project.domain,
                keyword.rank if keyword.rank > 0 else 'NR'
            ))
        
        html = '<ul style="margin: 0; padding-left: 20px;">'
        html += ''.join(keyword_list)
        
        if obj.keyword_tags.count() > 10:
            html += format_html(
                '<li style="color: #6b7280;">... and {} more</li>',
                obj.keyword_tags.count() - 10
            )
        
        html += '</ul>'
        return format_html(html)
# Import report admin configurations
from .admin_reports import *
