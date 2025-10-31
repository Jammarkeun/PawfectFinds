from flask import request as flask_request
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import current_app
from app import db
from app.models.models import RiderAvailability, Order, Notification
import json

# Initialize SocketIO without app (will be initialized with app later)
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')

# Store active rider connections
active_riders = {}

def init_rider_websocket(app):
    """Initialize WebSocket with the Flask app"""
    socketio.init_app(app, cors_allowed_origins="*")
    return socketio

@socketio.on('connect')
def handle_connect():
    """Handle new WebSocket connection"""
    print(f"Client connected: {flask_request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print(f"Client disconnected: {flask_request.sid}")
    # Remove from active riders if they were connected as a rider
    for rider_id, sid in list(active_riders.items()):
        if sid == flask_request.sid:
            del active_riders[rider_id]
            break

@socketio.on('rider_online')
def handle_rider_online(data):
    """Handle when a rider comes online"""
    rider_id = data.get('rider_id')
    if rider_id:
        # Add rider to active riders and join their personal room
        active_riders[rider_id] = flask_request.sid
        join_room(f'rider_{rider_id}')
        
        # Also join the general riders room for broadcast messages
        join_room('riders')
        print(f"Rider {rider_id} is now online and available")

        # Update rider availability in database
        rider = RiderAvailability.query.filter_by(rider_id=rider_id).first()
        if not rider:
            rider = RiderAvailability(rider_id=rider_id, is_online=True, is_available=True)
            db.session.add(rider)
        else:
            rider.is_online = True
            rider.is_available = True
        
        try:
            db.session.commit()
            print(f"Rider {rider_id} availability updated in database")
        except Exception as e:
            db.session.rollback()
            print(f"Error updating rider availability: {str(e)}")
            
        # Send any pending orders to the rider
        pending_orders = Order.query.filter(
            Order.status == 'ready_for_pickup',
            Order.rider_id.is_(None)
        ).all()
        
        for order in pending_orders:
            order_data = {
                'id': order.id,
                'order_number': order.order_number,
                'total_amount': float(order.total_amount) if order.total_amount else 0,
                'pickup_address': {
                    'name': order.seller.business_name or 'Store',
                    'address': f"{order.seller.address or 'Pickup Location'}, {order.seller.city or ''}, {order.seller.province or ''}",
                    'contact': order.seller.phone or ''
                },
                'delivery_address': {
                    'name': order.shipping_address.recipient_name,
                    'address': f"{order.shipping_address.street_address}, {order.shipping_address.city}, {order.shipping_address.province}",
                    'contact': order.shipping_address.contact_number
                },
                'items': [{
                    'name': item.product.name,
                    'quantity': item.quantity,
                    'price': float(item.price) if item.price else 0
                } for item in order.items],
                'items_count': len(order.items)
            }
            
            emit('new_delivery_opportunity', {
                'order_id': order_data['id'],
                'order_number': order_data['order_number'],
                'pickup_address': order_data['pickup_address'],
                'delivery_address': order_data['delivery_address'],
                'total_amount': order_data['total_amount'],
                'items_count': order_data['items_count']
            }, room=flask_request.sid)

def notify_riders_new_order(order_data):
    """Notify all available riders about a new order"""
    try:
        # Get all available riders who are online and not currently on a delivery
        available_riders = RiderAvailability.query.filter_by(
            is_online=True, 
            is_available=True,
            current_order_id=None
        ).all()
        
        print(f"Notifying {len(available_riders)} available riders about order {order_data['id']}")
        
        for rider in available_riders:
            if rider.rider_id in active_riders:
                try:
                    # Send the order details to the rider
                    socketio.emit('new_delivery_opportunity', {
                        'order_id': order_data['id'],
                        'order_number': order_data['order_number'],
                        'pickup_address': order_data['pickup_address'],
                        'delivery_address': order_data['delivery_address'],
                        'total_amount': order_data['total_amount'],
                        'items_count': order_data['items_count']
                    }, room=active_riders[rider.rider_id])
                    print(f"Notification sent to rider {rider.rider_id}")
                except Exception as e:
                    print(f"Error notifying rider {rider.rider_id}: {str(e)}")
    except Exception as e:
        print(f"Error in notify_riders_new_order: {str(e)}")

def notify_order_taken(order_id, rider_id):
    """Notify all riders that an order has been taken"""
    try:
        print(f"Notifying all riders that order {order_id} was taken by rider {rider_id}")
        
        # Notify the rider who took the order
        if rider_id in active_riders:
            socketio.emit('order_accepted', {
                'order_id': order_id,
                'message': 'You have accepted this order.'
            }, room=active_riders[rider_id])
        
        # Notify all other riders that the order is no longer available
        socketio.emit('order_taken', {
            'order_id': order_id,
            'rider_id': rider_id,
            'message': 'This order has been accepted by another rider.'
        }, room='riders')
        
        print(f"Order {order_id} taken notification sent to all riders")
    except Exception as e:
        print(f"Error in notify_order_taken: {str(e)}")

@socketio.on('accept_order')
def handle_accept_order(data):
    """Handle when a rider accepts an order"""
    try:
        rider_id = data.get('rider_id')
        order_id = data.get('order_id')
        
        if not rider_id or not order_id:
            print(f"Missing rider_id or order_id in accept_order: {data}")
            return
            
        print(f"Rider {rider_id} is attempting to accept order {order_id}")
        
        # Get the rider's availability
        rider = RiderAvailability.query.filter_by(rider_id=rider_id).first()
        if not rider or not rider.is_available:
            print(f"Rider {rider_id} is not available to accept orders")
            emit('order_accept_error', {
                'order_id': order_id,
                'message': 'You are not available to accept orders.'
            }, room=flask_request.sid)
            return
        
        # Use database transaction with row locking to prevent race conditions
        try:
            # Start a database transaction
            order = Order.query.filter_by(
                id=order_id,
                status='ready_for_pickup',
                rider_id=None
            ).with_for_update().first()
            
            if not order:
                print(f"Order {order_id} is no longer available")
                emit('order_accept_error', {
                    'order_id': order_id,
                    'message': 'This order is no longer available.'
                }, room=flask_request.sid)
                return
                
            # Assign the order to the rider
            order.rider_id = rider_id
            order.status = 'assigned'
            order.assigned_at = datetime.utcnow()
            
            # Update rider availability
            rider.is_available = False
            rider.current_order_id = order_id
            
            # Save changes to the database
            db.session.commit()
            
            print(f"Order {order_id} assigned to rider {rider_id}")
            
            # Notify all riders that the order has been taken
            notify_order_taken(order_id, rider_id)
            
            # Send success response to the rider
            emit('order_accepted', {
                'order_id': order_id,
                'message': 'Order accepted successfully!',
                'redirect_url': url_for('rider.order_details', order_id=order_id)
            }, room=flask_request.sid)
            
        except Exception as e:
            db.session.rollback()
            print(f"Error assigning order {order_id} to rider {rider_id}: {str(e)}")
            emit('order_accept_error', {
                'order_id': order_id,
                'message': 'An error occurred while accepting the order. Please try again.'
            }, room=flask_request.sid)
    
    except Exception as e:
        print(f"Error in handle_accept_order: {str(e)}")
        emit('order_accept_error', {
            'order_id': data.get('order_id'),
            'message': 'An unexpected error occurred. Please try again.'
        }, room=flask_request.sid)
