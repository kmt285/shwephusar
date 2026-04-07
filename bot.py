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

NAME, GENDER, LOOKING_FOR, AGE, CITY, BIO, PHOTO = range(7)
EDIT_CHOICE, PARTIAL_TEXT, PARTIAL_PHOTO = range(7, 10)

def get_main_menu():
    """အမြဲတမ်းပေါ်နေမယ့် Main Menu ခလုတ်များ ဖန်တီးသည့် Function"""
    keyboard = [
        [KeyboardButton("🔍 Match ရှာမည် 💖")],
        [KeyboardButton("👤 ကျွန်ုပ်၏ Profile"), KeyboardButton("👀 လျှို့ဝှက် Like များ")],
        [KeyboardButton("🎁 နေ့စဉ် Coin ယူမည်"), KeyboardButton("✅ အကောင့်အတည်ပြုရန်")]
    ]
    # resize_keyboard က ခလုတ်ကို ဖုန်းစခရင်နဲ့ ကွက်တိဖြစ်အောင် ညှိပေးပြီး၊ is_persistent က အမြဲပေါ်နေအောင် လုပ်ပေးပါတယ်
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)

async def send_log(context: ContextTypes.DEFAULT_TYPE, message: str, photo_id: str = None):
    """Admin Log Channel သို့ ဓာတ်ပုံနှင့်တကွ သတင်းလှမ်းပို့မည့် Function"""
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
    
    # Ban ခံထားရသူဖြစ်ပါက Bot အသုံးပြုခွင့်ကို လုံးဝ ပိတ်ပင်မည်
    if existing_user and existing_user.get("is_banned"):
        await update.message.reply_text("🚫 သင့်အကောင့်သည် စည်းမျဉ်းချိုးဖောက်မှုများကြောင့် ပိတ်ပင်ခံထားရပါသည်။")
        return ConversationHandler.END

    if not update.message.from_user.username:
        await update.message.reply_text(
            "⚠️ သင့်အကောင့်မှာ Telegram Username မရှိသေးပါ။\n"
            "Match ဖြစ်တဲ့အခါ အခြားသူများက သင့်ကို ဆက်သွယ်နိုင်ရန် Settings > Username မှာ အရင်သွားရောက် သတ်မှတ်ပေးပါ။\n\n"
            "သတ်မှတ်ပြီးပါက /start ကို ပြန်နှိပ်ပါ။"
        )
        return ConversationHandler.END
        
    user_id = update.message.from_user.id
    existing_user = await users_collection.find_one({"user_id": user_id})
    
    # User လည်းရှိပြီးသား (နာမည်ဖြည့်ထားပြီးသား) ဆိုရင် Main Menu ကိုပဲ အမြဲပြပေးပါမည်။
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
            "သင့်နာမည် ဘယ်လိုခေါ်လဲ?"
        )
        return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text
    keyboard = [
        [InlineKeyboardButton("👦 ကျား", callback_data="Male"), InlineKeyboardButton("👧 မ", callback_data="Female")]
    ]
    await update.message.reply_text("သင်က ကျား လား? မ လား?", reply_markup=InlineKeyboardMarkup(keyboard))
    return GENDER

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['gender'] = query.data
    keyboard = [
        [InlineKeyboardButton("👦 ကျား", callback_data="Male"), InlineKeyboardButton("👧 မ", callback_data="Female"), InlineKeyboardButton("🌈 နှစ်မျိုးလုံး", callback_data="Both")]
    ]
    await query.edit_message_text("သင်က ဘယ်လိုဖူးစာရှင်ကို ရှာနေတာလဲ?", reply_markup=InlineKeyboardMarkup(keyboard))
    return LOOKING_FOR

async def get_looking_for(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['looking_for'] = query.data
    
    # အသက် တောင်းမယ့်အဆင့်
    await query.edit_message_text("သင့်အသက် ဘယ်လောက်ရှိပြီလဲ? (ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ၊ ဥပမာ - 20)")
    return AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['age'] = update.message.text
    
    # မြို့ တောင်းမယ့်အဆင့်
    await update.message.reply_text("သင်ဘယ်မြို့ကလဲ? (ဥပမာ - ရန်ကုန်, မန္တလေး)")
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
                "passed": [], # <--- (၁) ကိုယ့်ရဲ့ Pass စာရင်းကို အသစ်ပြန်ဖျက်ပေးမည်
                "is_editing": False 
            },
            "$setOnInsert": {
                "likes": [],     
                "matches": [],
                "hard_passed": [],
                "pass_counts": {},
                "coins": 5,          
                "last_daily": None,
                "is_verified": False 
            }
        },
        upsert=True
    )
    
    # -------------------------------------------------------------
    # (၂) သူများတွေရဲ့ Pass စာရင်းထဲကနေ ကိုယ့်ကို ပြန်ဖယ်ထုတ်ပေးမည်
    # (ဒါမှ ကိုယ့်ပုံအသစ်ကို သူတို့ ပြန်မြင်ရမှာ ဖြစ်ပါတယ်)
    # -------------------------------------------------------------
    await users_collection.update_many(
        {}, # User အကုန်လုံးဆီမှာ ရှာမယ်
        {"$pull": {"passed": user_id}} # passed array ထဲကနေ လက်ရှိ user_id ကို ဆွဲထုတ်ဖျက်ပစ်မယ်
    )
    
    await update.message.reply_text(
        "🎉 Profile အောင်မြင်စွာ တည်ဆောက်/ပြင်ဆင်ပြီးပါပြီ!\nအောက်ပါ Menu ခလုတ်များမှတစ်ဆင့် အလွယ်တကူ စတင်အသုံးပြုနိုင်ပါပြီ။",
        reply_markup=get_main_menu()
    )
    
    # Log Channel သို့ လူသစ်ရောက်ကြောင်း ဓာတ်ပုံနှင့် ပို့မည့်အပိုင်း
    username_str = f"@{update.message.from_user.username}" if update.message.from_user.username else "မရှိပါ"
    
    log_text = (
        f"🆕 <b>User Profile အသစ် / ပြင်ဆင်မှု!</b>\n"
        f"👤 အမည်: {context.user_data['name']}\n"
        f"💬 Username: {username_str}\n"
        f"🚻 ကျား/မ: {context.user_data['gender']}\n"
        f"📍 မြို့: {context.user_data['city']}\n"
        f"🆔 User ID: <code>{user_id}</code>"
    )
    await send_log(context, log_text, photo_id=photo_file_id)
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    
    # Profile ပြင်နေရင်း Cancel လုပ်ခဲ့ရင် Error မဖြစ်အောင် is_editing ကို False ပြန်ထားပေးမည်
    await users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"is_editing": False}}
    )
    
    # User မျက်စိမလည်သွားစေရန် Main Menu ကိုပါ တစ်ခါတည်း ပြန်ထုတ်ပေးပါမည်
    await update.message.reply_text(
        "❌ လုပ်ငန်းစဉ်ကို ရပ်ဆိုင်းလိုက်ပါပြီ။",
        reply_markup=get_main_menu() 
    )
    context.user_data.clear()
    return ConversationHandler.END
    
