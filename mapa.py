"""
Sistema de Mapa Galactico - mapa.py
Grade A-I / 1-8 | Imagem 2000x1333px
Canal fixo: #mapa-galactico

INSTALACAO:
  pip install Pillow aiohttp

INTEGRACAO no bot.py (ja feita):
  from mapa import setup_mapa
  setup_mapa(bot, dados, salvar)  <- no on_ready
"""

import discord
from discord import app_commands
from discord.ext import commands
import json
import io
import os
import math
from datetime import datetime

# Pasta onde mapa.py está — garante que mapa_fundo.png seja sempre encontrado
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
MAPA_FUNDO    = os.path.join(BASE_DIR, "mapa_fundo.png")

try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_OK = True
except ImportError:
    PILLOW_OK = False

try:
    import aiohttp
    AIOHTTP_OK = True
except ImportError:
    AIOHTTP_OK = False

ARQUIVO_MAPA   = "mapa_config.json"
NOME_CANAL     = "mapa-galactico"

# Dimensoes e grade — A–Q / 1–18
MAPA_W     = 3400
MAPA_H     = 2400
GRADE_COLS = 17   # A até Q
GRADE_ROWS = 18   # 1 até 18
CELL_W     = MAPA_W / GRADE_COLS
CELL_H     = MAPA_H / GRADE_ROWS
COLUNAS    = [chr(ord('A') + i) for i in range(GRADE_COLS)]  # A-Q

ROXO       = 0x6B21A8
VERDE      = 0x3B0764
ALERT      = 0x7C3AED
PERIGO     = 0x7F1D1D
RODAPE_ADM = "Conselho dos Administradores"
SEP        = "░▒▓█  Cartografia Galactica  █▓▒░"

# Distância mínima entre centros para não sobrepor (em pixels)
DISTANCIA_MINIMA = 130


# ==============================
# GRADE
# ==============================
def grade_para_xy(celula):
    celula = celula.strip().upper()
    if len(celula) < 2:
        return None
    col = celula[0]
    try:
        row = int(celula[1:])
    except ValueError:
        return None
    if col not in COLUNAS or row < 1 or row > GRADE_ROWS:
        return None
    ci = COLUNAS.index(col)
    return (int(CELL_W * ci + CELL_W / 2), int(CELL_H * (row - 1) + CELL_H / 2))

def xy_para_grade(x, y):
    ci = min(int(x / CELL_W), GRADE_COLS - 1)
    ri = min(int(y / CELL_H), GRADE_ROWS - 1)
    return f"{COLUNAS[ci]}{ri + 1}"


# ==============================
# VERIFICAÇÃO DE COLISÃO
# ==============================
def verificar_colisao(cfg, x, y, raio, nome_ignorar=None):
    """
    Verifica se um novo território em (x, y) com dado raio
    ficaria muito próximo de algum território já existente.
    Retorna lista de dicts com os territórios próximos.
    """
    proximos = []
    for nome, info in cfg.get("territorios", {}).items():
        if nome == nome_ignorar:
            continue
        dx = info["x"] - x
        dy = info["y"] - y
        dist = math.sqrt(dx * dx + dy * dy)
        raio_outro = info.get("raio", 63)
        soma_raios = raio + raio_outro + 20
        if dist < soma_raios:
            proximos.append({
                "nome":      nome,
                "distancia": int(dist),
                "celula":    info.get("celula", xy_para_grade(info["x"], info["y"])),
                "sobrepos":  dist < (raio + raio_outro),
            })
    proximos.sort(key=lambda p: p["distancia"])
    return proximos


