import discord
from discord.ext import commands
import asyncio
import json  # Importa a biblioteca para manipulação de JSON
import random  # Importa a biblioteca para rolar dados
import os

# --- Gerenciamento de Configuração ---

CONFIG_FILE = 'config.json'

# Dicionário que guardará as configs de todos os servidores na memória
configs = {}


def load_configs():
    """Carrega as configurações do arquivo JSON para a memória."""
    global configs
    try:
        with open(CONFIG_FILE, 'r') as f:
            configs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Se o arquivo não existe ou está vazio/corrompido, começa com um dicionário vazio.
        configs = {}


def save_configs():
    """Salva as configurações da memória de volta para o arquivo JSON."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(configs, f, indent=4)


def get_server_config(guild_id: int):
    """Busca a configuração de um servidor específico ou cria uma padrão."""
    guild_id_str = str(guild_id)  # JSON usa strings como chaves
    if guild_id_str not in configs:
        # Se o servidor é novo para o bot, cria uma config padrão
        configs[guild_id_str] = {
            "canal_introducao": "introducao",
            "cargo_jogador": "Jogador",
            "categoria_privados": "Sessões Individuais"
        }
        save_configs()  # Salva a nova configuração padrão
    return configs[guild_id_str]


# --- Configuração do Bot ---
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    """Função chamada quando o bot está pronto e conectado."""
    load_configs()  # Carrega as configurações ao iniciar
    print(f'O Mago "{bot.user.name}" esta online e pronto para a aventura!')
    print(f'Configuracoes carregadas para {len(configs)} servidor(es).')
    print('------')


@bot.event
async def on_member_join(member: discord.Member):
    """Função acionada toda vez que um novo membro entra no servidor."""
    guild = member.guild
    # Busca a configuração específica para ESTE servidor
    server_config = get_server_config(guild.id)

    print(f'Novo membro entrou: {member.name} no servidor {guild.name}')
    channel = discord.utils.get(guild.text_channels,
                                name=server_config["canal_introducao"])
    if not channel:
        print(
            f"ERRO: Canal '{server_config['canal_introducao']}' não encontrado no servidor {guild.name}."
        )
        return

    # ... (o resto do código do embed é igual) ...
    embed = discord.Embed(
        title=f"Bem-vindo(a) à aventura, {member.name}!",
        description=
        f"Eu sou O Mago, o guardião deste servidor de RPG. Para começarmos, por favor, responda a esta mensagem enviando **apenas o nome do seu personagem**.\n\n*Você tem 5 minutos para responder.*",
        color=discord.Color.purple())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="A sua jornada está prestes a começar...")
    await channel.send(embed=embed)

    def check(message):
        return message.author == member and message.channel == channel

    try:
        response_message = await bot.wait_for('message',
                                              timeout=300.0,
                                              check=check)
        player_name = response_message.content
        await response_message.delete()
    except asyncio.TimeoutError:
        await channel.send(
            f"{member.mention}, parece que você se perdeu na floresta... \n Você demorou demais para responder. Entre em contato com o Mestre"
        )
        return

    # Usa a config do servidor para encontrar o cargo
    role = discord.utils.get(guild.roles, name=server_config["cargo_jogador"])
    if role:
        await member.add_roles(role)
    else:
        print(
            f"ERRO: O cargo '{server_config['cargo_jogador']}' não foi encontrado."
        )
        return

    # Usa a config do servidor para encontrar a categoria
    category = discord.utils.get(guild.categories,
                                 name=server_config["categoria_privados"])
    if not category:
        category = await guild.create_category(
            server_config["categoria_privados"])

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        member: discord.PermissionOverwrite(read_messages=True,
                                            send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True)
    }
    private_channel = await guild.create_text_channel(
        name=f'diario-{player_name.lower().replace(" ", "-")}',
        overwrites=overwrites,
        category=category,
        topic=f"Diário de Bordo de {player_name}.")

    await channel.send(
        f"Perfeito, {member.mention}! Seu cargo foi concedido e o canal {private_channel.mention} foi criado. Boa sorte!"
    )
    await private_channel.send(
        f"Olá, {player_name}! Este é o seu canal privado.")


# --- Comandos Utilitários ---
@bot.command(name='ping', help="Verifica a latência do bot.")
async def ping(ctx):
    latency_ms = round(bot.latency * 1000)
    await ctx.send(
        f"🏓 Pong! A minha velocidade de resposta é de `{latency_ms}ms`.")


@bot.command(name='roll', help="Rola dados. Ex: !roll 2d6 + 1d10 + 5")
async def roll(ctx, *, formula: str):
    """
    Rola dados de acordo com uma fórmula no formato XdY + Z.
    Ex: !roll 3d6 + 1d4 + 5
    """
    try:
        # Limpa a fórmula de espaços e a divide pelas somas
        parts = formula.lower().replace(' ', '').split('+')
        total = 0
        details = []

        for part in parts:
            if 'd' in part:
                # É uma rolagem de dados (ex: "2d6")
                num_dice_str, num_sides_str = part.split('d')

                # Permite a sintaxe "d6" (que significa 1d6)
                num_dice = int(num_dice_str) if num_dice_str else 1
                num_sides = int(num_sides_str)

                # Limites para evitar abuso
                if not (0 < num_dice <= 100 and 0 < num_sides <= 1000):
                    await ctx.send(
                        "Valores de dados inválidos. Use entre 1-100 dados e 1-1000 lados."
                    )
                    return

                rolls = [random.randint(1, num_sides) for _ in range(num_dice)]
                part_sum = sum(rolls)
                total += part_sum
                details.append(f"`{part}`: {rolls} (Soma: {part_sum})")

            else:
                # É um modificador constante (ex: "5")
                modifier = int(part)
                total += modifier
                details.append(f"Modificador: `+{modifier}`")

        # Cria uma resposta bonita usando Embed
        embed = discord.Embed(title="🎲 Rolagem de Dados",
                              description=f"**Fórmula:** `{formula}`",
                              color=discord.Color.dark_red())
        embed.add_field(name="Detalhes",
                        value="\n".join(details),
                        inline=False)
        embed.add_field(name="Resultado Final",
                        value=f"**{total}**",
                        inline=False)
        embed.set_footer(text=f"Rolado por {ctx.author.display_name}")

        await ctx.send(embed=embed)

    except ValueError:
        await ctx.send(
            f"Não entendi a fórmula `{formula}`. Por favor, use o formato `!roll XdY + Z`."
        )
    except Exception as e:
        await ctx.send(f"Ocorreu um erro arcano ao tentar ler sua magia: {e}")


# --- Comandos de Configuração (Modificados) ---


@bot.command(name='setcanalintro')
@commands.has_permissions(administrator=True)
async def set_canal_intro(ctx, *, nome_canal: str):
    """Define o nome do canal de introdução PARA ESTE SERVIDOR."""
    server_config = get_server_config(ctx.guild.id)
    server_config["canal_introducao"] = nome_canal
    save_configs()  # Salva a alteração no arquivo JSON
    await ctx.send(
        f"✅ O canal de introdução deste servidor foi definido para `{nome_canal}`."
    )


@bot.command(name='setcargojogador')
@commands.has_permissions(administrator=True)
async def set_cargo_jogador(ctx, *, nome_cargo: str):
    """Define o nome do cargo dos jogadores PARA ESTE SERVIDOR."""
    server_config = get_server_config(ctx.guild.id)
    server_config["cargo_jogador"] = nome_cargo
    save_configs()  # Salva a alteração
    await ctx.send(
        f"✅ O cargo de jogador deste servidor foi definido para `{nome_cargo}`."
    )


@bot.command(name='setcategoriaprivada')
@commands.has_permissions(administrator=True)
async def set_categoria_privada(ctx, *, nome_categoria: str):
    """Define a categoria dos canais privados PARA ESTE SERVIDOR."""
    server_config = get_server_config(ctx.guild.id)
    server_config["categoria_privados"] = nome_categoria
    save_configs()  # Salva a alteração
    await ctx.send(
        f"✅ A categoria de canais privados deste servidor foi definida para `{nome_categoria}`."
    )


# Handler de erro genérico para os comandos acima
@set_canal_intro.error
@set_cargo_jogador.error
@set_categoria_privada.error
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("🚫 Apenas administradores podem usar este comando.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            f"❓ Faltou um argumento. Use `!help {ctx.command.name}` para ver como usar."
        )


# --- Executando o Bot ---
BOT_TOKEN = os.getenv('DISCORD_TOKEN')

bot.run(BOT_TOKEN)
