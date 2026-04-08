import os
import logging
import io
import asyncio
from dotenv import load_dotenv
from telegram.error import Forbidden
from telegram.constants import ChatAction
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, ReplyKeyboardMarkup, KeyboardButton
from keep_alive import keep_alive
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta

# Load Environment Variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_ID = os.getenv("ADMIN_ID")
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database Setup
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client.match_bot_db
users_collection = db.users
interactions_collection = db.interactions

NAME, GENDER, LOOKING_FOR, AGE, CITY, BIO, PHOTO = range(7)
EDIT_CHOICE, PARTIAL_TEXT, PARTIAL_PHOTO = range(7, 10)
ICEBREAKER_TEXT = 10 # <--- Direct Message (Icebreaker) အတွက် အသစ်

def get_main_menu():

    keyboard = [
        [KeyboardButton("🔍 Match Partner 💖")],
        [KeyboardButton("My Profile"), KeyboardButton("Who Liked You")],
        [KeyboardButton("Daily Coin"), KeyboardButton("Buy VIP / Coin")],
        [KeyboardButton("Invite Friends"), KeyboardButton("Profile Verify")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)

async def send_log(context: ContextTypes.DEFAULT_TYPE, message: str, photo_id: str = None):

    if LOG_CHANNEL_ID:
        try:
            # ဓာတ်ပုံ ID ပါလာရင် ဓာတ်ပုံပါ တွဲပို့မယ်
            if photo_id:
                await context.bot.send_photo(chat_id=LOG_CHANNEL_ID, photo=photo_id, caption=message, parse_mode="HTML")
            # ဓာတ်ပုံ မပါလာရင် စာသားပဲ ပို့မယ်
            else:
                await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=message, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Log Channel သို့ ပို့ရန် အဆင်မပြေပါ: {e}")

# ==========================================
# 1. Registration Flow
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    existing_user = await users_collection.find_one({"user_id": user_id})

    if existing_user and existing_user.get("is_banned"):
        await update.message.reply_text("🚫 သင့်အကောင့်သည် စည်းမျဉ်းချိုးဖောက်မှုများကြောင့် ပိတ်ပင်ခံထားရပါသည်။")
        return ConversationHandler.END

    # User အသစ်ဖြစ်မှသာ Referral ကို လက်ခံမည် (User အဟောင်းတွေ လိမ်နှိပ်လို့ မရအောင် ကာကွယ်ခြင်း)
    if not existing_user and context.args and context.args[0].startswith("ref_"):
        try:
            referrer_id = int(context.args[0].split("_")[1])
            if referrer_id != user_id: # ကိုယ့်ကိုယ်ကိုယ် ပြန် Invite လုပ်ခြင်းကို ကာကွယ်ခြင်း
                context.user_data['referrer_id'] = referrer_id
        except: pass

    if not update.message.from_user.username:
        await update.message.reply_text(
            "⚠️ သင့်အကောင့်မှာ Telegram Username မရှိသေးပါ။\n"
            "Match ဖြစ်တဲ့အခါ သင့်ကို ဆက်သွယ်နိုင်ရန် Settings > Username မှာ အရင်သွားရောက် သတ်မှတ်ပေးပါ။\n\n"
            "သတ်မှတ်ပြီးပါက /start ကို ပြန်နှိပ်ပါ။"
        )
        return ConversationHandler.END
        
    user_id = update.message.from_user.id
    existing_user = await users_collection.find_one({"user_id": user_id})
    
    if existing_user and existing_user.get("name"):
        # အကယ်၍ Profile ပြင်နေရင်း (is_editing: True) တန်းလန်းနဲ့ /start ပြန်နှိပ်မိရင် False ပြန်ပြောင်းပေးမည်
        if existing_user.get("is_editing"):
            await users_collection.update_one({"user_id": user_id}, {"$set": {"is_editing": False}})
            
        await update.message.reply_text(
            f"မင်္ဂလာပါ {existing_user['name']} ခင်ဗျာ။ အောက်ပါ Menu များမှ တစ်ဆင့် ရွေးချယ်အသုံးပြုနိုင်ပါတယ်။",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "Shwe Phusar (ရွှေဖူးစာ)မှကြိုဆိုပါတယ်။ 💖\n"
            "ဖူးစာရှင်ရှာဖွေနိုင်ရန် သင့်ရဲ့ Profile ကို အရင်တည်ဆောက်ပါ။\n\n"
            "Please, Your Name?"
        )
        return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text
    keyboard = [
        [InlineKeyboardButton("I'm Male/ကျား", callback_data="Male"), InlineKeyboardButton("I'm Female/မ", callback_data="Female")]
    ]
    await update.message.reply_text("Male? or Female? ကျား/မ", reply_markup=InlineKeyboardMarkup(keyboard))
    return GENDER

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['gender'] = query.data
    keyboard = [
        [InlineKeyboardButton("Male/ကျား", callback_data="Male"), InlineKeyboardButton("Female/မ", callback_data="Female"), InlineKeyboardButton("No Matter", callback_data="Both")]
    ]
    await query.edit_message_text("Looking For?", reply_markup=InlineKeyboardMarkup(keyboard))
    return LOOKING_FOR

async def get_looking_for(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['looking_for'] = query.data
    
    await query.edit_message_text("Your Age? အသက်(ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ၊ ဥပမာ - 20)")
    return AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['age'] = update.message.text
    
    await update.message.reply_text("Your Location? သင်ဘယ်မြို့ကလဲ? (ဥပမာ - ရန်ကုန်, မန္တလေး)")
    return CITY

async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['city'] = update.message.text
    
    await update.message.reply_text("သင့်အကြောင်း အနည်းငယ် (သို့) သင်ရှာဖွေနေတဲ့သူရဲ့ ပုံစံကို စာတိုလေး ရေးပေးပါ။")
    return BIO

async def get_bio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['bio'] = update.message.text
    await update.message.reply_text("နောက်ဆုံးအနေနဲ့ သင့်ရဲ့ Profile အတွက် အကောင်းဆုံး ဓာတ်ပုံတစ်ပုံကို ပို့ပေးပါ။ (Photo အနေနဲ့ပို့ပေးပါ)")
    return PHOTO

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo_file_id = update.message.photo[-1].file_id
    user_id = update.message.from_user.id
    
    referrer_id = context.user_data.get('referrer_id')
    initial_coins = 10 if referrer_id else 5
    
    await users_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "username": update.message.from_user.username,
                "name": context.user_data['name'],
                "gender": context.user_data['gender'],
                "looking_for": context.user_data['looking_for'],
                "age": context.user_data['age'],
                "city": context.user_data['city'],
                "bio": context.user_data['bio'],
                "photo_id": photo_file_id,
                "passed": [], 
                "is_editing": False 
            },
            "$setOnInsert": {
                "likes": [],     
                "matches": [],
                "hard_passed": [],
                "pass_counts": {},
                "coins": initial_coins,
                "last_daily": None,
                "is_verified": False 
            }
        },
        upsert=True
    )

    if referrer_id:
        await users_collection.update_one({"user_id": referrer_id}, {"$inc": {"coins": 5}})
        try:
            await context.bot.send_message(
                chat_id=referrer_id,
                text="🎉 <b>ဂုဏ်ယူပါတယ်။</b> သင့်ဖိတ်ခေါ်လင့်ခ်မှ သူငယ်ချင်းတစ်ယောက် Profile ဖွင့်ပြီးသွားလို့ <b>5 Coins</b> လက်ဆောင်ရရှိသွားပါပြီ။",
                parse_mode="HTML"
            )
        except: pass
    
    await interactions_collection.delete_many({
        "target_id": user_id, 
        "action": {"$in": ["pass", "hard_pass"]}
    })
    
    await update.message.reply_text(
        "🎉 Profile အောင်မြင်စွာ တည်ဆောက်/ပြင်ဆင်ပြီးပါပြီ!\nအောက်ပါ Menu ခလုတ်များမှတစ်ဆင့် အလွယ်တကူ စတင်အသုံးပြုနိုင်ပါပြီ။",
        reply_markup=get_main_menu()
    )

    username_str = f"@{update.message.from_user.username}" if update.message.from_user.username else "မရှိပါ"
    
    log_text = (
        f" <b>User Profile အသစ် / ပြင်ဆင်မှု!</b>\n"
        f" အမည်: {context.user_data['name']}\n"
        f" Username: {username_str}\n"
        f" ကျား/မ: {context.user_data['gender']}\n"
        f" မြို့: {context.user_data['city']}\n"
        f" User ID: <code>{user_id}</code>"
    )
    await send_log(context, log_text, photo_id=photo_file_id)
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    
    await users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"is_editing": False}}
    )

    await update.message.reply_text(
        "❌ လုပ်ငန်းစဉ်ကို ရပ်ဆိုင်းလိုက်ပါပြီ။",
        reply_markup=get_main_menu() 
    )
    context.user_data.clear()
    return ConversationHandler.END
    
