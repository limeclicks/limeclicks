"""
Helper functions to generate realistic SERP test data
"""

from datetime import datetime
from typing import Dict, List, Any, Optional


def create_realistic_serp_results(
    domain: str = "example.com",
    keyword: str = "python tutorial",
    rank_position: Optional[int] = None,
    include_features: bool = True,
    num_results: int = 10
) -> Dict[str, Any]:
    """
    Create realistic SERP results matching GoogleSearchParser output
    
    Args:
        domain: Domain to include in results (if rank_position is set)
        keyword: Search keyword for context
        rank_position: Position where domain should appear (1-100, None for not ranked)
        include_features: Whether to include SERP features
        num_results: Number of organic results to generate
    
    Returns:
        Realistic SERP data structure
    """
    
    # Common domains that appear in search results
    competitor_domains = [
        "w3schools.com",
        "realpython.com",
        "python.org",
        "geeksforgeeks.org",
        "tutorialspoint.com",
        "stackoverflow.com",
        "medium.com",
        "dev.to",
        "github.com",
        "youtube.com",
        "udemy.com",
        "coursera.org",
        "freecodecamp.org",
        "codecademy.com",
        "programiz.com"
    ]
    
    # Generate organic results
    organic_results = []
    domain_inserted = False
    
    for i in range(1, min(num_results + 1, 101)):  # Max 100 results
        # Insert our domain at the specified position
        if rank_position and i == rank_position and not domain_inserted:
            organic_results.append({
                'position': i,
                'title': f"Learn {keyword.title()} - Best Guide | {domain.title()}",
                'url': f"https://{domain}/{keyword.replace(' ', '-')}/",
                'displayed_url': f"{domain} › {keyword.replace(' ', '-')}",
                'description': f"Comprehensive guide to {keyword}. Learn everything you need to know about {keyword} with practical examples and best practices. Start your journey today!",
                'favicon': f"https://{domain}/favicon.ico",
                'cached_url': f"https://webcache.googleusercontent.com/search?q=cache:xyz{i}:{domain}",
                'date': None,
                'sitelinks': []
            })
            domain_inserted = True
        else:
            # Generate competitor result
            comp_domain = competitor_domains[(i - 1) % len(competitor_domains)]
            organic_results.append({
                'position': i,
                'title': f"{keyword.title()} - {comp_domain.split('.')[0].title()} Tutorial",
                'url': f"https://{comp_domain}/learn/{keyword.replace(' ', '-')}",
                'displayed_url': f"{comp_domain} › learn › {keyword.replace(' ', '-')}",
                'description': f"Learn {keyword} from scratch. This tutorial covers all the basics of {keyword} with step-by-step examples and exercises. Perfect for beginners!",
                'favicon': f"https://{comp_domain}/favicon.ico",
                'cached_url': f"https://webcache.googleusercontent.com/search?q=cache:abc{i}:{comp_domain}",
                'date': None,
                'sitelinks': []
            })
    
    # Generate sponsored results
    sponsored_results = []
    if include_features:
        sponsored_results = [
            {
                'position': 1,
                'title': f"Online {keyword.title()} Course - 90% Off Today",
                'url': "https://www.udemy.com/course/complete-python-bootcamp",
                'displayed_url': "Ad · www.udemy.com",
                'description': "Master Python programming from zero to hero. Join 500,000+ students. Certificate included.",
                'is_ad': True
            },
            {
                'position': 2,
                'title': f"Professional {keyword.title()} Training",
                'url': "https://www.coursera.org/learn/python",
                'displayed_url': "Ad · www.coursera.org",
                'description': "University-level Python courses. Learn from top instructors. Financial aid available.",
                'is_ad': True
            }
        ]
    
    # Build the complete response structure
    response = {
        'organic_results': organic_results,
        'sponsored_results': sponsored_results,
        'total_results': "About 234,000,000 results",
        'search_time': "0.42 seconds",
        'organic_count': len(organic_results),
        'sponsored_count': len(sponsored_results),
        'results': organic_results,  # Backward compatibility
    }
    
    # Add SERP features if requested
    if include_features:
        response['related_searches'] = [
            f"{keyword} for beginners",
            f"{keyword} advanced",
            f"best {keyword} resources",
            f"{keyword} examples",
            f"{keyword} documentation",
            f"free {keyword} course",
            f"{keyword} projects",
            f"{keyword} cheat sheet"
        ]
        
        response['people_also_ask'] = [
            {
                'question': f"What is {keyword}?",
                'snippet': f"{keyword.title()} is a powerful concept that helps developers build better applications.",
                'source': "stackoverflow.com",
                'source_url': "https://stackoverflow.com/questions/example"
            },
            {
                'question': f"How do I start learning {keyword}?",
                'snippet': f"The best way to learn {keyword} is to start with basic concepts and practice regularly.",
                'source': "reddit.com",
                'source_url': "https://reddit.com/r/learnprogramming"
            },
            {
                'question': f"Is {keyword} worth learning in 2024?",
                'snippet': f"Yes, {keyword} remains highly relevant and in-demand in 2024.",
                'source': "dev.to",
                'source_url': "https://dev.to/article/example"
            },
            {
                'question': f"What are the best resources for {keyword}?",
                'snippet': "Top resources include official documentation, online courses, and interactive tutorials.",
                'source': "github.com",
                'source_url': "https://github.com/awesome-lists"
            }
        ]
        
        response['featured_snippet'] = {
            'text': f"{keyword.title()} is an essential skill for modern developers. It provides powerful tools and frameworks for building scalable applications. Key benefits include ease of learning, vast ecosystem, and strong community support.",
            'source': "python.org",
            'source_url': "https://www.python.org/about/",
            'type': "paragraph"
        }
        
        response['videos'] = [
            {
                'title': f"{keyword.title()} Full Course for Beginners",
                'url': "https://www.youtube.com/watch?v=example1",
                'source': "YouTube",
                'duration': "4:30:00",
                'thumbnail': "https://i.ytimg.com/vi/example1/maxresdefault.jpg",
                'channel': "Programming with Mosh",
                'date': "2 months ago",
                'views': "2.3M views"
            },
            {
                'title': f"Learn {keyword} in 60 Minutes",
                'url': "https://www.youtube.com/watch?v=example2",
                'source': "YouTube",
                'duration': "1:02:15",
                'thumbnail': "https://i.ytimg.com/vi/example2/maxresdefault.jpg",
                'channel': "Traversy Media",
                'date': "3 weeks ago",
                'views': "450K views"
            }
        ]
        
        response['local_pack'] = [
            {
                'name': f"{keyword.title()} Bootcamp NYC",
                'rating': 4.8,
                'reviews': 234,
                'address': "123 Tech St, New York, NY 10001",
                'phone': "(212) 555-0123",
                'hours': "Mon-Fri 9AM-6PM",
                'website': "https://bootcamp.example.com"
            },
            {
                'name': "Code Academy Training Center",
                'rating': 4.9,
                'reviews': 567,
                'address': "456 Learning Ave, New York, NY 10002",
                'phone': "(212) 555-0456",
                'hours': "Mon-Sat 8AM-8PM",
                'website': "https://codeacademy.example.com"
            }
        ]
        
        response['images'] = {
            'results': [
                {
                    'thumbnail': "https://example.com/images/python-logo.jpg",
                    'source': "python.org",
                    'title': "Python Programming Language"
                },
                {
                    'thumbnail': "https://example.com/images/code-example.png",
                    'source': "github.com",
                    'title': f"{keyword} Code Examples"
                }
            ]
        }
    
    return response


