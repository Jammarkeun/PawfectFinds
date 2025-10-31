from flask import Flask, request
from flask_session import Session
from flask_wtf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_socketio import SocketIO
import os
from dotenv import load_dotenv

# Initialize extensions
db = SQLAlchemy()
sess = Session()
csrf = CSRFProtect()
migrate = Migrate()
socketio = SocketIO()

def create_app(config_name='default'):
    app = Flask(__name__)
    
    # Load environment variables from .env file in the root directory
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"Loaded .env file from: {env_path}")
    else:
        print(f"Warning: .env file not found at {env_path}")
    
    # Debug: Print all environment variables
    print("\n=== Environment Variables ===")
    for key in ['MAIL_SERVER', 'MAIL_PORT', 'MAIL_USE_TLS', 'MAIL_USERNAME', 'MAIL_PASSWORD', 'EMAIL_FROM']:
        print(f"{key}: {os.getenv(key, '[NOT SET]')}")
    print("==========================\n")
    
    # Basic configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['UPLOAD_FOLDER'] = 'static/uploads'
    
    # MySQL Database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'mysql+mysqlconnector://root:password@localhost/pawfect_findsdatabase')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_recycle': 280,
        'pool_pre_ping': True
    }
    
    # Email configuration - load directly from environment
    email_from = os.getenv('EMAIL_FROM')
    sender_name = 'Pawfect Finds'
    
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() in ['true', '1']
    app.config['MAIL_USERNAME'] = email_from
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    
    # Set the default sender with both name and email
    app.config['MAIL_DEFAULT_SENDER'] = (sender_name, email_from)
    app.config['MAIL_SENDER_NAME'] = sender_name
    
    # Debug email config
    print("\n=== Email Configuration ===")
    print(f"MAIL_SERVER: {app.config['MAIL_SERVER']}")
    print(f"MAIL_PORT: {app.config['MAIL_PORT']}")
    print(f"MAIL_USE_TLS: {app.config['MAIL_USE_TLS']}")
    print(f"MAIL_USERNAME: {app.config['MAIL_USERNAME']}")
    print(f"MAIL_DEFAULT_SENDER: {app.config['MAIL_DEFAULT_SENDER']}")
    print("MAIL_PASSWORD:", "[SET]" if app.config['MAIL_PASSWORD'] else "[NOT SET]")
    print("=========================\n")
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    sess.init_app(app)
    csrf.init_app(app)
    
    # Initialize WebSocket
    from app.services.rider_websocket import init_rider_websocket
    init_rider_websocket(app)
    socketio.init_app(app)
    
    # Import models to ensure they are registered with SQLAlchemy
    from app.models import models
    
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
    
    # Create upload directories
    upload_folders = [
        app.config['UPLOAD_FOLDER'],
        os.path.join(app.config['UPLOAD_FOLDER'], 'products'),
        os.path.join(app.config['UPLOAD_FOLDER'], 'profiles'),
        os.path.join(app.config['UPLOAD_FOLDER'], 'documents')
    ]
    
    for folder in upload_folders:
        os.makedirs(folder, exist_ok=True)
    
    # Register blueprints (only main for now)
    from app.routes.main import main_bp
    app.register_blueprint(main_bp)
    
    from app.models import user
    
    return app
