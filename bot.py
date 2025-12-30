"""
TELEGRAM BOT + WEB APP BACKEND
Production-Ready Educational Games Platform
"""

import logging
from datetime import datetime
from typing import Optional
import asyncio
import json

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, MenuButtonWebApp
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
import asyncpg
from asyncpg.pool import Pool

# CORS Middleware
async def cors_middleware(app, handler):
    async def middleware_handler(request):
        # Handle preflight requests
        if request.method == 'OPTIONS':
            response = web.Response()
        else:
            response = await handler(request)
        
        # Add CORS headers
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Max-Age'] = '3600'
        
        return response
    return middleware_handler

# ========================
# CONFIGURATION
# ========================
BOT_TOKEN = "8541500695:AAECtLNSycfJ1eb8TleOu0MXRhEt-rjE8Wk"
WEB_APP_URL = "https://earnest-croquembouche-00781f.netlify.app"
DATABASE_URL = "postgresql://postgres:jQIBmJLVxNraaJWnbvWVXKldgscHbsEP@postgres.railway.internal:5432/railway"
ADMIN_IDS = [1172284285, 1365319493]
WEBHOOK_HOST = "https://worker-production-2313.up.railway.app"
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
API_PORT = 8080
SECRET_TOKEN = "my_super_secret_key_13022005"

# ========================
# LOGGING
# ========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========================
# DATABASE SETUP
# ========================
db_pool: Optional[Pool] = None

