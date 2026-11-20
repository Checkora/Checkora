"""The sitemap search engines read: the main pages, every lesson and every opening."""

from django.conf import settings
from django.shortcuts import render
from django.urls import reverse
from django.utils.text import slugify

from .opening_trainer_data import OPENINGS
from .views import LESSON_LEVELS

# (url name, how often it changes, priority)
MAIN_PAGES = (
    ('landing', 'weekly', '1.0'),
    ('index', 'weekly', '0.9'),
    ('puzzles', 'weekly', '0.8'),
    ('lessons', 'monthly', '0.8'),
    ('opening_trainer', 'monthly', '0.7'),
    ('rules', 'monthly', '0.6'),
    ('forum', 'daily', '0.6'),
)


def sitemap_pages():
    pages = [(reverse(name), changefreq, priority) for name, changefreq, priority in MAIN_PAGES]
    for level in LESSON_LEVELS:
        for lesson in level['lessons']:
            pages.append((reverse('lesson_detail', args=[slugify(lesson)]), 'monthly', '0.5'))
    for opening in OPENINGS:
        pages.append((reverse('opening_detail', args=[opening['slug']]), 'monthly', '0.5'))
    return pages


def sitemap(request):
    urls = [
        {'loc': settings.SITE_URL + path, 'changefreq': changefreq, 'priority': priority}
        for path, changefreq, priority in sitemap_pages()
    ]
    return render(request, 'sitemap.xml', {'urls': urls}, content_type='application/xml')
