import os
import discord
from discord.ext import commands

# =========================
# TOKEN (RAILWAY ENV)
# =========================
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("❌ TOKEN fehlt! Setze ihn in Railway Variables als TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# TICKET SYSTEM
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

        embed = discord.Embed(
            title="🎫 Ticket geöffnet",
            description=f"User: {user.mention}\nGrund: {self.reason.value}",
            color=0x00ff00
        )

        await channel.send(embed=embed, view=TicketControlView())

        tickets[channel.id] = {
            "owner": user.id,
            "claimed_by": None,
            "reason": self.reason.value
        }

        await interaction.response.send_message("✅ Ticket erstellt!", ephemeral=True)


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📌 Übernehmen", style=discord.ButtonStyle.blurple)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):

        data = tickets.get(interaction.channel.id)

        if not data:
            return await interaction.response.send_message("❌ Fehler", ephemeral=True)

        if interaction.user.id == data["owner"]:
            return await interaction.response.send_message("❌ eigenes Ticket geht nicht", ephemeral=True)

        if data["claimed_by"]:
            return await interaction.response.send_message("❌ schon übernommen", ephemeral=True)

        if not has_ticket_access(interaction.user):
            return await interaction.response.send_message("❌ keine Rechte", ephemeral=True)

        data["claimed_by"] = interaction.user.id

        await interaction.channel.send(f"📌 Übernommen von {interaction.user.mention}")
        await interaction.response.send_message("✅ übernommen", ephemeral=True)

    @discord.ui.button(label="🔒 Schließen", style=discord.ButtonStyle.red)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CloseModal())


class CloseModal(discord.ui.Modal, title="Ticket schließen"):
    reason = discord.ui.TextInput(label="Grund", required=True)

    async def on_submit(self, interaction: discord.Interaction):

        data = tickets.get(interaction.channel.id)

        if not data:
            return await interaction.response.send_message("❌ Fehler", ephemeral=True)

        user = interaction.user

        if not (user.guild_permissions.administrator or user.id in [data["owner"], data["claimed_by"]]):
            return await interaction.response.send_message("❌ keine Rechte", ephemeral=True)

        # DM an Owner
        try:
            owner = await bot.fetch_user(data["owner"])
            await owner.send(
                embed=discord.Embed(
                    title="🔒 Ticket geschlossen",
                    description=f"Grund: {self.reason.value}",
                    color=0xff0000
                )
            )
        except:
            pass

        await interaction.channel.send(
            f"🔒 geschlossen von {user.mention}\nGrund: {self.reason.value}"
        )

        tickets.pop(interaction.channel.id, None)
        await interaction.channel.delete()


# =========================
# COMMANDS
# =========================

@bot.command(help="Ping des Bots anzeigen")
async def ping(ctx):
    await ctx.send(f"Pong 🏓 `{round(bot.latency * 1000)}ms`")


@bot.command(help="Nachricht senden")
async def say(ctx, *, msg):
    await ctx.message.delete()
    await ctx.send(msg)


@bot.command(help="User Informationen")
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author

    embed = discord.Embed(title="User Info", color=0x00ff00)
    embed.add_field(name="Name", value=member.name)
    embed.add_field(name="ID", value=member.id)

    await ctx.send(embed=embed)


@bot.command(help="Server Informationen")
async def serverinfo(ctx):
    g = ctx.guild

    embed = discord.Embed(title="Server Info", color=0x00ff00)
    embed.add_field(name="Name", value=g.name)
    embed.add_field(name="Members", value=g.member_count)

    await ctx.send(embed=embed)


@bot.command(help="Alle Server mit Invite anzeigen")
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


@bot.command(help="Ticket System öffnen")
async def ticketpanel(ctx):
    embed = discord.Embed(
        title="🎫 Ticket System",
        description="Klicke um Ticket zu erstellen",
        color=0x00ff00
    )
    await ctx.send(embed=embed, view=TicketPanel())


@bot.command(help="Ticket Role hinzufügen (nur Owner)")
async def addticketrole(ctx, role: discord.Role):
    if ctx.guild.owner_id != ctx.author.id:
        return await ctx.send("❌ nur Owner")

    ticket_roles.append(role.id)
    await ctx.send("✅ Role hinzugefügt")


@bot.command(help="Alle Commands anzeigen")
async def cmds(ctx):

    embed = discord.Embed(title="📜 Commands", color=0x5865F2)

    for command in bot.commands:
        if command.hidden:
            continue

        embed.add_field(
            name=f"!{command.name}",
            value=command.help or "Keine Beschreibung",
            inline=False
        )

    await ctx.send(embed=embed)


# =========================
# READY
# =========================
@bot.event
async def on_ready():
    print("BOT ONLINE:", bot.user)


bot.run(TOKEN)
