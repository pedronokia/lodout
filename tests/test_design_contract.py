"""Contrato de design do site público -- trava os tokens da identidade
OpenCode lendo `style.css` do disco (sem navegador, roda na suíte normal).

A regressão visual (`tests/visual/visual_regression.py`) pega MUDANÇAS
de renderização; este teste pega mudanças de FONTE -- alguém trocar
`--accent`, o corpo de 17px, o raio dos cards etc. e não perceber. Se
um token mudar de propósito, o teste muda junto: é o documento vivo da
identidade visual (valores conferidos com opencode.ai/brand em 2026-11-12).
"""
from __future__ import annotations

import io
import re
from pathlib import Path

STYLE = (
    Path(__file__).resolve().parents[1]
    / "lodout" / "public_site" / "static" / "style.css"
)


def _css() -> str:
    return STYLE.read_text(encoding="utf-8")


def _bloco(css: str, seletor: str) -> str:
    """Texto da PRIMEIRA regra `seletor { ... }` (do abre-chaves ao
    primeiro fecha-chaves). Suficiente para regras simples da folha --
    blocos com @media aninhado não passam por aqui."""
    início = css.find(f"{seletor} {{")
    assert início >= 0, f"regra não encontrada: {seletor}"
    fim = css.find("}", início)
    return css[início:fim]


def _bloco_final(css: str, seletor: str) -> str:
    """A ÚLTIMA regra de um seletor repetido (a que vale no cascade)."""
    início = css.rfind(f"{seletor} {{")
    assert início >= 0, f"regra não encontrada: {seletor}"
    fim = css.find("}", início)
    return css[início:fim]


def _efetivo(css: str, seletor: str) -> "dict[str, str]":
    """O que de fato vale para `seletor` fora de @media: junta, na ordem
    da folha, as declarações de toda regra de nível 0 cuja lista de
    seletores contém `seletor`; a última de cada propriedade vence (como
    no cascade, com a mesma especificidade). Criado em 28/11: vários
    testes liam a PRIMEIRA regra de um seletor (`_bloco`) e passavam com
    uma declaração que uma regra mais abaixo já tinha substituído."""
    limpo = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    alvo = re.sub(r"\s+", " ", seletor.strip())
    valores: "dict[str, str]" = {}
    profundidade, inicio = 0, 0
    for i, ch in enumerate(limpo):
        if ch == "{":
            if profundidade == 0:
                prelude, abertura = limpo[inicio:i], i
            profundidade += 1
        elif ch == "}":
            profundidade -= 1
            if profundidade == 0:
                inicio = i + 1
                if prelude.strip().startswith("@"):
                    continue
                seletores = [re.sub(r"\s+", " ", x.strip())
                             for x in prelude.split(",")]
                if alvo not in seletores:
                    continue
                for decl in limpo[abertura + 1:i].split(";"):
                    if ":" in decl:
                        prop, valor = decl.split(":", 1)
                        valores[prop.strip()] = valor.strip()
        elif ch == ";" and profundidade == 0:
            inicio = i + 1
    assert valores, f"regra não encontrada: {seletor}"
    return valores


def _bloco_apos(css: str, trecho: str) -> str:
    """Primeiro bloco `{ ... }` depois da última ocorrência de `trecho`
    (útil para seletores agrupados por vírgula)."""
    início = css.rindex(trecho)
    abertura = css.index("{", início)
    fim = css.index("}", abertura)
    return css[abertura:fim]


def test_tokens_de_superficie_opencode():
    css = _css()
    # PRETO #080808 (cabeçalho) + #0F1012 no conteúdo (pedido 26/11):
    # folha #1e1e1e, hover #252525, texto #e8e8e8, secundário #b3b3b3
    # (4,5:1 no hover), bordas #4a4a4a.
    assert "--bg: #0F1012" in css
    assert "--bg-elevated: #1e1e1e" in css
    assert "--surface: #1e1e1e" in css
    assert "--surface-strong: #0a0a0a" in css
    assert "--surface-sunken: #131313" in css
    assert "--surface-escura: #0F1012" in css
    assert "--text: #e8e8e8" in css
    assert "--text-muted: #b3b3b3" in css
    assert "--border: #4a4a4a" in css


def test_laranja_da_casa():
    css = _css()
    # Laranja da casa (Claude Code): #f97316 nos botões/pílulas ativas (70%
    # opacidade = rgba(249, 115, 22, 0.7)) e hover #b8480a. Links: eram
    # #d0580c (4.5:1 no branco, do tema claro); no fundo escuro davam
    # 4,0:1 -- agora o próprio #f97316 (5,9:1 em --surface; auditoria de
    # acessibilidade com axe-core, 2026-11-14).
    assert "--accent: #f97316" in css
    assert "--accent-bright: #f97316" in css
    assert "--accent-hover: #b8480a" in css
    assert "background: rgba(184, 72, 10, 0.7);" in css
    # Foco de teclado e item ativo das barras escuras acompanham o laranja.
    assert "--focus: #f97316" in css
    assert "--chrome-foco: #fb923c" in css
    # Anel de foco dos formulários e selo "novo" acompanham o laranja.
    assert "rgba(249, 115, 22, 0.28)" in css
    assert "rgba(249, 115, 22, 0.1)" in css


