import asyncio
import random
import os
import asyncpg
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.types import ChatMemberUpdated

TOKEN = os.getenv("TOKEN") # На Render берем из Environment Variables
DATABASE_URL = os.getenv("DATABASE_URL") # Render сам даст эту ссылку

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher()
db_pool = None # Пул подключений к БД

# ===== 200+ СТАТЕЙ =====
ARTICLES = [
    "📰 <b>ГОРЯЧИЕ НОВОСТИ</b>\n\n{user} сегодня был замечен за поеданием 5-й пиццы подряд. Ученые в шоке, холодильник в панике.",
    "📰 <b>СЕНСАЦИЯ</b>\n\n{user} официально признан самым громким смехом в чате. Соседи из соседнего чата подали жалобу.",
    "📰 <b>ЭКОНОМИКА</b>\n\nАкции компании {user} выросли на 300% после фразы 'ща сделаю'. Инвесторы плачут от счастья.",
    "📰 <b>КУЛЬТУРА</b>\n\n{user} выпустил новый хит 'Я в афк на 5 минут'. Уже 24 часа в топе чартов.",
    "📰 <b>СПОРТ</b>\n\n{user} установил мировой рекорд по залипанию в телефон. Золотая медаль и горб в подарок.",
    "📰 <b>ПОГОДА</b>\n\nСегодня в чате солнечно, потому что {user} зашел и всем поднял настроение.",
    "📰 <b>КРИМИНАЛ</b>\n\n{user} подозревается в краже всех мемов из интернета. Доказательств нет, но мы то знаем.",
    "📰 <b>НАУКА</b>\n\n{user} доказал теорему 'Если не я, то кто?'. Нобелевскую выдали в виде стикеров.",
    # Добавь сюда еще 192+ штук сам
]
used_articles = {} # user_id: [список использованных]

# ===== ВСПОМОГАТЕЛКИ =====
async def is_admin(message):
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    return member.status in ["administrator", "creator"]

def get_user_link(user: types.User):
    return f"<a href='tg://user?id={user.id}'>{user.full_name}</a>"

# ===== КОМАНДЫ =====

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = """👋 <b>Чем я могу вам помочь?</b>

Напишите одно из слов:
<code>Команды</code> - список всех команд
<code>Нужно повышение</code> - список админов
<code>Помощь</code> - связь с главным
"""
    await message.reply(text)

@dp.message(F.text.lower() == "команды")
async def cmd_list(message: types.Message):
    text = """
📜 <b>ВСЕ ДОСТУПНЫЕ КОМАНДЫ:</b>

<b>Основные:</b>
/все - Список участников по ролям
/моястатья - Выпустить газету про себя
/help - Это меню

<b>Админ:</b>
/kick @юзер - Кикнуть
/ban @юзер - Забанить навсегда
/mute @юзер 10m - Мут на время. s m h d
/warn @юзер - Выдать варн. 3 варна = бан
"""
    await message.reply(text)

@dp.message(F.text.lower() == "нужно повышение")
async def need_promo(message: types.Message):
    admins = await bot.get_chat_administrators(message.chat.id)
    text = "👑 <b>АДМИНИСТРАЦИЯ ГРУППЫ:</b>\n\n"
    for admin in admins:
        if admin.user.is_bot: continue
        text += f"{get_user_link(admin.user)}\n"
    await message.reply(text)

@dp.message(F.text.lower() == "помощь")
async def need_help(message: types.Message):
    await message.reply("Обратитесь к @Xonadatio")

# 1. /ВСЕ С РОЛЯМИ
@dp.message(Command("все"))
async def mention_all(message: types.Message):
    if not await is_admin(message): return

    admins_list = []
    members_list = []

    async for chat_member in bot.get_chat_members(message.chat.id):
        user = chat_member.user
        if user.is_bot: continue
        user_link = get_user_link(user)

        if chat_member.status in ["creator", "administrator"]:
            admins_list.append(f"{user_link} 🎩")
        else:
            members_list.append(f"{user_link} 🏷️")

    text = f"📢 <b>ВСЕ УЧАСТНИКИ ЧАТА: {message.chat.title}</b>\n\n"
    text += "<b>Администрация 🎩</b>\n" + "\n".join(admins_list) + "\n\n"
    text += "<b>Участники 🏷️</b>\n" + "\n".join(members_list)

    if len(text) > 4000: text = text[:4000] + "\n\n...и другие"
    await message.reply(text, disable_web_page_preview=True)

