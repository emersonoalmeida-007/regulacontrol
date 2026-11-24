import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from . import brasilapi, consultas, custos
from .forms import LicencaForm, RenovacaoForm, UnidadeForm
from .models import Licenca, OrgaoEmissor, Status, Unidade
from .permissoes import PodeEditarMixin, pode_editar


@login_required
def painel(request):
    """Painel de conformidade (RF09)."""
    contexto = {
        "resumo": consultas.resumo(),
        "custo_anual": custos.resumo_custos()["total_anual"],
        "status_choices": Status.choices,
        "dados_graficos": {
            "vencimentos": consultas.vencimentos_por_mes(),
            "pendencias": consultas.pendencias_por_orgao(),
        },
        "proximas": consultas.filtrar_por_status(consultas.licencas_ativas(), Status.VENCE_30)[:10],
        "vencidas": consultas.filtrar_por_status(consultas.licencas_ativas(), Status.VENCIDA)[:10],
    }
    return render(request, "licencas/painel.html", contexto)


class LicencaListView(LoginRequiredMixin, ListView):
    """Lista com filtros (RF07). Com ?parcial=1 devolve só a tabela, usada pelo JavaScript."""

    template_name = "licencas/lista.html"
    context_object_name = "licencas"

    def get_queryset(self):
        return consultas.aplicar_filtros(consultas.licencas_ativas(), self.request.GET)

    def get_template_names(self):
        if self.request.GET.get("parcial"):
            return ["licencas/_tabela.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            unidades=Unidade.objects.all(),
            orgaos=OrgaoEmissor.objects.all(),
            status_choices=Status.choices,
            filtros=self.request.GET,
        )
        return ctx


class LicencaDetailView(LoginRequiredMixin, DetailView):
    model = Licenca
    template_name = "licencas/detalhe.html"
    context_object_name = "licenca"

    def get_queryset(self):
        return Licenca.objects.select_related("tipo__orgao", "unidade", "responsavel").prefetch_related(
            "renovacoes__registrado_por"
        )


class LicencaCreateView(LoginRequiredMixin, PodeEditarMixin, CreateView):
    model = Licenca
    form_class = LicencaForm
    template_name = "licencas/form.html"
    extra_context = {"titulo": "Nova licença"}

    def form_valid(self, form):
        messages.success(self.request, "Licença cadastrada.")
        return super().form_valid(form)


class LicencaUpdateView(LoginRequiredMixin, PodeEditarMixin, UpdateView):
    model = Licenca
    form_class = LicencaForm
    template_name = "licencas/form.html"
    extra_context = {"titulo": "Editar licença"}

    def form_valid(self, form):
        messages.success(self.request, "Licença atualizada.")
        return super().form_valid(form)


@login_required
def renovar(request, pk):
    """Registra uma renovação (RF06) e atualiza as datas da licença."""
    licenca = get_object_or_404(Licenca, pk=pk)
    if not pode_editar(request.user):
        messages.error(request, "Seu perfil só permite consulta.")
        return redirect(licenca)
    form = RenovacaoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        renovacao = form.save(commit=False)
        renovacao.licenca = licenca
        renovacao.registrado_por = request.user
        renovacao.save()
        messages.success(request, f"Renovação registrada. Nova validade: {renovacao.nova_validade:%d/%m/%Y}.")
        return redirect(licenca)
    return render(request, "licencas/renovar.html", {"licenca": licenca, "form": form})


@login_required
def exportar_csv(request):
    """Exporta a lista filtrada em CSV (RF11), pronto para abrir no Excel."""
    qs = consultas.aplicar_filtros(consultas.licencas_ativas(), request.GET)
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = 'attachment; filename="licencas.csv"'
    resposta.write("﻿")  # BOM para o Excel reconhecer acentos
    w = csv.writer(resposta, delimiter=";")
    w.writerow(["Tipo", "Órgão", "Unidade", "Número", "Emissão", "Validade", "Dias restantes", "Status", "Responsável"])
    for lic in qs:
        w.writerow([
            lic.tipo.nome, lic.tipo.orgao.sigla, lic.unidade.nome, lic.numero,
            f"{lic.data_emissao:%d/%m/%Y}", f"{lic.data_validade:%d/%m/%Y}", lic.dias_restantes,
            lic.status_label, lic.responsavel.get_full_name() if lic.responsavel else "",
        ])
    return resposta


class UnidadeListView(LoginRequiredMixin, ListView):
    model = Unidade
    template_name = "licencas/unidades.html"
    context_object_name = "unidades"


class UnidadeCreateView(LoginRequiredMixin, PodeEditarMixin, CreateView):
    model = Unidade
    form_class = UnidadeForm
    template_name = "licencas/unidade_form.html"
    success_url = reverse_lazy("licencas:unidades")

    def form_valid(self, form):
        messages.success(self.request, "Unidade cadastrada.")
        return super().form_valid(form)


class UnidadeUpdateView(LoginRequiredMixin, PodeEditarMixin, UpdateView):
    model = Unidade
    form_class = UnidadeForm
    template_name = "licencas/unidade_form.html"
    success_url = reverse_lazy("licencas:unidades")

    def form_valid(self, form):
        messages.success(self.request, "Unidade atualizada.")
        return super().form_valid(form)


@login_required
def relatorio_custos(request):
    """Relatório gerencial de custos (valores, periodicidade e fluxo de pagamentos)."""
    fluxo = custos.fluxo_pagamentos()
    contexto = {
        "resumo": custos.resumo_custos(),
        "fluxo": fluxo,
        "total_fluxo": sum((m["valor"] for m in fluxo), custos.ZERO),
        "dados_fluxo": [{"mes": m["mes"], "valor": float(m["valor"])} for m in fluxo],
        "licencas": custos.licencas_com_valor().order_by("unidade__nome", "tipo__nome"),
        "sem_valor": consultas.licencas_ativas().filter(valor__isnull=True),
    }
    return render(request, "licencas/relatorio_custos.html", contexto)


@login_required
def exportar_custos_csv(request):
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = 'attachment; filename="custos_licencas.csv"'
    resposta.write("﻿")
    w = csv.writer(resposta, delimiter=";")
    w.writerow(["Unidade", "Porte", "Licença", "Órgão", "Valor", "Periodicidade", "Custo anual", "Validade"])
    for lic in custos.licencas_com_valor().order_by("unidade__nome", "tipo__nome"):
        w.writerow([
            lic.unidade.nome, lic.unidade.get_porte_display(), lic.tipo.nome, lic.tipo.orgao.sigla,
            f"{lic.valor:.2f}".replace(".", ","), lic.get_periodicidade_display(),
            f"{lic.custo_anual:.2f}".replace(".", ","), f"{lic.data_validade:%d/%m/%Y}",
        ])
    return resposta


@login_required
def buscar_cnpj(request, cnpj):
    """Ponte entre o JavaScript da tela e a BrasilAPI (RF02)."""
    cnpj = "".join(ch for ch in cnpj if ch.isdigit())
    if len(cnpj) != 14:
        return JsonResponse({"erro": "O CNPJ precisa ter 14 números."}, status=400)
    try:
        return JsonResponse(brasilapi.consultar_cnpj(cnpj))
    except brasilapi.CnpjNaoEncontrado:
        return JsonResponse({"erro": "CNPJ não encontrado na Receita Federal."}, status=404)
    except brasilapi.BrasilApiIndisponivel:
        return JsonResponse({"erro": "BrasilAPI indisponível. Preencha os dados manualmente."}, status=502)
