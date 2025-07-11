"""RSS feed samples for testing with dynamic dates"""

from datetime import UTC, datetime, timedelta


def _get_recent_date_str(days_ago=1, hours_offset=0):
    """Generate a date string for testing that's always recent"""
    date = datetime.now(UTC) - timedelta(days=days_ago, hours=hours_offset)
    return date.strftime("%a, %d %b %Y %H:%M:%S GMT")


def _get_old_date_str():
    """Generate a date string that's always older than max_age_days"""
    date = datetime.now(UTC) - timedelta(days=30)
    return date.strftime("%a, %d %b %Y %H:%M:%S GMT")


# TechCrunch AI feed sample
def get_techcrunch_rss():
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>TechCrunch - Artificial Intelligence</title>
        <link>https://techcrunch.com/category/artificial-intelligence/</link>
        <description>Startup and Technology News</description>  # noqa: E501
        <item>
            <title>OpenAI launches new GPT-5 model with enhanced capabilities</title>
            <link>https://techcrunch.com/2024/01/15/openai-gpt5-launch/</link>
            <description>OpenAI has announced the release of GPT-5, featuring improved reasoning and multimodal capabilities...</description>  # noqa: E501
            <pubDate>{_get_recent_date_str()}</pubDate>
            <author>tech@techcrunch.com (Sarah Johnson)</author>
            <guid>https://techcrunch.com/?p=123456</guid>
        </item>
        <item>
            <title>AI startup raises $100M to revolutionize healthcare</title>
            <link>https://techcrunch.com/2024/01/14/ai-health-funding/</link>
            <description>MedAI, a startup using artificial intelligence for medical diagnosis, has secured $100 million in Series B funding...</description>  # noqa: E501
            <pubDate>{_get_recent_date_str(days_ago=1, hours_offset=4)}</pubDate>
            <author>tech@techcrunch.com (Mike Chen)</author>
            <guid>https://techcrunch.com/?p=123457</guid>
        </item>
    </channel>
</rss>"""


# The Verge AI feed sample
def get_verge_rss():
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>The Verge - AI</title>
        <link>https://www.theverge.com/ai-artificial-intelligence</link>
        <description>AI news from The Verge</description>  # noqa: E501
        <item>
            <title>Google's new AI model challenges ChatGPT dominance</title>
            <link>https://www.theverge.com/2024/1/15/google-ai-model</link>
            <description><![CDATA[Google has unveiled its latest AI model that promises to rival OpenAI's ChatGPT...]]></description>  # noqa: E501
            <pubDate>{_get_recent_date_str()}</pubDate>
            <author>Jane Smith</author>
            <guid>https://www.theverge.com/2024/1/15/google-ai-model</guid>
        </item>
    </channel>
</rss>"""


# ArXiv AI feed sample (note different structure)
def get_arxiv_rss():
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns="http://purl.org/rss/1.0/"
         xmlns:dc="http://purl.org/dc/elements/1.1/">
    <channel rdf:about="http://arxiv.org/rss/cs.AI">
        <title>cs.AI updates on arXiv.org</title>
        <link>http://arxiv.org/rss/cs.AI</link>
        <description>Computer Science - Artificial Intelligence</description>  # noqa: E501
    </channel>
    <item rdf:about="http://arxiv.org/abs/2401.12345">
        <title>Efficient Transformer Architecture for Large Language Models</title>
        <link>http://arxiv.org/abs/2401.12345</link>
        <description>We present a novel transformer architecture that reduces computational complexity...</description>  # noqa: E501
        <dc:creator>John Doe, Jane Smith, Bob Johnson</dc:creator>
        <dc:date>{datetime.now(UTC).replace(hour=9, minute=0, second=0).isoformat()}</dc:date>  # noqa: E501
    </item>
    <item rdf:about="http://arxiv.org/abs/2401.12346">
        <title>Reinforcement Learning in Complex Environments</title>
        <link>http://arxiv.org/abs/2401.12346</link>
        <description>This paper explores new approaches to reinforcement learning...</description>  # noqa: E501
        <dc:creator>Alice Chen, David Wilson</dc:creator>
        <dc:date>{(datetime.now(UTC) - timedelta(hours=6)).isoformat()}</dc:date>
    </item>
