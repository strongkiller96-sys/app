# -*- coding: utf-8 -*-
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'FragmentApi'))

import asyncio
import re
import json
import random
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from aiogram.exceptions import TelegramForbiddenError

load_dotenv()


API_ID = 30239558
API_HASH = '88542878ea824e69cadcf277be0a2dc3'
PHONE = '+998912224241'
SESSION_NAME = 'user_session'

BOT_TOKEN = os.getenv('BOT_TOKEN', '8642232109:AAGI4EXqhbOG0vS_U0jrVlg2V-NC6vb_Ics')
ADMIN_ID = int(os.getenv('ADMIN_ID', 7705853975))
CHANNEL_ID = -1003288115754  

ADMIN_USERNAME = "@starschibratan"

ADMIN_CARD = {
    "number": "5614 6861 0848 8258",
    "name": "ERGASHEV TOHIRJON",
    "card": "Davr bank Uzcard"
}

COMMISSION_MIN = 1 
COMMISSION_MAX = 700  

PAYMENT_TIMEOUT_MINUTES = 15

PREMIUM_PRICES = {
    3: 160000,  
    6: 220000,   
    12: 400000   
}

STARS_PRICE_RANGE_1 = 210 
STARS_PRICE_RANGE_2 = 200  


async def safe_send_message(user_id, text, **kwargs):
    """Foydalanuvchi botni bloklagan bo'lsa ham xatolik bermaydi"""
    try:
        await bot.send_message(user_id, text, **kwargs)
        return True
    except TelegramForbiddenError:
        print(f"⚠️ Foydalanuvchi {user_id} botni bloklagan")
        return False
    except Exception as e:
        print(f"❌ Xatolik: {e}")
        return False


class PurchaseState(StatesGroup):
    waiting_for_username = State()
    waiting_for_custom_stars = State()
    waiting_for_custom_premium = State()


storage = MemoryStorage()
user_client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

orders = {}
next_order_id = 1


def add_commission(base_amount):
    """Asosiy summaga random komissiya qo'shish"""
    commission = random.randint(COMMISSION_MIN, COMMISSION_MAX)
    total_amount = base_amount + commission
    return total_amount, commission


async def check_channel():
    """Kanalga bot ulanganligini tekshirish"""
    try:
        chat = await bot.get_chat(CHANNEL_ID)
        print(f"✅ Kanal topildi: {chat.title} (ID: {CHANNEL_ID})")
        print(f"👤 Kanal username: @{chat.username if chat.username else 'yoq'}")
        
        try:
            await bot.send_message(
                CHANNEL_ID, 
                f"✅ Bot ishga tushdi!\n⏰ {datetime.now().strftime('%H:%M %d.%m.%Y')}"
            )
            print("✅ Test xabar kanalga yuborildi")
        except Exception as e:
            print(f"⚠️ Test xabar yuborilmadi: {e}")
        
        return True
    except Exception as e:
        print(f"❌ Kanalga ulanishda xatolik: {e}")
        print("⚠️ Bot kanalga admin qilinganligini tekshiring!")
        return False


async def check_username_exists(username):
    """Telegram username mavjudligini tekshirish"""
    try:
        clean_username = username.replace('@', '')
        entity = await user_client.get_entity(clean_username)
        
        if entity:
            if hasattr(entity, 'first_name'):
                full_name = f"{entity.first_name or ''} {entity.last_name or ''}".strip()
            else:
                full_name = "Noma'lum"
            
            print(f"✅ Username topildi: @{clean_username} - Ism: {full_name}")
            return True, entity, full_name
        else:
            return False, None, None
            
    except Exception as e:
        print(f"❌ Username topilmadi: {username}")
        return False, None, None


async def check_expired_orders():
    """Muddati o'tgan buyurtmalarni yopish"""
    while True:
        try:
            current_time = datetime.now()
            expired_count = 0
            
            for order_id, order_data in list(orders.items()):
                if order_data['status'] == 'pending':
                    order_time = datetime.fromisoformat(order_data['time'])
                    time_diff = current_time - order_time
                    
                    if time_diff.total_seconds() > PAYMENT_TIMEOUT_MINUTES * 60:
                        order_data['status'] = 'expired'
                        expired_count += 1
                        
                        await safe_send_message(
                            order_data['user_id'],
                            f"⏰ <b>To'lov muddati tugadi!</b>\n\n"
                            f"🆔 Buyurtma #{order_id}\n"
                            f"⏳ {PAYMENT_TIMEOUT_MINUTES} daqiqa muddat tugadi.\n\n"
                            f"✅ Yangi buyurtma berishingiz mumkin!",
                            parse_mode="HTML"
                        )
                        
                        print(f"⏰ Buyurtma #{order_id} muddati tugadi")
            
            if expired_count > 0:
                print(f"⏰ {expired_count} ta buyurtma muddati tugadi")
                
        except Exception as e:
            print(f"❌ Xatolik: {e}")
        
        await asyncio.sleep(60)


