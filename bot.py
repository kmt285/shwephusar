import os
import logging
import io
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database Setup
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client.match_bot_db
users_collection = db.users

# Conversation States (AGE နဲ့ CITY ထပ်တိုးထားပါတယ်)
NAME, GENDER, LOOKING_FOR, AGE, CITY, BIO, PHOTO = range(7)

# ==========================================
# 1. Registration Flow
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.from_user.username:
        await update.message.reply_text(
            "⚠️ သင့်အကောင့်မှာ Telegram Username မရှိသေးပါ။\n"
            "Match ဖြစ်တဲ့အခါ အခြားသူများက သင့်ကို ဆက်သွယ်နိုင်ရန် Settings > Username မှာ အရင်သွားရောက် သတ်မှတ်ပေးပါ။\n\n"
            "သတ်မှတ်ပြီးပါက /start ကို ပြန်နှိပ်ပါ။"
        )
        return ConversationHandler.END
        
    user_id = update.message.from_user.id
    existing_user = await users_collection.find_one({"user_id": user_id})
    
    # User လည်းရှိတယ်၊ Edit လုပ်နေတာလည်း မဟုတ်ဘူးဆိုရင်သာ တားပါမယ်
    if existing_user and not existing_user.get("is_editing", False):
        await update.message.reply_text(
            f"မင်္ဂလာပါ {existing_user['name']} ခင်ဗျာ။ သင်က Profile ရှိပြီးသားဖြစ်ပါတယ်။ ဖူးစာရှင်ရှာဖို့ /match ကို နှိပ်ပါ။"
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
    
    # အသစ်ထည့်တာ (insert_one) အစား Update လုပ်တာ (update_one) ကို ပြောင်းသုံးပါမယ်
    await users_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                # $set ထဲက အချက်အလက်တွေက Profile ပြင်တိုင်း အမြဲတမ်း Update ဖြစ်ပါမယ်
                "username": update.message.from_user.username,
                "name": context.user_data['name'],
                "gender": context.user_data['gender'],
                "looking_for": context.user_data['looking_for'],
                "age": context.user_data['age'],
                "city": context.user_data['city'],
                "bio": context.user_data['bio'],
                "photo_id": photo_file_id,
                "is_editing": False  # Edit လုပ်တာ ပြီးဆုံးသွားပြီဖြစ်ကြောင်း မှတ်သားမယ်
            },
            "$setOnInsert": {
                # $setOnInsert ကတော့ ပထမဆုံးအကြိမ် Bot ကို စသုံးတဲ့သူတွေအတွက် "တစ်ကြိမ်" သာ အလုပ်လုပ်ပါမယ်
                "likes": [],     
                "passed": [],    
                "matches": [],
                "hard_passed": [],   
                "pass_counts": {},
                "coins": 5,         
                "last_daily": None
                "is_verified": False
            }
        },
        upsert=True # User မရှိရင် အသစ်တည်ဆောက်မယ်၊ ရှိရင် Update လုပ်မယ်လို့ အဓိပ္ပာယ်ရပါတယ်
    )
    
    await update.message.reply_text("🎉 Profile အောင်မြင်စွာ တည်ဆောက်ပြီးပါပြီ!\nဖူးစာရှင် စတင်ရှာဖွေရန် : /match ကိုနှိပ်ပါ။")
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Profile ဖန်တီးခြင်းကို ရပ်ဆိုင်းလိုက်ပါပြီ။")
    context.user_data.clear()
    return ConversationHandler.END


# ==========================================
# 2. Matching Engine (Priority Logic ဖြင့်)
# ==========================================

