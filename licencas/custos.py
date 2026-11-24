"""Controle de custos das licenças: custo anualizado, agrupamentos e fluxo de pagamentos.

Regras:
- custo anual = valor × pagamentos por ano (mensal 12, semestral 2, anual 1);
- fluxo de pagamentos (próximos 12 meses):
    mensal    → todo mês, a partir do mês atual;
    semestral → no mês da validade e a cada 6 meses;
    anual     → no mês da validade.
  Se a validade já passou, o pagamento entra no mês atual (renovação em atraso).
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.utils import timezone

from .consultas import licencas_ativas
from .models import MESES_ENTRE_PAGAMENTOS, Periodicidade, Porte

ZERO = Decimal("0.00")


def _indice_mes(d: date) -> int:
    return d.year * 12 + d.month - 1


def _rotulo(indice: int) -> str:
    return f"{indice % 12 + 1:02d}/{indice // 12}"


def licencas_com_valor():
    return licencas_ativas().filter(valor__isnull=False)


def resumo_custos() -> dict:
    """Indicadores e agrupamentos do relatório gerencial."""
    licencas = list(licencas_ativas())
    com_valor = [lic for lic in licencas if lic.valor is not None]
    total_anual = sum((lic.custo_anual for lic in com_valor), ZERO)

    def agrupar(chave, rotulo):
        grupos = defaultdict(lambda: {"quantidade": 0, "custo_anual": ZERO})
        for lic in com_valor:
            g = grupos[chave(lic)]
            g["rotulo"] = rotulo(lic)
            g["quantidade"] += 1
            g["custo_anual"] += lic.custo_anual
        linhas = sorted(grupos.values(), key=lambda g: g["custo_anual"], reverse=True)
        for g in linhas:
            g["percentual"] = round(100 * g["custo_anual"] / total_anual, 1) if total_anual else 0
        return linhas

    return {
        "total_anual": total_anual,
        "media_mensal": (total_anual / 12).quantize(Decimal("0.01")),
        "qtd_com_valor": len(com_valor),
        "qtd_sem_valor": len(licencas) - len(com_valor),
        "por_unidade": agrupar(
            lambda lic: lic.unidade_id,
            lambda lic: f"{lic.unidade.nome}"
            + (f" · {Porte(lic.unidade.porte).label}" if lic.unidade.porte else ""),
        ),
        "por_orgao": agrupar(lambda lic: lic.tipo.orgao_id, lambda lic: lic.tipo.orgao.sigla),
        "por_periodicidade": agrupar(lambda lic: lic.periodicidade, lambda lic: Periodicidade(lic.periodicidade).label),
        "por_porte": agrupar(
            lambda lic: lic.unidade.porte or "",
            lambda lic: Porte(lic.unidade.porte).label if lic.unidade.porte else "Porte não informado",
        ),
    }


def fluxo_pagamentos(meses: int = 12, hoje: date | None = None) -> list[dict]:
    """Quanto será pago em cada um dos próximos meses, começando pelo mês atual."""
    hoje = hoje or timezone.localdate()
    inicio = _indice_mes(hoje)
    fim = inicio + meses
    valores = defaultdict(lambda: ZERO)
    quantidades = defaultdict(int)

    for lic in licencas_com_valor():
        passo = MESES_ENTRE_PAGAMENTOS[lic.periodicidade]
        if lic.periodicidade == Periodicidade.MENSAL:
            primeiro = inicio
        else:
            primeiro = max(_indice_mes(lic.data_validade), inicio)
        for mes in range(primeiro, fim, passo):
            valores[mes] += lic.valor
            quantidades[mes] += 1

    return [
        {"mes": _rotulo(m), "valor": valores[m], "quantidade": quantidades[m]}
        for m in range(inicio, fim)
    ]