async def init_db():
    """Initialize database connection pool"""
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    
    async with db_pool.acquire() as conn:
        # Users table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                phone VARCHAR(50) NOT NULL,
                is_pro BOOLEAN DEFAULT FALSE,
                is_admin BOOLEAN DEFAULT FALSE,
                is_blocked BOOLEAN DEFAULT FALSE,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Games table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id SERIAL PRIMARY KEY,
                game_id VARCHAR(255) UNIQUE NOT NULL,
                creator_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                game_type VARCHAR(100) NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                questions JSONB NOT NULL,
                settings JSONB,
                plays_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_pro_only BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Pro Requests table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pro_requests (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                status VARCHAR(50) DEFAULT 'pending',
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP,
                admin_note TEXT,
                reviewed_by BIGINT
            )
        """)
        
        # Game Results table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS game_results (
                id SERIAL PRIMARY KEY,
                game_id VARCHAR(255) REFERENCES games(game_id) ON DELETE CASCADE,
                player_id BIGINT,
                player_name VARCHAR(255),
                score INTEGER NOT NULL,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Admin logs
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_logs (
                id SERIAL PRIMARY KEY,
                admin_id BIGINT NOT NULL,
                action VARCHAR(255) NOT NULL,
                target_user_id BIGINT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Automatically set admin status for ADMIN_IDS
        for admin_id in ADMIN_IDS:
            await conn.execute("""
                INSERT INTO users (user_id, name, phone, is_admin)
                VALUES ($1, 'Admin', '+998000000000', TRUE)
                ON CONFLICT (user_id) DO UPDATE SET is_admin = TRUE
            """, admin_id)
    
    logger.info("Database initialized successfully")

# ========================
# BOT INITIALIZATION
# ========================
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ========================
# BOT HANDLERS
# ========================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Handle /start command - only show Games button"""
    user_id = message.from_user.id
    
    # Update last active
    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE users SET last_active = CURRENT_TIMESTAMP
            WHERE user_id = $1
        """, user_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎮 O'yinlar",
            web_app=WebAppInfo(url=WEB_APP_URL)
        )],
        [InlineKeyboardButton(
            text="📞 Admin bilan bog'lanish",
            url=f"tg://user?id={ADMIN_IDS[0]}"
        )]
    ])
    
    await message.answer(
        "🎮 <b>Ta'limiy O'yinlar Platformasiga Xush Kelibsiz!</b>\n\n"
        "📚 20+ turli o'yin mavjud\n"
        "🎯 O'z o'yiningizni yarating va ulashing\n"
        "🏆 PRO funksiyalar bilan yanada ko'proq imkoniyatlar\n\n"
        "Boshlash uchun <b>O'yinlar</b> tugmasini bosing 👇",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Admin panel access"""
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("❌ Sizda admin huquqi yo'q!")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="👨‍💼 Admin Panel",
            web_app=WebAppInfo(url=f"{WEB_APP_URL}?admin=true")
        )]
    ])
    
    await message.answer(
        "👨‍💼 <b>Admin Panel</b>\n\n"
        "Admin paneliga kirish uchun tugmani bosing:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Show user statistics"""
    user_id = message.from_user.id
    
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        
        if not user:
            await message.answer("❌ Siz ro'yxatdan o'tmagansiz! Web App orqali ro'yxatdan o'ting.")
            return
        
        games_count = await conn.fetchval(
            "SELECT COUNT(*) FROM games WHERE creator_id = $1", user_id
        )
        
        total_plays = await conn.fetchval(
            "SELECT COALESCE(SUM(plays_count), 0) FROM games WHERE creator_id = $1", user_id
        )
    
    status = "⭐ PRO" if user['is_pro'] else "🆓 Free"
    
    await message.answer(
        f"📊 <b>Statistikangiz:</b>\n\n"
        f"👤 Ism: {user['name']}\n"
        f"📱 Telefon: {user['phone']}\n"
        f"🎯 Status: {status}\n"
        f"🎮 Yaratilgan o'yinlar: {games_count}\n"
        f"▶️ Jami o'ynashlar: {total_plays}\n"
        f"📅 Ro'yxatdan o'tgan: {user['registered_at'].strftime('%d.%m.%Y')}",
        parse_mode="HTML"
    )

# ========================
# REST API
# ========================
routes = web.RouteTableDef()

async def verify_token(request):
    """Verify API token"""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return False
    token = auth_header[7:]
    return token == SECRET_TOKEN

@routes.post('/api/register')
async def register_user(request):
    """Register new user"""
    try:
        data = await request.json()
        user_id = data.get('user_id')
        name = data.get('name')
        phone = data.get('phone')
        
        if not all([user_id, name, phone]):
            return web.json_response({'error': 'Missing required fields'}, status=400)
        
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, name, phone)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE
                SET name = $2, phone = $3, last_active = CURRENT_TIMESTAMP
            """, user_id, name, phone)
        
        logger.info(f"User registered: {user_id} - {name}")
        return web.json_response({'success': True, 'message': 'User registered'})
    
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return web.json_response({'error': str(e)}, status=500)

@routes.get('/api/user/{user_id}')
async def get_user(request):
    """Get user info"""
    user_id = int(request.match_info['user_id'])
    
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("""
            SELECT user_id, name, phone, is_pro, is_admin, is_blocked, 
                   registered_at, last_active
            FROM users WHERE user_id = $1
        """, user_id)
        
        if not user:
            return web.json_response({'error': 'User not found'}, status=404)
        
        return web.json_response({
            'user_id': user['user_id'],
            'name': user['name'],
            'phone': user['phone'],
            'is_pro': user['is_pro'],
            'is_admin': user['is_admin'],
            'is_blocked': user['is_blocked'],
            'registered_at': user['registered_at'].isoformat(),
            'last_active': user['last_active'].isoformat()
        })

@routes.post('/api/games')
async def create_game(request):
    """Create new game"""
    if not await verify_token(request):
        return web.json_response({'error': 'Unauthorized'}, status=401)
    
    try:
        data = await request.json()
        creator_id = data.get('creator_id')
        game_type = data.get('game_type')
        title = data.get('title')
        description = data.get('description', '')
        questions = data.get('questions', [])
        settings = data.get('settings', {})
        is_pro_only = data.get('is_pro_only', False)
        
        # Generate unique game_id
        import uuid
        game_id = str(uuid.uuid4())[:8]
        
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO games (game_id, creator_id, game_type, title, description, 
                                 questions, settings, is_pro_only)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, game_id, creator_id, game_type, title, description, 
                 json.dumps(questions), json.dumps(settings), is_pro_only)
        
        logger.info(f"Game created: {game_id} by user {creator_id}")
        return web.json_response({
            'success': True,
            'game_id': game_id,
            'share_url': f"{WEB_APP_URL}?game={game_id}"
        })
    
    except Exception as e:
        logger.error(f"Game creation error: {e}")
        return web.json_response({'error': str(e)}, status=500)

@routes.get('/api/games/{game_id}')
async def get_game(request):
    """Get game details"""
    game_id = request.match_info['game_id']
    
    async with db_pool.acquire() as conn:
        game = await conn.fetchrow("""
            SELECT g.*, u.name as creator_name
            FROM games g
            JOIN users u ON g.creator_id = u.user_id
            WHERE g.game_id = $1
        """, game_id)
        
        if not game:
            return web.json_response({'error': 'Game not found'}, status=404)
        
        # Increment plays count
        await conn.execute("""
            UPDATE games SET plays_count = plays_count + 1 
            WHERE game_id = $1
        """, game_id)
        
        return web.json_response({
            'game_id': game['game_id'],
            'creator_id': game['creator_id'],
            'creator_name': game['creator_name'],
            'game_type': game['game_type'],
            'title': game['title'],
            'description': game['description'],
            'questions': json.loads(game['questions']),
            'settings': json.loads(game['settings']) if game['settings'] else {},
            'plays_count': game['plays_count'],
            'is_pro_only': game['is_pro_only'],
            'created_at': game['created_at'].isoformat()
        })

@routes.get('/api/my-games/{user_id}')
async def get_my_games(request):
    """Get user's games"""
    user_id = int(request.match_info['user_id'])
    
    async with db_pool.acquire() as conn:
        games = await conn.fetch("""
            SELECT game_id, game_type, title, description, plays_count, 
                   created_at, is_pro_only
            FROM games
            WHERE creator_id = $1
            ORDER BY created_at DESC
        """, user_id)
        
        return web.json_response([{
            'game_id': g['game_id'],
            'game_type': g['game_type'],
            'title': g['title'],
            'description': g['description'],
            'plays_count': g['plays_count'],
            'is_pro_only': g['is_pro_only'],
            'created_at': g['created_at'].isoformat(),
            'share_url': f"{WEB_APP_URL}?game={g['game_id']}"
        } for g in games])

