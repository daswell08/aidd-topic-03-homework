from rest_framework import serializers

from dashboard.models import Share


class ShareSerializer(serializers.ModelSerializer):
    last_price = serializers.DecimalField(
        max_digits=20,
        decimal_places=9,
        coerce_to_string=False,
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Share
        fields = (
            "id",
            "figi",
            "isin",
            "name",
            "ticker",
            "currency",
            "last_price",
            "is_trend_high",
            "updated_at",
        )
