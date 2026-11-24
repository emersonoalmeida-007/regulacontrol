"""Perfis de acesso (RF01): Administrador, Analista e Consulta, via grupos do Django."""
from django.contrib.auth.mixins import UserPassesTestMixin

GRUPO_ADMIN = "Administrador"
GRUPO_ANALISTA = "Analista"
GRUPO_CONSULTA = "Consulta"
GRUPOS = [GRUPO_ADMIN, GRUPO_ANALISTA, GRUPO_CONSULTA]


def pode_editar(user) -> bool:
    """Administradores e analistas cadastram e renovam; Consulta só visualiza."""
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name__in=[GRUPO_ADMIN, GRUPO_ANALISTA]).exists()


class PodeEditarMixin(UserPassesTestMixin):
    def test_func(self):
        return pode_editar(self.request.user)
