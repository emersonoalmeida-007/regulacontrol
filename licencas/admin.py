from django.contrib import admin

from .models import Licenca, OrgaoEmissor, RegistroMensal, Renovacao, TipoLicenca, Unidade


@admin.register(RegistroMensal)
class RegistroMensalAdmin(admin.ModelAdmin):
    list_display = ["mes", "unidade", "total", "em_dia", "vencidas", "atualizado_em"]
    list_filter = ["unidade"]
    date_hierarchy = "mes"


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = ["nome", "cnpj_formatado", "porte", "municipio", "uf"]
    list_filter = ["porte"]
    search_fields = ["nome", "cnpj", "razao_social"]


@admin.register(OrgaoEmissor)
class OrgaoAdmin(admin.ModelAdmin):
    list_display = ["sigla", "nome", "esfera"]


@admin.register(TipoLicenca)
class TipoAdmin(admin.ModelAdmin):
    list_display = ["nome", "orgao"]
    list_filter = ["orgao"]


class RenovacaoInline(admin.TabularInline):
    model = Renovacao
    extra = 0
    readonly_fields = ["validade_anterior", "registrado_por", "registrado_em"]


@admin.register(Licenca)
class LicencaAdmin(admin.ModelAdmin):
    list_display = ["tipo", "unidade", "numero", "data_validade", "status_label", "valor", "periodicidade", "responsavel", "ativa"]
    list_filter = ["tipo__orgao", "unidade", "periodicidade", "ativa"]
    search_fields = ["numero", "tipo__nome", "unidade__nome"]
    date_hierarchy = "data_validade"
    inlines = [RenovacaoInline]

    @admin.display(description="status")
    def status_label(self, obj):
        return obj.status_label
