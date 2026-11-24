"""API REST própria (RF10), com Django REST Framework.

GET /api/licencas/            lista (filtros: status, unidade, orgao, q)
GET /api/licencas/<id>/       detalhe
GET /api/resumo/              indicadores do painel
GET /api/custos/              custos por unidade, órgão, porte, periodicidade e fluxo de 12 meses
"""
from rest_framework import serializers, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import consultas, custos
from .models import Licenca


class LicencaSerializer(serializers.ModelSerializer):
    tipo = serializers.CharField(source="tipo.nome")
    orgao = serializers.CharField(source="tipo.orgao.sigla")
    unidade = serializers.CharField(source="unidade.nome")
    responsavel = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)
    status_label = serializers.CharField(read_only=True)
    dias_restantes = serializers.IntegerField(read_only=True)
    porte_unidade = serializers.CharField(source="unidade.get_porte_display", read_only=True)
    custo_anual = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Licenca
        fields = [
            "id", "tipo", "orgao", "unidade", "porte_unidade", "numero", "data_emissao", "data_validade",
            "dias_restantes", "status", "status_label", "responsavel",
            "valor", "periodicidade", "custo_anual", "dias_aviso",
        ]

    def get_responsavel(self, obj):
        return obj.responsavel.get_full_name() if obj.responsavel else None


class LicencaViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LicencaSerializer

    def get_queryset(self):
        return consultas.aplicar_filtros(consultas.licencas_ativas(), self.request.query_params)


@api_view(["GET"])
def resumo_custos(request):
    r = custos.resumo_custos(request.query_params)
    return Response({
        "total_anual": r["total_anual"],
        "media_mensal": r["media_mensal"],
        "por_unidade": r["por_unidade"],
        "por_orgao": r["por_orgao"],
        "por_porte": r["por_porte"],
        "por_periodicidade": r["por_periodicidade"],
        "fluxo_12_meses": custos.fluxo_pagamentos(params=request.query_params),
    })


@api_view(["GET"])
def resumo(request):
    return Response({
        **consultas.resumo(),
        "vencimentos_por_mes": consultas.vencimentos_por_mes(),
        "pendencias_por_orgao": consultas.pendencias_por_orgao(),
    })