def test_raios_da_apple():
    css = _css()
    # Pílula de 980px (botões/chips) e cards com raio 18px.
    assert "--radius-pill: 980px" in css
    assert "--radius-md: 18px" in css
    # A grade usa as medidas da Apple: 980px de conteúdo.
    assert "--largura-conteudo: 980px" in css
    # Pelo menos um botão/chip usa a pílula (não um raio menor).
    assert "border-radius: var(--radius-pill);" in css


def test_corpo_tipografico_17px():
    css = _css()
    assert "--fs-base: 1.0625rem" in css  # 17px
    corpo = _bloco(css, "body")
    assert "font-size: var(--fs-base);" in corpo
    # 25/17 ≈ 1.47 (25px de entrelinha em corpo de 17px).
    assert "line-height: 1.47;" in corpo
    # Espaçamento entre letras pelo tamanho de cada elemento, não um
    # valor fixo no body herdado por todo texto
    # menor -- isso espremia os rótulos de 12px (2026-11-15).
    assert "letter-spacing" not in corpo
    assert "letter-spacing: calc((1em - 12px) * -0.04);" in css
    assert "font-weight: 450;" in corpo


def test_fontes_oficiais_autohospedadas():
    """26/11, escolha do usuário: Outfit (títulos), Geist (corpo) e
    Geist Mono (dados). Auto-hospedadas porque o CSP de produção é
    `default-src 'self'` -- um @import do Google Fonts seria bloqueado
    e o visitante cairia no fallback do sistema."""
    css = _css()
    for familia, arquivo, pesos in (
        ("Outfit", "outfit-latin.woff2", "600 800"),
        ("Geist", "geist-latin.woff2", "400 700"),
        ("Geist Mono", "geist-mono-latin.woff2", "500 700"),
    ):
        assert f'font-family: "{familia}";' in css
        assert f'src: url("fonts/{arquivo}?v=1") format("woff2");' in css
        assert f"font-weight: {pesos};" in css
    assert css.count("font-display: swap;") >= 3
    assert "--font-display: 'Outfit', 'Outfit Fallback', sans-serif;" in css
    assert "--font-sans: 'Geist', 'Geist Fallback', sans-serif;" in css
    assert "--font-mono: 'Geist Mono', monospace;" in css
    # Revisão 26/11 (pedido do usuário): números na Geist tabular; a
    # Geist Mono fica só para código.
    assert "--font-num: 'Geist', 'Geist Fallback', sans-serif;" in css


def test_fallback_com_a_medida_das_fontes():
    """28/11: na primeira visita, a troca da Arial pela Geist mudava a
    quebra de linha da página inicial e empurrava o destaque ~30px (CLS
    0,25). Os fallbacks esticam a Arial para ocupar o mesmo espaço."""
    css = _css()
    for familia in ("Geist Fallback", "Outfit Fallback"):
        início = css.index(f'font-family: "{familia}";')
        bloco = css[início:css.index("}", início)]
        assert "src: local(" in bloco
        assert "size-adjust:" in bloco and "ascent-override:" in bloco
        assert "descent-override:" in bloco


def test_sem_import_do_google_fonts():
    """A URL oficial do Google Fonts serve de referência, mas o arquivo
    local é que conta. Nada de @import ou link externo em runtime."""
    css = _css()
    assert "fonts.googleapis.com" not in css
    assert "fonts.gstatic.com" not in css


def test_arquivos_da_fonte_comitados():
    """WOFF2 e licenças SIL OFL 1.1 no repositório -- sem eles o site
    cai no fallback do sistema e volta a divergir entre computadores.
    A Inter segue como fonte antiga; o cartão de compartilhamento usa
    as três fontes atuais do site (teste abaixo)."""
    pasta = STYLE.parent / "fonts"
    for nome in ("outfit-latin.woff2", "geist-latin.woff2",
                 "geist-mono-latin.woff2",
                 "inter-latin-opsz-normal.woff2"):
        fonte = pasta / nome
        assert fonte.is_file() and fonte.stat().st_size > 20_000
        assert fonte.read_bytes()[:4] == b"wOF2"
    for nome in ("OFL-Outfit.txt", "OFL-Geist.txt", "OFL-Geist-Mono.txt",
                 "OFL.txt"):
        licenca = (pasta / nome).read_text(encoding="utf-8")
        assert "SIL OPEN FONT LICENSE" in licenca


