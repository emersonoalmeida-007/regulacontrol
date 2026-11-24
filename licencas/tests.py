"""Testes automatizados do RegulaControl.

Rodar:  python manage.py test
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core import mail
from django.http import QueryDict
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import alertas, brasilapi, consultas, custos
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

    def test_lista_com_filtros_de_multipla_escolha(self):
        outra = Unidade.objects.create(nome="CD Dois", cnpj="11444777000161")
        self.criar_licenca(-3, numero="VENC-U1")
        self.criar_licenca(10, tipo=self.avcb, numero="V30-U1")
        self.criar_licenca(200, numero="OK-U1")
        self.criar_licenca(10, unidade=outra, numero="V30-U2")
        url = reverse("licencas:lista")

        resp = self.client.get(url, {"status": ["vencida", "vence_30"], "parcial": "1"})
        for numero in ("VENC-U1", "V30-U1", "V30-U2"):
            self.assertContains(resp, numero)
        self.assertNotContains(resp, "OK-U1")

        resp = self.client.get(url, {"status": ["vencida", "vence_30"], "unidade": [outra.pk], "parcial": "1"})
        self.assertContains(resp, "V30-U2")
        self.assertNotContains(resp, "VENC-U1")
        self.assertContains(resp, "Unidades: CD Dois")

        resp = self.client.get(url, {"tipo": [self.afe.pk, self.avcb.pk], "unidade": [self.unidade.pk]})
        self.assertContains(resp, f'value="{self.avcb.pk}" checked')
        self.assertNotContains(resp, "V30-U2")

        csv_txt = self.client.get(reverse("licencas:exportar"), {"status": ["vencida"]}).content.decode()
        self.assertIn("VENC-U1", csv_txt)
        self.assertNotIn("OK-U1", csv_txt)

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


class CustosTests(Base):
    def test_custo_anual_por_periodicidade(self):
        mensal = self.criar_licenca(100, valor=Decimal("100.00"), periodicidade="mensal")
        semestral = self.criar_licenca(100, valor=Decimal("1000.00"), periodicidade="semestral")
        anual = self.criar_licenca(100, valor=Decimal("5000.00"), periodicidade="anual")
        sem_valor = self.criar_licenca(100)
        self.assertEqual(mensal.custo_anual, Decimal("1200.00"))
        self.assertEqual(semestral.custo_anual, Decimal("2000.00"))
        self.assertEqual(anual.custo_anual, Decimal("5000.00"))
        self.assertIsNone(sem_valor.custo_anual)

    def test_resumo_soma_e_agrupa(self):
        self.unidade.porte = "grande_i"
        self.unidade.save()
        self.criar_licenca(100, valor=Decimal("100.00"), periodicidade="mensal")
        self.criar_licenca(100, tipo=self.avcb, valor=Decimal("800.00"), periodicidade="anual")
        self.criar_licenca(100)  # sem valor
        r = custos.resumo_custos()
        self.assertEqual(r["total_anual"], Decimal("2000.00"))
        self.assertEqual(r["media_mensal"], Decimal("166.67"))
        self.assertEqual((r["qtd_com_valor"], r["qtd_sem_valor"]), (2, 1))
        self.assertEqual(r["por_porte"][0]["rotulo"], "Grande Porte – Grupo I")
        anvisa = next(g for g in r["por_orgao"] if g["rotulo"] == "ANVISA")
        self.assertEqual(anvisa["custo_anual"], Decimal("1200.00"))
        self.assertEqual(anvisa["percentual"], Decimal("60.0"))

    def test_fluxo_de_pagamentos(self):
        hoje = date(2027, 3, 15)
        validade = lambda d: dict(data_emissao=d - timedelta(days=200), data_validade=d)  # noqa: E731
        Licenca.objects.create(tipo=self.afe, unidade=self.unidade, numero="M", valor=Decimal("100"),
                               periodicidade="mensal", **validade(date(2027, 12, 1)))
        Licenca.objects.create(tipo=self.afe, unidade=self.unidade, numero="S", valor=Decimal("600"),
                               periodicidade="semestral", **validade(date(2027, 5, 10)))
        Licenca.objects.create(tipo=self.afe, unidade=self.unidade, numero="A", valor=Decimal("2400"),
                               periodicidade="anual", **validade(date(2027, 8, 20)))
        Licenca.objects.create(tipo=self.afe, unidade=self.unidade, numero="ATRASO", valor=Decimal("50"),
                               periodicidade="anual", **validade(date(2027, 1, 5)))
        fluxo = {m["mes"]: m["valor"] for m in custos.fluxo_pagamentos(hoje=hoje)}
        self.assertEqual(len(fluxo), 12)
        self.assertEqual(fluxo["03/2027"], Decimal("150"))   # mensal + anual em atraso
        self.assertEqual(fluxo["05/2027"], Decimal("700"))   # mensal + semestral
        self.assertEqual(fluxo["08/2027"], Decimal("2500"))  # mensal + anual
        self.assertEqual(fluxo["11/2027"], Decimal("700"))   # mensal + semestral (6 meses depois)
        self.assertEqual(fluxo["02/2028"], Decimal("100"))   # só mensal

    def test_valor_aceita_formato_brasileiro(self):
        form = LicencaForm(data={
            "tipo": self.afe.pk, "unidade": self.unidade.pk, "numero": "X", "data_emissao": "2027-01-01",
            "data_validade": "2028-01-01", "valor": "R$ 1.250,50", "periodicidade": "anual", "ativa": True,
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["valor"], Decimal("1250.50"))

    def test_relatorio_e_csv(self):
        self.client.force_login(self.consulta)
        self.criar_licenca(100, valor=Decimal("1000.00"), periodicidade="semestral", numero="CUSTO-1")
        resp = self.client.get(reverse("licencas:relatorio_custos"))
        self.assertContains(resp, "R$ 2.000,00")
        csv_txt = self.client.get(reverse("licencas:exportar_custos")).content.decode("utf-8")
        self.assertIn("2000,00", csv_txt)
        self.assertEqual(self.client.get("/api/custos/").json()["total_anual"], 2000.0)

    def test_filtros_de_multipla_escolha(self):
        outra = Unidade.objects.create(nome="CD Dois", cnpj="11444777000161", porte="epp")
        self.criar_licenca(100, valor=Decimal("100.00"), periodicidade="mensal", numero="U1-M")
        self.criar_licenca(100, tipo=self.avcb, valor=Decimal("500.00"), periodicidade="anual", numero="U1-A")
        self.criar_licenca(100, unidade=outra, valor=Decimal("300.00"), periodicidade="semestral", numero="U2-S")

        def total(**filtros):
            qd = QueryDict(mutable=True)
            for chave, valores in filtros.items():
                qd.setlist(chave, [str(v) for v in valores])
            return custos.resumo_custos(qd)["total_anual"]

        self.assertEqual(total(), Decimal("2300.00"))
        self.assertEqual(total(unidade=[self.unidade.pk]), Decimal("1700.00"))
        self.assertEqual(total(unidade=[self.unidade.pk, outra.pk]), Decimal("2300.00"))  # OU dentro do filtro
        self.assertEqual(total(periodicidade=["mensal", "semestral"]), Decimal("1800.00"))
        self.assertEqual(total(unidade=[self.unidade.pk], periodicidade=["semestral"]), Decimal("0"))  # E entre filtros
        self.assertEqual(total(tipo=[self.avcb.pk]), Decimal("500.00"))
        self.assertEqual(total(porte=["epp"]), Decimal("600.00"))
        self.assertEqual(total(orgao=[self.anvisa.pk]), Decimal("1800.00"))

    def test_relatorio_filtrado_parcial_e_csv(self):
        self.client.force_login(self.consulta)
        self.criar_licenca(100, valor=Decimal("100.00"), periodicidade="anual", numero="FICA")
        self.criar_licenca(100, tipo=self.avcb, valor=Decimal("900.00"), periodicidade="anual", numero="SAI")
        url = reverse("licencas:relatorio_custos")
        resp = self.client.get(url, {"tipo": [self.afe.pk], "parcial": "1"})
        self.assertContains(resp, "R$ 100,00")
        self.assertContains(resp, "Filtros aplicados")
        self.assertNotContains(resp, "<html")
        completo = self.client.get(url, {"tipo": [self.afe.pk]})
        self.assertContains(completo, f'value="{self.afe.pk}" checked')
        csv_txt = self.client.get(reverse("licencas:exportar_custos"), {"tipo": [self.avcb.pk]}).content.decode()
        self.assertIn("900,00", csv_txt)
        self.assertNotIn("100,00", csv_txt)

    def test_unidade_guarda_porte(self):
        self.client.force_login(self.analista)
        resp = self.client.post(reverse("licencas:unidade_editar", args=[self.unidade.pk]), {
            "cnpj": self.unidade.cnpj, "nome": "CD Teste", "porte": "epp",
        })
        self.assertRedirects(resp, reverse("licencas:unidades"))
        self.unidade.refresh_from_db()
        self.assertEqual(self.unidade.get_porte_display(), "Empresa de Pequeno Porte (EPP)")


class DiasAvisoTests(Base):
    def caso(self, dias_aviso, dias_ate_vencer):
        lic = self.criar_licenca(dias_ate_vencer, dias_aviso=dias_aviso)
        return lic.deve_alertar()

    def test_padrao(self):
        self.assertTrue(self.caso(None, 90))
        self.assertTrue(self.caso(None, 60))
        self.assertFalse(self.caso(None, 45))
        self.assertTrue(self.caso(None, 30))
        self.assertTrue(self.caso(None, -3))

    def test_aviso_personalizado_maior_que_30(self):
        self.assertTrue(self.caso(120, 120))
        self.assertFalse(self.caso(120, 90))  # substitui os marcos de 90 e 60
        self.assertTrue(self.caso(120, 30))

    def test_aviso_personalizado_menor_que_30(self):
        self.assertFalse(self.caso(15, 30))
        self.assertFalse(self.caso(15, 16))
        self.assertTrue(self.caso(15, 15))
        self.assertTrue(self.caso(15, 2))

    def test_alerta_usa_dias_personalizados(self):
        self.criar_licenca(120, numero="AVISO-120", dias_aviso=120)
        self.criar_licenca(120, tipo=self.avcb, numero="SEM-AVISO")
        alertas.enviar_alertas()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("vence em 120 dia(s)", mail.outbox[0].body)
        self.assertNotIn("AVCB", mail.outbox[0].body)


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
