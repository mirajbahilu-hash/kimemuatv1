# bot.py
import os
import json
import datetime
import logging
from pathlib import Path
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.query import Query

# ------------------------------------------------------------------
#  Configuration & logging
# ------------------------------------------------------------------
load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN          = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME   = os.getenv("CHANNEL_USERNAME")
DB_CHANNEL_USERNAME= os.getenv("DB_MAIN_CHANNEL_USERNAME")  # kept for forwarder

# ------------ Appwrite ------------
APPWRITE_ENDPOINT  = os.getenv("APPWRITE_ENDPOINT", "https://cloud.appwrite.io/v1")
APPWRITE_PROJECT   = os.getenv("APPWRITE_PROJECT_ID")
APPWRITE_KEY       = os.getenv("APPWRITE_API_KEY")
APPWRITE_DB        = os.getenv("APPWRITE_DATABASE_ID")
APPWRITE_COLL      = os.getenv("APPWRITE_COLLECTION_ID")

_appwrite_client = Client()
_appwrite_client.set_endpoint(APPWRITE_ENDPOINT)
_appwrite_client.set_project(APPWRITE_PROJECT)
_appwrite_client.set_key(APPWRITE_KEY)
_appwrite_db = Databases(_appwrite_client)

# ------------------------------------------------------------------
#  Appwrite helpers
# ------------------------------------------------------------------
async def get_user_doc(uid: int) -> dict | None:
    try:
        res = await _appwrite_db.list_documents(
            database_id=APPWRITE_DB,
            collection_id=APPWRITE_COLL,
            queries=[Query.equal("user_id", str(uid))]
        )
        if res["total"]:
            return res["documents"][0]
        return None
    except Exception as e:
        logger.error("get_user_doc error: %s", e)
        return None

async def create_user_doc(user, referrer_id: int | None) -> dict:
    doc = {
        "user_id":        str(user.id),
        "first_name":     user.first_name,
        "username":       user.username or "",
        "start_date":     str(datetime.datetime.utcnow()),
        "referral_link":  f"https://t.me/kimemuatbot?start={user.id}",
        "kimem_coins":    "0",
        "invited":        json.dumps([])
    }
    try:
        created = await _appwrite_db.create_document(
            database_id=APPWRITE_DB,
            collection_id=APPWRITE_COLL,
            document_id=str(user.id),
            data=doc
        )
        if referrer_id and referrer_id != user.id:
            await _credit_referrer(str(referrer_id), user)
        return created
    except Exception as e:
        logger.error("create_user_doc error: %s", e)
        return doc

async def _credit_referrer(referrer_uid: str, invitee_user):
    try:
        ref_doc = await get_user_doc(int(referrer_uid))
        if not ref_doc:
            return
        coins = int(ref_doc["kimem_coins"]) + 10
        invited = json.loads(ref_doc["invited"])
        invited.append({
            "user_id": invitee_user.id,
            "name":    invitee_user.full_name,
            "date":    str(datetime.datetime.utcnow())
        })
        await _appwrite_db.update_document(
            database_id=APPWRITE_DB,
            collection_id=APPWRITE_COLL,
            document_id=referrer_uid,
            data={"kimem_coins": str(coins), "invited": json.dumps(invited)}
        )
    except Exception as e:
        logger.error("_credit_referrer error: %s", e)

async def ensure_user(user: Update.effective_user, referrer_id: int | None = None) -> dict:
    uid = user.id
    doc = await get_user_doc(uid)
    if doc:
        return doc
    return await create_user_doc(user, referrer_id)

