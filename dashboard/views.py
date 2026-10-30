from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, ListView, UpdateView, View

from .forms import (
    InvestmentStrategyForm,
    PortfolioForm,
    PortfolioTransactionForm,
    PriceAlertForm,
    ShareModelForm,
)
from .models import (
    InvestmentStrategy,
    Portfolio,
    PriceAlert,
    PriceAlertNotification,
    PriceHistory,
    Share,
    StrategyTrade,
    WatchlistItem,
)
from .services.graph import get_graph, get_history_graph
from .services.trading import get_portfolio_positions, record_portfolio_transaction

PRICE_HISTORY_PERIODS = (7, 30, 90, 180, 365)


class IsUserAuthenticatedMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated

    @staticmethod
    def handle_no_permission():
        return redirect("dashboard:index")


class ShareListView(ListView):
    """Список акций"""

    model = Share
    template_name = "dashboard/list.html"
    paginate_by = 100
    ordering = ["name"]


class ShareDetailView(View):
    def get(self, request, pk):
        share = get_object_or_404(Share, pk=pk)
        try:
            selected_days = int(request.GET.get("days", 180))
        except ValueError:
            selected_days = 180
        if selected_days not in PRICE_HISTORY_PERIODS:
            selected_days = 180

        period_end = timezone.now()
        period_start = period_end - timedelta(days=selected_days)
        history = list(
            PriceHistory.objects.filter(
                share=share, recorded_at__range=(period_start, period_end)
            ).order_by("recorded_at")
        )

        absolute_change = None
        percentage_change = None
        if history:
            first_price = history[0].price
            last_price = history[-1].price
            absolute_change = last_price - first_price
            if first_price != 0:
                percentage_change = (
                    absolute_change / first_price * Decimal("100")
                ).quantize(Decimal("0.01"))

        plot_div = (
            get_history_graph(history)
            if history
            else get_graph(share, days=selected_days)
        )

        context = {
            "plot_div": plot_div,
            "share": share,
            "price_history": history,
            "selected_days": selected_days,
            "periods": PRICE_HISTORY_PERIODS,
            "absolute_change": absolute_change,
            "percentage_change": percentage_change,
        }
        if request.user.is_authenticated:
            context.update(
                watchlist_item=WatchlistItem.objects.filter(
                    user=request.user, share=share
                ).first(),
                alert_form=PriceAlertForm(),
                user_alerts=PriceAlert.objects.filter(
                    user=request.user, share=share
                ).order_by("-created_at"),
            )
        return render(
            request,
            "dashboard/detail.html",
            context,
        )


class ShareCreateView(IsUserAuthenticatedMixin, CreateView):
    """Добавление инструмента"""

    template_name = "dashboard/create.html"
    form_class = ShareModelForm
    success_url = reverse_lazy("dashboard:index")


@login_required
def watchlist(request):
    return render(
        request,
        "dashboard/watchlist.html",
        {
            "items": WatchlistItem.objects.filter(user=request.user).select_related(
                "share"
            ),
            "notifications": PriceAlertNotification.objects.filter(
                alert__user=request.user, read_at__isnull=True
            ).select_related("alert__share"),
        },
    )


@login_required
@require_POST
def add_to_watchlist(request, share_id):
    share = get_object_or_404(Share, pk=share_id)
    WatchlistItem.objects.get_or_create(user=request.user, share=share)
    messages.success(request, "Акция добавлена в список наблюдения.")
    return redirect("dashboard:detail", pk=share.pk)


@login_required
@require_POST
def remove_from_watchlist(request, item_id):
    item = get_object_or_404(WatchlistItem, pk=item_id, user=request.user)
    item.delete()
    messages.success(request, "Акция удалена из списка наблюдения.")
    return redirect("dashboard:watchlist")


@login_required
@require_POST
def create_price_alert(request, share_id):
    share = get_object_or_404(Share, pk=share_id)
    form = PriceAlertForm(request.POST)
    if form.is_valid():
        alert, created = PriceAlert.objects.get_or_create(
            user=request.user,
            share=share,
            direction=form.cleaned_data["direction"],
            target_price=form.cleaned_data["target_price"],
        )
        if created:
            messages.success(request, "Уведомление о цене создано.")
        else:
            messages.info(request, "Такое уведомление уже настроено.")
    else:
        messages.error(request, "Не удалось создать уведомление: проверьте данные.")
    return redirect("dashboard:detail", pk=share.pk)


@login_required
@require_POST
def toggle_price_alert(request, pk):
    alert = get_object_or_404(PriceAlert, pk=pk, user=request.user)
    alert.is_active = not alert.is_active
    alert.save(update_fields=["is_active"])
    return redirect("dashboard:detail", pk=alert.share_id)


