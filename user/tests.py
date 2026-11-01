from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

User = get_user_model()


class UserAuthTests(APITestCase):
    def test_login_url_contains_slash_after_user(self):
        self.assertEqual(reverse("user:auth"), "/user/login/")
        response = self.client.get(reverse("user:auth"))
        self.assertEqual(response.status_code, 200)

    def test_registration_and_login_lowercase_email(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "Person@Example.COM",
                "password1": "StrongPass123",
                "password2": "StrongPass123",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="person@example.com")
        self.assertEqual(user.username, "person@example.com")

        self.client.get(reverse("user:logout"))
        login_response = self.client.post(
            reverse("user:auth"),
            {"email": "PERSON@example.com", "password": "StrongPass123"},
        )
        self.assertEqual(login_response.status_code, 302)

    def test_registration_password_mismatch(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "one@example.com",
                "password1": "StrongPass123",
                "password2": "OtherPass123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "не совпадают")
        self.assertFalse(User.objects.filter(email="one@example.com").exists())

    def test_duplicate_email(self):
        User.objects.create_user(
            username="dup@example.com", email="dup@example.com", password="StrongPass123"
        )
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "dup@example.com",
                "password1": "StrongPass123",
                "password2": "StrongPass123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "уже зарегистрирован")

    def test_invalid_login(self):
        response = self.client.post(
            reverse("user:auth"),
            {"email": "missing@example.com", "password": "nope"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Неверный логин или пароль")