async def send_to_channel(order_id, order_data, status_emoji, status_text):
    """Buyurtma ma'lumotlarini kanalga yuborish"""
    try:
        clean_nickname = order_data['nickname'].replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')
        
        if order_data['product_type'] == 'stars':
            type_text = "Stars ⭐"
            price_text = f"{order_data['stars']} 🌟"
        else:
            type_text = "Premium 💎"
            price_text = f"{order_data['months']} oy 📅"
        
        base_amount = order_data['base_amount']
        commission = order_data['commission']
        total_amount = order_data['amount']
        
        channel_message = f"""
<b>🆔 Order ID:</b> {order_id}
<b>📋 Type:</b> {type_text}
<b>💳 Payment Type:</b> balance
<b>👤 Nickname:</b> {clean_nickname}
<b>💸 Amount:</b> {total_amount:,.2f} so'm
<b>💰 Base:</b> {base_amount:,.2f} so'm
<b>➕ Commission:</b> {commission} so'm
<b>🏷️ Price:</b> {price_text}
<b>{status_emoji} Status:</b> {status_text}
<b>⏰ Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        if CHANNEL_ID:
            await bot.send_message(CHANNEL_ID, channel_message, parse_mode="HTML")
            print(f"📨 Kanalga yuborildi: Order #{order_id} - {status_text}")
            
    except Exception as e:
        print(f"❌ Kanalga yuborishda xatolik: {e}")
        await safe_send_message(
            ADMIN_ID,
            f"❌ Kanalga yuborishda xatolik\n\n"
            f"🆔 #{order_id}\n"
            f"📄 Xatolik: {e}",
            parse_mode="HTML"
        )


try:
    from app.methods import FragmentStars, FragmentPremium
    FRAGMENT_AVAILABLE = True
    print("✅ FragmentAPI yuklandi")
    
    stars_client = FragmentStars()
    premium_client = FragmentPremium()
    
    if os.path.exists('cookies.json'):
        with open('cookies.json', 'r') as f:
            cookies_data = json.load(f)
            stars_client.cookies = cookies_data
            premium_client.cookies = cookies_data
        print("✅ Cookies yuklandi")
        
except ImportError:
    FRAGMENT_AVAILABLE = False
    print("⚠️ FragmentAPI yuklanmadi")


async def check_balance():
    """FragmentAPI balansini tekshirish"""
    if not FRAGMENT_AVAILABLE:
        return 1000000
    
    try:
        if hasattr(stars_client, 'get_balance'):
            return await stars_client.get_balance()
        return None
    except Exception:
        return None


async def send_stars(username, stars_count):
    """Stars yuborish"""
    if not FRAGMENT_AVAILABLE:
        print(f"🔄 TEST: {stars_count} Stars -> {username}")
        return {"ok": True}
    
    try:
        result = await stars_client.buy_stars(username=username, amount=stars_count)
        print(f"📄 Stars javobi: {result}")
        
        if result and result.get('success'):
            return {"ok": True, "result": result}
        else:
            return {"ok": False, "error": "unknown_error"}
    except Exception as e:
        print(f"❌ Xatolik: {e}")
        return {"ok": False, "error": str(e)}


async def send_premium(username, months):
    """Premium yuborish"""
    if not FRAGMENT_AVAILABLE:
        print(f"🔄 TEST: {months} oy Premium -> {username}")
        return {"ok": True}
    
    try:
        result = await premium_client.buy_premium(username=username, months=months)
        print(f"📄 Premium javobi: {result}")
        
        if result and result.get('ok'):
            return {"ok": True, "result": result}
        else:
            return {"ok": False, "error": "unknown_error"}
    except Exception as e:
        print(f"❌ Xatolik: {e}")
        return {"ok": False, "error": str(e)}


async def safe_edit_message(message, new_text, new_keyboard=None):
    """Xabarni xavfsiz o'zgartirish"""
    try:
        await message.edit_text(new_text, reply_markup=new_keyboard, parse_mode="HTML")
    except Exception as e:
        if "message is not modified" not in str(e):
            print(f"Xatolik: {e}")


