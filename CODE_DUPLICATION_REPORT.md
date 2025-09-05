# Code Duplication Analysis Report

## Executive Summary
This report identifies significant code duplication patterns across the Django application codebase. The analysis covered 7 Django apps with their views, models, forms, utilities, middleware, and template tags.

## Critical Duplication Areas

### 1. View Logic Duplication (HIGH PRIORITY)

#### Permission Checks
- **Impact**: 9/9 view files affected
- **Files**: All view files in accounts, competitors, keywords, project, site_audit apps
- **Pattern**: Repeated `Q(user=request.user) | Q(members=request.user)` queries
- **Recommendation**: Create a permission mixin or decorator

#### Pagination Logic
- **Impact**: 7/9 view files affected  
- **Pattern**: Nearly identical pagination implementation across all views
```python
paginator = Paginator(items, per_page)
try:
    page_obj = paginator.page(page)
except (PageNotAnInteger, EmptyPage):
    page_obj = paginator.page(1)
```
- **Recommendation**: Extract to common pagination utility

#### HTMX Response Patterns
- **Impact**: 6/9 view files affected
- **Pattern**: Repeated HTMX request detection and partial template rendering
```python
if request.headers.get('HX-Request'):
    return render(request, 'partial_template.html', context)
return render(request, 'full_template.html', context)
```
- **Recommendation**: Create HTMX response helper functions

#### Search and Filter Logic
- **Impact**: 5/9 view files affected
- **Pattern**: Similar search query handling across views
- **Recommendation**: Create reusable search/filter mixins

### 2. Model Duplication (HIGH PRIORITY)

#### Timestamp Fields
- **Impact**: 6/7 model files affected
- **Pattern**: Repeated `created_at` and `updated_at` fields
- **Recommendation**: Create abstract TimestampedModel base class

#### Domain Cleaning Methods (EXACT DUPLICATE)
- **Files**: 
  - `competitors/models.py` (lines 22-50)
  - `project/models.py` (lines 17-45)
- **Impact**: Identical 28-line method duplicated
- **Recommendation**: Move to shared domain utilities module

#### Status Management
- **Impact**: Multiple models with status fields
- **Pattern**: Similar status choices and transition methods
- **Recommendation**: Create StatusMixin for common status operations

### 3. Service & Utility Duplication (MEDIUM PRIORITY)

#### Email Services (DUPLICATE FUNCTIONALITY)
- **Files**:
  - `/services/email_service.py` (140 lines)
  - `/project/email_service.py` (93 lines)
- **Impact**: Two separate Brevo email implementations
- **Recommendation**: Consolidate into single email service

#### Storage Services (DUPLICATE FUNCTIONALITY)  
- **Files**:
  - `/services/r2_storage.py` (comprehensive R2 service)
  - `/site_audit/r2_upload.py` (292 lines with similar logic)
  - `/services/storage_backends.py` (Django backends)
- **Impact**: Overlapping R2/storage functionality
- **Recommendation**: Create unified storage abstraction layer

#### File Handling Patterns
- **Impact**: Multiple files with similar file type detection and validation
- **Recommendation**: Create shared file utility module

### 4. Form Duplication (LOW PRIORITY)

#### Email Field Validation
- **Files**: accounts/forms.py (4 forms with similar email fields)
- **Pattern**: Repeated email field definitions with similar error messages
```python
email = forms.EmailField(
    label="Email",
    error_messages={
        'required': 'Please enter your email address',
        'invalid': 'That doesn\'t look like a valid email address'
    }
)
```
- **Recommendation**: Create custom EmailField subclass

#### ReCaptcha Integration
- **Impact**: 4 forms with identical ReCaptcha field setup
- **Recommendation**: Create ReCaptchaFormMixin

#### Domain Validation
- **Files**: project/forms.py
- **Pattern**: Domain cleaning logic similar to model methods
- **Recommendation**: Use shared domain validation utilities

### 5. Template Tags (LOW PRIORITY)

#### Dictionary Access Filters
- **Files**: site_audit/templatetags/pagespeed_filters.py
- **Pattern**: `get_item` filter for dictionary access (common pattern)
- **Recommendation**: Consider using built-in filters or creating shared template tag library

## Code Statistics

### Duplication by Category
1. **View Logic**: ~40% duplicated patterns
2. **Model Methods**: ~25% duplicated patterns
3. **Service/Utilities**: ~35% duplicated functionality
4. **Forms**: ~20% duplicated validation
5. **Middleware/Decorators**: Minimal duplication (well structured)
6. **Template Tags**: Minimal duplication

### Most Duplicated Patterns
1. Permission checking logic (50+ occurrences)
2. Pagination implementation (25+ occurrences)
3. HTMX response handling (20+ occurrences)
4. Timestamp fields (15+ models)
5. Domain cleaning/validation (3 exact duplicates)

## Recommended Refactoring Priority

### Phase 1 - High Impact (1-2 weeks)
1. **Create base mixins/classes**:
   - `PermissionMixin` for consistent access control
   - `TimestampedModel` abstract base model
   - `PaginationMixin` for views
   - `HTMXResponseMixin` for partial template handling

2. **Extract shared utilities**:
   - Move domain cleaning to `common/utils/domain.py`
   - Create `common/utils/pagination.py`
   - Consolidate file handling utilities

### Phase 2 - Medium Impact (1 week)
1. **Consolidate services**:
   - Merge email services into single module
   - Create unified storage service abstraction
   - Standardize error handling patterns

2. **Create common validators**:
   - Domain validation utilities
   - File type and size validators
   - Common form field validators

### Phase 3 - Low Impact (Optional)
1. **Form improvements**:
   - Create custom form fields for common patterns
   - Implement form mixins for shared functionality

2. **Template tag consolidation**:
   - Create shared template tag library
   - Remove redundant filters

## Implementation Guidelines

### Creating Base Classes
```python
# common/models.py
class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
```

### Creating Mixins
```python
# common/mixins.py
class PermissionMixin:
    def get_queryset(self):
        return super().get_queryset().filter(
            Q(user=self.request.user) | 
            Q(members=self.request.user)
        )
```

### Extracting Utilities
```python
# common/utils/domain.py
def clean_domain_string(domain_str):
    """Centralized domain cleaning logic"""
    # Move the 28-line duplicated method here
```

## Expected Benefits

1. **Code Reduction**: ~15-20% reduction in total code
2. **Maintenance**: Single source of truth for common operations
3. **Testing**: Easier to test centralized utilities
4. **Consistency**: Uniform behavior across the application
5. **Development Speed**: Faster feature development with reusable components

## Risks and Mitigation

1. **Risk**: Breaking existing functionality during refactoring
   - **Mitigation**: Comprehensive test coverage before refactoring

2. **Risk**: Over-abstraction making code harder to understand
   - **Mitigation**: Keep abstractions simple and well-documented

3. **Risk**: Performance impact from additional abstraction layers
   - **Mitigation**: Profile critical paths and optimize as needed

## Conclusion

The codebase shows significant opportunities for reducing duplication, particularly in view logic, model patterns, and service utilities. Implementing the recommended refactoring in phases will improve maintainability while minimizing risk to existing functionality.

Priority should be given to the most frequently duplicated patterns (permission checks, pagination, HTMX responses) as these provide the highest return on investment.