def test_cartao_de_compartilhamento_usa_a_identidade_atual():
    """26/11: o og-image sai da marca oficial chanfrada, sem TM, com
    título em Outfit, sobre o fundo do site. Desde 27/11 os números
    usam a Geist, como no site (sem fonte monoespaçada)."""
    from PIL import Image as _Img
    from lodout.public_site import og_cards

    origem = (STYLE.parent.parent / "og_cards.py").read_text(encoding="utf-8")
    for familia in ("outfit-latin.woff2", "geist-latin.woff2"):
        assert familia in origem
    assert "geist-mono" not in origem
    assert og_cards._LOGO.name == "logo-escura-og.png"
    assert og_cards._LOGO.is_file()
    # A marca do cartão vem do mesmo partial do topo/rodapé (sem TM).
    gerador = (Path(__file__).resolve().parents[1] / "scripts"
               / "gerar_assets_marca.py").read_text(encoding="utf-8")
    assert "_logo_svg.html" in gerador and "logo-escura-og.png" in gerador

    img = _Img.open(io.BytesIO(og_cards.cartao_padrao())).convert("RGB")
    assert img.size == (og_cards.LARGURA, og_cards.ALTURA)
    assert img.getpixel((0, 0)) == (22, 22, 22)
    assert all(img.getpixel((x, 4)) == (22, 22, 22)
               for x in range(0, og_cards.LARGURA, 50))
    assert set(og_cards._FONTES) == {"outfit", "geist"}


def test_titulos_outfit_700_e_escala_32_48_64():
    """26/11, escolha do usuário: Outfit 700 nos cabeçalhos, tracking
    -0,025em e entrelinha 1,15 em todos os tamanhos."""
    css = _css()
    titulos = _bloco(css, "h1, h2, h3")
    assert "font-family: var(--font-display);" in titulos
    assert "--font-display: 'Outfit', 'Outfit Fallback', sans-serif;" in css
    assert "font-weight: 700;" in titulos
    assert "letter-spacing: -0.025em;" in titulos
    assert "line-height: 1.15;" in titulos
    assert "--fs-xl: 2rem" in css      # 32px
    assert "--fs-2xl: 3rem" in css     # 48px
    assert "--fs-display: 4rem" in css  # 64px


def test_dados_em_geist_tabular():
    """Revisão 26/11 (pedido do usuário: a Geist Mono nos números tinha
    "cara de IA genérica"): preços, variações, desgastes e notas usam a
    mesma regra, Geist com algarismos tabulares, sem zero cortado."""
    css = _css()
    # O que vale de fato em cada seletor (28/11: antes lia o grupo que
    # começava em `.tabular-num`, classe que nenhuma página usa).
    for seletor in (".cartao-item-preco", ".icone-tendencia",
                    ".item-exterior", ".nota-numero", ".nota-margem"):
        regra = _efetivo(css, seletor)
        assert regra.get("font-family") == "var(--font-num)", seletor
        assert regra.get("font-variant-numeric") == "tabular-nums", seletor
        assert '"tnum" 1' in regra.get("font-feature-settings", ""), seletor


