// Preenche os dados da unidade pelo CNPJ, usando a BrasilAPI (RF02).
(function () {
  const form = document.querySelector("form[data-url-cnpj]");
  if (!form) return;
  const campo = document.getElementById("id_cnpj");
  const aviso = document.getElementById("aviso-cnpj");
  const urlModelo = form.dataset.urlCnpj;

  function mascara(numeros) {
    return numeros
      .replace(/^(\d{2})(\d)/, "$1.$2")
      .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
      .replace(/\.(\d{3})(\d)/, ".$1/$2")
      .replace(/(\d{4})(\d)/, "$1-$2");
  }

  function preencher(id, valor) {
    const el = document.getElementById(id);
    if (el && valor && !el.value) el.value = valor; // não sobrescreve o que a pessoa já digitou
  }

  campo.addEventListener("input", () => {
    const numeros = campo.value.replace(/\D/g, "").slice(0, 14);
    campo.value = mascara(numeros);
  });

  campo.addEventListener("blur", async () => {
    const numeros = campo.value.replace(/\D/g, "");
    if (numeros.length !== 14) return;
    aviso.textContent = "Buscando dados do CNPJ…";
    try {
      const resp = await fetch(urlModelo.replace("00000000000000", numeros));
      const dados = await resp.json();
      if (!resp.ok) {
        aviso.textContent = dados.erro || "Não foi possível consultar o CNPJ.";
        return;
      }
      preencher("id_razao_social", dados.razao_social);
      preencher("id_nome", dados.nome_fantasia || dados.razao_social);
      preencher("id_logradouro", dados.logradouro);
      preencher("id_municipio", dados.municipio);
      preencher("id_uf", dados.uf);
      aviso.textContent = "Dados preenchidos pela BrasilAPI. Confira antes de salvar.";
    } catch {
      aviso.textContent = "Sem conexão com a BrasilAPI. Preencha os dados manualmente.";
    }
  });
})();
