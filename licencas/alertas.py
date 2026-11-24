"""Alertas de vencimento por e-mail (RF08).

Cada responsável recebe UM e-mail por dia com:
- licenças vencidas ou que vencem em até 30 dias (todo dia, até renovar);
- licenças que completam exatamente 90 ou 60 dias para o vencimento (lembrete antecipado).
"""
from collections import defaultdict
from datetime import date, timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone

from .consultas import licencas_ativas

MARCOS_ANTECIPADOS = (90, 60)


def licencas_para_alertar(hoje: date | None = None):
    hoje = hoje or timezone.localdate()
    filtro = Q(data_validade__lte=hoje + timedelta(days=30))
    for dias in MARCOS_ANTECIPADOS:
        filtro |= Q(data_validade=hoje + timedelta(days=dias))
    return licencas_ativas().filter(filtro).exclude(responsavel__isnull=True).exclude(responsavel__email="")


def montar_mensagem(licencas) -> str:
    linhas = ["Olá,", "", "Estas licenças sob sua responsabilidade precisam de atenção:", ""]
    for lic in licencas:
        if lic.dias_restantes < 0:
            prazo = f"VENCIDA há {lic.dias_atraso} dia(s)"
        else:
            prazo = f"vence em {lic.dias_restantes} dia(s)"
        linhas.append(
            f"- {lic.tipo.nome} ({lic.tipo.orgao.sigla}) – {lic.unidade.nome} – "
            f"validade {lic.data_validade:%d/%m/%Y} – {prazo}"
        )
    linhas += ["", "Acesse o RegulaControl para registrar a renovação.", "", "RegulaControl"]
    return "\n".join(linhas)


def enviar_alertas(hoje: date | None = None, simular: bool = False) -> int:
    """Envia os e-mails e devolve quantos foram enviados (ou seriam, em simulação)."""
    por_responsavel = defaultdict(list)
    for lic in licencas_para_alertar(hoje):
        por_responsavel[lic.responsavel].append(lic)

    for usuario, licencas in por_responsavel.items():
        vencidas = sum(1 for lic in licencas if lic.dias_restantes < 0)
        assunto = f"[RegulaControl] {len(licencas)} licença(s) exigem atenção"
        if vencidas:
            assunto += f" – {vencidas} vencida(s)"
        if not simular:
            send_mail(assunto, montar_mensagem(licencas), settings.DEFAULT_FROM_EMAIL, [usuario.email])
    return len(por_responsavel)
