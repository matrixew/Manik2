import os
import json
import asyncio
import threading
import logging
import calendar
import smtplib
import random
import uuid
import hashlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_from_directory, session
import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    BotCommand, WebAppInfo
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

load_dotenv()

# ===== НАСТРОЙКА ЛОГИРОВАНИЯ =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== КОНФИГУРАЦИЯ =====
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8968782590:AAGmY5PtCdsNg32iYxJetiFEwf9tFtB9iiA')
TELEGRAM_CHAT_ID = int(os.getenv('TELEGRAM_CHAT_ID', '1922216067'))

def is_admin_user(user_id):
    try:
        return str(user_id).strip() == str(TELEGRAM_CHAT_ID).strip()
    except Exception:
        return False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BOOKINGS_FILE = os.getenv('BOOKINGS_FILE', os.path.join(BASE_DIR, 'booking.json'))
USERS_FILE = os.getenv('USERS_FILE', os.path.join(BASE_DIR, 'users.json'))
PROMOS_FILE = os.getenv('PROMOS_FILE', os.path.join(BASE_DIR, 'promos.json'))
REVIEWS_FILE = os.getenv('REVIEWS_FILE', os.path.join(BASE_DIR, 'reviews.json'))
SERVICES_FILE = os.getenv('SERVICES_FILE', os.path.join(BASE_DIR, 'services.json'))
MASTERS_FILE = os.getenv('MASTERS_FILE', os.path.join(BASE_DIR, 'masters.json'))

SITE_URL = os.getenv('SITE_URL', 'http://BotProk.wisp.uno')
SALON_NAME = os.getenv('SALON_NAME', 'BotProk Nails')

# ===== НАСТРОЙКА SMTP (Mail.ru) =====
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.mail.ru')
SMTP_PORT = int(os.getenv('SMTP_PORT', '465'))
SMTP_EMAIL = os.getenv('SMTP_EMAIL', 'botprok@mail.ru')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', 'ShODst24YUVYhKamT04T')
SMTP_USE_SSL = os.getenv('SMTP_USE_SSL', 'True').lower() in ('true', '1', 't')

# ===== ДАННЫЕ =====
SERVICES = [
    {'id': 'classic', 'name': 'Классический маникюр', 'price': '1 500 ₽', 'duration': '60 мин', 'duration_minutes': 60, 'price_num': 1500},
    {'id': 'hardware', 'name': 'Аппаратный маникюр', 'price': '1 700 ₽', 'duration': '60 мин', 'duration_minutes': 60, 'price_num': 1700},
    {'id': 'pedicure', 'name': 'Педикюр', 'price': '2 500 ₽', 'duration': '90 мин', 'duration_minutes': 90, 'price_num': 2500},
    {'id': 'gel', 'name': 'Покрытие гель-лаком', 'price': '2 000 ₽', 'duration': '60 мин', 'duration_minutes': 60, 'price_num': 2000},
    {'id': 'complex', 'name': 'Маникюр + покрытие', 'price': '3 000 ₽', 'duration': '90 мин', 'duration_minutes': 90, 'price_num': 3000},
    {'id': 'spa', 'name': 'SPA-маникюр', 'price': '3 500 ₽', 'duration': '90 мин', 'duration_minutes': 90, 'price_num': 3500}
]

MASTERS = [
    {'id': 'anna', 'name': 'Анна Соколова', 'experience': '10 лет'},
    {'id': 'ekaterina', 'name': 'Екатерина Волкова', 'experience': '7 лет'},
    {'id': 'maria', 'name': 'Мария Петрова', 'experience': '5 лет'},
    {'id': 'olga', 'name': 'Ольга Иванова', 'experience': '8 лет'},
    {'id': 'daria', 'name': 'Дарья Кузнецова', 'experience': '4 года'},
    {'id': 'elena', 'name': 'Елена Смирнова', 'experience': '6 лет'}
]

