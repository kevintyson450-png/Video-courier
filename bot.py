import asyncio
import os
import shutil
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from aiogram.enums import ParseMode
import yt_dlp

from config import BOT_TOKEN, DOWNLOAD_PATH, SITES

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot setup
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# User settings (temporary memory)
user_settings = {}

def is_valid_url(url):
    """Check karein ki URL sahi hai ya nahi"""
    return any(site in url.lower() for site in SITES)

@dp.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer(
        "🎬 **Video Downloader Bot**\n\n"
        "Mujhe koi bhi video link bhejo:\n"
        "• YouTube\n• Instagram\n• TikTok\n• Facebook\n• Twitter/X\n• Bilibili\n• VK\n\n"
        "Commands:\n"
        "/audio - Audio only mode ON/OFF\n"
        "/quality - Quality select karo\n\n"
        "Bas link paste karo, download shuru!",
        parse_mode=ParseMode.MARKDOWN
    )

@dp.message(Command("audio"))
async def audio_cmd(message: Message):
    user_id = message.from_user.id
    current = user_settings.get(user_id, {}).get('audio', False)
    
    user_settings[user_id] = {'audio': not current}
    
    status = "✅ ON" if not current else "❌ OFF"
    await message.answer(f"🔊 Audio Only Mode: {status}")

@dp.message(Command("quality"))
async def quality_cmd(message: Message):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🥇 Best Quality", callback_data="best")],
        [types.InlineKeyboardButton(text="🥈 1080p", callback_data="1080")],
        [types.InlineKeyboardButton(text="🥉 720p", callback_data="720")],
    ])
    await message.answer("📊 Select Quality:", reply_markup=keyboard)

@dp.callback_query(F.data.in_(["best", "1080", "720"]))
async def quality_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_settings[user_id] = user_settings.get(user_id, {})
    user_settings[user_id]['quality'] = callback.data
    
    await callback.answer(f"Quality set: {callback.data}")
    await callback.message.edit_text(f"✅ Quality set to: {callback.data.upper()}\nAb link bhejo!")

@dp.message(F.text)
async def download_handler(message: Message):
    url = message.text.strip()
    user_id = message.from_user.id
    
    # Check URL
    if not url.startswith('http'):
        await message.reply("❌ Link bhejo jo http se start hota ho!")
        return
    
    if not is_valid_url(url):
        await message.reply("❌ Ye site support nahi karti. Sirf YouTube, Insta, TikTok, etc.")
        return
    
    # Status message
    status = await message.reply("⏳ Processing...")
    
    try:
        # Download folder setup
        user_folder = os.path.join(DOWNLOAD_PATH, str(user_id))
        os.makedirs(user_folder, exist_ok=True)
        
        # Get user preferences
        prefs = user_settings.get(user_id, {})
        is_audio = prefs.get('audio', False)
        quality = prefs.get('quality', 'best')
        
        # yt-dlp options setup
        if is_audio:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(user_folder, '%(title)s.%(ext)s'),
                'extractaudio': True,
                'audioformat': 'mp3',
                'audioquality': '0',
                'quiet': True,
                'no_warnings': True,
            }
        else:
            if quality == '1080':
                fmt = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
            elif quality == '720':
                fmt = 'bestvideo[height<=720]+bestaudio/best[height<=720]'
            else:
                fmt = 'bestvideo+bestaudio/best'
            
            ydl_opts = {
                'format': fmt,
                'outtmpl': os.path.join(user_folder, '%(title)s.%(ext)s'),
                'merge_output_format': 'mp4',
                'quiet': True,
                'no_warnings': True,
            }
        
        # Download
        await status.edit_text("📥 Downloading...")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Video')
        
        # Find file
        files = os.listdir(user_folder)
        if not files:
            raise Exception("Download failed")
        
        filename = files[0]
        filepath = os.path.join(user_folder, filename)
        
        # Check file size (Telegram limit 2GB, but keep it safe under 50MB for free users)
        file_size = os.path.getsize(filepath)
        if file_size > 1.9 * 1024 * 1024 * 1024:  # 1.9 GB
            await status.edit_text("❌ File bahut bada hai (2GB+)")
            return
        
        # Upload
        await status.edit_text("📤 Uploading to Telegram...")
        
        if is_audio:
            await message.answer_audio(FSInputFile(filepath), title=title)
        else:
            if file_size < 50 * 1024 * 1024:  # < 50MB as video
                await message.answer_video(FSInputFile(filepath), caption=f"🎬 {title}")
            else:
                await message.answer_document(FSInputFile(filepath), caption=f"🎬 {title}")
        
        # Cleanup
        await status.delete()
        shutil.rmtree(user_folder)
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error: {error_msg}")
        
        # Simple error messages
        if "unavailable" in error_msg.lower():
            await status.edit_text("❌ Video unavailable (private ya deleted hai)")
        elif "copyright" in error_msg.lower():
            await status.edit_text("❌ Copyright violation")
        else:
            await status.edit_text(f"❌ Error: {error_msg[:100]}")
        
        # Cleanup
        if os.path.exists(user_folder):
            shutil.rmtree(user_folder, ignore_errors=True)

async def main():
    # Ensure download path exists
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    
    # Start bot
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