# --- (ဒီအောက်က Code လေးကို အသစ်ထပ်တိုးပါ) ---
async def prompt_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Profile ဖြည့်နေစဉ် တခြား Command နှိပ်မိပါက သတိပေးမည့် Function"""
    await update.message.reply_text(
        "⚠️ လုပ်ငန်းစဉ် မပြီးဆုံးသေးပါ။\n\n"
        "❌ ရပ်ဆိုင်းလိုပါက: /cancel ကို နှိပ်ပါ။\n"
        "🔄 အစကနေ ပြန်စလိုပါက: /start ကို နှိပ်ပါ။"
    )


# ==========================================
# 2. Matching Engine (Priority Logic ဖြင့်)
# ==========================================

async def show_next_profile(current_user, update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    seen_users = current_user.get('likes', []) + current_user.get('passed', []) + current_user.get('matches', []) + current_user.get('hard_passed', [])
    seen_users.append(current_user['user_id']) 
    
    base_query = {"user_id": {"$nin": seen_users}, "is_active": {"$ne": False}}
    if current_user['looking_for'] != "Both":
        base_query['gender'] = current_user['looking_for']
    base_query['looking_for'] = {"$in": [current_user['gender'], "Both"]}
    
    target_user = None

    if current_user.get('city') and current_user.get('age'):
        query_1 = base_query.copy()
        query_1['city'] = current_user['city']
        query_1['age'] = current_user['age']
        target_user = await users_collection.find_one(query_1)
        
    if not target_user and current_user.get('city'):
        query_2 = base_query.copy()
        query_2['city'] = current_user['city']
        target_user = await users_collection.find_one(query_2)

    if not target_user:
        target_user = await users_collection.find_one(base_query)
    
    if not target_user and current_user.get('passed'):
        second_chance_seen = current_user.get('likes', []) + current_user.get('matches', []) + current_user.get('hard_passed', [])
        second_chance_seen.append(current_user['user_id'])
        
        query_second = {"user_id": {"$nin": second_chance_seen}}
        if current_user['looking_for'] != "Both":
            query_second['gender'] = current_user['looking_for']
        query_second['looking_for'] = {"$in": [current_user['gender'], "Both"]}
        
        target_user = await users_collection.find_one(query_second)
        if target_user:
            await users_collection.update_one({"user_id": current_user['user_id']}, {"$set": {"passed": []}})

    # ... (အပေါ်က Code တွေက အရင်အတိုင်းပါ)
    if target_user:
        # သီးသန့် အကောင့်အခြေအနေ (Status) ဖန်တီးခြင်း
        status = "✅ အတည်ပြုပြီး (Verified User)" if target_user.get("is_verified") else "❌ အတည်မပြုရသေးပါ"
        
        caption = (
            f"👤 အမည်: {target_user['name']}, {target_user.get('age', '-')} နှစ်\n"
            f"📍 မြို့: {target_user.get('city', 'မသိပါ')}\n"
            f"🚻 ကျား/မ: {target_user['gender']}\n"
            f"🛡️ အကောင့်အခြေအနေ: {status}\n"
            f"📝 Bio: {target_user.get('bio', 'မရှိပါ')}"
        )
        keyboard = [
            [
                InlineKeyboardButton("❌ Pass", callback_data=f"pass_{target_user['user_id']}"),
                InlineKeyboardButton("❤️ Like", callback_data=f"like_{target_user['user_id']}")
            ],
            [
                InlineKeyboardButton("🌟 Super Like (3 Coins)", callback_data=f"superlike_{target_user['user_id']}")
            ],
            [
                InlineKeyboardButton("⚠️ Report တင်မည်", callback_data=f"report_{target_user['user_id']}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # (အပေါ်က Keyboard နဲ့ Caption အပိုင်းတွေက အရင်အတိုင်းပါ)
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if is_callback:
            try:
                await update.callback_query.message.delete()
            except: pass
            # msg ကို return ယူပါမယ်
            msg = await context.bot.send_photo(
                chat_id=update.callback_query.message.chat_id,
                photo=target_user['photo_id'],
                caption=caption,
                reply_markup=reply_markup
            )
        else:
            # msg ကို return ယူပါမယ်
            msg = await update.message.reply_photo(photo=target_user['photo_id'], caption=caption, reply_markup=reply_markup)
            
        # -------------------------------------------------------------
        # ပို့လိုက်တဲ့ Message ID နဲ့ User ID ကို နောက်တစ်ခါ ဖျက်ဖို့/Pass ဖို့ မှတ်ထားမယ်
        # -------------------------------------------------------------
        context.user_data['last_match_msg_id'] = msg.message_id
        context.user_data['last_viewed_user_id'] = target_user['user_id']

    # Empty States: လူမရှိတော့လျှင် Profile ပြင်ရန် တိုက်တွန်းမည့်အပိုင်း
    # -------------------------------------------------------------
    else:
        text = (
            "🏜️ <b>လောလောဆယ် သင့်အတွက် ကိုက်ညီမယ့်သူ ကုန်သွားပါပြီ!</b>\n\n"
            "💡 <b>အကြံပြုချက်:</b> သင့် Profile ဓာတ်ပုံကို ပိုမိုက်တဲ့ပုံ ပြောင်းခြင်း၊ မြို့နှင့် အချက်အလက်များ ပြင်ဆင်ခြင်းဖြင့် လူသစ်များနှင့် Match ပိုရနိုင်ပါတယ်။"
        )
        # Profile ပြင်ရန် Button ကို တစ်ခါတည်း ထည့်ပေးထားမည်
        keyboard = [[InlineKeyboardButton("✏️ Profile ပြင်ဆင်မည်", callback_data="edit_profile")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if is_callback:
            await update.callback_query.message.delete()
            await context.bot.send_message(chat_id=update.callback_query.message.chat_id, text=text, parse_mode="HTML", reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)

async def match_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/match (သို့) 🔍 Match ရှာမည် နှိပ်လျှင် အလုပ်လုပ်မည့် Function"""
    user_id = update.message.from_user.id
    current_user = await users_collection.find_one({"user_id": user_id})
    
    if not current_user:
        await update.message.reply_text("သင့်မှာ Profile မရှိသေးပါ။ /start ကိုနှိပ်ပြီး အရင်ဖန်တီးပါ။")
        return

    # -------------------------------------------------------------
    # UX မြှင့်တင်ခြင်း: Chat ရှင်းလင်းရေး နှင့် Auto-Pass စနစ်
    # -------------------------------------------------------------
    # ယခင်ပြထားတဲ့ Profile ရှိနေရင် Chat ရှုပ်မနေအောင် အရင်ဖျက်မယ်
    if 'last_match_msg_id' in context.user_data:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=context.user_data['last_match_msg_id'])
        except Exception:
            pass # ဖျက်ပြီးသားဖြစ်နေရင် ကျော်သွားမယ်
            
        # Like/Pass မနှိပ်ဘဲ Match ကို ထပ်နှိပ်ရင် "Pass" လုပ်တယ်လို့ အလိုအလျောက် သတ်မှတ်မယ် (နောက်တစ်ယောက်ကို ပြောင်းပြအောင်လို့ပါ)
        if 'last_viewed_user_id' in context.user_data:
            last_viewed_id = context.user_data['last_viewed_user_id']
            target_str_id = str(last_viewed_id)
            
            await users_collection.update_one(
                {"user_id": user_id},
                {
                    "$addToSet": {"passed": last_viewed_id},
                    "$inc": {f"pass_counts.{target_str_id}": 1}
                }
            )
            
            # ၃ ခါပြည့်စစ်ဆေးခြင်း
            updated_user = await users_collection.find_one({"user_id": user_id})
            pass_count = updated_user.get("pass_counts", {}).get(target_str_id, 0)
            if pass_count >= 3:
                await users_collection.update_one(
                    {"user_id": user_id}, 
                    {"$addToSet": {"hard_passed": last_viewed_id}}
                )
                
    # Auto-pass လုပ်ပြီးသွားတဲ့ Database အသစ်ကို ပြန်ခေါ်မယ်
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
        
        # Database တွင် is_banned ကို True လုပ်ပြီး is_active ကို False လုပ်မည် (Match များတွင် မပေါ်တော့ရန်)
        await users_collection.update_one({"user_id": target_user_id}, {"$set": {"is_banned": True, "is_active": False}})
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n🚫 <b>BANNED (အကောင့်ပိတ်လိုက်ပါပြီ)</b>", parse_mode="HTML")
        
        try: # ပိတ်ခံရသူထံသို့ အသိပေးစာပို့မည်
            await context.bot.send_message(chat_id=target_user_id, text="🚫 <b>သင့်အကောင့်သည် စည်းမျဉ်းချိုးဖောက်မှုများကြောင့် Shwe Phusar မှ ပိတ်ပင်ခံလိုက်ရပါသည်။</b>", parse_mode="HTML")
        except: pass
        return

    # --- (၂) REPORT LOGIC ---
    if action == "report":
        target_user = await users_collection.find_one({"user_id": target_user_id})
        
        # User တစ်ယောက်က တစ်ခါပဲ Report လို့ရအောင် တားမည်
        if current_user_id in target_user.get("reported_by", []):
            await query.answer("⚠️ ဤအကောင့်ကို သင် Report တင်ထားပြီးပါပြီ။", show_alert=True)
        else:
            await users_collection.update_one(
                {"user_id": target_user_id},
                {"$inc": {"report_count": 1}, "$addToSet": {"reported_by": current_user_id}}
            )
            await query.answer("✅ Report တင်ခြင်း အောင်မြင်ပါသည်။ Admin မှ စစ်ဆေးပေးပါမည်။", show_alert=True)
            
            # Admin ထံသို့ သတင်းလှမ်းပို့မည်
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
                
        # Report တင်ပြီးသည်နှင့် ထိုသူကို မမြင်ရတော့အောင် Pass ခလုတ်နှိပ်သကဲ့သို့ အလိုအလျောက် ပြောင်းပေးမည်
        action = "pass"

    if action == "superlike":
        if current_user.get("coins", 0) < 3:
            await query.answer("❌ Super Like ပေးရန် Coin ၃ ခု လိုအပ်ပါသည်။ /daily နှိပ်၍ အခမဲ့ရယူပါ။", show_alert=True)
            return
        await users_collection.update_one({"user_id": current_user_id}, {"$inc": {"coins": -3}})
        await query.answer("🌟 Super Like အောင်မြင်စွာ ပို့လိုက်ပါပြီ!", show_alert=True)
    else:
        await query.answer()

    if action == "pass":
        target_str_id = str(target_user_id)
        await users_collection.update_one(
            {"user_id": current_user_id},
            {
                "$addToSet": {"passed": target_user_id},
                "$inc": {f"pass_counts.{target_str_id}": 1}
            }
        )
        updated_user = await users_collection.find_one({"user_id": current_user_id})
        pass_count = updated_user.get("pass_counts", {}).get(target_str_id, 0)
        
        if pass_count >= 3:
            await users_collection.update_one({"user_id": current_user_id}, {"$addToSet": {"hard_passed": target_user_id}})

    elif action in ["like", "superlike"]:
        await users_collection.update_one({"user_id": current_user_id}, {"$addToSet": {"likes": target_user_id}})
        
        target_user = await users_collection.find_one({"user_id": target_user_id})
        is_match = target_user and current_user_id in target_user.get("likes", [])

        if is_match:
            await users_collection.update_one({"user_id": current_user_id}, {"$addToSet": {"matches": target_user_id}})
            await users_collection.update_one({"user_id": target_user_id}, {"$addToSet": {"matches": current_user_id}})
            
            target_username = f"@{target_user['username']}" if target_user.get('username') else f"<a href='tg://user?id={target_user['user_id']}'>{target_user['name']}</a>"
            await context.bot.send_message(chat_id=current_user_id, text=f"🎉 <b>Match ဖြစ်သွားပါပြီ!</b>\nသင်နဲ့ {target_user['name']} တို့ နှစ်ဦးသဘောတူ Match ဖြစ်သွားပါပြီ。\nစကားသွားပြောရန်: {target_username}", parse_mode="HTML")
            
            current_username = f"@{current_user['username']}" if current_user.get('username') else f"<a href='tg://user?id={current_user['user_id']}'>{current_user['name']}</a>"
            try:
                await context.bot.send_message(chat_id=target_user_id, text=f"🎉 <b>Match အသစ် ရပါပြီ!</b>\n{current_user['name']} နဲ့ သင်တို့ နှစ်ဦးသဘောတူ Match ဖြစ်သွားပါပြီ。\nစကားသွားပြောရန်: {current_username}", parse_mode="HTML")
            except Forbidden:
                # Bot ကို Block ထားပါက Database တွင် အမှတ်အသားပြုမည်
                await users_collection.update_one({"user_id": target_user_id}, {"$set": {"is_active": False}})
            except: pass

            # -------------------------------------------------------------
            # Log Channel သို့ Match ဖြစ်ကြောင်း ပို့မည့်အပိုင်း
            curr_uname = f"@{current_user['username']}" if current_user.get('username') else "မရှိပါ"
            tgt_uname = f"@{target_user['username']}" if target_user.get('username') else "မရှိပါ"
            
            log_text = (
                f"💞 <b>Match အသစ် ဖြစ်သွားပါပြီ!</b>\n"
                f"1️⃣ {current_user['name']} ({curr_uname}) - <code>{current_user_id}</code>\n"
                f"2️⃣ {target_user['name']} ({tgt_uname}) - <code>{target_user_id}</code>"
            )
            # Match ဖြစ်သူ နှစ်ယောက်ထဲမှ လက်ရှိ Action ယူသူ၏ ပုံကို ပူးတွဲပို့ပါမည်
            await send_log(context, log_text, photo_id=current_user['photo_id'])

        elif action == "superlike":
            status = "✅ အတည်ပြုပြီး (Verified User)" if current_user.get("is_verified") else "❌ အတည်မပြုရသေးပါ"
            caption = (
                f"🌟 <b>WOW! သင့်ကို တစ်စုံတစ်ယောက်က Super Like 🌟 ပေးလိုက်ပါတယ်။</b>\n\n"
                f"👤 အမည်: {current_user['name']}, {current_user.get('age', '-')} နှစ်\n"
                f"📍 မြို့: {current_user.get('city', 'မသိပါ')}\n"
                f"🚻 ကျား/မ: {current_user['gender']}\n"
                f"🛡️ အကောင့်အခြေအနေ: {status}\n"
                f"📝 Bio: {current_user.get('bio', 'မရှိပါ')}"
            )
            keyboard = [
                [
                    InlineKeyboardButton("❌ Pass", callback_data=f"pass_{current_user_id}"),
                    InlineKeyboardButton("❤️ Match ပြန်လုပ်မည်", callback_data=f"like_{current_user_id}")
                ]
            ]
            try:
                await context.bot.send_photo(
                    chat_id=target_user_id,
                    photo=current_user['photo_id'],
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML"
                )
            except Forbidden:
                await users_collection.update_one({"user_id": target_user_id}, {"$set": {"is_active": False}})
            except Exception as e:
                logger.error(f"Failed to send superlike notification to {target_user_id}: {e}")
                
    await context.bot.send_chat_action(chat_id=current_user_id, action=ChatAction.TYPING)
    
    current_user_updated = await users_collection.find_one({"user_id": current_user_id})
    await show_next_profile(current_user_updated, update, context, is_callback=True)