def test_vitrine_tem_regua_vertical_unica():
    """26/11: imagem, nome, motivo, preço e rodapé da vitrine usam o
    mesmo intervalo de 8px. O preço é um bloco só, para a variação não
    partir o valor ao meio em larguras intermediárias."""
    css = _css()
    corpo = _bloco(css, ".grade-cards > .cartao-item .cartao-item-corpo")
    assert "gap: 8px;" in corpo
    rodape = _bloco(css, ".grade-cards > .cartao-item .cartao-item-rodape")
    assert "gap: 8px;" in rodape
    assert "margin-top: auto;" in rodape
    preco = _bloco(css, ".grade-cards > .cartao-item .cartao-item-preco")
    assert "font-family: var(--font-num);" in preco
    assert "flex-wrap: wrap;" in preco
    filhos = _bloco(css, ".grade-cards > .cartao-item .cartao-item-preco > *")
    assert "white-space: nowrap;" in filhos
    # Coluna mínima no celular (11rem) evita quatro cartões estreitos em
    # 640px, onde o preço em mono não cabia ao lado do botão.
    assert "minmax(min(100%, 11rem), 1fr)" in css

    html = (STYLE.parent.parent / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'class="cartao-item-preco-valor"' in html


def test_svgs_dos_icones_sao_a_marca_oficial():
    """26/11: os ícones saem dos mesmos SVG da marca chanfrada usada no
    topo/rodapé -- #1A1D24, contorno branco 45%, Outfit 800 e sem TM.
    Pequeno leva o monograma; grande leva `lodout` em quadrado seguro."""
    static = STYLE.parent
    caminho = static / "favicon.svg"
    svg = caminho.read_text(encoding="utf-8")
    app = (static / "logo-escura-app.svg").read_text(encoding="utf-8")

    silhueta = (
        'd="M84 14H242C247.523 14 252 18.4772 252 24V64.3431'
        'C252 66.9953 250.946 69.5389 249.071 71.4142'
        'L217.414 103.071C215.539 104.946 212.995 106 210.343 106'
        'H18C12.4772 106 8 101.523 8 96V58.6569'
        'C8 56.0047 9.05357 53.4611 10.9289 51.5858'
        'L76.9289 16.9289C78.8043 15.0536 81.3478 14 84 14Z"'
    )
    for fonte in (svg, app):
        assert silhueta in fonte
        assert 'fill="#1A1D24"' in fonte
        assert 'stroke="rgba(255,255,255,0.45)"' in fonte
        assert 'font-family="Outfit, sans-serif"' in fonte
        assert 'font-weight="800"' in fonte
        assert "TM" not in fonte and "™" not in fonte

    assert 'viewBox="0 0 256 256"' in svg and ">l</text>" in svg
    assert 'viewBox="0 0 512 512"' in app and ">lodout</text>" in app
    # Fundo escuro do sistema e margem de segurança no quadrado do app.
    assert '<rect width="512" height="512" fill="#080808"/>' in app
    assert 'scale(1.64) translate(-130 -60)' in app

    gerador = (Path(__file__).resolve().parents[1] / "scripts"
               / "gerar_assets_marca.py").read_text(encoding="utf-8")
    assert "favicon.svg" in gerador and "logo-escura-app.svg" in gerador
    assert "apple-touch-icon.png" in gerador and "favicon.ico" in gerador


def test_rodape_cinza_claro_12px():
    css = _css()
    rodape = _bloco(css, "footer.rodape")
    # Faixa própria em --surface-sunken. Texto em --fs-xs desde o
    # redesenho de 2026-11-14 (12px ficava pequeno demais pro aviso).
    assert "background: var(--surface-sunken);" in rodape
    assert "font-size: var(--fs-xs);" in rodape
    # Marca e aviso à esquerda, links à direita, base embaixo.
    assert '"marca nav"' in rodape and '"base  base"' in rodape


def test_cards_sem_fio_com_elevacao_hover():
    css = _css()
    card = _bloco(css, ".cartao-item")
    # Card-tile: sem fio em repouso; elevação sutil (shadow-lg) + fio
    # laranja 35% no hover/focus. Transição suave, respeita reduced-motion.
    assert "border: 0;" in card
    assert "border-radius: var(--radius-md);" in card
    assert "transition: box-shadow var(--dur-emphasis) var(--ease-standard), border-color var(--dur-emphasis) var(--ease-standard);" in card
    assert "box-shadow: var(--shadow-lg);" in css
    assert "border: 1px solid rgba(249, 115, 22, 0.35);" in css
    # Brilho diagonal animado no hover/focus (reduced-motion o esconde).
    assert ".cartao-item-brilho {" in css
    assert "rgba(249, 115, 22, 0.12)" in css
    # Focus visível no card.
    assert ".cartao-item:focus-visible {" in css
    assert "outline: 2px solid var(--focus);" in css
    # Estado pressed.
    assert ".cartao-item:active {" in css
    assert "transform: scale(0.995);" in css


def test_pagina_branca_com_faixa_borda_a_borda():
    """A página inteira é o branco #ffffff e as seções grandes atravessam
    a tela de borda a borda (truque 100vw), com o conteúdo de volta na
    coluna dentro da faixa."""
    css = _css()
    assert "background: var(--bg);" in css  # body na página branca
    faixa = _bloco(css, ".faixa")
    assert "width: 100vw;" in faixa
    assert "margin-left: calc(50% - 50vw);" in faixa
    # O html corta o excedente do 100vw (barra de rolagem).
    html_bloco = _bloco(css, "html")
    assert "overflow-x: clip;" in html_bloco


def test_ficha_do_item_tile_branca():
    css = _css()
    ficha = _bloco(css, ".resumo-cards-item")
    # Painel de métricas vira tile branca na página cinza, com o selo
    # de Nota em caixinha cinza dentro (inverso do layout antigo).
    assert "background: var(--surface);" in ficha
    selo = _bloco(css, ".resumo-cards-item .card-nota-destaque")
    assert "background: var(--surface-strong);" in selo


def test_polimento_da_maquete_v4():
    """Rodada 2026-11-12: laranja como identidade + polimento aprovado
    na maquete v4 (pílulas, abas, faixa de informação, CTA do item e
    rodapé alinhado)."""
    css = _css()
    # Vitrine/Lista ativo ficou neutro em 2026-11-14 (o laranja fica só
    # na aba de categoria; dois controles laranja lado a lado disputavam).
    # 28/11: as conferências leem o valor que VALE (`_efetivo`, a última
    # regra do seletor), não a primeira -- várias passavam com declarações
    # que uma regra mais abaixo já tinha trocado.
    visao = _efetivo(css, '.seletor-visao a[aria-current="page"]')
    assert visao["background"] == "var(--surface-hover)"
    assert "rgba(249, 115, 22" not in visao["background"]
    # Abas de categoria: fantasma quando inativas (fundo branco quase
    # transparente + fio fino), laranja na ativa. O que vale hoje é
    # branco a 4% com fio a 8% (a regra "transparent" do começo da folha
    # já era substituída mais abaixo).
    aba = _efetivo(css, ".aba-categoria")
    fundo = re.fullmatch(r"rgba\(255, 255, 255, (0?\.\d+)\)", aba["background"])
    assert fundo and float(fundo.group(1)) <= 0.06, aba["background"]
    assert aba["border"].startswith("1px solid ")
    aba_ativa = _efetivo(css, '.aba-categoria[aria-current="page"]')
    assert "rgba(249, 115, 22" in aba_ativa["background"]
    # O laranja de ação virou token (auditoria 17/11), com o mesmo valor.
    assert "--accent-acao: rgba(249, 115, 22, 0.7);" in css
    # Estado da coleta na home: linha leve com bolinha de status (revisão 20/11:
    # polimento compacto com fs-xs).
    linha = _efetivo(css, ".status-coleta")
    assert linha["padding-left"] == "14px" and linha["font-size"] == "var(--fs-xs)"
    assert _efetivo(css, ".status-coleta-ponto")["background"] == "var(--positive)"
    # CTA laranja da página do item, em pílula com texto branco (70% opacidade).
    acao = _efetivo(css, ".botao-acao")
    assert acao["background"] == "var(--accent-acao)"
    assert acao["border-radius"] == "var(--radius-pill)"
    # Linha de coleta fechando a ficha do item (régua de baixo).
    coleta = _efetivo(css, ".resumo-cards-item .card-coleta")
    assert coleta["border-top"] == "1px solid var(--border)"
    # Aviso do rodapé em linha curta (não atravessa a largura toda): a
    # medida de leitura do site é ~75 letras; o que vale hoje é 62ch (o
    # 46ch do começo da folha já era substituído mais abaixo).
    medida = _efetivo(css, ".rodape-marca p")["max-width"]
    assert medida.endswith("ch") and int(medida[:-2]) <= 65, medida


def test_respeita_reduced_motion():
    css = _css()
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_sem_estilo_inline_no_css():
    """O CSP não permite estilos inline (AGENTS.md): a folha não pode
    nem ela mesma normalizar `style=""` em lugar nenhum."""
    css = _css()
    sem_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    assert not re.search(r'\bstyle\s*=\s*"', sem_comentarios)


# ── Contraste calculado (auditoria de acessibilidade, 2026-11-14) ──────
# Em vez de só fixar o hex, CALCULA o contraste WCAG de cada par texto ×
# fundo que o site usa de verdade. Se alguém trocar um token por um tom
# bonito mas ilegível (como os verdes/vermelhos de tema claro que ficaram
# meses no fundo escuro, ~3,2:1), este teste quebra com o par e o valor.

def _tokens(css: str) -> "dict[str, str]":
    raiz = css[css.index(":root {"):]
    raiz = raiz[:raiz.index("\n}")]
    return dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})\b", raiz))


