from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from game.models import Discussion

User = get_user_model()

class ForumPaginationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        
        # Create 22 discussions to test pagination boundaries
        for i in range(22):
            Discussion.objects.create(
                user=self.user,
                title=f"Test Discussion {i}",
                content=f"Content for test discussion {i}"
            )
        self.forum_url = reverse("forum")

    def test_forum_pagination_first_page(self):
        response = self.client.get(self.forum_url)
        self.assertEqual(response.status_code, 200)
        
        page_obj = response.context["page_obj"]
        self.assertEqual(page_obj.paginator.num_pages, 2)
        self.assertEqual(len(page_obj), 20)
        self.assertTrue(page_obj.has_next())
        self.assertFalse(page_obj.has_previous())

    def test_forum_pagination_second_page(self):
        response = self.client.get(self.forum_url, {"page": 2})
        self.assertEqual(response.status_code, 200)
        
        page_obj = response.context["page_obj"]
        self.assertEqual(page_obj.number, 2)
        self.assertEqual(len(page_obj), 2)
        self.assertFalse(page_obj.has_next())
        self.assertTrue(page_obj.has_previous())

    def test_forum_pagination_out_of_bounds(self):
        # Assert out-of-range page number returns last page
        response = self.client.get(self.forum_url, {"page": 99})
        self.assertEqual(response.status_code, 200)
        page_obj = response.context["page_obj"]
        self.assertEqual(page_obj.number, 2)
        
        # Assert non-integer page value returns first page
        response = self.client.get(self.forum_url, {"page": "not_an_int"})
        self.assertEqual(response.status_code, 200)
        page_obj = response.context["page_obj"]
        self.assertEqual(page_obj.number, 1)

    def test_forum_pagination_with_sort(self):
        response = self.client.get(self.forum_url, {"page": 2, "sort": "oldest"})
        self.assertEqual(response.status_code, 200)
        
        page_obj = response.context["page_obj"]
        self.assertEqual(page_obj.number, 2)
        self.assertEqual(response.context["sort_by"], "oldest")
        
        html = response.content.decode("utf-8")
        self.assertIn("?page=1&sort=oldest", html)
