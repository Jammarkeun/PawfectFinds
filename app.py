from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)
from flask_wtf.csrf import CSRFProtect, CSRFError, generate_csrf
from flask_socketio import SocketIO
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Local application imports
from app.models.user import User
from app.services.database import Database
from config.config import Config
from app.controllers.auth_controller import auth_bp
from app.controllers.admin_controller import admin_bp
from app.controllers.seller_controller import seller_bp
from app.controllers.user_controller import user_bp
from app.controllers.public_controller import public_bp
from app.controllers.cart_controller import cart_bp
from app.controllers.order_controller import order_bp
from app.controllers.search_controller import search_bp
from app.controllers.review_controller import review_bp
from app.controllers.rider_controller import rider_bp

def create_app():
    """Application factory function"""
    import os
    from flask_socketio import join_room, leave_room, emit
    
    app = Flask(__name__, static_folder='static')
    # Performance: cache static files aggressively
    from datetime import timedelta
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = timedelta(days=30)
    
    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
        
    app.config.from_object(Config)

    # Initialize extensions
    db = Database()
    csrf = CSRFProtect(app)
    socketio = SocketIO(app, cors_allowed_origins="*")

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(seller_bp, url_prefix='/seller')
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(public_bp, url_prefix='/')
    app.register_blueprint(cart_bp, url_prefix='/cart')
    app.register_blueprint(order_bp, url_prefix='/order')
    app.register_blueprint(search_bp, url_prefix='/search')
    app.register_blueprint(review_bp, url_prefix='/review')
    app.register_blueprint(rider_bp, url_prefix='/rider')

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        app.logger.error(f"CSRF error: {e.description}")
        app.logger.error(f"Request method: {request.method}")
        app.logger.error(f"Request path: {request.path}")
        app.logger.error(f"Request form data: {dict(request.form)}")
        app.logger.error(f"Request cookies: {request.cookies}")
        app.logger.error(f"Session contents: {dict(session)}")
        flash('Your session expired or the form is invalid. Please try again.', 'error')
        return render_template('errors/403.html'), 403

    # Create tables when the application starts
    with app.app_context():
        db.create_tables()

    @app.after_request
    def add_cache_headers(response):
        """Hint browsers to cache static assets longer."""
        if request.path.startswith('/static/'):
            response.headers.setdefault('Cache-Control', 'public, max-age=2592000, immutable')
        return response

    @app.context_processor
    def inject_user():
        """Inject current user into all templates"""
        if 'user_id' in session:
            user = User.get_by_id(session['user_id'])
            return dict(current_user=user, csrf_token_value=generate_csrf())
        return dict(current_user=None, csrf_token_value=generate_csrf())
    
    @app.template_filter('image_url')
    def image_url_filter(image_url):
        """Template filter to handle image URLs properly"""
        if not image_url:
            return 'https://via.placeholder.com/300x200?text=No+Image'
        
        # If it's already a full URL (external), return as is
        if image_url.startswith('http://') or image_url.startswith('https://'):
            return image_url
        
        # If it starts with /static/, return as is (already correct)
        if image_url.startswith('/static/'):
            return image_url
        
        # If it's a relative path, add /static/ prefix
        if image_url.startswith('uploads/'):
            return f'/static/{image_url}'
        
        # Default case: treat as static file
        return url_for('static', filename=image_url)

    # Currency and discount helpers
    @app.template_filter('php')
    def php_currency(value):
        try:
            amount = float(value or 0)
            return f"₱{amount:,.2f}"
        except Exception:
            return "₱0.00"

    GLOBAL_DISCOUNT_PHP = 50.0

    @app.template_filter('apply_discount')
    def apply_discount(value):
        try:
            amount = float(value or 0)
            discounted = max(0.0, amount - GLOBAL_DISCOUNT_PHP)
            return discounted
        except Exception:
            return value

    @app.route('/')
    def index():
        """Main landing page"""
        return redirect(url_for('public.landing'))

    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template('errors/500.html'), 500

    return app

app = create_app()

if __name__ == '__main__':
    # Initialize Socket.IO with the app
    from app.services.rider_websocket import socketio
    socketio.init_app(app)
    # Run the app with Socket.IO support
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
