import os
import sqlite3
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime
from zoneinfo import ZoneInfo

def get_kst_now():
    return datetime.now(ZoneInfo("Asia/Seoul"))

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
CREATE TABLE IF NOT EXISTS congrats_count(
user_id TEXT PRIMARY KEY,
count INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS announced(
user_id TEXT,
date TEXT
)
""")

conn.commit()

# ---------------- 축하 버튼 ----------------

class BirthdayView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

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

        cursor.execute(
            "INSERT OR IGNORE INTO congrats_count VALUES (?,0)",
            (interaction.user.id,)
        )

        cursor.execute(
            "UPDATE congrats_count SET count=count+1 WHERE user_id=?",
            (interaction.user.id,)
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
        await interaction.response.send_message("MM-DD 형식으로 입력", ephemeral=True)
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

    await interaction.response.send_message(
        f"{member.display_name} 생일 삭제 완료",
        ephemeral=True
    )


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

# ---------------- 축하 랭킹 ----------------

@bot.tree.command(name="축하랭킹")
async def congrats_rank(interaction: discord.Interaction):

    cursor.execute(
        "SELECT * FROM congrats_count ORDER BY count DESC LIMIT 5"
    )

    data = cursor.fetchall()

    embed = discord.Embed(title="🏆 축하왕 랭킹", color=0xffd700)

    for i, (user_id, count) in enumerate(data, start=1):

        member = interaction.guild.get_member(int(user_id))

        if member:
            embed.add_field(
                name=f"{i}위 {member.display_name}",
                value=f"{count}회 축하"
            )

    await interaction.response.send_message(embed=embed)

# ---------------- 월간 캘린더 ----------------

async def send_monthly_calendar():

    guild = bot.get_guild(GUILD_ID)
    channel = await bot.fetch_channel(CHANNEL_ID)

    now = get_kst_now()

    if now.day != 1:
        return

    month = now.strftime("%m")

    cursor.execute("SELECT * FROM birthdays")
    data = cursor.fetchall()

    birthday_list = []

    for user_id, date in data:

        if date.startswith(month):

            member = guild.get_member(int(user_id))

            if member:
                birthday_list.append(f"{date} {member.display_name}")

    if birthday_list:

        embed = discord.Embed(
            title=f"📅 {month}월 생일 캘린더",
            description="\n".join(birthday_list),
            color=0xff69b4
        )

        await channel.send(embed=embed)

# ---------------- 생일 실행 ----------------

async def run_birthday():

    guild = bot.get_guild(GUILD_ID)
    channel = await bot.fetch_channel(CHANNEL_ID)

    role = guild.get_role(ROLE_ID)

    if role is None:
        print("❌ ROLE NOT FOUND")
        return

    today = get_kst_now().strftime("%m-%d")

    cursor.execute("SELECT * FROM birthdays")
    data = cursor.fetchall()

    for user_id, date in data:

        member = guild.get_member(int(user_id))

        if member is None:
            try:
                member = await guild.fetch_member(int(user_id))
            except:
                continue

        if date == today:

            cursor.execute(
                "SELECT * FROM announced WHERE user_id=? AND date=?",
                (user_id, today)
            )

            if cursor.fetchone():
                continue

            try:
                await member.add_roles(role)
                print(f"역할 지급 성공:{member}")
            except Exception as e:
                print(f"역할 지급 실패:{e}")

            try:
                if not member.display_name.startswith("🎂"):
                    await member.edit(nick=f"🎂 {member.display_name}")
            except:
                pass

            embed = discord.Embed(
                title="🎉 생일 축하!",
                description=f"오늘은 {member.mention}님의 생일입니다! 다들 축하해 주세요!! 🥳",
                color=0xff69b4
            )

            view = BirthdayView()

            message = await channel.send(embed=embed, view=view)

            cursor.execute(
                "INSERT INTO announced VALUES (?,?)",
                (user_id, today)
            )

            conn.commit()

            try:
                await member.send("🎂 생일 축하합니다!")
            except:
                pass

        else:

            if role in member.roles:
                try:
                    await member.remove_roles(role)
                except:
                    pass

            if member.display_name.startswith("🎂 "):
                try:
                    await member.edit(nick=member.display_name.replace("🎂 ", ""))
                except:
                    pass

# ---------------- 자동 루프 ----------------

@tasks.loop(minutes=1)
async def birthday_loop():

    now = get_kst_now()

    if now.strftime("%m-%d %H:%M") == "01-01 00:02":
        cursor.execute("DELETE FROM announced")
        conn.commit()

    if now.strftime("%H:%M") == "00:00":
        await run_birthday()

    if now.strftime("%H:%M") == "00:01":
        await send_monthly_calendar()

# ---------------- 테스트 ----------------

@bot.tree.command(name="생일테스트")
async def birthday_test(interaction: discord.Interaction):

    await run_birthday()

    await interaction.response.send_message("테스트 실행 완료", ephemeral=True)

# ---------------- READY ----------------

@bot.event
async def on_ready():

    guild = discord.Object(id=GUILD_ID)

    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)

    bot.add_view(BirthdayView())

    birthday_loop.start()

    print("🎂 생일봇 완전판 실행 완료")

bot.run(TOKEN)
