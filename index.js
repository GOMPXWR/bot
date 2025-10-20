const { Client, GatewayIntentBits, EmbedBuilder, ActivityType } = require('discord.js');
const axios = require('axios');

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildMembers
    ]
});

const CONFIG = {
    canalNoticias: process.env.CANAL_NOTICIAS || '1429302754085703791',
    rolMencion: process.env.ROL_MENCION || '1429302433309261985',
    seriesSeguidas: {
        manga: [
            "The 100 Girlfriends Who Really, Really, Really, Really, Really Love You",
            "One Piece",
            "Spy x Family",
            "Dandadan",
            "When Will Her Tears Dry"
        ],
        anime: [
            "The 100 Girlfriends Who Really, Really, Really, Really, Really Love You",
            "Spy x Family",
            "Dandadan",
            "When Will Her Tears Dry"
        ]
    },
    ultimasNoticias: new Set()
};

client.once('ready', () => {
    console.log(`✅ Bot conectado como ${client.user.tag}`);
    client.user.setActivity('noticias de anime 🎬', { type: ActivityType.Watching });
    
    setInterval(verificarNoticias, 10 * 60 * 1000);
    verificarNoticias();
});

async function verificarNoticias() {
    try {
        console.log('🔍 Verificando noticias...');
        const channel = await client.channels.fetch(CONFIG.canalNoticias);
        if (!channel) return;

        const anuncios = await buscarAnunciosAniList();
        const noticiasReddit = await buscarNoticiasReddit();

        for (const anuncio of anuncios) {
            const idNoticia = `anuncio_${anuncio.titulo}`;
            if (!CONFIG.ultimasNoticias.has(idNoticia)) {
                const embed = new EmbedBuilder()
                    .setTitle('🎊 ¡NUEVO ANIME ANUNCIADO!')
                    .setDescription(`**${anuncio.titulo}**`)
                    .setColor(0x00FF00)
                    .setURL(anuncio.url)
                    .addFields(
                        { name: 'Formato', value: anuncio.formato, inline: true },
                        { name: 'Fecha Est.', value: anuncio.fecha, inline: true },
                        { name: 'Tipo', value: 'Nuevo Anime', inline: true }
                    )
                    .setFooter({ text: 'AniList' });

                await channel.send({
                    content: `<@&${CONFIG.rolMencion}> ¡Nuevo anime anunciado!`,
                    embeds: [embed]
                });
                CONFIG.ultimasNoticias.add(idNoticia);
            }
        }

        for (const noticia of noticiasReddit) {
            const idNoticia = `reddit_${noticia.created}`;
            if (!CONFIG.ultimasNoticias.has(idNoticia)) {
                const embed = new EmbedBuilder()
                    .setTitle('🔍 Posible Noticia/Filtración')
                    .setDescription(noticia.titulo)
                    .setColor(0xFF9900)
                    .setURL(noticia.url)
                    .addFields(
                        { name: 'Fuente', value: `r/${noticia.subreddit}`, inline: true },
                        { name: 'Tipo', value: 'Noticia Reddit', inline: true }
                    )
                    .setFooter({ text: '⚠️ Información no confirmada' });

                await channel.send({ embeds: [embed] });
                CONFIG.ultimasNoticias.add(idNoticia);
            }
        }

        if (CONFIG.ultimasNoticias.size > 100) {
            const arrayNoticias = Array.from(CONFIG.ultimasNoticias);
            CONFIG.ultimasNoticias = new Set(arrayNoticias.slice(-100));
        }
    } catch (error) {
        console.error('❌ Error en verificación:', error);
    }
}

async function buscarAnunciosAniList() {
    try {
        const query = `
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
        `;

        const response = await axios.post('https://graphql.anilist.co', { query });
        const anuncios = [];

        for (const media of response.data.data.Page.media) {
            const titulo = media.title.romaji || media.title.english;
            anuncios.push({
                titulo: titulo,
                tipo: 'NUEVO_ANIME',
                fecha: `${media.startDate.year}-${media.startDate.month}-${media.startDate.day}`,
                url: media.siteUrl,
                formato: media.format
            });
        }
        return anuncios;
    } catch (error) {
        console.error('Error en AniList:', error);
        return [];
    }
}

async function buscarNoticiasReddit() {
    try {
        const response = await axios.get('https://www.reddit.com/r/anime/new/.json?limit=15');
        const noticias = [];

        for (const post of response.data.data.children) {
            const titulo = post.data.title.toLowerCase();
            const keywords = [
                'season 2', 'season 3', 'sequel', 'announced', 'confirmed',
                'leak', 'rumor', 'adaptation', 'trailer', 'release date',
                'anime awards', 'cancel', 'renewed', 'delay'
            ];
            const seriesEspecificas = [
                'roshidere', '100 girlfriends', 'dandadan',
                'spy x family', 'one piece', 'when will her tears dry'
            ];

            if (keywords.some(keyword => titulo.includes(keyword)) ||
                seriesEspecificas.some(serie => titulo.includes(serie))) {
                noticias.push({
                    titulo: post.data.title,
                    url: `https://reddit.com${post.data.permalink}`,
                    tipo: 'NOTICIA_REDDIT',
                    subreddit: post.data.subreddit,
                    created: post.data.created_utc
                });
            }
        }
        return noticias;
    } catch (error) {
        console.error('Error en Reddit:', error);
        return [];
    }
}

