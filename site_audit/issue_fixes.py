"""
Comprehensive fix definitions for all Screaming Frog SEO issues
"""

ISSUE_FIXES = {
    # Response Code Issues (4xx, 5xx, 3xx)
    'internal_client_error_4xx': {
        'title': 'Fix 404 Error (Page Not Found)',
        'description': 'This page returns a 404 error, meaning it cannot be found.',
        'fix_steps': [
            'Check if the URL is correct and the page should exist',
            'If the page was deleted, implement a 301 redirect to a relevant page',
            'If the page should exist, restore it or fix the broken link',
            'Update or remove all internal links pointing to this URL',
            'Submit the updated sitemap to search engines'
        ],
        'impact': 'Broken links hurt user experience and waste crawl budget',
        'priority': 'critical'
    },
    
    'internal_server_error_5xx': {
        'title': 'Fix Server Error (500)',
        'description': 'This page returns a server error, preventing access.',
        'fix_steps': [
            'Check server logs for the specific error details',
            'Review recent code deployments that may have caused the issue',
            'Verify database connections and server resources',
            'Test the page functionality and fix any backend errors',
            'Monitor server performance and implement error handling'
        ],
        'impact': 'Server errors severely damage SEO and user experience',
        'priority': 'critical'
    },
    
    'internal_redirection_3xx': {
        'title': 'Fix Redirect Chain',
        'description': 'This URL is part of a redirect chain or loop.',
        'fix_steps': [
            'Map out the complete redirect chain',
            'Update links to point directly to the final destination',
            'Eliminate intermediate redirects where possible',
            'Use 301 redirects for permanent moves',
            'Update internal links and sitemap'
        ],
        'impact': 'Redirect chains slow page load and dilute link equity',
        'priority': 'high'
    },
    
    'external_client_error_4xx': {
        'title': 'Fix External Broken Link',
        'description': 'External link returns an error.',
        'fix_steps': [
            'Verify if the external site is permanently down',
            'Find an alternative resource to link to',
            'Remove the link if no alternative exists',
            'Consider using archived versions if appropriate',
            'Regularly monitor external links'
        ],
        'impact': 'Broken external links reduce page quality signals',
        'priority': 'medium'
    },
    
    'external_server_error_5xx': {
        'title': 'Fix External Server Error',
        'description': 'External link has server issues.',
        'fix_steps': [
            'Check if the error is temporary',
            'Contact the external site if possible',
            'Find alternative resources to link to',
            'Consider removing if persistently broken',
            'Set up monitoring for critical external links'
        ],
        'impact': 'Links to error pages reduce content quality',
        'priority': 'medium'
    },
    
    'external_no_response': {
        'title': 'Fix Unresponsive External Link',
        'description': 'External link does not respond.',
        'fix_steps': [
            'Verify the URL is correct',
            'Check if the site has moved to a new domain',
            'Find alternative resources',
            'Remove dead links',
            'Implement regular link checking'
        ],
        'impact': 'Dead links frustrate users and waste crawl budget',
        'priority': 'low'
    },
    
    'internal_blocked_robots': {
        'title': 'Fix Robots.txt Blocking',
        'description': 'This URL is blocked by robots.txt.',
        'fix_steps': [
            'Review robots.txt rules',
            'Determine if blocking is intentional',
            'Remove blocking if page should be indexed',
            'Use noindex meta tag instead if needed',
            'Test changes with robots.txt tester'
        ],
        'impact': 'Blocked pages cannot be indexed by search engines',
        'priority': 'high'
    },
    
    # Meta Content Issues
    'missing_title': {
        'title': 'Add Missing Page Title',
        'description': 'This page lacks a title tag, crucial for SEO.',
        'fix_steps': [
            'Add a unique, descriptive title tag to the HTML head',
            'Include primary keywords naturally',
            'Keep title between 50-60 characters',
            'Make it compelling for click-through',
            'Ensure it accurately describes page content'
        ],
        'impact': 'Title tags are critical ranking factors and appear in search results',
        'priority': 'critical'
    },
    
    'duplicate_title': {
        'title': 'Fix Duplicate Title Tag',
        'description': 'Multiple pages share the same title.',
        'fix_steps': [
            'Create unique titles for each page',
            'Include page-specific keywords',
            'Add modifiers like location, year, or category',
            'Review site architecture for duplicate content',
            'Consider canonical tags if appropriate'
        ],
        'impact': 'Duplicate titles confuse search engines and reduce rankings',
        'priority': 'high'
    },
    
    'title_too_long': {
        'title': 'Shorten Title Tag',
        'description': 'Title exceeds recommended length.',
        'fix_steps': [
            'Reduce title to 50-60 characters',
            'Keep most important keywords at the beginning',
            'Remove unnecessary words or brand repetition',
            'Test appearance in search results preview',
            'Maintain readability and click appeal'
        ],
        'impact': 'Long titles get truncated in search results',
        'priority': 'medium'
    },
    
    'title_too_short': {
        'title': 'Expand Title Tag',
        'description': 'Title is too short to be descriptive.',
        'fix_steps': [
            'Expand title to at least 30 characters',
            'Add relevant keywords and modifiers',
            'Include brand name if space permits',
            'Make it descriptive and compelling',
            'Avoid keyword stuffing'
        ],
        'impact': 'Short titles miss ranking opportunities',
        'priority': 'medium'
    },
    
    'missing_meta_description': {
        'title': 'Add Meta Description',
        'description': 'Page lacks a meta description.',
        'fix_steps': [
            'Write unique 150-160 character description',
            'Include target keywords naturally',
            'Add compelling call-to-action',
            'Accurately summarize page content',
            'Make it click-worthy for search results'
        ],
        'impact': 'Meta descriptions improve click-through rates',
        'priority': 'high'
    },
    
    'duplicate_meta_description': {
        'title': 'Fix Duplicate Meta Description',
        'description': 'Multiple pages share the same description.',
        'fix_steps': [
            'Write unique descriptions for each page',
            'Focus on page-specific value propositions',
            'Include different keywords for each page',
            'Review for duplicate content issues',
            'Test click-through rate improvements'
        ],
        'impact': 'Unique descriptions improve search visibility',
        'priority': 'high'
    },
    
    'meta_too_long': {
        'title': 'Shorten Meta Description',
        'description': 'Description exceeds recommended length.',
        'fix_steps': [
            'Reduce to 150-160 characters',
            'Keep key message in first 120 characters',
            'Remove redundant information',
            'Maintain compelling call-to-action',
            'Test in search preview tools'
        ],
        'impact': 'Long descriptions get truncated in results',
        'priority': 'medium'
    },
    
    'meta_too_short': {
        'title': 'Expand Meta Description',
        'description': 'Description is too brief.',
        'fix_steps': [
            'Expand to at least 120 characters',
            'Add more detail about page content',
            'Include relevant keywords',
            'Add compelling reasons to click',
            'Describe unique value proposition'
        ],
        'impact': 'Short descriptions miss engagement opportunities',
        'priority': 'medium'
    },
    
    # Heading Issues
    'missing_h1': {
        'title': 'Add H1 Heading',
        'description': 'Page lacks a primary H1 heading.',
        'fix_steps': [
            'Add one clear H1 heading per page',
            'Include primary target keywords',
            'Make it descriptive of page content',
            'Place it prominently on the page',
            'Ensure it differs from the title tag'
        ],
        'impact': 'H1 tags help search engines understand page topic',
        'priority': 'high'
    },
    
    'duplicate_h1': {
        'title': 'Fix Duplicate H1',
        'description': 'Multiple pages have identical H1 headings.',
        'fix_steps': [
            'Create unique H1 for each page',
            'Reflect specific page content',
            'Include page-specific keywords',
            'Review site structure for duplicates',
            'Consider content consolidation if needed'
        ],
        'impact': 'Unique H1s improve content differentiation',
        'priority': 'medium'
    },
    
    'multiple_h1': {
        'title': 'Fix Multiple H1 Tags',
        'description': 'Page has more than one H1 tag.',
        'fix_steps': [
            'Keep only one H1 per page',
            'Convert others to H2 or H3',
            'Ensure proper heading hierarchy',
            'Make H1 the main page topic',
            'Use subheadings for sections'
        ],
        'impact': 'Multiple H1s confuse page hierarchy',
        'priority': 'medium'
    },
    
    'missing_h2': {
        'title': 'Add H2 Subheadings',
        'description': 'Page lacks H2 subheadings for structure.',
        'fix_steps': [
            'Add H2 tags for main sections',
            'Create logical content hierarchy',
            'Include secondary keywords',
            'Improve content scannability',
            'Break up long content blocks'
        ],
        'impact': 'Subheadings improve readability and SEO',
        'priority': 'low'
    },
    
    # Image Issues
    'missing_alt_text': {
        'title': 'Add Image Alt Text',
        'description': 'Images lack alt text for accessibility.',
        'fix_steps': [
            'Add descriptive alt text to all images',
            'Include relevant keywords naturally',
            'Describe image content accurately',
            'Keep alt text concise but descriptive',
            'Use empty alt="" for decorative images'
        ],
        'impact': 'Alt text improves accessibility and image SEO',
        'priority': 'medium'
    },
    
    'large_image_size': {
        'title': 'Optimize Large Images',
        'description': 'Images are too large and slow loading.',
        'fix_steps': [
            'Compress images without quality loss',
            'Use appropriate formats (WebP, JPEG, PNG)',
            'Implement lazy loading',
            'Serve responsive image sizes',
            'Use CDN for image delivery'
        ],
        'impact': 'Large images slow page speed and hurt rankings',
        'priority': 'high'
    },
    
    # Technical SEO Issues
    'missing_canonical': {
        'title': 'Add Canonical Tag',
        'description': 'Page lacks canonical URL specification.',
        'fix_steps': [
            'Add canonical tag to HTML head',
            'Point to preferred version of page',
            'Use absolute URLs',
            'Ensure consistency across pages',
            'Review for duplicate content'
        ],
        'impact': 'Canonical tags prevent duplicate content issues',
        'priority': 'high'
    },
    
    'noindex': {
        'title': 'Review Noindex Tag',
        'description': 'Page is set to noindex.',
        'fix_steps': [
            'Verify if noindex is intentional',
            'Remove if page should be indexed',
            'Check robots.txt compatibility',
            'Submit to search console if changed',
            'Monitor indexation status'
        ],
        'impact': 'Noindex pages cannot rank in search results',
        'priority': 'info'
    },
    
    'mixed_content': {
        'title': 'Fix Mixed Content (HTTPS/HTTP)',
        'description': 'Page loads insecure HTTP resources.',
        'fix_steps': [
            'Update all resources to HTTPS',
            'Fix hardcoded HTTP links',
            'Update external resource URLs',
            'Implement Content Security Policy',
            'Test thoroughly after changes'
        ],
        'impact': 'Mixed content triggers browser warnings',
        'priority': 'critical'
    },
    
    'missing_hsts_header': {
        'title': 'Add HSTS Security Header',
        'description': 'Site lacks HTTP Strict Transport Security.',
        'fix_steps': [
            'Configure HSTS header on server',
            'Set appropriate max-age directive',
            'Include subdomains if applicable',
            'Test implementation carefully',
            'Consider HSTS preload list'
        ],
        'impact': 'HSTS improves security and SEO trust',
        'priority': 'critical'
    },
    
    # URL Issues
    'url_uppercase': {
        'title': 'Fix Uppercase URLs',
        'description': 'URLs contain uppercase characters.',
        'fix_steps': [
            'Convert URLs to lowercase',
            'Implement 301 redirects from old URLs',
            'Update all internal links',
            'Configure server for case-insensitive',
            'Update sitemap with new URLs'
        ],
        'impact': 'Uppercase URLs can cause duplicate content',
        'priority': 'medium'
    },
    
    'url_underscores': {
        'title': 'Replace URL Underscores',
        'description': 'URLs use underscores instead of hyphens.',
        'fix_steps': [
            'Replace underscores with hyphens',
            'Set up 301 redirects',
            'Update internal linking',
            'Update external backlinks if possible',
            'Submit updated sitemap'
        ],
        'impact': 'Search engines prefer hyphens in URLs',
        'priority': 'medium'
    },
    
    'url_parameters': {
        'title': 'Handle URL Parameters',
        'description': 'URLs contain parameters that may cause issues.',
        'fix_steps': [
            'Review parameter necessity',
            'Implement canonical tags',
            'Configure parameter handling in Search Console',
            'Consider URL rewriting',
            'Use robots.txt if appropriate'
        ],
        'impact': 'Parameters can create duplicate content',
        'priority': 'info'
    },
    
    # Content Issues
    'low_content_pages': {
        'title': 'Add More Content',
        'description': 'Page has insufficient content.',
        'fix_steps': [
            'Expand content to 300+ words minimum',
            'Add valuable, unique information',
            'Include relevant keywords naturally',
            'Add supporting media if relevant',
            'Consider combining thin pages'
        ],
        'impact': 'Thin content provides little value to users',
        'priority': 'medium'
    },
    
    'readability_difficult': {
        'title': 'Improve Content Readability',
        'description': 'Content is difficult to read.',
        'fix_steps': [
            'Use shorter sentences and paragraphs',
            'Add subheadings and bullet points',
            'Simplify complex vocabulary',
            'Increase white space',
            'Target 8th-grade reading level'
        ],
        'impact': 'Poor readability increases bounce rate',
        'priority': 'low'
    },
    
    # Pagination Issues
    'pagination_sequence_error': {
        'title': 'Fix Pagination Sequence',
        'description': 'Pagination has sequencing issues.',
        'fix_steps': [
            'Verify rel="prev" and rel="next" tags',
            'Ensure sequential numbering',
            'Fix broken pagination links',
            'Implement view-all page if appropriate',
            'Add pagination markup'
        ],
        'impact': 'Broken pagination confuses crawlers',
        'priority': 'low'
    }
}

def get_fix_for_issue(issue_type):
    """
    Get fix information for a specific issue type
    
    Args:
        issue_type: The type of issue from Screaming Frog
    
    Returns:
        Dictionary with fix information or generic fix
    """
    # Try exact match
    if issue_type in ISSUE_FIXES:
        return ISSUE_FIXES[issue_type]
    
    # Try partial match
    issue_lower = issue_type.lower()
    for key, fix in ISSUE_FIXES.items():
        if key in issue_lower or issue_lower in key:
            return fix
    
    # Return generic fix for unknown issues
    return {
        'title': 'Review and Fix Issue',
        'description': f'Issue detected: {issue_type}',
        'fix_steps': [
            'Review the specific issue details',
            'Consult SEO best practices',
            'Implement appropriate fix',
            'Test the changes',
            'Monitor for improvements'
        ],
        'impact': 'This issue may affect SEO performance',
        'priority': 'medium'
    }