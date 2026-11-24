"""Cria dados FICTÍCIOS para demonstração e para o vídeo do PI.

Empresa, CNPJs, números de licença e pessoas são inventados. Não use dados reais
sem autorização por escrito da organização parceira (LGPD).
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from licencas.models import Licenca, OrgaoEmissor, Periodicidade, Porte, TipoLicenca, Unidade
from licencas.permissoes import GRUPO_ADMIN, GRUPO_ANALISTA, GRUPO_CONSULTA

SENHA_DEMO = "demo12345"

ORGAOS = [
    ("ANVISA", "Agência Nacional de Vigilância Sanitária", "federal"),
    ("VISA-SP", "Vigilância Sanitária Municipal de São Paulo", "municipal"),
    ("CBPMESP", "Corpo de Bombeiros da Polícia Militar do Estado de São Paulo", "estadual"),
    ("CETESB", "Companhia Ambiental do Estado de São Paulo", "estadual"),
    ("PMSP", "Prefeitura Municipal de São Paulo", "municipal"),
    ("CRF-SP", "Conselho Regional de Farmácia de São Paulo", "conselho"),
]

TIPOS = [
    ("Autorização de Funcionamento (AFE)", "ANVISA"),
    ("Autorização Especial (AE)", "ANVISA"),
    ("Licença Sanitária", "VISA-SP"),
    ("Auto de Vistoria do Corpo de Bombeiros (AVCB)", "CBPMESP"),
    ("Licença de Operação", "CETESB"),
    ("Alvará de Funcionamento", "PMSP"),
    ("Certidão de Regularidade Técnica", "CRF-SP"),
]

UNIDADES = [
    ("CD Guarulhos", "11222333000181", "Distribuidora Exemplo Ltda", "Guarulhos", "SP", Porte.GRANDE_I),
    ("CD Cajamar", "11222333000262", "Distribuidora Exemplo Ltda", "Cajamar", "SP", Porte.MEDIO_III),
    ("Escritório São Paulo", "11222333000343", "Distribuidora Exemplo Ltda", "São Paulo", "SP", Porte.EPP),
]

# Valores FICTÍCIOS por tipo de licença (mesma ordem de TIPOS): (valor, periodicidade)
VALORES = [
    (Decimal("4500.00"), Periodicidade.ANUAL),      # AFE
    (Decimal("3200.00"), Periodicidade.ANUAL),      # AE
    (Decimal("850.00"), Periodicidade.ANUAL),       # Licença Sanitária
    (Decimal("1200.00"), Periodicidade.ANUAL),      # AVCB
    (Decimal("1300.00"), Periodicidade.SEMESTRAL),  # Licença de Operação
    (Decimal("95.00"), Periodicidade.MENSAL),       # Alvará (parcelado)
    (Decimal("120.00"), Periodicidade.MENSAL),      # Certidão de Regularidade Técnica
]

# (tipo, unidade, dias até o vencimento) — espalhados para mostrar todos os status
LICENCAS = [
    (0, 0, 420), (1, 0, 25), (2, 0, -12), (3, 0, 75), (4, 0, 200), (6, 0, 55),
    (0, 1, 310), (2, 1, 18), (3, 1, -3), (4, 1, 90), (5, 1, 140),
    (2, 2, 240), (3, 2, 45), (5, 2, 8), (6, 2, 365),
]


class Command(BaseCommand):
    help = "Carrega dados fictícios de demonstração (empresa, unidades, licenças e usuários)."

    @transaction.atomic
    def handle(self, *args, **options):
        hoje = timezone.localdate()
        User = get_user_model()

        usuarios = {}
        for login, nome, sobrenome, grupo in [
            ("admin", "Ana", "Administradora", GRUPO_ADMIN),
            ("analista", "Bruno", "Analista", GRUPO_ANALISTA),
            ("consulta", "Carla", "Gestora", GRUPO_CONSULTA),
        ]:
            u, criado = User.objects.get_or_create(
                username=login,
                defaults={"first_name": nome, "last_name": sobrenome, "email": f"{login}@exemplo.com.br"},
            )
            if criado:
                u.set_password(SENHA_DEMO)
                u.is_staff = u.is_superuser = login == "admin"
                u.save()
            u.groups.add(Group.objects.get(name=grupo))
            usuarios[login] = u

        orgaos = {
            sigla: OrgaoEmissor.objects.get_or_create(sigla=sigla, defaults={"nome": nome, "esfera": esfera})[0]
            for sigla, nome, esfera in ORGAOS
        }
        tipos = [
            TipoLicenca.objects.get_or_create(nome=nome, orgao=orgaos[sigla])[0] for nome, sigla in TIPOS
        ]
        unidades = []
        for nome, cnpj, razao, mun, uf, porte in UNIDADES:
            u, _ = Unidade.objects.get_or_create(
                cnpj=cnpj, defaults={"nome": nome, "razao_social": razao, "municipio": mun, "uf": uf}
            )
            if not u.porte:  # completa bases criadas antes do campo existir
                u.porte = porte
                u.save(update_fields=["porte"])
            unidades.append(u)

        criadas = 0
        for i, (t, u, dias) in enumerate(LICENCAS, start=1):
            validade = hoje + timedelta(days=dias)
            lic, criada = Licenca.objects.get_or_create(
                tipo=tipos[t],
                unidade=unidades[u],
                defaults={
                    "numero": f"DEMO-{i:04d}",
                    "data_emissao": validade - timedelta(days=365),
                    "data_validade": validade,
                    "responsavel": usuarios["analista"] if i % 3 else usuarios["admin"],
                },
            )
            criadas += criada
            if lic.valor is None:  # completa bases criadas antes do controle de custos
                lic.valor, lic.periodicidade = VALORES[t]
                if i == 1:
                    lic.dias_aviso = 120  # exemplo de aviso personalizado
                lic.save(update_fields=["valor", "periodicidade", "dias_aviso"])

        self.stdout.write(self.style.SUCCESS(
            f"Dados de demonstração prontos ({criadas} licenças novas). "
            f"Usuários: admin / analista / consulta, senha {SENHA_DEMO}"
        ))