# ------------------------------------------------------------------
#  Existing forward maps (unchanged)
# ------------------------------------------------------------------
FORWARD_MAP = {
    "🎯 Kimem Short Notes": ("MAIN", 7),
    "🌐 Websites": ("MAIN", 104),
    "📖 UAT Overview": ("MAIN", 201),
    "❓ Frequently Asked": ("MAIN", 202),
    "🏫 AAU Overview": ("MAIN", 301),
    "🏢 AAU Departments": ("MAIN", 302),
    "📍 AAU Campuses": ("MAIN", 303),
    "🎒 Life In AAU": ("MAIN", 304),
    "🎓 AAU After Graduation": ("MAIN", 305),
    "🌐AAU Websites": ("MAIN", 306),
    "🏫 ASTU Overview": ("MAIN", 311),
    "🏢 ASTU Departments": ("MAIN", 312),
    "📍 ASTU Campuses": ("MAIN", 313),
    "🎒 Life In ASTU": ("MAIN", 314),
    "🎓 ASTU After Graduation": ("MAIN", 315),
    "🌐ASTU Websites": ("MAIN", 316),
    "🏫 AASTU Overview": ("MAIN", 321),
    "🏢 AASTU Departments": ("MAIN", 322),
    "📍 AASTU Campuses": ("MAIN", 323),
    "🎒 Life In AASTU": ("MAIN", 324),
    "🎓 AASTU After Graduation": ("MAIN", 325),
    "🌐AASTU Websites": ("MAIN", 326),
    "🏥 SPHMMC Overview": ("MAIN", 331),
    "🏢 SPHMMC Departments": ("MAIN", 332),
    "📍 SPHMMC Campuses": ("MAIN", 333),
    "🎒 Life In SPHMMC": ("MAIN", 334),
    "🎓 SPHMMC After Graduation": ("MAIN", 335),
    "🌐SPHMMC Websites": ("MAIN", 336),
    "🏫 Bahiradar University": ("OTHERS", 401),
    "🏫 Haramaya University": ("OTHERS", 402),
    "🏫 Jimma University": ("OTHERS", 403),
    "📘 AAU Last Year UAT": ("MAIN", 501),
    "📖 AAU Model UAT": ("MAIN", 502),
    "📚 AAU UAT Overview": ("MAIN", 503),
    "❓ AAU UAT FAQ": ("MAIN", 504),
    "📝 How to Prepare For AAU": ("MAIN", 505),
    "📘 ASTU Last Year UAT": ("MAIN", 511),
    "📖 ASTU Model UAT": ("MAIN", 512),
    "📚 ASTU UAT Overview": ("MAIN", 513),
    "❓ ASTU UAT FAQ": ("MAIN", 514),
    "📝 How to Prepare For ASTU": ("MAIN", 515),
    "📘 AASTU Last Year UAT": ("MAIN", 521),
    "📖 AASTU Model UAT": ("MAIN", 522),
    "📚 AASTU UAT Overview": ("MAIN", 523),
    "❓ AASTU UAT FAQ": ("MAIN", 524),
    "📝 How to Prepare For AASTU": ("MAIN", 525),
    "📘 SPHMMC Last Year Exam": ("MAIN", 531),
    "📖 SPHMMC Model Exam": ("MAIN", 532),
    "📚 SPHMMC Exam Overview": ("MAIN", 533),
    "❓ SPHMMC Exam FAQ": ("MAIN", 534),
    "📝 How to Prepare For SPHMMC": ("MAIN", 535),
}

MULTI_FORWARD_MAP = {
    "📘 Text Books": [("MAIN", 10), ("MAIN", 13), ("BOOKS", 11)],
}

PATTERN_BACK = "^⬅ Back$"

# ------------------------------------------------------------------
#  Helper utilities
# ------------------------------------------------------------------
def set_user_state(context: ContextTypes.DEFAULT_TYPE, menu: str):
    context.user_data["prev_menu"] = menu

