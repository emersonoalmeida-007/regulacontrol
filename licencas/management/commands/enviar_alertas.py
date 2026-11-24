from django.core.management.base import BaseCommand

from licencas.alertas import enviar_alertas
from licencas.analises import registrar_mes


class Command(BaseCommand):
    help = (
        "Rotina diária: envia por e-mail os alertas de vencimento e grava a foto do mês "
        "de cada unidade (histórico da tela Análises)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--simular", action="store_true", help="Mostra quantos e-mails seriam enviados, sem enviar.")

    def handle(self, *args, simular=False, **options):
        total = enviar_alertas(simular=simular)
        acao = "seriam enviados" if simular else "enviados"
        self.stdout.write(self.style.SUCCESS(f"{total} e-mail(s) de alerta {acao}."))
        if not simular:
            unidades = registrar_mes()
            self.stdout.write(self.style.SUCCESS(f"Histórico do mês atualizado para {unidades} unidade(s)."))
