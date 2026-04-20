import os
import discord
from discord.ext import commands

# =========================
# TOKEN (RAILWAY ENV)
# =========================
TOKEN = os.getenv("TOKEN")

if TOKEN is None:
    raise ValueError("❌ TOKEN fehlt! Setze ihn in Railway Variables als TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# SETTINGS
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


# =========================
# TICKET CONTROL
# =========================
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

        if data["claimed_by"] is not None:
            return await interaction.response.send_message("❌ schon übernommen", ephemeral=True)

        if not has_ticket_access(interaction.user):
            return await interaction.response.send_message("❌ keine Rechte", ephemeral=True)

        data["claimed_by"] = interaction.user.id

        await interaction.channel.send(f"📌 Ticket übernommen von {interaction.user.mention}")
        await interaction.response.send_message("✅ übernommen", ephemeral=True)

    @discord.ui.button(label="🔒 Schließen", style=discord.ButtonStyle.red)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_modal(CloseModal())


# =========================
# CLOSE MODAL
# =========================
class CloseModal(discord.ui.Modal, title="Ticket schließen"):
    reason = discord.ui.TextInput(label="Grund", required=True)

    async def on_submit(self, interaction: discord.Interaction):

        data = tickets.get(interaction.channel.id)

        if not data:
            return await interaction.response.send_message("❌ Fehler", ephemeral=True)

        user = interaction.user

        is_owner = user.id == data["owner"]
        is_claimed = data["claimed_by"] == user.id
        is_admin = interaction.user.guild_permissions.administrator

        if not (is_owner or is_claimed or is_admin):
            return await interaction.response.send_message("❌ keine Rechte", ephemeral=True)

        # DM an User
        try:
            owner = await bot.fetch_user(data["owner"])

            embed = discord.Embed(
                title="🔒 Ticket geschlossen",
                description=f"Grund: {self.reason.value}",
                color=0xff0000
            )

            await owner.send(embed=embed)

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
@bot.command()
async def ticketpanel(ctx):
    embed = discord.Embed(
        title="🎫 Ticket System",
        description="Klicke um Ticket zu erstellen",
        color=0x00ff00
    )
    await ctx.send(embed=embed, view=TicketPanel())


@bot.command()
async def addticketrole(ctx, role: discord.Role):
    if ctx.guild.owner_id != ctx.author.id:
        return await ctx.send("❌ nur Owner")

    ticket_roles.append(role.id)
    await ctx.send(f"✅ Role {role.name} hinzugefügt")


@bot.command()
async def cmds(ctx):
    embed = discord.Embed(title="📜 Commands", color=0x3498db)
    embed.add_field(name="ticketpanel", value="Ticket öffnen", inline=False)
    embed.add_field(name="addticketrole", value="Ticket Rechte setzen", inline=False)
    embed.add_field(name="ownerpanel", value="Owner Menü", inline=False)
    await ctx.send(embed=embed)


@bot.command()
async def ownerpanel(ctx):
    if ctx.guild.owner_id != ctx.author.id:
        return await ctx.send("❌ nur Owner")

    await ctx.send("👑 Owner Panel aktiv")


# =========================
# READY
# =========================
@bot.event
async def on_ready():
    print("BOT ONLINE:", bot.user)


bot.run(TOKEN)