</rdf:RDF>"""


# OpenAI Blog feed sample
def get_openai_rss():
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>OpenAI Blog</title>
        <link>https://openai.com/blog/</link>
        <description>Latest updates from OpenAI</description>  # noqa: E501
        <item>
            <title>Introducing GPT-5: Our Most Capable Model</title>
            <link>https://openai.com/blog/gpt-5</link>
            <description>Today we're releasing GPT-5, our most capable and aligned model to date...</description>  # noqa: E501
            <pubDate>{_get_recent_date_str()}</pubDate>
            <guid>https://openai.com/blog/gpt-5</guid>
        </item>
    </channel>
</rss>"""


# Anthropic Blog feed sample
def get_anthropic_rss():
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>Anthropic Blog</title>
        <link>https://www.anthropic.com/blog</link>
        <description>News and research from Anthropic</description>  # noqa: E501
        <item>
            <title>Claude 3: Enhanced Safety and Capabilities</title>
            <link>https://www.anthropic.com/blog/claude-3</link>
            <description>We're excited to announce Claude 3, featuring improved safety measures...</description>  # noqa: E501
            <pubDate>{_get_recent_date_str()}</pubDate>
            <author>Anthropic Team</author>
            <guid>https://www.anthropic.com/blog/claude-3</guid>
        </item>
    </channel>
</rss>"""


# Old article for testing age filtering
def get_old_article_rss():
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>Test Feed</title>
        <item>
            <title>Old AI News Article</title>
            <link>https://example.com/old-article</link>
            <description>This article is too old and should be filtered out...</description>  # noqa: E501
            <pubDate>{_get_old_date_str()}</pubDate>
        </item>
        <item>
            <title>Recent AI Development</title>
            <link>https://example.com/recent-article</link>
            <description>This is a recent article that should be included...</description>  # noqa: E501
            <pubDate>{_get_recent_date_str()}</pubDate>
        </item>
    </channel>
</rss>"""


# Duplicate articles for deduplication testing
def get_duplicate_rss():
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>Test Feed</title>
        <item>
            <title>Breaking: Major AI Breakthrough</title>
            <link>https://example.com/ai-breakthrough</link>
            <description>Scientists announce major breakthrough in AI...</description>  # noqa: E501
            <pubDate>{_get_recent_date_str()}</pubDate>
        </item>
        <item>
            <title>Breaking: Major AI Breakthrough</title>
            <link>https://example.com/ai-breakthrough</link>
            <description>Scientists announce major breakthrough in AI...</description>  # noqa: E501
            <pubDate>{_get_recent_date_str()}</pubDate>
        </item>
        <item>
            <title>Different Article</title>
            <link>https://example.com/different</link>
            <description>This is a different article...</description>  # noqa: E501
            <pubDate>{_get_recent_date_str(hours_offset=1)}</pubDate>
        </item>
    </channel>
</rss>"""


# Malformed RSS for error handling
MALFORMED_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>Broken Feed</title>
        <item>
            <title>Article without link</title>
            <!-- Missing required link element -->
            <description>This article has no link...</description>  # noqa: E501
            <pubDate>Mon, 15 Jan 2024 10:00:00 GMT</pubDate>
        </item>
    </channel>
</rss>"""


# Empty RSS feed
EMPTY_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>Empty Feed</title>
        <link>https://example.com/</link>
        <description>No items</description>  # noqa: E501
    </channel>
</rss>"""


# For backward compatibility - generate on import
TECHCRUNCH_RSS = get_techcrunch_rss()
VERGE_RSS = get_verge_rss()
ARXIV_RSS = get_arxiv_rss()
OPENAI_RSS = get_openai_rss()
ANTHROPIC_RSS = get_anthropic_rss()
OLD_ARTICLE_RSS = get_old_article_rss()
DUPLICATE_RSS = get_duplicate_rss()