def create_empty_serp_results(keyword: str = "test keyword") -> Dict[str, Any]:
    """
    Create empty SERP results (no results found scenario)
    
    Args:
        keyword: Search keyword for context
    
    Returns:
        Empty SERP data structure
    """
    return {
        'organic_results': [],
        'sponsored_results': [],
        'total_results': "About 0 results",
        'search_time': "0.23 seconds",
        'related_searches': [],
        'people_also_ask': [],
        'featured_snippet': None,
        'knowledge_panel': None,
        'organic_count': 0,
        'sponsored_count': 0,
        'results': []
    }


def create_sponsored_only_results(
    domain: str = "example.com",
    keyword: str = "buy widgets online"
) -> Dict[str, Any]:
    """
    Create SERP results with domain only in sponsored results
    
    Args:
        domain: Domain to include in sponsored results
        keyword: Search keyword for context
    
    Returns:
        SERP data with domain in ads only
    """
    response = create_realistic_serp_results(
        domain="competitor.com",
        keyword=keyword,
        rank_position=None,  # Not in organic
        include_features=False,
        num_results=10
    )
    
    # Add our domain to sponsored results
    response['sponsored_results'] = [
        {
            'position': 1,
            'title': f"Best {keyword.title()} - {domain.title()}",
            'url': f"https://{domain}/shop/{keyword.replace(' ', '-')}",
            'displayed_url': f"Ad · {domain}",
            'description': f"Premium quality {keyword}. Free shipping on orders over $50. Shop now!",
            'is_ad': True
        },
        {
            'position': 2,
            'title': "Discount Widgets Store",
            'url': "https://discountwidgets.com",
            'displayed_url': "Ad · discountwidgets.com",
            'description': "Lowest prices guaranteed. 30-day returns. Shop widgets today!",
            'is_ad': True
        }
    ]
    response['sponsored_count'] = len(response['sponsored_results'])
    
    return response