def get_payment_keyboard(amount, order_id):
    """To'lov uchun keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Karta raqami", callback_data=f"copy_card_{order_id}")],
        [InlineKeyboardButton(text=f"💰 {amount:,} so'm", callback_data=f"copy_amount_{order_id}")],
        [InlineKeyboardButton(text="✅ To'lov qildim", callback_data=f"payment_done_{order_id}")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="back_to_main")]
    ])
    return keyboard


@dp.callback_query(lambda c: c.data.startswith("copy_card_"))
async def copy_card_callback(callback_query: types.CallbackQuery):
    await callback_query.answer("💳 Karta nusxalandi", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("copy_amount_"))
async def copy_amount_callback(callback_query: types.CallbackQuery):
    await callback_query.answer("💰 Summa nusxalandi", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("payment_done_"))
async def payment_done_callback(callback_query: types.CallbackQuery):
    order_id = callback_query.data.replace("payment_done_", "")
    await callback_query.answer("✅ Tekshirilmoqda", show_alert=True)
    
    await callback_query.message.answer(
        f"✅ <b>To'lov tekshirilmoqda</b>\n\n"
        f"🆔 Buyurtma #{order_id}\n"
        f"📨 @CardXabarBot dan xabar kelgach tasdiqlanadi.\n\n"
        f"⏳ Bu jarayon 1-2 daqiqa olishi mumkin.",
        parse_mode="HTML"
    )


@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    
    if user_id == ADMIN_ID:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
            [InlineKeyboardButton(text="💳 Karta", callback_data="admin_card")],
            [InlineKeyboardButton(text="💰 Balans", callback_data="admin_balance")],
            [InlineKeyboardButton(text="👤 Admin lichkasi", callback_data="admin_contact")],
            [InlineKeyboardButton(text="📢 Test kanal", callback_data="test_channel")]
        ])
        await message.answer("👑 Admin Panel", reply_markup=keyboard)
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Stars", callback_data="main_stars")],
            [InlineKeyboardButton(text="💎 Premium", callback_data="main_premium")],
            [InlineKeyboardButton(text="📞 Admin", callback_data="contact_admin")],
            [InlineKeyboardButton(text="❓ Yordam", callback_data="user_help")]
        ])
        await message.answer("🌟 StarPremium Bot\n\nQuyidagi tugmalardan birini tanlang:", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "test_channel")
async def test_channel_callback(callback_query: types.CallbackQuery):
    await callback_query.answer("📢 Test")
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    try:
        test_msg = f"""
<b>🔔 TEST XABAR</b>

Agar bu xabarni ko'rayotgan bo'lsangiz, bot kanalga xabar yuborayapti!

