import os
import uuid
import logging
import hashlib
from datetime import datetime, date
from flask import Flask, render_template, request, send_file, jsonify, session, redirect, url_for, flash
from urllib.parse import urlparse
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from gtts import gTTS
import tempfile
import threading
import time
from functools import wraps
from models import db, User, TTSRequest, VoiceUsageStats, DailyStats, PopularTexts
from sqlalchemy import func

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

# Database configuration
database_url = os.environ.get("DATABASE_URL")
if database_url:
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Initialize database
    db.init_app(app)
    
    # Create tables
    with app.app_context():
        db.create_all()
else:
    logging.warning("No DATABASE_URL found, running without database features")
    database_url = None

# Voice presets with numbered system - accurate descriptions
VOICE_PRESETS = {
    "Voice 1": {"lang": "en", "tld": "com", "flag": "🇺🇸", "description": "English - US accent"},
    "Voice 2": {"lang": "en", "tld": "co.uk", "flag": "🇬🇧", "description": "English - UK accent"},
    "Voice 3": {"lang": "en", "tld": "co.in", "flag": "🇮🇳", "description": "English - Indian accent"},
    "Voice 4": {"lang": "hi", "tld": "co.in", "flag": "🇮🇳", "description": "Hindi - Indian"},
    "Voice 5": {"lang": "es", "tld": "com", "flag": "🇪🇸", "description": "Spanish - Standard"},
    "Voice 6": {"lang": "fr", "tld": "com", "flag": "🇫🇷", "description": "French - Standard"},
    "Voice 7": {"lang": "de", "tld": "com", "flag": "🇩🇪", "description": "German - Standard"},
    "Voice 8": {"lang": "ja", "tld": "com", "flag": "🇯🇵", "description": "Japanese - Standard"},
    "Voice 9": {"lang": "pt", "tld": "com.br", "flag": "🇧🇷", "description": "Portuguese - Brazilian"},
    "Voice 10": {"lang": "ru", "tld": "com", "flag": "🇷🇺", "description": "Russian - Standard"},
    "Voice 11": {"lang": "ar", "tld": "com", "flag": "🇸🇦", "description": "Arabic - Standard"},
    "Voice 12": {"lang": "en", "tld": "co.za", "flag": "🇿🇦", "description": "English - South African"}
}

