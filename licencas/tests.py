"""Testes automatizados do RegulaControl.

Rodar:  python manage.py test
"""
from datetime import date, timedelta
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import alertas, brasilapi, consultas
from .forms import LicencaForm, UnidadeForm
from .models import Licenca, OrgaoEmissor, Renovacao, Status, TipoLicenca, Unidade, calcular_status

HOJE = date(2027, 3, 15)


class CalcularStatusTests(TestCase):
    """A regra central: status pelos dias até o vencimento, incluindo os limites de cada faixa."""

    def caso(self, dias, esperado):
        self.assertEqual(calcular_status(HOJE + timedelta(days=dias), HOJE), esperado, f"{dias} dias")

    def test_vencida_a_partir_do_dia_seguinte(self):
        self.caso(-1, Status.VENCIDA)
        self.caso(-400, Status.VENCIDA)

    def test_vence_no_proprio_dia_ainda_nao_esta_vencida(self):
        self.caso(0, Status.VENCE_30)

    def test_limites_das_faixas(self):
        self.caso(30, Status.VENCE_30)
        self.caso(31, Status.VENCE_60)
        self.caso(60, Status.VENCE_60)
        self.caso(61, Status.VENCE_90)
        self.caso(90, Status.VENCE_90)
        self.caso(91, Status.VIGENTE)


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hoje = timezone.localdate()
        cls.anvisa = OrgaoEmissor.objects.create(sigla="ANVISA", nome="Agência Nacional", esfera="federal")
        cls.bombeiros = OrgaoEmissor.objects.create(sigla="CBPMESP", nome="Bombeiros", esfera="estadual")
        cls.afe = TipoLicenca.objects.create(nome="AFE", orgao=cls.anvisa)
        cls.avcb = TipoLicenca.objects.create(nome="AVCB", orgao=cls.bombeiros)
        cls.unidade = Unidade.objects.create(nome="CD Teste", cnpj="11222333000181")
        cls.analista = User.objects.create_user("analista", "analista@ex.com", "senha-forte-123", first_name="Bia")
        cls.analista.groups.add(Group.objects.get(name="Analista"))
        cls.consulta = User.objects.create_user("consulta", "consulta@ex.com", "senha-forte-123")
        cls.consulta.groups.add(Group.objects.get(name="Consulta"))

    def criar_licenca(self, dias, tipo=None, **extra):
        validade = self.hoje + timedelta(days=dias)
        dados = dict(
            tipo=tipo or self.afe, unidade=self.unidade, numero=f"N{dias}",
            data_emissao=validade - timedelta(days=365), data_validade=validade, responsavel=self.analista,
        )
        dados.update(extra)
        return Licenca.objects.create(**dados)


class ConsultasTests(Base):
    def test_filtro_por_status_bate_com_o_status_calculado(self):
        for dias in (-5, 0, 30, 31, 60, 61, 90, 91, 300):
            self.criar_licenca(dias)
        for status in Status:
            filtradas = consultas.filtrar_por_status(Licenca.objects.all(), status)
            self.assertTrue(filtradas.exists(), status)
            self.assertTrue(all(lic.status == status for lic in filtradas), status)

    def test_resumo_calcula_percentual_de_conformidade(self):
        self.criar_licenca(-10)
        for dias in (10, 100, 200):
            self.criar_licenca(dias, tipo=self.avcb if dias == 10 else self.afe)
        r = consultas.resumo()
        self.assertEqual(r["total"], 4)
        self.assertEqual(r["por_status"]["vencida"], 1)
        self.assertEqual(r["conformidade_pct"], 75.0)

    def test_resumo_ignora_licencas_inativas(self):
        self.criar_licenca(-10, ativa=False)
        self.assertEqual(consultas.resumo()["total"], 0)

    def test_pendencias_por_orgao(self):
        self.criar_licenca(-1)
        self.criar_licenca(5, tipo=self.avcb)
        self.criar_licenca(200)
        self.assertEqual(
            sorted(consultas.pendencias_por_orgao(), key=lambda p: p["orgao"]),
            [{"orgao": "ANVISA", "quantidade": 1}, {"orgao": "CBPMESP", "quantidade": 1}],
        )

    def test_vencimentos_por_mes_tem_12_meses(self):
        self.assertEqual(len(consultas.vencimentos_por_mes()), 12)


class RenovacaoTests(Base):
    def test_renovacao_atualiza_licenca_e_guarda_validade_anterior(self):
        lic = self.criar_licenca(10)
        anterior = lic.data_validade
        nova = self.hoje + timedelta(days=375)
        Renovacao.objects.create(licenca=lic, nova_emissao=self.hoje, nova_validade=nova, registrado_por=self.analista)
        lic.refresh_from_db()
        self.assertEqual(lic.data_validade, nova)
        self.assertEqual(lic.renovacoes.get().validade_anterior, anterior)
        self.assertEqual(lic.status, Status.VIGENTE)


