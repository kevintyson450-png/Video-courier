import asyncio
import os
import shutil
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode
import yt_dlp

from config import BOT_TOKEN, DOWNLOAD_PATH, PLATFORMS

# Logging setup (Errors track karne ke liye)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# User preferences storage (temporary)
user_prefs = {}

def is_supported_url(url: str) -> bool:
    """Check if URL is from supported platform"""
    url_lower = url.lower()
    return any(platform in url_lower for platform in PLATFORMS)

def get_ydl_opts(user_id: int, url: str) -> dict:
    """Generate yt-dlp options based on user preferences"""
    prefs = user_prefs.get(user_id, {'audio_only': False, 'quality': 'best'})
    
    # Download path
    user_folder = os.path.join(DOWNLOAD_PATH, str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    
    if prefs.get('audio_only', False):
        # Audio only mode
        return {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(user_folder, '%(title)s.%(ext)s'),
            'extractaudio': True,
            'audioformat': 'mp3',
            'audioquality': '0',  # Best quality
            'embed_thumbnail': True,
            'addmetadata': True,
            'quiet': True,
            'no_warnings': True,
        }
    else:
        # Video mode - Best quality logic
        quality = prefs.get('quality', 'best')
        
        if quality == 'best':
            format_selector = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        elif quality == '1080':
            format_selector = 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]'
        elif quality == '720':
            format_selector = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]'
        else:
            format_selector = 'best'
            
        return {
            'format': format_selector,
            'outtmpl': os.path.join(user_folder, '%(title)s.%(ext)s'),
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
            'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,  # For private videos
        }

@dp.message(Command("start"))
async def cmd_start(message: Message):
    welcome_text = """
🎥 **Universal Video Downloader Bot**

Mujhe kisi bhi platform ka link bhejo, main video download karke dunga!

✅ Supported Platforms:
• YouTube, Instagram, Facebook
• TikTok, Twitter/X, Snapchat
• Bilibili, VK, Reddit, aur bhi bahut kuch!

⚙️ Commands:
/audio - Audio only mode toggle
/quality - Video quality select karein
/help - Madad

Simply link bhejo!
    """
    await message.answer(welcome_text, parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = """
📝 **Usage Guide:**

1. **Video Download**: Direct link bhejo
2. **Audio Only**: Pehle /audio command bhejo, fir link
3. **Quality**: /quality se 4K/1080p/720p select karo

⚠️ **Note**: 
• Private videos ke liye cookies.txt file chahiye hoti hai
• Bahut bade videos (500MB+) me time lag sakta hai
    """
    await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("audio"))
async def cmd_audio(message: Message):
    user_id = message.from_user.id
    current = user_prefs.get(user_id, {}).get('audio_only', False)
    
    user_prefs[user_id] = user_prefs.get(user_id, {})
    user_prefs[user_id]['audio_only'] = not current
    
    status = "✅ ON" if not current else "❌ OFF"
    mode_text = "Audio Only" if not current else "Video"
    
    await message.answer(f"🔊 Audio Only Mode: {status}\nAb aapko {mode_text} milega!")

@dp.message(Command("quality"))
async def cmd_quality(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥇 Best (4K/Original)", callback_data="qual_best")],
        [InlineKeyboardButton(text="🥈 1080p Full HD", callback_data="qual_1080")],
        [InlineKeyboardButton(text="🥉 720p HD", callback_data="qual_720")],
    ])
    await message.answer("📊 Select Video Quality:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("qual_"))
async def process_quality(callback: CallbackQuery):
    quality = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    user_prefs[user_id] = user_prefs.get(user_id, {})
    user_prefs[user_id]['quality'] = quality
    
    quality_names = {'best': 'Best Available', '1080': '1080p Full HD', '720': '720p HD'}
    await callback.answer(f"Quality set to: {quality_names.get(quality, quality)}")
    await callback.message.edit_text(f"✅ Quality set to: **{quality_names.get(quality, quality)}**\nAb aap link bhej sakte hain!", parse_mode=ParseMode.MARKDOWN)

@dp.message(F.text)
async def download_video(message: Message):
    url = message.text.strip()
    user_id = message.from_user.id
    
    # URL Validation
    if not url.startswith(('http://', 'https://')):
        await message.reply("❌ Invalid URL! Please send a valid link starting with http:// or https://")
        return
    
    if not is_supported_url(url):
        await message.reply("❌ Unsupported platform! Currently supported: YouTube, Instagram, TikTok, Facebook, Twitter, etc.")
        return
    
    # Status message
    status_msg = await message.reply("⏳ Checking link...")
    
    try:
        # Get info first (without downloading)
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Unknown')
            duration = info.get('duration', 0)
            
            # Check file size if possible
            filesize = info.get('filesize') or info.get('filesize_approx', 0)
            
            # Telegram limit check (2GB for bots, 50MB for free users - preferably keep under 50MB for reliability)
            if filesize > 1.9 * 1024 * 1024 * 1024:  # 1.9GB safety limit
                await status_msg.edit_text("❌ File too large! Maximum 1.9GB allowed.")
                return
        
        await status_msg.edit_text(f"📥 Downloading: **{title}**...", parse_mode=ParseMode.MARKDOWN)
        
        # Download
        ydl_opts = get_ydl_opts(user_id, url)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [url])
        
        # Find downloaded file
        user_folder = os.path.join(DOWNLOAD_PATH, str(user_id))
        files = os.listdir(user_folder)
        
        if not files:
            raise Exception("Download failed - no file found")
        
        filename = files[0]
        filepath = os.path.join(user_folder, filename)
        
        # Check if audio or video
        is_audio = user_prefs.get(user_id, {}).get('audio_only', False)
        
        await status_msg.edit_text("📤 Uploading to Telegram...")
        
        # Send file
        if is_audio:
            await message.answer_audio(
                FSInputFile(filepath),
                title=title,
                performer="Video Downloader Bot"
            )
        else:
            # For videos, use answer_video if file is small enough, else document
            file_size = os.path.getsize(filepath)
            
            if file_size < 50 * 1024 * 1024:  # < 50MB as video
                await message.answer_video(FSInputFile(filepath), caption=f"🎬 {title}")
            else:
                await message.answer_document(FSInputFile(filepath), caption=f"🎬 {title}")
        
        # Cleanup
        await status_msg.delete()
        shutil.rmtree(user_folder)
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error for user {user_id}: {error_msg}")
        
        # User-friendly error messages
        if "Private video" in error_msg:
            await status_msg.edit_text("🔒 Private video! Isko download karne ke liye cookies chahiye.")
        elif "Video unavailable" in error_msg:
            await status_msg.edit_text("❌ Video unavailable! Ho sakta hai delete ho gaya ya region restricted ho.")
        elif "HTTP Error 403" in error_msg:
            await status_msg.edit_text("❌ Access forbidden! Platform ne block kar diya.")
        elif "No video formats found" in error_msg:
            await status_msg.edit_text("❌ No downloadable formats found! Ho sakta hai live stream ho.")
        else:
            await status_msg.edit_text(f"❌ Error: {error_msg[:200]}")
        
        # Cleanup on error
        user_folder = os.path.join(DOWNLOAD_PATH, str(user_id))
        if os.path.exists(user_folder):
            shutil.rmtree(user_folder)

async def main():
    # Create download directory
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    
    # Start bot
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
