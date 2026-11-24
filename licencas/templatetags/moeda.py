from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def reais(valor):
    """Formata como moeda brasileira: 1234.5 -> 'R$ 1.234,50'. Vazio -> '—'."""
    if valor in (None, ""):
        return "—"
    texto = f"{Decimal(valor):,.2f}"  # 1,234.50
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")
