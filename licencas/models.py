"""Modelos do RegulaControl: unidades, órgãos, tipos de licença, licenças e renovações."""
from datetime import date

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Status(models.TextChoices):
    """Situação de uma licença, calculada a partir da data de validade."""

    VENCIDA = "vencida", "Vencida"
    VENCE_30 = "vence_30", "Vence em até 30 dias"
    VENCE_60 = "vence_60", "Vence em até 60 dias"
    VENCE_90 = "vence_90", "Vence em até 90 dias"
    VIGENTE = "vigente", "Vigente"


def calcular_status(data_validade: date, hoje: date | None = None) -> str:
    """Regra central do sistema: classifica a licença pelos dias até o vencimento.

    A licença vale até o fim do dia da validade; no dia seguinte está vencida.
    """
    hoje = hoje or timezone.localdate()
    dias = (data_validade - hoje).days
    if dias < 0:
        return Status.VENCIDA
    if dias <= 30:
        return Status.VENCE_30
    if dias <= 60:
        return Status.VENCE_60
    if dias <= 90:
        return Status.VENCE_90
    return Status.VIGENTE


cnpj_validator = RegexValidator(r"^\d{14}$", "Informe o CNPJ com 14 números, sem pontos ou barras.")


class Unidade(models.Model):
    """Estabelecimento da empresa (matriz ou filial) que precisa de licenças."""

    nome = models.CharField("nome da unidade", max_length=120)
    cnpj = models.CharField("CNPJ", max_length=14, unique=True, validators=[cnpj_validator])
    razao_social = models.CharField("razão social", max_length=200, blank=True)
    logradouro = models.CharField(max_length=200, blank=True)
    municipio = models.CharField("município", max_length=100, blank=True)
    uf = models.CharField("UF", max_length=2, blank=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "unidade"

    def __str__(self):
        return self.nome

    @property
    def cnpj_formatado(self):
        c = self.cnpj
        return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else c


class OrgaoEmissor(models.Model):
    class Esfera(models.TextChoices):
        FEDERAL = "federal", "Federal"
        ESTADUAL = "estadual", "Estadual"
        MUNICIPAL = "municipal", "Municipal"
        CONSELHO = "conselho", "Conselho de classe"

    sigla = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=150)
    esfera = models.CharField(max_length=10, choices=Esfera.choices)

    class Meta:
        ordering = ["sigla"]
        verbose_name = "órgão emissor"
        verbose_name_plural = "órgãos emissores"

    def __str__(self):
        return self.sigla


class TipoLicenca(models.Model):
    nome = models.CharField(max_length=150)
    orgao = models.ForeignKey(OrgaoEmissor, on_delete=models.PROTECT, related_name="tipos", verbose_name="órgão")
    descricao = models.TextField("descrição", blank=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "tipo de licença"
        verbose_name_plural = "tipos de licença"

    def __str__(self):
        return f"{self.nome} ({self.orgao.sigla})"


class Licenca(models.Model):
    tipo = models.ForeignKey(TipoLicenca, on_delete=models.PROTECT, related_name="licencas")
    unidade = models.ForeignKey(Unidade, on_delete=models.PROTECT, related_name="licencas")
    numero = models.CharField("número/protocolo", max_length=60)
    data_emissao = models.DateField("data de emissão")
    data_validade = models.DateField("data de validade")
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="licencas",
        verbose_name="responsável",
    )
    arquivo = models.FileField("arquivo PDF", upload_to="licencas/%Y/", blank=True)
    observacoes = models.TextField("observações", blank=True)
    ativa = models.BooleanField(default=True, help_text="Desmarque se a licença deixou de ser necessária.")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["data_validade"]
        verbose_name = "licença"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(data_validade__gte=models.F("data_emissao")),
                name="validade_depois_da_emissao",
            )
        ]

    def __str__(self):
        return f"{self.tipo.nome} – {self.unidade.nome}"

    def get_absolute_url(self):
        return reverse("licencas:detalhe", args=[self.pk])

    @property
    def status(self):
        return calcular_status(self.data_validade)

    @property
    def status_label(self):
        return Status(self.status).label

    @property
    def dias_restantes(self):
        return (self.data_validade - timezone.localdate()).days

    @property
    def dias_atraso(self):
        return max(0, -self.dias_restantes)


class Renovacao(models.Model):
    """Histórico: cada renovação registra a validade anterior e atualiza a licença."""

    licenca = models.ForeignKey(Licenca, on_delete=models.CASCADE, related_name="renovacoes")
    validade_anterior = models.DateField(editable=False)
    nova_emissao = models.DateField("nova data de emissão")
    nova_validade = models.DateField("nova data de validade")
    numero_protocolo = models.CharField("número/protocolo", max_length=60, blank=True)
    observacao = models.TextField("observação", blank=True)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    registrado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-registrado_em"]
        verbose_name = "renovação"
        verbose_name_plural = "renovações"

    def __str__(self):
        return f"Renovação de {self.licenca} até {self.nova_validade:%d/%m/%Y}"

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.validade_anterior = self.licenca.data_validade
            self.licenca.data_emissao = self.nova_emissao
            self.licenca.data_validade = self.nova_validade
            if self.numero_protocolo:
                self.licenca.numero = self.numero_protocolo
            self.licenca.save()
        super().save(*args, **kwargs)
