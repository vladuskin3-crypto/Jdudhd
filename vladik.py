import asyncio
import hashlib
import html
import logging
import os
import random
import re
import sqlite3
import time
from datetime import date

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8778580583:AAHUjcjXlgQZt19Rb3w79YR0Q1iF0MDmXl0")
CHIME_CHANCE = float(os.getenv("CHIME_CHANCE", "0.04"))  # шанс, что Владик сам вставит реплику
CHIME_COOLDOWN = 120  # секунд между самопроизвольными репликами в одном чате
BOT_NAME = "Владик"

# ---------------------------------------------------------------- БАЗА
db = sqlite3.connect("vladik.db")
db.execute(
    """CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER, user_id INTEGER, name TEXT,
        msgs INTEGER DEFAULT 0, quiz INTEGER DEFAULT 0,
        PRIMARY KEY (chat_id, user_id))"""
)
db.commit()


def esc(s: str) -> str:
    return html.escape(s or "")


def mention(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{esc(name)}</a>'


# ---------------------------------------------------------------- КОНТЕНТ
HOW_ARE_YOU = [
    "Отлично! Только что победил в споре с холодильником 🧊",
    "Как дела? Как у голубя на площади — крошек много, настроение хорошее 🐦",
    "Бодр, весел и слегка перекормлен чатом 😎",
    "Дела идут, а я за ними бегу 🏃",
    "Пока вы писали, я успел заскучать. Теперь всё супер!",
    "Лучше всех! А у тебя как? Только честно 👀",
    "Зарядка 100%, настроение 146%, сарказм в норме 🔋",
    "Жив, здоров и готов к приключениям. Ну, или хотя бы к печеньке 🍪",
    "Как в сказке: чем дальше, тем страннее 🎠",
]
WHAT_DOING = [
    "Читаю ваш чат и делаю умный вид 🧐",
    "Тренируюсь быть душой компании. Пока получается плохо, но громко.",
    "Охраняю чат от тишины 🛡",
    "Выдумываю, чем бы вас развлечь. Спойлер: мемами и вопросами.",
    "Сижу в телефоне. Ой, я и есть в телефоне 📱",
    "Считаю, кто сегодня больше всех писал. Результаты — в /top 📊",
    "Учусь у вас плохому. Получается отлично 😈",
    "Притворяюсь, что работаю. Начальство не видит? Отлично!",
    "Медитирую на ваши сообщения. Это дзен. Или шум. Пока не понял 🧘",
]
WHO_ARE_YOU = [
    "Я Владик — маленький, шустрый и очень любопытный бот. Умею шутить, играть и допрашивать 😄 Список: /help",
    "Владик, местный весельчак. Без меня в чате слишком тихо! /help — мои умения.",
]
GREET = [
    "Привет-привет! 👋",
    "О, живой человек! Здарова 😄",
    "Приветствую! Чего расскажешь?",
    "Ку-ку! Я тут, не сплю.",
]
THANKS = ["Обращайся! 😉", "Всегда пожалуйста!", "Да не за что, я же душа компании 😎"]
BORED = [
    "Скучно? Сейчас исправим! Держи вопрос:",
    "Скука — враг чата. Включаю режим развлечений:",
]
GENERIC = [
    "Хм, интересно… продолжай 🤔",
    "Ого! А подробнее?",
    "Я это запомню и использую против тебя. Шучу. Или нет 😏",
    "Согласен на 63%.",
    "Не знаю, что ответить, но звучит громко.",
    "А вот тут спорно! Кто со мной?",
    "Секунду, записываю в блокнотик 📝",
    "Мудро. Глупо, но мудро.",
    "Это было сильно. Я аж чипсы уронил 🥔",
    "Ты сейчас сказал(а) это серьёзно? Потому что я записываю 🎙",
    "Принято к сведению и отправлено в архив «Потом разберёмся» 🗄",
    "Звучит как начало отличной истории. Или хорошей ссоры 😄",
    "Я бы поспорил, но мне лень. И ты, скорее всего, прав(а).",
]
CHIMES = [
    "Подслушал вас и не удержался: а вы точно знаете, о чём говорите? 😄",
    "*тихо ест попкорн* 🍿",
    "Я тут, если что. Просто наблюдаю.",
    "Так, а кто сегодня платит за чат? 😅",
    "Чувствую, назревает интересный спор. Продолжайте!",
    "Ваш чат — моя любимая передача 📺",
    "Тишина в чате? Подозрительно… Кто-то что-то замышляет 🕵️",
    "Напоминаю: пить воду, держать спину ровно и не ссориться из-за мелочей 💧",
    "Я не вмешиваюсь, я просто слежу, чтобы всё было красиво 🎭",
]
JOKES = [
    "— Почему программисты путают Хэллоуин и Рождество?\n— Потому что 31 Oct = 25 Dec 🎃",
    "Купил будильник «для ленивых». Он сам встаёт и сам идёт на работу. Я просто сплю дальше.",
    "— Доктор, у меня провалы в памяти.\n— И давно?\n— Что давно?",
    "Если долго смотреть в холодильник, он начнёт смотреть на тебя с укором.",
    "Wi-Fi — единственная вещь, в которую я верю, хотя её не вижу.",
    "Я не ленивый, я в режиме энергосбережения 🔋",
    "Говорят, деньги не пахнут. Но почему-то всегда пахнут пиццей, которой уже нет.",
    "Кот упал со шкафа и сделал вид, что так и планировал. Учитесь!",
]
FACTS = [
    "У осьминога три сердца 🐙",
    "Мёд практически не портится — его находили съедобным в древних гробницах 🍯",
    "Бананы с точки зрения ботаники — ягоды, а клубника — нет 🍌",
    "Улитка может спать до трёх лет 🐌",
    "Молния нагревает воздух сильнее, чем поверхность Солнца ⚡",
    "Коровы имеют лучших друзей и грустят в разлуке 🐄",
    "Вомбаты делают кубические какашки. Серьёзно 🟫",
]
QUESTIONS = [
    "Какой суперсилой вы бы выбрали обладать на один день?",
    "Что бы вы сделали, если бы выиграли миллион прямо сейчас?",
    "Самый нелепый случай в вашей жизни — рассказывайте!",
    "Какое блюдо вы бы ели каждый день, если бы вес не менялся?",
    "С каким персонажем из кино вы бы поменялись местами?",
    "Какая ваша самая странная привычка?",
    "Куда бы вы поехали прямо сейчас, если бы билеты были бесплатные?",
    "Какой навык вы хотели бы освоить за неделю?",
    "Кошки или собаки? Аргументируйте, иначе не засчитано 😼🐶",
    "Утро или ночь? Кто вы по жизни: сова или жаворонок?",
]
TRUTHS = [
    "Какую самую неловкую вещь ты делал(а) на людях?",
    "О чём ты чаще всего врёшь?",
    "Кому в этом чате ты бы доверил(а) секрет?",
    "Какой твой самый странный страх?",
    "Что ты делал(а) последним перед сном и стыдно ли тебе?",
]
DARES = [
    "Напиши в чат сообщение, используя только эмодзи, чтобы все угадали фразу.",
    "Поставь на аватарку смешное фото на час.",
    "Придумай и расскажи шутку про того, кто писал последним.",
    "Отправь голосовое и спой припев любой песни.",
    "Напиши комплимент каждому, кто сейчас онлайн.",
]
BALL = [
    "Бесспорно ✅", "Да, 100% 👍", "Скорее да", "Знаки говорят — да",
    "Туманно, спроси позже 🌫", "Лучше не рассказывать 🤐", "Сомнительно",
    "Даже не думай ❌", "Мой ответ — нет", "Шансы мизерные",
]
COMPLIMENTS = [
    "ты как Wi-Fi в метро — редкость и радость 📶",
    "с тобой в чате веселее на 40%",
    "у тебя идеальное чувство юмора. Ну, почти.",
    "ты тот человек, ради которого стоит не отключать уведомления",
    "ты умнее, чем думаешь. И забавнее, чем признаёшь.",
]
ROASTS = [
    "пишешь так быстро, что мысли не успевают за пальцами 😄",
    "ты как понедельник — все тебя ждут с тревогой, но любят",
    "если бы лень была спортом, у тебя был бы пьедестал 🏆",
    "у тебя талант: сказать «ща» и пропасть на три часа",
]
HOROSCOPE = [
    "Сегодня звёзды советуют не спорить с холодильником 🌟",
    "День удачи на мелочи: найдёшь монетку или хорошее настроение.",
    "Осторожнее с обещаниями — вечером придётся выполнять.",
    "Ждёт приятная новость. Или хотя бы вкусный перекус 🍕",
    "Тебя оценит тот, от кого не ждёшь. Не прячься!",
    "Лучше день провести в кругу друзей, а не в вечном скролле.",
]
QUIZ = [
    ("Какая планета ближе всего к Солнцу?", ["Венера", "Меркурий", "Марс", "Земля"], 1),
    ("Сколько будет 7 × 8?", ["54", "56", "64", "48"], 1),
    ("Столица Японии?", ["Киото", "Осака", "Токио", "Нагоя"], 2),
    ("Какой океан самый большой?", ["Атлантический", "Индийский", "Тихий", "Северный Ледовитый"], 2),
    ("Сколько ног у паука?", ["6", "8", "10", "12"], 1),
    ("Какой газ мы вдыхаем для жизни?", ["Азот", "Углекислый газ", "Кислород", "Гелий"], 2),
    ("Кто написал «Войну и мир»?", ["Достоевский", "Толстой", "Чехов", "Пушкин"], 1),
    ("Самое высокое животное на Земле?", ["Слон", "Жираф", "Верблюд", "Лось"], 1),
    ("Сколько цветов в радуге?", ["5", "6", "7", "8"], 2),
    ("Как называется самая длинная река в России?", ["Волга", "Лена", "Обь", "Енисей"], 2),
]
WELCOME = [
    "Ооо, новенький! Добро пожаловать, {name}! Представься и расскажи, чем живёшь 😄",
    "{name}, привет! Владик на связи. Правила простые: веселимся и не скучаем 🎉",
    "Свежая кровь в чате! {name}, с тебя шутка 😏",
]

HELP_TEXT = f"""<b>Я — {BOT_NAME}!</b> Душа вашей компании 😎

<b>Болтаю:</b> просто позови меня по имени — «Владик, как дела?», «что делаешь?», «привет», «кто ты?»

<b>Команды:</b>
/joke — шутка
/fact — интересный факт
/question — вопрос для обсуждения
/truth — вопрос «правда»
/dare — задание «действие»
/ball вопрос — шар предсказаний
/choose а, б, в — выбрать за вас
/who кто ... — выберу случайного участника
/rate что-то — оценю от 0 до 10
/compat — ответом на сообщение: совместимость
/horoscope — гороскоп на день
/compliment и /roast — комплимент или лёгкая подколка (ответом на сообщение — для человека)
/dice — кубик, /coin — монетка
/quiz — викторина (кнопками)
/guess — угадай число от 1 до 100
/top — самые болтливые, /quiztop — лучшие знатоки
"""

# ---------------------------------------------------------------- СОСТОЯНИЕ
router = Router()
router.message.filter(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP, ChatType.PRIVATE}))
guess_games: dict[int, int] = {}
quiz_active: dict[tuple[int, int], int] = {}  # (chat_id, message_id) -> quiz index
last_chime: dict[int, float] = {}
BOT_USERNAME = ""
BOT_ID = 0


