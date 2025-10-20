import os
import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
from datetime import datetime
import json
from dotenv import load_dotenv

# Cargar variables del entorno
load_dotenv()

# Configuración del bot
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Configuración
CONFIG = {
    'canal_noticias': int(os.getenv('CANAL_NOTICIAS', 0)),
    'rol_anime': int(os.getenv('ROL_MENCION', 0)),
    'series_seguidas': {
        'manga': [
            "The 100 Girlfriends Who Really, Really, Really, Really, Really Love You",
            "One Piece", 
            "Spy x Family",
            "Dandadan",
            "When Will Her Tears Dry"  # Roshidere
        ],
        'anime': [
            "The 100 Girlfriends Who Really, Really, Really, Really, Really Love You",
            "Spy x Family",
            "Dandadan",
            "When Will Her Tears Dry"
        ]
    },
    'ultimas_noticias': set(),
    'ultimos_capitulos': {}
}

class AnimeNewsTracker:
    def __init__(self):
        self.session = None
    
    async def get_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def buscar_nuevos_anuncios(self):
        """Buscar nuevos anuncios de anime"""
        try:
            query = '''
            query {
                Page(page: 1, perPage: 10) {
                    media(status: NOT_YET_RELEASED, type: ANIME, sort: ID_DESC) {
                        title { romaji english }
                        startDate { year month day }
                        siteUrl
                        format
                    }
                }
            }
            '''
            
            session = await self.get_session()
            async with session.post('https://graphql.anilist.co', 
                                  json={'query': query}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    anuncios = []
                    for media in data['data']['Page']['media']:
                        titulo = media['title']['romaji'] or media['title']['english']
                        anuncios.append({
                            'titulo': titulo,
                            'tipo': 'NUEVO_ANIME',
                            'fecha': f"{media['startDate']['year']}-{media['startDate']['month']}-{media['startDate']['day']}",
                            'url': media['siteUrl'],
                            'formato': media['format']
                        })
                    return anuncios
        except Exception as e:
            print(f"Error buscando anuncios: {e}")
        return []
    
    async def buscar_info_serie(self, nombre_serie, tipo="ANIME"):
        """Buscar información específica de una serie"""
        try:
            query = '''
            query ($search: String, $type: MediaType) {
                Media(search: $search, type: $type) {
                    title { romaji english }
                    status
                    episodes
                    chapters
                    nextAiringEpisode { episode airingAt }
                    siteUrl
                    description
                }
            }
            '''
            
            variables = {'search': nombre_serie, 'type': tipo}
            session = await self.get_session()
            async with session.post('https://graphql.anilist.co', 
                                  json={'query': query, 'variables': variables}) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            print(f"Error buscando info de {nombre_serie}: {e}")
        return None
    
    async def buscar_noticias_reddit(self):
        """Buscar noticias en Reddit"""
        try:
            session = await self.get_session()
            async with session.get('https://www.reddit.com/r/anime/new/.json?limit=15') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    noticias = []
                    
                    for post in data['data']['children']:
                        titulo = post['data']['title'].lower()
                        contenido = post['data']['selftext'].lower()
                        
                        # Palabras clave importantes
                        keywords = [
                            'season 2', 'season 3', 'sequel', 'announced', 'confirmed',
                            'leak', 'rumor', 'adaptation', 'trailer', 'release date',
                            'anime awards', 'cancel', 'renewed', 'delay'
                        ]
                        
                        # Series específicas que te interesan
                        series_especificas = [
                            'roshidere', '100 girlfriends', 'dandadan', 
                            'spy x family', 'one piece', 'when will her tears dry'
                        ]
                        
                        if any(keyword in titulo for keyword in keywords) or \
                           any(serie in titulo for serie in series_especificas):
                            noticias.append({
                                'titulo': post['data']['title'],
                                'url': f"https://reddit.com{post['data']['permalink']}",
                                'tipo': 'NOTICIA_REDDIT',
                                'subreddit': post['data']['subreddit'],
                                'created': post['data']['created_utc']
                            })
                    
                    return noticias
        except Exception as e:
            print(f"Error buscando en Reddit: {e}")
        return []

# Instancia del tracker
tracker = AnimeNewsTracker()

@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user.name}')
    print(f'🆔 ID: {bot.user.id}')
    print(f'📅 Conectado a {len(bot.guilds)} servidores')
    
    # Iniciar tareas automáticas
    if not monitoreo_automatico.is_running():
        monitoreo_automatico.start()
    
    # Activar presencia
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="noticias de anime 🎬"
        )
    )

