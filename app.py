import os
import asyncio
import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from pyrogram import Client
from pyrogram.enums import ParseMode, ChatType, UserStatus
from pyrogram.errors import PeerIdInvalid, UsernameNotOccupied, ChannelInvalid
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from contextlib import asynccontextmanager

try:
    from config import API_ID, API_HASH, BOT_TOKEN
except ImportError:
    API_ID = os.getenv("API_ID")
    API_HASH = os.getenv("API_HASH")
    BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

client = None

def get_dc_locations():
    return {
        1: "MIA, Miami, USA, US",
        2: "AMS, Amsterdam, Netherlands, NL",
        3: "MBA, Mumbai, India, IN",
        4: "STO, Stockholm, Sweden, SE",
        5: "SIN, Singapore, SG",
        6: "LHR, London, United Kingdom, GB",
        7: "FRA, Frankfurt, Germany, DE",
        8: "JFK, New York, USA, US",
        9: "HKG, Hong Kong, HK",
        10: "TYO, Tokyo, Japan, JP",
        11: "SYD, Sydney, Australia, AU",
        12: "GRU, São Paulo, Brazil, BR",
        13: "DXB, Dubai, UAE, AE",
        14: "CDG, Paris, France, FR",
        15: "ICN, Seoul, South Korea, KR",
    }

def calculate_account_age(creation_date):
    today = datetime.now()
    delta = relativedelta(today, creation_date)
    years = delta.years
    months = delta.months
    days = delta.days
    return f"{years} years, {months} months, {days} days"

def estimate_account_creation_date(user_id):
    reference_points = [
        (100000000, datetime(2013, 8, 1)),
        (1273841502, datetime(2020, 8, 13)),
        (1500000000, datetime(2021, 5, 1)),
        (2000000000, datetime(2022, 12, 1)),
    ]
    closest_point = min(reference_points, key=lambda x: abs(x[0] - user_id))
    closest_user_id, closest_date = closest_point
    id_difference = user_id - closest_user_id
    days_difference = id_difference / 20000000
    creation_date = closest_date + timedelta(days=days_difference)
    return creation_date

def format_user_status(status):
    if not status:
        return "Unknown"
    status_map = {
        UserStatus.ONLINE: "Online",
        UserStatus.OFFLINE: "Offline",
        UserStatus.RECENTLY: "Recently online",
        UserStatus.LAST_WEEK: "Last seen within week",
        UserStatus.LAST_MONTH: "Last seen within month",
        UserStatus.LONG_AGO: "Last seen long ago"
    }
    return status_map.get(status, "Unknown")

def get_profile_photo_url(username, size=320):
    if username:
        username = username.strip('@')
        return f"https://t.me/i/userpic/{size}/{username}.jpg"
    return None

def format_usernames_list(usernames):
    if not usernames:
        return []
    formatted_usernames = []
    for username_obj in usernames:
        if hasattr(username_obj, 'username'):
            formatted_usernames.append(username_obj.username)
        else:
            formatted_usernames.append(str(username_obj))
    return formatted_usernames

