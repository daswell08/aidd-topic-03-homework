from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView, View

from .forms import HistoryPeriodForm, ShareModelForm, TradeForm
from .models import PortfolioTransaction, Share
from .services.graph import get_graph
from .services.portfolio import execute_trade, price_history_stats, summarize_portfolio


class ShareListView(ListView):
    """Список акций"""

    model = Share
    template_name = "dashboard/list.html"
    paginate_by = 100
    ordering = ["name"]


class ShareDetailView(View):
    @staticmethod
    def get(request, pk):
        share = get_object_or_404(Share, id=pk)
        days = 180
        if "days" in request.GET:
            period_form = HistoryPeriodForm(request.GET)
            if period_form.is_valid():
                days = period_form.cleaned_data["days"]
        else:
            period_form = HistoryPeriodForm(initial={"days": days})

        stats = price_history_stats(share, days=days)
        return render(
            request,
            "dashboard/detail.html",
            {
                "plot_div": get_graph(share, days=days),
                "share": share,
                "period_form": period_form,
                "stats": stats,
                "days": days,
            },
        )


class ShareCreateView(LoginRequiredMixin, CreateView):
    """Добавление инструмента"""

    template_name = "dashboard/create.html"
    form_class = ShareModelForm
    success_url = reverse_lazy("dashboard:index")


class ShareUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование инструмента"""

    model = Share
    template_name = "dashboard/create.html"
    form_class = ShareModelForm
    success_url = reverse_lazy("dashboard:index")


class ShareDeleteView(LoginRequiredMixin, DeleteView):
    """Удаление инструмента"""

    model = Share
    template_name = "dashboard/delete.html"
    success_url = reverse_lazy("dashboard:index")


class ShareHistoryView(View):
    """История рыночных цен акции."""

    @staticmethod
    def get(request, pk):
        share = get_object_or_404(Share, id=pk)
        days = 180
        if "days" in request.GET:
            period_form = HistoryPeriodForm(request.GET)
            if period_form.is_valid():
                days = period_form.cleaned_data["days"]
        else:
            period_form = HistoryPeriodForm(initial={"days": days})

        stats = price_history_stats(share, days=days)
        return render(
            request,
            "dashboard/history.html",
            {
                "share": share,
                "period_form": period_form,
                "stats": stats,
                "plot_div": get_graph(share, days=days),
                "days": days,
            },
        )


class PortfolioView(LoginRequiredMixin, View):
    """Виртуальный инвестиционный портфель."""

    @staticmethod
    def get(request):
        summary = summarize_portfolio(request.user)
        transactions = (
            PortfolioTransaction.objects.filter(user=request.user)
            .select_related("share")[:50]
        )
        return render(
            request,
            "dashboard/portfolio.html",
            {
                "summary": summary,
                "transactions": transactions,
                "form": TradeForm(),
            },
        )


class TradeCreateView(LoginRequiredMixin, View):
    """Покупка или продажа акций в виртуальном портфеле."""

    @staticmethod
    def get(request):
        initial = {}
        share_id = request.GET.get("share")
        if share_id:
            initial["share"] = share_id
        return render(request, "dashboard/trade.html", {"form": TradeForm(initial=initial)})

    @staticmethod
    def post(request):
        form = TradeForm(request.POST)
        if form.is_valid():
            try:
                execute_trade(
                    user=request.user,
                    share=form.cleaned_data["share"],
                    side=form.cleaned_data["side"],
                    quantity=form.cleaned_data["quantity"],
                    price=form.cleaned_data.get("price"),
                )
                messages.success(request, "Операция успешно выполнена.")
                return redirect("dashboard:portfolio")
            except ValidationError as exc:
                form.add_error(None, exc)
        return render(request, "dashboard/trade.html", {"form": form})
