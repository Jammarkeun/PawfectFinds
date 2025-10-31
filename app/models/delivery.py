from app.services.database import Database

class Delivery:
    @staticmethod
    def create(order_id, rider_id, delivery_notes=None):
        """Create a new delivery assignment"""
        db = Database()
        try:
            # Insert delivery with initial status and timestamp
            db.execute_query(
                """
                INSERT INTO deliveries (order_id, rider_id, status, delivery_notes, assigned_at)
                VALUES (%s, %s, 'assigned', %s, CURRENT_TIMESTAMP)
                """,
                (order_id, rider_id, delivery_notes)
            )
            # Update order with rider_id and status to shipped
            db.execute_query(
                """
                UPDATE orders
                SET rider_id = %s, status = 'shipped'
                WHERE id = %s
                """,
                (rider_id, order_id)
            )
            return True
        except Exception as e:
            print(f"Error creating delivery: {e}")
            return False

    @staticmethod
    def get_by_id(delivery_id):
        """Get delivery by ID"""
        db = Database()
        result = db.execute_query(
            "SELECT * FROM deliveries WHERE id = %s",
            (delivery_id,),
            fetch=True,
            fetchone=True
        )
        if result:
            # Add order and rider details
            order = db.execute_query(
                "SELECT * FROM orders WHERE id = %s",
                (result['order_id'],),
                fetch=True,
                fetchone=True
            )
            if order:
                # Get order items
                items = db.execute_query(
                    "SELECT oi.*, p.name, p.image_url FROM order_items oi JOIN products p ON oi.product_id = p.id WHERE oi.order_id = %s",
                    (order['id'],),
                    fetch=True
                )
                order['items'] = items

                # Get customer details
                customer = db.execute_query(
                    "SELECT first_name, last_name, phone FROM users WHERE id = %s",
                    (order['user_id'],),
                    fetch=True,
                    fetchone=True
                )
                if customer:
                    result['customer_name'] = f"{customer['first_name']} {customer['last_name']}"
                    result['customer_phone'] = customer['phone'] or ''
                else:
                    result['customer_name'] = 'Unknown'
                    result['customer_phone'] = ''

                result['order'] = order

            rider = db.execute_query(
                "SELECT id, first_name, last_name, phone FROM users WHERE id = %s",
                (result['rider_id'],),
                fetch=True,
                fetchone=True
            )
            if rider:
                result['rider'] = rider
        return result

    @staticmethod
    def get_by_order_id(order_id):
        """Get delivery by order ID to check if assigned"""
        db = Database()
        return db.execute_query(
            "SELECT * FROM deliveries WHERE order_id = %s",
            (order_id,),
            fetch=True,
            fetchone=True
        )

    @staticmethod
    def list_for_rider(rider_id, status=None):
        """List deliveries for a rider"""
        db = Database()
        query = """
            SELECT d.*, o.user_id, o.seller_id, o.total_amount, o.shipping_address,
                   o.payment_method, o.notes as order_notes
            FROM deliveries d
            JOIN orders o ON d.order_id = o.id
            WHERE d.rider_id = %s
        """
        params = [rider_id]
        if status:
            query += " AND d.status = %s"
            params.append(status)
        query += " ORDER BY d.assigned_at DESC"
        
        results = db.execute_query(query, tuple(params), fetch=True)
        for delivery in results:
            # Add customer details
            customer = db.execute_query(
                "SELECT first_name, last_name, phone FROM users WHERE id = %s",
                (delivery['user_id'],),
                fetch=True,
                fetchone=True
            )
            if customer:
                delivery['customer_name'] = f"{customer['first_name']} {customer['last_name']}"
                delivery['customer_phone'] = customer['phone'] or ''
            else:
                delivery['customer_name'] = 'Unknown'
                delivery['customer_phone'] = ''
        return results

    @staticmethod
    def update_status(delivery_id, status, notes=None):
        """Update delivery status (picked_up, on_the_way, delivered, failed)"""
        db = Database()
        try:
            # Update delivery with status and optional notes/timestamp
            timestamp_field = None
            if status == 'picked_up':
                timestamp_field = 'picked_up_at = CURRENT_TIMESTAMP'
            elif status == 'on_the_way':
                timestamp_field = 'on_the_way_at = CURRENT_TIMESTAMP'
            elif status == 'delivered':
                timestamp_field = 'delivered_at = CURRENT_TIMESTAMP'

            if notes:
                if timestamp_field:
                    db.execute_query(
                        f"""
                        UPDATE deliveries
                        SET status = %s, delivery_notes = %s, {timestamp_field}
                        WHERE id = %s
                        """,
                        (status, notes, delivery_id)
                    )
                else:
                    db.execute_query(
                        """
                        UPDATE deliveries
                        SET status = %s, delivery_notes = %s
                        WHERE id = %s
                        """,
                        (status, notes, delivery_id)
                    )
            else:
                if timestamp_field:
                    db.execute_query(
                        f"""
                        UPDATE deliveries
                        SET status = %s, {timestamp_field}
                        WHERE id = %s
                        """,
                        (status, delivery_id)
                    )
                else:
                    db.execute_query(
                        """
                        UPDATE deliveries
                        SET status = %s
                        WHERE id = %s
                        """,
                        (status, delivery_id)
                    )

            # Update order status accordingly
            delivery = db.execute_query(
                "SELECT order_id FROM deliveries WHERE id = %s",
                (delivery_id,),
                fetch=True,
                fetchone=True
            )
            if delivery:
                order_id = delivery['order_id']
                order_status_map = {
                    'picked_up': 'picked_up',
                    'on_the_way': 'on_the_way',
                    'delivered': 'delivered',
                    'failed': 'cancelled'
                }
                new_order_status = order_status_map.get(status, 'shipped')

                # Set order timestamp if applicable
                order_timestamp_field = None
                if status == 'picked_up':
                    order_timestamp_field = 'picked_up_at = CURRENT_TIMESTAMP'
                elif status == 'delivered':
                    order_timestamp_field = 'delivered_at = CURRENT_TIMESTAMP'

                if order_timestamp_field:
                    db.execute_query(
                        f"""
                        UPDATE orders
                        SET status = %s, {order_timestamp_field}
                        WHERE id = %s
                        """,
                        (new_order_status, order_id)
                    )
                else:
                    db.execute_query(
                        """
                        UPDATE orders
                        SET status = %s
                        WHERE id = %s
                        """,
                        (new_order_status, order_id)
                    )

            return True
        except Exception as e:
            print(f"Error updating delivery status: {e}")
            return False

    @staticmethod
    def assign_rider(order_id, rider_id, delivery_notes=None):
        """Assign or change rider for an order"""
        db = Database()
        try:
            # Check if delivery exists
            existing = db.execute_query("SELECT id FROM deliveries WHERE order_id = %s", (order_id,), fetch=True, fetchone=True)
            if existing:
                # Update existing delivery
                db.execute_query(
                    "UPDATE deliveries SET rider_id = %s, delivery_notes = %s WHERE order_id = %s",
                    (rider_id, delivery_notes, order_id)
                )
            else:
                # Create new delivery
                db.execute_query(
                    """
                    INSERT INTO deliveries (order_id, rider_id, status, delivery_notes, assigned_at)
                    VALUES (%s, %s, 'assigned', %s, CURRENT_TIMESTAMP)
                    """,
                    (order_id, rider_id, delivery_notes)
                )

            # Update order with rider_id, set status to shipped if not already shipped or later
            db.execute_query(
                """
                UPDATE orders
                SET rider_id = %s, status = CASE WHEN status NOT IN ('shipped', 'on_the_way', 'delivered') THEN 'shipped' ELSE status END
                WHERE id = %s
                """,
                (rider_id, order_id)
            )
            return True
        except Exception as e:
            print(f"Error assigning rider: {e}")
            return False

    @staticmethod
    def get_all_riders_with_availability():
        """Get all active riders with availability status"""
        db = Database()
        return db.execute_query(
            """
            SELECT u.id, u.first_name, u.last_name, u.phone,
                   COUNT(d.id) as current_deliveries
            FROM users u
            LEFT JOIN deliveries d ON u.id = d.rider_id AND d.status != 'delivered'
            WHERE u.role = 'rider' AND u.status = 'active'
            GROUP BY u.id, u.first_name, u.last_name, u.phone
            ORDER BY current_deliveries ASC
            """,
            fetch=True
        )