def create_serp_with_all_features(
    domain: str = "example.com",
    rank_position: int = 3
) -> Dict[str, Any]:
    """
    Create SERP results with all possible features for comprehensive testing
    
    Args:
        domain: Domain to test
        rank_position: Where domain appears in organic results
    
    Returns:
        SERP data with maximum features
    """
    response = create_realistic_serp_results(
        domain=domain,
        keyword="python programming guide",
        rank_position=rank_position,
        include_features=True,
        num_results=20
    )
    
    # Add additional features
    response['knowledge_panel'] = {
        'title': "Python (programming language)",
        'subtitle': "High-level programming language",
        'description': "Python is a high-level, interpreted programming language with dynamic semantics.",
        'image': "https://upload.wikimedia.org/wikipedia/commons/python-logo.png",
        'facts': {
            'Designed by': "Guido van Rossum",
            'First appeared': "1991",
            'Stable release': "3.12.0",
            'Typing discipline': "Duck, dynamic, strong typing",
            'OS': "Cross-platform",
            'License': "Python Software Foundation License"
        },
        'source': "Wikipedia",
        'source_url': "https://en.wikipedia.org/wiki/Python_(programming_language)"
    }
    
    response['top_stories'] = [
        {
            'title': "Python 3.12 Released with Major Performance Improvements",
            'source': "Python.org",
            'date': "2 days ago",
            'url': "https://python.org/news/python-312-release",
            'thumbnail': "https://python.org/images/news-thumb.jpg"
        },
        {
            'title': "Why Python Remains the Top Language for AI Development",
            'source': "TechCrunch",
            'date': "1 week ago",
            'url': "https://techcrunch.com/python-ai-development",
            'thumbnail': "https://techcrunch.com/images/python-ai.jpg"
        }
    ]
    
    response['shopping'] = [
        {
            'title': "Python Programming Book",
            'price': "$39.99",
            'source': "Amazon",
            'rating': 4.5,
            'reviews': 1234,
            'url': "https://amazon.com/dp/example",
            'image': "https://amazon.com/images/book.jpg"
        }
    ]
    
    response['twitter'] = [
        {
            'username': "@gvanrossum",
            'handle': "Guido van Rossum",
            'tweet': "Excited about the new features in Python 3.12!",
            'date': "3 hours ago",
            'likes': 5234,
            'retweets': 892,
            'url': "https://twitter.com/gvanrossum/status/example"
        }
    ]
    
    return response


def create_test_scenarios() -> List[Dict[str, Any]]:
    """
    Create a variety of test scenarios for comprehensive testing
    
    Returns:
        List of test scenarios with different configurations
    """
    return [
        {
            'name': 'Domain ranked #1',
            'domain': 'pythontutorial.net',
            'keyword': 'python basics',
            'data': create_realistic_serp_results('pythontutorial.net', 'python basics', 1)
        },
        {
            'name': 'Domain ranked #10',
            'domain': 'learnpython.org',
            'keyword': 'python advanced topics',
            'data': create_realistic_serp_results('learnpython.org', 'python advanced topics', 10)
        },
        {
            'name': 'Domain ranked #50',
            'domain': 'mypythonblog.com',
            'keyword': 'python web scraping',
            'data': create_realistic_serp_results('mypythonblog.com', 'python web scraping', 50)
        },
        {
            'name': 'Domain not ranked',
            'domain': 'newsite.com',
            'keyword': 'competitive keyword',
            'data': create_realistic_serp_results('newsite.com', 'competitive keyword', None)
        },
        {
            'name': 'Domain in sponsored only',
            'domain': 'pythoncourse.com',
            'keyword': 'python certification',
            'data': create_sponsored_only_results('pythoncourse.com', 'python certification')
        },
        {
            'name': 'No results found',
            'domain': 'example.com',
            'keyword': 'xyzabc123nonexistent',
            'data': create_empty_serp_results('xyzabc123nonexistent')
        },
        {
            'name': 'All features present',
            'domain': 'python.org',
            'keyword': 'python programming',
            'data': create_serp_with_all_features('python.org', 2)
        }
    ]