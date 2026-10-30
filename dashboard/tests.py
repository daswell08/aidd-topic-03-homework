from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from dashboard.models import (
    InvestmentStrategy,
    Portfolio,
    PortfolioTransaction,
    PriceAlert,
    PriceAlertNotification,
    PriceHistory,
    Share,
    StrategyTrade,
    WatchlistItem,
)
from dashboard.services.market_automation import (
    process_investment_strategies,
    process_price_alerts,
)
from dashboard.services.trading import (
    get_portfolio_positions,
    record_portfolio_transaction,
)


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
        self.assertIsInstance(apple_share["last_price"], float)

    def test_share_detail(self):
        response = self.client.get("/api/v1/shares/")
        share_detail = response.json().get("results")[0]
        response = self.client.get(f"/api/v1/shares/{share_detail['id']}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_share_detail_invalid(self):
        response = self.client.get("/api/v1/shares/2/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("dashboard.views.get_history_graph", return_value="<div>history</div>")
    def test_share_detail_shows_saved_history_for_selected_period(self, graph):
        now = timezone.now()
        PriceHistory.objects.create(
            share=self.apple_share,
            price=Decimal("90.00"),
            recorded_at=now - timedelta(days=60),
        )
        PriceHistory.objects.create(
            share=self.apple_share,
            price=Decimal("100.00"),
            recorded_at=now - timedelta(days=20),
        )
        PriceHistory.objects.create(
            share=self.apple_share,
            price=Decimal("125.00"),
            recorded_at=now - timedelta(days=10),
        )

        response = self.client.get(
            f"{reverse('dashboard:detail', args=[self.apple_share.id])}?days=30"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.context["selected_days"], 30)
        self.assertEqual(len(response.context["price_history"]), 2)
        self.assertEqual(response.context["absolute_change"], Decimal("25.00"))
        self.assertEqual(response.context["percentage_change"], Decimal("25.00"))
        graph.assert_called_once_with(response.context["price_history"])

    @patch("dashboard.views.get_graph", return_value="<div>api history</div>")
    def test_share_detail_falls_back_to_api_when_no_saved_history(self, graph):
        response = self.client.get(
            f"{reverse('dashboard:detail', args=[self.apple_share.id])}?days=7"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.context["absolute_change"], None)
        self.assertEqual(response.context["percentage_change"], None)
        graph.assert_called_once_with(self.apple_share, days=7)

    @patch("dashboard.views.get_history_graph", return_value="<div>history</div>")
    def test_share_detail_does_not_calculate_percentage_from_zero(self, graph):
        now = timezone.now()
        PriceHistory.objects.create(
            share=self.apple_share,
            price=Decimal("0"),
            recorded_at=now - timedelta(days=1),
        )
        PriceHistory.objects.create(
            share=self.apple_share,
            price=Decimal("10"),
            recorded_at=now,
        )

        response = self.client.get(
            f"{reverse('dashboard:detail', args=[self.apple_share.id])}?days=7"
        )

        self.assertEqual(response.context["absolute_change"], Decimal("10"))
        self.assertIsNone(response.context["percentage_change"])
        graph.assert_called_once()

    @patch("dashboard.tasks.get_last_data")
    def test_price_update_saves_history_once_for_repeated_timestamp(
        self, get_last_data
    ):
        recorded_at = timezone.now()
        get_last_data.return_value = (Decimal("100.123456789"), recorded_at)

        from dashboard.tasks import update_last_price

        update_last_price.run()
        update_last_price.run()

        self.apple_share.refresh_from_db()
        self.assertEqual(self.apple_share.last_price, Decimal("100.123456789"))
        self.assertEqual(PriceHistory.objects.filter(share=self.apple_share).count(), 1)
        self.assertEqual(
            PriceHistory.objects.get(share=self.apple_share).price,
            Decimal("100.123456789"),
        )
        self.assertEqual(get_last_data.call_count, 2)

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


class InvestingFeatureTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="investor",
            email="investor@example.com",
            password="test-password",
        )
        self.other_user = user_model.objects.create_user(
            username="other",
            email="other@example.com",
            password="test-password",
        )
        self.share = Share.objects.create(
            figi="BBG000B9XRY4",
            isin="US0378331005",
            name="Apple",
            ticker="AAPL",
            currency="usd",
            uid="a9eb4238-eba9-488c-b102-b6140fd08e38",
            last_price=Decimal("17"),
        )
        self.client.force_login(self.user)

    def test_watchlist_add_is_idempotent_and_user_scoped(self):
        add_url = reverse("dashboard:watchlist-add", args=[self.share.pk])
        self.assertEqual(self.client.post(add_url).status_code, 302)
        self.assertEqual(self.client.post(add_url).status_code, 302)
        self.assertEqual(
            WatchlistItem.objects.filter(user=self.user, share=self.share).count(),
            1,
        )

        foreign_item = WatchlistItem.objects.create(
            user=self.other_user, share=self.share
        )
        remove_url = reverse("dashboard:watchlist-remove", args=[foreign_item.pk])
        self.assertEqual(self.client.post(remove_url).status_code, 404)
        self.assertTrue(WatchlistItem.objects.filter(pk=foreign_item.pk).exists())

    def test_price_alert_notifies_once_until_condition_clears(self):
        alert = PriceAlert.objects.create(
            user=self.user,
            share=self.share,
            direction=PriceAlert.Direction.ABOVE,
            target_price=Decimal("100"),
        )
        first_time = timezone.now()
        process_price_alerts(self.share, Decimal("101"), first_time)
        process_price_alerts(self.share, Decimal("101"), first_time)
        self.assertEqual(alert.notifications.count(), 1)

        process_price_alerts(
            self.share, Decimal("99"), first_time + timedelta(minutes=1)
        )
        alert.refresh_from_db()
        self.assertTrue(alert.is_armed)
        process_price_alerts(
            self.share, Decimal("101"), first_time + timedelta(minutes=2)
        )
        self.assertEqual(alert.notifications.count(), 2)

    def test_duplicate_price_alert_submission_does_not_create_another_alert(self):
        create_url = reverse("dashboard:alert-create", args=[self.share.pk])
        payload = {"direction": "above", "target_price": "100"}
        self.client.post(create_url, payload)
        self.client.post(create_url, payload)
        self.assertEqual(
            PriceAlert.objects.filter(
                user=self.user, share=self.share, target_price=Decimal("100")
            ).count(),
            1,
        )

    @patch("dashboard.tasks.get_last_data")
    def test_automatic_price_update_triggers_alert_only_once(self, get_last_data):
        alert = PriceAlert.objects.create(
            user=self.user,
            share=self.share,
            direction=PriceAlert.Direction.ABOVE,
            target_price=Decimal("100"),
        )
        recorded_at = timezone.now()
        get_last_data.return_value = (Decimal("101"), recorded_at)

        from dashboard.tasks import update_last_price

        update_last_price.run()
        update_last_price.run()

        self.assertEqual(alert.notifications.count(), 1)
        self.share.refresh_from_db()
        self.assertEqual(self.share.last_price, Decimal("101"))

    def test_portfolio_tracks_average_cost_and_profit(self):
        portfolio = Portfolio.objects.create(user=self.user, name="Long term")
        record_portfolio_transaction(
            portfolio,
            share=self.share,
            side=PortfolioTransaction.Side.BUY,
            quantity=Decimal("2"),
            price=Decimal("10"),
        )
        record_portfolio_transaction(
            portfolio,
            share=self.share,
            side=PortfolioTransaction.Side.BUY,
            quantity=Decimal("2"),
            price=Decimal("20"),
        )
        record_portfolio_transaction(
            portfolio,
            share=self.share,
            side=PortfolioTransaction.Side.SELL,
            quantity=Decimal("1"),
            price=Decimal("30"),
        )

        position = get_portfolio_positions(portfolio)[0]
        self.assertEqual(position["quantity"], Decimal("3"))
        self.assertEqual(position["average_cost"], Decimal("15"))
        self.assertEqual(position["current_value"], Decimal("51"))
        self.assertEqual(position["realized_profit"], Decimal("15"))
        self.assertEqual(position["unrealized_profit"], Decimal("6"))
        self.assertEqual(position["total_profit"], Decimal("21"))

    def test_portfolio_rejects_sale_larger_than_holding(self):
        portfolio = Portfolio.objects.create(user=self.user, name="Test")
        with self.assertRaises(ValidationError):
            record_portfolio_transaction(
                portfolio,
                share=self.share,
                side=PortfolioTransaction.Side.SELL,
                quantity=Decimal("1"),
                price=Decimal("10"),
            )
        self.assertEqual(portfolio.transactions.count(), 0)

    def test_portfolio_marks_value_unknown_when_market_price_is_missing(self):
        self.share.last_price = None
        self.share.save(update_fields=["last_price"])
        portfolio = Portfolio.objects.create(user=self.user, name="Unpriced")
        record_portfolio_transaction(
            portfolio,
            share=self.share,
            side=PortfolioTransaction.Side.BUY,
            quantity=Decimal("1"),
            price=Decimal("10"),
        )

        position = get_portfolio_positions(portfolio)[0]
        self.assertIsNone(position["current_value"])
        self.assertIsNone(position["unrealized_profit"])
        response = self.client.get(
            reverse("dashboard:portfolio-detail", args=[portfolio.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "оценка неполная")

    def test_portfolio_is_private_to_its_owner(self):
        portfolio = Portfolio.objects.create(user=self.other_user, name="Private")
        response = self.client.get(
            reverse("dashboard:portfolio-detail", args=[portfolio.pk])
        )
        self.assertEqual(response.status_code, 404)

    @patch("dashboard.views.get_graph", return_value="<div>graph</div>")
    def test_authenticated_feature_pages_render(self, graph):
        WatchlistItem.objects.create(user=self.user, share=self.share)
        portfolio = Portfolio.objects.create(user=self.user, name="My portfolio")
        strategy = InvestmentStrategy.objects.create(
            user=self.user,
            share=self.share,
            name="My strategy",
            buy_below=Decimal("10"),
            sell_above=Decimal("20"),
            quantity=Decimal("1"),
        )
        alert = PriceAlert.objects.create(
            user=self.user,
            share=self.share,
            direction=PriceAlert.Direction.ABOVE,
            target_price=Decimal("20"),
        )
        PriceAlertNotification.objects.create(
            alert=alert,
            price=Decimal("21"),
            recorded_at=timezone.now(),
        )
        urls = [
            reverse("dashboard:watchlist"),
            reverse("dashboard:portfolios"),
            reverse("dashboard:portfolio-detail", args=[portfolio.pk]),
            reverse("dashboard:strategies"),
            reverse("dashboard:strategy-detail", args=[strategy.pk]),
            reverse("dashboard:notifications"),
            reverse("dashboard:detail", args=[self.share.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        graph.assert_called_once_with(self.share, days=180)

    def test_portfolio_transaction_view_uses_current_price_and_rejects_oversell(self):
        portfolio = Portfolio.objects.create(user=self.user, name="Trading")
        detail_url = reverse("dashboard:portfolio-detail", args=[portfolio.pk])
        response = self.client.post(
            detail_url,
            {
                "share": self.share.pk,
                "side": PortfolioTransaction.Side.BUY,
                "quantity": "2",
                "price": "",
            },
        )
        self.assertRedirects(response, detail_url)
        item = portfolio.transactions.get()
        self.assertEqual(item.price, Decimal("17"))

        response = self.client.post(
            detail_url,
            {
                "share": self.share.pk,
                "side": PortfolioTransaction.Side.SELL,
                "quantity": "3",
                "price": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(portfolio.transactions.count(), 1)

    def test_duplicate_portfolio_name_is_rejected(self):
        Portfolio.objects.create(user=self.user, name="Same")
        response = self.client.post(reverse("dashboard:portfolios"), {"name": "Same"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "У вас уже есть портфель")
        self.assertEqual(Portfolio.objects.filter(user=self.user).count(), 1)

    def test_strategy_simulates_idempotent_buy_and_sell(self):
        strategy = InvestmentStrategy.objects.create(
            user=self.user,
            share=self.share,
            name="Buy low sell high",
            buy_below=Decimal("100"),
            sell_above=Decimal("110"),
            quantity=Decimal("2"),
        )
        buy_time = timezone.now()
        process_investment_strategies(self.share, Decimal("90"), buy_time)
        process_investment_strategies(self.share, Decimal("90"), buy_time)
        strategy.refresh_from_db()
        self.assertEqual(strategy.position_quantity, Decimal("2"))
        self.assertEqual(strategy.trades.count(), 1)

        sell_time = buy_time + timedelta(minutes=1)
        process_investment_strategies(self.share, Decimal("110"), sell_time)
        process_investment_strategies(self.share, Decimal("110"), sell_time)
        strategy.refresh_from_db()
        self.assertEqual(strategy.position_quantity, Decimal("0"))
        self.assertEqual(strategy.realized_profit, Decimal("40"))
        self.assertEqual(strategy.trades.count(), 2)

    def test_strategy_requires_sell_threshold_above_buy_threshold(self):
        response = self.client.post(
            reverse("dashboard:strategies"),
            {
                "name": "Invalid thresholds",
                "share": self.share.pk,
                "buy_below": "100",
                "sell_above": "100",
                "quantity": "1",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            InvestmentStrategy.objects.filter(name="Invalid thresholds").exists()
        )

    def test_notifications_can_only_be_read_by_alert_owner(self):
        alert = PriceAlert.objects.create(
            user=self.other_user,
            share=self.share,
            direction=PriceAlert.Direction.ABOVE,
            target_price=Decimal("100"),
        )
        notification = PriceAlertNotification.objects.create(
            alert=alert,
            price=Decimal("101"),
            recorded_at=timezone.now(),
        )
        response = self.client.post(
            reverse("dashboard:notification-read", args=[notification.pk])
        )
        self.assertEqual(response.status_code, 404)