# Ensure audio directory exists
AUDIO_DIR = os.path.join("static", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

# Authentication credentials for analytics
ANALYTICS_USERNAME = "heart"
ANALYTICS_PASSWORD = "heart"

def require_auth(f):
    """Decorator to require authentication for analytics routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('analytics_login'))
        return f(*args, **kwargs)
    return decorated_function

def cleanup_old_files():
    """Clean up audio files older than 30 minutes"""
    try:
        current_time = time.time()
        for filename in os.listdir(AUDIO_DIR):
            if filename.endswith('.mp3'):
                file_path = os.path.join(AUDIO_DIR, filename)
                if os.path.isfile(file_path):
                    file_age = current_time - os.path.getctime(file_path)
                    if file_age > 1800:  # 30 minutes
                        os.remove(file_path)
                        logging.info(f"Cleaned up old file: {filename}")
    except Exception as e:
        logging.error(f"Error during cleanup: {e}")

def log_tts_request(text, voice_name, filename, request_source='web', ip_address=None, user_agent=None, processing_time=None, user_id=None):
    """Log TTS request to database"""
    if not database_url:
        return  # Skip logging if no database
        
    try:
        voice_config = VOICE_PRESETS[voice_name]
        
        # Create TTS request record
        tts_request = TTSRequest(
            user_id=user_id,
            text=text,
            voice=voice_name,
            language=voice_config["lang"],
            tld=voice_config["tld"],
            filename=filename,
            character_count=len(text),
            ip_address=ip_address,
            user_agent=user_agent,
            request_source=request_source,
            processing_time=processing_time
        )
        
        # Get file size if exists
        filepath = os.path.join(AUDIO_DIR, filename)
        if os.path.exists(filepath):
            tts_request.file_size = os.path.getsize(filepath)
        
        db.session.add(tts_request)
        
        # Update voice usage stats
        voice_stat = VoiceUsageStats.query.filter_by(voice_name=voice_name).first()
        if voice_stat:
            voice_stat.usage_count += 1
            voice_stat.total_characters += len(text)
            voice_stat.last_used = datetime.utcnow()
        else:
            voice_stat = VoiceUsageStats(
                voice_name=voice_name,
                usage_count=1,
                total_characters=len(text),
                last_used=datetime.utcnow()
            )
            db.session.add(voice_stat)
        
        # Update daily stats
        today = date.today()
        daily_stat = DailyStats.query.filter_by(date=today).first()
        if daily_stat:
            daily_stat.total_requests += 1
            daily_stat.total_characters += len(text)
            if request_source == 'api':
                daily_stat.api_requests += 1
            else:
                daily_stat.web_requests += 1
        else:
            daily_stat = DailyStats(
                date=today,
                total_requests=1,
                total_characters=len(text),
                api_requests=1 if request_source == 'api' else 0,
                web_requests=1 if request_source == 'web' else 0,
                unique_ips=1 if ip_address else 0
            )
            db.session.add(daily_stat)
        
        # Track popular texts (hash for privacy)
        text_hash = hashlib.sha256(text.lower().strip().encode()).hexdigest()
        popular_text = PopularTexts.query.filter_by(text_hash=text_hash).first()
        if popular_text:
            popular_text.usage_count += 1
            popular_text.last_used = datetime.utcnow()
        else:
            popular_text = PopularTexts(
                text_hash=text_hash,
                text_preview=text[:200],  # Store first 200 chars for reference
                usage_count=1
            )
            db.session.add(popular_text)
        
        db.session.commit()
        logging.info(f"Logged TTS request: {voice_name}, {len(text)} chars")
        
    except Exception as e:
        logging.error(f"Error logging TTS request: {e}")
        db.session.rollback()

def generate_speech(text, voice_name, request_source='web', ip_address=None, user_agent=None, user_id=None):
    """Generate speech from text using selected voice"""
    start_time = time.time()
    try:
        if voice_name not in VOICE_PRESETS:
            raise ValueError(f"Invalid voice: {voice_name}")
        
        voice_config = VOICE_PRESETS[voice_name]
        
        # Create gTTS object
        tts = gTTS(
            text=text,
            lang=voice_config["lang"],
            tld=voice_config["tld"]
        )
        
        # Generate unique filename
        filename = f"{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)
        
        # Save audio file
        tts.save(filepath)
        processing_time = time.time() - start_time
        
        # Log to database
        log_tts_request(text, voice_name, filename, request_source, ip_address, user_agent, processing_time, user_id)
        
        logging.info(f"Generated audio file: {filename} in {processing_time:.2f}s")
        
        return filename
    except Exception as e:
        logging.error(f"Error generating speech: {e}")
        raise

@app.route("/", methods=["GET", "POST"])
def index():
    """Main page with TTS form"""
    audio_file = None
    error_message = None
    
    if request.method == "POST":
        try:
            text = request.form.get("text", "").strip()
            voice = request.form.get("voice", "")
            
            if not text:
                error_message = "Please enter some text to convert"
            elif not voice or voice not in VOICE_PRESETS:
                error_message = "Please select a valid voice"
            elif len(text) > 5000:
                error_message = "Text is too long. Maximum 5000 characters allowed."
            else:
                # Generate speech
                audio_file = generate_speech(
                    text, voice, 
                    request_source='web',
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    user_id=current_user.id if current_user.is_authenticated else None
                )
                
                # Schedule cleanup in background
                threading.Timer(1800, cleanup_old_files).start()
                
        except Exception as e:
            error_message = f"Error generating speech: {str(e)}"
            logging.error(f"Form submission error: {e}")
    
    return render_template("index.html", 
                         voices=VOICE_PRESETS,
                         audio_file=audio_file,
                         error_message=error_message)

@app.route("/api", methods=["GET"])
def api_tts():
    """Public API endpoint for text-to-speech conversion"""
    try:
        text = request.args.get("text", "").strip()
        voice = request.args.get("voice", "")
        
        # Validate parameters
        if not text:
            return jsonify({"error": "Missing 'text' parameter"}), 400
        
        if not voice:
            return jsonify({"error": "Missing 'voice' parameter"}), 400
            
        if voice not in VOICE_PRESETS:
            return jsonify({
                "error": f"Invalid voice. Available voices: {list(VOICE_PRESETS.keys())}"
            }), 400
            
        if len(text) > 5000:
            return jsonify({"error": "Text too long. Maximum 5000 characters allowed."}), 400
        
        # Generate speech
        filename = generate_speech(
            text, voice,
            request_source='api',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            user_id=current_user.id if current_user.is_authenticated else None
        )
        filepath = os.path.join(AUDIO_DIR, filename)
        
        # Schedule cleanup
        threading.Timer(1800, cleanup_old_files).start()
        
        # Return audio file
        return send_file(
            filepath,
            mimetype="audio/mpeg",
            as_attachment=True,
            download_name=f"tts_output_{filename}"
        )
        
    except Exception as e:
        logging.error(f"API error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/download/<filename>")
def download_audio(filename):
    """Download generated audio file"""
    try:
        filepath = os.path.join(AUDIO_DIR, filename)
        if os.path.exists(filepath) and filename.endswith('.mp3'):
            return send_file(
                filepath,
                mimetype="audio/mpeg",
                as_attachment=True,
                download_name=f"aawaaz_ai_{filename}"
            )
        else:
            return "File not found", 404
    except Exception as e:
        logging.error(f"Download error: {e}")
        return "Error downloading file", 500

@app.route("/play/<filename>")
def play_audio(filename):
    """Serve audio file for playback"""
    try:
        filepath = os.path.join(AUDIO_DIR, filename)
        if os.path.exists(filepath) and filename.endswith('.mp3'):
            return send_file(filepath, mimetype="audio/mpeg")
        else:
            return "File not found", 404
    except Exception as e:
        logging.error(f"Play error: {e}")
        return "Error playing file", 500

@app.route("/api-docs")
def api_docs():
    """API documentation page"""
    return render_template("api_docs.html", voices=VOICE_PRESETS)

@app.route("/api/voices", methods=["GET"])
def get_voices():
    """Get available voices as JSON"""
    return jsonify({
        "voices": VOICE_PRESETS,
        "total_voices": len(VOICE_PRESETS),
        "character_limit": 5000
    })

@app.route("/signup", methods=["GET", "POST"])
def signup():
    """User registration page"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        
        # Validation
        if not username or not email or not password:
            flash("All required fields must be filled", "error")
        elif len(username) < 3:
            flash("Username must be at least 3 characters", "error")
        elif len(password) < 6:
            flash("Password must be at least 6 characters", "error")
        elif password != confirm_password:
            flash("Passwords do not match", "error")
        elif User.query.filter_by(username=username).first():
            flash("Username already exists", "error")
        elif User.query.filter_by(email=email).first():
            flash("Email already registered", "error")
        else:
            try:
                # Create new user
                user = User(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name
                )
                user.set_password(password)
                
                db.session.add(user)
                db.session.commit()
                
                flash("Account created successfully! Please log in.", "success")
                return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback()
                flash("Error creating account. Please try again.", "error")
                logging.error(f"Signup error: {e}")
    
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """User login page"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember_me = request.form.get("remember_me") == "on"
        
        if not username or not password:
            flash("Please enter both username and password", "error")
        else:
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                login_user(user, remember=remember_me)
                user.last_login = datetime.utcnow()
                db.session.commit()
                
                flash(f"Welcome back, {user.first_name or user.username}!", "success")
                
                # Redirect to next page or home (with security validation)
                next_page = request.args.get('next')
                if next_page:
                    # Validate the next URL to prevent open redirect attacks
                    parsed_url = urlparse(next_page)
                    # Only allow relative URLs (no scheme or netloc)
                    if not parsed_url.netloc and not parsed_url.scheme:
                        return redirect(next_page)
                return redirect(url_for('index'))
            else:
                flash("Invalid username or password", "error")
    
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    """User logout"""
    logout_user()
    flash("You have been logged out successfully", "success")
    return redirect(url_for('index'))

@app.route("/profile")
@login_required
def profile():
    """User profile page with personal TTS history"""
    # Get user's TTS requests
    user_requests = TTSRequest.query.filter_by(user_id=current_user.id).order_by(TTSRequest.created_at.desc()).limit(20).all()
    
    # Get user stats
    total_requests = TTSRequest.query.filter_by(user_id=current_user.id).count()
    total_characters = db.session.query(func.sum(TTSRequest.character_count)).filter_by(user_id=current_user.id).scalar() or 0
    
    # Get user's favorite voices
    favorite_voices = db.session.query(
        TTSRequest.voice,
        func.count(TTSRequest.id).label('count')
    ).filter_by(user_id=current_user.id).group_by(TTSRequest.voice).order_by(func.count(TTSRequest.id).desc()).limit(5).all()
    
    return render_template("profile.html", 
                         user_requests=user_requests,
                         total_requests=total_requests,
                         total_characters=total_characters,
                         favorite_voices=favorite_voices)

@app.route("/analytics/login", methods=["GET", "POST"])
def analytics_login():
    """Login page for analytics dashboard"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if username == ANALYTICS_USERNAME and password == ANALYTICS_PASSWORD:
            session['authenticated'] = True
            session.permanent = True
            flash("Successfully logged in to analytics dashboard", "success")
            return redirect(url_for('stats_dashboard'))
        else:
            flash("Invalid username or password", "error")
    
    return render_template("analytics_login.html")

@app.route("/analytics/logout")
def analytics_logout():
    """Logout from analytics"""
    session.pop('authenticated', None)
    flash("Successfully logged out", "success")
    return redirect(url_for('index'))

@app.route("/stats")
@require_auth
def stats_dashboard():
    """Analytics dashboard (protected)"""
    if not database_url:
        return render_template("stats.html", database_available=False)
    
    try:
        # Get basic stats
        total_requests = TTSRequest.query.count()
        total_characters = db.session.query(func.sum(TTSRequest.character_count)).scalar() or 0
        
        # Get voice usage stats
        voice_stats = VoiceUsageStats.query.order_by(VoiceUsageStats.usage_count.desc()).limit(10).all()
        
        # Get recent daily stats
        recent_stats = DailyStats.query.order_by(DailyStats.date.desc()).limit(7).all()
        
        # Get popular texts (anonymized)
        popular_texts = PopularTexts.query.order_by(PopularTexts.usage_count.desc()).limit(5).all()
        
        return render_template("stats.html", 
                             database_available=True,
                             total_requests=total_requests,
                             total_characters=total_characters,
                             voice_stats=voice_stats,
                             recent_stats=recent_stats,
                             popular_texts=popular_texts)
    except Exception as e:
        logging.error(f"Error loading stats: {e}")
        return render_template("stats.html", database_available=False, error=str(e))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