@routes.post('/api/pro-request')
async def request_pro(request):
    """Request PRO access"""
    if not await verify_token(request):
        return web.json_response({'error': 'Unauthorized'}, status=401)
    
    try:
        data = await request.json()
        user_id = data.get('user_id')
        
        async with db_pool.acquire() as conn:
            # Check if already pro
            is_pro = await conn.fetchval(
                "SELECT is_pro FROM users WHERE user_id = $1", user_id
            )
            
            if is_pro:
                return web.json_response({'error': 'Already PRO user'}, status=400)
            
            # Check if already has pending request
            existing = await conn.fetchval("""
                SELECT id FROM pro_requests 
                WHERE user_id = $1 AND status = 'pending'
            """, user_id)
            
            if existing:
                return web.json_response({'error': 'Request already pending'}, status=400)
            
            # Create request
            await conn.execute("""
                INSERT INTO pro_requests (user_id, status)
                VALUES ($1, 'pending')
            """, user_id)
        
        # Notify admins
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"📨 <b>Yangi PRO so'rov!</b>\n\n"
                    f"User ID: {user_id}\n"
                    f"Admin paneldan ko'rib chiqing.",
                    parse_mode="HTML"
                )
            except:
                pass
        
        logger.info(f"PRO request created for user {user_id}")
        return web.json_response({'success': True, 'message': 'Request submitted'})
    
    except Exception as e:
        logger.error(f"PRO request error: {e}")
        return web.json_response({'error': str(e)}, status=500)