# ==========================================
# 3. My Profile System
# ==========================================

async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    # --- "sending photo..." လေး ပြပေးမည့် အပိုင်း ---
    await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.UPLOAD_PHOTO)
    
    user = await users_collection.find_one({"user_id": user_id})
    
    if not user:
        await update.message.reply_text("သင့်မှာ Profile မရှိသေးပါ။ /start ကိုနှိပ်ပြီး အရင်ဖန်တီးပါ။")
        return
        
    # သီးသန့် အကောင့်အခြေအနေ (Status) ဖန်တီးခြင်း
    status = "✅ အတည်ပြုပြီး (Verified User)" if user.get("is_verified") else "❌ အတည်မပြုရသေးပါ"
    
    caption = (
        f"🌟 **သင့်ရဲ့ လက်ရှိ Profile** 🌟\n\n"
        f"👤 အမည်: {user['name']} ({user.get('age', '-')} နှစ်)\n"
        f"📍 မြို့: {user.get('city', 'မသိပါ')}\n"
        f"🚻 ကျား/မ: {user['gender']}\n"
        f"🛡️ အကောင့်အခြေအနေ: {status}\n"
        f"🔍 ရှာဖွေနေသူ: {user['looking_for']}\n"
        f"📝 Bio: {user.get('bio', 'မရှိပါ')}"
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
        "age": "🎂 သင့်အသက်အသစ်ကို ဂဏန်းဖြင့် ရိုက်ထည့်ပါ။ (ဥပမာ - 22)",
        "city": "📍 သင်ယခုနေထိုင်သည့် မြို့အမည်သစ်ကို ရိုက်ထည့်ပါ။",
        "bio": "📝 သင့်အကြောင်း Bio အသစ်ကို ရေးပေးပါ။",
        "photo": "📸 သင့် Profile ဓာတ်ပုံအသစ်ကို ပို့ပေးပါ။ (Photo အနေဖြင့်ပို့ပါ)"
    }
    
    await query.message.edit_text(prompts[choice])
    return PARTIAL_PHOTO if choice == "photo" else PARTIAL_TEXT

