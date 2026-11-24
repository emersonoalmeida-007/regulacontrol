"""Gera um vídeo curto (< 1 min) de demonstração do RegulaControl.

Como funciona:
  1. Abre o sistema no Microsoft Edge (via Playwright) e tira um print de cada tela, com legenda.
  2. Gera a narração de cada cena com a voz pt-BR do Windows (Microsoft Maria).
  3. Junta prints e narração em um MP4 com ffmpeg (pacote imageio-ffmpeg).

Pré-requisitos (Windows):
  pip install playwright imageio-ffmpeg
  servidor rodando em http://127.0.0.1:8000 com os dados de `python manage.py carregar_demo`

Uso:
  python video/gerar_video.py
"""
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
USUARIO, SENHA = "analista", "demo12345"  # usuário fictício de carregar_demo
PASTA = Path(__file__).resolve().parent
SAIDA = PASTA / "RegulaControl_demo.mp4"
VOZ = "Microsoft Maria Desktop"
VELOCIDADE = 2  # -10 a 10
PAUSA = 0.5     # segundos de respiro no fim de cada cena
LIMITE = 59.5   # o vídeo precisa ter menos de 1 minuto

# (id, legenda na tela, narração)
CENAS = [
    ("login", "RegulaControl · gestão de licenças regulatórias",
     "Este é o RegulaControl, um sistema web que controla licenças regulatórias, "
     "como a autorização da Anvisa, o alvará e o auto de vistoria dos bombeiros."),
    ("painel", "Painel de conformidade com indicadores e gráficos",
     "No painel de conformidade, a gestão vê quantas licenças estão em dia, "
     "quantas venceram e o que vence nos próximos meses."),
    ("lista", "Status automático e filtros sem recarregar a página",
     "Cada licença recebe um status automático pela data de validade. "
     "Os filtros atualizam a lista sem recarregar a página."),
    ("detalhe", "Ficha da licença e histórico de renovações",
     "A ficha da licença reúne responsável, documento em PDF e histórico de renovações."),
    ("cnpj", "Dados da unidade preenchidos pela BrasilAPI",
     "No cadastro de unidades, o CNPJ é consultado na Brasil API e os dados são preenchidos sozinhos."),
    ("api", "Alertas por e-mail e API REST própria",
     "O sistema também envia alertas diários por e-mail e oferece uma API REST própria."),
    ("fim", "Projeto Integrador em Computação II · UNIVESP",
     "RegulaControl: licenças em dia, operação sem surpresas."),
]

LEGENDA_JS = """(texto) => {
  document.getElementById('legenda-video')?.remove();
  const d = document.createElement('div');
  d.id = 'legenda-video';
  d.textContent = texto;
  Object.assign(d.style, {
    position: 'fixed', left: '50%', bottom: '28px', transform: 'translateX(-50%)', zIndex: 99999,
    background: 'rgba(15,30,51,.94)', color: '#fff', padding: '12px 26px', borderRadius: '12px',
    font: '600 22px "Segoe UI", system-ui, sans-serif', boxShadow: '0 10px 30px rgba(0,0,0,.25)',
    whiteSpace: 'nowrap', borderLeft: '5px solid #5ea2ef'
  });
  document.body.appendChild(d);
}"""


def capturar(tmp: Path) -> None:
    with sync_playwright() as p:
        nav = p.chromium.launch(channel="msedge", headless=True)
        pg = nav.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=1.5, locale="pt-BR")

        def foto(cena_id, legenda):
            pg.evaluate(LEGENDA_JS, legenda)
            pg.wait_for_timeout(300)
            pg.screenshot(path=tmp / f"{cena_id}.png")

        leg = {c[0]: c[1] for c in CENAS}

        pg.goto(f"{BASE}/entrar/")
        foto("login", leg["login"])

        pg.fill("#id_username", USUARIO)
        pg.fill("#id_password", SENHA)
        pg.click("button[type=submit]")
        pg.wait_for_url(f"{BASE}/")
        pg.wait_for_timeout(1500)  # animação dos gráficos
        foto("painel", leg["painel"])

        pg.goto(f"{BASE}/licencas/")
        pg.select_option("#f-status", "vence_30")
        pg.wait_for_function("document.querySelector('.contagem').textContent.startsWith('3 ')", timeout=5000)
        foto("lista", leg["lista"])

        pg.goto(f"{BASE}/licencas/3/")
        foto("detalhe", leg["detalhe"])

        pg.goto(f"{BASE}/unidades/nova/")
        pg.fill("#id_cnpj", "00000000000191")  # CNPJ público (Banco do Brasil), só para demonstrar a consulta
        pg.press("#id_cnpj", "Tab")
        try:
            pg.wait_for_function(
                "document.getElementById('aviso-cnpj').textContent.includes('BrasilAPI')", timeout=12000
            )
        except Exception:
            print("Aviso: a BrasilAPI não respondeu; a cena do CNPJ mostra o formulário sem preencher.")
        pg.wait_for_timeout(300)
        foto("cnpj", leg["cnpj"])

        pg.goto(f"{BASE}/api/resumo/")
        foto("api", leg["api"])

        pg.context.clear_cookies()
        pg.goto(f"{BASE}/entrar/")
        foto("fim", leg["fim"])
        nav.close()


def narrar(texto: str, destino: Path) -> float:
    arquivo_texto = destino.with_suffix(".txt")
    arquivo_texto.write_text(texto, encoding="utf-8")
    ps = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        f"$s.SelectVoice('{VOZ}'); $s.Rate = {VELOCIDADE};"
        f"$s.SetOutputToWaveFile('{destino}');"
        f"$s.Speak((Get-Content -Raw -Encoding UTF8 '{arquivo_texto}')); $s.Dispose()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    with wave.open(str(destino)) as w:
        return w.getnframes() / w.getframerate()


def montar(tmp: Path, duracoes: dict) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    lista = tmp / "lista.txt"
    with lista.open("w", encoding="utf-8") as f:
        for cena_id, _, _ in CENAS:
            dur = duracoes[cena_id] + PAUSA
            quadros = int(dur * 30) + 1
            seg = tmp / f"{cena_id}.mp4"
            filtro = (
                "[0:v]scale=3840:-2,"
                f"zoompan=z='min(zoom+0.0004,1.04)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={quadros}:s=1920x1080:fps=30,"
                "format=yuv420p[v];[1:a]apad,aresample=44100[a]"
            )
            subprocess.run([
                ffmpeg, "-y", "-loglevel", "error", "-i", str(tmp / f"{cena_id}.png"), "-i", str(tmp / f"{cena_id}.wav"),
                "-filter_complex", filtro, "-map", "[v]", "-map", "[a]", "-t", f"{dur:.2f}",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "128k", str(seg),
            ], check=True)
            f.write(f"file '{seg.as_posix()}'\n")
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lista),
                    "-c", "copy", "-movflags", "+faststart", str(SAIDA)], check=True)


def main():
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        duracoes = {cid: narrar(txt, tmp / f"{cid}.wav") for cid, _, txt in CENAS}
        total = sum(duracoes.values()) + PAUSA * len(CENAS)
        print(f"Narração: {total:.1f} s")
        if total > LIMITE:
            sys.exit(f"Narração passou de {LIMITE} s; aumente VELOCIDADE ou encurte o texto.")
        capturar(tmp)
        montar(tmp, duracoes)
        for cid in duracoes:  # guarda os prints, úteis para o relatório
            (tmp / f"{cid}.png").replace(PASTA / f"tela_{cid}.png")
    print(f"Vídeo salvo em {SAIDA} ({total:.1f} s)")


if __name__ == "__main__":
    main()