def _luminancia(hexcor: str) -> float:
    c = [int(hexcor[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _contraste(a: str, b: str) -> float:
    la, lb = _luminancia(a), _luminancia(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _mistura(frente: str, fundo: str, alfa: float) -> str:
    f = [int(frente[i:i + 2], 16) for i in (1, 3, 5)]
    g = [int(fundo[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(f[k] * alfa + g[k] * (1 - alfa)):02x}" for k in range(3))


def test_contraste_dos_textos_sobre_os_fundos():
    t = _tokens(_css())
    fundos = ["--bg", "--surface", "--surface-hover"]
    textos = ["--text", "--text-muted", "--text-bright", "--accent-bright",
              "--positive", "--warn", "--danger"]
    ruins = []
    for tx in textos:
        for fd in fundos:
            r = _contraste(t[tx], t[fd])
            if r < 4.5:
                ruins.append(f"{tx} {t[tx]} sobre {fd} {t[fd]}: {r:.2f}:1")
    assert not ruins, "texto abaixo de 4,5:1 -> " + "; ".join(ruins)


def test_contraste_dos_selos_sobre_fundo_tingido():
    # Selos (tendência, Descontinuada, resultado da coleta, pontos do Por
    # quê) pintam o fundo com a própria cor a 6-14%, inclusive na linha
    # da tabela em hover: o texto deles usa os tons -selo.
    t = _tokens(_css())
    for tx, base in (("--positive-selo", "#22a04a"), ("--danger-selo", "#f85149")):
        for fd in ("--surface", "--surface-hover"):
            tingido = _mistura(base, t[fd], 0.14)
            r = _contraste(t[tx], tingido)
            assert r >= 4.5, f"{tx} sobre {fd} tingido ({tingido}): {r:.2f}:1"


def test_contraste_de_texto_branco_nos_fundos_cheios():
    # Botão de perigo e contador de favoritos: branco por cima.
    t = _tokens(_css())
    for fd in ("--danger-fundo",):
        r = _contraste("#ffffff", t[fd])
        assert r >= 4.5, f"branco sobre {fd} {t[fd]}: {r:.2f}:1"


def test_linhas_escondidas_somem_tambem_no_celular():
    """No celular cada linha da conta vira cartão (display: grid), o que
    passava por cima do atributo `hidden`: busca e filtros não escondiam
    nada lá (achado em 2026-11-16). A regra do `hidden` precisa vir
    depois da regra de cartão."""
    css = (Path(__file__).resolve().parents[1] / "lodout" / "public_site" / "static" / "style.css").read_text(encoding="utf-8")
    cartao = css.index("table.tabela-cards-mobile tbody tr:not(.linha-regras) {")
    escondida = css.rindex("table.tabela-conta tbody tr[hidden] { display: none; }")
    assert escondida > cartao


def test_rotulos_de_venda_por_nao_quebram_no_computador():
    """A rodada 11 da revisão (16/11) pôs `white-space: normal` na linha de
    "Venda por" a partir de 641px e "Sem prejuízo"/"Lucrar 20%" passaram a
    quebrar em todas as linhas a 1280px. Texto maior é tratado com um
    corte em em (empilha rótulo e valor), não com a quebra."""
    css = (Path(__file__).resolve().parents[1] / "lodout" / "public_site" / "static" / "style.css").read_text(encoding="utf-8")
    assert ".tabela-conta .venda-por-linha { white-space: normal; }" not in css
    assert "@media (min-width: 641px) and (max-width: 64em)" in css


def test_losango_some_quando_o_item_tem_imagem():
    """28/11: a regra do quadro compacto repunha o placeholder (display:
    flex) e o "◇" aparecia através do fundo transparente das armas na
    Minha conta. Com imagem, ele fica escondido; sem, volta (app.js tira
    a classe -com-imagem quando a imagem falha)."""
    css = _css()
    regra = ".icone-item-quadro-compacto.icone-item-quadro-com-imagem .icone-item-placeholder"
    assert "display: none;" in _bloco_final(css, regra)
    assert css.index(regra) > css.index(".icone-item-quadro-compacto .icone-item-placeholder {")


def test_ajuste_fino_da_conta():
    """Ajuste 26/11: linhas de apoio com respiro lateral, célula do item
    mais baixa no computador e os quatro valores numéricos na mesma régua
    Geist tabular, alinhados à direita."""
    css = _css()
    # Cartões: as linhas abaixo do valor não encostam na borda interna.
    assert "padding-inline: 6px;" in _bloco_final(css, ".resumo-cards-conta .card-sub")
    # Item: nome inteiro, quebrando em linhas (pedido do usuário, 27/11:
    # "o nome não pode ficar cortado"); o title segue com o nome completo.
    link = _bloco_final(css, ".tabela-conta .celula-item-conta-texto > .link-item")
    assert "text-overflow: ellipsis;" not in link
    assert "white-space: normal;" in link
    # Colunas fixas no computador: nome longo não estica a tabela além
    # da borda dos cartões e dos filtros.
    assert "table.tabela-conta { table-layout: fixed; width: 100%; }" in css
    html = (STYLE.parent.parent / "templates" / "conta.html").read_text(encoding="utf-8")
    assert 'title="{{ row.name_fmt }}"' in html
    # Computador: menos vão vertical dentro da célula do item.
    item = _bloco_final(css, '.tabela-conta td[data-label="Item"]')
    assert "padding-top: 6px;" in item and "padding-bottom: 6px;" in item
    texto = _bloco_final(css, ".tabela-conta .celula-item-conta-texto")
    assert "gap: 1px;" in texto
    extra = _bloco_final(css, ".tabela-conta .celula-item-conta-extra")
    assert "margin-top: 1px;" in extra and "line-height: 1.15;" in extra
    # Quatro colunas: custo, valor de hoje, lucro/prejuízo e venda.
    pago = _bloco_final(css, '.tabela-conta td[data-label="Você pagou"]')
    assert "text-align: right;" in pago
    assert "justify-content: flex-end;" in _bloco_final(
        css, '.tabela-conta td[data-label="Você pagou"] .form-custo'
    )
    alinhados = _bloco_apos(
        css,
        ".tabela-conta .celula-numero,\n.tabela-conta .celula-venda-por {",
    )
    assert "text-align: right;" in alinhados
    numeros = _bloco_apos(
        css, '.tabela-conta td[data-label="Você pagou"] .input-custo,'
    )
    assert "font-family: var(--font-num);" in numeros
    assert "font-variant-numeric: tabular-nums;" in numeros
    assert 'font-feature-settings: "tnum" 1;' in numeros
    for seletor in (
        '.tabela-conta td[data-label="Você pagou"] .input-custo',
        ".tabela-conta .celula-numero",
        ".tabela-conta .celula-numero .valor-unidade",
        ".tabela-conta .celula-numero .valor-total",
        ".tabela-conta .celula-numero .lucro-pct",
        '.tabela-conta .celula-venda-por [data-campo="empate"]',
        '.tabela-conta .celula-venda-por [data-campo="alvo"]',
    ):
        assert seletor in css, seletor


def test_superficies_sem_tom_azulado():
    """Fundos ficaram azul-marinho em 19/11 (rgba(18, 24, 38)); o DESIGN.md
    pede cinza neutro. Revisão 20/11: só o botão da Steam pode ser azul."""
    import re as _re
    css = _css()
    assert "rgba(18, 24, 38" not in css
    for cor in ("#0d121c", "#111827"):
        assert cor not in css.lower()


def _secao_consistencia() -> str:
    css = _css()
    return css[css.index("Consistência de interface — 26/11"):]


def test_consistencia_de_interface_26_11():
    """Rodada das 20 melhorias: cards, régua numérica, tabelas, anéis,
    rodapé e estados interativos. A seção fica no fim da folha para valer
    sobre as regras antigas sem mudar regra de negócio."""
    secao = _secao_consistencia()
    # Fundo pedido pelo usuário e a mesma rampa de tokens em toda a folha.
    assert "--bg: #0F1012" in _css()
    assert "--surface-escura: #0F1012" in _css()
    # Cards: altura cheia e respiro lateral (há uma variante só no celular).
    assert "height: 100%;\n  padding-inline: 22px;" in secao
    sub = _bloco_apos(secao, ".resumo-cards-conta .card-sub {")
    assert "padding-inline: 6px;" in sub
    # Montantes e percentuais na mesma régua Geist tabular.
    numeros = _bloco_apos(secao, ".movimento-linha-numeros {")
    assert "font-family: var(--font-num);" in numeros
    assert "font-variant-numeric: tabular-nums;" in numeros
    assert 'font-feature-settings: "tnum" 1;' in numeros
    for seletor in (".card-valor", ".cartao-item-preco", ".frequencia strong",
                    ".encomenda-preco-hoje", ".ranking-pos-num"):
        assert seletor in secao, seletor
    # Ranking: coluna ITEM protegida e nome inteiro, quebrando linha
    # (pedido do usuário, 28/11; antes era ellipsis).
    assert ".tabela-top20 { table-layout: fixed; }" in secao
    for n, pct in enumerate(("4%", "34%", "15%", "13%", "11%", "23%"), 1):
        assert f".tabela-top20 thead th:nth-child({n}) {{ width: {pct}; }}" in secao
    item = _bloco_apos(secao, ".tabela-top20 .celula-item-ranking > .link-item {")
    assert "white-space: normal;" in item and "overflow-wrap: break-word;" in item
    assert "text-overflow: ellipsis;" not in item
    # Anel de nota centrado também no celular.
    anel = _bloco_apos(secao, ".nota,\n.nota-mini {")
    assert "place-items: center;" in anel and "text-align: center;" in anel
    # Foco de teclado reforçado sem anel duplo.
    assert (":focus-visible { outline: 2px solid var(--focus); "
            "outline-offset: 3px; }") in secao
    # Rodapé alinhado, com a marca intacta (teste próprio mais acima).
    assert ".rodape-nav-grupo { gap: 2px; }" in secao
    assert ".rodape-marca p { max-width: 62ch; }" in secao
    # Vitrine: nenhum filho soma margem vertical à régua de 8px.
    vitrine = _bloco_apos(
        secao, ".grade-cards > .cartao-item .cartao-item-corpo > *,"
    )
    assert "margin-block: 0;" in vitrine


def test_conta_compacta_sem_overflow_no_celular():
    """Chips mais discretos, colunas sem quebra e 390–640px sem rolagem
    horizontal: os seletores e valores precisam continuar na seção final."""
    import re as _re
    css = _css()
    secao = _secao_consistencia()
    chip = _bloco_apos(
        secao, ".tabela-conta .celula-item-conta-extra .item-exterior,"
    )
    assert "color: var(--text-muted);" in chip
    assert "font-weight: 400;" in chip
    assert "line-height: 1.2;" in chip
    quebras = _bloco_apos(secao, ".tabela-conta .encomenda-preco-hoje {")
    assert "white-space: nowrap;" in quebras
    assert ".conta-ferramentas .conta-filtro[aria-pressed=\"false\"]:hover" in secao
    movel = secao[secao.rindex("@media (max-width: 640px) {"):]
    assert "min-width: 0; max-width: 100%;" in movel
    assert ".conta-ferramentas .conta-filtro { white-space: nowrap; }" in movel
    azuladas = []
    for m in _re.finditer(r"rgba?\(\s*(\d+),\s*(\d+),\s*(\d+)", css):
        r, g, b = map(int, m.groups())
        if b - r >= 12 and b >= g and max(r, g, b) < 60:
            azuladas.append(m.group(0))
    assert not azuladas, azuladas


def test_um_verde_um_vermelho_um_amarelo_sem_cinza_azulado():
    """Revisão 20/11: o CSS tinha 4 verdes, 3 vermelhos e 2 amarelos além
    dos oficiais (--positive, --danger, --warn), e um cinza-azulado
    (#94a3b8) em textos de apoio. Fica um de cada, como no DESIGN.md."""
    css = _css().lower()
    for cor in ("#10b981", "#22c55e", "#34d399", "#4ade80",
                "#ef4444", "#f87171", "#ff8a80", "#facc15", "#94a3b8",
                "rgba(16, 185, 129", "rgba(239, 68, 68", "rgba(148, 163, 184"):
        assert cor not in css, cor


def test_unico_azul_e_o_botao_da_steam():
    """Opção C (pedido do usuário, 20/11): "Mais negociado", "anunciado",
    barrinha de liquidez, faixa "Subiram" e o link "Steam Market" saíram do
    azul-céu. O único azul que fica é o do botão "Entrar com Steam"."""
    import re as _re
    css = _css().lower()
    for cor in ("#38bdf8", "rgba(56, 189, 248", "#0ea5e9", "#0284c7"):
        assert cor not in css, cor
    usos = [m.start() for m in _re.finditer(r"102, 192, 244|#66c0f4", css)]
    for pos in usos:
        inicio = css.rfind("}", 0, pos)
        seletor = css[inicio + 1:css.find("{", inicio)]
        assert ":root" in seletor or "conta-link-entrar" in seletor, seletor.strip()[-80:]


# Exceções da escala de letras (27/11, combinadas com o usuário): número
# dentro de moldura fixa (anéis de nota, contadores redondos), teclas
# (kbd), barra de baixo do celular, ícones desenhados com texto, campo
# de valor (o iOS dá zoom em campo abaixo de 16px) e o preço da vitrine
# (16px, pedido do usuário). Tudo o mais usa um degrau --fs-*.
_EXCECOES_ESCALA = {
    ".hero-destaque-nota-num": "1.5rem",
    ".nota-mini.nota-tres-digitos .nota-numero": "0.6875rem",
    ".cartao-item-nota-numero": "0.6875rem",
    "table.tabela-conta .celula-item-conta-cabeca > .nota-mini .nota-numero": "0.65rem",
    ".resumo-cards.resumo-cards-item .card-valor.nota .nota-numero": "1.5rem !important",
    ".spotlight-fechar kbd": "0.6875rem",
    ".spotlight-atalho kbd": "0.6875rem",
    ".spotlight-gatilho-kbd": "0.625rem",
    ".nav-inferior a": "0.6875rem",
    ".badge-contagem-filtros": "0.6875rem",
    ".botao-filtro-topo .badge-contagem-filtros": "0.625rem",
    ".icone-item-placeholder::before": "1.6rem",
    # Duas regras (desktop e celular) com tamanhos próprios do ícone.
    ".icone-item-quadro-compacto .icone-item-placeholder::before": None,
    ".adicionar-manual > summary::before": "0.85rem",
    ".cartao-item-rodape .botao-favorito": "16px",
    ".form-filtros button.filtros-fechar-popover": "1rem !important",
    ".simulador-input": "1rem",
    ".grade-cards > .cartao-item .cartao-item-preco .cartao-item-preco-valor": "1rem",
}


def test_tamanhos_de_letra_seguem_a_escala():
    """27/11: o CSS tinha ~230 tamanhos soltos (11, 11,2, 11,5, 12,5,
    15px...) e textos parecidos saíam diferentes de uma página para
    outra. Toda declaração de font-size usa um degrau da escala
    (--fs-*), um valor relativo (em, inherit, clamp() nos títulos
    fluidos) ou é uma exceção registrada acima. Nenhum degrau fica
    abaixo de 12px."""
    import re as _re
    css = _re.sub(r"/\*.*?\*/", "", _css(), flags=_re.S)
    soltos = []
    for regra in _re.finditer(r"([^{}]*)\{([^{}]*)\}", css):
        seletor = " ".join(regra.group(1).split())
        for valor in _re.findall(r"font-size:\s*([^;]+);", regra.group(2)):
            valor = valor.strip()
            if (valor.startswith("var(--fs-") or valor.startswith("inherit")
                    or valor.startswith("clamp(") or _re.fullmatch(r"[0-9.]+em", valor)):
                continue
            esperado = _EXCECOES_ESCALA.get(seletor, "")
            if esperado is None or valor == esperado:
                continue
            soltos.append(f"{seletor} {{ font-size: {valor} }}")
    assert not soltos, "Tamanho fora da escala (use var(--fs-*)):\n" + "\n".join(soltos)
    # Degraus da escala: o menor é 12px (0,75rem).
    degraus = dict(_re.findall(r"--(fs-[a-z0-9]+):\s*([0-9.]+)rem;", _css()))
    assert degraus["fs-2xs"] == "0.75"
    assert min(float(v) for v in degraus.values()) >= 0.75
    assert degraus["fs-titulo"] == "1.5"


def test_minify_css_mantem_as_regras():
    """27/11: o build compacta o style.css (scripts/minify_static.py)
    também nas quebras de linha e espaços. A cópia compactada precisa
    ter as mesmas regras e declarações, e o texto entre aspas
    (content, url, nomes de fonte) passa intacto."""
    import importlib.util
    import re as _re
    caminho = Path(__file__).resolve().parents[1] / "scripts" / "minify_static.py"
    spec = importlib.util.spec_from_file_location("minify_static", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    original = _css()
    mini = mod.minify_css(original)
    assert len(mini) < len(original) * 0.8

    strings = _re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')

    def regras(css: str):
        css = _re.sub(r"/\*.*?\*/", "", css, flags=_re.S)
        assert strings.findall(css) == strings.findall(mini)
        fora = strings.sub('""', css)
        blocos = []
        for m in _re.finditer(r"([^{}]*)\{([^{}]*)\}", fora):
            seletor = " ".join(m.group(1).split())
            seletor = _re.sub(r"\s*([,>])\s*", r"\1", seletor)
            decls = tuple(_re.sub(r"\s*([,>])\s*", r"\1", " ".join(d.split()))
                          for d in m.group(2).split(";") if d.strip())
            blocos.append((seletor, decls))
        return blocos

    assert regras(original) == regras(mini)
    assert original.count("{") == mini.count("{")


def test_alto_contraste_marca_o_escolhido():
    """Auditoria 28/11: no alto contraste do Windows o fundo some, e a aba,
    o período e Vitrine/Lista escolhidos ficavam iguais aos outros."""
    css = _css()
    inicio = css.index("@media (forced-colors: active)")
    bloco = css[inicio:css.index("\n}", inicio)]
    for seletor in ('main a[aria-current="page"]', 'main a[aria-current="true"]',
                    'main [aria-pressed="true"]'):
        assert seletor in bloco
    assert "border: 2px solid Highlight;" in bloco
    assert ".botao-acao { border: 1px solid ButtonText; }" in bloco
