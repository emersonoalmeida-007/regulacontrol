"""Consumo da API externa BrasilAPI (https://brasilapi.com.br) para dados de CNPJ."""
import json
import urllib.error
import urllib.request

URL_CNPJ = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"


class CnpjNaoEncontrado(Exception):
    pass


class BrasilApiIndisponivel(Exception):
    pass


def consultar_cnpj(cnpj: str, timeout: float = 8.0) -> dict:
    """Retorna só os campos que o cadastro de unidade usa."""
    req = urllib.request.Request(URL_CNPJ.format(cnpj=cnpj), headers={"User-Agent": "RegulaControl/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (400, 404):
            raise CnpjNaoEncontrado(cnpj) from e
        raise BrasilApiIndisponivel(str(e)) from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise BrasilApiIndisponivel(str(e)) from e

    partes = [dados.get("descricao_tipo_de_logradouro"), dados.get("logradouro")]
    logradouro = " ".join(p for p in partes if p)
    if dados.get("numero"):
        logradouro += f", {dados['numero']}"
    return {
        "razao_social": dados.get("razao_social", ""),
        "nome_fantasia": dados.get("nome_fantasia", ""),
        "logradouro": logradouro,
        "municipio": (dados.get("municipio") or "").title(),
        "uf": dados.get("uf", ""),
    }
