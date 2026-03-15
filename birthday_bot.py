import os
import sqlite3
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta

TOKEN = os.getenv("TOKEN")

GUILD_ID = 1377672440276058214
CHANNEL_ID = 1377672440783704219
ROLE_ID = 1482668657178972300

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- DATABASE ----------------

conn = sqlite3.connect("birthday.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS birthdays(
user_id TEXT PRIMARY KEY,
date TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS congrats(
message_id TEXT,
user_id TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS announced(
user_id TEXT,
date TEXT
)
""")

conn.commit()

# ---------------- 버튼 ----------------

class BirthdayView(discord.ui.View):

    def __init__(self, member=None):
        super().__init__(timeout=None)
        self.member = member

    @discord.ui.button(label="🎁 축하하기 (0)", style=discord.ButtonStyle.green, custom_id="birthday_congrats")
    async def congrats(self, interaction: discord.Interaction, button: discord.ui.Button):

        cursor.execute(
            "SELECT * FROM congrats WHERE message_id=? AND user_id=?",
            (interaction.message.id, interaction.user.id)
        )

        if cursor.fetchone():
            await interaction.response.send_message("이미 축하했습니다 🎂", ephemeral=True)
            return

        cursor.execute(
            "INSERT INTO congrats VALUES (?,?)",
            (interaction.message.id, interaction.user.id)
        )

        conn.commit()

        cursor.execute(
            "SELECT COUNT(*) FROM congrats WHERE message_id=?",
            (interaction.message.id,)
        )

        count = cursor.fetchone()[0]

        button.label = f"🎁 축하하기 ({count})"

        await interaction.message.edit(view=self)

        await interaction.response.send_message("🎉 축하를 보냈습니다!", ephemeral=True)

# ---------------- 생일 등록 ----------------

@bot.tree.command(name="생일등록")
@app_commands.checks.has_permissions(administrator=True)

async def add_birthday(interaction: discord.Interaction, member: discord.Member, date: str):

    try:
        datetime.strptime(date, "%m-%d")
    except:
        await interaction.response.send_message("MM-DD 형식", ephemeral=True)
        return

    cursor.execute(
        "INSERT OR REPLACE INTO birthdays VALUES (?,?)",
        (member.id, date)
    )

    conn.commit()

    await interaction.response.send_message(
        f"{member.mention} 생일 등록 완료 🎂",
        ephemeral=True
    )

# ---------------- 생일 삭제 ----------------

@bot.tree.command(name="생일삭제")
@app_commands.checks.has_permissions(administrator=True)

async def remove_birthday(interaction: discord.Interaction, member: discord.Member):

    cursor.execute(
        "DELETE FROM birthdays WHERE user_id=?",
        (member.id,)
    )

    conn.commit()

    await interaction.response.send_message("삭제 완료", ephemeral=True)

# ---------------- 생일 목록 ----------------

@bot.tree.command(name="생일목록")

async def birthday_list(interaction: discord.Interaction):

    cursor.execute("SELECT * FROM birthdays")

    data = cursor.fetchall()

    embed = discord.Embed(title="🎂 생일 목록", color=0xff69b4)

    for user_id, date in data:

        member = interaction.guild.get_member(int(user_id))

        if member:
            embed.add_field(name=member.display_name, value=date)

    await interaction.response.send_message(embed=embed)

# ---------------- 생일 체크 ----------------

@tasks.loop(minutes=1)
async def birthday_check():

    now = datetime.now()

    if now.strftime("%H:%M") != "00:00":
        return

    guild = bot.get_guild(GUILD_ID)
    channel = bot.get_channel(CHANNEL_ID)
    role = guild.get_role(ROLE_ID)

    today = now.strftime("%m-%d")

    cursor.execute("SELECT * FROM birthdays")

    data = cursor.fetchall()

    for user_id, date in data:

        member = guild.get_member(int(user_id))

        if not member:
            continue

        cursor.execute(
            "SELECT * FROM announced WHERE user_id=? AND date=?",
            (user_id, today)
        )

        if cursor.fetchone():
            continue

        if date == today:

            try:
                await member.add_roles(role)
            except:
                pass

            try:
                if not member.display_name.startswith("🎂"):
                    await member.edit(nick=f"🎂 {member.display_name}")
            except:
                pass

            embed = discord.Embed(
                title="🎉 생일 축하!",
                description=f"{member.mention}님의 생일입니다!",
                color=0xff69b4
            )

            view = BirthdayView(member)

            message = await channel.send(embed=embed, view=view)

            cursor.execute(
                "INSERT INTO announced VALUES (?,?)",
                (user_id, today)
            )

            conn.commit()

# ---------------- READY ----------------

@bot.event
async def on_ready():

    await bot.tree.sync()

    bot.add_view(BirthdayView())

    birthday_check.start()

    print("생일봇 실행 완료")

bot.run(TOKEN)
