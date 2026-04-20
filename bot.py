import os
import discord
from discord.ext import commands

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN fehlt in Railway Variables!")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# COMMAND REGISTRY (NEU)
# =========================
command_list = []


def register_command(name: str, desc: str):
    command_list.append((name, desc))


# =========================
# TICKET SYSTEM DATA
# =========================
ticket_roles = []
tickets = {}
ticket_counter = 0


def has_ticket_access(member: discord.Member):
    if member.guild.owner_id == member.id:
        return True
    if not ticket_roles:
        return True
    return any(r.id in ticket_roles for r in member.roles)


# =========================
# TICKET PANEL
# =========================
class TicketPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Ticket erstellen", style=discord.ButtonStyle.green)
    async def create(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal())


class TicketModal(discord.ui.Modal, title="Ticket erstellen"):
    reason = discord.ui.TextInput(label="Grund", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        global ticket_counter
        ticket_counter += 1

        guild = interaction.guild
        user = interaction.user

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True)
        }

        channel = await guild.create_text_channel(
            name=f"ticket-{ticket_counter}",
            overwrites=overwrites
        )

        await channel.send(
            embed=discord.Embed(
                title="🎫 Ticket geöffnet",
                description=f"User: {user.mention}\nGrund: {self.reason.value}",
                color=0x00ff00
            ),
            view=TicketControlView()
        )

        tickets[channel.id] = {
            "owner": user.id,
            "claimed_by": None,
            "reason": self.reason.value
        }

        await interaction.response.send_message("Ticket erstellt!", ephemeral=True)


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📌 Übernehmen", style=discord.ButtonStyle.blurple)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):

        data = tickets.get(interaction.channel.id)

        if not data:
            return await interaction.response.send_message("Fehler", ephemeral=True)

        if interaction.user.id == data["owner"]:
            return await interaction.response.send_message("Eigene Tickets nicht übernehmen", ephemeral=True)

        if data["claimed_by"]:
            return await interaction.response.send_message("Schon übernommen", ephemeral=True)

        if not has_ticket_access(interaction.user):
            return await interaction.response.send_message("Keine Rechte", ephemeral=True)

        data["claimed_by"] = interaction.user.id

        await interaction.channel.send(f"📌 Übernommen von {interaction.user.mention}")
        await interaction.response.send_message("OK", ephemeral=True)

    @discord.ui.button(label="🔒 Schließen", style=discord.ButtonStyle.red)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CloseModal())


class CloseModal(discord.ui.Modal, title="Ticket schließen"):
    reason = discord.ui.TextInput(label="Grund", required=True)

    async def on_submit(self, interaction: discord.Interaction):

        data = tickets.get(interaction.channel.id)

        if not data:
            return await interaction.response.send_message("Fehler", ephemeral=True)

        user = interaction.user

        if not (user.guild_permissions.administrator or user.id in [data["owner"], data["claimed_by"]]):
            return await interaction.response.send_message("Keine Rechte", ephemeral=True)

        try:
            owner = await bot.fetch_user(data["owner"])
            await owner.send(
                embed=discord.Embed(
                    title="Ticket geschlossen",
                    description=f"Grund: {self.reason.value}",
                    color=0xff0000
                )
            )
        except:
            pass

        await interaction.channel.send(f"Geschlossen von {user.mention}\nGrund: {self.reason.value}")

        tickets.pop(interaction.channel.id, None)
        await interaction.channel.delete()


# =========================
# COMMAND HELPER
# =========================
def cmd(name, desc):
    register_command(name, desc)


# =========================
# COMMANDS
# =========================
@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong 🏓 `{round(bot.latency * 1000)}ms`")


cmd("ping", "Bot Ping anzeigen")


@bot.command()
async def say(ctx, *, msg):
    await ctx.message.delete()
    await ctx.send(msg)


cmd("say", "Nachricht senden")


@bot.command()
async def help(ctx):
    embed = discord.Embed(title="📜 Help", color=0x3498db)
    for name, desc in command_list:
        embed.add_field(name=f"!{name}", value=desc, inline=False)
    await ctx.send(embed=embed)


cmd("help", "Command Liste anzeigen")


@bot.command()
async def cmds(ctx):
    embed = discord.Embed(title="📜 Commands", color=0x5865F2)

    for name, desc in command_list:
        embed.add_field(name=f"!{name}", value=desc, inline=False)

    await ctx.send(embed=embed)


# =========================
# USER INFO
# =========================
@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author

    embed = discord.Embed(title="User Info", color=0x00ff00)
    embed.add_field(name="Name", value=member.name)
    embed.add_field(name="ID", value=member.id)

    await ctx.send(embed=embed)


cmd("userinfo", "User Infos anzeigen")


# =========================
# SERVER INFO
# =========================
@bot.command()
async def serverinfo(ctx):
    g = ctx.guild

    embed = discord.Embed(title="Server Info", color=0x00ff00)
    embed.add_field(name="Name", value=g.name)
    embed.add_field(name="Members", value=g.member_count)

    await ctx.send(embed=embed)


cmd("serverinfo", "Server Infos anzeigen")


# =========================
# SERVERLIST
# =========================
@bot.command()
async def serverlist(ctx):

    embed = discord.Embed(title="🌐 Server Liste", color=0x5865F2)

    for guild in bot.guilds:
        invite = None
        try:
            for c in guild.text_channels:
                invite = await c.create_invite(max_age=300)
                break
        except:
            pass

        embed.add_field(
            name=guild.name,
            value=invite.url if invite else "Kein Invite",
            inline=False
        )

    await ctx.send(embed=embed)


cmd("serverlist", "Alle Server anzeigen")


# =========================
# TICKET PANEL
# =========================
@bot.command()
async def ticketpanel(ctx):
    embed = discord.Embed(
        title="🎫 Ticket System",
        description="Klicke um Ticket zu erstellen",
        color=0x00ff00
    )
    await ctx.send(embed=embed, view=TicketPanel())


cmd("ticketpanel", "Ticket System öffnen")


# =========================
# ROLE SYSTEM
# =========================
@bot.command()
async def addticketrole(ctx, role: discord.Role):
    if ctx.guild.owner_id != ctx.author.id:
        return await ctx.send("Nur Owner")

    ticket_roles.append(role.id)
    await ctx.send("Role hinzugefügt")


cmd("addticketrole", "Ticket Rechte setzen")


# =========================
# READY
# =========================
@bot.event
async def on_ready():
    print("BOT ONLINE:", bot.user)


bot.run(TOKEN)
