from django.urls import include, path

from dashboard.views import (
    PortfolioView,
    ShareCreateView,
    ShareDeleteView,
    ShareDetailView,
    ShareHistoryView,
    ShareListView,
    ShareUpdateView,
    TradeCreateView,
)

app_name = "dashboard"

urlpatterns = [
    path("", ShareListView.as_view(), name="index"),
    path("portfolio/", PortfolioView.as_view(), name="portfolio"),
    path("portfolio/trade/", TradeCreateView.as_view(), name="trade"),
    path("create", ShareCreateView.as_view(), name="create"),
    path("update/<int:pk>", ShareUpdateView.as_view(), name="update"),
    path("delete/<int:pk>", ShareDeleteView.as_view(), name="delete"),
    path("<int:pk>/history/", ShareHistoryView.as_view(), name="history"),
    path("<int:pk>", ShareDetailView.as_view(), name="detail"),
    path("api/", include("dashboard.api.urls")),
]