@routes.get('/api/admin/pro-requests')
async def get_pro_requests(request):
    """Get all PRO requests (admin only)"""
    if not await verify_token(request):
        return web.json_response({'error': 'Unauthorized'}, status=401)
    
    async with db_pool.acquire() as conn:
        requests = await conn.fetch("""
            SELECT pr.*, u.name, u.phone
            FROM pro_requests pr
            JOIN users u ON pr.user_id = u.user_id
            ORDER BY pr.requested_at DESC
        """)
        
        return web.json_response([{
            'id': r['id'],
            'user_id': r['user_id'],
            'name': r['name'],
            'phone': r['phone'],
            'status': r['status'],
            'requested_at': r['requested_at'].isoformat(),
            'reviewed_at': r['reviewed_at'].isoformat() if r['reviewed_at'] else None,
            'admin_note': r['admin_note']
        } for r in requests])

@routes.post('/api/admin/approve-pro')
async def approve_pro(request):
    """Approve PRO request (admin only)"""
    if not await verify_token(request):
        return web.json_response({'error': 'Unauthorized'}, status=401)
    
    try:
        data = await request.json()
        request_id = data.get('request_id')
        admin_id = data.get('admin_id')
        admin_note = data.get('admin_note', '')
        action = data.get('action', 'approve')  # approve or reject
        
        async with db_pool.acquire() as conn:
            # Get request
            req = await conn.fetchrow("""
                SELECT user_id FROM pro_requests WHERE id = $1
            """, request_id)
            
            if not req:
                return web.json_response({'error': 'Request not found'}, status=404)
            
            user_id = req['user_id']
            
            if action == 'approve':
                # Grant PRO status
                await conn.execute("""
                    UPDATE users SET is_pro = TRUE WHERE user_id = $1
                """, user_id)
                
                # Update request
                await conn.execute("""
                    UPDATE pro_requests 
                    SET status = 'approved', reviewed_at = CURRENT_TIMESTAMP,
                        admin_note = $1, reviewed_by = $2
                    WHERE id = $3
                """, admin_note, admin_id, request_id)
                
                # Notify user
                try:
                    await bot.send_message(
                        user_id,
                        "🎉 <b>Tabriklaymiz!</b>\n\n"
                        "PRO statusingiz tasdiqlandi! Endi barcha PRO funksiyalardan foydalanishingiz mumkin.\n\n"
                        f"💬 Admin izohi: {admin_note}" if admin_note else "",
                        parse_mode="HTML"
                    )
                except:
                    pass
                
                # Log
                await conn.execute("""
                    INSERT INTO admin_logs (admin_id, action, target_user_id, details)
                    VALUES ($1, $2, $3, $4)
                """, admin_id, 'approve_pro', user_id, admin_note)
                
                message = 'PRO approved'
            else:
                # Reject request
                await conn.execute("""
                    UPDATE pro_requests 
                    SET status = 'rejected', reviewed_at = CURRENT_TIMESTAMP,
                        admin_note = $1, reviewed_by = $2
                    WHERE id = $3
                """, admin_note, admin_id, request_id)
                
                # Notify user
                try:
                    await bot.send_message(
                        user_id,
                        "❌ <b>PRO so'rovi rad etildi</b>\n\n"
                        f"💬 Sabab: {admin_note}" if admin_note else "PRO so'rovingiz ko'rib chiqildi.",
                        parse_mode="HTML"
                    )
                except:
                    pass
                
                # Log
                await conn.execute("""
                    INSERT INTO admin_logs (admin_id, action, target_user_id, details)
                    VALUES ($1, $2, $3, $4)
                """, admin_id, 'reject_pro', user_id, admin_note)
                
                message = 'PRO rejected'
        
        logger.info(f"PRO request {request_id} {action}ed by admin {admin_id}")
        return web.json_response({'success': True, 'message': message})
    
    except Exception as e:
        logger.error(f"PRO approval error: {e}")
        return web.json_response({'error': str(e)}, status=500)