async def receive_partial_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """စာသားအသစ် ပြင်ဆင်ခြင်းကို Database တွင် သိမ်းမည့် Function"""
    user_id = update.message.from_user.id
    field = context.user_data.get('edit_field')
    new_text = update.message.text
    
    if field == "name":
        # နာမည်တွင် ✅ အတုများ မပါစေရန် စစ်ထုတ်မည်
        new_text = new_text.replace("✅", "").replace("✔️", "").strip()
        
    await users_collection.update_one({"user_id": user_id}, {"$set": {field: new_text}})
    
    await update.message.reply_text("✅ အောင်မြင်စွာ ပြင်ဆင်ပြီးပါပြီ။", reply_markup=get_main_menu())
    await my_profile(update, context) # ပြင်ပြီးသား Profile ကို ချက်ချင်း ပြန်ပြပေးမည်
    context.user_data.clear()
    return ConversationHandler.END

async def receive_partial_edit_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ဓာတ်ပုံအသစ် ပြင်ဆင်ခြင်းကို Database တွင် သိမ်းမည့် Function"""
    user_id = update.message.from_user.id
    photo_file_id = update.message.photo[-1].file_id
    
    await users_collection.update_one({"user_id": user_id}, {"$set": {"photo_id": photo_file_id}})
    
    # ဓာတ်ပုံအသစ်တင်လိုက်ပါက သူများတွေဆီမှာ ပြန်ပေါ်စေရန် Pass လုပ်ထားသော စာရင်းထဲမှ ဖယ်ထုတ်မည်
    await users_collection.update_many({}, {"$pull": {"passed": user_id}})
    
    await update.message.reply_text("✅ ဓာတ်ပုံအသစ်ကို အောင်မြင်စွာ ပြောင်းလဲပြီးပါပြီ။", reply_markup=get_main_menu())
    await my_profile(update, context)
    context.user_data.clear()
    return ConversationHandler.END
    
async def get_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin မှ User စာရင်းနှင့် အရေအတွက်ကို txt ဖိုင်ဖြင့် ထုတ်ယူမည့် Function (/user)"""
    user_id = update.message.from_user.id
    
    # Admin ဟုတ်/မဟုတ် စစ်ဆေးခြင်း
    if str(user_id) != str(ADMIN_ID):
        await update.message.reply_text("⛔Access Denied!")
        return

    # Database ထဲက User အရေအတွက်ကိုသာ အရင်ရေတွက်ခြင်း
    total_users = await users_collection.count_documents({})

    if total_users == 0:
        await update.message.reply_text("လောလောဆယ် Bot အသုံးပြုသူ မရှိသေးပါ။")
        return

    # Memory မစားစေရန် BytesIO ဖိုင်ထဲသို့ တိုက်ရိုက်ရေးထည့်ခြင်း
    txt_file = io.BytesIO()
    header = f"=== LeoMatch Bot Users List ===\nTotal Users: {total_users}\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" + "=" * 40 + "\n\n"
    txt_file.write(header.encode('utf-8'))

    # async for ကိုသုံး၍ Database မှ Data များကို တစ်ကြောင်းချင်းစီသာ ဆွဲထုတ်ဖတ်ခြင်း
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

    # ဖိုင်ကို အစကနေ ပြန်ဖတ်နိုင်ရန် ညွှန်းတံကို အစသို့ ပြန်ရွှေ့ခြင်း
    txt_file.seek(0)
    txt_file.name = "bot_users_list.txt"

