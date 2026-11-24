from .permissoes import pode_editar


def perfil(request):
    """Disponibiliza `pode_editar` em todos os templates, para esconder botões do perfil Consulta."""
    return {"pode_editar": pode_editar(request.user)}
