"""What search engines see: the sitemap, canonical links and the home page's heading."""

import re

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from game.opening_trainer_data import OPENINGS
from game.views import LESSON_LEVELS


@override_settings(SITE_URL='https://example.org')
class SitemapTest(TestCase):
    def locations(self):
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/xml')
        return re.findall(r'<loc>([^<]+)</loc>', response.content.decode())

    def test_lists_every_lesson_and_opening(self):
        locations = self.locations()
        lessons = sum(len(level['lessons']) for level in LESSON_LEVELS)
        self.assertEqual(len(locations), 7 + lessons + len(OPENINGS))
        self.assertIn('https://example.org/', locations)
        self.assertIn('https://example.org/lessons/how-pieces-move/', locations)
        self.assertIn('https://example.org/openings/italian-game/', locations)
        self.assertEqual(len(set(locations)), len(locations))

    def test_every_listed_page_opens(self):
        for location in self.locations():
            path = location.removeprefix('https://example.org')
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)


class CanonicalTest(TestCase):
    def test_each_page_names_itself_without_the_query(self):
        response = self.client.get(reverse('forum'), {'page': 2})
        self.assertContains(
            response, f'<link rel="canonical" href="{settings.SITE_URL}{reverse("forum")}">', html=True,
        )

    def test_home_has_one_canonical_link(self):
        content = self.client.get(reverse('landing')).content.decode()
        self.assertEqual(content.count('rel="canonical"'), 1)


class HomeHeadingTest(TestCase):
    def test_the_one_h1_says_what_the_site_is(self):
        content = self.client.get(reverse('landing')).content.decode()
        headings = re.findall(r'<h1[^>]*>(.*?)</h1>', content, re.S)
        self.assertEqual(len(headings), 1)
        self.assertIn('online chess', headings[0].lower())