async def get_user_info(username):
    try:
        DC_LOCATIONS = get_dc_locations()
        user = await client.get_users(username)
        
        full_user = await client.get_chat(username)
        bio = getattr(full_user, 'bio', None)
        
        premium_status = getattr(user, 'is_premium', False)
        dc_location = DC_LOCATIONS.get(user.dc_id, "Unknown")
        account_created = estimate_account_creation_date(user.id)
        account_created_str = account_created.strftime("%B %d, %Y")
        account_age = calculate_account_age(account_created)
        verified_status = getattr(user, 'is_verified', False)
        status = format_user_status(getattr(user, 'status', None))
        
        flags = "Clean"
        if getattr(user, 'is_scam', False):
            flags = "Scam"
        elif getattr(user, 'is_fake', False):
            flags = "Fake"
        
        profile_photo_url = get_profile_photo_url(user.username) if user.username else None
        
        last_online_date = None
        next_offline_date = None
        if hasattr(user, 'last_online_date') and user.last_online_date:
            last_online_date = user.last_online_date.strftime("%B %d, %Y at %H:%M:%S")
        if hasattr(user, 'next_offline_date') and user.next_offline_date:
            next_offline_date = user.next_offline_date.strftime("%B %d, %Y at %H:%M:%S")
        
        usernames_list = format_usernames_list(getattr(user, 'usernames', []))
        
        user_data = {
            "success": True,
            "type": "bot" if user.is_bot else "user",
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "usernames": usernames_list,
            "bio": bio,
            "dc_id": user.dc_id,
            "dc_location": dc_location,
            "is_premium": premium_status,
            "is_verified": verified_status,
            "is_bot": user.is_bot,
            "is_scam": getattr(user, 'is_scam', False),
            "is_fake": getattr(user, 'is_fake', False),
            "is_frozen": getattr(user, 'is_frozen', False),
            "frozen_icon": getattr(user, 'frozen_icon', None),
            "flags": flags,
            "status": status,
            "last_online_date": last_online_date,
            "next_offline_date": next_offline_date,
            "account_created": account_created_str,
            "account_age": account_age,
            "profile_photo_url": profile_photo_url,
            "api_dev": "@ISmartCoder",
            "api_updates": "https://t.me/TheSmartDev",
            "links": {
                "android": f"tg://openmessage?user_id={user.id}",
                "ios": f"tg://user?id={user.id}",
                "permanent": f"tg://user?id={user.id}"
            }
        }
        return user_data
    except (PeerIdInvalid, UsernameNotOccupied, IndexError):
        return {"success": False, "error": "User not found"}
    except Exception as e:
        LOGGER.error(f"Error fetching user info: {str(e)}")
        return {"success": False, "error": f"Failed to fetch user information: {str(e)}"}

async def get_chat_info(username):
    try:
        DC_LOCATIONS = get_dc_locations()
        chat = await client.get_chat(username)
        
        chat_type_map = {
            ChatType.SUPERGROUP: "supergroup",
            ChatType.GROUP: "group",
            ChatType.CHANNEL: "channel"
        }
        chat_type = chat_type_map.get(chat.type, "unknown")
        dc_location = DC_LOCATIONS.get(getattr(chat, 'dc_id', None), "Unknown")
        
        profile_photo_url = get_profile_photo_url(chat.username) if chat.username else None
        usernames_list = format_usernames_list(getattr(chat, 'usernames', []))
        
        if chat.username:
            join_link = f"t.me/{chat.username}"
            permanent_link = f"t.me/{chat.username}"
        elif chat.id < 0:
            chat_id_str = str(chat.id).replace('-100', '')
            join_link = f"t.me/c/{chat_id_str}/1"
            permanent_link = f"t.me/c/{chat_id_str}/1"
        else:
            join_link = f"tg://resolve?domain={chat.id}"
            permanent_link = f"tg://resolve?domain={chat.id}"
        
        flags = "Clean"
        if getattr(chat, 'is_scam', False):
            flags = "Scam"
        elif getattr(chat, 'is_fake', False):
            flags = "Fake"
        
        chat_data = {
            "success": True,
            "type": chat_type,
            "id": chat.id,
            "title": chat.title,
            "username": chat.username,
            "usernames": usernames_list,
            "description": getattr(chat, 'description', None),
            "dc_id": getattr(chat, 'dc_id', None),
            "dc_location": dc_location,
            "members_count": getattr(chat, 'members_count', None),
            "is_verified": getattr(chat, 'is_verified', False),
            "is_restricted": getattr(chat, 'is_restricted', False),
            "is_scam": getattr(chat, 'is_scam', False),
            "is_fake": getattr(chat, 'is_fake', False),
            "is_frozen": getattr(chat, 'is_frozen', False),
            "frozen_icon": getattr(chat, 'frozen_icon', None),
            "flags": flags,
            "profile_photo_url": profile_photo_url,
            "api_dev": "@ISmartCoder",
            "api_updates": "https://t.me/TheSmartDev",
            "links": {
                "join": join_link,
                "permanent": permanent_link
            }
        }
        return chat_data
    except (ChannelInvalid, PeerIdInvalid):
        return {"success": False, "error": "Chat not found or access denied"}
    except Exception as e:
        LOGGER.error(f"Error fetching chat info: {str(e)}")
        return {"success": False, "error": f"Failed to fetch chat information: {str(e)}"}

