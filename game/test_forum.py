from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from game.models import Discussion

User = get_user_model()


class ForumPaginationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="password"
        )

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
        response = self.client.get(
            self.forum_url,
            {"page": 2, "sort": "oldest"}
        )
        self.assertEqual(response.status_code, 200)

        page_obj = response.context["page_obj"]
        self.assertEqual(page_obj.number, 2)
        self.assertEqual(response.context["sort_by"], "oldest")

        html = response.content.decode("utf-8")
        self.assertIn("?page=1&sort=oldest", html)


class ForumSearchAndFilterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="forumuser",
            password="password"
        )
        self.d1 = Discussion.objects.create(
            user=self.user,
            title="Sicilian Defense Analysis",
            content="Discussing openings strategies for black.",
            category="openings"
        )
        self.d2 = Discussion.objects.create(
            user=self.user,
            title="Tactical Mate Puzzle",
            content="Check out this awesome puzzle I found.",
            category="puzzles"
        )
        self.d3 = Discussion.objects.create(
            user=self.user,
            title="General Feedback on Checkora",
            content="Great platform for learning chess openings.",
            category="feedback"
        )
        self.forum_url = reverse("forum")

    def test_search_discussions_by_query(self):
        response = self.client.get(self.forum_url, {"q": "Sicilian"})
        self.assertEqual(response.status_code, 200)
        page_obj = response.context["page_obj"]
        self.assertEqual(len(page_obj), 1)
        self.assertEqual(page_obj[0].id, self.d1.id)

    def test_search_discussions_by_content(self):
        response = self.client.get(self.forum_url, {"q": "awesome"})
        self.assertEqual(response.status_code, 200)
        page_obj = response.context["page_obj"]
        self.assertEqual(len(page_obj), 1)
        self.assertEqual(page_obj[0].id, self.d2.id)

    def test_filter_discussions_by_category(self):
        response = self.client.get(self.forum_url, {"category": "puzzles"})
        self.assertEqual(response.status_code, 200)
        page_obj = response.context["page_obj"]
        self.assertEqual(len(page_obj), 1)
        self.assertEqual(page_obj[0].id, self.d2.id)

    def test_combined_search_and_category_filter(self):
        response = self.client.get(
            self.forum_url,
            {"q": "openings", "category": "feedback"}
        )
        self.assertEqual(response.status_code, 200)
        page_obj = response.context["page_obj"]
        self.assertEqual(len(page_obj), 1)
        self.assertEqual(page_obj[0].id, self.d3.id)

    def test_create_discussion_with_category(self):
        User.objects.create_user(
            username="newuser",
            password="password"
        )
        self.client.login(username="newuser", password="password")
        response = self.client.post(reverse("forum_new"), {
            "title": "New Endgame Tactics",
            "category": "puzzles",
            "content": "Share your best endgame puzzle positions here!"
        })
        self.assertEqual(response.status_code, 302)
        new_discussion = Discussion.objects.get(
            title="New Endgame Tactics"
        )
        self.assertEqual(new_discussion.category, "puzzles")

    def test_pagination_with_encoded_query_params(self):
        for i in range(25):
            Discussion.objects.create(
                user=self.user,
                title=f"Special & Query #{i}",
                content="Testing pagination URL encoding",
                category="puzzles"
            )
        response = self.client.get(
            self.forum_url,
            {"q": "Special & Query", "category": "puzzles"}
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("q=Special%20%26%20Query", html)
        self.assertIn("category=puzzles", html)