📊 Test vaqti: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📢 Kanal ID: <code>{CHANNEL_ID}</code>
"""
        
        await bot.send_message(CHANNEL_ID, test_msg, parse_mode="HTML")
        await callback_query.message.answer("✅ Test xabar kanalga yuborildi!")
        
    except Exception as e:
        await callback_query.message.answer(f"❌ Xatolik: {e}")


@dp.callback_query(lambda c: c.data == "contact_admin")
async def contact_admin(callback_query: types.CallbackQuery):
    await callback_query.answer("📞 Admin")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Admin bilan bog'lanish", url=f"https://t.me/{ADMIN_USERNAME.replace('@', '')}")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="back_to_main")]
    ])
    
    await safe_edit_message(
        callback_query.message,
        f"📞 <b>Admin bilan bog'lanish</b>\n\nAdmin: {ADMIN_USERNAME}",
        keyboard
    )

@dp.callback_query(lambda c: c.data == "main_stars")
async def stars_main_menu(callback_query: types.CallbackQuery):
    await callback_query.answer("⭐ Stars")
    
    stars_50_total, _ = add_commission(50 * STARS_PRICE_RANGE_1)
    stars_100_total, _ = add_commission(100 * STARS_PRICE_RANGE_1)
    stars_500_total, _ = add_commission(500 * STARS_PRICE_RANGE_1)
    stars_1000_total, _ = add_commission(1000 * STARS_PRICE_RANGE_2)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⭐ 50 Stars ~ {stars_50_total:,} so'm", callback_data="buy_stars_50")],
        [InlineKeyboardButton(text=f"⭐ 100 Stars ~ {stars_100_total:,} so'm", callback_data="buy_stars_100")],
        [InlineKeyboardButton(text=f"⭐ 500 Stars ~ {stars_500_total:,} so'm", callback_data="buy_stars_500")],
        [InlineKeyboardButton(text=f"⭐ 1000 Stars ~ {stars_1000_total:,} so'm", callback_data="buy_stars_1000")],
        [InlineKeyboardButton(text="✏️ Boshqa miqdor", callback_data="custom_stars")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="back_to_main")]
    ])
    
    await safe_edit_message(
        callback_query.message,
        f"⭐ Stars narxlari:\n\n"
        f"• 50-500 Stars: 210 so'm/star + komissiya\n"
        f"• 501-5000 Stars: 200 so'm/star + komissiya\n\n"
        f"✶ To'lov summasi har bir buyurtma uchun farqli bo'ladi!",
        keyboard
    )

@dp.callback_query(lambda c: c.data.startswith('buy_stars_'))
async def buy_stars_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer("✅ Tanlandi")
    
    stars = int(callback_query.data.split('_')[2])
    
    if stars <= 500:
        base = stars * STARS_PRICE_RANGE_1
    else:
        base = stars * STARS_PRICE_RANGE_2
    
    total, commission = add_commission(base)
    
    await state.update_data(
        product_type='stars',
        stars=stars,
        base_amount=base,
        commission=commission,
        amount=total
    )
    await state.set_state(PurchaseState.waiting_for_username)
    
    await safe_edit_message(
        callback_query.message,
        f"✅ <b>{stars} Stars tanlandi</b>\n\n"
        f"💰 Asosiy summa: {base:,} so'm\n"
        f"➕ Komissiya: {commission} so'm\n"
        f"💳 To'lov: <b>{total:,} so'm</b>\n\n"
        f"📝 Endi Telegram username'ingizni kiriting (masalan: @username):",
        None
    )

@dp.callback_query(lambda c: c.data == "custom_stars")
async def custom_stars_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer("✏️")
    await state.set_state(PurchaseState.waiting_for_custom_stars)
    await safe_edit_message(
        callback_query.message,
        f"✏️ <b>Maxsus Stars miqdori</b>\n\n"
        f"Iltimos, kerakli Stars miqdorini kiriting (50-5000):\n"
        f"Misol: 250, 750, 1500, 2500\n\n"
        f"Narxlar:\n"
        f"• 50-500: 210 so'm/star + komissiya\n"
        f"• 501-5000: 200 so'm/star + komissiya",
        None
    )

@dp.message(PurchaseState.waiting_for_custom_stars)
async def process_custom_stars(message: types.Message, state: FSMContext):
    try:
        stars = int(message.text.strip())
        
        if stars < 50:
            await message.answer("❌ Minimal 50 Stars sotib olish mumkin!")
            return
        if stars > 5000:
            await message.answer("❌ Maksimal 5000 Stars sotib olish mumkin!")
            return
        
        if stars <= 500:
            base = stars * STARS_PRICE_RANGE_1
        else:
            base = stars * STARS_PRICE_RANGE_2
        
        total, commission = add_commission(base)
        
        await state.update_data(
            product_type='stars',
            stars=stars,
            base_amount=base,
            commission=commission,
            amount=total
        )
        await state.set_state(PurchaseState.waiting_for_username)
        
        await message.answer(
            f"✅ <b>{stars} Stars tanlandi</b>\n\n"
            f"💰 Asosiy summa: {base:,} so'm\n"
            f"➕ Komissiya: {commission} so'm\n"
            f"💳 To'lov: <b>{total:,} so'm</b>\n\n"
            f"📝 Endi Telegram username'ingizni kiriting (masalan: @username):",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Noto'g'ri format! Iltimos, faqat son kiriting")


@dp.callback_query(lambda c: c.data == "main_premium")
async def premium_main_menu(callback_query: types.CallbackQuery):
    await callback_query.answer("💎 Premium")
    
    premium_3_total, _ = add_commission(PREMIUM_PRICES[3])
    premium_6_total, _ = add_commission(PREMIUM_PRICES[6])
    premium_12_total, _ = add_commission(PREMIUM_PRICES[12])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 1 oylik - Admin bilan bog'lanish", url=f"https://t.me/{ADMIN_USERNAME.replace('@', '')}")],
        [InlineKeyboardButton(text=f"💎 3 oylik ~ {premium_3_total:,} so'm", callback_data="buy_premium_3")],
        [InlineKeyboardButton(text=f"💎 6 oylik ~ {premium_6_total:,} so'm", callback_data="buy_premium_6")],
        [InlineKeyboardButton(text=f"💎 12 oylik ~ {premium_12_total:,} so'm", callback_data="buy_premium_12")],
        [InlineKeyboardButton(text="✏️ Boshqa oy", callback_data="custom_premium")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="back_to_main")]
    ])
    
    await safe_edit_message(
        callback_query.message,
        f"💎 Premium narxlari:\n\n"
        f"• 1 oylik: Admin bilan bog'lanishingiz kerak\n"
        f"• 3 oylik: {PREMIUM_PRICES[3]:,} so'm + komissiya\n"
        f"• 6 oylik: {PREMIUM_PRICES[6]:,} so'm + komissiya\n"
        f"• 12 oylik: {PREMIUM_PRICES[12]:,} so'm + komissiya\n\n"
        f"📌 To'lov summasi har bir buyurtma uchun farqli bo'ladi!",
        keyboard
    )

@dp.callback_query(lambda c: c.data.startswith('buy_premium_'))
async def buy_premium_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer("✅ Tanlandi")
    
    months = int(callback_query.data.split('_')[2])
    
    if months == 1:
        await callback_query.answer("❌ 1 oylik faqat admin orqali!", show_alert=True)
        return
    
    if months in PREMIUM_PRICES:
        base = PREMIUM_PRICES[months]
    else:
        base = months * 40000
    
    total, commission = add_commission(base)
    
    await state.update_data(
        product_type='premium',
        months=months,
        base_amount=base,
        commission=commission,
        amount=total
    )
    await state.set_state(PurchaseState.waiting_for_username)
    
    await safe_edit_message(
        callback_query.message,
        f"✅ <b>{months} oylik Premium tanlandi</b>\n\n"
        f"💰 Asosiy summa: {base:,} so'm\n"
        f"➕ Komissiya: {commission} so'm\n"
        f"💳 To'lov: <b>{total:,} so'm</b>\n\n"
        f"📝 Endi Telegram username'ingizni kiriting (masalan: @username):",
        None
    )

@dp.callback_query(lambda c: c.data == "custom_premium")
async def custom_premium_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer("✏️")
    await state.set_state(PurchaseState.waiting_for_custom_premium)
    await safe_edit_message(
        callback_query.message,
        f"✏️ <b>Maxsus Premium oyi</b>\n\n"
        f"Iltimos, kerakli oy miqdorini kiriting (3-12):\n"
        f"Misol: 3, 4, 5, 8, 10\n\n"
        f"Narxlar:\n"
        f"• 3 oylik: {PREMIUM_PRICES[3]:,} so'm + komissiya\n"
        f"• 6 oylik: {PREMIUM_PRICES[6]:,} so'm + komissiya\n"
        f"• 12 oylik: {PREMIUM_PRICES[12]:,} so'm + komissiya",
        None
    )

@dp.message(PurchaseState.waiting_for_custom_premium)
async def process_custom_premium(message: types.Message, state: FSMContext):
    try:
        months = int(message.text.strip())
        
        if months < 3:
            await message.answer(
                f"❌ Minimal 3 oy sotib olish mumkin!\n\n"
                f"1-2 oylik premium olish uchun admin bilan bog'lanishingiz kerak:\n"
                f"{ADMIN_USERNAME}",
                parse_mode="HTML"
            )
            return
        if months > 12:
            await message.answer("❌ Maksimal 12 oy sotib olish mumkin!")
            return
        
        if months in PREMIUM_PRICES:
            base = PREMIUM_PRICES[months]
        else:
            base = months * 40000
        
        total, commission = add_commission(base)
        
        await state.update_data(
            product_type='premium',
            months=months,
            base_amount=base,
            commission=commission,
            amount=total
        )
        await state.set_state(PurchaseState.waiting_for_username)
        
        await message.answer(
            f"✅ <b>{months} oylik Premium tanlandi</b>\n\n"
            f"💰 Asosiy summa: {base:,} so'm\n"
            f"➕ Komissiya: {commission} so'm\n"
            f"💳 To'lov: <b>{total:,} so'm</b>\n\n"
            f"📝 Endi Telegram username'ingizni kiriting (masalan: @username):",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Noto'g'ri format! Iltimos, faqat son kiriting")


@dp.message(PurchaseState.waiting_for_username)
async def process_username(message: types.Message, state: FSMContext):
    global next_order_id
    
    user_id = message.from_user.id
    username = message.text.strip()
    
    if not username.startswith('@'):
        username = f"@{username}"
    
    wait_msg = await message.answer("🔍 Username tekshirilmoqda...")
    
    exists, entity, full_name = await check_username_exists(username)
    
    if not exists:
        await wait_msg.delete()
        await message.answer(
            f"❌ <b>Username topilmadi!</b>\n\n"
            f"'{username}' nomli foydalanuvchi mavjud emas.\n\n"
            f"📝 Iltimos, qaytadan to'g'ri username kiriting:",
            parse_mode="HTML"
        )
        return
    
    await wait_msg.delete()
    
    data = await state.get_data()
    
    order_id = next_order_id
    next_order_id += 1
    
    nickname = full_name if full_name != "Noma'lum" else username.replace('@', '')
    
    expiry_time = datetime.now() + timedelta(minutes=PAYMENT_TIMEOUT_MINUTES)
    
    if data['product_type'] == 'stars':
        orders[order_id] = {
            'user_id': user_id,
            'username': username,
            'nickname': nickname,
            'fullname': full_name,
            'product_type': 'stars',
            'stars': data['stars'],
            'base_amount': data['base_amount'],
            'commission': data['commission'],
            'amount': data['amount'],
            'status': 'pending',
            'time': datetime.now().isoformat(),
            'expiry_time': expiry_time.isoformat()
        }
        product_text = f"⭐ {data['stars']} Stars"
    else:
        orders[order_id] = {
            'user_id': user_id,
            'username': username,
            'nickname': nickname,
            'fullname': full_name,
            'product_type': 'premium',
            'months': data['months'],
            'base_amount': data['base_amount'],
            'commission': data['commission'],
            'amount': data['amount'],
            'status': 'pending',
            'time': datetime.now().isoformat(),
            'expiry_time': expiry_time.isoformat()
        }
        product_text = f"💎 {data['months']} oylik Premium"
    
    payment_keyboard = get_payment_keyboard(data['amount'], order_id)
    
    await message.answer(
        f"✅ <b>Ma'lumotlar saqlandi!</b>\n\n"
        f"🆔 Buyurtma raqami: #{order_id}\n"
        f"👤 Ism: {nickname}\n"
        f"📦 Mahsulot: {product_text}\n"
        f"💰 Asosiy summa: {data['base_amount']:,} so'm\n"
        f"➕ Komissiya: {data['commission']} so'm\n\n"
        f"💳 <b>To'lov uchun:</b>\n"
        f"<code>{ADMIN_CARD['number']}</code>\n"
        f"{ADMIN_CARD['name']}\n\n"
        f"💰 <b>To'lov summasi: {data['amount']:,} so'm</b>\n\n"
        f"⏰ <b>MUHIM!</b>\n"
        f"• Aynan <b>{data['amount']:,} so'm</b> to'lang!\n"
        f"• 1 so'm kam yoki ko'p bo'lsa, to'lov aniqlanmaydi!\n"
        f"• To'lov {PAYMENT_TIMEOUT_MINUTES} daqiqa ichida amalga oshirilishi kerak",
        reply_markup=payment_keyboard,
        parse_mode="HTML"
    )
    await state.clear()
    
    await safe_send_message(
        ADMIN_ID,
        f"🆕 <b>Yangi buyurtma!</b>\n\n"
        f"🆔 #{order_id}\n"
        f"👤 Ism: {nickname}\n"
        f"👤 Username: {username}\n"
        f"📦 {product_text}\n"
        f"💰 Asosiy: {data['base_amount']:,} so'm\n"
        f"➕ Komissiya: {data['commission']} so'm\n"
        f"💳 To'lov: {data['amount']:,} so'm",
        parse_mode="HTML"
    )


@dp.callback_query(lambda c: c.data == "user_help")
async def user_help(callback_query: types.CallbackQuery):
    await callback_query.answer("❓ Yordam")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Admin", callback_data="contact_admin")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="back_to_main")]
    ])
    
    await safe_edit_message(
        callback_query.message,
        f"📞 <b>Yordam</b>\n\n"
        f"💳 Karta: <code>{ADMIN_CARD['number']}</code>\n"
        f"👤 Ism: {ADMIN_CARD['name']}\n\n"
        f"⭐ Stars: 50-500:210 so'm/star + komissiya\n"
        f"⭐ Stars: 501-5000:200 so'm/star + komissiya\n"
        f"💎 Premium:\n"
        f"• 1 oylik: Admin orqali\n"
        f"• 3 oylik: {PREMIUM_PRICES[3]:,} so'm + komissiya\n"
        f"• 6 oylik: {PREMIUM_PRICES[6]:,} so'm + komissiya\n"
        f"• 12 oylik: {PREMIUM_PRICES[12]:,} so'm + komissiya\n\n"
        f"📌 <b>Qanday ishlaydi:</b>\n"
        f"1. Kerakli mahsulotni tanlang\n"
        f"2. Username kiriting\n"
        f"3. Sizga maxsus to'lov summasi ko'rsatiladi\n"
        f"4. <b>AYNAN O'SHA SUMMANI</b> kartaga to'lang\n"
        f"5. To'lov avtomatik tekshiriladi\n\n"
        f"⏰ To'lov uchun {PAYMENT_TIMEOUT_MINUTES} daqiqa vaqt bor!\n\n"
        f"📞 Admin: {ADMIN_USERNAME}",
        keyboard
    )

@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback_query: types.CallbackQuery):
    await callback_query.answer("🔙 Asosiy")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Stars", callback_data="main_stars")],
        [InlineKeyboardButton(text="💎 Premium", callback_data="main_premium")],
        [InlineKeyboardButton(text="📞 Admin", callback_data="contact_admin")],
        [InlineKeyboardButton(text="❓ Yordam", callback_data="user_help")]
    ])
    
    await safe_edit_message(
        callback_query.message,
        "🌟 <b>StarPremium Bot</b>\n\nQuyidagi tugmalardan birini tanlang:",
        keyboard
    )


@dp.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats(callback_query: types.CallbackQuery):
    await callback_query.answer("📊")
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    pending = len([o for o in orders.values() if o['status'] == 'pending'])
    completed = len([o for o in orders.values() if o['status'] == 'completed'])
    expired = len([o for o in orders.values() if o['status'] == 'expired'])
    error = len([o for o in orders.values() if o['status'] == 'error'])
    total_amount = sum(o['amount'] for o in orders.values() if o['status'] == 'completed')
    total_commission = sum(o['commission'] for o in orders.values() if o['status'] == 'completed')
    
    text = f"📊 <b>Statistika</b>\n\n"
    text += f"📦 Jami: {len(orders)}\n"
    text += f"⏳ Kutilayotgan: {pending}\n"
    text += f"✅ Tasdiqlangan: {completed}\n"
    text += f"⏰ Muddati o'tgan: {expired}\n"
    text += f"❌ Xatolik: {error}\n"
    text += f"💰 Umumiy summa: {total_amount:,} so'm\n"
    text += f"➕ Jami komissiya: {total_commission:,} so'm\n\n"
    
    if orders:
        text += "📋 <b>Oxirgi 5:</b>\n"
        for order_id in sorted(orders.keys(), reverse=True)[:5]:
            o = orders[order_id]
            if o['product_type'] == 'stars':
                product = f"⭐ {o['stars']}"
            else:
                product = f"💎 {o['months']} oy"
            text += f"• #{order_id}: {o['nickname']} - {product} - {o['amount']:,} so'm - {o['status']}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Balans", callback_data="admin_balance")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
    ])
    
    await safe_edit_message(callback_query.message, text, keyboard)

@dp.callback_query(lambda c: c.data == "admin_card")
async def admin_card(callback_query: types.CallbackQuery):
    await callback_query.answer("💳")
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    text = f"💳 <b>Karta ma'lumotlari</b>\n\n"
    text += f"🏦 Bank: {ADMIN_CARD['bank']}\n"
    text += f"💳 Raqam: <code>{ADMIN_CARD['number']}</code>\n"
    text += f"👤 Ism: {ADMIN_CARD['name']}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
    ])
    
    await safe_edit_message(callback_query.message, text, keyboard)

@dp.callback_query(lambda c: c.data == "admin_balance")
async def admin_balance(callback_query: types.CallbackQuery):
    await callback_query.answer("💰")
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    balance = await check_balance()
    
    text = f"💰 <b>Balans ma'lumotlari</b>\n\n"
    
    if balance is None:
        text += "❌ Balansni tekshirish imkoniyati yo'q"
    else:
        text += f"💎 Joriy balans: {balance:,} TON\n\n"
        text += f"⭐ 50 Stars ≈ 0.35 TON\n"
        text += f"⭐ 500 Stars ≈ 3.5 TON\n"
        text += f"⭐ 1000 Stars ≈ 7 TON\n"
        text += f"💎 3 oylik ≈ 6 TON\n"
        text += f"💎 6 oylik ≈ 12 TON\n"
        text += f"💎 12 oylik ≈ 24 TON\n\n"
        
        if balance < 500:
            text += "⚠️ Diqqat! Balans kam!"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Admin lichkasi", callback_data="admin_contact")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
    ])
    
    await safe_edit_message(callback_query.message, text, keyboard)

@dp.callback_query(lambda c: c.data == "admin_contact")
async def admin_contact(callback_query: types.CallbackQuery):
    await callback_query.answer("📞")
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Lichkaga o'tish", url=f"https://t.me/{ADMIN_USERNAME.replace('@', '')}")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
    ])
    
    await safe_edit_message(
        callback_query.message,
        f"📞 <b>Admin lichkasi</b>\n\n👤 {ADMIN_USERNAME}",
        keyboard
    )

@dp.callback_query(lambda c: c.data == "admin_back")
async def admin_back(callback_query: types.CallbackQuery):
    await callback_query.answer("🔙")
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="💳 Karta", callback_data="admin_card")],
        [InlineKeyboardButton(text="💰 Balans", callback_data="admin_balance")],
        [InlineKeyboardButton(text="👤 Admin lichkasi", callback_data="admin_contact")],
        [InlineKeyboardButton(text="📢 Test kanal", callback_data="test_channel")]
    ])
    
    await safe_edit_message(callback_query.message, "👑 <b>Admin Panel</b>", keyboard)


@user_client.on(events.NewMessage(chats='@CardXabarBot'))
async def handle_cardxabar(event):
    try:
        text = event.message.text
        print(f"\n📨 CardXabar: {text[:50]}...")
        
        amount = 0
        match = re.search(r'([\d\s]+\.\d{2})\s*UZS', text)
        if match:
            amount_str = match.group(1).replace(' ', '').split('.')[0]
            amount = int(amount_str)
            print(f"💰 To'lov summasi: {amount} so'm")
        
        if amount == 0:
            print("❌ Summa topilmadi")
            return
        
        card_match = re.search(r'\*(\d{4})', text)
        if not card_match or card_match.group(1) != ADMIN_CARD['number'][-4:]:
            print("❌ Boshqa karta")
            return
        
        print(f"✅ Admin kartasiga to'lov: {amount} so'm")
        
        found_order = None
        found_id = None
        
        for oid, odata in orders.items():
            if odata['status'] == 'pending' and odata['amount'] == amount:
                found_order = odata
                found_id = oid
                break
        
        if found_order:
            print(f"👤 Buyurtma #{found_id} - {found_order['nickname']}")
            
            if found_order['product_type'] == 'stars':
                result = await send_stars(found_order['username'], found_order['stars'])
                product_text = f"⭐ {found_order['stars']} Stars"
            else:
                result = await send_premium(found_order['username'], found_order['months'])
                product_text = f"💎 {found_order['months']} oylik Premium"
            
            if result.get('ok'):
                await safe_send_message(
                    found_order['user_id'],
                    f"✅ <b>To'lov qabul qilindi!</b>\n\n"
                    f"🆔 #{found_id}\n"
                    f"{product_text} yuborildi!\n"
                    f"💰 Summa: {found_order['amount']:,} so'm",
                    parse_mode="HTML"
                )
                
                found_order['status'] = 'completed'
                found_order['completed_time'] = datetime.now().isoformat()
                
                await send_to_channel(found_id, found_order, "✅", "Completed")
                
                await safe_send_message(
                    ADMIN_ID,
                    f"✅ <b>To'lov tasdiqlandi!</b>\n\n"
                    f"🆔 #{found_id}\n"
                    f"👤 {found_order['nickname']}\n"
                    f"📦 {product_text}\n"
                    f"💰 {found_order['amount']:,} so'm",
                    parse_mode="HTML"
                )
            else:
                await safe_send_message(
                    found_order['user_id'],
                    f"⚠️ <b>To'lov qabul qilindi, lekin texnik muammo!</b>\n\n"
                    f"🆔 #{found_id}\n"
                    f"💰 {found_order['amount']:,} so'm to'lovingiz qabul qilindi.\n"
                    f"❌ Botda muammo yuz berdi.\n\n"
                    f"📞 Admin: {ADMIN_USERNAME}",
                    parse_mode="HTML"
                )
                
                await safe_send_message(
                    ADMIN_ID,
                    f"⚠️ <b>Balans muammosi!</b>\n\n"
                    f"🆔 #{found_id}\n"
                    f"👤 {found_order['nickname']}\n"
                    f"📦 {product_text}\n"
                    f"💰 {found_order['amount']:,} so'm\n\n"
                    f"❌ Iltimos, tekshiring!",
                    parse_mode="HTML"
                )
                
                found_order['status'] = 'error'
                await send_to_channel(found_id, found_order, "⚠️", "Error")
        else:
            await safe_send_message(
                ADMIN_ID,
                f"⚠️ <b>Noma'lum to'lov!</b>\n\n"
                f"💰 Summa: {amount} so'm\n"
                f"🕐 Vaqt: {datetime.now().strftime('%H:%M %d.%m.%Y')}",
                parse_mode="HTML"
            )
            print(f"⚠️ Noma'lum to'lov: {amount} so'm")
                
    except Exception as e:
        print(f"❌ CardXabar xatoligi: {e}")
        import traceback
        traceback.print_exc()


async def main():
    print("=" * 60)
    print("🌟 STAR PREMIUM BOT")
    print("=" * 60)
    print(f"👑 Admin ID: {ADMIN_ID}")
    print(f"📞 Admin lichkasi: {ADMIN_USERNAME}")
    print(f"💳 Karta: {ADMIN_CARD['number']}")
    print(f"💰 Komissiya: {COMMISSION_MIN}-{COMMISSION_MAX} so'm")
    print(f"⏰ To'lov muddati: {PAYMENT_TIMEOUT_MINUTES} daqiqa")
    print(f"💰 Premium narxlari:")
    print(f"   • 1 oylik: Admin orqali")
    print(f"   • 3 oylik: {PREMIUM_PRICES[3]:,} so'm + komissiya")
    print(f"   • 6 oylik: {PREMIUM_PRICES[6]:,} so'm + komissiya")
    print(f"   • 12 oylik: {PREMIUM_PRICES[12]:,} so'm + komissiya")
    print(f"⭐ Stars: 50-500=210 so'm, 501-5000=200 so'm + komissiya")
    
    await check_channel()
    print("=" * 60)
    
    balance = await check_balance()
    if balance is not None:
        print(f"💰 Joriy balans: {balance} TON")
        if balance < 500:
            print("⚠️ DIQQAT! Balans kam!")
    else:
        print("⚠️ Balansni tekshirish imkoniyati yo'q")
    print("=" * 60)
    
    asyncio.create_task(check_expired_orders())
    
    await user_client.start(phone=PHONE)
    print("✅ Telegram akkaunt ulandi!")
    print("📨 @CardXabarBot kuzatilmoqda...")
    print("=" * 60)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())