async def get_telegram_info(username):
    username = username.strip('@').replace('https://', '').replace('http://', '').replace('t.me/', '').replace('/', '').replace(':', '')
    LOGGER.info(f"Fetching info for: {username}")
    
    user_info = await get_user_info(username)
    if user_info["success"]:
        return user_info
    
    chat_info = await get_chat_info(username)
    if chat_info["success"]:
        return chat_info
    
    return {"success": False, "error": "Entity not found in Telegram database"}

@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    
    LOGGER.info("Creating Bot Client From BOT_TOKEN")
    os.makedirs("/tmp", exist_ok=True)
    client = Client(
        "GetUserInfo",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        workdir="/tmp",
        in_memory=True
    )
    LOGGER.info("Bot Client Created Successfully!")
    
    await client.start()
    LOGGER.info("Pyrogram client started successfully!")
    
    yield
    
    if client:
        await client.stop()
        LOGGER.info("Pyrogram client stopped!")

app = FastAPI(
    title="Telegram Info API",
    description="Get information about Telegram users, bots, channels, and groups",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/info")
async def info_endpoint(username: str = Query(..., description="Username, user ID, or Telegram link"), size: int = Query(320, description="Profile photo size")):
    try:
        result = await get_telegram_info(username)
        
        if result["success"] and "profile_photo_url" in result and result["profile_photo_url"]:
            result["profile_photo_url"] = get_profile_photo_url(
                result.get("username"), size
            ) if result.get("username") else None
        
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=404, detail=result["error"])
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"API error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    uptime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    bot_status = "connected" if client and client.is_connected else "disconnected"
    
    return {
        "success": True,
        "status": "API is running smoothly ✅",
        "api_info": {
            "name": "Telegram Info API",
            "version": "1.0.0",
            "description": "Advanced Telegram entity information retrieval system",
            "uptime_check": uptime,
            "bot_status": f"Pyrogram Client: {bot_status}",
            "features": [
                "User & Bot Information",
                "Channel & Group Details",
                "Account Age Estimation",
                "Data Center Location",
                "Premium Status Detection",
                "Verification Status",
                "Real-time Status Tracking",
                "Profile Photo URLs",
                "Multiple Usernames Support",
                "Bio Information"
            ]
        },
        "endpoints": {
            "/": "Status Dashboard (HTML)",
            "/info": "Get Telegram entity information",
            "/health": "API health check and information",
            "/docs": "Interactive API documentation",
            "/redoc": "Alternative API documentation"
        },
        "developer": {
            "created_by": "@ISmartCoder",
            "proudly_developed": "Proudly developed by @ISmartCoder ✅",
            "updates_channel": "https://t.me/TheSmartDev",
            "support": "Join our updates channel for latest features!"
        },
        "stats": {
            "supported_entities": ["Users", "Bots", "Channels", "Groups", "Supergroups"],
            "data_centers": len(get_dc_locations()),
            "response_format": "JSON",
            "authentication": "Bot Token Based",
            "deployment": "Vercel Ready with in-memory sessions"
        }
    }

@app.get("/")
async def root():
    try:
        return FileResponse("status.html", media_type="text/html")
    except Exception as e:
        return {
            "success": True,
            "message": "Telegram Info API is running",
            "api_name": "Telegram Info API",
            "status": "Running",
            "developer": "@ISmartCoder",
            "updates_channel": "https://t.me/TheSmartDev",
            "endpoints": {
                "/info": "Get Telegram entity information (requires username parameter)",
                "/health": "API health check and detailed information",
                "/docs": "Interactive API documentation",
                "/redoc": "Alternative API documentation"
            },
            "usage_example": "/info?username=telegram"
        }

if __name__ == "__main__":
    import uvicorn
    LOGGER.info("Starting FastAPI server with Uvicorn...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        log_level="info",
        reload=False
    )