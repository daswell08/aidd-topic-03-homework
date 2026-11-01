from django import forms

from .models import PortfolioTransaction, Share


class ShareModelForm(forms.ModelForm):
    """Инструмент"""

    class Meta:
        model = Share
        fields = "__all__"


class TradeForm(forms.Form):
    share = forms.ModelChoiceField(
        queryset=Share.objects.all().order_by("ticker"),
        label="Акция",
    )
    side = forms.ChoiceField(
        choices=PortfolioTransaction.SIDE_CHOICES,
        label="Операция",
    )
    quantity = forms.IntegerField(
        min_value=1,
        label="Количество",
    )
    price = forms.DecimalField(
        max_digits=18,
        decimal_places=6,
        required=False,
        label="Цена (пусто = текущая рыночная)",
    )


class HistoryPeriodForm(forms.Form):
    PERIOD_CHOICES = (
        (7, "7 дней"),
        (30, "30 дней"),
        (90, "90 дней"),
        (180, "180 дней"),
        (365, "365 дней"),
    )
    days = forms.TypedChoiceField(
        choices=PERIOD_CHOICES,
        coerce=int,
        initial=180,
        label="Период",
    )