@tasks.loop(minutes=int(os.getenv('INTERVALO_VERIFICACION', 15)))
async def monitoreo_automatico():
    """Monitoreo automático de noticias"""
    try:
        print(f"🔍 Verificando noticias... {datetime.now().strftime('%H:%M:%S')}")
        
        if not CONFIG['canal_noticias']:
            return
        
        channel = bot.get_channel(CONFIG['canal_noticias'])
        if not channel:
            return
        
        # 1. Buscar nuevos anuncios de anime
        nuevos_anuncios = await tracker.buscar_nuevos_anuncios()
        for anuncio in nuevos_anuncios:
            id_noticia = f"anuncio_{anuncio['titulo']}"
            if id_noticia not in CONFIG['ultimas_noticias']:
                rol = channel.guild.get_role(CONFIG['rol_anime'])
                
                embed = discord.Embed(
                    title="🎊 ¡NUEVO ANIME ANUNCIADO!",
                    description=f"**{anuncio['titulo']}**",
                    color=0x00ff00,
                    url=anuncio['url']
                )
                embed.add_field(name="Formato", value=anuncio['formato'], inline=True)
                embed.add_field(name="Fecha Est.", value=anuncio['fecha'], inline=True)
                embed.add_field(name="Tipo", value="Nuevo Anime", inline=True)
                embed.set_footer(text="AniList")
                
                mensaje = f"{rol.mention if rol else ''} ¡Nuevo anime anunciado!"
                await channel.send(mensaje, embed=embed)
                CONFIG['ultimas_noticias'].add(id_noticia)
        
        # 2. Buscar noticias en Reddit
        noticias_reddit = await tracker.buscar_noticias_reddit()
        for noticia in noticias_reddit:
            id_noticia = f"reddit_{noticia['created']}"
            if id_noticia not in CONFIG['ultimas_noticias']:
                embed = discord.Embed(
                    title="🔍 Posible Noticia/Filtración",
                    description=noticia['titulo'],
                    color=0xff9900,
                    url=noticia['url']
                )
                embed.add_field(name="Fuente", value=f"r/{noticia['subreddit']}", inline=True)
                embed.add_field(name="Tipo", value="Noticia Reddit", inline=True)
                embed.set_footer(text="⚠️ Información no confirmada")
                
                await channel.send(embed=embed)
                CONFIG['ultimas_noticias'].add(id_noticia)
                
        # Limpiar noticias viejas (mantener solo las últimas 100)
        if len(CONFIG['ultimas_noticias']) > 100:
            CONFIG['ultimas_noticias'] = set(list(CONFIG['ultimas_noticias'])[-100:])
            
    except Exception as e:
        print(f"❌ Error en monitoreo automático: {e}")

@bot.command()
async def setup(ctx, canal: discord.TextChannel, rol: discord.Role):
    """Configurar el canal y rol para notificaciones"""
    CONFIG['canal_noticias'] = canal.id
    CONFIG['rol_anime'] = rol.id
    
    embed = discord.Embed(title="✅ Configuración Completada", color=0x00ff00)
    embed.add_field(name="Canal de Noticias", value=canal.mention, inline=True)
    embed.add_field(name="Rol de Mención", value=rol.mention, inline=True)
    embed.add_field(name="Estado", value="Monitoreo activado", inline=True)
    
    await ctx.send(embed=embed)
    
    # Reiniciar monitoreo si no está corriendo
    if not monitoreo_automatico.is_running():
        monitoreo_automatico.start()