# ------------------------------------------------------------------
#  Start / Intro flow
# ------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    referrer_id = None
    if context.args and context.args[0].isdigit():
        referrer_id = int(context.args[0])

    user_data = await ensure_user(user, referrer_id)

    if referrer_id is None and user_data.get("has_seen_intro"):
        await update.message.reply_text(f"Welcome back, {user.first_name}! 👋")
        await send_home_menu(update, context)
        return

    # Mark intro shown
    try:
        await _appwrite_db.update_document(
            database_id=APPWRITE_DB,
            collection_id=APPWRITE_COLL,
            document_id=str(user.id),
            data={"has_seen_intro": True}
        )
    except Exception as e:
        logger.error("update has_seen_intro error: %s", e)

    keyboard = [[InlineKeyboardButton("Okay Continue.", callback_data="continue")]]
    with open("img/cover.png", "rb") as image:
        await update.message.reply_photo(
            photo=image,
            caption="Welcome to Kimem UAT your gateway to AAU, ASTU, AASTU and SPHMMC",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def continue_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()

    username = query.from_user.username or query.from_user.first_name
    keyboard = [
        [InlineKeyboardButton("Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.strip('@')}")],
        [InlineKeyboardButton("Confirm Join", callback_data="check_join")]
    ]
    with open("img/cover.png", "rb") as image:
        await query.message.chat.send_photo(
            photo=image,
            caption=f"Hey There '{username}' Welcome to Kimem UAT, We are here to guide you through the UAT journey for free. Please join the following channel First.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def check_join_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            await query.message.delete()
            await send_home_menu(update, context)
        else:
            await query.message.reply_text("❌ You haven't joined the channel yet.")
    except Exception as e:
        logger.error("Error checking membership: %s", e)
        await query.message.reply_text("⚠️ Could not verify your channel join. Please try again later.")

# ------------------------------------------------------------------
#  Menu helpers
# ------------------------------------------------------------------
async def send_home_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    home_keyboard = [
        ["💰 Referral","📚 UAT Preparation"],
        ["🗂️ Resources", "🏛️ About AAU"],
        ["🏫 About ASTU", "🏫 About AASTU", "🏥 About SPHMMC"],
        ["🎓 Other Universities", "ℹ️ About Kimem UAT"]
    ]
    reply_markup = ReplyKeyboardMarkup(home_keyboard, resize_keyboard=True)
    target = update.callback_query or update.message
    await target.reply_text(
        "🏠 You are back home. Use the options below:",
        reply_markup=reply_markup
    )

# ------------------------------------------------------------------
#  Referral section
# ------------------------------------------------------------------
async def referral_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_doc = await ensure_user(user)

    invited_count = len(json.loads(user_doc["invited"]))
    coins = int(user_doc["kimem_coins"])
    link = user_doc["referral_link"]

    caption = (
        f"Hello {user.first_name};\n"
        f"--------------------------------\n"
        f"You have invited: {invited_count} people\n"
        f"You have: {coins} Kimem Coins\n"
        f"----------------------------------\n"
        f"Your invite link:\n{link}\n"
        f"---------------------------------------\n"
        f"Get 10 Coins per person you invite\n"
        f"Collect Kimem Coins and get my paid Telegram Bot and Website Development Courses for free. "
        f"The coins will be listed after the UAT exam."
    )

    keyboard = [
        [InlineKeyboardButton("Your invites", callback_data="show_invites")],
        [InlineKeyboardButton("Developer's Channel", url="https://t.me/yosdevhub")],
    ]
    with open("img/referral.png", "rb") as img:
        await update.message.reply_photo(
            photo=img,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

async def show_invites_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    user_doc = await get_user_doc(user_id)
    invited = json.loads(user_doc["invited"]) if user_doc else []

    if not invited:
        text = "You haven't invited anyone yet."
    else:
        lines = [f"📋 Invites list ({len(invited)} total):"]
        for inv in invited:
            lines.append(f"• {inv['name']} – {inv['date'][:10]}")
        text = "\n".join(lines)

    keyboard = [[InlineKeyboardButton("⬅ Go Back", callback_data="referral_back")]]
    try:
        await query.message.edit_caption(caption=text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error("Failed to edit caption: %s", e)
        await query.message.reply_text(text)

async def referral_back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    user_doc = await get_user_doc(user.id)

    invited_count = len(json.loads(user_doc["invited"]))
    coins = int(user_doc["kimem_coins"])
    link = user_doc["referral_link"]

    caption = (
        f"Hello {user.first_name};\n"
        f"--------------------------------\n"
        f"You have invited: {invited_count} people\n"
        f"You have: {coins} Kimem Coins\n"
        f"----------------------------------\n"
        f"Your invite link:\n{link}\n"
        f"---------------------------------------\n"
        f"Get 10 Coins per person you invite\n"
        f"Collect Kimem Coins and get my paid Telegram Bot and Website Development Courses for free. "
        f"The coins will be listed after the UAT exam."
    )

    keyboard = [
        [InlineKeyboardButton("Your invites", callback_data="show_invites")],
        [InlineKeyboardButton("Developer's Channel", url="https://t.me/yosdevhub")],
    ]
    try:
        await query.message.edit_caption(caption=caption, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error("Failed to go back to referral screen: %s", e)
        await query.message.reply_text(caption)

# ------------------------------------------------------------------
#  Generic menu handlers
# ------------------------------------------------------------------
async def uat_preparation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_state(context, "HOME")
    keyboard = [
        ["❓ What is UAT?", "🏛 AAU UAT"],
        ["🏫 AASTU & ASTU UAT", "🏥 SPHMMC Entrance"],
        ["⬅ Back", "🏠Home"]
    ]
    await update.message.reply_text(
        "📘 UAT Preparation Section\nChoose the university or topic you want to explore:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def resources_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_state(context, "HOME")
    keyboard = [
        ["🎯 Kimem Short Notes","📘 Text Books"],
        ["📚 SAT Collection","🌐 Websites"],
        ["⬅ Back", "🏠Home"]
    ]
    await update.message.reply_text(
        "🗂️ Resources Section:\nSelect a category to explore useful learning materials.",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def about_university_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, university: str):
    set_user_state(context, "HOME")
    keyboard = [
        [f"🏫 {university} Overview", f"🏢 {university} Departments"],
        [f"📍 {university} Campuses", f"🎒 Life In {university}"],
        [f"🎓 {university} After Graduation", f"🌐{university} Websites"],
        ["⬅ Back", "🏠Home"]
    ]
    await update.message.reply_text(
        f"🏛️ About {university} Section:\nSelect an option to learn more.",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def other_universities_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_state(context, "HOME")
    keyboard = [
        ["🏫 Bahiradar University"],
        ["🏫 Haramaya University"],
        ["🏫 Jimma University"],
        ["⬅ Back", "🏠Home"]
    ]
    await update.message.reply_text(
        "🎓 Other Universities Section:\nSelect a university to learn more.",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def about_kimem_uat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_channel = DB_CHANNEL_USERNAME
    if not db_channel:
        await update.message.reply_text("⚠️ Channel not configured.")
        return
    try:
        await context.bot.copy_message(
            chat_id=update.effective_chat.id,
            from_chat_id=db_channel,
            message_id=6
        )
    except Exception as e:
        logger.error("Error copying message: %s", e)
        await update.message.reply_text("⚠️ Could not retrieve info. Please try again later.")

# ------------------------------------------------------------------
#  UAT sub-menu handlers
# ------------------------------------------------------------------
async def uat_university_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, university: str):
    set_user_state(context, "UAT_PREPARATION")
    keyboard = [
        [f"📘 {university} Last Year UAT", f"📖 {university} Model UAT"],
        [f"📚 {university} UAT Overview", f"❓ {university} UAT FAQ"],
        [f"📝 How to Prepare For {university}"],
        ["⬅ Back", "🏠Home"]
    ]
    await update.message.reply_text(
        f"🏛 {university} UAT Section:\nChoose an option to explore:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def what_is_uat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_state(context, "UAT_PREPARATION")
    kb = [
        ["📖 UAT Overview"],
        ["❓ Frequently Asked"],
        ["⬅ Back", "🏠Home"]
    ]
    await update.message.reply_text(
        "Choose an option to learn about UAT:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

async def aastu_astu_uat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_state(context, "UAT_PREPARATION")
    keyboard = [
        ["📘 AASTU & ASTU Last Year UAT", "📖 AASTU & ASTU Model UAT"],
        ["📚 AASTU & ASTU UAT Overview","❓ AASTU & ASTU UAT FAQ"],
        ["📝 How to Prepare For AASTU & ASTU"],
        ["⬅ Back", "🏠Home"]
    ]
    await update.message.reply_text(
        "🏫 AASTU & ASTU UAT Section:\nChoose an option to explore:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def sphmmc_entrance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_state(context, "UAT_PREPARATION")
    keyboard = [
        ["📘 SPHMMC Last Year Exam", "📖 SPHMMC Model Exam"],
        ["📚 SPHMMC Exam Overview", "❓ SPHMMC Exam FAQ"],
        ["📝 How to Prepare For SPHMMC"],
        ["⬅ Back", "🏠Home"]
    ]
    await update.message.reply_text(
        "🏥 SPHMMC Entrance Section:\nChoose an option to explore:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def universal_back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prev = context.user_data.get("prev_menu")
    if prev == "HOME":
        await send_home_menu(update, context)
    elif prev == "UAT_PREPARATION":
        await uat_preparation_handler(update, context)
    else:
        await send_home_menu(update, context)

# ------------------------------------------------------------------
#  Forward-map generators (unchanged except async)
# ------------------------------------------------------------------
def make_forwarder(channel_key: str, msg_id: int):
    env_key = f"DB_{channel_key}_CHANNEL_USERNAME"
    channel = os.getenv(env_key)
    if not channel:
        logger.warning("Env var %s not set – skipping some handlers", env_key)
        return None

    async def _handler(update: Update, _: ContextTypes.DEFAULT_TYPE):
        try:
            await update.get_bot().copy_message(
                chat_id=update.effective_chat.id,
                from_chat_id=channel,
                message_id=msg_id
            )
        except Exception as e:
            logger.error("Error forwarding %s/%s: %s", channel_key, msg_id, e)
            await update.message.reply_text("⚠️ Could not retrieve info.")
    return _handler

def make_multi_forwarder(entries):
    channels = {}
    for key, _ in entries:
        env_key = f"DB_{key}_CHANNEL_USERNAME"
        channels[key] = os.getenv(env_key)
        if channels[key] is None:
            logger.warning("Missing env var %s – skipped multi-forward", env_key)
            return None

    async def _handler(update: Update, _: ContextTypes.DEFAULT_TYPE):
        try:
            for key, msg_id in entries:
                await update.get_bot().copy_message(
                    chat_id=update.effective_chat.id,
                    from_chat_id=channels[key],
                    message_id=msg_id
                )
        except Exception as e:
            logger.error("Multi-forward failed: %s", e)
            await update.message.reply_text("⚠️ Could not retrieve info.")
    return _handler

# ------------------------------------------------------------------
#  Main entry-point
# ------------------------------------------------------------------
def main():
    if not BOT_TOKEN or not CHANNEL_USERNAME:
        logger.error("Missing .env values. BOT_TOKEN and CHANNEL_USERNAME are required.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Command & callback handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(continue_handler, pattern="^continue$"))
    app.add_handler(CallbackQueryHandler(check_join_handler, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(show_invites_handler, pattern="^show_invites$"))
    app.add_handler(CallbackQueryHandler(referral_back_handler, pattern="^referral_back$"))

    # Text message handlers
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^📚 UAT Preparation$"), uat_preparation_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🏠Home$"), send_home_menu))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🗂️ Resources$"), resources_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^💰 Referral$"), referral_handler))

    # University about handlers
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🏛️ About AAU$"), lambda u, c: about_university_handler(u, c, "AAU")))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🏫 About ASTU$"), lambda u, c: about_university_handler(u, c, "ASTU")))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🏫 About AASTU$"), lambda u, c: about_university_handler(u, c, "AASTU")))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🏥 About SPHMMC$"), lambda u, c: about_university_handler(u, c, "SPHMMC")))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🎓 Other Universities$"), other_universities_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^ℹ️ About Kimem UAT$"), about_kimem_uat_handler))

    # UAT preparation handlers
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^❓ What is UAT\?$"), what_is_uat_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🏛 AAU UAT$"), lambda u, c: uat_university_handler(u, c, "AAU")))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🏛 ASTU UAT$"), lambda u, c: uat_university_handler(u, c, "ASTU")))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🏛 AASTU UAT$"), lambda u, c: uat_university_handler(u, c, "AASTU")))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🏫 AASTU & ASTU UAT$"), aastu_astu_uat_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🏥 SPHMMC Entrance$"), sphmmc_entrance_handler))

    # Back handler
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(PATTERN_BACK), universal_back_handler))

    # Register forward-map handlers
    for text, (key, mid) in FORWARD_MAP.items():
        handler_fn = make_forwarder(key, mid)
        if handler_fn:
            app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{text}$"), handler_fn))

    for button_text, entries in MULTI_FORWARD_MAP.items():
        handler_fn = make_multi_forwarder(entries)
        if handler_fn:
            app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{button_text}$"), handler_fn))

    logger.info("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()