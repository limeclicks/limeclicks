"""
Issue Templates for Site Audit

This module contains predefined issue templates with descriptions and resolutions
for common SEO and technical issues found during site audits.
"""

ISSUE_TEMPLATES = {
    # Critical Issues (Show-stoppers for SEO)
    'missing_title': {
        'severity': 'critical',
        'category': 'metadata',
        'description': 'Page has no title tag',
        'impact': 'Pages without title tags will not rank well in search results',
        'resolution': """
1. Add a unique, descriptive title tag to the page
2. Keep title between 50-60 characters
3. Include primary keyword near the beginning
4. Make it compelling to encourage clicks
5. Ensure each page has a unique title

Example:
<title>Primary Keyword - Secondary Keyword | Brand Name</title>
        """,
    },
    
    'duplicate_title': {
        'severity': 'critical',
        'category': 'metadata',
        'description': 'Multiple pages have the same title tag',
        'impact': 'Search engines may ignore duplicate pages or show the wrong page',
        'resolution': """
1. Create unique titles for each page
2. Include page-specific keywords
3. Add unique identifiers (page number, category, etc.)
4. Review site structure to avoid duplicate content

Tips:
- For category pages: "Category Name - Page X | Brand"
- For products: "Product Name - Category | Brand"
- For blog posts: "Post Title - Blog | Brand"
        """,
    },
    
    'missing_meta_description': {
        'severity': 'critical',
        'category': 'metadata',
        'description': 'Page has no meta description',
        'impact': 'Missing opportunity to control snippet in search results',
        'resolution': """
1. Add a compelling meta description
2. Keep it between 150-160 characters
3. Include target keywords naturally
4. Write for humans, not search engines
5. Include a call-to-action

Example:
<meta name="description" content="Compelling description with keywords and CTA">
        """,
    },
    
    'broken_internal_link': {
        'severity': 'critical',
        'category': 'technical',
        'description': 'Internal link is broken (404 error)',
        'impact': 'Poor user experience and wasted link equity',
        'resolution': """
1. Fix or remove all broken links
2. Update links to moved content
3. Implement 301 redirects for moved pages
4. Set up regular link monitoring
5. Use relative URLs when possible

Tools:
- Check Google Search Console for 404 errors
- Use link checking tools regularly
- Implement proper redirect chains
        """,
    },
    
    # High Priority Issues
    'title_too_long': {
        'severity': 'high',
        'category': 'metadata',
        'description': 'Title tag exceeds 60 characters',
        'impact': 'Title will be truncated in search results',
        'resolution': """
1. Shorten title to 50-60 characters
2. Put important keywords first
3. Remove unnecessary words
4. Use symbols instead of words where appropriate
5. Test appearance in SERP preview tools
        """,
    },
    
    'meta_description_too_long': {
        'severity': 'high',
        'category': 'metadata',
        'description': 'Meta description exceeds 160 characters',
        'impact': 'Description will be truncated in search results',
        'resolution': """
1. Shorten to 150-160 characters
2. Front-load important information
3. Remove redundant phrases
4. Keep the call-to-action intact
5. Test in SERP preview tools
        """,
    },
    
    'missing_h1': {
        'severity': 'high',
        'category': 'content',
        'description': 'Page has no H1 heading tag',
        'impact': 'Missing important SEO signal and structure',
        'resolution': """
1. Add exactly one H1 tag per page
2. Include primary keyword in H1
3. Make it descriptive and relevant
4. Place it near the top of content
5. Keep it different from the title tag

Best Practices:
- H1 should describe page content
- Use H2-H6 for subheadings
- Maintain proper heading hierarchy
        """,
    },
    
    'duplicate_h1': {
        'severity': 'high',
        'category': 'content',
        'description': 'Page has multiple H1 tags',
        'impact': 'Confuses search engines about main topic',
        'resolution': """
1. Keep only one H1 tag per page
2. Convert other H1s to H2 or H3
3. Maintain proper heading hierarchy
4. Use H1 for main topic only
5. Use subheadings for sections

Proper Structure:
- H1: Main page topic
- H2: Major sections
- H3: Subsections
- H4-H6: Further subdivisions
        """,
    },
    
    'missing_canonical': {
        'severity': 'high',
        'category': 'technical',
        'description': 'Page missing canonical URL tag',
        'impact': 'Risk of duplicate content issues',
        'resolution': """
1. Add canonical tag to all pages
2. Point to the preferred URL version
3. Use absolute URLs in canonical tags
4. Ensure consistency across redirects
5. Validate canonical implementation

Example:
<link rel="canonical" href="https://example.com/preferred-url/">
        """,
    },
    
    # Medium Priority Issues
    'thin_content': {
        'severity': 'medium',
        'category': 'content',
        'description': 'Page has insufficient content (under 300 words)',
        'impact': 'May be considered low quality by search engines',
        'resolution': """
1. Add more valuable content (aim for 500+ words)
2. Include relevant information users seek
3. Add FAQs, guides, or resources
4. Include multimedia content
5. Ensure content matches search intent

Content Ideas:
- Answer common questions
- Provide detailed explanations
- Include examples and case studies
- Add related resources
- Create comprehensive guides
        """,
    },
    
    'missing_alt_text': {
        'severity': 'medium',
        'category': 'accessibility',
        'description': 'Images missing alt attributes',
        'impact': 'Poor accessibility and missed SEO opportunity',
        'resolution': """
1. Add descriptive alt text to all images
2. Include keywords naturally
3. Keep alt text concise but descriptive
4. Use empty alt="" for decorative images
5. Describe image content and context

Examples:
<img src="product.jpg" alt="Red running shoes with white laces">
<img src="decoration.jpg" alt=""> <!-- Decorative image -->
        """,
    },
    
    'redirect_chain': {
        'severity': 'medium',
        'category': 'technical',
        'description': 'Multiple redirects in sequence',
        'impact': 'Slower page loads and diluted link equity',
        'resolution': """
1. Redirect directly to final destination
2. Update all internal links
3. Fix chains to use single 301 redirect
4. Monitor for new redirect chains
5. Document redirect rules

Best Practice:
Old URL → Final URL (single 301 redirect)
Avoid: URL1 → URL2 → URL3 → Final URL
        """,
    },
    
    # Low Priority Issues
    'missing_structured_data': {
        'severity': 'low',
        'category': 'technical',
        'description': 'Page lacks structured data markup',
        'impact': 'Missing rich snippet opportunities',
        'resolution': """
1. Add appropriate Schema.org markup
2. Use JSON-LD format (recommended)
3. Test with Google's Rich Results Test
4. Implement relevant schemas:
   - Organization
   - Product
   - Article
   - LocalBusiness
   - FAQ
   - HowTo

Example:
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Company Name",
  "url": "https://example.com"
}
</script>
        """,
    },
    
    'external_nofollow': {
        'severity': 'info',
        'category': 'links',
        'description': 'External links should use rel="nofollow"',
        'impact': 'May pass link equity to external sites',
        'resolution': """
1. Add rel="nofollow" to untrusted links
2. Use for user-generated content
3. Consider rel="sponsored" for ads
4. Use rel="ugc" for user content
5. Keep follow for trusted sources

Examples:
<a href="external.com" rel="nofollow">Untrusted Link</a>
<a href="trusted.com">Trusted Source</a>
        """,
    },
}


def get_issue_template(issue_type):
    """Get issue template by type"""
    return ISSUE_TEMPLATES.get(issue_type, {
        'severity': 'medium',
        'category': 'other',
        'description': 'Unknown issue type',
        'impact': 'May affect SEO performance',
        'resolution': 'Review and fix the identified issue',
    })


def get_severity(issue_type):
    """Get issue severity"""
    template = get_issue_template(issue_type)
    return template.get('severity', 'medium')


def get_resolution(issue_type):
    """Get issue resolution"""
    template = get_issue_template(issue_type)
    return template.get('resolution', '')


def get_impact(issue_type):
    """Get issue impact"""
    template = get_issue_template(issue_type)
    return template.get('impact', '')


def get_category(issue_type):
    """Get issue category"""
    template = get_issue_template(issue_type)
    return template.get('category', 'other')