# ==============================
# CÉLULA ALEATÓRIA LIVRE
# ==============================
def encontrar_celula_aleatoria_livre(cfg, raio=30, seed=None):
    """
    Escolhe aleatoriamente uma célula livre na grade inteira.
    Evita as bordas (margem de 1 célula) para não ficar no canto.
    Retorna (x, y, celula) ou None se o mapa estiver completamente lotado.
    """
    import random as _rnd
    rng = _rnd.Random(seed)

    # Grade interior (evita bordas)
    cols_internas = COLUNAS[1:-1]   # B até P
    rows_internas = list(range(2, GRADE_ROWS))  # 2 até 17

    todas = [(c, r) for c in cols_internas for r in rows_internas]
    rng.shuffle(todas)

    for (col, row) in todas:
        celula = f"{col}{row}"
        resultado = encontrar_posicao_livre(cfg, celula, raio)
        if resultado is not None:
            return resultado  # (x, y, celula_real)

    return None


def mapear_capital_automatico(cfg, nome_capital, cor_hex="6B21A8", raio=30):
    """
    Chamado pelo main.py ao criar um novo império.
    Encontra célula livre, registra no mapa e salva.
    Retorna a célula onde foi colocado, ou None se falhou.
    """
    import random as _rnd
    seed = sum(ord(c) for c in nome_capital)  # seed baseada no nome = reproduzível
    resultado = encontrar_celula_aleatoria_livre(cfg, raio=raio, seed=seed)
    if resultado is None:
        return None
    x, y, celula = resultado
    cfg["territorios"][nome_capital] = {
        "x":      x,
        "y":      y,
        "raio":   raio,
        "celula": celula,
    }
    salvar_mapa(cfg)
    return celula