@routes.get('/api/admin/users')
async def get_all_users(request):
    """Get all users (admin only)"""
    if not await verify_token(request):
        return web.json_response({'error': 'Unauthorized'}, status=401)
    
    async with db_pool.acquire() as conn:
        users = await conn.fetch("""
            SELECT u.user_id, u.name, u.phone, u.is_pro, u.is_blocked, 
                   u.registered_at, u.last_active,
                   COUNT(DISTINCT g.id) as games_count,
                   COALESCE(SUM(g.plays_count), 0) as total_plays
            FROM users u
            LEFT JOIN games g ON u.user_id = g.creator_id
            WHERE u.is_admin = FALSE
            GROUP BY u.user_id
            ORDER BY u.registered_at DESC
        """)
        
        return web.json_response([{
            'user_id': u['user_id'],
            'name': u['name'],
            'phone': u['phone'],
            'is_pro': u['is_pro'],
            'is_blocked': u['is_blocked'],
            'games_count': u['games_count'],
            'total_plays': u['total_plays'],
            'registered_at': u['registered_at'].isoformat(),
            'last_active': u['last_active'].isoformat()
        } for u in users])

@routes.post('/api/admin/block-user')
async def block_user(request):
    """Block/unblock user (admin only)"""
    if not await verify_token(request):
        return web.json_response({'error': 'Unauthorized'}, status=401)
    
    try:
        data = await request.json()
        user_id = data.get('user_id')
        blocked = data.get('blocked', True)
        admin_id = data.get('admin_id')
        
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE users SET is_blocked = $1 WHERE user_id = $2
            """, blocked, user_id)
            
            action = 'block_user' if blocked else 'unblock_user'
            await conn.execute("""
                INSERT INTO admin_logs (admin_id, action, target_user_id)
                VALUES ($1, $2, $3)
            """, admin_id, action, user_id)
        
        logger.info(f"User {user_id} {'blocked' if blocked else 'unblocked'} by admin {admin_id}")
        return web.json_response({'success': True})
    
    except Exception as e:
        logger.error(f"Block user error: {e}")
        return web.json_response({'error': str(e)}, status=500)

@routes.get('/api/admin/stats')
async def get_admin_stats(request):
    """Get platform statistics (admin only)"""
    if not await verify_token(request):
        return web.json_response({'error': 'Unauthorized'}, status=401)
    
    async with db_pool.acquire() as conn:
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_admin = FALSE")
        pro_users = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_pro = TRUE")
        total_games = await conn.fetchval("SELECT COUNT(*) FROM games")
        total_plays = await conn.fetchval("SELECT COALESCE(SUM(plays_count), 0) FROM games")
        pending_requests = await conn.fetchval(
            "SELECT COUNT(*) FROM pro_requests WHERE status = 'pending'"
        )
        
        return web.json_response({
            'total_users': total_users,
            'pro_users': pro_users,
            'total_games': total_games,
            'total_plays': total_plays,
            'pending_requests': pending_requests
        })

@routes.post('/webhook')
async def webhook_handler(request):
    """Handle Telegram webhook"""
    update = await request.json()
    telegram_update = types.Update(**update)
    await dp.feed_update(bot, telegram_update)
    return web.Response()

# ========================
# APPLICATION STARTUP
# ========================
async def on_startup(app):
    """Initialize on startup"""
    await init_db()
    
    await bot.set_webhook(
        url=WEBHOOK_URL,
        allowed_updates=dp.resolve_used_update_types()
    )
    logger.info(f"Webhook set to {WEBHOOK_URL}")
    
    # Set menu button
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="🎮 O'yinlar",
            web_app=WebAppInfo(url=WEB_APP_URL)
        )
    )
    logger.info("Bot started successfully")

async def on_shutdown(app):
    """Cleanup on shutdown"""
    if db_pool:
        await db_pool.close()
    await bot.session.close()
    logger.info("Bot stopped")

# ========================
# MAIN
# ========================
def main():
    """Main entry point"""
    app = web.Application(middlewares=[cors_middleware])
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    # Webhook mode
    web.run_app(app, host='0.0.0.0', port=API_PORT)

if __name__ == '__main__':
    main()