async def prompt_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Profile ဖြည့်နေစဉ် တခြား Command နှိပ်မိပါက သတိပေးမည့် Function"""
    await update.message.reply_text(
        "⚠️ လုပ်ငန်းစဉ် မပြီးဆုံးသေးပါ။\n\n"
        "❌ ရပ်ဆိုင်းလိုပါက: /cancel ကို နှိပ်ပါ။\n"
        "🔄 အစကနေ ပြန်စလိုပါက: /start ကို နှိပ်ပါ။"
    )

async def invite_friend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🤝 သူငယ်ချင်းကို ဖိတ်မည် ကိုနှိပ်လျှင် Referral Link ထုတ်ပေးမည့် Function"""
    user_id = update.message.from_user.id
    bot_username = context.bot.username
    
    # မိမိ၏ သီးသန့် Referral Link ဖန်တီးခြင်း
    invite_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    text = (
        "🤝 <b>သူငယ်ချင်းကို ဖိတ်ခေါ်ပြီး အခမဲ့ Coin များ ရယူပါ!</b>\n\n"
        "အောက်ပါ Link ကို Copy ကူးပြီး သင့်သူငယ်ချင်းများထံ ပေးပို့လိုက်ပါ။\n\n"
        "သင့် Link မှတစ်ဆင့် သူငယ်ချင်းတစ်ယောက် Bot တွင် <b>Profile ဖွင့်ပြီးတိုင်း</b> သင့်အတွက် <b>5 Coins</b> နှင့် သူငယ်ချင်းအတွက် <b>5 Coins</b> (စုစုပေါင်း 10 Coins) လက်ဆောင်ရရှိပါမည်။ 🎁\n\n"
        f"🔗 <b>သင့်၏ ဖိတ်ခေါ်လင့်ခ်:</b>\n<code>{invite_link}</code>"
    )
    await update.message.reply_text(text, parse_mode="HTML")
    
# ==========================================
# 2. Matching Engine (Priority Logic ဖြင့်)
# ==========================================

