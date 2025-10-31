from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import request
import json

socketio = SocketIO(cors_allowed_origins="*")

# Store active riders and their socket IDs
active_riders = {}  # {rider_id: [socket_id1, socket_id2, ...]}
order_rooms = {}  # {order_id: {'rider_id': rider_id, 'status': 'pending'}}

def init_websocket(app):
    """Initialize WebSocket with the Flask app"""
    socketio.init_app(app)
    return socketio

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')

@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client disconnected: {request.sid}')
    # Clean up any rider associations
    for rider_id, sockets in list(active_riders.items()):
        if request.sid in sockets:
            sockets.remove(request.sid)
            if not sockets:
                del active_riders[rider_id]
                # Notify all sellers that rider went offline
                emit('rider_status', {'rider_id': rider_id, 'is_online': False}, broadcast=True)

@socketio.on('rider_online')
def handle_rider_online(data):
    """Handle rider coming online"""
    rider_id = data.get('rider_id')
    if not rider_id:
        return
    
    # Add rider to active riders
    if rider_id not in active_riders:
        active_riders[rider_id] = []
    if request.sid not in active_riders[rider_id]:
        active_riders[rider_id].append(request.sid)
    
    # Join rider to their personal room
    join_room(f'rider_{rider_id}')
    
    # Notify all sellers that a rider is online
    emit('rider_status', {'rider_id': rider_id, 'is_online': True}, broadcast=True)

@socketio.on('new_order')
def handle_new_order(data):
    """Notify all active riders about a new order"""
    order_id = data.get('order_id')
    if not order_id:
        return
    
    # Create a room for this order
    order_rooms[order_id] = {'status': 'pending', 'rider_id': None}
    
    # Emit to all riders
    emit('new_delivery_available', 
         {'order_id': order_id, 'order_details': data.get('order_details')}, 
         room='riders',
         namespace='/')

@socketio.on('accept_order')
def handle_accept_order(data):
    """Handle rider accepting an order"""
    order_id = data.get('order_id')
    rider_id = data.get('rider_id')
    
    if not order_id or not rider_id or order_id not in order_rooms:
        return {'status': 'error', 'message': 'Invalid order or rider'}
    
    # Check if order is still available
    if order_rooms[order_id]['status'] != 'pending':
        return {'status': 'error', 'message': 'Order already taken'}
    
    # Mark order as accepted
    order_rooms[order_id].update({
        'status': 'accepted',
        'rider_id': rider_id
    })
    
    # Notify all riders that order is taken
    emit('order_taken', 
         {'order_id': order_id, 'rider_id': rider_id}, 
         room='riders',
         namespace='/')
    
    # Notify the seller
    emit('order_accepted', 
         {'order_id': order_id, 'rider_id': rider_id}, 
         room=f'seller_{data.get("seller_id")}',
         namespace='/')
    
    return {'status': 'success', 'message': 'Order accepted successfully'}

@socketio.on('update_location')
def handle_location_update(data):
    """Update rider's current location"""
    rider_id = data.get('rider_id')
    lat = data.get('lat')
    lng = data.get('lng')
    
    if rider_id and lat is not None and lng is not None:
        # Update in database
        from app.services.database import Database
        db = Database()
        db.execute_query(
            """
            INSERT INTO rider_availability (rider_id, is_online, current_location)
            VALUES (%s, TRUE, POINT(%s, %s))
            ON CONFLICT (rider_id) 
            DO UPDATE SET 
                is_online = TRUE,
                last_seen = CURRENT_TIMESTAMP,
                current_location = POINT(%s, %s)
            """,
            (rider_id, lng, lat, lng, lat)
        )
        
        # Notify all sellers about rider's location update
        emit('rider_location_updated', 
             {'rider_id': rider_id, 'lat': lat, 'lng': lng}, 
             broadcast=True)

@socketio.on('join_riders_room')
def join_riders_room():
    """Join the general riders room"""
    join_room('riders')

@socketio.on('join_seller_room')
def join_seller_room(data):
    """Join a seller's specific room"""
    seller_id = data.get('seller_id')
    if seller_id:
        join_room(f'seller_{seller_id}')

@socketio.on('leave_riders_room')
def leave_riders_room():
    """Leave the general riders room"""
    leave_room('riders')

@socketio.on('leave_seller_room')
def leave_seller_room(data):
    """Leave a seller's specific room"""
    seller_id = data.get('seller_id')
    if seller_id:
        leave_room(f'seller_{seller_id}')