def load_services_data():
    if os.path.exists(SERVICES_FILE):
        try:
            with open(SERVICES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    save_services_data(SERVICES)
    return SERVICES

def save_services_data(services):
    try:
        with open(SERVICES_FILE, 'w', encoding='utf-8') as f:
            json.dump(services, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения услуг: {e}")

def load_masters_data():
    if os.path.exists(MASTERS_FILE):
        try:
            with open(MASTERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    save_masters_data(MASTERS)
    return MASTERS

def save_masters_data(masters):
    try:
        with open(MASTERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(masters, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения мастеров: {e}")

def load_promos():
    if os.path.exists(PROMOS_FILE):
        try:
            with open(PROMOS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    default_promos = [
        {'code': 'FIRST10', 'discount_type': 'percent', 'discount_value': 10, 'active': True},
        {'code': 'WELCOME500', 'discount_type': 'fixed', 'discount_value': 500, 'active': True}
    ]
    save_promos(default_promos)
    return default_promos

def save_promos(promos):
    try:
        with open(PROMOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(promos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения промокодов: {e}")

def load_reviews():
    if os.path.exists(REVIEWS_FILE):
        try:
            with open(REVIEWS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_reviews(reviews):
    try:
        with open(REVIEWS_FILE, 'w', encoding='utf-8') as f:
            json.dump(reviews, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения отзывов: {e}")


AVAILABLE_TIMES = [f"{h:02d}:00" for h in range(10, 21)]

# ============================================
# РАБОТА С JSON-ФАЙЛАМИ
# ============================================

def repair_bookings_file():
    try:
        if not os.path.exists(BOOKINGS_FILE):
            return
        
        with open(BOOKINGS_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        if not content:
            save_bookings([])
            logger.info("Файл bookings.json был пуст, создан новый")
            return
        
        try:
            json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Файл bookings.json поврежден, создается новый")
            save_bookings([])
    except Exception as e:
        logger.error(f"Ошибка восстановления bookings.json: {e}")

def load_bookings():
    try:
        if os.path.exists(BOOKINGS_FILE):
            with open(BOOKINGS_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return []
                bookings = json.loads(content)
                if not isinstance(bookings, list):
                    bookings = []
                max_id = 0
                for i, booking in enumerate(bookings):
                    if not isinstance(booking, dict):
                        continue
                    if 'id' not in booking:
                        booking['id'] = i + 1
                    if booking['id'] > max_id:
                        max_id = booking['id']
                    if 'name' in booking and 'client_name' not in booking:
                        booking['client_name'] = booking['name']
                    if 'phone' in booking and 'client_phone' not in booking:
                        booking['client_phone'] = booking['phone']
                    if 'status' not in booking:
                        booking['status'] = 'active'
                    if 'price' not in booking:
                        booking['price'] = 0
                save_bookings(bookings)
                return bookings
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON в bookings.json: {e}")
        save_bookings([])
        return []
    except Exception as e:
        logger.error(f"Ошибка загрузки записей: {e}")
        return []

def save_bookings(bookings):
    try:
        with open(BOOKINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(bookings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения записей: {e}")
        return False

def load_users():
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'users': {}}
    except Exception as e:
        logger.error(f"Ошибка загрузки пользователей: {e}")
        return {'users': {}}

def save_users(users_data):
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения пользователей: {e}")
        return False

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_verification_code():
    return str(random.randint(1000, 9999))

def send_email(to_email, code):
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['To'] = to_email
        msg['Subject'] = 'Код подтверждения BotProk'

        body = f"""
        Здравствуйте!

        Ваш код подтверждения для восстановления пароля: {code}

        Если вы не запрашивали восстановление пароля, просто проигнорируйте это письмо.

        С уважением,
        Команда BotProk
        """
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        if SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            server.starttls()

        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        logger.info(f"Письмо отправлено на {to_email}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки письма: {e}")
        return False

# ============================================
# ОБНОВЛЕНИЕ СТАТУСОВ ЗАПИСЕЙ
# ============================================

def update_booking_statuses():
    try:
        bookings = load_bookings()
        if not bookings:
            return
        
        now = datetime.now()
        updated = False
        
        for booking in bookings:
            if not isinstance(booking, dict):
                continue
            if booking.get('status') != 'active':
                continue
            
            try:
                booking_datetime = datetime.strptime(f"{booking['date']} {booking['time']}", "%Y-%m-%d %H:%M")
                
                service_name = booking.get('service', '')
                duration_minutes = 0
                for service in SERVICES:
                    if service['name'] == service_name:
                        duration_minutes = service.get('duration_minutes', 0)
                        break
                
                if duration_minutes == 0:
                    continue
                
                end_time = booking_datetime + timedelta(minutes=duration_minutes)
                
                if now > end_time:
                    booking['status'] = 'completed'
                    updated = True
                    logger.info(f"Запись #{booking.get('id')} завершена")
                    
            except Exception as e:
                logger.error(f"Ошибка обработки записи #{booking.get('id')}: {e}")
                continue
        
        if updated:
            save_bookings(bookings)
            logger.info("Статусы записей обновлены")
            
    except Exception as e:
        logger.error(f"Ошибка обновления статусов: {e}")

def get_bookings_with_status_update():
    update_booking_statuses()
    return load_bookings()

# ============================================
# РАБОТА С ЗАПИСЯМИ
# ============================================

def add_booking(data):
    bookings = load_bookings()
    max_id = max([b.get('id', 0) for b in bookings if isinstance(b, dict)]) if bookings else 0
    new_id = max_id + 1
    booking = {
        'id': new_id,
        'name': data.get('name', ''),
        'phone': data.get('phone', ''),
        'client_name': data.get('name', ''),
        'client_phone': data.get('phone', ''),
        'service': data['service'],
        'master': data['master'],
        'master_id': data.get('master_id', ''),
        'date': data['date'],
        'time': data['time'],
        'price': data.get('price', 0),
        'status': 'active',
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    bookings.append(booking)
    save_bookings(bookings)
    return new_id

def get_bookings_by_date(date):
    bookings = get_bookings_with_status_update()
    return [b for b in bookings if isinstance(b, dict) and b.get('date') == date]

def get_bookings_by_date_master(date, master):
    bookings = get_bookings_with_status_update()
    return [b for b in bookings if isinstance(b, dict) and b.get('date') == date and b.get('master') == master]

def get_stats():
    bookings = get_bookings_with_status_update()
    stats = {}
    today = datetime.now()
    for i in range(30):
        date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        count = len([b for b in bookings if isinstance(b, dict) and b.get('date') == date])
        if count > 0:
            stats[date] = count
    return stats

def get_all_bookings():
    return get_bookings_with_status_update()

def get_bookings_for_date(date):
    return get_bookings_by_date(date)

def delete_booking(booking_id):
    bookings = load_bookings()
    for booking in bookings:
        if isinstance(booking, dict) and booking.get('id') == booking_id:
            booking['status'] = 'canceled'
            save_bookings(bookings)
            return True
    return False

def delete_all_bookings():
    bookings = load_bookings()
    if not bookings:
        return False
    save_bookings([])
    return True

def get_masters_list():
    return [m['name'] for m in MASTERS]

def get_master_stats():
    bookings = get_bookings_with_status_update()
    stats = {}
    for b in bookings:
        if not isinstance(b, dict):
            continue
        master = b.get('master', '')
        if master not in stats:
            stats[master] = 0
        stats[master] += 1
    for m in MASTERS:
        if m['name'] not in stats:
            stats[m['name']] = 0
    return stats

def get_master_calendar(master, year, month):
    bookings = get_bookings_with_status_update()
    days_with_bookings = set()
    for b in bookings:
        if not isinstance(b, dict):
            continue
        if b.get('status') == 'canceled':
            continue
        b_master = b.get('master', b.get('master_id', ''))
        if b_master == master:
            try:
                date_obj = datetime.strptime(b['date'], '%Y-%m-%d')
                if date_obj.year == year and date_obj.month == month:
                    days_with_bookings.add(date_obj.day)
            except:
                pass
    return days_with_bookings

def get_master_month_stats(master, year, month):
    bookings = get_bookings_with_status_update()
    total = 0
    for b in bookings:
        if not isinstance(b, dict):
            continue
        if b.get('status') == 'canceled':
            continue
        b_master = b.get('master', b.get('master_id', ''))
        if b_master == master:
            try:
                date_obj = datetime.strptime(b['date'], '%Y-%m-%d')
                if date_obj.year == year and date_obj.month == month:
                    total += 1
            except:
                pass
    return total

def get_month_bookings(year, month):
    bookings = get_bookings_with_status_update()
    result = {}
    for b in bookings:
        if not isinstance(b, dict):
            continue
        if b.get('status') == 'canceled':
            continue
        try:
            date_obj = datetime.strptime(b['date'], '%Y-%m-%d')
            if date_obj.year == year and date_obj.month == month:
                day = date_obj.day
                if day not in result:
                    result[day] = []
                result[day].append(b)
        except:
            pass
    return result

def get_master_month_bookings(master, year, month):
    bookings = get_bookings_with_status_update()
    result = {}
    for b in bookings:
        if not isinstance(b, dict):
            continue
        if b.get('status') == 'canceled':
            continue
        b_master = b.get('master', b.get('master_id', ''))
        if b_master == master:
            try:
                date_obj = datetime.strptime(b['date'], '%Y-%m-%d')
                if date_obj.year == year and date_obj.month == month:
                    day = date_obj.day
                    if day not in result:
                        result[day] = []
                    result[day].append(b)
            except:
                pass
    return result

def get_revenue_stats():
    bookings = get_bookings_with_status_update()
    stats = {
        'today': {'count': 0, 'revenue': 0, 'by_service': {}, 'by_master': {}},
        'week': {'count': 0, 'revenue': 0, 'by_service': {}, 'by_master': {}},
        'month': {'count': 0, 'revenue': 0, 'by_service': {}, 'by_master': {}},
        'total': {'count': 0, 'revenue': 0, 'by_service': {}, 'by_master': {}},
        'by_month': {}
    }
    
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    for b in bookings:
        if not isinstance(b, dict):
            continue
        if b.get('status') == 'canceled':
            continue
            
        price = b.get('price', 0)
        service = b.get('service', '')
        master = b.get('master', '')
        date = b.get('date', '')
        
        if date:
            month_key = date[:7]
            if month_key not in stats['by_month']:
                stats['by_month'][month_key] = {'count': 0, 'revenue': 0, 'by_service': {}, 'by_master': {}}
            stats['by_month'][month_key]['count'] += 1
            stats['by_month'][month_key]['revenue'] += price
            if service not in stats['by_month'][month_key]['by_service']:
                stats['by_month'][month_key]['by_service'][service] = {'count': 0, 'revenue': 0}
            stats['by_month'][month_key]['by_service'][service]['count'] += 1
            stats['by_month'][month_key]['by_service'][service]['revenue'] += price
            if master not in stats['by_month'][month_key]['by_master']:
                stats['by_month'][month_key]['by_master'][master] = {'count': 0, 'revenue': 0}
            stats['by_month'][month_key]['by_master'][master]['count'] += 1
            stats['by_month'][month_key]['by_master'][master]['revenue'] += price
        
        stats['total']['count'] += 1
        stats['total']['revenue'] += price
        if service not in stats['total']['by_service']:
            stats['total']['by_service'][service] = {'count': 0, 'revenue': 0}
        stats['total']['by_service'][service]['count'] += 1
        stats['total']['by_service'][service]['revenue'] += price
        if master not in stats['total']['by_master']:
            stats['total']['by_master'][master] = {'count': 0, 'revenue': 0}
        stats['total']['by_master'][master]['count'] += 1
        stats['total']['by_master'][master]['revenue'] += price
        
        if b.get('date') == today:
            stats['today']['count'] += 1
            stats['today']['revenue'] += price
            if service not in stats['today']['by_service']:
                stats['today']['by_service'][service] = {'count': 0, 'revenue': 0}
            stats['today']['by_service'][service]['count'] += 1
            stats['today']['by_service'][service]['revenue'] += price
            if master not in stats['today']['by_master']:
                stats['today']['by_master'][master] = {'count': 0, 'revenue': 0}
            stats['today']['by_master'][master]['count'] += 1
            stats['today']['by_master'][master]['revenue'] += price
        
        if b.get('date') >= week_ago:
            stats['week']['count'] += 1
            stats['week']['revenue'] += price
            if service not in stats['week']['by_service']:
                stats['week']['by_service'][service] = {'count': 0, 'revenue': 0}
            stats['week']['by_service'][service]['count'] += 1
            stats['week']['by_service'][service]['revenue'] += price
            if master not in stats['week']['by_master']:
                stats['week']['by_master'][master] = {'count': 0, 'revenue': 0}
            stats['week']['by_master'][master]['count'] += 1
            stats['week']['by_master'][master]['revenue'] += price
        
        if b.get('date') >= month_ago:
            stats['month']['count'] += 1
            stats['month']['revenue'] += price
            if service not in stats['month']['by_service']:
                stats['month']['by_service'][service] = {'count': 0, 'revenue': 0}
            stats['month']['by_service'][service]['count'] += 1
            stats['month']['by_service'][service]['revenue'] += price
            if master not in stats['month']['by_master']:
                stats['month']['by_master'][master] = {'count': 0, 'revenue': 0}
            stats['month']['by_master'][master]['count'] += 1
            stats['month']['by_master'][master]['revenue'] += price
    
    return stats

def get_client_stats():
    bookings = get_bookings_with_status_update()
    clients = {}
    
    for b in bookings:
        if not isinstance(b, dict):
            continue
        phone = b.get('client_phone', b.get('phone', ''))
        if phone:
            if phone not in clients:
                clients[phone] = {
                    'name': b.get('client_name', b.get('name', '')),
                    'visits': 0,
                    'total_spent': 0,
                    'last_visit': None
                }
            clients[phone]['visits'] += 1
            clients[phone]['total_spent'] += b.get('price', 0)
            if not clients[phone]['last_visit'] or b.get('date') > clients[phone]['last_visit']:
                clients[phone]['last_visit'] = b.get('date')
    
    return clients

# ============================================
# ИНИЦИАЛИЗАЦИЯ АДМИНИСТРАТОРА
# ============================================

def init_admin():
    users = load_users()
    if 'users' not in users:
        users['users'] = {}
    
    admin_exists = False
    for user_id, user_data in users['users'].items():
        if user_data.get('role') == 'admin':
            admin_exists = True
            break
    
    if not admin_exists:
        admin_id = str(uuid.uuid4())
        users['users'][admin_id] = {
            'id': admin_id,
            'name': 'Admin',
            'phone': 'admin',
            'email': 'admin@botprok.ru',
            'password': hash_password('admin123'),
            'role': 'admin'
        }
        save_users(users)
        logger.info("Администратор создан: Admin / admin123")

# ============================================
# FLASK — САЙТ
# ============================================

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'supersecretkey_botprok_2026'

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": SALON_NAME,
        "short_name": "BotProk",
        "description": "Онлайн-запись на маникюр",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#F8F6FD",
        "theme_color": "#6C3B9E",
        "icons": [
            {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png"}
        ]
    })

@app.route('/sw.js')
def service_worker():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

@app.route('/api/services')
def get_services():
    return jsonify(load_services_data())

@app.route('/api/masters')
def get_masters():
    return jsonify(load_masters_data())

@app.route('/api/times')
def get_times():
    date = request.args.get('date')
    master_id = request.args.get('master_id')
    
    if not date or not master_id:
        return jsonify([{'time': t, 'booked': False} for t in AVAILABLE_TIMES])
    
    try:
        master_obj = next((m for m in MASTERS if m['id'] == master_id), None)
        if not master_obj:
            return jsonify([{'time': t, 'booked': False} for t in AVAILABLE_TIMES])
        
        master_name = master_obj['name']
        bookings = get_bookings_by_date_master(date, master_name)
        
        # УЧИТЫВАЕМ ВСЕ ЗАПИСИ КРОМЕ ОТМЕНЕННЫХ
        booked_times = [b['time'] for b in bookings if b.get('status') != 'canceled']
        
        available = []
        for time in AVAILABLE_TIMES:
            is_booked = time in booked_times
            available.append({
                'time': time,
                'booked': is_booked
            })
        return jsonify(available)
    except Exception as e:
        logger.error(f"Ошибка в /api/times: {e}")
        return jsonify([{'time': t, 'booked': False} for t in AVAILABLE_TIMES])

@app.route('/api/book', methods=['POST'])
def book():
    try:
        data = request.json
        logger.info(f"Бронирование: {data}")
        
        name = data.get('name')
        phone = data.get('phone')
        service = data.get('service')
        master = data.get('master')
        master_id = data.get('master_id')
        date = data.get('date')
        time = data.get('time')

        if not all([name, phone, service, master, date, time]):
            missing = []
            if not name: missing.append('name')
            if not phone: missing.append('phone')
            if not service: missing.append('service')
            if not master: missing.append('master')
            if not date: missing.append('date')
            if not time: missing.append('time')
            
            return jsonify({'success': False, 'message': f'Отсутствуют поля: {", ".join(missing)}'}), 400

        # ПРОВЕРКА ЗАНЯТОСТИ — учитываем ВСЕ записи, кроме отмененных
        bookings = get_bookings_by_date_master(date, master)
        booked_times = [b['time'] for b in bookings if b.get('status') != 'canceled']
        
        if time in booked_times:
            return jsonify({
                'success': False, 
                'message': f'Время {time} уже занято у мастера {master}. Выберите другое время.'
            }), 409

        service_obj = next((s for s in SERVICES if s['name'] == service), None)
        price = service_obj['price_num'] if service_obj else 0

        data['master_id'] = master_id if master_id else ''
        data['price'] = price
        booking_id = add_booking(data)

        date_formatted = datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')
        text = (
            f"Новая запись с сайта!\n\n"
            f"ID: #{booking_id}\n"
            f"Имя: {name}\n"
            f"Телефон: {phone}\n"
            f"Услуга: {service}\n"
            f"Мастер: {master}\n"
            f"Дата: {date_formatted}\n"
            f"Время: {time}\n"
            f"Сумма: {price} ₽"
        )

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': text,
            'parse_mode': 'HTML'
        })

        user_id = session.get('user_id')
        if user_id:
            message = 'Запись создана. Её можно отслеживать в личном кабинете!'
        else:
            message = 'Запись создана. Зарегистрируйтесь, чтобы отслеживать её в личном кабинете!'

        return jsonify({
            'success': True, 
            'message': message,
            'id': booking_id
        })

    except Exception as e:
        logger.error(f"Ошибка бронирования: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/my_bookings', methods=['POST'])
def my_bookings():
    try:
        data = request.json
        phone = data.get('phone')
        
        if not phone:
            return jsonify({'error': 'Phone required'}), 400
        
        bookings = get_bookings_with_status_update()
        user_bookings = []
        
        for b in bookings:
            if not isinstance(b, dict):
                continue
            b_phone = b.get('client_phone', b.get('phone', ''))
            if b_phone.replace('+', '').replace(' ', '').replace('-', '') == phone.replace('+', '').replace(' ', '').replace('-', ''):
                user_bookings.append(b)
        
        return jsonify(user_bookings)
    except Exception as e:
        logger.error(f"Ошибка получения записей: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/promo/apply', methods=['POST'])
def apply_promo():
    try:
        data = request.json or {}
        code = data.get('code', '').strip().upper()
        total = float(data.get('total', 0))
        
        promos = load_promos()
        promo = next((p for p in promos if p.get('code') == code and p.get('active')), None)
        
        if not promo:
            return jsonify({'success': False, 'message': 'Недействительный промокод'}), 400
            
        discount = 0
        if promo.get('discount_type') == 'percent':
            discount = round(total * (promo.get('discount_value', 0) / 100.0), 2)
        elif promo.get('discount_type') == 'fixed':
            discount = float(promo.get('discount_value', 0))
            
        discount = min(discount, total)
        final_total = max(0, total - discount)
        
        return jsonify({
            'success': True,
            'code': code,
            'discount': discount,
            'final_total': final_total,
            'message': f'Промокод {code} применен!'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': 'Ошибка применения промокода'}), 500

@app.route('/api/reviews/add', methods=['POST'])
def add_review():
    try:
        data = request.json or {}
        master = data.get('master')
        rating = int(data.get('rating', 5))
        comment = data.get('comment', '').strip()
        client_name = data.get('client_name', 'Клиент')
        booking_id = data.get('booking_id')
        
        if not master or not comment:
            return jsonify({'success': False, 'message': 'Укажите мастера и текст отзыва'}), 400
            
        reviews = load_reviews()
        new_review = {
            'id': str(uuid.uuid4()),
            'booking_id': booking_id,
            'master': master,
            'client_name': client_name,
            'rating': rating,
            'comment': comment,
            'status': 'approved',
            'date': datetime.now().strftime('%Y-%m-%d %H:%M')
        }
        reviews.append(new_review)
        save_reviews(reviews)
        return jsonify({'success': True, 'message': 'Спасибо за ваш отзыв!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/reviews/list', methods=['GET'])
def list_reviews():
    reviews = load_reviews()
    approved = [r for r in reviews if r.get('status') == 'approved']
    
    master_ratings = {}
    for r in approved:
        m = r.get('master')
        if m:
            if m not in master_ratings:
                master_ratings[m] = {'sum': 0, 'count': 0}
            master_ratings[m]['sum'] += r.get('rating', 5)
            master_ratings[m]['count'] += 1
            
    averages = {}
    for m, d in master_ratings.items():
        averages[m] = round(d['sum'] / d['count'], 1) if d['count'] > 0 else 5.0
        
    return jsonify({
        'reviews': approved,
        'master_ratings': averages
    })

@app.route('/api/admin/services', methods=['GET', 'POST', 'DELETE'])
def admin_services():
    services = load_services_data()
    if request.method == 'GET':
        return jsonify(services)
    elif request.method == 'POST':
        data = request.json or {}
        srv_id = data.get('id') or str(uuid.uuid4())
        data['id'] = srv_id
        data['price_num'] = int(data.get('price_num', 0))
        existing = next((s for s in services if s['id'] == srv_id), None)
        if existing:
            existing.update(data)
        else:
            services.append(data)
        save_services_data(services)
        return jsonify({'success': True, 'services': services})
    elif request.method == 'DELETE':
        srv_id = request.args.get('id')
        services = [s for s in services if s['id'] != srv_id]
        save_services_data(services)
        return jsonify({'success': True, 'services': services})

@app.route('/api/admin/masters', methods=['GET', 'POST', 'DELETE'])
def admin_masters():
    masters = load_masters_data()
    if request.method == 'GET':
        return jsonify(masters)
    elif request.method == 'POST':
        data = request.json or {}
        m_id = data.get('id') or str(uuid.uuid4())
        data['id'] = m_id
        existing = next((m for m in masters if m['id'] == m_id), None)
        if existing:
            existing.update(data)
        else:
            masters.append(data)
        save_masters_data(masters)
        return jsonify({'success': True, 'masters': masters})
    elif request.method == 'DELETE':
        m_id = request.args.get('id')
        masters = [m for m in masters if m['id'] != m_id]
        save_masters_data(masters)
        return jsonify({'success': True, 'masters': masters})

@app.route('/api/admin/promos', methods=['GET', 'POST', 'DELETE'])
def admin_promos():
    promos = load_promos()
    if request.method == 'GET':
        return jsonify(promos)
    elif request.method == 'POST':
        data = request.json or {}
        code = data.get('code', '').strip().upper()
        if not code:
            return jsonify({'success': False, 'message': 'Укажите промокод'}), 400
        existing = next((p for p in promos if p['code'] == code), None)
        if existing:
            existing.update(data)
        else:
            promos.append(data)
        save_promos(promos)
        return jsonify({'success': True, 'promos': promos})
    elif request.method == 'DELETE':
        code = request.args.get('code')
        promos = [p for p in promos if p['code'] != code]
        save_promos(promos)
        return jsonify({'success': True, 'promos': promos})

@app.route('/api/admin/reviews/status', methods=['POST'])
def admin_review_status():
    try:
        data = request.json or {}
        review_id = data.get('id')
        status = data.get('status', 'approved')
        reviews = load_reviews()
        for r in reviews:
            if r.get('id') == review_id:
                r['status'] = status
                break
        save_reviews(reviews)
        return jsonify({'success': True, 'reviews': reviews})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/quick_book', methods=['POST'])
def admin_quick_book():
    try:
        data = request.json or {}
        booking_id = add_booking(data)
        return jsonify({'success': True, 'id': booking_id, 'message': 'Запись успешно добавлена!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================
# АВТОРИЗАЦИЯ И РЕГИСТРАЦИЯ
# ============================================

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        password_confirm = data.get('password_confirm', '')

        if not all([name, phone, email, password, password_confirm]):
            return jsonify({'success': False, 'message': 'Заполните все поля'}), 400

        if len(password) < 6:
            return jsonify({'success': False, 'message': 'Пароль должен быть не менее 6 символов'}), 400

        if password != password_confirm:
            return jsonify({'success': False, 'message': 'Пароли не совпадают'}), 400

        users = load_users()
        for user_id, user_data in users['users'].items():
            if user_data.get('phone') == phone:
                return jsonify({'success': False, 'message': 'Пользователь с таким номером уже существует'}), 400
            if user_data.get('email') == email:
                return jsonify({'success': False, 'message': 'Пользователь с таким email уже существует'}), 400

        user_id = str(uuid.uuid4())
        users['users'][user_id] = {
            'id': user_id,
            'name': name,
            'phone': phone,
            'email': email,
            'password': hash_password(password),
            'role': 'user'
        }
        save_users(users)

        return jsonify({
            'success': True,
            'message': 'Регистрация успешна! Теперь войдите в систему.',
            'user': {
                'id': user_id,
                'name': name,
                'phone': phone,
                'email': email,
                'role': 'user'
            }
        })
    except Exception as e:
        logger.error(f"Ошибка регистрации: {e}")
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        login_input = data.get('login', '').strip()
        password = data.get('password', '')

        if not login_input or not password:
            return jsonify({'success': False, 'message': 'Заполните все поля'}), 400

        users = load_users()
        user_data = None

        login_normalized = login_input.lower()
        
        for user_id, user in users['users'].items():
            user_phone = user.get('phone', '').lower()
            user_email = user.get('email', '').lower()
            user_name = user.get('name', '').lower()
            
            if (user_phone == login_normalized or 
                user_email == login_normalized or 
                user_name == login_normalized):
                user_data = user
                break

        if not user_data:
            return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404

        if user_data.get('password') != hash_password(password):
            return jsonify({'success': False, 'message': 'Неверный пароль'}), 401

        session['user_id'] = user_data['id']
        session['user_name'] = user_data['name']
        session['user_role'] = user_data.get('role', 'user')
        session['user_phone'] = user_data.get('phone', '')
        session['user_email'] = user_data.get('email', '')

        return jsonify({
            'success': True,
            'message': 'Вход выполнен успешно',
            'user': {
                'id': user_data['id'],
                'name': user_data['name'],
                'phone': user_data['phone'],
                'email': user_data['email'],
                'role': user_data.get('role', 'user')
            }
        })
    except Exception as e:
        logger.error(f"Ошибка входа: {e}")
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500

@app.route('/api/forgot_password', methods=['POST'])
def forgot_password():
    try:
        data = request.json
        email = data.get('email', '').strip().lower()

        if not email:
            return jsonify({'success': False, 'message': 'Введите email'}), 400

        users = load_users()
        user_data = None
        user_id = None

        for uid, user in users['users'].items():
            if user.get('email') == email:
                user_data = user
                user_id = uid
                break

        if not user_data:
            return jsonify({'success': False, 'message': 'Пользователь с таким email не найден'}), 404

        code = generate_verification_code()
        
        if send_email(email, code):
            session['reset_code'] = code
            session['reset_email'] = email
            session['reset_user_id'] = user_id
            
            return jsonify({
                'success': True,
                'message': 'Код подтверждения отправлен на вашу почту'
            })
        else:
            return jsonify({'success': False, 'message': 'Ошибка отправки письма. Попробуйте позже.'}), 500
    except Exception as e:
        logger.error(f"Ошибка восстановления пароля: {e}")
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500

@app.route('/api/reset_password', methods=['POST'])
def reset_password():
    try:
        data = request.json
        code = data.get('code', '').strip()
        new_password = data.get('new_password', '')
        new_password_confirm = data.get('new_password_confirm', '')

        if not code or not new_password or not new_password_confirm:
            return jsonify({'success': False, 'message': 'Заполните все поля'}), 400

        if len(new_password) < 6:
            return jsonify({'success': False, 'message': 'Пароль должен быть не менее 6 символов'}), 400

        if new_password != new_password_confirm:
            return jsonify({'success': False, 'message': 'Пароли не совпадают'}), 400

        saved_code = session.get('reset_code')
        saved_email = session.get('reset_email')
        saved_user_id = session.get('reset_user_id')

        if not saved_code or not saved_email or not saved_user_id:
            return jsonify({'success': False, 'message': 'Сессия истекла. Запросите код заново.'}), 400

        if code != saved_code:
            return jsonify({'success': False, 'message': 'Неверный код подтверждения'}), 400

        users = load_users()
        if saved_user_id not in users['users']:
            return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404

        users['users'][saved_user_id]['password'] = hash_password(new_password)
        save_users(users)

        session.pop('reset_code', None)
        session.pop('reset_email', None)
        session.pop('reset_user_id', None)

        return jsonify({
            'success': True,
            'message': 'Пароль успешно изменен! Теперь войдите с новым паролем.'
        })
    except Exception as e:
        logger.error(f"Ошибка смены пароля: {e}")
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500

@app.route('/api/check_auth', methods=['GET'])
def check_auth():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'authenticated': False})

        users = load_users()
        if user_id not in users['users']:
            session.clear()
            return jsonify({'authenticated': False})

        user = users['users'][user_id]
        return jsonify({
            'authenticated': True,
            'user': {
                'id': user['id'],
                'name': user['name'],
                'phone': user['phone'],
                'email': user['email'],
                'role': user.get('role', 'user')
            }
        })
    except Exception as e:
        logger.error(f"Ошибка проверки авторизации: {e}")
        return jsonify({'authenticated': False}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Выход выполнен'})

@app.route('/api/user_info', methods=['GET'])
def user_info():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Не авторизован'}), 401

        users = load_users()
        if user_id not in users['users']:
            return jsonify({'error': 'Пользователь не найден'}), 404

        user = users['users'][user_id]
        return jsonify({
            'id': user['id'],
            'name': user['name'],
            'phone': user['phone'],
            'email': user['email'],
            'role': user.get('role', 'user')
        })
    except Exception as e:
        logger.error(f"Ошибка получения информации: {e}")
        return jsonify({'error': 'Ошибка сервера'}), 500

# ============================================
# АДМИН API
# ============================================

@app.route('/api/admin/stats')
def admin_stats():
    return jsonify(get_stats())

@app.route('/api/admin/bookings')
def admin_bookings():
    update_booking_statuses()
    date = request.args.get('date')
    master = request.args.get('master')
    if date and master:
        bookings = get_bookings_by_date_master(date, master)
    elif date:
        bookings = get_bookings_by_date(date)
    else:
        bookings = get_all_bookings()
    return jsonify(bookings)

@app.route('/api/admin/masters_list')
def admin_masters_list():
    return jsonify(get_masters_list())

@app.route('/api/admin/delete', methods=['POST'])
def admin_delete():
    data = request.json
    booking_id = data.get('id')
    if delete_booking(booking_id):
        return jsonify({'success': True, 'message': f'Запись #{booking_id} отменена'})
    return jsonify({'success': False, 'message': 'Запись не найдена'}), 404

@app.route('/api/admin/delete_all', methods=['POST'])
def admin_delete_all():
    if delete_all_bookings():
        return jsonify({'success': True, 'message': 'Все записи удалены'})
    return jsonify({'success': False, 'message': 'Нет записей для удаления'}), 404

@app.route('/api/admin/master_stats')
def admin_master_stats():
    return jsonify(get_master_stats())

@app.route('/api/admin/master_calendar')
def admin_master_calendar():
    master = request.args.get('master')
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    if not master:
        return jsonify({'error': 'Master required'}), 400
    
    days = get_master_calendar(master, year, month)
    total = get_master_month_stats(master, year, month)
    return jsonify({
        'days': list(days),
        'total': total,
        'year': year,
        'month': month
    })

@app.route('/api/admin/month_bookings')
def admin_month_bookings():
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    
    result = get_month_bookings(year, month)
    return jsonify(result)

@app.route('/api/admin/master_month_bookings')
def admin_master_month_bookings():
    master = request.args.get('master')
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    
    if not master:
        return jsonify({'error': 'Master required'}), 400
    
    result = get_master_month_bookings(master, year, month)
    return jsonify(result)

@app.route('/api/admin/revenue_stats')
def admin_revenue_stats():
    return jsonify(get_revenue_stats())

@app.route('/api/admin/client_stats')
def admin_client_stats():
    return jsonify(get_client_stats())

@app.route('/api/check_availability', methods=['POST'])
def check_availability():
    try:
        data = request.json
        date = data.get('date')
        master = data.get('master')
        
        if not date or not master:
            return jsonify({'error': 'Date and master required'}), 400
        
        bookings = get_bookings_by_date_master(date, master)
        return jsonify({'booked_times': [b['time'] for b in bookings if b.get('status') != 'canceled']})
    except Exception as e:
        logger.error(f"Ошибка проверки доступности: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================
# TELEGRAM БОТ — АДМИН-ПАНЕЛЬ
# ============================================

bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

user_state = {}

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Сегодня"), KeyboardButton(text="Завтра")],
            [KeyboardButton(text="Календарь"), KeyboardButton(text="Календарь мастера")],
            [KeyboardButton(text="Статистика"), KeyboardButton(text="Статистика по мастерам")],
            [KeyboardButton(text="Выручка"), KeyboardButton(text="Все записи")],
            [KeyboardButton(text="Удалить запись"), KeyboardButton(text="Удалить все записи")],
            [KeyboardButton(text="Ссылка на сайт")]
        ],
        resize_keyboard=True
    )

def get_calendar_keyboard(year, month, mode='general', master=None):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    month_names = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                   "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    
    if master:
        title = f"Мастер {master}: {month_names[month-1]} {year}"
    else:
        title = f"{month_names[month-1]} {year}"
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text=title, callback_data="ignore")
    ])
    
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    row = []
    for day in days:
        row.append(InlineKeyboardButton(text=day, callback_data="ignore"))
    keyboard.inline_keyboard.append(row)
    
    cal = calendar.monthcalendar(year, month)
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                date_str = f"{year:04d}-{month:02d}-{day:02d}"
                if master:
                    bookings = get_bookings_for_date(date_str)
                    has_booking = any(b.get('master') == master for b in bookings)
                else:
                    bookings = get_bookings_for_date(date_str)
                    has_booking = len(bookings) > 0
                
                if has_booking:
                    button_text = f"•{day}"
                else:
                    button_text = str(day)
                row.append(InlineKeyboardButton(
                    text=button_text, 
                    callback_data=f"cal_date_{date_str}_{master if master else 'general'}"
                ))
        keyboard.inline_keyboard.append(row)
    
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1
    
    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1
    
    if master:
        prev_callback = f"cal_nav_master_{master}_{prev_year}_{prev_month}"
        next_callback = f"cal_nav_master_{master}_{next_year}_{next_month}"
        today_callback = f"cal_nav_master_{master}_{datetime.now().year}_{datetime.now().month}"
        back_callback = "back_to_master_select"
    else:
        prev_callback = f"cal_nav_general_{prev_year}_{prev_month}"
        next_callback = f"cal_nav_general_{next_year}_{next_month}"
        today_callback = f"cal_nav_general_{datetime.now().year}_{datetime.now().month}"
        back_callback = "back_to_main_menu"
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="◀", callback_data=prev_callback),
        InlineKeyboardButton(text="Сегодня", callback_data=today_callback),
        InlineKeyboardButton(text="▶", callback_data=next_callback)
    ])
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="Назад", callback_data=back_callback)
    ])
    
    return keyboard

def get_master_selection_keyboard():
    masters = get_masters_list()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    stats = get_master_stats()
    for master in masters:
        count = stats.get(master, 0)
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{master} ({count} зап.)", 
                callback_data=f"select_master_{master}"
            )
        ])
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="Назад", callback_data="back_to_main_menu")
    ])
    return keyboard

def get_client_keyboard():
    buttons = [
        [KeyboardButton(text="Записаться онлайн", web_app=WebAppInfo(url=SITE_URL))],
        [KeyboardButton(text="О нас"), KeyboardButton(text="Ссылка на сайт")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# ===== ОБРАБОТЧИКИ КОМАНД =====

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_state[message.from_user.id] = {'page': 'main'}
    if is_admin_user(message.from_user.id):
        await message.answer(
            f"Админ-панель {SALON_NAME}\n\n"
            "Выберите действие:\n\n"
            "Сегодня/Завтра — записи на ближайшие дни\n"
            "Календарь — общий календарь записей\n"
            "Календарь мастера — записи конкретного мастера\n"
            "Статистика — статистика за 30 дней\n"
            "Статистика по мастерам — нагрузка на мастеров\n"
            "Выручка — финансовая аналитика\n"
            "Все записи — полный список\n"
            "Удалить запись — удаление по ID\n"
            "Удалить все записи — полная очистка\n"
            "Ссылка на сайт — ссылка для клиентов",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer(
            f"Добро пожаловать в студию маникюра {SALON_NAME}!\n\n"
            "Нажмите «Записаться онлайн», чтобы выбрать услугу, мастера и время прямо в Telegram!",
            reply_markup=get_client_keyboard()
        )

@dp.message(F.text.in_(["О нас", "ℹ️ О нас"]))
async def show_about_us(message: types.Message):
    await message.answer(
        f"Студия маникюра {SALON_NAME}\n\n"
        "Мы предлагаем премиальный уход за ногтями:\n"
        "• Классический и аппаратный маникюр\n"
        "• Гель-лак и дизайн любой сложности\n"
        "• Педикюр и SPA-уход\n\n"
        "Адрес: ул. Примерная, 10\n"
        "Режим работы: Ежедневно с 10:00 до 21:00\n"
        "Телефон: +7 (900) 000-00-00\n\n"
        f"Записаться онлайн: {SITE_URL}",
        reply_markup=get_client_keyboard()
    )

@dp.message(F.text.in_(["Записаться онлайн", "Записаться", "💅 Записаться онлайн"]))
async def show_booking_link(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Записаться (WebApp)", web_app=WebAppInfo(url=SITE_URL))],
        [InlineKeyboardButton(text="Открыть в браузере", url=SITE_URL)]
    ])
    await message.answer(
        "Нажмите кнопку ниже для онлайн-записи:",
        reply_markup=keyboard
    )

@dp.message(F.text.in_(["Админ-панель", "🔒 Админ-панель"]))
async def show_admin_panel_cmd(message: types.Message):
    if not is_admin_user(message.from_user.id):
        await message.answer("У вас нет доступа к админ-панели.", reply_markup=get_client_keyboard())
        return
    await message.answer("Панель администратора:", reply_markup=get_main_keyboard())

@dp.message(F.text.in_(["Ссылка на сайт", "🌐 Ссылка на сайт"]))
async def show_site_link(message: types.Message):
    await message.answer(
        f"Сайт для записи клиентов:\n\n"
        f"{SITE_URL}\n\n"
        f"Все записи с сайта автоматически синхронизируются.",
        reply_markup=get_main_keyboard() if is_admin_user(message.from_user.id) else get_client_keyboard()
    )




@dp.message(lambda message: message.text == "Сегодня")
async def show_today(message: types.Message):
    if message.from_user.id != TELEGRAM_CHAT_ID:
        return
    
    user_state[message.from_user.id] = {'page': 'main'}
    
    today = datetime.now().strftime("%Y-%m-%d")
    bookings = get_bookings_by_date(today)
    date_formatted = datetime.now().strftime("%d.%m.%Y")
    
    if not bookings:
        await message.answer(f"Записей на {date_formatted} нет", reply_markup=get_main_keyboard())
        return
    
    text = f"Записи на {date_formatted}\n\n"
    for b in sorted(bookings, key=lambda x: x['time']):
        status_text = "Активна" if b.get('status') == 'active' else ("Завершена" if b.get('status') == 'completed' else "Отменена")
        text += (
            f"ID #{b.get('id', '?')} | {b['time']}\n"
            f"{b.get('client_name', b.get('name', '?'))} | {b.get('client_phone', b.get('phone', '?'))}\n"
            f"{b['service']} | {b['master']}\n"
            f"{b.get('price', 0)} ₽ | {status_text}\n\n"
        )
    
    await message.answer(text[:4000], reply_markup=get_main_keyboard())

@dp.message(lambda message: message.text == "Завтра")
async def show_tomorrow(message: types.Message):
    if message.from_user.id != TELEGRAM_CHAT_ID:
        return
    
    user_state[message.from_user.id] = {'page': 'main'}
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    bookings = get_bookings_by_date(tomorrow)
    date_formatted = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    
    if not bookings:
        await message.answer(f"Записей на {date_formatted} нет", reply_markup=get_main_keyboard())
        return
    
    text = f"Записи на {date_formatted}\n\n"
    for b in sorted(bookings, key=lambda x: x['time']):
        status_text = "Активна" if b.get('status') == 'active' else ("Завершена" if b.get('status') == 'completed' else "Отменена")
        text += (
            f"ID #{b.get('id', '?')} | {b['time']}\n"
            f"{b.get('client_name', b.get('name', '?'))} | {b.get('client_phone', b.get('phone', '?'))}\n"
            f"{b['service']} | {b['master']}\n"
            f"{b.get('price', 0)} ₽ | {status_text}\n\n"
        )
    
    await message.answer(text[:4000], reply_markup=get_main_keyboard())

@dp.message(lambda message: message.text == "Календарь")
async def show_calendar(message: types.Message):
    if message.from_user.id != TELEGRAM_CHAT_ID:
        return
    
    user_state[message.from_user.id] = {'page': 'general_calendar'}
    
    now = datetime.now()
    await message.answer(
        "Общий календарь записей\n\n"
        "• — есть запись в этот день\n"
        "Нажмите на день для просмотра записей",
        reply_markup=get_calendar_keyboard(now.year, now.month)
    )

@dp.message(lambda message: message.text == "Статистика")
async def show_stats(message: types.Message):
    if message.from_user.id != TELEGRAM_CHAT_ID:
        return
    
    user_state[message.from_user.id] = {'page': 'main'}
    
    stats = get_stats()
    if not stats:
        await message.answer("Статистика\n\nНет записей за последние 30 дней", reply_markup=get_main_keyboard())
        return
    
    text = "Статистика за 30 дней\n\n"
    total = 0
    for date, count in sorted(stats.items(), reverse=True):
        date_formatted = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m.%Y")
        text += f"{date_formatted}: {count} зап.\n"
        total += count
    text += f"\nВсего: {total} записей"
    
    await message.answer(text, reply_markup=get_main_keyboard())

@dp.message(lambda message: message.text == "Статистика по мастерам")
async def show_master_stats_handler(message: types.Message):
    if message.from_user.id != TELEGRAM_CHAT_ID:
        return
    
    user_state[message.from_user.id] = {'page': 'main'}
    
    stats = get_master_stats()
    text = "Статистика по мастерам\n\n"
    total_all = 0
    for master, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
        text += f"{master}: {count} зап.\n"
        total_all += count
    text += f"\nВсего: {total_all} записей"
    
    await message.answer(text, reply_markup=get_main_keyboard())

@dp.message(lambda message: message.text == "Выручка")
async def show_revenue(message: types.Message):
    if message.from_user.id != TELEGRAM_CHAT_ID:
        return
    
    user_state[message.from_user.id] = {'page': 'main'}
    
    stats = get_revenue_stats()
    text = "Финансовая аналитика\n\n"
    text += f"Сегодня: {stats['today']['count']} зап. на {stats['today']['revenue']} ₽\n"
    text += f"За неделю: {stats['week']['count']} зап. на {stats['week']['revenue']} ₽\n"
    text += f"За месяц: {stats['month']['count']} зап. на {stats['month']['revenue']} ₽\n"
    text += f"Всего: {stats['total']['count']} зап. на {stats['total']['revenue']} ₽\n\n"
    
    text += "По услугам:\n"
    for service, data in sorted(stats['total']['by_service'].items(), key=lambda x: x[1]['revenue'], reverse=True):
        text += f"{service}: {data['count']} зап. на {data['revenue']} ₽\n"
    
    text += "\nПо мастерам:\n"
    for master, data in sorted(stats['total']['by_master'].items(), key=lambda x: x[1]['revenue'], reverse=True):
        text += f"{master}: {data['count']} зап. на {data['revenue']} ₽\n"
    
    await message.answer(text[:4000], reply_markup=get_main_keyboard())

@dp.message(lambda message: message.text == "Календарь мастера")
async def select_master_calendar(message: types.Message):
    if message.from_user.id != TELEGRAM_CHAT_ID:
        return
    
    user_state[message.from_user.id] = {'page': 'master_select'}
    
    await message.answer(
        "Выберите мастера\n\n"
        "Для просмотра его календаря записей:",
        reply_markup=get_master_selection_keyboard()
    )

@dp.message(lambda message: message.text == "Все записи")
async def show_all_bookings(message: types.Message):
    if message.from_user.id != TELEGRAM_CHAT_ID:
        return
    
    user_state[message.from_user.id] = {'page': 'main'}
    
    bookings = get_all_bookings()
    if not bookings:
        await message.answer("Нет записей", reply_markup=get_main_keyboard())
        return
    
    text = "Все записи\n\n"
    for b in sorted(bookings, key=lambda x: (x['date'], x['time']), reverse=True):
        status_text = "Активна" if b.get('status') == 'active' else ("Завершена" if b.get('status') == 'completed' else "Отменена")
        text += (
            f"ID #{b.get('id', '?')} | {b['date']} | {b['time']}\n"
            f"{b.get('client_name', b.get('name', '?'))} | {b.get('client_phone', b.get('phone', '?'))}\n"
            f"{b['service']} | {b['master']} | {b.get('price', 0)} ₽ | {status_text}\n\n"
        )
    
    if len(text) > 4000:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            await message.answer(part)
    else:
        await message.answer(text, reply_markup=get_main_keyboard())

@dp.message(lambda message: message.text == "Удалить запись")
async def delete_booking_start(message: types.Message):
    if message.from_user.id != TELEGRAM_CHAT_ID:
        return
    
    user_state[message.from_user.id] = {'page': 'delete'}
    
    await message.answer(
        "Удаление записи\n\n"
        "Введите ID записи для удаления.\n"
        "Например: 5\n\n"
        "Для отмены нажмите любую кнопку меню.",
        reply_markup=get_main_keyboard()
    )

@dp.message(lambda message: message.text and message.text.isdigit())
async def delete_booking_by_id(message: types.Message):
    if message.from_user.id != TELEGRAM_CHAT_ID:
        return
    
    state = user_state.get(message.from_user.id, {})
    if state.get('page') != 'delete':
        return
    
    booking_id = int(message.text)
    if delete_booking(booking_id):
        await message.answer(f"Запись #{booking_id} отменена!", reply_markup=get_main_keyboard())
    else:
        await message.answer(f"Запись #{booking_id} не найдена", reply_markup=get_main_keyboard())
    
    user_state[message.from_user.id] = {'page': 'main'}

@dp.message(lambda message: message.text == "Удалить все записи")
async def delete_all_bookings_start(message: types.Message):
    if message.from_user.id != TELEGRAM_CHAT_ID:
        return
    
    bookings = get_all_bookings()
    if not bookings:
        await message.answer("Нет записей для удаления", reply_markup=get_main_keyboard())
        return
    
    user_state[message.from_user.id] = {'page': 'delete_all_confirm'}
    
    await message.answer(
        f"ВНИМАНИЕ!\n\n"
        f"Вы уверены, что хотите удалить ВСЕ ЗАПИСИ ({len(bookings)} шт.)?\n\n"
        f"Это действие НЕЛЬЗЯ будет отменить!\n\n"
        f"Напишите Да или Нет в чат.",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text.in_(["Да", "да", "Нет", "нет"]))
async def handle_delete_all_confirmation(message: types.Message):
    if not is_admin_user(message.from_user.id):
        await message.answer("Для вызова меню нажмите 'Записаться онлайн'.", reply_markup=get_client_keyboard())
        return
    
    state = user_state.get(message.from_user.id, {})
    if state.get('page') != 'delete_all_confirm':
        await message.answer("Панель администратора:", reply_markup=get_main_keyboard())
        return
    
    text = message.text.lower().strip()
    
    if text == "да":
        bookings = get_all_bookings()
        count = len(bookings)
        if delete_all_bookings():
            await message.answer(
                f"Все записи ({count} шт.) успешно удалены!",
                reply_markup=get_main_keyboard()
            )
        else:
            await message.answer(
                "Ошибка при удалении записей",
                reply_markup=get_main_keyboard()
            )
    else:
        await message.answer(
            "Удаление всех записей отменено",
            reply_markup=get_main_keyboard()
        )
    
    user_state[message.from_user.id] = {'page': 'main'}

@dp.message()
async def default_fallback_handler(message: types.Message):
    logger.info(f"Fallback handler received from {message.from_user.id}: {message.text}")
    if is_admin_user(message.from_user.id):
        await message.answer(f"Панель администратора {SALON_NAME}:", reply_markup=get_main_keyboard())
    else:
        await message.answer(
            f"Добро пожаловать в студию маникюра {SALON_NAME}!\n\n"
            "Нажмите «Записаться онлайн», чтобы выбрать услугу, мастера и время прямо в Telegram!",
            reply_markup=get_client_keyboard()
        )


# ===== CALLBACK ОБРАБОТЧИКИ =====

@dp.callback_query(lambda c: c.data == "back_to_main_menu")
async def back_to_main_menu(callback: types.CallbackQuery):
    if callback.from_user.id != TELEGRAM_CHAT_ID:
        await callback.answer("Нет доступа")
        return
    
    user_state[callback.from_user.id] = {'page': 'main'}
    
    await callback.message.delete()
    await callback.message.answer(
        f"Админ-панель {SALON_NAME}\n\nВыберите действие:",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_to_master_select")
async def back_to_master_select(callback: types.CallbackQuery):
    if callback.from_user.id != TELEGRAM_CHAT_ID:
        await callback.answer("Нет доступа")
        return
    
    user_state[callback.from_user.id] = {'page': 'master_select'}
    
    await callback.message.edit_text(
        "Выберите мастера\n\n"
        "Для просмотра его календаря записей:",
        reply_markup=get_master_selection_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("cal_date_"))
async def show_date_bookings(callback: types.CallbackQuery):
    if callback.from_user.id != TELEGRAM_CHAT_ID:
        await callback.answer("Нет доступа")
        return
    
    parts = callback.data.split("_")
    date_str = parts[2]
    source = parts[3] if len(parts) > 3 else 'general'
    
    bookings = get_bookings_by_date(date_str)
    date_formatted = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    
    if not bookings:
        await callback.answer(f"Нет записей на {date_formatted}")
        return
    
    if source != 'general':
        bookings = [b for b in bookings if b.get('master') == source]
        if not bookings:
            await callback.answer(f"Нет записей мастера {source} на {date_formatted}")
            return
    
    text = f"Записи на {date_formatted}\n\n"
    for b in sorted(bookings, key=lambda x: x['time']):
        status_text = "Активна" if b.get('status') == 'active' else ("Завершена" if b.get('status') == 'completed' else "Отменена")
        text += (
            f"ID #{b.get('id', '?')} | {b['time']}\n"
            f"{b.get('client_name', b.get('name', '?'))} | {b.get('client_phone', b.get('phone', '?'))}\n"
            f"{b['service']} | {b['master']}\n"
            f"{b.get('price', 0)} ₽ | {status_text}\n\n"
        )
    
    await callback.message.answer(text[:4000], reply_markup=get_main_keyboard())
    await callback.answer(f"{date_formatted}")

@dp.callback_query(lambda c: c.data.startswith("cal_nav_general_"))
async def general_calendar_nav(callback: types.CallbackQuery):
    if callback.from_user.id != TELEGRAM_CHAT_ID:
        await callback.answer("Нет доступа")
        return
    
    parts = callback.data.split("_")
    year = int(parts[3])
    month = int(parts[4])
    
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1
    
    user_state[callback.from_user.id] = {'page': 'general_calendar'}
    
    await callback.message.edit_text(
        "Общий календарь записей\n\n"
        "• — есть запись в этот день\n"
        "Нажмите на день для просмотра записей",
        reply_markup=get_calendar_keyboard(year, month)
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("cal_nav_master_"))
async def master_calendar_nav(callback: types.CallbackQuery):
    if callback.from_user.id != TELEGRAM_CHAT_ID:
        await callback.answer("Нет доступа")
        return
    
    parts = callback.data.split("_")
    master = parts[3]
    year = int(parts[4])
    month = int(parts[5])
    
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1
    
    user_state[callback.from_user.id] = {'page': f'master_calendar_{master}'}
    
    await callback.message.edit_text(
        f"Календарь мастера {master}\n\n"
        "• — есть запись в этот день\n"
        "Нажмите на день для просмотра записей",
        reply_markup=get_calendar_keyboard(year, month, mode='master', master=master)
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("select_master_"))
async def select_master_calendar_callback(callback: types.CallbackQuery):
    if callback.from_user.id != TELEGRAM_CHAT_ID:
        await callback.answer("Нет доступа")
        return
    
    master = callback.data.replace("select_master_", "")
    now = datetime.now()
    
    user_state[callback.from_user.id] = {'page': f'master_calendar_{master}'}
    
    await callback.message.edit_text(
        f"Календарь мастера {master}\n\n"
        "• — есть запись в этот день\n"
        "Нажмите на день для просмотра записей",
        reply_markup=get_calendar_keyboard(now.year, now.month, mode='master', master=master)
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "ignore")
async def ignore_callback(callback: types.CallbackQuery):
    await callback.answer()

# ============================================
# ЗАПУСК
# ============================================

def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async def start_bot():
        await bot.set_my_commands([
            BotCommand(command="start", description="Открыть админ-панель")
        ])
        logger.info("Бот админ-панели запущен!")
        await dp.start_polling(bot, handle_signals=False)
    loop.run_until_complete(start_bot())

if __name__ == '__main__':
    repair_bookings_file()
    
    if not os.path.exists(BOOKINGS_FILE):
        save_bookings([])
        logger.info("Файл bookings.json создан")
    else:
        bookings = load_bookings()
        logger.info(f"Загружено {len(bookings)} записей")
    
    init_admin()
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("Бот запущен в фоновом потоке")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