class TrackMiddleware(BaseMiddleware):
    """Запоминает участников и считает сообщения."""

    async def __call__(self, handler, event: Message, data):
        u = event.from_user
        if u and not u.is_bot and event.chat.type != ChatType.PRIVATE:
            db.execute(
                "INSERT INTO users (chat_id, user_id, name, msgs) VALUES (?, ?, ?, 1) "
                "ON CONFLICT(chat_id, user_id) DO UPDATE SET msgs = msgs + 1, name = excluded.name",
                (event.chat.id, u.id, u.full_name),
            )
            db.commit()
        return await handler(event, data)


def arg_of(message: Message) -> str:
    parts = (message.text or "").split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def target_of(message: Message):
    """Пользователь, на сообщение которого ответили (или сам автор)."""
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    return message.from_user


# ---------------------------------------------------------------- КОМАНДЫ
@router.message(Command("start", "help"))
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT)


@router.message(Command("joke"))
async def cmd_joke(message: Message):
    await message.answer(random.choice(JOKES))


@router.message(Command("fact"))
async def cmd_fact(message: Message):
    await message.answer("🧠 " + random.choice(FACTS))


@router.message(Command("question"))
async def cmd_question(message: Message):
    await message.answer("❓ " + random.choice(QUESTIONS))


@router.message(Command("truth"))
async def cmd_truth(message: Message):
    u = target_of(message)
    await message.answer(f"🫣 {mention(u.id, u.full_name)}, правда: {random.choice(TRUTHS)}")


