from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from app.utils.decorators import login_required
from app.models.delivery import Delivery
from app.models.order import Order
from app.models.user import User
from app.services.database import Database

rider_bp = Blueprint('rider', __name__)

def rider_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_role') != 'rider':
            flash('Access denied. Riders only.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@rider_bp.route('/dashboard')
@login_required
@rider_required
def dashboard():
    rider_id = session['user_id']
    status = request.args.get('status')
    deliveries = Delivery.list_for_rider(rider_id, status=status)

    # Get rider statistics
    db = Database()
    stats = db.execute_query("""
        SELECT
            COUNT(CASE WHEN d.status = 'assigned' THEN 1 END) as pending_deliveries,
            COUNT(CASE WHEN d.status = 'delivered' THEN 1 END) as completed_deliveries,
            COALESCE(SUM(CASE WHEN d.status = 'delivered' THEN o.total_amount * 0.1 END), 0) as monthly_earnings,
            COALESCE(AVG(r.rating), 0) as avg_rating
        FROM deliveries d
        LEFT JOIN orders o ON d.order_id = o.id
        LEFT JOIN order_items oi ON o.id = oi.order_id
        LEFT JOIN reviews r ON oi.product_id = r.product_id AND o.user_id = r.user_id
        WHERE d.rider_id = %s
          AND MONTH(d.assigned_at) = MONTH(CURRENT_DATE)
          AND YEAR(d.assigned_at) = YEAR(CURRENT_DATE)
    """, (rider_id,), fetch=True, fetchone=True)

    return render_template('rider/dashboard.html',
                         deliveries=deliveries,
                         status=status,
                         pending_deliveries=stats['pending_deliveries'],
                         completed_deliveries=stats['completed_deliveries'],
                         monthly_earnings=stats['monthly_earnings'],
                         avg_rating=stats['avg_rating'])

@rider_bp.route('/deliveries/update-status', methods=['POST'])
@login_required
@rider_required
def update_delivery_status():
    delivery_id = request.form.get('delivery_id')
    status = request.form.get('status')
    notes = request.form.get('notes', '')
    try:
        if Delivery.update_status(delivery_id, status, notes if notes.strip() else None):
            flash('Delivery status updated and customer notified.', 'success')
            # Fetch for notification
            delivery = Delivery.get_by_id(delivery_id)
            if delivery and delivery['order']:
                customer = User.get_by_id(delivery['order']['user_id'])
                if customer and customer['email']:
                    print(f"Notification: Delivery {delivery_id} status changed to '{status}' for customer {customer['email']}")
        else:
            flash('Failed to update delivery status.', 'error')
    except Exception as e:
        flash('Error updating delivery status.', 'error')
    return redirect(url_for('rider.dashboard'))

@rider_bp.route('/delivery/<int:delivery_id>/details')
@login_required
@rider_required
def delivery_details(delivery_id):
    delivery = Delivery.get_by_id(delivery_id)
    if not delivery or delivery['rider_id'] != session['user_id']:
        return jsonify({'error': 'Delivery not found or unauthorized.'}), 404
    html = render_template('rider/delivery_detail_modal.html', delivery=delivery)
    return jsonify({'html': html})
