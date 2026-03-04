#!/usr/bin/env python3
"""
RSS/Atom feed fetcher and parser for rss-intel skill.
Usage:
  python fetch-feeds.py fetch <url>          # Fetch a single feed, output JSON
  python fetch-feeds.py fetch-all <path>     # Fetch all feeds from feeds.json
  python fetch-feeds.py validate <url>       # Validate a feed URL
"""

import sys
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import re

NAMESPACES = {
    'atom': 'http://www.w3.org/2005/Atom',
    'dc':   'http://purl.org/dc/elements/1.1/',
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'media': 'http://search.yahoo.com/mrss/',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; rss-intel/1.0)',
    'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml, */*',
}

def fetch_url(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            charset = 'utf-8'
            ct = r.headers.get_content_charset()
            if ct:
                charset = ct
            return raw.decode(charset, errors='replace')
    except Exception as e:
        return None, str(e)

def clean_html(text):
    """Strip HTML tags and normalize whitespace."""
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#\d+;', '', text)
    text = re.sub(r'&\w+;', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:500]  # Limit summary length

def parse_date(date_str):
    """Try to parse various date formats, return ISO string or original."""
    if not date_str:
        return ''
    date_str = date_str.strip()
    formats = [
        '%a, %d %b %Y %H:%M:%S %z',
        '%a, %d %b %Y %H:%M:%S GMT',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%dT%H:%M:%S.%f%z',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.isoformat()
        except Exception:
            pass
    return date_str

def parse_rss(root, url):
    """Parse RSS 2.0 feed."""
    channel = root.find('channel')
    if channel is None:
        return None

    feed_title = ''
    t = channel.find('title')
    if t is not None and t.text:
        feed_title = t.text.strip()

    articles = []
    for item in channel.findall('item'):
        title_el = item.find('title')
        link_el = item.find('link')
        desc_el = item.find('description')
        date_el = item.find('pubDate')
        dc_date = item.find('dc:date', NAMESPACES)

        title = title_el.text.strip() if title_el is not None and title_el.text else '(no title)'
        link = link_el.text.strip() if link_el is not None and link_el.text else url
        summary = clean_html(desc_el.text if desc_el is not None else '')
        pub_date = parse_date(
            (date_el.text if date_el is not None else None) or
            (dc_date.text if dc_date is not None else None) or ''
        )

        articles.append({
            'title': title,
            'link': link,
            'summary': summary,
            'published': pub_date,
        })

    return {'feed_title': feed_title, 'articles': articles}

def parse_atom(root, url):
    """Parse Atom 1.0 feed."""
    ns = 'http://www.w3.org/2005/Atom'

    def tag(name):
        return f'{{{ns}}}{name}'

    feed_title_el = root.find(tag('title'))
    feed_title = feed_title_el.text.strip() if feed_title_el is not None and feed_title_el.text else ''

    articles = []
    for entry in root.findall(tag('entry')):
        title_el = entry.find(tag('title'))
        link_el = entry.find(tag('link'))
        summary_el = entry.find(tag('summary'))
        content_el = entry.find(tag('content'))
        updated_el = entry.find(tag('updated'))
        published_el = entry.find(tag('published'))

        title = title_el.text.strip() if title_el is not None and title_el.text else '(no title)'

        link = url
        if link_el is not None:
            link = link_el.get('href', url)

        summary_text = ''
        if summary_el is not None:
            summary_text = summary_el.text or ''
        elif content_el is not None:
            summary_text = content_el.text or ''
        summary = clean_html(summary_text)

        pub_date = parse_date(
            (published_el.text if published_el is not None else None) or
            (updated_el.text if updated_el is not None else None) or ''
        )

        articles.append({
            'title': title,
            'link': link,
            'summary': summary,
            'published': pub_date,
        })

    return {'feed_title': feed_title, 'articles': articles}

def fetch_and_parse(url):
    result = fetch_url(url)
    if isinstance(result, tuple):
        content, error = result
        return {'success': False, 'url': url, 'error': error, 'articles': []}
    content = result

    if not content:
        return {'success': False, 'url': url, 'error': 'Empty response', 'articles': []}

    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        return {'success': False, 'url': url, 'error': f'XML parse error: {e}', 'articles': []}

    tag = root.tag.lower()
    parsed = None

    if 'rss' in tag or root.tag == 'rss':
        parsed = parse_rss(root, url)
    elif 'feed' in tag or 'atom' in root.tag.lower():
        parsed = parse_atom(root, url)
    else:
        # Try RSS first, then Atom
        parsed = parse_rss(root, url)
        if parsed is None:
            parsed = parse_atom(root, url)

    if parsed is None:
        return {'success': False, 'url': url, 'error': 'Unrecognized feed format', 'articles': []}

    return {
        'success': True,
        'url': url,
        'feed_title': parsed['feed_title'],
        'article_count': len(parsed['articles']),
        'articles': parsed['articles'],
    }

def cmd_fetch(url):
    result = fetch_and_parse(url)
    print(json.dumps(result, ensure_ascii=False, indent=2))

def cmd_fetch_all(feeds_path):
    try:
        with open(feeds_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(json.dumps({'success': False, 'error': str(e), 'results': []}))
        return

    feeds = config.get('feeds', [])
    if not feeds:
        print(json.dumps({'success': True, 'results': [], 'message': 'No feeds configured'}))
        return

    results = []
    for feed in feeds:
        url = feed.get('url', '')
        name = feed.get('name', '')
        if not url:
            continue
        r = fetch_and_parse(url)
        if name:
            r['configured_name'] = name
        results.append(r)

    print(json.dumps({'success': True, 'results': results}, ensure_ascii=False, indent=2))

def cmd_validate(url):
    result = fetch_and_parse(url)
    if result['success']:
        title = result.get('feed_title', '') or url
        count = result.get('article_count', 0)
        print(json.dumps({
            'valid': True,
            'url': url,
            'feed_title': title,
            'article_count': count,
        }, ensure_ascii=False))
    else:
        print(json.dumps({
            'valid': False,
            'url': url,
            'error': result.get('error', 'Unknown error'),
        }, ensure_ascii=False))

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: fetch-feeds.py <fetch|fetch-all|validate> <url|path>')
        sys.exit(1)

    cmd = sys.argv[1]
    arg = sys.argv[2]

    if cmd == 'fetch':
        cmd_fetch(arg)
    elif cmd == 'fetch-all':
        cmd_fetch_all(arg)
    elif cmd == 'validate':
        cmd_validate(arg)
    else:
        print(f'Unknown command: {cmd}')
        sys.exit(1)