@router.message(Command("dare"))
async def cmd_dare(message: Message):
    u = target_of(message)
    await message.answer(f"😈 {mention(u.id, u.full_name)}, действие: {random.choice(DARES)}")


@router.message(Command("ball"))
async def cmd_ball(message: Message):
    if not arg_of(message):
        await message.answer("Задай вопрос: /ball я стану миллионером?")
        return
    await message.answer(f"🔮 {random.choice(BALL)}")


@router.message(Command("choose"))
async def cmd_choose(message: Message):
    options = [o.strip() for o in re.split(r",|\sили\s", arg_of(message)) if o.strip()]
    if len(options) < 2:
        await message.answer("Дай варианты: /choose пицца, суши, шаурма")
        return
    await message.answer(f"🎯 Выбираю: <b>{esc(random.choice(options))}</b>")


@router.message(Command("who"))
async def cmd_who(message: Message):
    rows = db.execute("SELECT user_id, name FROM users WHERE chat_id=?", (message.chat.id,)).fetchall()
    if not rows:
        await message.answer("Я пока никого не знаю — пусть сначала пообщаются!")
        return
    uid, name = random.choice(rows)
    text = arg_of(message) or "самый загадочный"
    await message.answer(f"👉 Кто {esc(text)}? Конечно, {mention(uid, name)}!")