client.on('messageCreate', async (message) => {
    if (message.author.bot) return;

    if (message.content === '!setup') {
        if (!message.member.permissions.has('ADMINISTRATOR')) {
            return message.reply('❌ Necesitas permisos de administrador.');
        }
        
        CONFIG.canalNoticias = message.channel.id;
        const rol = message.mentions.roles.first();
        if (rol) CONFIG.rolMencion = rol.id;

        const embed = new EmbedBuilder()
            .setTitle('✅ Configuración Completada')
            .setColor(0x00FF00)
            .addFields(
                { name: 'Canal de Noticias', value: `<#${CONFIG.canalNoticias}>`, inline: true },
                { name: 'Rol de Mención', value: `<@&${CONFIG.rolMencion}>`, inline: true },
                { name: 'Estado', value: 'Monitoreo activado', inline: true }
            );

        await message.reply({ embeds: [embed] });
    }

    if (message.content === '!estado') {
        const embed = new EmbedBuilder()
            .setTitle('🤖 Estado del Bot')
            .setColor(0x3498DB)
            .addFields(
                { name: 'Canal Configurado', value: `<#${CONFIG.canalNoticias}>`, inline: true },
                { name: 'Series Seguidas', value: `${CONFIG.seriesSeguidas.manga.length} mangas\n${CONFIG.seriesSeguidas.anime.length} animes`, inline: true },
                { name: 'Últimas Noticias', value: CONFIG.ultimasNoticias.size.toString(), inline: true },
                { name: 'Ping', value: `${client.ws.ping}ms`, inline: true }
            );

        await message.reply({ embeds: [embed] });
    }

    if (message.content === '!roshidere') {
        const info = await buscarInfoAniList("When Will Her Tears Dry", "MANGA");
        if (info && info.data.Media) {
            const media = info.data.Media;
            const titulo = media.title.romaji || media.title.english;
            
            const embed = new EmbedBuilder()
                .setTitle(`📖 ${titulo}`)
                .setColor(0xFF6B6B)
                .addFields(
                    { name: 'Estado', value: media.status, inline: true },
                    { name: 'Capítulos', value: media.chapters?.toString() || 'Desconocido', inline: true },
                    { name: 'Enlace', value: `[AniList](${media.siteUrl})`, inline: true }
                );

            await message.reply({ embeds: [embed] });
        } else {
            await message.reply('❌ No se pudo encontrar información de Roshidere');
        }
    }

    if (message.content === '!cien_novias') {
        const infoManga = await buscarInfoAniList("The 100 Girlfriends Who Really, Really, Really, Really, Really Love You", "MANGA");
        const infoAnime = await buscarInfoAniList("The 100 Girlfriends Who Really, Really, Really, Really, Really Love You", "ANIME");
        
        const embed = new EmbedBuilder()
            .setTitle('💕 100 Girlfriends Info')
            .setColor(0xFF6B6B);

        if (infoManga?.data?.Media) {
            const manga = infoManga.data.Media;
            embed.addFields({
                name: '📖 Manga',
                value: `Capítulos: ${manga.chapters || '?'}\nEstado: ${manga.status}`,
                inline: true
            });
        }

        if (infoAnime?.data?.Media) {
            const anime = infoAnime.data.Media;
            embed.addFields({
                name: '🎬 Anime', 
                value: `Episodios: ${anime.episodes || '?'}\nEstado: ${anime.status}`,
                inline: true
            });
        }

        await message.reply({ embeds: [embed] });
    }

    if (message.content === '!forzar_verificacion') {
        await message.reply('🔍 Forzando verificación...');
        await verificarNoticias();
        await message.reply('✅ Verificación completada');
    }
});

async function buscarInfoAniList(nombreSerie, tipo) {
    try {
        const query = `
            query ($search: String, $type: MediaType) {
                Media(search: $search, type: $type) {
                    title { romaji english }
                    status
                    episodes
                    chapters
                    siteUrl
                    description
                }
            }
        `;

        const variables = { search: nombreSerie, type: tipo };
        const response = await axios.post('https://graphql.anilist.co', {
            query,
            variables
        });

        return response.data;
    } catch (error) {
        console.error('Error buscando info:', error);
        return null;
    }
}

client.login(process.env.DISCORD_TOKEN);