async def show_next_profile(current_user, update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    seen_users = current_user.get('likes', []) + current_user.get('passed', []) + current_user.get('matches', []) + current_user.get('hard_passed', [])
    seen_users.append(current_user['user_id']) 
    
    base_query = {"user_id": {"$nin": seen_users}}
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

    if target_user:
        # ✅ ပါ/မပါ စစ်ဆေးပြီး နာမည်ဘေးမှာ ကပ်မယ့်အပိုင်း
        verified_mark = " ✅" if target_user.get("is_verified") else ""
        caption = (
            f"👤 အမည်: {target_user['name']}{verified_mark}, {target_user.get('age', '-')} နှစ်\n"
            f"📍 မြို့: {target_user.get('city', 'မသိပါ')}\n"
            f"🚻 ကျား/မ: {target_user['gender']}\n"
            f"📝 Bio: {target_user.get('bio', 'မရှိပါ')}"
        )
        keyboard = [
            [
                InlineKeyboardButton("❌ Pass", callback_data=f"pass_{target_user['user_id']}"),
                InlineKeyboardButton("❤️ Like", callback_data=f"like_{target_user['user_id']}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if is_callback:
            await update.callback_query.message.delete()
            await context.bot.send_photo(
                chat_id=update.callback_query.message.chat_id,
                photo=target_user['photo_id'],
                caption=caption,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_photo(photo=target_user['photo_id'], caption=caption, reply_markup=reply_markup)
    else:
        text = "😔 လောလောဆယ် သင့်အတွက် ကိုက်ညီမယ့်သူ အသစ်မရှိတော့ပါ။ ခဏနေမှ /match ကို ပြန်နှိပ်ကြည့်ပါ!"
        if is_callback:
            await update.callback_query.message.delete()
            await context.bot.send_message(chat_id=update.callback_query.message.chat_id, text=text)
        else:
            await update.message.reply_text(text)

async def match_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    current_user = await users_collection.find_one({"user_id": user_id})
    if not current_user:
        await update.message.reply_text("သင့်မှာ Profile မရှိသေးပါ။ /start ကိုနှိပ်ပြီး အရင်ဖန်တီးပါ။")
        return
    await update.message.reply_text("🔍 သင့်အတွက် ကိုက်ညီမယ့် ဖူးစာရှင်ကို ရှာဖွေနေပါတယ်...")
    await show_next_profile(current_user, update, context)

async def handle_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data 
    action, target_user_id_str = data.split("_")
    target_user_id = int(target_user_id_str)
    current_user_id = query.from_user.id
    
    if action == "pass":
        target_str_id = str(target_user_id)
        
        # passed list ထဲ ထည့်မယ်၊ ပြီးတော့ pass_counts ကို ၁ တိုးမယ် ($inc ကို သုံးပါသည်)
        await users_collection.update_one(
            {"user_id": current_user_id},
            {
                "$addToSet": {"passed": target_user_id},
                "$inc": {f"pass_counts.{target_str_id}": 1}
            }
        )
        
        # ၃ ခါ ပြည့်/မပြည့် စစ်ဆေးမယ်
        updated_user = await users_collection.find_one({"user_id": current_user_id})
        pass_count = updated_user.get("pass_counts", {}).get(target_str_id, 0)
        
        if pass_count >= 3:
            # ၃ ခါပြည့်သွားပါက hard_passed (လုံးဝမပြတော့မည့်စာရင်း) ထဲသို့ ထည့်မည်
            await users_collection.update_one(
                {"user_id": current_user_id},
                {"$addToSet": {"hard_passed": target_user_id}}
            )

    elif action == "like":
        await users_collection.update_one({"user_id": current_user_id}, {"$addToSet": {"likes": target_user_id}})
        
        target_user = await users_collection.find_one({"user_id": target_user_id})
        if target_user and current_user_id in target_user.get("likes", []):
            await users_collection.update_one({"user_id": current_user_id}, {"$addToSet": {"matches": target_user_id}})
            await users_collection.update_one({"user_id": target_user_id}, {"$addToSet": {"matches": current_user_id}})
            
            # HTML format နဲ့ Error ရှင်းထားတဲ့အပိုင်း
            target_username = f"@{target_user['username']}" if target_user.get('username') else target_user['name']
            await context.bot.send_message(
                chat_id=current_user_id,
                text=f"🎉 <b>ဖူးစာရှင်ရှာတွေ့သွားပါပြီ!</b>\nသင်နဲ့ {target_user['name']} တို့ နှစ်ဦးသဘောတူ Match ဖြစ်သွားပါပြီ。\nစကားသွားပြောရန်: {target_username}",
                parse_mode="HTML"
            )
            
            current_user = await users_collection.find_one({"user_id": current_user_id})
            current_username = f"@{current_user['username']}" if current_user.get('username') else current_user['name']
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"🎉 <b>ဖူးစာရှင် အသစ် ရပါပြီ!</b>\n{current_user['name']} နဲ့ သင်တို့ နှစ်ဦးသဘောတူ Match ဖြစ်သွားပါပြီ。\nစကားသွားပြောရန်: {current_username}",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to send match notification to {target_user_id}: {e}")

    current_user_updated = await users_collection.find_one({"user_id": current_user_id})
    await show_next_profile(current_user_updated, update, context, is_callback=True)


# ==========================================
# 3. My Profile System
# ==========================================

async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user = await users_collection.find_one({"user_id": user_id})
    
    if not user:
        await update.message.reply_text("သင့်မှာ Profile မရှိသေးပါ။ /start ကိုနှိပ်ပြီး အရင်ဖန်တီးပါ။")
        return
        
    # ✅ ပါ/မပါ စစ်ဆေးပြီး နာမည်ဘေးမှာ ကပ်မယ့်အပိုင်း
    verified_mark = " ✅" if user.get("is_verified") else ""
    caption = (
        f"🌟 **သင့်ရဲ့ လက်ရှိ Profile** 🌟\n\n"
        f"👤 အမည်: {user['name']}{verified_mark} ({user.get('age', '-')} နှစ်)\n"
        f"📍 မြို့: {user.get('city', 'မသိပါ')}\n"
        f"🚻 ကျား/မ: {user['gender']}\n"
        f"🔍 ရှာဖွေနေသူ: {user['looking_for']}\n"
        f"📝 Bio: {user.get('bio', 'မရှိပါ')}"
    )
    
    keyboard = [[InlineKeyboardButton("✏️ Profile အသစ်ပြန်ပြင်မည်", callback_data="edit_profile")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_photo(photo=user['photo_id'], caption=caption, reply_markup=reply_markup)

async def handle_edit_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    # ဖျက်မယ့်အစား is_editing: True လို့ သတ်မှတ်ပါမယ် (ဒါမှ Coin တွေ၊ Match တွေ မပျောက်မှာပါ)
    await users_collection.update_one({"user_id": user_id}, {"$set": {"is_editing": True}})
    
    await query.message.delete()
    await context.bot.send_message(
        chat_id=user_id,
        text="✅ သင့် Profile အချက်အလက်ဟောင်းများကို ပြင်ဆင်ရန် အသင့်ဖြစ်ပါပြီ။\nအချက်အလက်များ အသစ်ပြန်လည် ဖြည့်စွက်ရန် /start ကို နှိပ်ပါ။"
    )

async def get_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin မှ User စာရင်းနှင့် အရေအတွက်ကို txt ဖိုင်ဖြင့် ထုတ်ယူမည့် Function (/user)"""
    user_id = update.message.from_user.id
    
    # Admin ဟုတ်/မဟုတ် စစ်ဆေးခြင်း
    if str(user_id) != str(ADMIN_ID):
        await update.message.reply_text("⛔Access Denied!")
        return

    # Database ထဲက User အားလုံးကို ဆွဲထုတ်ခြင်း
    users = await users_collection.find().to_list(length=None)
    total_users = len(users)

    if total_users == 0:
        await update.message.reply_text("လောလောဆယ် Bot အသုံးပြုသူ မရှိသေးပါ။")
        return

    # txt ဖိုင်ထဲတွင် ရေးမည့် စာသားများကို စီစဉ်ခြင်း
    file_content = f"=== LeoMatch Bot Users List ===\n"
    file_content += f"Total Users: {total_users}\n"
    file_content += f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    file_content += "=" * 40 + "\n\n"

    for idx, user in enumerate(users, 1):
        name = user.get("name", "Unknown")
        # Username မရှိရင် 'မရှိပါ' လို့ ပြမယ်
        username = f"@{user.get('username')}" if user.get("username") else "မရှိပါ"
        uid = user.get("user_id", "Unknown")
        gender = user.get("gender", "-")
        coins = user.get("coins", 0)
        
        # User တစ်ယောက်ချင်းစီရဲ့ အချက်အလက်ကို စာကြောင်းတစ်ကြောင်းစီ ထည့်မယ်
        file_content += f"{idx}. Name: {name} | Username: {username} | Gender: {gender} | Coins: {coins} | UserID: {uid}\n"

    # စာသားများကို Memory ထဲတွင် txt ဖိုင်အဖြစ် ဖန်တီးခြင်း
    txt_file = io.BytesIO(file_content.encode('utf-8'))
    txt_file.name = "bot_users_list.txt"

    # Admin ထံသို့ စာနှင့်တကွ ဖိုင်ကို ပို့ဆောင်ခြင်း
    await update.message.reply_text(f"📊 စုစုပေါင်း Bot အသုံးပြုသူ: <b>{total_users}</b> ဦး\nအသေးစိတ်ကို အောက်ပါ txt ဖိုင်တွင် ကြည့်ရှုနိုင်ပါသည်။", parse_mode="HTML")
    
    await context.bot.send_document(
        chat_id=user_id,
        document=txt_file,
        filename="bot_users_list.txt"
    )

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

    # Database ထဲက User အားလုံးကို ဆွဲထုတ်ခြင်း
    users = await users_collection.find().to_list(length=None)
    total_users = len(users)
    success_count = 0
    
    # ပို့နေကြောင်း Status အရင်ပြထားမယ် (ကြာသွားရင် စိတ်မပူအောင်လို့ပါ)
    status_msg = await update.message.reply_text(f"📣 Broadcast စတင်ပို့ဆောင်နေပါသည်...\nစုစုပေါင်း User အရေအတွက်: {total_users} ဦး")

    # User တစ်ယောက်ချင်းစီဆီကို Loop ပတ်ပြီး စာပို့ခြင်း
    for user in users:
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
        except Exception as e:
            # User က Bot ကို Block ထားရင် Error တက်နိုင်လို့ ကျော်သွားအောင် ရေးထားပါတယ်
            logger.error(f"Broadcast ပို့ရန် အဆင်မပြေပါ User ID {user['user_id']}: {e}")

    # ပို့ပြီးသွားရင် Status ကို Update ပြန်လုပ်ပေးမယ်
    await status_msg.edit_text(f"✅ Broadcast ပို့ဆောင်မှု ပြီးဆုံးပါပြီ။\nအောင်မြင်စွာပို့နိုင်ခဲ့သူ: {success_count}/{total_users} ဦး")

# ==========================================
# 5. Premium / Coin Features (See Who Liked You)
# ==========================================

async def check_likes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/likes နှိပ်လျှင် မိမိကို Like ထားသူများကို စစ်ဆေးမည့် Function"""
    user_id = update.message.from_user.id
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
        # ✅ ပါ/မပါ စစ်ဆေးပြီး နာမည်ဘေးမှာ ကပ်မယ့်အပိုင်း
        verified_mark = " ✅" if liker.get("is_verified") else ""
        caption = (
            f"💖 <b>ဒီသူက သင့်ကို Like ပေးထားပါတယ်!</b> 💖\n\n"
            f"👤 အမည်: {liker['name']}{verified_mark}, {liker.get('age', '-')} နှစ်\n"
            f"📍 မြို့: {liker.get('city', 'မသိပါ')}\n"
            f"🚻 ကျား/မ: {liker['gender']}\n"
            f"📝 Bio: {liker.get('bio', 'မရှိပါ')}"
        )
        keyboard = [
            [
                InlineKeyboardButton("❌ Pass", callback_data=f"pass_{liker['user_id']}"),
                InlineKeyboardButton("❤️ Match ပြန်လုပ်မည်", callback_data=f"like_{liker['user_id']}")
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
        "ကျေးဇူးပြု၍ သင့်မျက်နှာ သေချာပေါ်လွင်ပြီး <b>လက်နှစ်ချောင်း (✌️) ထောင်ထားသော ဆဲလ်ဖီ (Selfie) ပုံ</b> တစ်ပုံကို ယခုပို့ပေးပါ။\n\n"
        "<i>(မှတ်ချက် - ဤပုံကို Admin မှလွဲ၍ မည်သူမှ မြင်ရမည်မဟုတ်ပါ။ ကိုယ်ရေးကိုယ်တာ လုံခြုံရေးကို အပြည့်အဝ အာမခံပါသည်။)</i>",
        parse_mode="HTML"
    )
    return VERIFY_PHOTO_STATE

async def receive_verify_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User ပို့လိုက်သော Selfie ကို လက်ခံပြီး Admin ထံ ပို့မည့် Function"""
    photo_file_id = update.message.photo[-1].file_id
    user_id = update.message.from_user.id
    user = await users_collection.find_one({"user_id": user_id})

    # Admin ဆီကို Approve/Reject ခလုတ်နဲ့ လှမ်းပို့မယ်
    keyboard = [
        [
            InlineKeyboardButton("✅ လက်ခံမည်", callback_data=f"verify_approve_{user_id}"),
            InlineKeyboardButton("❌ ပယ်ချမည်", callback_data=f"verify_reject_{user_id}")
        ]
    ]
    
    caption = (
        f"🛡️ <b>Verification Request</b> 🛡️\n\n"
        f"👤 အမည်: {user['name']}\n"
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
                text="🎉 <b>ဂုဏ်ယူပါတယ်။</b> သင့်အကောင့်ကို အတည်ပြု (Verify) ပြီးပါပြီ။ သင့်နာမည်ဘေးတွင် အပြာရောင်အမှန်ခြစ် (✅) ပေါ်နေပါတော့မည်။", 
                parse_mode="HTML"
            )
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

    # Registration Flow
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GENDER: [CallbackQueryHandler(get_gender, pattern="^(Male|Female)$")],
            LOOKING_FOR: [CallbackQueryHandler(get_looking_for, pattern="^(Male|Female|Both)$")],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
            BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bio)],
            PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)
    
    # -------------------------------------------------------------
    # Blue Tick Verification Handler အသစ် ထည့်သွင်းခြင်း
    # -------------------------------------------------------------
    verify_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("verify", verify_start)],
        states={
            VERIFY_PHOTO_STATE: [MessageHandler(filters.PHOTO, receive_verify_photo)],
        },
        fallbacks=[CommandHandler("cancel", verify_cancel)],
    )
    application.add_handler(verify_conv_handler)
    application.add_handler(CallbackQueryHandler(handle_verify_action, pattern="^verify_(approve|reject)_"))

    # Match Command နဲ့ Like/Pass Action 
    application.add_handler(CommandHandler("match", match_command))
    application.add_handler(CallbackQueryHandler(handle_action, pattern="^(like_|pass_)"))
    
    # My Profile Commands 
    application.add_handler(CommandHandler("myprofile", my_profile))
    application.add_handler(CallbackQueryHandler(handle_edit_profile, pattern="^edit_profile$"))
    
    # Admin Features
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("user", get_users_list))
    
    # Coins and Gamification
    application.add_handler(CommandHandler("likes", check_likes_command))
    application.add_handler(CallbackQueryHandler(handle_reveal_like, pattern="^reveal_like$"))
    application.add_handler(CommandHandler("daily", daily_reward))
    
    # Help Menu
    application.add_handler(CommandHandler("help", help_command))

    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

# ဤအပိုင်းသည် Bot ကို စတင်အလုပ်လုပ်စေသော အဓိက Code ဖြစ်ပါသည်
if __name__ == "__main__":
    main()