@router.message(Command("rate"))
async def cmd_rate(message: Message):
    thing = arg_of(message)
    if not thing and message.reply_to_message:
        thing = message.reply_to_message.text or "это"
    if not thing:
        await message.answer("Что оценить? /rate мою причёску")
        return
    score = int(hashlib.md5(thing.lower().encode()).hexdigest(), 16) % 11
    await message.answer(f"⭐ «{esc(thing[:80])}» — <b>{score}/10</b>")


@router.message(Command("compat"))
async def cmd_compat(message: Message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer("Ответь командой /compat на сообщение человека 💞")
        return
    a, b = message.from_user, message.reply_to_message.from_user
    key = "-".join(map(str, sorted([a.id, b.id])))
    pct = int(hashlib.md5(key.encode()).hexdigest(), 16) % 101
    await message.answer(f"💞 Совместимость {mention(a.id, a.full_name)} и {mention(b.id, b.full_name)}: <b>{pct}%</b>")


@router.message(Command("horoscope"))
async def cmd_horoscope(message: Message):
    seed = f"{message.from_user.id}{date.today()}"
    rnd = random.Random(seed)
    await message.answer(f"🔭 {rnd.choice(HOROSCOPE)}")


@router.message(Command("compliment"))
async def cmd_compliment(message: Message):
    u = target_of(message)
    await message.answer(f"💐 {mention(u.id, u.full_name)}, {random.choice(COMPLIMENTS)}")


@router.message(Command("roast"))
async def cmd_roast(message: Message):
    u = target_of(message)
    await message.answer(f"😏 {mention(u.id, u.full_name)}, {random.choice(ROASTS)} (любя!)")


@router.message(Command("dice"))
async def cmd_dice(message: Message):
    await message.answer_dice()


@router.message(Command("coin"))
async def cmd_coin(message: Message):
    await message.answer(random.choice(["🪙 Орёл!", "🪙 Решка!"]))


# ---------------------------------------------------------------- ВИКТОРИНА
@router.message(Command("quiz"))
async def cmd_quiz(message: Message):
    idx = random.randrange(len(QUIZ))
    question, answers, _ = QUIZ[idx]
    kb = InlineKeyboardBuilder()
    for i, a in enumerate(answers):
        kb.button(text=a, callback_data=f"quiz:{idx}:{i}")
    kb.adjust(2)
    sent = await message.answer(f"🎓 <b>Викторина!</b>\n{esc(question)}", reply_markup=kb.as_markup())
    quiz_active[(sent.chat.id, sent.message_id)] = idx


@router.callback_query(F.data.startswith("quiz:"))
async def quiz_answer(call: CallbackQuery):
    _, idx, choice = call.data.split(":")
    idx, choice = int(idx), int(choice)
    key = (call.message.chat.id, call.message.message_id)
    if key not in quiz_active:
        await call.answer("Этот вопрос уже разобран!", show_alert=True)
        return
    question, answers, correct = QUIZ[idx]
    if choice != correct:
        await call.answer("Мимо! Попробуй ещё 😜", show_alert=False)
        return
    del quiz_active[key]
    u = call.from_user
    db.execute(
        "INSERT INTO users (chat_id, user_id, name, quiz) VALUES (?, ?, ?, 1) "
        "ON CONFLICT(chat_id, user_id) DO UPDATE SET quiz = quiz + 1, name = excluded.name",
        (call.message.chat.id, u.id, u.full_name),
    )
    db.commit()
    await call.message.edit_text(
        f"🎓 {esc(question)}\n\n✅ Правильно: <b>{esc(answers[correct])}</b>\n🏆 Первым ответил {mention(u.id, u.full_name)}!"
    )
    await call.answer("Верно! 🎉")


# ---------------------------------------------------------------- УГАДАЙ ЧИСЛО
@router.message(Command("guess"))
async def cmd_guess(message: Message):
    guess_games[message.chat.id] = random.randint(1, 100)
    await message.answer("🔢 Загадал число от 1 до 100. Пишите числа в чат, кто угадает — тот молодец!")


# ---------------------------------------------------------------- ТОПЫ
@router.message(Command("top"))
async def cmd_top(message: Message):
    rows = db.execute(
        "SELECT user_id, name, msgs FROM users WHERE chat_id=? ORDER BY msgs DESC LIMIT 5", (message.chat.id,)
    ).fetchall()
    if not rows:
        await message.answer("Пока статистики нет. Пишите больше!")
        return
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lines = [f"{medals[i]} {mention(r[0], r[1])} — {r[2]} сообщ." for i, r in enumerate(rows)]
    await message.answer("📊 <b>Самые болтливые:</b>\n" + "\n".join(lines))


@router.message(Command("quiztop"))
async def cmd_quiztop(message: Message):
    rows = db.execute(
        "SELECT user_id, name, quiz FROM users WHERE chat_id=? AND quiz>0 ORDER BY quiz DESC LIMIT 5",
        (message.chat.id,),
    ).fetchall()
    if not rows:
        await message.answer("Никто ещё не отвечал на викторину. Запусти /quiz!")
        return
    lines = [f"{i + 1}. {mention(r[0], r[1])} — {r[2]} 🏆" for i, r in enumerate(rows)]
    await message.answer("🎓 <b>Лучшие знатоки:</b>\n" + "\n".join(lines))


# ---------------------------------------------------------------- НОВЫЕ УЧАСТНИКИ
@router.message(F.new_chat_members)
async def on_new_members(message: Message):
    for u in message.new_chat_members:
        if u.is_bot:
            continue
        await message.answer(random.choice(WELCOME).format(name=mention(u.id, u.full_name)))


# ---------------------------------------------------------------- БОЛТОВНЯ
def addressed_to_bot(message: Message) -> bool:
    text = (message.text or "").lower()
    # имя в любом падеже (Владик, Владика, Владиком), но не «Владикавказ»
    if re.search(r"\bвладик(а|у|ом|е)?\b", text) or (BOT_USERNAME and f"@{BOT_USERNAME.lower()}" in text):
        return True
    r = message.reply_to_message
    return bool(r and r.from_user and r.from_user.id == BOT_ID)  # ответ на сообщение самого бота


@router.message(F.text & ~F.text.startswith("/"))
async def on_text(message: Message):
    text = message.text.lower()
    chat_id = message.chat.id

    # игра «угадай число»
    if chat_id in guess_games and re.fullmatch(r"\d{1,6}", text.strip()):
        n, target = int(text.strip()), guess_games[chat_id]
        if n == target:
            del guess_games[chat_id]
            u = message.from_user
            await message.answer(f"🎉 {mention(u.id, u.full_name)} угадал! Это было {target}!")
        elif n < target:
            await message.reply("Больше ⬆️")
        else:
            await message.reply("Меньше ⬇️")
        return

    if addressed_to_bot(message) or message.chat.type == ChatType.PRIVATE:
        if re.search(r"как (твои |ваши )?дела|как жизнь|как сам\b|как ты( там)?[?!. ]*$", text):
            await message.reply(random.choice(HOW_ARE_YOU))
        elif re.search(r"что (ты )?делаешь|чем занят|чем занимаешься|что творишь", text):
            await message.reply(random.choice(WHAT_DOING))
        elif re.search(r"кто ты|что ты умеешь|что умеешь|ты кто", text):
            await message.reply(random.choice(WHO_ARE_YOU))
        elif re.search(r"\b(привет\w*|здаров\w*|хай|хеллоу|добр(ый|ое|ого)|здравствуй\w*)\b", text):
            await message.reply(random.choice(GREET))
        elif re.search(r"спасибо|благодарю|\bспс\b", text):
            await message.reply(random.choice(THANKS))
        elif re.search(r"скучно|скука|нечего делать", text):
            await message.reply(f"{random.choice(BORED)}\n\n❓ {random.choice(QUESTIONS)}")
        elif re.search(r"шутк|анекдот|рассмеши", text):
            await message.reply(random.choice(JOKES))
        elif "?" in text:
            await message.reply(f"🔮 {random.choice(BALL)}")
        else:
            await message.reply(random.choice(GENERIC))
        return

    # самопроизвольная реплика
    now = time.time()
    if random.random() < CHIME_CHANCE and now - last_chime.get(chat_id, 0) > CHIME_COOLDOWN:
        last_chime[chat_id] = now
        await message.answer(random.choice(CHIMES))


# ---------------------------------------------------------------- ЗАПУСК
async def main():
    global BOT_USERNAME, BOT_ID
    if not BOT_TOKEN:
        raise SystemExit("Укажите BOT_TOKEN в файле .env")
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await bot.me()
    BOT_USERNAME = me.username or ""
    BOT_ID = me.id
    dp = Dispatcher()
    dp.message.outer_middleware(TrackMiddleware())
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
