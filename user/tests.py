from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from config.celery import app as celery_app


class UserAuthenticationTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.email = "investor@example.com"
        self.password = "A-valid-password-123!"

    def test_authentication_forms_render(self):
        response = self.client.get(reverse("user:auth"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="email"')
        response = self.client.get(reverse("user:registration"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="password2"')

    def test_registration_creates_user_and_logs_them_in(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": self.email,
                "password1": self.password,
                "password2": self.password,
            },
        )
        self.assertRedirects(response, reverse("dashboard:index"))
        user = self.user_model.objects.get(email=self.email)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_invalid_registration_renders_field_errors(self):
        response = self.client.post(
            reverse("user:registration"),
            {"email": self.email, "password1": "one", "password2": "two"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Пароли не совпадают.")
        self.assertFalse(self.user_model.objects.filter(email=self.email).exists())

    def test_registration_with_missing_fields_returns_form_errors(self):
        response = self.client.post(reverse("user:registration"), {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assertEqual(self.user_model.objects.count(), 0)

    def test_registration_rejects_duplicate_email_case_insensitively(self):
        self.user_model.objects.create_user(
            username=self.email,
            email=self.email,
            password=self.password,
        )
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": self.email.upper(),
                "password1": self.password,
                "password2": self.password,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Этот email уже зарегистрирован.")

    def test_login_rejects_missing_or_invalid_credentials_without_exception(self):
        response = self.client.post(reverse("user:auth"), {})
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            reverse("user:auth"),
            {"email": self.email, "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Неверный email или пароль.")

    def test_login_accepts_email_case_insensitively(self):
        self.user_model.objects.create_user(
            username=self.email,
            email=self.email,
            password=self.password,
        )
        response = self.client.post(
            reverse("user:auth"),
            {"email": self.email.upper(), "password": self.password},
        )
        self.assertRedirects(response, reverse("dashboard:index"))

    def test_logout_ends_the_authenticated_session(self):
        user = self.user_model.objects.create_user(
            username=self.email,
            email=self.email,
            password=self.password,
        )
        self.client.force_login(user)
        response = self.client.get(reverse("user:logout"))
        self.assertRedirects(response, reverse("dashboard:index"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_price_updates_are_scheduled_every_five_minutes(self):
        self.assertEqual(
            celery_app.conf.beat_schedule["add-every-5-min"]["schedule"], 300.0
        )