# ==========================================
# 4. Admin Feature (Broadcast System)
# ==========================================

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin မှ User အားလုံးထံ Media အစုံနှင့် Text များကို /broadcast လုပ်မယ့် Function"""
    user_id = update.message.from_user.id
    
    # Admin ဟုတ်/မဟုတ် စစ်ဆေးခြင်း
    if str(user_id) != str(ADMIN_ID):
        await update.message.reply_text("⛔Access Denied")
        return

    # Reply လုပ်ထားတဲ့ Message ဟုတ်/မဟုတ် စစ်ဆေးခြင်း
    reply_to_msg = update.message.reply_to_message

    # Reply လည်းမလုပ်ထားဘူး၊ နောက်မှာလည်း စာသားမပါဘူးဆိုရင် Error ပြမယ်
    if not reply_to_msg and not context.args:
        await update.message.reply_text(
            "⚠️ <b>အသုံးပြုပုံ မှားယွင်းနေပါတယ်။</b>\n\n"
            "<b>နည်းလမ်း (၁):</b> ပို့လိုသော စာသား၊ ပုံ (သို့) ဗီဒီယိုကို Reply ပြန်ပြီး <code>/broadcast</code> ဟု ရိုက်ပါ။ (မီဒီယာအားလုံးပို့ရန်)\n"
            "<b>နည်းလမ်း (၂):</b> <code>/broadcast [ပို့လိုသောစာသား]</code> ဟု တိုက်ရိုက်ရိုက်ပါ။",
            parse_mode="HTML"
        )
        return

    # Database ထဲက အမှန်တကယ် Active ဖြစ်နေတဲ့ User အရေအတွက်ကိုသာ ရေတွက်ခြင်း
    total_users = await users_collection.count_documents({"is_active": {"$ne": False}})
    success_count = 0
    
    # ပို့နေကြောင်း Status အရင်ပြထားမယ် (ကြာသွားရင် စိတ်မပူအောင်လို့ပါ)
    status_msg = await update.message.reply_text(f"📣 Broadcast စတင်ပို့ဆောင်နေပါသည်...\nစုစုပေါင်း User အရေအတွက်: {total_users} ဦး")

    # Memory မစားစေရန် async for ဖြင့် တစ်ယောက်ချင်းစီသာ ဆွဲထုတ်ခြင်း
    async for user in users_collection.find({"is_active": {"$ne": False}}):
        try:
            if reply_to_msg:
                # Reply လုပ်ပြီး ပို့တာဆိုရင် copy_message ကို သုံးပါမယ် (ပုံ, ဗီဒီယို, File, Text အားလုံးရပါတယ်)
                await context.bot.copy_message(
                    chat_id=user["user_id"],
                    from_chat_id=update.message.chat_id,
                    message_id=reply_to_msg.message_id
                )
            else:
                # Text သီးသန့် ပို့တာဆိုရင်
                broadcast_text = " ".join(context.args)
                await context.bot.send_message(
                    chat_id=user["user_id"],
                    text=f"📢 <b>Admin အသိပေးချက်</b>\n\n{broadcast_text}",
                    parse_mode="HTML"
                )
            success_count += 1
        except Forbidden:
            # User မှ Bot ကို Block ထားခြင်းဖြစ်၍ Database တွင် ပိတ်ထားမည်
            await users_collection.update_one({"user_id": user["user_id"]}, {"$set": {"is_active": False}})
            logger.warning(f"User {user['user_id']} blocked the bot. Marked as inactive.")
        except Exception as e:
            logger.error(f"Broadcast ပို့ရန် အဆင်မပြေပါ User ID {user['user_id']}: {e}")

    # ပို့ပြီးသွားရင် Status ကို Update ပြန်လုပ်ပေးမယ်
    await status_msg.edit_text(f"✅ Broadcast ပို့ဆောင်မှု ပြီးဆုံးပါပြီ။\nအောင်မြင်စွာပို့နိုင်ခဲ့သူ: {success_count}/{total_users} ဦး")

# ==========================================
# 5. Premium / Coin Features (See Who Liked You)
# ==========================================

async def check_likes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """👀 လျှို့ဝှက် Like များ ကို နှိပ်လျှင် အလုပ်လုပ်မည့် Function"""
    user_id = update.message.from_user.id
    
    # --- "typing..." လေး ပြပေးမည့် အပိုင်း ---
    await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
    
    current_user = await users_collection.find_one({"user_id": user_id})

    if not current_user:
        await update.message.reply_text("သင့်မှာ Profile မရှိသေးပါ။ /start ကိုနှိပ်ပါ။")
        return

    # ကိုယ့်ကို Like ထားပြီး ကိုယ်က ပြန်မ Like, မ Pass ရသေးတဲ့သူတွေကို ရှာမယ်
    seen_by_me = current_user.get('likes', []) + current_user.get('passed', []) + current_user.get('matches', [])
    
    # အရေအတွက်ကိုပဲ အရင်ရေတွက်မယ်
    likers_count = await users_collection.count_documents({
        "likes": user_id,
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

    if coins < 1:
        await query.message.edit_text("❌ Coin မလောက်ပါ။ /daily ကိုနှိပ်ပြီး နေ့စဉ်အခမဲ့ Coin ရယူနိုင်ပါတယ်။")
        return

    seen_by_me = current_user.get('likes', []) + current_user.get('passed', []) + current_user.get('matches', [])
    
    pending_likers_cursor = users_collection.find({
        "likes": user_id,
        "user_id": {"$nin": seen_by_me}
    }).limit(5)
    
    likers = await pending_likers_cursor.to_list(length=None)

    if not likers:
        await query.message.edit_text("😔 လောလောဆယ် ပြစရာလူ မရှိတော့ပါ။")
        return

    await users_collection.update_one({"user_id": user_id}, {"$inc": {"coins": -1}})

    await query.message.delete()
    await context.bot.send_message(
        chat_id=user_id,
        text=f"✅ <b>Coin 1 ခု သုံးပြီး သင့်ကို Like ထားသူ ({len(likers)}) ယောက်ကို ဖွင့်ပြလိုက်ပါပြီ!</b>\n(လက်ကျန် Coin: {coins - 1} စေ့)",
        parse_mode="HTML"
    )

    for liker in likers:
        # သီးသန့် အကောင့်အခြေအနေ (Status) ဖန်တီးခြင်း
        status = "✅ အတည်ပြုပြီး (Verified User)" if liker.get("is_verified") else "❌ အတည်မပြုရသေးပါ"
        
        caption = (
            f"💖 <b>ဒီသူက သင့်ကို Like ပေးထားပါတယ်!</b> 💖\n\n"
            f"👤 အမည်: {liker['name']}, {liker.get('age', '-')} နှစ်\n"
            f"📍 မြို့: {liker.get('city', 'မသိပါ')}\n"
            f"🚻 ကျား/မ: {liker['gender']}\n"
            f"🛡️ အကောင့်အခြေအနေ: {status}\n"
            f"📝 Bio: {liker.get('bio', 'မရှိပါ')}"
        )
        keyboard = [
            [
                InlineKeyboardButton("❌ Pass", callback_data=f"pass_{liker['user_id']}"),
                InlineKeyboardButton("❤️ Match ပြန်လုပ်မည်", callback_data=f"like_{liker['user_id']}")
            ],
            [
                InlineKeyboardButton("🌟 Super Like (3 Coins)", callback_data=f"superlike_{liker['user_id']}")
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
    """/daily နှိပ်လျှင် နေ့စဉ် အခမဲ့ Coin 1 ခု ပေးမည့် Function"""
    user_id = update.message.from_user.id
    current_user = await users_collection.find_one({"user_id": user_id})
    
    if not current_user:
        await update.message.reply_text("သင့်မှာ Profile မရှိသေးပါ။ /start ကိုနှိပ်ပါ။")
        return

    now = datetime.utcnow()
    last_daily = current_user.get("last_daily")

    # 24 နာရီ ပြည့်/မပြည့် စစ်ဆေးခြင်း
    if last_daily and (now - last_daily).days < 1:
        next_time = last_daily + timedelta(days=1)
        hours_left = int((next_time - now).total_seconds() // 3600)
        await update.message.reply_text(f"⏳ ယနေ့အတွက် Coin ရယူပြီးပါပြီ။ နောက်ထပ် {hours_left} နာရီ နေမှ ပြန်ယူလို့ရပါမယ်။ Coin ဝယ်ယူရန် @moviestoreadmin")
        return

    # Coin ၁ ခု တိုးပေးပြီး အချိန်မှတ်မယ်
    await users_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"coins": 1}, "$set": {"last_daily": now}}
    )
    new_coins = current_user.get('coins', 0) + 1
    await update.message.reply_text(f"🎁 နေ့စဉ်လက်ဆောင် 1 Coin ရရှိပါသည်! ယခု လက်ကျန်: {new_coins} Coin")

# ==========================================
# 6. Help Command & Bot Menu Setup
# ==========================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/help နှိပ်လျှင် အသုံးပြုနည်း လမ်းညွှန်ပြသမည့် Function"""
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
    """Bot စတင်သည်နှင့် Menu Button ကို အလိုအလျောက် သတ်မှတ်ပေးမည့် Function"""
    commands = [
        BotCommand("start", "Bot ကို စတင်ရန် (သို့) Profile ဖွင့်ရန်"),
        BotCommand("match", "ကိုက်ညီမည့်သူများကို ရှာဖွေရန် 💖"),
        BotCommand("myprofile", "မိမိ၏ Profile ကိုကြည့်ရန် / ပြင်ရန် 👤"),
        BotCommand("likes", "မိမိကို Like ထားသူများကို ကြည့်ရန် 👀"),
        BotCommand("daily", "နေ့စဉ် အခမဲ့ Coin ယူရန် 🎁"),
        BotCommand("verify", "အကောင့်အစစ်ဖြစ်ကြောင်း Blue Tick ✅ ယူရန်"), # <--- အသစ်ပါလာတဲ့စာကြောင်း
        BotCommand("help", "အသုံးပြုနည်း လမ်းညွှန်ဖတ်ရန် ❓"),
    ]
    await application.bot.set_my_commands(commands)