@login_required
def portfolio_list(request):
    form = PortfolioForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        name = form.cleaned_data["name"]
        portfolio, created = Portfolio.objects.get_or_create(
            user=request.user, name=name
        )
        if not created:
            form.add_error("name", "У вас уже есть портфель с таким названием.")
        else:
            messages.success(request, "Виртуальный портфель создан.")
            return redirect("dashboard:portfolio-detail", pk=portfolio.pk)
    return render(
        request,
        "dashboard/portfolio_list.html",
        {
            "form": form,
            "portfolios": Portfolio.objects.filter(user=request.user),
        },
    )


@login_required
def portfolio_detail(request, pk):
    portfolio = get_object_or_404(Portfolio, pk=pk, user=request.user)
    form = PortfolioTransactionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        share = form.cleaned_data["share"]
        price = form.cleaned_data["price"] or share.last_price
        if price is None or price <= 0:
            form.add_error("price", "Нет цены для акции; укажите цену вручную.")
        else:
            try:
                record_portfolio_transaction(
                    portfolio,
                    share=share,
                    side=form.cleaned_data["side"],
                    quantity=form.cleaned_data["quantity"],
                    price=price,
                )
            except ValidationError as error:
                form.add_error("quantity", error.messages[0])
            else:
                messages.success(request, "Операция виртуального портфеля записана.")
                return redirect("dashboard:portfolio-detail", pk=portfolio.pk)

    positions = get_portfolio_positions(portfolio)
    unpriced_positions = sum(
        position["current_value"] is None for position in positions
    )
    current_value = sum(
        (
            position["current_value"]
            for position in positions
            if position["current_value"] is not None
        ),
        Decimal("0"),
    )
    realized_profit = sum(
        (position["realized_profit"] for position in positions), Decimal("0")
    )
    unrealized_profit = sum(
        (
            position["unrealized_profit"]
            for position in positions
            if position["unrealized_profit"] is not None
        ),
        Decimal("0"),
    )
    return render(
        request,
        "dashboard/portfolio_detail.html",
        {
            "portfolio": portfolio,
            "form": form,
            "positions": positions,
            "unpriced_positions": unpriced_positions,
            "current_value": current_value,
            "realized_profit": realized_profit,
            "unrealized_profit": unrealized_profit,
            "total_profit": realized_profit + unrealized_profit,
            "transactions": portfolio.transactions.select_related("share")[:50],
        },
    )


@login_required
def strategy_list(request):
    form = InvestmentStrategyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        strategy = form.save(commit=False)
        strategy.user = request.user
        strategy.save()
        messages.success(request, "Стратегия создана.")
        return redirect("dashboard:strategies")
    return render(
        request,
        "dashboard/strategy_list.html",
        {
            "form": form,
            "strategies": InvestmentStrategy.objects.filter(
                user=request.user
            ).select_related("share"),
        },
    )


@login_required
@require_POST
def toggle_strategy(request, pk):
    strategy = get_object_or_404(InvestmentStrategy, pk=pk, user=request.user)
    strategy.is_active = not strategy.is_active
    strategy.save(update_fields=["is_active", "updated_at"])
    return redirect("dashboard:strategies")


@login_required
def strategy_detail(request, pk):
    strategy = get_object_or_404(InvestmentStrategy, pk=pk, user=request.user)
    unrealized_profit = None
    if strategy.share.last_price is not None:
        unrealized_profit = (
            strategy.share.last_price - strategy.average_entry_price
        ) * strategy.position_quantity
    return render(
        request,
        "dashboard/strategy_detail.html",
        {
            "strategy": strategy,
            "trades": StrategyTrade.objects.filter(strategy=strategy),
            "unrealized_profit": unrealized_profit,
        },
    )


@login_required
def notifications(request):
    return render(
        request,
        "dashboard/notifications.html",
        {
            "notifications": PriceAlertNotification.objects.filter(
                alert__user=request.user
            ).select_related("alert__share"),
        },
    )


@login_required
@require_POST
def mark_notification_read(request, pk):
    notification = get_object_or_404(
        PriceAlertNotification, pk=pk, alert__user=request.user
    )
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
    return redirect("dashboard:notifications")


class ShareUpdateView(IsUserAuthenticatedMixin, UpdateView):
    """Редактирование инструмента"""

    model = Share
    template_name = "dashboard/create.html"
    form_class = ShareModelForm
    success_url = reverse_lazy("dashboard:index")


class ShareDeleteView(IsUserAuthenticatedMixin, DeleteView):
    """Удаление задачи"""

    model = Share
    template_name = "dashboard/delete.html"
    success_url = reverse_lazy("dashboard:index")
