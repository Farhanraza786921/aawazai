from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
import uuid
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

class User(UserMixin, db.Model):
    """User model for authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationship to TTS requests
    tts_requests = db.relationship('TTSRequest', backref='user', lazy=True)
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if provided password matches hash"""
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        """Required by Flask-Login"""
        return str(self.id)
    
    def __repr__(self):
        return f'<User {self.username}>'

class TTSRequest(db.Model):
    """Model to track text-to-speech requests"""
    __tablename__ = 'tts_requests'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)  # Optional for guest users
    text = db.Column(db.Text, nullable=False)
    voice = db.Column(db.String(100), nullable=False)
    language = db.Column(db.String(10), nullable=False)
    tld = db.Column(db.String(20), nullable=False)
    filename = db.Column(db.String(100), nullable=False)
    character_count = db.Column(db.Integer, nullable=False)
    ip_address = db.Column(db.String(45))  # IPv6 compatible
    user_agent = db.Column(db.Text)
    request_source = db.Column(db.String(20), default='web')  # 'web' or 'api'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    file_size = db.Column(db.Integer)  # Size in bytes
    processing_time = db.Column(db.Float)  # Processing time in seconds
    
    def __repr__(self):
        return f'<TTSRequest {self.id}: {self.voice} - {self.character_count} chars>'

class VoiceUsageStats(db.Model):
    """Model to track voice usage statistics"""
    __tablename__ = 'voice_usage_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    voice_name = db.Column(db.String(100), nullable=False, unique=True)
    usage_count = db.Column(db.Integer, default=0)
    total_characters = db.Column(db.BigInteger, default=0)
    last_used = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<VoiceUsageStats {self.voice_name}: {self.usage_count} uses>'

class DailyStats(db.Model):
    """Model to track daily usage statistics"""
    __tablename__ = 'daily_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    total_requests = db.Column(db.Integer, default=0)
    total_characters = db.Column(db.BigInteger, default=0)
    api_requests = db.Column(db.Integer, default=0)
    web_requests = db.Column(db.Integer, default=0)
    unique_ips = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<DailyStats {self.date}: {self.total_requests} requests>'

class PopularTexts(db.Model):
    """Model to track popular/trending texts"""
    __tablename__ = 'popular_texts'
    
    id = db.Column(db.Integer, primary_key=True)
    text_hash = db.Column(db.String(64), nullable=False, unique=True)  # SHA256 hash
    text_preview = db.Column(db.String(200), nullable=False)  # First 200 chars
    usage_count = db.Column(db.Integer, default=1)
    last_used = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<PopularTexts {self.text_preview[:50]}...: {self.usage_count} uses>'