# ==========================================
# 7. Blue Tick Verification System (✅)
# ==========================================
VERIFY_PHOTO_STATE = 100 # Verification အတွက် သီးသန့် State

async def verify_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User မှ /verify ဟု ရိုက်လိုက်လျှင် Selfie တောင်းမည့် Function"""
    user_id = update.message.from_user.id
    user = await users_collection.find_one({"user_id": user_id})
    
    if not user:
        await update.message.reply_text("သင့်မှာ Profile မရှိသေးပါ။ /start ကိုနှိပ်ပါ။")
        return ConversationHandler.END
        
    if user.get("is_verified"):
        await update.message.reply_text("✅ သင့်အကောင့်က Verified ဖြစ်ပြီးသားပါ။ ထပ်လုပ်ရန်မလိုအပ်တော့ပါ။")
        return ConversationHandler.END
        
    await update.message.reply_text(
        "📸 <b>အကောင့်အစစ်ဖြစ်ကြောင်း အတည်ပြုခြင်း (Blue Tick Verification)</b>\n\n"
        "ကျေးဇူးပြု၍ သင့်မျက်နှာ သေချာပေါ်လွင်ပြီး <b>လက်နှစ်ချောင်း (✌️) ထောင်ထားသော ဆဲလ်ဖီ (Selfie) ပုံ</b> တစ်ပုံကို ပို့ပေးပါ။\n\n"
        "<i>(Note: This image will not be visible to anyone except the admin. Privacy is fully guaranteed.)</i>",
        parse_mode="HTML"
    )
    return VERIFY_PHOTO_STATE

async def receive_verify_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User ပို့လိုက်သော Selfie ကို လက်ခံပြီး Admin ထံ ပို့မည့် Function"""
    photo_file_id = update.message.photo[-1].file_id
    user_id = update.message.from_user.id
    user = await users_collection.find_one({"user_id": user_id})

    # -------------------------------------------------------------
    # Username ကို ဆွဲထုတ်မည့်အပိုင်း (အသစ်ထပ်တိုးထားသည်)
    # -------------------------------------------------------------
    username_str = f"@{update.message.from_user.username}" if update.message.from_user.username else "မရှိပါ"

    # Admin ဆီကို Approve/Reject ခလုတ်နဲ့ လှမ်းပို့မယ်
    keyboard = [
        [
            InlineKeyboardButton("✅ လက်ခံမည်", callback_data=f"verify_approve_{user_id}"),
            InlineKeyboardButton("❌ ပယ်ချမည်", callback_data=f"verify_reject_{user_id}")
        ]
    ]
    
    # -------------------------------------------------------------
    # Caption ထဲမှာ Username ပါ ထည့်ရေးပါမယ် (အသစ်ပြင်ထားသည်)
    # -------------------------------------------------------------
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
        await update.message.reply_text("⏳ သင့်ပုံကို Admin ထံသို့ စစ်ဆေးရန် ပို့လိုက်ပါပြီ။ အတည်ပြုချက်ရပါက အကြောင်းကြားပေးပါမည်။")
    except Exception as e:
        logger.error(f"Error sending verify photo to admin: {e}")
        await update.message.reply_text("⚠️ တောင်းပန်ပါတယ်။ စနစ်ချို့ယွင်းမှုဖြစ်ပေါ်နေပါတယ်။ Admin ID မှန်မမှန် ပြန်စစ်ပါ။")
        
    return ConversationHandler.END

