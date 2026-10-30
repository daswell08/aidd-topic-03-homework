from django.urls import include, path

from dashboard.views import (
    ShareCreateView,
    ShareDeleteView,
    ShareDetailView,
    ShareListView,
    ShareUpdateView,
    add_to_watchlist,
    create_price_alert,
    mark_notification_read,
    notifications,
    portfolio_detail,
    portfolio_list,
    remove_from_watchlist,
    strategy_detail,
    strategy_list,
    toggle_price_alert,
    toggle_strategy,
    watchlist,
)

app_name = "dashboard"

urlpatterns = [
    path("", ShareListView.as_view(), name="index"),
    path("watchlist/", watchlist, name="watchlist"),
    path("watchlist/add/<int:share_id>/", add_to_watchlist, name="watchlist-add"),
    path(
        "watchlist/remove/<int:item_id>/",
        remove_from_watchlist,
        name="watchlist-remove",
    ),
    path("alerts/create/<int:share_id>/", create_price_alert, name="alert-create"),
    path("alerts/<int:pk>/toggle/", toggle_price_alert, name="alert-toggle"),
    path("notifications/", notifications, name="notifications"),
    path(
        "notifications/<int:pk>/read/", mark_notification_read, name="notification-read"
    ),
    path("portfolios/", portfolio_list, name="portfolios"),
    path("portfolios/<int:pk>/", portfolio_detail, name="portfolio-detail"),
    path("strategies/", strategy_list, name="strategies"),
    path("strategies/<int:pk>/", strategy_detail, name="strategy-detail"),
    path("strategies/<int:pk>/toggle/", toggle_strategy, name="strategy-toggle"),
    path("<int:pk>", ShareDetailView.as_view(), name="detail"),
    path("create", ShareCreateView.as_view(), name="create"),
    path("update/<int:pk>", ShareUpdateView.as_view(), name="update"),
    path("delete/<int:pk>", ShareDeleteView.as_view(), name="delete"),
    path("api/", include("dashboard.api.urls")),
]
