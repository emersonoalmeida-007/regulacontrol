from django.urls import path

from . import views

app_name = "licencas"

urlpatterns = [
    path("", views.painel, name="painel"),
    path("licencas/", views.LicencaListView.as_view(), name="lista"),
    path("licencas/nova/", views.LicencaCreateView.as_view(), name="criar"),
    path("licencas/exportar.csv", views.exportar_csv, name="exportar"),
    path("licencas/<int:pk>/", views.LicencaDetailView.as_view(), name="detalhe"),
    path("licencas/<int:pk>/editar/", views.LicencaUpdateView.as_view(), name="editar"),
    path("licencas/<int:pk>/renovar/", views.renovar, name="renovar"),
    path("unidades/", views.UnidadeListView.as_view(), name="unidades"),
    path("unidades/nova/", views.UnidadeCreateView.as_view(), name="unidade_criar"),
    path("unidades/<int:pk>/editar/", views.UnidadeUpdateView.as_view(), name="unidade_editar"),
    path("relatorios/custos/", views.relatorio_custos, name="relatorio_custos"),
    path("relatorios/custos.csv", views.exportar_custos_csv, name="exportar_custos"),
    path("unidades/cnpj/<str:cnpj>/", views.buscar_cnpj, name="buscar_cnpj"),
]