async def verify_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verification ကို Cancel လုပ်လျှင်"""
    await update.message.reply_text("Verification လုပ်ငန်းစဉ်ကို ရပ်ဆိုင်းလိုက်ပါပြီ။")
    return ConversationHandler.END

async def handle_verify_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin မှ Approve သို့မဟုတ် Reject နှိပ်လျှင် အလုပ်လုပ်မည့် Function"""
    query = update.callback_query
    
    # Admin သာ နှိပ်ခွင့်ရှိအောင် တားထားမယ်
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
            
            # --- Partial Edit အတွက် အသစ်တိုးလာမည့် အပိုင်း ---
            EDIT_CHOICE: [CallbackQueryHandler(handle_edit_choice, pattern="^edit_opt_")],
            PARTIAL_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_partial_edit_text)],
            PARTIAL_PHOTO: [MessageHandler(filters.PHOTO, receive_partial_edit_photo)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.COMMAND, prompt_cancel) # <--- အခြား Command နှိပ်မိလျှင် သတိပေးမည်
        ],
        allow_reentry=True # <--- အရေးကြီးဆုံး (အချိန်မရွေး /start ဖြင့် ပြန်စခွင့်ပေးသည်)
    )
    application.add_handler(conv_handler)
    
    # -------------------------------------------------------------
    # ၂။ Blue Tick Verification Handler (အစားထိုးရန်)
    # -------------------------------------------------------------
    verify_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("verify", verify_start),
            MessageHandler(filters.Regex("^✅ အကောင့်အတည်ပြုရန်$"), verify_start)
        ],
        states={
            VERIFY_PHOTO_STATE: [MessageHandler(filters.PHOTO, receive_verify_photo)],
        },
        fallbacks=[
            CommandHandler("cancel", verify_cancel),
            MessageHandler(filters.COMMAND, prompt_cancel) # <--- အခြား Command နှိပ်မိလျှင် သတိပေးမည်
        ],
        allow_reentry=True # <--- အရေးကြီးဆုံး (အချိန်မရွေး ပြန်စခွင့်ပေးသည်)
    )
    application.add_handler(verify_conv_handler)

    # Match Command နဲ့ Like/Pass Action 
    application.add_handler(CommandHandler("match", match_command))
    application.add_handler(CallbackQueryHandler(handle_action, pattern="^(like_|pass_|superlike_|report_|ban_)"))
    
    # My Profile Commands 
    application.add_handler(CommandHandler("myprofile", my_profile))
    
    # Admin Features
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("user", get_users_list))
    
    # Coins and Gamification
    application.add_handler(CommandHandler("likes", check_likes_command))
    application.add_handler(CallbackQueryHandler(handle_reveal_like, pattern="^reveal_like$"))
    application.add_handler(CommandHandler("daily", daily_reward))

    # Main Menu Button Handlers (အမြဲတမ်းပေါ်နေသော ခလုတ်များအတွက်)
    # -------------------------------------------------------------
    application.add_handler(MessageHandler(filters.Regex("^🔍 Match ရှာမည် 💖$"), match_command))
    application.add_handler(MessageHandler(filters.Regex("^👤 ကျွန်ုပ်၏ Profile$"), my_profile))
    application.add_handler(MessageHandler(filters.Regex("^👀 လျှို့ဝှက် Like များ$"), check_likes_command))
    application.add_handler(MessageHandler(filters.Regex("^🎁 နေ့စဉ် Coin ယူမည်$"), daily_reward))
    
    # Help Menu
    application.add_handler(CommandHandler("help", help_command))

    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

# ဤအပိုင်းသည် Bot ကို စတင်အလုပ်လုပ်စေသော အဓိက Code ဖြစ်ပါသည်
if __name__ == "__main__":
    main()