# ==============================
# POSIÇÃO AUTOMÁTICA NA CÉLULA
# ==============================
def encontrar_posicao_livre(cfg, celula, raio, nome_ignorar=None):
    """
    Tenta encontrar uma posição livre dentro da célula (ou células vizinhas
    se necessário) para um novo território com o raio dado.

    Estratégia: testa uma grade de candidatos dentro da célula,
    do centro para as bordas, e retorna o primeiro ponto sem colisão.

    Retorna (x, y, celula_usada) ou None se não encontrar espaço.
    """
    celula = celula.strip().upper()
    col = celula[0]
    row = int(celula[1:])
    ci  = COLUNAS.index(col)
    ri  = row - 1

    # Limites da célula (com margem interna para o círculo não sair)
    margem  = raio + 8
    x_min   = int(CELL_W * ci)       + margem
    x_max   = int(CELL_W * (ci + 1)) - margem
    y_min   = int(CELL_H * ri)       + margem
    y_max   = int(CELL_H * (ri + 1)) - margem

    if x_min >= x_max or y_min >= y_max:
        # Célula muito pequena para o raio — usa o centro mesmo
        cx = int(CELL_W * ci + CELL_W / 2)
        cy = int(CELL_H * ri + CELL_H / 2)
        return (cx, cy, celula)

    # Gera candidatos em espiral a partir do centro
    cx = int(CELL_W * ci + CELL_W / 2)
    cy = int(CELL_H * ri + CELL_H / 2)

    passo = max(raio * 2 + 15, 30)
    candidatos = []

    # Centro primeiro
    candidatos.append((cx, cy))

    # Anéis ao redor do centro
    for anel in range(1, 8):
        d = anel * passo
        for dx in range(-anel, anel + 1):
            for dy in range(-anel, anel + 1):
                if abs(dx) == anel or abs(dy) == anel:
                    px = cx + dx * (passo // anel if anel > 0 else passo)
                    py = cy + dy * (passo // anel if anel > 0 else passo)
                    # Mantém dentro dos limites da célula
                    px = max(x_min, min(x_max, cx + dx * passo // max(anel, 1)))
                    py = max(y_min, min(y_max, cy + dy * passo // max(anel, 1)))
                    candidatos.append((px, py))

    # Testa cada candidato
    vistos = set()
    for (px, py) in candidatos:
        key = (px, py)
        if key in vistos:
            continue
        vistos.add(key)
        # Confere se está dentro da célula
        if not (x_min <= px <= x_max and y_min <= py <= y_max):
            continue
        colisoes = verificar_colisao(cfg, px, py, raio, nome_ignorar)
        if not any(c["sobrepos"] for c in colisoes):
            cel_real = xy_para_grade(px, py)
            return (px, py, cel_real)

    return None


# ==============================
# ARQUIVOS
# ==============================
def carregar_mapa():
    if not os.path.exists(ARQUIVO_MAPA):
        return {"fundo_url": "", "territorios": {}, "msg_id": None, "canal_id": None}
    with open(ARQUIVO_MAPA, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {"fundo_url": "", "territorios": {}, "msg_id": None, "canal_id": None}

def salvar_mapa(cfg):
    with open(ARQUIVO_MAPA, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)


# ==============================
# AUXILIARES
# ==============================
def hex_to_rgb(h):
    h = h.lstrip("#")
    if len(h) != 6:
        return (108, 33, 168)
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def tem_permissao_adm(interaction):
    cargos = [c.name.lower() for c in interaction.user.roles]
    return "adm" in cargos or "administrador" in cargos or interaction.user.guild_permissions.administrator

async def baixar_fundo(url):
    if not AIOHTTP_OK:
        return False
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                if r.status == 200:
                    data = await r.read()
                    img  = Image.open(io.BytesIO(data)).convert("RGBA")
                    img  = img.resize((MAPA_W, MAPA_H), Image.LANCZOS)
                    img.save(MAPA_FUNDO)
                    return True
    except Exception:
        pass
    return False


# ==============================
# GERAR IMAGEM
# ==============================
def gerar_imagem_mapa(cfg, dados_imperios):
    if not PILLOW_OK:
        return None

    territorios = cfg.get("territorios", {})

    if os.path.exists(MAPA_FUNDO):
        base = Image.open(MAPA_FUNDO).convert("RGBA")
        base = base.resize((MAPA_W, MAPA_H), Image.LANCZOS)
    else:
        import random
        base = Image.new("RGBA", (MAPA_W, MAPA_H), (8, 4, 20, 255))
        d = ImageDraw.Draw(base)
        random.seed(42)
        for _ in range(600):
            sx, sy = random.randint(0, MAPA_W), random.randint(0, MAPA_H)
            sb = random.randint(100, 255)
            d.ellipse([sx-1, sy-1, sx+1, sy+1], fill=(sb, sb, sb, 150))

    overlay = Image.new("RGBA", (MAPA_W, MAPA_H), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)

    try:
        fn = ImageFont.truetype("arial.ttf", 20)
        fi = ImageFont.truetype("arial.ttf", 14)
        fg = ImageFont.truetype("arial.ttf", 17)
        fl = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        fn = fi = fg = fl = ImageFont.load_default()

    p2i = {}
    for id_u, imp in dados_imperios.items():
        for p in imp.get("planetas", []):
            p2i[p.lower()] = imp
        for s in imp.get("sistemas", []):
            p2i[s.lower()] = imp

    # Grade sutil
    for ci in range(GRADE_COLS + 1):
        draw.line([(int(CELL_W*ci), 0), (int(CELL_W*ci), MAPA_H)], fill=(255,255,255,15), width=1)
    for ri in range(GRADE_ROWS + 1):
        draw.line([(0, int(CELL_H*ri)), (MAPA_W, int(CELL_H*ri))], fill=(255,255,255,15), width=1)

    # Rótulos grade
    for ci, letra in enumerate(COLUNAS):
        gx = int(CELL_W * ci + CELL_W / 2)
        draw.text((gx, 10), letra, fill=(255,255,255,100), font=fg, anchor="mt")
    for ri in range(GRADE_ROWS):
        gy = int(CELL_H * ri + CELL_H / 2)
        draw.text((12, gy), str(ri+1), fill=(255,255,255,100), font=fg, anchor="lm")

    raio_pad = int(min(CELL_W, CELL_H) * 0.38)

    for nome, info in territorios.items():
        x, y  = info["x"], info["y"]
        raio  = info.get("raio", raio_pad)
        imp   = p2i.get(nome.lower())

        if imp:
            r, g, b  = hex_to_rgb(imp.get("cor", "6B21A8"))
            cfill    = (r,g,b,55)
            cborda   = (r,g,b,210)
            ctxt     = (r,g,b,255)
            nome_imp = imp["nome"]
        else:
            cfill, cborda, ctxt = (55,55,85,40), (130,120,160,160), (175,170,205,255)
            nome_imp = "Neutro"

        draw.ellipse([x-raio,y-raio,x+raio,y+raio], fill=cfill, outline=cborda, width=3)
        h = raio + 12
        draw.ellipse([x-h,y-h,x+h,y+h], fill=None, outline=(*cborda[:3],35), width=2)
        draw.ellipse([x-5,y-5,x+5,y+5], fill=(255,255,255,200))
        draw.ellipse([x-3,y-3,x+3,y+3], fill=cborda)
        draw.text((x, y-raio-7), nome, fill=(255,255,255,235), font=fn, anchor="mb")
        if raio >= 40 and imp:
            draw.text((x, y+7), nome_imp[:15], fill=ctxt, font=fi, anchor="mt")
        ref = info.get("celula", xy_para_grade(x, y))
        draw.text((x, y+raio+5), f"[{ref}]", fill=(190,185,215,120), font=fi, anchor="mt")

    # Legenda
    n_imp = len(dados_imperios)
    lw, lh = 290, n_imp*28+40
    lx = MAPA_W - lw - 10
    ly = MAPA_H - lh - 10
    draw.rectangle([lx-8,ly-8,lx+lw,ly+lh], fill=(5,3,18,200), outline=(90,70,150,180), width=1)
    draw.text((lx+lw//2, ly+2), "IMPERIOS", fill=(200,180,255,255), font=fg, anchor="mt")
    cy = ly + 28
    for id_u, imp in sorted(dados_imperios.items(), key=lambda x: x[1]["nome"]):
        r,g,b = hex_to_rgb(imp.get("cor","6B21A8"))
        nt    = len(imp.get("planetas",[]))+len(imp.get("sistemas",[]))
        draw.rectangle([lx,cy,lx+15,cy+15], fill=(r,g,b))
        draw.text((lx+22,cy+7), f"{imp['nome'][:22]}  [{nt}]", fill=(220,210,245,255), font=fl, anchor="lm")
        cy += 28

    final = Image.alpha_composite(base, overlay).convert("RGB")
    buf   = io.BytesIO()
    final.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ==============================
# EMBED DO CANAL FIXO
# ==============================
def montar_embed_mapa(cfg, dados_imperios):
    territorios  = cfg.get("territorios", {})
    dados_imperios = dados_imperios or {}

    p2i = {}
    for id_u, imp in dados_imperios.items():
        for p in imp.get("planetas", []):
            p2i[p.lower()] = imp
        for s in imp.get("sistemas", []):
            p2i[s.lower()] = imp

    embed = discord.Embed(
        title="🗺️  Mapa Galáctico  —  Estado Atual",
        description=f"{SEP}\n*Controle territorial dos impérios da galáxia.*",
        color=ROXO
    )

    imp_setores = {}
    neutros     = []
    for nome_t, info in sorted(territorios.items()):
        cel = info.get("celula", xy_para_grade(info["x"], info["y"]))
        imp = p2i.get(nome_t.lower())
        if imp:
            chave = imp["nome"]
            imp_setores.setdefault(chave, {"imp": imp, "setores": []})
            imp_setores[chave]["setores"].append(f"`{cel}` {nome_t}")
        else:
            neutros.append(f"`{cel}` {nome_t}")

    for nome_imp, dados in sorted(imp_setores.items()):
        imp  = dados["imp"]
        setores = dados["setores"]
        total   = len(setores)
        valor   = "\n".join(setores[:8])
        if total > 8:
            valor += f"\n*... e mais {total-8}*"
        embed.add_field(
            name=f"🏛️ {nome_imp}  [{total} setor(es)]",
            value=valor or "—",
            inline=True
        )

    if neutros:
        embed.add_field(
            name=f"⬜ Território Neutro  [{len(neutros)}]",
            value="\n".join(neutros[:6]) + (f"\n*... e mais {len(neutros)-6}*" if len(neutros) > 6 else ""),
            inline=True
        )

    embed.add_field(name="\u200b", value=SEP, inline=False)
    embed.add_field(name="🌐 Territórios",  value=f"`{len(territorios)}`",         inline=True)
    embed.add_field(name="🏛️ Impérios",     value=f"`{len(dados_imperios)}`",      inline=True)
    embed.add_field(name="🗺️ Grade",         value="`A–I  ×  1–8`",               inline=True)

    agora = datetime.now().strftime("%d/%m/%Y às %H:%M")
    embed.set_footer(text=f"⬡ Cartografia Galáctica  ·  Atualizado em {agora}")
    embed.set_image(url="attachment://mapa.png")
    return embed


# ==============================
# ATUALIZAR CANAL FIXO
# ==============================
async def atualizar_canal_mapa(bot, cfg, dados_imperios):
    if not PILLOW_OK:
        return

    canal = discord.utils.get(bot.get_all_channels(), name=NOME_CANAL)
    if not canal:
        return

    buf = gerar_imagem_mapa(cfg, dados_imperios)
    if not buf:
        return

    embed = montar_embed_mapa(cfg, dados_imperios)
    buf.seek(0)
    file2 = discord.File(io.BytesIO(buf.read()), filename="mapa.png")

    msg_id = cfg.get("msg_id")
    if msg_id:
        try:
            msg = await canal.fetch_message(int(msg_id))
            await msg.delete()
        except Exception:
            pass

    try:
        nova_msg = await canal.send(file=file2, embed=embed)
        cfg["msg_id"]   = nova_msg.id
        cfg["canal_id"] = canal.id
        salvar_mapa(cfg)
    except Exception:
        pass


# ==============================
# SETUP
# ==============================
def setup_mapa(bot, dados_ref, salvar_fn):
    cfg = carregar_mapa()

    # ── !mapa ────────────────────────────────────────────────────────
    @bot.command(name="mapa")
    async def cmd_mapa(ctx):
        if not PILLOW_OK:
            return await ctx.send("Pillow nao instalado!\nRode: pip install Pillow aiohttp")
        await ctx.typing()
        await atualizar_canal_mapa(bot, cfg, dados_ref.get("imperios", {}))
        if ctx.channel.name != NOME_CANAL:
            buf = gerar_imagem_mapa(cfg, dados_ref.get("imperios", {}))
            if buf:
                embed = montar_embed_mapa(cfg, dados_ref.get("imperios", {}))
                await ctx.send(file=discord.File(buf, filename="mapa.png"), embed=embed)
            else:
                await ctx.send("Nenhum territorio mapeado. Use /mapear_territorio.")

    @bot.listen("on_message")
    async def mapa_on_message(message):
        if message.author.bot:
            return
        if message.channel.name != NOME_CANAL:
            return
        try:
            await message.delete()
        except Exception:
            pass
        await atualizar_canal_mapa(bot, cfg, dados_ref.get("imperios", {}))

    # ── /definir_fundo ───────────────────────────────────────────────
    @bot.tree.command(name="definir_fundo", description="[ADM] Define a imagem de fundo do mapa")
    @app_commands.describe(url="URL da imagem PNG/JPG")
    async def slash_definir_fundo(interaction, url: str):
        if not tem_permissao_adm(interaction):
            return await interaction.response.send_message("Sem permissao.", ephemeral=True)
        if not url.startswith("http"):
            return await interaction.response.send_message("URL invalida.", ephemeral=True)
        await interaction.response.defer()
        ok = await baixar_fundo(url)
        cfg["fundo_url"] = url
        salvar_mapa(cfg)
        if ok:
            embed = discord.Embed(title="Fundo Definido", description="Imagem baixada com sucesso!", color=VERDE)
            embed.set_image(url=url)
        else:
            embed = discord.Embed(title="URL Registrada", description="Nao foi possivel baixar agora. Tente !mapa.", color=ALERT)
        embed.set_footer(text=RODAPE_ADM)
        await interaction.followup.send(embed=embed)
        await atualizar_canal_mapa(bot, cfg, dados_ref.get("imperios", {}))

    # ── /mapear_territorio (COM POSIÇÃO AUTOMÁTICA) ───────────────────
    @bot.tree.command(name="mapear_territorio", description="[ADM] Posiciona um territorio no mapa (ex: B3) — ajuste automático se houver colisão")
    @app_commands.describe(
        nome   = "Nome exato do planeta/sistema",
        celula = "Célula da grade (ex: B3, D5, F2)",
        raio   = "Raio em pixels — pequeno: 20-35 | normal: 63 | grande: 100+"
    )
    async def slash_mapear(interaction, nome: str, celula: str, raio: int = 30):
        if not tem_permissao_adm(interaction):
            return await interaction.response.send_message("Sem permissao.", ephemeral=True)

        celula = celula.strip().upper()
        xy = grade_para_xy(celula)
        if not xy:
            return await interaction.response.send_message(
                f"Célula **{celula}** inválida.\nColunas: A–I | Linhas: 1–8 | Ex: B3, D5", ephemeral=True)
        if raio < 10 or raio > 200:
            return await interaction.response.send_message("Raio deve ser entre 10 e 200.", ephemeral=True)

        cx, cy = xy

        # Verifica se o centro da célula está livre
        colisoes_centro = verificar_colisao(cfg, cx, cy, raio, nome_ignorar=nome)
        sobrepostos_centro = [c for c in colisoes_centro if c["sobrepos"]]

        if not sobrepostos_centro:
            # Centro livre — posiciona normalmente
            x_final, y_final, cel_final = cx, cy, celula
            ajustado = False
        else:
            # Centro ocupado — busca posição livre automaticamente
            resultado = encontrar_posicao_livre(cfg, celula, raio, nome_ignorar=nome)

            if resultado is None:
                # Não encontrou espaço — avisa o ADM
                nomes_bloq = ", ".join(f"**{c['nome']}**" for c in sobrepostos_centro)
                embed = discord.Embed(
                    title="❌  Célula Lotada",
                    description=(
                        f"Não encontrei espaço livre em `{celula}` para **{nome}** (raio {raio}px).\n\n"
                        f"Territórios bloqueando: {nomes_bloq}\n\n"
                        f"💡 **Tente:**\n"
                        f"• Um raio menor: `raio:20`\n"
                        f"• Uma célula adjacente: `{celula[0]}{int(celula[1:])+1}` ou similar\n"
                        f"• `/mapear_territorio_forcar` para ignorar colisões"
                    ),
                    color=PERIGO
                )
                embed.set_footer(text=RODAPE_ADM)
                return await interaction.response.send_message(embed=embed, ephemeral=True)

            x_final, y_final, cel_final = resultado
            ajustado = (x_final != cx or y_final != cy)

        # Salva na posição encontrada
        cfg["territorios"][nome] = {
            "x":      x_final,
            "y":      y_final,
            "raio":   raio,
            "celula": cel_final,
        }
        salvar_mapa(cfg)

        # Verifica vizinhos próximos (não sobrepostos) para aviso
        vizinhos = [c for c in verificar_colisao(cfg, x_final, y_final, raio, nome_ignorar=nome) if not c["sobrepos"]]

        if ajustado:
            desc = (
                f"**{nome}** não cabia no centro de `{celula}` — "
                f"posicionado automaticamente em `{cel_final}` (raio {raio}px)."
            )
            cor = 0x78350F
            titulo = "📍  Território Mapeado  —  posição ajustada"
        else:
            desc = f"**{nome}** mapeado em `{cel_final}` (raio {raio}px)."
            cor = VERDE
            titulo = "✅  Território Mapeado"

        embed = discord.Embed(title=titulo, description=desc, color=cor)
        embed.add_field(name="📍 Posição final", value=f"`{cel_final}`",   inline=True)
        embed.add_field(name="🔵 Raio",          value=f"{raio}px",        inline=True)
        if ajustado:
            embed.add_field(name="🔀 Célula pedida", value=f"`{celula}`", inline=True)
        if vizinhos:
            viz_txt = "\n".join(f"• **{v['nome']}** `[{v['celula']}]` — {v['distancia']}px" for v in vizinhos[:4])
            embed.add_field(name="📡 Vizinhos próximos", value=viz_txt, inline=False)
        embed.set_footer(text=RODAPE_ADM)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await atualizar_canal_mapa(bot, cfg, dados_ref.get("imperios", {}))

    # ── /mapear_territorio_forcar ─────────────────────────────────────
    @bot.tree.command(name="mapear_territorio_forcar", description="[ADM] Força o mapeamento mesmo com sobreposição")
    @app_commands.describe(
        nome   = "Nome exato do planeta/sistema",
        celula = "Célula da grade (ex: B3)",
        raio   = "Raio em pixels (20-200)"
    )
    async def slash_mapear_forcar(interaction, nome: str, celula: str, raio: int = 63):
        if not tem_permissao_adm(interaction):
            return await interaction.response.send_message("Sem permissao.", ephemeral=True)
        xy = grade_para_xy(celula)
        if not xy:
            return await interaction.response.send_message(f"Célula **{celula}** inválida.", ephemeral=True)
        if raio < 20 or raio > 200:
            return await interaction.response.send_message("Raio deve ser entre 20 e 200.", ephemeral=True)
        x, y = xy
        cfg["territorios"][nome] = {"x": x, "y": y, "raio": raio, "celula": celula.upper()}
        salvar_mapa(cfg)
        embed = discord.Embed(
            title="⚠️  Território Mapeado (forçado)",
            description=f"**{nome}** mapeado em `{celula.upper()}` com raio {raio}px.\n*Sobreposição ignorada a pedido do ADM.*",
            color=ALERT
        )
        embed.set_footer(text=RODAPE_ADM)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await atualizar_canal_mapa(bot, cfg, dados_ref.get("imperios", {}))

    # ── /verificar_colisoes ───────────────────────────────────────────
    @bot.tree.command(name="verificar_colisoes", description="[ADM] Lista todos os territórios que se sobrepõem no mapa")
    async def slash_verificar_colisoes(interaction):
        if not tem_permissao_adm(interaction):
            return await interaction.response.send_message("Sem permissao.", ephemeral=True)
        territorios = cfg.get("territorios", {})
        if not territorios:
            return await interaction.response.send_message("Nenhum território mapeado.", ephemeral=True)

        problemas = []
        nomes = list(territorios.keys())
        for i, n1 in enumerate(nomes):
            for n2 in nomes[i+1:]:
                i1, i2 = territorios[n1], territorios[n2]
                dx = i1["x"] - i2["x"]
                dy = i1["y"] - i2["y"]
                dist = math.sqrt(dx*dx + dy*dy)
                soma = i1.get("raio", 63) + i2.get("raio", 63)
                if dist < soma:
                    problemas.append(
                        f"⚠️ **{n1}** `[{i1.get('celula','?')}]`  ×  **{n2}** `[{i2.get('celula','?')}]`  —  dist: {int(dist)}px"
                    )

        if not problemas:
            embed = discord.Embed(
                title="✅  Nenhuma Sobreposição",
                description="Todos os territórios estão bem espaçados no mapa.",
                color=VERDE
            )
        else:
            embed = discord.Embed(
                title=f"⚠️  {len(problemas)} Sobreposição(ões) Encontrada(s)",
                description="\n".join(problemas),
                color=0x7F1D1D
            )
            embed.set_footer(text="Use /mapear_territorio com raio menor ou célula diferente para corrigir")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /remover_territorio_mapa ─────────────────────────────────────
    @bot.tree.command(name="remover_territorio_mapa", description="[ADM] Remove um territorio do mapa")
    @app_commands.describe(nome="Nome do territorio")
    async def slash_remover_mapa(interaction, nome: str):
        if not tem_permissao_adm(interaction):
            return await interaction.response.send_message("Sem permissao.", ephemeral=True)
        if nome not in cfg["territorios"]:
            lista = "\n".join(f"- {t} [{cfg['territorios'][t].get('celula','?')}]"
                              for t in cfg["territorios"]) or "Nenhum."
            return await interaction.response.send_message(f"{nome} nao encontrado.\n{lista}", ephemeral=True)
        del cfg["territorios"][nome]
        salvar_mapa(cfg)
        embed = discord.Embed(title="Territorio Removido", description=f"**{nome}** apagado do mapa.", color=PERIGO)
        embed.set_footer(text=RODAPE_ADM)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await atualizar_canal_mapa(bot, cfg, dados_ref.get("imperios", {}))

    # ── /listar_mapa ─────────────────────────────────────────────────
    @bot.tree.command(name="listar_mapa", description="[ADM] Lista todos os territorios mapeados")
    async def slash_listar_mapa(interaction):
        if not tem_permissao_adm(interaction):
            return await interaction.response.send_message("Sem permissao.", ephemeral=True)
        t = cfg.get("territorios", {})
        if not t:
            return await interaction.response.send_message("Nenhum territorio mapeado.", ephemeral=True)
        por_col = {}
        for nome, info in sorted(t.items()):
            cel = info.get("celula", xy_para_grade(info["x"], info["y"]))
            raio = info.get("raio", 63)
            por_col.setdefault(cel[0], []).append(f"`{cel}` {nome} *(r:{raio})*")
        embed = discord.Embed(title="Territorios Mapeados", description=f"Total: {len(t)}", color=ROXO)
        for col in sorted(por_col):
            embed.add_field(name=f"Coluna {col}", value="\n".join(por_col[col]), inline=True)
        embed.set_footer(text=RODAPE_ADM)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /mapa_grade ──────────────────────────────────────────────────
    @bot.tree.command(name="mapa_grade", description="Mostra a referencia da grade do mapa (A1-Q18)")
    async def slash_mapa_grade(interaction):
        # Grade grande — divide em blocos para não passar o limite do Discord
        header = "　　" + "  ".join(f"**{c}**" for c in COLUNAS)
        linhas = []
        for ri in range(GRADE_ROWS):
            linha = f"**{ri+1:02}** " + "  ".join(f"`{COLUNAS[ci]}{ri+1}`" for ci in range(GRADE_COLS))
            linhas.append(linha)
        # Divide em 3 embeds se necessário
        desc = header + "\n" + "\n".join(linhas)
        embed = discord.Embed(
            title="Grade Galáctica — A–Q × 1–18",
            description=desc[:4000],
            color=ROXO
        )
        embed.add_field(name="Células",  value=f"{GRADE_COLS * GRADE_ROWS} total ({GRADE_COLS}×{GRADE_ROWS})", inline=True)
        embed.add_field(name="Tamanho",  value=f"{int(CELL_W)}×{int(CELL_H)} px/célula",                       inline=True)
        embed.add_field(name="Mapa",     value=f"{MAPA_W}×{MAPA_H} px",                                        inline=True)
        embed.set_footer(text="Use /mapear_territorio celula:D5 raio:25 para territórios pequenos")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /resetar_mapa ────────────────────────────────────────────────
    @bot.tree.command(name="resetar_mapa", description="[ADM] Apaga todos os territorios do mapa (irreversivel!)")
    @app_commands.describe(confirmar="Digite CONFIRMAR para resetar")
    async def slash_resetar_mapa(interaction, confirmar: str):
        if not tem_permissao_adm(interaction):
            return await interaction.response.send_message("Sem permissao.", ephemeral=True)
        if confirmar != "CONFIRMAR":
            return await interaction.response.send_message(
                "❌ Para resetar, digite exatamente `CONFIRMAR` no campo confirmar.", ephemeral=True)
        total = len(cfg.get("territorios", {}))
        cfg["territorios"] = {}
        cfg["msg_id"]      = None
        salvar_mapa(cfg)
        embed = discord.Embed(
            title="🗑️  Mapa Resetado",
            description=f"Todos os **{total}** territórios foram apagados.",
            color=PERIGO
        )
        embed.set_footer(text=RODAPE_ADM)
        await interaction.response.send_message(embed=embed)

    return cfg, atualizar_canal_mapa