async def show_next_profile(current_user, update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    # မိမိ Like, Pass, Match လုပ်ထားဖူးသူ အားလုံးကို ဆွဲထုတ်မည်
    my_interactions = await interactions_collection.find({"user_id": current_user['user_id']}).to_list(length=None)
    seen_users = [doc['target_id'] for doc in my_interactions]
    seen_users.append(current_user['user_id']) 

    match_query = {
        "user_id": {"$nin": seen_users},
        "is_active": {"$ne": False},
        "is_banned": {"$ne": True}
    }

    if current_user['looking_for'] != "Both":
        match_query['gender'] = current_user['looking_for']
    match_query['looking_for'] = {"$in": [current_user['gender'], "Both"]}
    
    target_user = None

    if current_user.get('city'):
        query_city = match_query.copy()
        query_city['city'] = current_user['city']
        docs = await users_collection.aggregate([{"$match": query_city}, {"$sample": {"size": 1}}]).to_list(length=1)
        if docs:
            target_user = docs[0]

    if not target_user:
        docs = await users_collection.aggregate([{"$match": match_query}, {"$sample": {"size": 1}}]).to_list(length=1)
        if docs:
            target_user = docs[0]

    if not target_user:
        strict_interactions = await interactions_collection.find({
            "user_id": current_user['user_id'],
            "action": {"$in": ["match", "like", "superlike", "hard_pass"]}
        }).to_list(length=None)
        second_chance_seen = [doc['target_id'] for doc in strict_interactions]
        second_chance_seen.append(current_user['user_id'])
        
        query_second = {
            "user_id": {"$nin": second_chance_seen},
            "is_active": {"$ne": False},
            "is_banned": {"$ne": True}
        }
        if current_user['looking_for'] != "Both":
            query_second['gender'] = current_user['looking_for']
        query_second['looking_for'] = {"$in": [current_user['gender'], "Both"]}
        
        docs = await users_collection.aggregate([{"$match": query_second}, {"$sample": {"size": 1}}]).to_list(length=1)
        if docs:
            target_user = docs[0]
            
    if target_user:
        status = "✅ Verified User" if target_user.get("is_verified") else "❌ Non Verify"
        
        caption = (
            f"Name: <b>{target_user['name']}</b>\n\n"
            f"Age: {target_user.get('age', '-')} နှစ်\n\n"
            f"Location: {target_user.get('city', 'မသိပါ')}\n\n"
            f"Gender: {target_user['gender']}\n\n"
            f"User Stats: <b>{status}</b>\n\n"
            f"Bio: {target_user.get('bio', 'မရှိပါ')}"
        )
        keyboard = [
            [
                InlineKeyboardButton("❌ Pass", callback_data=f"pass_{target_user['user_id']}"),
                InlineKeyboardButton("❤️ Like", callback_data=f"like_{target_user['user_id']}")
            ],
            [
                InlineKeyboardButton("🌟 Super Like", callback_data=f"superlike_{target_user['user_id']}"),
                InlineKeyboardButton("💌 Direct Message", callback_data=f"icebreaker_{target_user['user_id']}")
            ],
            [
                InlineKeyboardButton("⚠️ Report", callback_data=f"report_{target_user['user_id']}") 
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if is_callback:
            try:
                await update.callback_query.message.delete()
            except: pass
            msg = await context.bot.send_photo(
                chat_id=update.callback_query.message.chat_id,
                photo=target_user['photo_id'],
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        else:
            msg = await update.message.reply_photo(
                photo=target_user['photo_id'], 
                caption=caption, 
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            
        context.user_data['last_match_msg_id'] = msg.message_id
        context.user_data['last_viewed_user_id'] = target_user['user_id']

    else:
        text = (
            "🏜️ <b>လောလောဆယ် သင့်အတွက် ကိုက်ညီမယ့်သူ ကုန်သွားပါပြီ!</b>\n\n"
            "💡 <b>အကြံပြုချက်:</b> သင့် Profile ဓာတ်ပုံကို ပိုမိုက်တဲ့ပုံ ပြောင်းခြင်း၊ မြို့နှင့် အချက်အလက်များ ပြင်ဆင်ခြင်းဖြင့် လူသစ်များနှင့် Match ပိုရနိုင်ပါတယ်။"
        )
        keyboard = [[InlineKeyboardButton("✏️ Profile ပြင်ဆင်မည်", callback_data="edit_profile")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if is_callback:
            await update.callback_query.message.delete()
            await context.bot.send_message(chat_id=update.callback_query.message.chat_id, text=text, parse_mode="HTML", reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)
            
async def match_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    current_user = await users_collection.find_one({"user_id": user_id})
    
    if not current_user:
        await update.message.reply_text("သင့်မှာ Profile မရှိသေးပါ။ /start ကိုနှိပ်ပြီး အရင်ဖန်တီးပါ။")
        return

    if 'last_match_msg_id' in context.user_data:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=context.user_data['last_match_msg_id'])
        except Exception:
            pass
            
        if 'last_viewed_user_id' in context.user_data:
            last_viewed_id = context.user_data['last_viewed_user_id']
            
            interaction = await interactions_collection.find_one({"user_id": user_id, "target_id": last_viewed_id})
            pass_count = interaction.get("pass_count", 0) + 1 if interaction else 1
            final_action = "hard_pass" if pass_count >= 3 else "pass"
            
            await interactions_collection.update_one(
                {"user_id": user_id, "target_id": last_viewed_id},
                {"$set": {"action": final_action, "pass_count": pass_count}},
                upsert=True
            )
            
            context.user_data.pop('last_viewed_user_id', None)
            context.user_data.pop('last_match_msg_id', None)
            
            updated_user = await users_collection.find_one({"user_id": user_id})
            pass_count = updated_user.get("pass_counts", {}).get(target_str_id, 0)
            if pass_count >= 3:
                await users_collection.update_one(
                    {"user_id": user_id}, 
                    {"$addToSet": {"hard_passed": last_viewed_id}}
                )
                
    current_user = await users_collection.find_one({"user_id": user_id})
        
    # -------------------------------------------------------------
    await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
    loading_msg = await update.message.reply_text("🔍 <i>သင့်အတွက် အကောင်းဆုံး ဖူးစာရှင်ကို ရှာဖွေနေပါတယ်...</i>", parse_mode="HTML")
    await asyncio.sleep(1)
    await loading_msg.delete()
    
    await show_next_profile(current_user, update, context)
    
async def handle_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    context.user_data.pop('last_match_msg_id', None)
    context.user_data.pop('last_viewed_user_id', None)
    action, target_user_id_str = data.split("_")[0], data.split("_")[1]
    target_user_id = int(target_user_id_str)
    current_user_id = query.from_user.id
    current_user = await users_collection.find_one({"user_id": current_user_id})

    # --- (၁) ADMIN BAN LOGIC ---
    if action == "ban":
        if str(current_user_id) != str(ADMIN_ID):
            await query.answer("⛔ Admin သာလျှင် လုပ်ဆောင်နိုင်ပါသည်။", show_alert=True)
            return
        
        await users_collection.update_one({"user_id": target_user_id}, {"$set": {"is_banned": True, "is_active": False}})
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n🚫 <b>BANNED (အကောင့်ပိတ်လိုက်ပါပြီ)</b>", parse_mode="HTML")
        
        try: # ပိတ်ခံရသူထံသို့ အသိပေးစာပို့မည်
            await context.bot.send_message(chat_id=target_user_id, text="🚫 <b>သင့်အကောင့်သည် စည်းမျဉ်းချိုးဖောက်မှုများကြောင့် Shwe Phusar မှ ပိတ်ပင်ခံလိုက်ရပါသည်။</b>", parse_mode="HTML")
        except: pass
        return

    if action == "report":
        target_user = await users_collection.find_one({"user_id": target_user_id})

        if current_user_id in target_user.get("reported_by", []):
            await query.answer("⚠️ ဤအကောင့်ကို သင် Report တင်ထားပြီးပါပြီ။", show_alert=True)
        else:
            await users_collection.update_one(
                {"user_id": target_user_id},
                {"$inc": {"report_count": 1}, "$addToSet": {"reported_by": current_user_id}}
            )
            await query.answer("✅ Report တင်ခြင်း အောင်မြင်ပါသည်။ Admin မှ စစ်ဆေးပေးပါမည်။", show_alert=True)
            
            updated_target = await users_collection.find_one({"user_id": target_user_id})
            report_count = updated_target.get("report_count", 1)
            
            admin_msg = (
                f"🚨 <b>REPORT ALERT (အကောင့်တိုင်ကြားမှု)</b> 🚨\n\n"
                f"⚠️ <b>တိုင်ကြားခံရသူ:</b> {target_user['name']} (<code>{target_user_id}</code>)\n"
                f"👤 <b>တိုင်ကြားသူ:</b> {current_user['name']} (<code>{current_user_id}</code>)\n"
                f"📊 <b>စုစုပေါင်း Report အကြိမ်ရေ:</b> {report_count}\n\n"
                f"<i>(Report အကြိမ်ရေများနေပါက အောက်ပါခလုတ်ဖြင့် Banned ပြုလုပ်နိုင်ပါသည်။)</i>"
            )
            admin_keyboard = [[InlineKeyboardButton("🚫 Ban လုပ်မည် (အကောင့်ပိတ်ရန်)", callback_data=f"ban_{target_user_id}")]]
            
            try:
                await context.bot.send_photo(chat_id=ADMIN_ID, photo=target_user['photo_id'], caption=admin_msg, reply_markup=InlineKeyboardMarkup(admin_keyboard), parse_mode="HTML")
            except Exception as e:
                logger.error(f"Failed to send report to admin: {e}")
                
        action = "pass"

    if action in ["superlike", "like", "pass"]:
        if action == "superlike":
            is_vip = current_user.get("is_vip", False)
            if current_user.get("coins", 0) < 3 and not is_vip:
                await query.answer("❌ Super Like ပေးရန် Coin ၃ ခု လိုအပ်ပါသည်။ /daily နှိပ်၍ အခမဲ့ရယူပါ။ (သို့) VIP ဝယ်ယူပါ။", show_alert=True)
                return
            if not is_vip:
                await users_collection.update_one({"user_id": current_user_id}, {"$inc": {"coins": -3}})
            await query.answer("🌟 Super Like အောင်မြင်စွာ ပို့လိုက်ပါပြီ!", show_alert=True)
        else:
            await query.answer()

        if action == "pass":
            interaction = await interactions_collection.find_one({"user_id": current_user_id, "target_id": target_user_id})
            pass_count = interaction.get("pass_count", 0) + 1 if interaction else 1
            final_action = "hard_pass" if pass_count >= 3 else "pass"
            
            await interactions_collection.update_one(
                {"user_id": current_user_id, "target_id": target_user_id},
                {"$set": {"action": final_action, "pass_count": pass_count}},
                upsert=True
            )

        elif action in ["like", "superlike"]:
            target_interaction = await interactions_collection.find_one({
                "user_id": target_user_id, 
                "target_id": current_user_id,
                "action": {"$in": ["like", "superlike"]}
            })
            
            target_user = await users_collection.find_one({"user_id": target_user_id})

            if target_interaction:
                await interactions_collection.update_one(
                    {"user_id": current_user_id, "target_id": target_user_id},
                    {"$set": {"action": "match"}}, upsert=True
                )
                await interactions_collection.update_one(
                    {"user_id": target_user_id, "target_id": current_user_id},
                    {"$set": {"action": "match"}}, upsert=True
                )
                
                target_username = f"@{target_user['username']}" if target_user.get('username') else f"<a href='tg://user?id={target_user['user_id']}'>{target_user['name']}</a>"
                await context.bot.send_message(chat_id=current_user_id, text=f"🎉 <b>Match ဖြစ်သွားပါပြီ!</b>\nသင်နဲ့ {target_user['name']} တို့ နှစ်ဦးသဘောတူ Match ဖြစ်သွားပါပြီ。\nစကားသွားပြောရန်: {target_username}", parse_mode="HTML")
                
                current_username = f"@{current_user['username']}" if current_user.get('username') else f"<a href='tg://user?id={current_user['user_id']}'>{current_user['name']}</a>"
                try:
                    await context.bot.send_message(chat_id=target_user_id, text=f"🎉 <b>Match အသစ် ရပါပြီ!</b>\n{current_user['name']} နဲ့ သင်တို့ နှစ်ဦးသဘောတူ Match ဖြစ်သွားပါပြီ。\nစကားသွားပြောရန်: {current_username}", parse_mode="HTML")
                except Forbidden:
                    await users_collection.update_one({"user_id": target_user_id}, {"$set": {"is_active": False}})
                except: pass

                curr_uname = f"@{current_user['username']}" if current_user.get('username') else "မရှိပါ"
                tgt_uname = f"@{target_user['username']}" if target_user.get('username') else "မရှိပါ"
                log_text = f"💞 <b>Match အသစ် ဖြစ်သွားပါပြီ!</b>\n1️⃣ {current_user['name']} ({curr_uname}) - <code>{current_user_id}</code>\n2️⃣ {target_user['name']} ({tgt_uname}) - <code>{target_user_id}</code>"
                await send_log(context, log_text, photo_id=current_user['photo_id'])

            else:
                await interactions_collection.update_one(
                    {"user_id": current_user_id, "target_id": target_user_id},
                    {"$set": {"action": action}}, upsert=True
                )

                if action == "superlike":
                    status = "✅ Verified User" if current_user.get("is_verified") else "❌ Non Verify"
                    caption = (
                        f"🌟 <b>WOW! သင့်ကို တစ်စုံတစ်ယောက်က Super Like 🌟 ပေးလိုက်ပါတယ်။</b>\n\n"
                        f"Name: {current_user['name']}, {current_user.get('age', '-')} နှစ်\n"
                        f"Location: {current_user.get('city', 'မသိပါ')}\n"
                        f"Gender: {current_user['gender']}\n"
                        f"Profile Stats: {status}\n"
                        f"Bio: {current_user.get('bio', 'မရှိပါ')}"
                    )
                    keyboard = [
                        [
                            InlineKeyboardButton("❌ Pass", callback_data=f"pass_{current_user_id}"),
                            InlineKeyboardButton("❤️ Match", callback_data=f"like_{current_user_id}")
                        ]
                    ]
                    try:
                        await context.bot.send_photo(
                            chat_id=target_user_id, photo=current_user['photo_id'],
                            caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
                        )
                    except Forbidden:
                        await users_collection.update_one({"user_id": target_user_id}, {"$set": {"is_active": False}})
                    except: pass
                
    await context.bot.send_chat_action(chat_id=current_user_id, action=ChatAction.TYPING)
    
    current_user_updated = await users_collection.find_one({"user_id": current_user_id})
    await show_next_profile(current_user_updated, update, context, is_callback=True)

async def start_icebreaker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    target_id = int(query.data.split("_")[1])

    current_user = await users_collection.find_one({"user_id": user_id})
    is_vip = current_user.get("is_vip", False)

    if current_user.get("coins", 0) < 5 and not is_vip:
        await query.answer("❌ Coin မလောက်ပါ။ Message ပို့ရန် 5 Coins လိုအပ်ပါသည်။", show_alert=True)
        return ConversationHandler.END

    context.user_data['icebreaker_target'] = target_id
    
    try: await query.message.delete()
    except: pass
    
    coin_text = "(အခမဲ့)" if is_vip else "(5 Coins ကျသင့်မည်)"
    await context.bot.send_message(
        chat_id=user_id,
        text=f"💌 <b>Direct Message</b> {coin_text}\n\n"
             f"သူ့ကို ပို့ချင်တဲ့ စာသား (Message) ကို အခု ရိုက်ထည့်လိုက်ပါ။\n"
             f"<i>(ဥပမာ - မင်္ဂလာပါ၊ Profile လေးကို သဘောကျသွားလို့ပါ...)</i>\n\n"
             f"❌ မပို့တော့ပါက /cancel ကို နှိပ်ပါ။",
        parse_mode="HTML"
    )
    return ICEBREAKER_TEXT

async def send_icebreaker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    target_id = context.user_data.get('icebreaker_target')
    message_text = update.message.text

    current_user = await users_collection.find_one({"user_id": user_id})
    is_vip = current_user.get("is_vip", False)

    if not is_vip:
        await users_collection.update_one({"user_id": user_id}, {"$inc": {"coins": -5}})

    await users_collection.update_one({"user_id": user_id}, {"$addToSet": {"likes": target_id}})

    status = "✅ Verified User" if current_user.get("is_verified") else "❌ Non Verify"
    caption = (
        f"💌 <b>သင့်ဆီကို Direct Message ပို့ထားတဲ့သူ ရှိနေပါတယ်!</b>\n\n"
        f"💬 <b>သူပြောထားတဲ့စာ:</b> <i>\"{message_text}\"</i>\n\n"
        f"Name: <b>{current_user['name']}</b> ({current_user.get('age', '-')} နှစ်)\n"
        f"Location: {current_user.get('city', 'မသိပါ')}\n"
        f"Gender: {current_user['gender']}\n"
        f"Profile Stats: <b>{status}</b>\n\n"
        f"Bio: {current_user.get('bio', 'မရှိပါ')}"
    )
    keyboard = [
        [
            InlineKeyboardButton("❌ Pass", callback_data=f"pass_{user_id}"),
            InlineKeyboardButton("❤️ Match", callback_data=f"like_{user_id}")
        ]
    ]
    try:
        await context.bot.send_photo(
            chat_id=target_id,
            photo=current_user['photo_id'],
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    except: pass

    await update.message.reply_text("✅ သင့်ရဲ့ Message ကို အောင်မြင်စွာ ပို့လိုက်ပါပြီ!")
    
    current_user_updated = await users_collection.find_one({"user_id": user_id})
    await show_next_profile(current_user_updated, update, context)
    
    context.user_data.clear()
    return ConversationHandler.END

# ==========================================
# 3. My Profile System
# ==========================================

async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.UPLOAD_PHOTO)
    
    user = await users_collection.find_one({"user_id": user_id})
    
    if not user:
        await update.message.reply_text("သင့်မှာ Profile မရှိသေးပါ။ /start ကိုနှိပ်ပြီး အရင်ဖန်တီးပါ။")
        return

    status = "✅ Verified User" if user.get("is_verified") else "❌ Non Verify"
    
    caption = (
        f"🌟 Current Profile 🌟\n\n"
        f"Name: {user['name']} ({user.get('age', '-')} နှစ်)\n"
        f"Location: {user.get('city', 'မသိပါ')}\n"
        f"Gender: {user['gender']}\n"
        f"Profile Stats: {status}\n"
        f"Looking For: {user['looking_for']}\n"
        f"Bio: {user.get('bio', 'မရှိပါ')}"
    )
    
    keyboard = [[InlineKeyboardButton("✏️ Profile အသစ်ပြန်ပြင်မည်", callback_data="edit_profile")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_photo(photo=user['photo_id'], caption=caption, reply_markup=reply_markup)

async def start_edit_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    keyboard = [
        [InlineKeyboardButton("👤 နာမည် ပြင်မည်", callback_data="edit_opt_name"), InlineKeyboardButton("🎂 အသက် ပြင်မည်", callback_data="edit_opt_age")],
        [InlineKeyboardButton("📍 မြို့ ပြင်မည်", callback_data="edit_opt_city"), InlineKeyboardButton("📝 Bio ပြင်မည်", callback_data="edit_opt_bio")],
        [InlineKeyboardButton("📸 ဓာတ်ပုံ ပြောင်းမည်", callback_data="edit_opt_photo")],
        [InlineKeyboardButton("❌ မပြင်တော့ပါ (Cancel)", callback_data="edit_opt_cancel")]
    ]
    
    try: await query.message.delete()
    except: pass
    
    await context.bot.send_message(
        chat_id=user_id,
        text="✏️ <b>Profile ပြင်ဆင်ခြင်း</b>\n\nမည်သည့်အချက်အလက်ကို ပြင်ဆင်လိုပါသလဲ? အောက်ပါခလုတ်များမှ ရွေးချယ်ပါ။",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    return EDIT_CHOICE

async def handle_edit_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ဘာကိုပြင်မလဲ ရွေးချယ်မှုကို လက်ခံမည့် Function"""
    query = update.callback_query
    await query.answer()
    choice = query.data.split("_")[2] # name, age, city, bio, photo, cancel
    
    if choice == "cancel":
        await query.message.delete()
        await context.bot.send_message(chat_id=query.from_user.id, text="❌ Profile ပြင်ဆင်ခြင်းကို ရပ်ဆိုင်းလိုက်ပါပြီ။", reply_markup=get_main_menu())
        return ConversationHandler.END
        
    context.user_data['edit_field'] = choice
    
    prompts = {
        "name": "👤 သင့်နာမည်အသစ်ကို ရိုက်ထည့်ပါ။",
        "age": "🎂 သင့်အသက်ကို ဂဏန်းဖြင့် ရိုက်ထည့်ပါ။ (ဥပမာ - 22)",
        "city": "📍 သင်ယခုနေထိုင်သည့် မြို့အမည်သစ်ကို ရိုက်ထည့်ပါ။",
        "bio": "📝 သင့်အကြောင်း Bio အသစ်ကို ရေးပေးပါ။",
        "photo": "📸 သင့် Profile ဓာတ်ပုံအသစ်ကို ပို့ပေးပါ။ (Photo အနေဖြင့်ပို့ပါ)"
    }
    
    await query.message.edit_text(prompts[choice])
    return PARTIAL_PHOTO if choice == "photo" else PARTIAL_TEXT

async def receive_partial_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    field = context.user_data.get('edit_field')
    new_text = update.message.text
    
    if field == "name":
        new_text = new_text.replace("✅", "").replace("✔️", "").strip()
        
    await users_collection.update_one({"user_id": user_id}, {"$set": {field: new_text}})
    
    await update.message.reply_text("✅ အောင်မြင်စွာ ပြင်ဆင်ပြီးပါပြီ။", reply_markup=get_main_menu())
    await my_profile(update, context) # ပြင်ပြီးသား Profile ကို ချက်ချင်း ပြန်ပြပေးမည်
    context.user_data.clear()
    return ConversationHandler.END

async def receive_partial_edit_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    photo_file_id = update.message.photo[-1].file_id
    
    await users_collection.update_one({"user_id": user_id}, {"$set": {"photo_id": photo_file_id}})
    
    await users_collection.update_many({}, {"$pull": {"passed": user_id}})
    
    await update.message.reply_text("✅ ဓာတ်ပုံအသစ်ကို အောင်မြင်စွာ ပြောင်းလဲပြီးပါပြီ။", reply_markup=get_main_menu())
    await my_profile(update, context)
    context.user_data.clear()
    return ConversationHandler.END
    
async def get_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if str(user_id) != str(ADMIN_ID):
        await update.message.reply_text("⛔Access Denied!")
        return

    total_users = await users_collection.count_documents({})

    if total_users == 0:
        await update.message.reply_text("လောလောဆယ် Bot အသုံးပြုသူ မရှိသေးပါ။")
        return

    txt_file = io.BytesIO()
    header = f"=== LeoMatch Bot Users List ===\nTotal Users: {total_users}\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" + "=" * 40 + "\n\n"
    txt_file.write(header.encode('utf-8'))

    idx = 1
    async for user in users_collection.find():
        name = user.get("name", "Unknown")
        username = f"@{user.get('username')}" if user.get("username") else "မရှိပါ"
        uid = user.get("user_id", "Unknown")
        gender = user.get("gender", "-")
        coins = user.get("coins", 0)
        
        line = f"{idx}. Name: {name} | Username: {username} | Gender: {gender} | Coins: {coins} | UserID: {uid}\n"
        txt_file.write(line.encode('utf-8'))
        idx += 1

    txt_file.seek(0)
    txt_file.name = "bot_users_list.txt"

# ==========================================
# 4. Admin Feature (Broadcast System)
# ==========================================

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if str(user_id) != str(ADMIN_ID):
        await update.message.reply_text("⛔Access Denied")
        return

    reply_to_msg = update.message.reply_to_message

    if not reply_to_msg and not context.args:
        await update.message.reply_text(
            "⚠️ <b>အသုံးပြုပုံ မှားယွင်းနေပါတယ်။</b>\n\n"
            "<b>နည်းလမ်း (၁):</b> ပို့လိုသော စာသား၊ ပုံ (သို့) ဗီဒီယိုကို Reply ပြန်ပြီး <code>/broadcast</code> ဟု ရိုက်ပါ။ (မီဒီယာအားလုံးပို့ရန်)\n"
            "<b>နည်းလမ်း (၂):</b> <code>/broadcast [ပို့လိုသောစာသား]</code> ဟု တိုက်ရိုက်ရိုက်ပါ။",
            parse_mode="HTML"
        )
        return

    total_users = await users_collection.count_documents({"is_active": {"$ne": False}})
    success_count = 0

    status_msg = await update.message.reply_text(f"📣 Broadcast စတင်ပို့ဆောင်နေပါသည်...\nစုစုပေါင်း User အရေအတွက်: {total_users} ဦး")

    async for user in users_collection.find({"is_active": {"$ne": False}}):
        try:
            if reply_to_msg:
                await context.bot.copy_message(
                    chat_id=user["user_id"],
                    from_chat_id=update.message.chat_id,
                    message_id=reply_to_msg.message_id
                )
            else:
                broadcast_text = " ".join(context.args)
                await context.bot.send_message(
                    chat_id=user["user_id"],
                    text=f"📢 <b>Admin အသိပေးချက်</b>\n\n{broadcast_text}",
                    parse_mode="HTML"
                )
            success_count += 1
        except Forbidden:
            await users_collection.update_one({"user_id": user["user_id"]}, {"$set": {"is_active": False}})
            logger.warning(f"User {user['user_id']} blocked the bot. Marked as inactive.")
        except Exception as e:
            logger.error(f"Broadcast ပို့ရန် အဆင်မပြေပါ User ID {user['user_id']}: {e}")

    await status_msg.edit_text(f"✅ Broadcast ပို့ဆောင်မှု ပြီးဆုံးပါပြီ။\nအောင်မြင်စွာပို့နိုင်ခဲ့သူ: {success_count}/{total_users} ဦး")

# ==========================================
# 5. Premium / Coin Features (See Who Liked You)
# ==========================================

async def check_likes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
    
    current_user = await users_collection.find_one({"user_id": user_id})

    if not current_user:
        await update.message.reply_text("သင့်မှာ Profile မရှိသေးပါ။ /start ကိုနှိပ်ပါ။")
        return
        
    my_interactions = await interactions_collection.find({"user_id": user_id}).to_list(length=None)
    seen_by_me = [doc['target_id'] for doc in my_interactions]

    likers_count = await interactions_collection.count_documents({
        "target_id": user_id,
        "action": {"$in": ["like", "superlike"]},
        "user_id": {"$nin": seen_by_me}
    })

    coins = current_user.get('coins', 0)

    if likers_count == 0:
        await update.message.reply_text(f"😔 လောလောဆယ် သင့်ကို လျှို့ဝှက် Like ထားသူ မရှိသေးပါ။\n💰 လက်ကျန် Coin: {coins}")
        return

    text = (
        f"🎉 <b>သတင်းကောင်း!</b> သင့်ကို သဘောကျလို့ လျှို့ဝှက် Like ပေးထားသူ <b>{likers_count}</b> ယောက် ရှိပါတယ်။\n"
        f"💰 သင့် လက်ကျန် Coin: <b>{coins}</b> စေ့\n\n"
        f"1 Coin သုံးပြီး သူတို့ကို တစ်ခါတည်း ဖွင့်ကြည့်မလား? (Flood မဖြစ်ရန် တစ်ကြိမ်လျှင် အများဆုံး ၅ ယောက်အထိသာ ပြသပေးမည်ဖြစ်သည်)"
    )
    keyboard = [[InlineKeyboardButton("👀 1 Coin သုံး၍ အားလုံးကိုကြည့်မည်", callback_data="reveal_like")]]
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_reveal_like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    current_user = await users_collection.find_one({"user_id": user_id})
    coins = current_user.get('coins', 0)
    is_vip = current_user.get('is_vip', False)

    if coins < 1 and not is_vip:
        await query.message.edit_text("❌ Coin မလောက်ပါ။ /daily ကိုနှိပ်ပြီး အခမဲ့ယူပါ (သို့) VIP ဝယ်ယူပါ။")
        return

    my_interactions = await interactions_collection.find({"user_id": user_id}).to_list(length=None)
    seen_by_me = [doc['target_id'] for doc in my_interactions]
    
    pending_likers_cursor = interactions_collection.find({
        "target_id": user_id,
        "action": {"$in": ["like", "superlike"]},
        "user_id": {"$nin": seen_by_me}
    }).limit(5)
    
    liker_interactions = await pending_likers_cursor.to_list(length=None)
    liker_ids = [doc['user_id'] for doc in liker_interactions]

    likers = await users_collection.find({"user_id": {"$in": liker_ids}}).to_list(length=None)

    if not is_vip:
        await users_collection.update_one({"user_id": user_id}, {"$inc": {"coins": -1}})
        text_msg = f"✅ <b>Coin 1 ခု သုံးပြီး သင့်ကို Like ထားသူ ({len(likers)}) ယောက်ကို ဖွင့်ပြလိုက်ပါပြီ!</b>\n(လက်ကျန် Coin: {coins - 1} စေ့)"
    else:
        text_msg = f"👑 <b>VIP အခွင့်အရေးဖြင့် သင့်ကို Like ထားသူ ({len(likers)}) ယောက်ကို အခမဲ့ ဖွင့်ပြလိုက်ပါပြီ!</b>"

    await query.message.delete()
    await context.bot.send_message(chat_id=user_id, text=text_msg, parse_mode="HTML")

    for liker in likers:
        status = "✅ Verified User" if liker.get("is_verified") else "❌ Non Verify"
        
        caption = (
            f"💖 <b>ဒီသူက သင့်ကို Like ပေးထားပါတယ်!</b> 💖\n\n"
            f"Name: {liker['name']}, {liker.get('age', '-')} နှစ်\n"
            f"Location: {liker.get('city', 'မသိပါ')}\n"
            f"Gender: {liker['gender']}\n"
            f"Profile Stats: {status}\n"
            f"Bio: {liker.get('bio', 'မရှိပါ')}"
        )
        keyboard = [
            [
                InlineKeyboardButton("❌ Pass", callback_data=f"pass_{liker['user_id']}"),
                InlineKeyboardButton("❤️ Match", callback_data=f"like_{liker['user_id']}")
            ],
            [
                InlineKeyboardButton("🌟 Super Like", callback_data=f"superlike_{liker['user_id']}")
            ]
        ]
        
        await context.bot.send_photo(
            chat_id=user_id,
            photo=liker['photo_id'],
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

async def daily_reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    current_user = await users_collection.find_one({"user_id": user_id})
    
    if not current_user:
        await update.message.reply_text("သင့်မှာ Profile မရှိသေးပါ။ /start ကိုနှိပ်ပါ။")
        return

    now = datetime.utcnow()
    last_daily = current_user.get("last_daily")

    if last_daily and (now - last_daily).days < 1:
        next_time = last_daily + timedelta(days=1)
        hours_left = int((next_time - now).total_seconds() // 3600)
        await update.message.reply_text(f"⏳ ယနေ့အတွက် Coin ရယူပြီးပါပြီ။ နောက်ထပ် {hours_left} နာရီ နေမှ ပြန်ယူလို့ရပါမယ်။ Coin ဝယ်ယူရန် @moviestoreadmin")
        return

    await users_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"coins": 1}, "$set": {"last_daily": now}}
    )
    new_coins = current_user.get('coins', 0) + 1
    await update.message.reply_text(f"🎁 နေ့စဉ်လက်ဆောင် 1 Coin ရရှိပါသည်! ယခု လက်ကျန်: {new_coins} Coin")

async def buy_coin_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "💎 <b>VIP နှင့် Coin ဝယ်ယူရန်</b> 💎\n\n"
        "Coin များဝယ်ယူပြီး ဖူးစာရှင်ကို ပိုမိုမြန်ဆန်စွာ ရှာဖွေလိုက်ပါ!\n\n"
        "🪙 <b>Coin ဈေးနှုန်းများ</b>\n"
        "🔸 15 Coins - 1,000 ကျပ်\n"
        "🔸 50 Coins - 3,000 ကျပ်\n"
        "🔸 100 Coins - 5,000 ကျပ်\n\n"
        "👑 <b>VIP Package (၁ လစာ - 10,000 ကျပ်)</b>\n"
        "- Super Like များ အကန့်အသတ်မရှိ အခမဲ့ပေးနိုင်ခြင်း\n"
        "- မိမိကို Like ထားသူများကို အခမဲ့ အမြဲတမ်းကြည့်နိုင်ခြင်း\n\n"
        "💳 <b>ငွေလွှဲရန် အကောင့်များ</b>\n"
        "🔹 KPay: 09123456789 (U Mya)\n"
        "🔹 WavePay: 09123456789 (U Mya)\n\n"
        "✅ <b>ဝယ်ယူနည်း</b>\n"
        f"ငွေလွှဲပြီးပါက ငွေလွှဲပြေစာ (Screenshot) နှင့် သင့် User ID: <code>{update.message.from_user.id}</code> ကို Admin <b>@YourAdminUsername</b> ထံသို့ ပို့ပေးပါ။ Admin မှ စစ်ဆေးပြီး မိနစ်အနည်းငယ်အတွင်း Coin ထည့်ပေးပါမည်။"
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def add_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.message.from_user.id) != str(ADMIN_ID):
        return
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        await users_collection.update_one({"user_id": target_id}, {"$inc": {"coins": amount}})
        await update.message.reply_text(f"✅ User ID: {target_id} သို့ Coin {amount} ခု ထည့်ပေးပြီးပါပြီ။")
        try: # User ထံ အသိပေးမည်
            await context.bot.send_message(chat_id=target_id, text=f"🎉 <b>ဂုဏ်ယူပါတယ်။</b> သင့်အကောင့်သို့ Coin {amount} ခု ရောက်ရှိလာပါပြီ။", parse_mode="HTML")
        except: pass
    except:
        await update.message.reply_text("⚠️ အသုံးပြုပုံ: /addcoin [User_ID] [Coin_အရေအတွက်]")

async def add_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin မှ User ကို VIP ပေးမည့် Function (/addvip)"""
    if str(update.message.from_user.id) != str(ADMIN_ID):
        return
    try:
        target_id = int(context.args[0])
        await users_collection.update_one({"user_id": target_id}, {"$set": {"is_vip": True}})
        await update.message.reply_text(f"✅ User ID: {target_id} ကို VIP အဖြစ် သတ်မှတ်ပေးပြီးပါပြီ။")
        try:
            await context.bot.send_message(chat_id=target_id, text="👑 <b>ဂုဏ်ယူပါတယ်။</b> သင်သည် ယခုမှစ၍ VIP User တစ်ယောက်ဖြစ်သွားပါပြီ! အခမဲ့ Super Like များကို စိတ်ကြိုက်အသုံးပြုနိုင်ပါပြီ။", parse_mode="HTML")
        except: pass
    except:
        await update.message.reply_text("⚠️ အသုံးပြုပုံ: /addvip [User_ID]")

# ==========================================
# 6. Help Command & Bot Menu Setup
# ==========================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 <b>Shwe Phusar အသုံးပြုနည်း လမ်းညွှန်</b>\n\n"
        "အောက်ပါ Command များကို နှိပ်၍ အလွယ်တကူ အသုံးပြုနိုင်ပါသည် -\n\n"
        "🔸 /start - Profile အသစ်စတင်ရန်\n"
        "🔸 /match - ဖူးစာရှင်ကို စတင်ရှာဖွေရန် 💖\n"
        "🔸 /myprofile - မိမိ၏ Profile ကို ကြည့်ရန် (သို့) ပြင်ရန် 👤\n"
        "🔸 /likes - မိမိကို Like ပေးထားသူများကို ကြည့်ရန် 👀\n"
        "🔸 /daily - နေ့စဉ် အခမဲ့ Coin ရယူရန် 🎁\n"
        "🔸 /help - ဤအသုံးပြုနည်း လမ်းညွှန်ကို ပြန်ဖတ်ရန်\n\n"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")

async def post_init(application: Application):
    commands = [
        BotCommand("start", "Bot ကို စတင်ရန် (သို့) Profile ဖွင့်ရန်"),
        BotCommand("match", "ကိုက်ညီမည့်သူများကို ရှာဖွေရန် 💖"),
        BotCommand("myprofile", "မိမိ၏ Profile ကိုကြည့်ရန် / ပြင်ရန် 👤"),
        BotCommand("likes", "မိမိကို Like ထားသူများကို ကြည့်ရန် 👀"),
        BotCommand("daily", "နေ့စဉ် အခမဲ့ Coin ယူရန် 🎁"),
        BotCommand("verify", "အကောင့်အစစ်ဖြစ်ကြောင်း Blue Tick ✅ ယူရန်"),
        BotCommand("help", "အသုံးပြုနည်း လမ်းညွှန်ဖတ်ရန် ❓"),
    ]
    await application.bot.set_my_commands(commands)
# ==========================================
# 7. Blue Tick Verification System (✅)
# ==========================================
VERIFY_PHOTO_STATE = 100 

async def verify_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user = await users_collection.find_one({"user_id": user_id})
    
    if not user:
        await update.message.reply_text("သင့်မှာ Profile မရှိသေးပါ။ /start ကိုနှိပ်ပါ။")
        return ConversationHandler.END
        
    if user.get("is_verified"):
        await update.message.reply_text("✅ Your Profile is Verified")
        return ConversationHandler.END
        
    await update.message.reply_text(
        "📸 <b>အကောင့်အစစ်ဖြစ်ကြောင်း အတည်ပြုခြင်း</b>\n\n"
        "ကျေးဇူးပြု၍ သင့်မျက်နှာ သေချာပေါ်လွင်ပြီး <b>လက်နှစ်ချောင်း (✌️) ထောင်ထားသော ဆဲလ်ဖီ (Selfie) ပုံ</b> တစ်ပုံကို ပို့ပေးပါ။\n\n"
        "<i>(Note: This image will not be visible to anyone except the admin. Privacy is fully guaranteed.)</i>",
        parse_mode="HTML"
    )
    return VERIFY_PHOTO_STATE

async def receive_verify_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file_id = update.message.photo[-1].file_id
    user_id = update.message.from_user.id
    user = await users_collection.find_one({"user_id": user_id})

    username_str = f"@{update.message.from_user.username}" if update.message.from_user.username else "မရှိပါ"

    keyboard = [
        [
            InlineKeyboardButton("✅ လက်ခံမည်", callback_data=f"verify_approve_{user_id}"),
            InlineKeyboardButton("❌ ပယ်ချမည်", callback_data=f"verify_reject_{user_id}")
        ]
    ]
    

    caption = (
        f"🛡️ <b>Verification Request</b> 🛡️\n\n"
        f"👤 အမည်: {user['name']}\n"
        f"💬 Username: {username_str}\n"
        f"🚻 ကျား/မ: {user['gender']}\n"
        f"🆔 User ID: <code>{user_id}</code>"
    )
    
    try:
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo_file_id,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        await update.message.reply_text("⏳ သင့်ပုံကို Shwe Phusar Team သို့ စစ်ဆေးရန် ပို့လိုက်ပါပြီ။ အတည်ပြုချက်ရပါက အကြောင်းကြားပေးပါမည်။")
    except Exception as e:
        logger.error(f"Error sending verify photo to admin: {e}")
        await update.message.reply_text("⚠️ တောင်းပန်ပါတယ်။ စနစ်ချို့ယွင်းမှုဖြစ်ပေါ်နေပါတယ်။ Admin ID မှန်မမှန် ပြန်စစ်ပါ။")
        
    return ConversationHandler.END

async def verify_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Verification လုပ်ငန်းစဉ်ကို ရပ်ဆိုင်းလိုက်ပါပြီ။")
    return ConversationHandler.END

async def handle_verify_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    if str(query.from_user.id) != str(ADMIN_ID):
        await query.answer("⛔ ဤခလုတ်ကို Admin သာ နှိပ်ခွင့်ရှိပါသည်။", show_alert=True)
        return
        
    await query.answer()
    data = query.data
    action, target_id_str = data.split("_")[1], data.split("_")[2]
    target_id = int(target_id_str)
    
    if action == "approve":
        await users_collection.update_one({"user_id": target_id}, {"$set": {"is_verified": True}})
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n✅ <b>APPROVED (အတည်ပြုပြီး)</b>", parse_mode="HTML")
        try:
            await context.bot.send_message(
                chat_id=target_id, 
                text="🎉 <b>ဂုဏ်ယူပါတယ်။</b> သင့်အကောင့်ကို အတည်ပြု (Verify) ပြီးပါပြီ။ ", 
                parse_mode="HTML"
            )
        except Forbidden:
            await users_collection.update_one({"user_id": target_id}, {"$set": {"is_active": False}})
        except: pass

    elif action == "reject":
        await users_collection.update_one({"user_id": target_id}, {"$set": {"is_verified": False}})
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n❌ <b>REJECTED (ပယ်ချလိုက်သည်)</b>", parse_mode="HTML")
        try:
            await context.bot.send_message(
                chat_id=target_id, 
                text="😔 <b>တောင်းပန်ပါတယ်။</b> သင့် Verification ပုံမှာ သတ်မှတ်ချက်များနှင့် မကိုက်ညီသဖြင့် ပယ်ချခံရပါတယ်။ /verify ကို နှိပ်ပြီး မျက်နှာနှင့် လက် ✌️ သေချာပေါ်သောပုံဖြင့် ပြန်လည်ကြိုးစားနိုင်ပါတယ်။", 
                parse_mode="HTML"
            )
        except: pass


# ==========================================
# 5. Main Logic
# ==========================================

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    keep_alive() 

    if not BOT_TOKEN or not MONGO_URI:
        logger.error("BOT_TOKEN သို့မဟုတ် MONGO_URI မရှိပါ။")
        return

    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

# -------------------------------------------------------------
    # ၁။ Registration Flow (အစားထိုးရန်)
    # -------------------------------------------------------------
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(start_edit_profile, pattern="^edit_profile$") 
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GENDER: [CallbackQueryHandler(get_gender, pattern="^(Male|Female)$")],
            LOOKING_FOR: [CallbackQueryHandler(get_looking_for, pattern="^(Male|Female|Both)$")],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
            BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bio)],
            PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
            EDIT_CHOICE: [CallbackQueryHandler(handle_edit_choice, pattern="^edit_opt_")],
            PARTIAL_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_partial_edit_text)],
            PARTIAL_PHOTO: [MessageHandler(filters.PHOTO, receive_partial_edit_photo)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.COMMAND, prompt_cancel)
        ],
        allow_reentry=True
    )
    application.add_handler(conv_handler)
    
    verify_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("verify", verify_start),
            MessageHandler(filters.Regex("^✅ Profile Verify$"), verify_start)
        ],
        states={
            VERIFY_PHOTO_STATE: [MessageHandler(filters.PHOTO, receive_verify_photo)],
        },
        fallbacks=[
            CommandHandler("cancel", verify_cancel),
            MessageHandler(filters.COMMAND, prompt_cancel)
        ],
        allow_reentry=True
    )
    application.add_handler(verify_conv_handler)

    icebreaker_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_icebreaker, pattern="^icebreaker_")],
        states={
            ICEBREAKER_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_icebreaker)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    application.add_handler(icebreaker_conv_handler)

    application.add_handler(CommandHandler("match", match_command))
    application.add_handler(CallbackQueryHandler(handle_action, pattern="^(like_|pass_|superlike_|report_|ban_)"))

    application.add_handler(CallbackQueryHandler(handle_verify_action, pattern="^verify_"))

    application.add_handler(CommandHandler("myprofile", my_profile))

    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("user", get_users_list))

    application.add_handler(CommandHandler("likes", check_likes_command))
    application.add_handler(CallbackQueryHandler(handle_reveal_like, pattern="^reveal_like$"))
    application.add_handler(CommandHandler("daily", daily_reward))

    application.add_handler(MessageHandler(filters.Regex("^🔍 Match Partner 💖$"), match_command))
    application.add_handler(MessageHandler(filters.Regex("^My Profile$"), my_profile))
    application.add_handler(MessageHandler(filters.Regex("^Who Liked You$"), check_likes_command))
    application.add_handler(MessageHandler(filters.Regex("^Daily Coin$"), daily_reward))
    application.add_handler(MessageHandler(filters.Regex("^Buy VIP / Coin$"), buy_coin_info))
    application.add_handler(CommandHandler("addcoin", add_coin))
    application.add_handler(CommandHandler("addvip", add_vip))
    application.add_handler(MessageHandler(filters.Regex("^Invite Friends$"), invite_friend))
    
    # Help Menu
    application.add_handler(CommandHandler("help", help_command))

    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
