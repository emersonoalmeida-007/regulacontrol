"""Cálculos da tela Análises: cenário por unidade, evolução histórica e previsão.

Histórico de cada licença (reconstrução):
- As renovações guardam a validade anterior e a nova. Antes da 1ª renovação registrada,
  a licença valia até `validade_anterior` dessa renovação; depois de cada renovação
  (pela data em que foi registrada), passa a valer até `nova_validade`.
- Início da licença: um ano antes da 1ª validade conhecida (ou a data de emissão, se não houver
  renovações). Antes disso, ela não entra nas contas.
- Meses com RegistroMensal gravado pela rotina diária usam o registro (mais exato), quando
  não há filtro por licença ou órgão (o registro é por unidade).
"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Prefetch
from django.utils import timezone

from . import consultas, custos
from .models import Licenca, RegistroMensal, Renovacao, Status, Unidade, calcular_status

MESES_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

# Ordem de gravidade, para escolher o "pior" status quando há mais de uma licença na célula.
GRAVIDADE = {Status.VENCIDA: 4, Status.VENCE_30: 3, Status.VENCE_60: 2, Status.VENCE_90: 1, Status.VIGENTE: 0}


def _rotulo_mes(d: date) -> str:
    return f"{MESES_PT[d.month - 1]}/{d.year % 100:02d}"


def _fim_do_mes(ano: int, mes: int) -> date:
    proximo = date(ano + (mes == 12), mes % 12 + 1, 1)
    return proximo - timedelta(days=1)


def pontos_mensais(meses: int, hoje: date) -> list[date]:
    """Último dia de cada um dos meses anteriores e, por fim, hoje."""
    pontos = []
    ano, mes = hoje.year, hoje.month
    for _ in range(meses - 1):
        mes -= 1
        if mes == 0:
            ano, mes = ano - 1, 12
        pontos.append(_fim_do_mes(ano, mes))
    return sorted(pontos) + [hoje]


def licencas(params=None):
    """Licenças ativas com filtros de múltipla escolha e renovações já carregadas."""
    qs = custos.filtrar(consultas.licencas_ativas(), params)
    return qs.prefetch_related(Prefetch("renovacoes", queryset=Renovacao.objects.order_by("registrado_em")))


# ---------- Reconstrução histórica ----------

def inicio_conhecido(lic: Licenca) -> date:
    renovacoes = list(lic.renovacoes.all())
    if renovacoes:
        return renovacoes[0].validade_anterior - timedelta(days=365)
    return lic.data_emissao


def validade_em(lic: Licenca, dia: date) -> date | None:
    """Até quando a licença valia no dia informado (None = ainda não existia)."""
    if dia < inicio_conhecido(lic):
        return None
    renovacoes = list(lic.renovacoes.all())
    if not renovacoes:
        return lic.data_validade
    validade = renovacoes[0].validade_anterior
    for r in renovacoes:
        if timezone.localtime(r.registrado_em).date() <= dia:
            validade = r.nova_validade
    return validade


def status_em(lic: Licenca, dia: date) -> str | None:
    validade = validade_em(lic, dia)
    return None if validade is None else calcular_status(validade, dia)


# ---------- A. Cenário por unidade ----------

def cenario_por_unidade(lista: list, hoje: date) -> list[dict]:
    """Gráficos 1 (conformidade) e 2 (placar)."""
    grupos = defaultdict(list)
    for lic in lista:
        grupos[lic.unidade].append(lic)
    linhas = []
    for unidade in sorted(grupos, key=lambda u: u.nome):
        itens = grupos[unidade]
        contagem = defaultdict(int)
        for lic in itens:
            contagem[calcular_status(lic.data_validade, hoje)] += 1
        total = len(itens)
        em_dia = total - contagem[Status.VENCIDA]
        futuras = sorted((lic for lic in itens if lic.data_validade >= hoje), key=lambda lic: lic.data_validade)
        linhas.append({
            "unidade": unidade,
            "total": total,
            "vigente": contagem[Status.VIGENTE],
            "vence_90": contagem[Status.VENCE_60] + contagem[Status.VENCE_90],
            "vence_30": contagem[Status.VENCE_30],
            "vencida": contagem[Status.VENCIDA],
            "pct_em_dia": round(100 * em_dia / total, 1) if total else 100.0,
            "proxima": futuras[0] if futuras else None,
            "custo_anual": sum((lic.custo_anual for lic in itens if lic.custo_anual is not None), Decimal("0")),
        })
    return linhas


def mapa_unidade_tipo(lista: list, hoje: date) -> dict:
    """Gráfico 3: grade unidade × tipo de licença com o pior status de cada célula."""
    unidades = sorted({lic.unidade for lic in lista}, key=lambda u: u.nome)
    tipos = sorted({lic.tipo for lic in lista}, key=lambda t: t.nome)
    celulas = {}
    for lic in lista:
        chave = (lic.unidade_id, lic.tipo_id)
        status = calcular_status(lic.data_validade, hoje)
        atual = celulas.get(chave)
        if atual is None or GRAVIDADE[status] > GRAVIDADE[atual["status"]]:
            celulas[chave] = {"status": status, "rotulo": Status(status).label, "licenca": lic}
    linhas = [
        {"unidade": u, "celulas": [celulas.get((u.pk, t.pk)) for t in tipos]}
        for u in unidades
    ]
    faltas = sum(1 for linha in linhas for c in linha["celulas"] if c is None)
    return {"tipos": tipos, "linhas": linhas, "faltas": faltas}


# ---------- B. Evolução e histórico ----------

def evolucao_conformidade(lista: list, meses: int, hoje: date, usar_registros: bool) -> dict:
    """Gráfico 4: % médio de licenças em dia em cada mês (dia a dia), geral e por unidade.

    A média diária capta licenças que ficaram vencidas no meio do mês, mesmo que renovadas
    antes do fim dele. O mês atual vai até hoje. Meses passados com RegistroMensal usam o
    registro (situação no último dia em que a rotina rodou naquele mês).
    """
    pontos = pontos_mensais(meses, hoje)
    unidades = sorted({lic.unidade for lic in lista}, key=lambda u: u.nome)
    registros = {}
    if usar_registros:
        for r in RegistroMensal.objects.filter(mes__gte=pontos[0].replace(day=1)):
            registros[(r.mes, r.unidade_id)] = r

    # contagem[ponto][unidade] = [licença-dias existentes, licença-dias em dia]
    contagem = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    ultimo = len(pontos) - 1
    for i, fim in enumerate(pontos):
        mes = fim.replace(day=1)
        dias = [mes + timedelta(days=n) for n in range((fim - mes).days + 1)]
        for u in unidades:
            reg = registros.get((mes, u.pk)) if i < ultimo else None
            if reg:
                contagem[i][u.pk] = [reg.total, reg.em_dia]
        for lic in lista:
            if i < ultimo and registros.get((mes, lic.unidade_id)):
                continue
            c = contagem[i][lic.unidade_id]
            for dia in dias:
                validade = validade_em(lic, dia)
                if validade is None:
                    continue
                c[0] += 1
                c[1] += validade >= dia

    def pct(total, em_dia):
        return round(100 * em_dia / total, 1) if total else None

    geral = []
    for i in range(len(pontos)):
        total = sum(c[0] for c in contagem[i].values())
        em_dia = sum(c[1] for c in contagem[i].values())
        geral.append(pct(total, em_dia))
    series = [
        {"nome": u.nome, "valores": [pct(*contagem[i][u.pk]) for i in range(len(pontos))]}
        for u in unidades
    ]
    rotulos = [_rotulo_mes(d) for d in pontos]
    tabela = [
        {"mes": rotulos[i], "geral": geral[i], "unidades": [s["valores"][i] for s in series]}
        for i in range(len(pontos))
    ]
    return {"meses": rotulos, "geral": geral, "unidades": series, "tabela": tabela}


def renovacoes_por_mes(lista: list, meses: int, hoje: date) -> list[dict]:
    """Gráfico 5: renovações registradas por mês, no prazo × em atraso."""
    pontos = pontos_mensais(meses, hoje)
    chaves = [(d.year, d.month) for d in pontos]
    no_prazo, atraso = defaultdict(int), defaultdict(int)
    for lic in lista:
        for r in lic.renovacoes.all():
            dia = timezone.localtime(r.registrado_em).date()
            chave = (dia.year, dia.month)
            if chave not in chaves:
                continue
            if dia <= r.validade_anterior:
                no_prazo[chave] += 1
            else:
                atraso[chave] += 1
    return [
        {"mes": _rotulo_mes(date(a, m, 1)), "no_prazo": no_prazo[(a, m)], "atraso": atraso[(a, m)]}
        for a, m in chaves
    ]


def linha_do_tempo(lista: list, hoje: date, meses_antes: int = 6, meses_depois: int = 12) -> dict:
    """Gráfico 6: barras de vigência (emissão → validade) por licença, agrupadas por unidade."""
    inicio = date(hoje.year - (hoje.month <= meses_antes), (hoje.month - meses_antes - 1) % 12 + 1, 1)
    fim_ano, fim_mes = hoje.year + (hoje.month + meses_depois - 1) // 12, (hoje.month + meses_depois - 1) % 12 + 1
    fim = _fim_do_mes(fim_ano, fim_mes)
    total_dias = (fim - inicio).days

    def pos(d: date) -> float:
        return round(100 * (min(max(d, inicio), fim) - inicio).days / total_dias, 2)

    marcas, ano, mes = [], inicio.year, inicio.month
    while date(ano, mes, 1) <= fim:
        d = date(ano, mes, 1)
        marcas.append({"rotulo": _rotulo_mes(d), "pos": pos(d)})
        ano, mes = ano + (mes == 12), mes % 12 + 1
    passo = 2 if len(marcas) > 12 else 1  # evita rótulos sobrepostos
    for n, m in enumerate(marcas):
        m["mostrar"] = n % passo == 0

    grupos = defaultdict(list)
    for lic in sorted(lista, key=lambda lic: (lic.unidade.nome, lic.data_validade)):
        esquerda, direita = pos(lic.data_emissao), pos(lic.data_validade)
        grupos[lic.unidade].append({
            "licenca": lic,
            "status": calcular_status(lic.data_validade, hoje),
            "esquerda": esquerda,
            "largura": max(direita - esquerda, 0.6),
            "corta_inicio": lic.data_emissao < inicio,
            "corta_fim": lic.data_validade > fim,
        })
    return {
        "inicio": inicio, "fim": fim, "hoje": pos(hoje), "marcas": marcas,
        "grupos": [{"unidade": u, "barras": grupos[u]} for u in sorted(grupos, key=lambda u: u.nome)],
    }


# ---------- C. Previsão ----------

def vencimentos_por_unidade(lista: list, hoje: date, meses: int = 12) -> dict:
    """Gráfico 7: quantas licenças vencem em cada um dos próximos meses, por unidade."""
    chaves, ano, mes = [], hoje.year, hoje.month
    for _ in range(meses):
        chaves.append((ano, mes))
        ano, mes = ano + (mes == 12), mes % 12 + 1
    unidades = sorted({lic.unidade for lic in lista}, key=lambda u: u.nome)
    contagem = defaultdict(int)
    for lic in lista:
        if lic.data_validade >= hoje.replace(day=1):
            contagem[(lic.unidade_id, lic.data_validade.year, lic.data_validade.month)] += 1
    return {
        "meses": [_rotulo_mes(date(a, m, 1)) for a, m in chaves],
        "series": [{"nome": u.nome, "valores": [contagem[(u.pk, a, m)] for a, m in chaves]} for u in unidades],
    }


def antecedencia_por_unidade(lista: list) -> list[dict]:
    """Gráfico 8: média de dias entre o registro da renovação e o vencimento anterior.

    Positivo = renovou antes de vencer; negativo = renovou depois de vencer.
    """
    dias = defaultdict(list)
    for lic in lista:
        for r in lic.renovacoes.all():
            dias[lic.unidade].append((r.validade_anterior - timezone.localtime(r.registrado_em).date()).days)
    linhas = []
    for u in sorted(dias, key=lambda u: u.nome):
        valores = dias[u]
        linhas.append({
            "unidade": u.nome,
            "media": round(sum(valores) / len(valores), 1),
            "renovacoes": len(valores),
            "em_atraso": sum(1 for v in valores if v < 0),
        })
    return linhas


# ---------- Registro mensal ----------

def registrar_mes(hoje: date | None = None) -> int:
    """Grava (ou atualiza) a foto do mês atual de cada unidade. Chamado pela rotina diária."""
    hoje = hoje or timezone.localdate()
    mes = hoje.replace(day=1)
    contagem = defaultdict(lambda: [0, 0])
    for lic in consultas.licencas_ativas():
        c = contagem[lic.unidade_id]
        c[0] += 1
        c[1] += lic.data_validade < hoje
    for unidade in Unidade.objects.all():
        total, vencidas = contagem[unidade.pk]
        RegistroMensal.objects.update_or_create(
            mes=mes, unidade=unidade,
            defaults={"total": total, "vencidas": vencidas, "em_dia": total - vencidas},
        )
    return Unidade.objects.count()


def montar(params=None, meses: int = 12, hoje: date | None = None) -> dict:
    """Tudo o que a tela Análises precisa, com os mesmos filtros."""
    hoje = hoje or timezone.localdate()
    lista = list(licencas(params))
    filtra_licenca = bool(params) and any(params.getlist(n) for n in ("tipo", "orgao", "porte", "periodicidade"))
    return {
        "hoje": hoje,
        "cenario": cenario_por_unidade(lista, hoje),
        "mapa": mapa_unidade_tipo(lista, hoje),
        "evolucao": evolucao_conformidade(lista, meses, hoje, usar_registros=not filtra_licenca),
        "renovacoes": renovacoes_por_mes(lista, meses, hoje),
        "linha_tempo": linha_do_tempo(lista, hoje),
        "vencimentos": vencimentos_por_unidade(lista, hoje),
        "antecedencia": antecedencia_por_unidade(lista),
    }
