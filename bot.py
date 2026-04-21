import os
import discord
from discord.ext import commands

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN fehlt!")

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# COMMAND ROLE SYSTEM
# =========================
command_roles = {}  # {"ping": [role_id, role_id]}


def has_permission(interaction: discord.Interaction, cmd_name: str):
    if interaction.user.guild.owner_id == interaction.user.id:
        return True

    allowed_roles = command_roles.get(cmd_name)

    if not allowed_roles:
        return True

    return any(role.id in allowed_roles for role in interaction.user.roles)


# =========================
# TICKET SYSTEM
# =========================
tickets = {}
ticket_counter = 0
ticket_roles = []


def has_ticket_access(member: discord.Member):
    if member.guild.owner_id == member.id:
        return True
    if not ticket_roles:
        return True
    return any(r.id in ticket_roles for r in member.roles)


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
                description=f"{user.mention}\nGrund: {self.reason}",
                color=0x00ff00
            ),
            view=TicketControlView()
        )

        tickets[channel.id] = {
            "owner": user.id,
            "claimed_by": None
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
            await owner.send(f"Ticket geschlossen\nGrund: {self.reason}")
        except:
            pass

        await interaction.channel.delete()


# =========================
# SLASH COMMANDS
# =========================

@bot.tree.command(name="ping", description="Ping anzeigen")
async def ping(interaction: discord.Interaction):
    if not has_permission(interaction, "ping"):
        return await interaction.response.send_message("Keine Rechte", ephemeral=True)

    await interaction.response.send_message(f"Pong {round(bot.latency*1000)}ms")


@bot.tree.command(name="cmds", description="Alle Commands anzeigen")
async def cmds(interaction: discord.Interaction):
    embed = discord.Embed(title="Commands")

    for cmd in bot.tree.get_commands():
        embed.add_field(
            name=f"/{cmd.name}",
            value=cmd.description or "Keine Beschreibung",
            inline=False
        )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="ticketpanel", description="Ticket Panel senden")
async def ticketpanel(interaction: discord.Interaction):
    if not has_permission(interaction, "ticketpanel"):
        return await interaction.response.send_message("Keine Rechte", ephemeral=True)

    embed = discord.Embed(title="Ticket System", description="Button klicken")
    await interaction.response.send_message(embed=embed, view=TicketPanel())


@bot.tree.command(name="giverole", description="Rolle geben")
async def giverole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not has_permission(interaction, "giverole"):
        return await interaction.response.send_message("Keine Rechte", ephemeral=True)

    await member.add_roles(role)
    await interaction.response.send_message(f"{member.mention} hat Rolle {role.name} bekommen")


@bot.tree.command(name="setcmdrole", description="Setzt Rollen für Command")
async def setcmdrole(interaction: discord.Interaction, command: str, role: discord.Role):
    if interaction.guild.owner_id != interaction.user.id:
        return await interaction.response.send_message("Nur Owner", ephemeral=True)

    if command not in command_roles:
        command_roles[command] = []

    command_roles[command].append(role.id)

    await interaction.response.send_message(f"Rolle gesetzt für /{command}")


# =========================
# READY + SYNC
# =========================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print("BOT ONLINE:", bot.user)


bot.run(TOKEN)
