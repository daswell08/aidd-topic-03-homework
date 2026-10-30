from decimal import Decimal

from django import forms

from .models import (
    InvestmentStrategy,
    Portfolio,
    PortfolioTransaction,
    PriceAlert,
    Share,
)


class ShareModelForm(forms.ModelForm):
    """Инструмент"""

    class Meta:
        model = Share
        fields = "__all__"


class PriceAlertForm(forms.ModelForm):
    class Meta:
        model = PriceAlert
        fields = ["direction", "target_price"]


class PortfolioForm(forms.ModelForm):
    class Meta:
        model = Portfolio
        fields = ["name"]


class PortfolioTransactionForm(forms.ModelForm):
    price = forms.DecimalField(
        required=False,
        max_digits=20,
        decimal_places=9,
        min_value=Decimal("0.000000001"),
        label="Цена за акцию (пусто — текущая)",
    )

    class Meta:
        model = PortfolioTransaction
        fields = ["share", "side", "quantity", "price"]
        widgets = {
            "quantity": forms.NumberInput(attrs={"min": "0.00000001"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["quantity"].min_value = Decimal("0.00000001")


class InvestmentStrategyForm(forms.ModelForm):
    class Meta:
        model = InvestmentStrategy
        fields = ["name", "share", "buy_below", "sell_above", "quantity"]

    def clean(self):
        cleaned_data = super().clean()
        buy_below = cleaned_data.get("buy_below")
        sell_above = cleaned_data.get("sell_above")
        if buy_below is not None and sell_above is not None:
            if sell_above <= buy_below:
                self.add_error(
                    "sell_above", "Цена продажи должна быть выше цены покупки."
                )
        return cleaned_data
