from django.contrib import admin

from dashboard.models import (
    PortfolioPosition,
    PortfolioTransaction,
    Share,
    SharePriceHistory,
)


@admin.register(Share)
class ShareAdmin(admin.ModelAdmin):
    list_display = ("figi", "isin", "name", "ticker", "currency", "last_price")
    search_fields = ("figi", "isin", "name", "ticker")
    fields = (
        "figi",
        "isin",
        "name",
        "ticker",
        "currency",
        "uid",
        "last_price",
        "is_trend_high",
    )


@admin.register(SharePriceHistory)
class SharePriceHistoryAdmin(admin.ModelAdmin):
    list_display = ("share", "price", "recorded_at")
    list_filter = ("share",)
    date_hierarchy = "recorded_at"


@admin.register(PortfolioPosition)
class PortfolioPositionAdmin(admin.ModelAdmin):
    list_display = ("user", "share", "quantity", "average_price")
    search_fields = ("user__username", "share__ticker")


@admin.register(PortfolioTransaction)
class PortfolioTransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "share", "side", "quantity", "price", "created_at")
    list_filter = ("side",)
