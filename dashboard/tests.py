from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from dashboard.models import (
    PortfolioPosition,
    PortfolioTransaction,
    Share,
    SharePriceHistory,
)
from dashboard.services.portfolio import execute_trade, price_history_stats, summarize_portfolio
from dashboard.services.quotations import quotation_to_decimal, quotation_to_float
from dashboard.tasks import update_last_price

User = get_user_model()


class DashboardTests(APITestCase):
    def setUp(self) -> None:
        self.apple_share = Share.objects.create(
            figi="BBG000B9XRY4",
            isin="US0378331005",
            name="Apple",
            ticker="AAPL",
            currency="usd",
            uid="a9eb4238-eba9-488c-b102-b6140fd08e38",
            last_price=100.50,
            is_trend_high=True,
        )

        self.second_company = {
            "figi": "BBG000B9XRY5",
            "isin": "US0378331004",
            "name": "Company_test",
            "ticker": "TESTTEST",
            "currency": "usd",
            "uid": "a9eb4238-eba9-488c-b102-b6140fd08e39",
            "last_price": 1.50,
            "is_trend_high": False,
        }

    def test_share_list_html(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_share_detail_html(self):
        response = self.client.get(
            reverse("dashboard:detail", args=[self.apple_share.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "Apple")

    def test_share_detail_html_missing(self):
        response = self.client.get(reverse("dashboard:detail", args=[99999]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_share_list(self):
        response = self.client.get("/api/v1/shares/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        apple_share = response.json().get("results")[0]
        self.assertEqual(apple_share["id"], self.apple_share.id)
        self.assertEqual(apple_share["figi"], self.apple_share.figi)
        self.assertEqual(apple_share["isin"], self.apple_share.isin)
        self.assertEqual(apple_share["name"], self.apple_share.name)
        self.assertEqual(apple_share["ticker"], self.apple_share.ticker)
        self.assertEqual(apple_share["currency"], self.apple_share.currency)

    def test_share_detail(self):
        response = self.client.get("/api/v1/shares/")
        share_detail = response.json().get("results")[0]
        response = self.client.get(f"/api/v1/shares/{share_detail['id']}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_share_detail_invalid(self):
        response = self.client.get("/api/v1/shares/2/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_share_update(self):
        response = self.client.get("/api/v1/shares/")
        share_detail = response.json().get("results")[0]
        response = self.client.put(
            f"/api/v1/shares/{share_detail['id']}/",
            {
                "id": share_detail["id"],
                "figi": self.apple_share.figi,
                "isin": self.apple_share.isin,
                "name": f"{self.apple_share.name}_test",
                "ticker": self.apple_share.ticker,
                "currency": self.apple_share.currency,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["figi"], self.apple_share.figi)
        self.assertEqual(body["name"], f"{self.apple_share.name}_test")

    def test_share_update_invalid(self):
        response = self.client.get("/api/v1/shares/")
        share_detail = response.json().get("results")[0]
        response = self.client.put(
            f"/api/v1/shares/{share_detail['id']}/",
            {
                "figi": self.apple_share.figi,
                "name": f"{self.apple_share.name}_test",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_share_create(self):
        response = self.client.post(
            "/api/v1/shares/", self.second_company, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.json()
        self.assertEqual(body["figi"], self.second_company["figi"])
        self.assertEqual(body["name"], self.second_company["name"])
        self.assertEqual(body["ticker"], self.second_company["ticker"])

        response = self.client.get("/api/v1/shares/")
        self.assertEqual(len(response.data["results"]), 2)

    def test_share_create_invalid(self):
        response = self.client.post(
            "/api/v1/shares/", {"figi": "BBG000B9XRY5"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_share_delete(self):
        response = self.client.get("/api/v1/shares/")
        share_detail = response.json().get("results")[0]
        response = self.client.delete(f"/api/v1/shares/{share_detail['id']}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        response = self.client.get("/api/v1/shares/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_share_delete_invalid(self):
        response = self.client.delete("/api/v1/shares/3/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PriceHistoryTests(APITestCase):
    def setUp(self):
        self.share = Share.objects.create(
            figi="BBG000B9XRY4",
            isin="US0378331005",
            name="Apple",
            ticker="AAPL",
            currency="usd",
            uid="uid-apple",
            last_price=100,
        )

    def test_quotation_includes_nano(self):
        quotation = SimpleNamespace(units=123, nano=500000000)
        self.assertEqual(quotation_to_decimal(quotation), Decimal("123.5"))
        self.assertEqual(quotation_to_float(quotation), 123.5)

    def test_history_stats_and_page(self):
        now = timezone.now()
        SharePriceHistory.objects.create(
            share=self.share, price=Decimal("100"), recorded_at=now - timedelta(days=2)
        )
        SharePriceHistory.objects.create(
            share=self.share, price=Decimal("110"), recorded_at=now
        )
        stats = price_history_stats(self.share, days=7)
        self.assertEqual(stats["first"], Decimal("100"))
        self.assertEqual(stats["last"], Decimal("110"))
        self.assertEqual(stats["abs_change"], Decimal("10.000000"))
        self.assertEqual(stats["pct_change"], Decimal("10.000000"))

        response = self.client.get(
            reverse("dashboard:history", args=[self.share.id]) + "?days=30"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "История цен")
        self.assertContains(response, "10")

    @patch("dashboard.tasks.get_last_data")
    def test_update_last_price_stores_history(self, mocked_last_data):
        observed_at = timezone.now()
        mocked_last_data.return_value = (105.25, observed_at)
        update_last_price()
        self.share.refresh_from_db()
        self.assertEqual(self.share.last_price, 105.25)
        self.assertTrue(self.share.is_trend_high)
        self.assertEqual(SharePriceHistory.objects.filter(share=self.share).count(), 1)

    @patch("dashboard.tasks.get_last_data")
    def test_update_last_price_marks_downtrend(self, mocked_last_data):
        mocked_last_data.return_value = (90.0, timezone.now())
        update_last_price()
        self.share.refresh_from_db()
        self.assertFalse(self.share.is_trend_high)


class PortfolioTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="trader@example.com",
            email="trader@example.com",
            password="secret12345",
        )
        self.share = Share.objects.create(
            figi="BBG000B9XRY4",
            isin="US0378331005",
            name="Apple",
            ticker="AAPL",
            currency="usd",
            uid="uid-apple",
            last_price=100,
        )

    def test_guest_cannot_open_portfolio(self):
        response = self.client.get(reverse("dashboard:portfolio"))
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn("/user/login/", response.url)

    def test_buy_and_average_price(self):
        execute_trade(self.user, self.share, PortfolioTransaction.BUY, 2, price=100)
        execute_trade(self.user, self.share, PortfolioTransaction.BUY, 2, price=120)
        position = PortfolioPosition.objects.get(user=self.user, share=self.share)
        self.assertEqual(position.quantity, 4)
        self.assertEqual(position.average_price, Decimal("110.000000"))

    def test_sell_and_unrealized_pnl(self):
        execute_trade(self.user, self.share, PortfolioTransaction.BUY, 10, price=100)
        execute_trade(self.user, self.share, PortfolioTransaction.SELL, 4, price=130)
        position = PortfolioPosition.objects.get(user=self.user, share=self.share)
        self.assertEqual(position.quantity, 6)
        self.assertEqual(position.average_price, Decimal("100.000000"))
        self.share.last_price = 150
        self.share.save(update_fields=["last_price"])
        summary = summarize_portfolio(self.user)
        self.assertEqual(summary["rows"][0]["pnl"], Decimal("300.000000"))

    def test_cannot_sell_more_than_owned(self):
        execute_trade(self.user, self.share, PortfolioTransaction.BUY, 1, price=100)
        with self.assertRaises(ValidationError):
            execute_trade(self.user, self.share, PortfolioTransaction.SELL, 2, price=100)

    def test_trade_via_http(self):
        self.client.login(username="trader@example.com", password="secret12345")
        response = self.client.post(
            reverse("dashboard:trade"),
            {
                "share": self.share.id,
                "side": PortfolioTransaction.BUY,
                "quantity": 3,
                "price": "101.5",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            PortfolioTransaction.objects.filter(user=self.user).count(), 1
        )
        page = self.client.get(reverse("dashboard:portfolio"))
        self.assertEqual(page.status_code, status.HTTP_200_OK)
        self.assertContains(page, "AAPL")