@bot.command()
async def roshidere(ctx):
    """Información sobre Roshidere"""
    info = await tracker.buscar_info_serie("When Will Her Tears Dry", "MANGA")
    
    if info and info['data']['Media']:
        media = info['data']['Media']
        titulo = media['title']['romaji'] or media['title']['english']
        
        embed = discord.Embed(title=f"📖 {titulo}", color=0xff6b6b)
        embed.add_field(name="Estado", value=media['status'], inline=True)
        embed.add_field(name="Capítulos", value=media['chapters'] or "Desconocido", inline=True)
        embed.add_field(name="Enlace", value=f"[AniList]({media['siteUrl']})", inline=True)
        
        if media['description']:
            descripcion = media['description'][:200] + "..." if len(media['description']) > 200 else media['description']
            embed.add_field(name="Descripción", value=descripcion, inline=False)
        
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ No se pudo encontrar información de Roshidere")

@bot.command()
async def cien_novias(ctx):
    """Información sobre 100 Girlfriends"""
    info_manga = await tracker.buscar_info_serie("The 100 Girlfriends Who Really, Really, Really, Really, Really Love You", "MANGA")
    info_anime = await tracker.buscar_info_serie("The 100 Girlfriends Who Really, Really, Really, Really, Really Love You", "ANIME")
    
    embed = discord.Embed(title="💕 100 Girlfriends Info", color=0xff6b6b)
    
    if info_manga and info_manga['data']['Media']:
        manga = info_manga['data']['Media']
        embed.add_field(
            name="📖 Manga", 
            value=f"Capítulos: {manga['chapters'] or '?'}\nEstado: {manga['status']}", 
            inline=True
        )
    
    if info_anime and info_anime['data']['Media']:
        anime = info_anime['data']['Media']
        embed.add_field(
            name="🎬 Anime", 
            value=f"Episodios: {anime['episodes'] or '?'}\nEstado: {anime['status']}", 
            inline=True
        )
    
    await ctx.send(embed=embed)

@bot.command()
async def estado(ctx):
    """Ver el estado del bot"""
    embed = discord.Embed(title="🤖 Estado del Bot", color=0x3498db)
    embed.add_field(name="Canal Configurado", value=f"<#{CONFIG['canal_noticias']}>" if CONFIG['canal_noticias'] else "No configurado", inline=True)
    embed.add_field(name="Monitoreo Activo", value="✅ Sí" if monitoreo_automatico.is_running() else "❌ No", inline=True)
    embed.add_field(name="Series Seguidas", value=f"{len(CONFIG['series_seguidas']['manga'])} mangas\n{len(CONFIG['series_seguidas']['anime'])} animes", inline=True)
    embed.add_field(name="Últimas Noticias", value=len(CONFIG['ultimas_noticias']), inline=True)
    embed.add_field(name="Ping", value=f"{round(bot.latency * 1000)}ms", inline=True)
    
    await ctx.send(embed=embed)

@bot.command()
async def forzar_verificacion(ctx):
    """Forzar una verificación inmediata"""
    await ctx.send("🔍 Forzando verificación...")
    await monitoreo_automatico()
    await ctx.send("✅ Verificación completada")

@bot.command()
async def agregar_serie(ctx, tipo: str, *, nombre: str):
    """Agregar una serie para seguir (manga o anime)"""
    if tipo.lower() not in ['manga', 'anime']:
        await ctx.send("❌ Tipo debe ser 'manga' o 'anime'")
        return
    
    CONFIG['series_seguidas'][tipo.lower()].append(nombre)
    await ctx.send(f"✅ Agregado {nombre} a {tipo} seguidos")

# Manejo de errores
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Comando no encontrado. Usa `!help` para ver comandos disponibles")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ No tienes permisos para usar este comando")
    else:
        await ctx.send(f"❌ Error: {str(error)}")
        print(f"Error: {error}")

# Ejecutar el bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ ERROR: No se encontró DISCORD_TOKEN en el archivo .env")
        print("💡 Asegúrate de crear un archivo .env con tu token")
    else:
        bot.run(token)