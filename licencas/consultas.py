"""Consultas reutilizadas pelas telas, pela API e pelo painel de conformidade."""
from collections import Counter
from datetime import date, timedelta

from django.db.models import Q, QuerySet
from django.utils import timezone

from .models import Licenca, Status, calcular_status


def filtrar_por_status(qs: QuerySet, status: str, hoje: date | None = None) -> QuerySet:
    """Traduz o status calculado em faixas de data, para filtrar direto no banco."""
    hoje = hoje or timezone.localdate()
    d = lambda n: hoje + timedelta(days=n)  # noqa: E731
    faixas = {
        Status.VENCIDA: Q(data_validade__lt=hoje),
        Status.VENCE_30: Q(data_validade__gte=hoje, data_validade__lte=d(30)),
        Status.VENCE_60: Q(data_validade__gt=d(30), data_validade__lte=d(60)),
        Status.VENCE_90: Q(data_validade__gt=d(60), data_validade__lte=d(90)),
        Status.VIGENTE: Q(data_validade__gt=d(90)),
    }
    return qs.filter(faixas[status]) if status in faixas else qs


def aplicar_filtros(qs: QuerySet, params) -> QuerySet:
    """Filtros da lista (RF07) e da API: unidade, órgão, status e texto livre."""
    if params.get("unidade"):
        qs = qs.filter(unidade_id=params["unidade"])
    if params.get("orgao"):
        qs = qs.filter(tipo__orgao_id=params["orgao"])
    if params.get("status"):
        qs = filtrar_por_status(qs, params["status"])
    if params.get("q"):
        termo = params["q"].strip()
        qs = qs.filter(
            Q(numero__icontains=termo)
            | Q(tipo__nome__icontains=termo)
            | Q(unidade__nome__icontains=termo)
            | Q(tipo__orgao__sigla__icontains=termo)
        )
    return qs


def licencas_ativas() -> QuerySet:
    return Licenca.objects.filter(ativa=True).select_related("tipo__orgao", "unidade", "responsavel")


def resumo(hoje: date | None = None) -> dict:
    """Indicadores do painel (RF09)."""
    hoje = hoje or timezone.localdate()
    contagem = Counter(calcular_status(v, hoje) for v in licencas_ativas().values_list("data_validade", flat=True))
    total = sum(contagem.values())
    em_dia = total - contagem[Status.VENCIDA]
    return {
        "total": total,
        "por_status": {s.value: contagem[s] for s in Status},
        "conformidade_pct": round(100 * em_dia / total, 1) if total else 100.0,
    }


def vencimentos_por_mes(meses: int = 12, hoje: date | None = None) -> list[dict]:
    """Quantas licenças vencem em cada um dos próximos meses (começando pelo atual)."""
    hoje = hoje or timezone.localdate()
    chaves = []
    ano, mes = hoje.year, hoje.month
    for _ in range(meses):
        chaves.append((ano, mes))
        mes += 1
        if mes > 12:
            ano, mes = ano + 1, 1
    contagem = Counter(
        (v.year, v.month)
        for v in licencas_ativas().filter(data_validade__gte=hoje.replace(day=1)).values_list("data_validade", flat=True)
    )
    return [{"mes": f"{m:02d}/{a}", "quantidade": contagem[(a, m)]} for a, m in chaves]


def pendencias_por_orgao(hoje: date | None = None) -> list[dict]:
    """Licenças vencidas ou vencendo em 30 dias, agrupadas por órgão emissor."""
    hoje = hoje or timezone.localdate()
    pendentes = licencas_ativas().filter(data_validade__lte=hoje + timedelta(days=30))
    contagem = Counter(pendentes.values_list("tipo__orgao__sigla", flat=True))
    return [{"orgao": o, "quantidade": q} for o, q in contagem.most_common()]