class FormulariosTests(Base):
    def test_validade_antes_da_emissao_e_recusada(self):
        form = LicencaForm(data={
            "tipo": self.afe.pk, "unidade": self.unidade.pk, "numero": "X",
            "data_emissao": "2027-05-01", "data_validade": "2027-04-01", "ativa": True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("data_validade", form.errors)

    def test_cnpj_aceita_mascara_e_guarda_so_numeros(self):
        form = UnidadeForm(data={"cnpj": "11.444.777/0001-61", "nome": "Filial"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["cnpj"], "11444777000161")

    def test_cnpj_incompleto_e_recusado(self):
        self.assertFalse(UnidadeForm(data={"cnpj": "123", "nome": "X"}).is_valid())


class PermissoesTests(Base):
    def test_paginas_exigem_login(self):
        resp = self.client.get(reverse("licencas:lista"))
        self.assertRedirects(resp, f"{reverse('login')}?next={reverse('licencas:lista')}")

    def test_perfil_consulta_ve_mas_nao_cadastra(self):
        self.client.force_login(self.consulta)
        self.assertEqual(self.client.get(reverse("licencas:lista")).status_code, 200)
        self.assertEqual(self.client.get(reverse("licencas:criar")).status_code, 403)

    def test_analista_cadastra_licenca(self):
        self.client.force_login(self.analista)
        resp = self.client.post(reverse("licencas:criar"), {
            "tipo": self.afe.pk, "unidade": self.unidade.pk, "numero": "AFE-1",
            "data_emissao": "2027-01-01", "data_validade": "2028-01-01",
            "responsavel": self.analista.pk, "ativa": "on",
        })
        lic = Licenca.objects.get(numero="AFE-1")
        self.assertRedirects(resp, lic.get_absolute_url())


class TelasTests(Base):
    def setUp(self):
        self.client.force_login(self.analista)

    def test_painel_mostra_indicadores(self):
        self.criar_licenca(-3)
        resp = self.client.get(reverse("licencas:painel"))
        self.assertContains(resp, "Painel de conformidade")
        self.assertContains(resp, 'id="dados-graficos"')

    def test_lista_parcial_devolve_so_a_tabela_filtrada(self):
        self.criar_licenca(-3, numero="VENCIDA-1")
        self.criar_licenca(200, tipo=self.avcb, numero="OK-1")
        resp = self.client.get(reverse("licencas:lista"), {"status": "vencida", "parcial": "1"})
        self.assertContains(resp, "VENCIDA-1")
        self.assertNotContains(resp, "OK-1")
        self.assertNotContains(resp, "<html")

    def test_exportar_csv(self):
        self.criar_licenca(10, numero="CSV-1")
        resp = self.client.get(reverse("licencas:exportar"))
        self.assertEqual(resp["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("CSV-1", resp.content.decode("utf-8"))

    def test_renovar_pela_tela(self):
        lic = self.criar_licenca(5)
        resp = self.client.post(reverse("licencas:renovar", args=[lic.pk]), {
            "nova_emissao": self.hoje.isoformat(),
            "nova_validade": (self.hoje + timedelta(days=365)).isoformat(),
        })
        self.assertRedirects(resp, lic.get_absolute_url())
        lic.refresh_from_db()
        self.assertEqual(lic.status, Status.VIGENTE)


class BrasilApiTests(Base):
    def setUp(self):
        self.client.force_login(self.analista)

    @mock.patch("licencas.views.brasilapi.consultar_cnpj")
    def test_busca_cnpj_devolve_dados(self, consultar):
        consultar.return_value = {"razao_social": "EMPRESA X", "nome_fantasia": "", "logradouro": "", "municipio": "Osasco", "uf": "SP"}
        resp = self.client.get(reverse("licencas:buscar_cnpj", args=["11444777000161"]))
        self.assertEqual(resp.json()["razao_social"], "EMPRESA X")
        consultar.assert_called_once_with("11444777000161")

    @mock.patch("licencas.views.brasilapi.consultar_cnpj", side_effect=brasilapi.CnpjNaoEncontrado)
    def test_cnpj_nao_encontrado(self, _):
        resp = self.client.get(reverse("licencas:buscar_cnpj", args=["11444777000161"]))
        self.assertEqual(resp.status_code, 404)

    def test_cnpj_invalido_nem_consulta_a_api(self):
        resp = self.client.get(reverse("licencas:buscar_cnpj", args=["123"]))
        self.assertEqual(resp.status_code, 400)


class ApiTests(Base):
    def test_api_exige_autenticacao(self):
        self.assertIn(self.client.get("/api/licencas/").status_code, (401, 403))

    def test_api_lista_com_status_e_filtro(self):
        self.criar_licenca(-3, numero="V1")
        self.criar_licenca(200, tipo=self.avcb, numero="OK")
        self.client.force_login(self.consulta)
        dados = self.client.get("/api/licencas/", {"status": "vencida"}).json()
        self.assertEqual(dados["count"], 1)
        self.assertEqual(dados["results"][0]["numero"], "V1")
        self.assertEqual(dados["results"][0]["status"], "vencida")

    def test_api_resumo(self):
        self.criar_licenca(10)
        self.client.force_login(self.consulta)
        dados = self.client.get("/api/resumo/").json()
        self.assertEqual(dados["total"], 1)
        self.assertEqual(len(dados["vencimentos_por_mes"]), 12)


class AlertasTests(Base):
    def test_um_email_por_responsavel_so_com_licencas_que_precisam_de_atencao(self):
        self.criar_licenca(-2, numero="VENC")
        self.criar_licenca(20, tipo=self.avcb, numero="V20")
        self.criar_licenca(60, numero="M60", unidade=Unidade.objects.create(nome="U2", cnpj="11444777000161"))
        self.criar_licenca(45, numero="SEM-ALERTA", unidade=Unidade.objects.create(nome="U3", cnpj="11444777000242"))
        enviados = alertas.enviar_alertas()
        self.assertEqual(enviados, 1)
        self.assertEqual(len(mail.outbox), 1)
        corpo = mail.outbox[0].body
        self.assertIn("VENCIDA", corpo)
        self.assertIn("vence em 60 dia(s)", corpo)
        self.assertNotIn("U3", corpo)
        self.assertEqual(mail.outbox[0].to, ["analista@ex.com"])

    def test_simulacao_nao_envia(self):
        self.criar_licenca(-2)
        self.assertEqual(alertas.enviar_alertas(simular=True), 1)
        self.assertEqual(len(mail.outbox), 0)
