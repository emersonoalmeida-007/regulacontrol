"""Opções dos filtros de múltipla escolha (caixas de seleção) usados nas telas."""
from .models import OrgaoEmissor, Periodicidade, Porte, Status, TipoLicenca, Unidade


def _unidades():
    return "unidade", "Unidades", [(str(u.pk), u.nome) for u in Unidade.objects.all()]


def _tipos():
    return "tipo", "Licenças", [(str(t.pk), str(t)) for t in TipoLicenca.objects.select_related("orgao")]


def _orgaos():
    return "orgao", "Órgãos", [(str(o.pk), o.sigla) for o in OrgaoEmissor.objects.all()]


def montar(params, grupos) -> list[dict]:
    """Cada grupo vira {nome, titulo, qtd_marcados, opcoes:[{valor, rotulo, marcado}]}."""
    filtros = []
    for nome, titulo, opcoes in grupos:
        marcados = set(params.getlist(nome))
        filtros.append({
            "nome": nome,
            "titulo": titulo,
            "qtd_marcados": len(marcados & {v for v, _ in opcoes}),
            "opcoes": [{"valor": v, "rotulo": r, "marcado": v in marcados} for v, r in opcoes],
        })
    return filtros


def ativos(filtros) -> list[tuple[str, str]]:
    """Pares (filtro, opção) marcados, para mostrar como etiquetas."""
    return [(f["titulo"], op["rotulo"]) for f in filtros for op in f["opcoes"] if op["marcado"]]


def filtros_licencas(params):
    return montar(params, [
        ("status", "Status", list(Status.choices)),
        _unidades(),
        _tipos(),
        _orgaos(),
    ])


def filtros_analises(params):
    return montar(params, [
        _unidades(),
        _tipos(),
        _orgaos(),
        ("porte", "Porte", list(Porte.choices)),
    ])


def filtros_custos(params):
    return montar(params, [
        _unidades(),
        _tipos(),
        _orgaos(),
        ("porte", "Porte", list(Porte.choices)),
        ("periodicidade", "Periodicidade", list(Periodicidade.choices)),
    ])