# 2. МОЯ СТАТЬЯ С АНТИ-ПОВТОРОМ
@dp.message(Command("моястатья"))
@dp.message(F.text.lower() == "моя статья")
async def my_article(message: types.Message):
    user_id = message.from_user.id
    if user_id not in used_articles: used_articles[user_id] = []

    available = [a for i, a in enumerate(ARTICLES) if used_articles[user_id].count(i) < 3]
    if not available:
        used_articles[user_id] = []
        available = ARTICLES

    choice = random.choice(available)
    index = ARTICLES.index(choice)
    used_articles[user_id].append(index)

    article = choice.format(user=get_user_link(message.from_user))
    await message.reply(article, disable_web_page_preview=True)

# 3. АДМИН КОМАНДЫ
@dp.message(Command("kick"))
async def kick(message: types.Message):
    if not await is_admin(message): return
    if not message.reply_to_message: return await message.reply("Ответь на сообщение того кого кикнуть")
    await bot.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
    await bot.unban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
    await message.reply(f"{get_user_link(message.reply_to_message.from_user)} был кикнут")

@dp.message(Command("ban"))
async def ban(message: types.Message):
    if not await is_admin(message): return
    if not message.reply_to_message: return await message.reply("Ответь на сообщение")
    await bot.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
    await message.reply(f"{get_user_link(message.reply_to_message.from_user)} забанен навсегда")

@dp.message(Command("mute"))
async def mute(message: types.Message, command: CommandObject):
    if not await is_admin(message): return
    if not message.reply_to_message or not command.args: return await message.reply("Пример: /mute 10m")
    time_str = command.args
    unit, val = time_str[-1], int(time_str[:-1])
    delta = timedelta(minutes=val) if unit=='m' else timedelta(hours=val) if unit=='h' else timedelta(days=val) if unit=='d' else timedelta(seconds=val)
    until = datetime.now() + delta
    await bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id, until_date=until)
    await message.reply(f"{get_user_link(message.reply_to_message.from_user)} в муте на {time_str}")

@dp.message(Command("warn"))
async def warn(message: types.Message):
    if not await is_admin(message): return
    if not message.reply_to_message: return await message.reply("Ответь на сообщение")

    user_id = message.reply_to_message.from_user.id
    chat_id = message.chat.id

    async with db_pool.acquire() as conn:
        res = await conn.fetchrow("SELECT count FROM warns WHERE user_id=$1 AND chat_id=$2", user_id, chat_id)
        count = 1 if not res else res['count'] + 1
        await conn.execute("INSERT INTO warns(user_id, chat_id, count) VALUES($1,$2,$3) ON CONFLICT (user_id, chat_id) DO UPDATE SET count=$3", user_id, chat_id, count)

    await message.reply(f"{get_user_link(message.reply_to_message.from_user)} получил варн {count}/3")

    if count >= 3:
        await bot.ban_chat_member(chat_id, user_id)
        await message.reply(f"{get_user_link(message.reply_to_message.from_user)} забанен за 3 варна")

# 4. АВТОБАН ЗА ВЫХОД
@dp.chat_member()
async def on_member_update(update: ChatMemberUpdated):
    old_status = update.old_chat_member.status
    new_status = update.new_chat_member.status
    user = update.new_chat_member.user
    chat_id = update.chat.id

    if old_status in ["member", "administrator"] and new_status == "left":
        async with db_pool.acquire() as conn:
            await conn.execute("INSERT INTO banned_on_exit(user_id, chat_id) VALUES($1,$2) ON CONFLICT DO NOTHING", user.id, chat_id)

    if old_status == "left" and new_status in ["member"]:
        async with db_pool.acquire() as conn:
            res = await conn.fetchrow("SELECT * FROM banned_on_exit WHERE user_id=$1 AND chat_id=$2", user.id, chat_id)
            if res:
                await bot.ban_chat_member(chat_id, user.id)
                await bot.send_message(chat_id, f"{get_user_link(user)} покинул нас и получил постоянную блокировку навсегда.")

# ===== ЗАПУСК + БД =====
async def create_db():
    global db_pool
    db_pool = await asyncpg.create_pool(dsn=DATABASE_URL)
    async with db_pool.acquire() as conn:
        await conn.execute("CREATE TABLE IF NOT EXISTS warns (user_id BIGINT, chat_id BIGINT, count INT, PRIMARY KEY(user_id, chat_id))")
        await conn.execute("CREATE TABLE IF NOT EXISTS banned_on_exit (user_id BIGINT, chat_id BIGINT, PRIMARY KEY(user_id, chat_id))")
    print("БД подключена")

async def main():
    await create_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
