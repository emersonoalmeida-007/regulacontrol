from django.core.management.base import BaseCommand

from licencas.alertas import enviar_alertas


class Command(BaseCommand):
    help = "Envia por e-mail os alertas de vencimento de licenças. Agende para rodar uma vez por dia."

    def add_arguments(self, parser):
        parser.add_argument("--simular", action="store_true", help="Mostra quantos e-mails seriam enviados, sem enviar.")

    def handle(self, *args, simular=False, **options):
        total = enviar_alertas(simular=simular)
        acao = "seriam enviados" if simular else "enviados"
        self.stdout.write(self.style.SUCCESS(f"{total} e-mail(s) de alerta {acao}."))
