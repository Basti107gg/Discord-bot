import os
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta

TOKEN = os.getenv("TOKEN")

OWNER_ID = 1037047883133890560

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# DATA
# =========================
command_roles = {}
global_bans = {}  # user_id: reason
temp_bans = {}    # guild_id: {user_id: unban_time}
perm_bans = {}    # guild_id: [user_ids]

# =========================
# PERMISSION CHECK
# =========================
def has_permission(interaction, cmd):
    if interaction.user.id == OWNER_ID:
        return True

    roles = command_roles.get(cmd)
    if not roles:
        return True

    return any(r.id in roles for r in interaction.user.roles)

# =========================
# AUTO UNBAN TASK
# =========================
@tasks.loop(seconds=10)
async def check_temp_bans():
    now = datetime.utcnow()

    for guild_id in list(temp_bans.keys()):
        guild = bot.get_guild(guild_id)
        if not guild:
            continue

        for user_id, unban_time in list(temp_bans[guild_id].items()):
            if now >= unban_time:
                try:
                    user = await bot.fetch_user(user_id)
                    await guild.unban(user)
                except:
                    pass
                del temp_bans[guild_id][user_id]

# =========================
# GLOBAL BAN
# =========================
@bot.tree.command(name="globalban", description="Global bannen")
async def globalban(interaction: discord.Interaction, user: discord.User, reason: str):

    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ Nur Owner", ephemeral=True)

    global_bans[user.id] = reason

    for guild in bot.guilds:
        try:
            await guild.ban(user, reason=reason)
        except:
            pass

    await interaction.response.send_message(f"🌍 {user} global gebannt")

# =========================
# GLOBAL UNBAN
# =========================
@bot.tree.command(name="globalunban", description="Global unban")
async def globalunban(interaction: discord.Interaction, user: discord.User):

    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ Nur Owner", ephemeral=True)

    global_bans.pop(user.id, None)

    for guild in bot.guilds:
        try:
            await guild.unban(user)
        except:
            pass

    await interaction.response.send_message(f"🌍 {user} global entbannt")

# =========================
# TEMP BAN
# =========================
@bot.tree.command(name="ban", description="Temporärer Ban")
async def ban(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str):

    if not has_permission(interaction, "ban"):
        return await interaction.response.send_message("❌ Keine Rechte", ephemeral=True)

    await member.ban(reason=reason)

    if interaction.guild.id not in temp_bans:
        temp_bans[interaction.guild.id] = {}

    temp_bans[interaction.guild.id][member.id] = datetime.utcnow() + timedelta(minutes=minutes)

    await interaction.response.send_message(f"⏳ {member} gebannt für {minutes} Minuten")

# =========================
# PERM BAN
# =========================
@bot.tree.command(name="permban", description="Permanent bannen")
async def permban(interaction: discord.Interaction, member: discord.Member, reason: str):

    if not has_permission(interaction, "permban"):
        return await interaction.response.send_message("❌ Keine Rechte", ephemeral=True)

    await member.ban(reason=reason)

    if interaction.guild.id not in perm_bans:
        perm_bans[interaction.guild.id] = []

    perm_bans[interaction.guild.id].append(member.id)

    await interaction.response.send_message(f"🔨 {member} permanent gebannt")

# =========================
# UNBAN
# =========================
@bot.tree.command(name="unban", description="Unban")
async def unban(interaction: discord.Interaction, user: discord.User):

    if not has_permission(interaction, "unban"):
        return await interaction.response.send_message("❌ Keine Rechte", ephemeral=True)

    try:
        await interaction.guild.unban(user)
    except:
        pass

    if interaction.guild.id in temp_bans:
        temp_bans[interaction.guild.id].pop(user.id, None)

    if interaction.guild.id in perm_bans:
        if user.id in perm_bans[interaction.guild.id]:
            perm_bans[interaction.guild.id].remove(user.id)

    await interaction.response.send_message(f"✅ {user} entbannt")

# =========================
# BANLIST
# =========================
@bot.tree.command(name="banlist", description="Alle Bans anzeigen")
async def banlist(interaction: discord.Interaction):

    if not has_permission(interaction, "banlist"):
        return await interaction.response.send_message("❌ Keine Rechte", ephemeral=True)

    embed = discord.Embed(title="Banliste")

    # Global
    for uid, reason in global_bans.items():
        embed.add_field(name=f"🌍 {uid}", value=f"Global: {reason}", inline=False)

    # Temp
    guild_temp = temp_bans.get(interaction.guild.id, {})
    for uid, time in guild_temp.items():
        embed.add_field(name=f"⏳ {uid}", value=f"Bis: {time}", inline=False)

    # Perm
    guild_perm = perm_bans.get(interaction.guild.id, [])
    for uid in guild_perm:
        embed.add_field(name=f"🔨 {uid}", value="Permanent", inline=False)

    await interaction.response.send_message(embed=embed)

# =========================
# SERVERLIST
# =========================
@bot.tree.command(name="serverlist", description="Server Liste")
async def serverlist(interaction: discord.Interaction):

    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ Nur Owner", ephemeral=True)

    embed = discord.Embed(title="🌐 Serverliste")

    for guild in bot.guilds:
        invite = None

        for ch in guild.text_channels:
            try:
                invite = await ch.create_invite(max_age=300)
                break
            except:
                continue

        embed.add_field(
            name=guild.name,
            value=invite.url if invite else "❌ Kein Invite möglich",
            inline=False
        )

    await interaction.response.send_message(embed=embed)

# =========================
# SET COMMAND ROLE
# =========================
@bot.tree.command(name="setcmdrole", description="Setzt Rolle für Command")
async def setcmdrole(interaction: discord.Interaction, command: str, role: discord.Role):

    if interaction.guild.owner_id != interaction.user.id:
        return await interaction.response.send_message("❌ Nur Owner", ephemeral=True)

    if command not in command_roles:
        command_roles[command] = []

    command_roles[command].append(role.id)

    await interaction.response.send_message(f"✅ Rolle gesetzt für {command}")

# =========================
# READY
# =========================
@bot.event
async def on_ready():
    await bot.tree.sync()
    check_temp_bans.start()
    print("BOT ONLINE:", bot.user)

bot.run(TOKEN)
