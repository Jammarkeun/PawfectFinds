from app.services.database import Database
from app.models.cart import Cart

class Order:
    """Order model to handle order creation and management"""

    @classmethod
    def create_from_cart(cls, user_id, shipping_address, payment_method='cod', notes=None):
        db = Database()
        items = Cart.get_user_cart(user_id)
        if not items:
            return None
        # Group by seller - create one order per seller like Shopee
        orders_created = []
        items_by_seller = {}
        for item in items:
            items_by_seller.setdefault(item['seller_id'], []).append(item)
        for seller_id, s_items in items_by_seller.items():
            total = sum(float(i['price']) * i['quantity'] for i in s_items)
            order_id = db.execute_query(
                """
                INSERT INTO orders (user_id, seller_id, total_amount, shipping_address, payment_method, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (user_id, seller_id, total, shipping_address, payment_method, notes),
            )
            for i in s_items:
                db.execute_query(
                    """
                    INSERT INTO order_items (order_id, product_id, quantity, price_at_time)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (order_id, i['product_id'], i['quantity'], i['price']),
                )
                # reduce stock
                db.execute_query(
                    "UPDATE products SET stock_quantity = stock_quantity - %s WHERE id = %s",
                    (i['quantity'], i['product_id']),
                )
            orders_created.append(order_id)
        # clear cart
        Cart.clear_cart(user_id)
        return orders_created

    @classmethod
    def get_by_id(cls, order_id):
        db = Database()
        order = db.execute_query("SELECT * FROM orders WHERE id = %s", (order_id,), fetch=True, fetchone=True)
        if not order:
            return None
        items = db.execute_query(
            """
            SELECT oi.id, oi.order_id, oi.product_id, oi.quantity, oi.price_at_time,
                   p.name, p.image_url FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = %s
            """,
            (order_id,),
            fetch=True,
        )
        order['items'] = items
        return order

    @classmethod
    def list_for_user(cls, user_id, limit=None, offset=0):
        db = Database()
        query = "SELECT * FROM orders WHERE user_id = %s ORDER BY created_at DESC"
        if limit:
            query += " LIMIT %s OFFSET %s"
            return db.execute_query(query, (user_id, limit, offset), fetch=True)
        return db.execute_query(query, (user_id,), fetch=True)

    @classmethod
    def list_for_seller(cls, seller_id, status=None, limit=None, offset=0):
        db = Database()
        query = """
            SELECT o.*, u.first_name as customer_name, u.email as customer_email, u.phone as customer_phone,
                   r.first_name as rider_name, r.last_name as rider_last_name, r.phone as rider_phone,
                   COUNT(oi.id) as items_count
            FROM orders o
            LEFT JOIN users u ON o.user_id = u.id
            LEFT JOIN deliveries d ON o.id = d.order_id
            LEFT JOIN users r ON d.rider_id = r.id
            LEFT JOIN order_items oi ON o.id = oi.order_id
            WHERE o.seller_id = %s
        """
        params = [seller_id]
        if status:
            query += " AND o.status = %s"
            params.append(status)
        query += " GROUP BY o.id ORDER BY o.created_at DESC"
        if limit:
            query += " LIMIT %s OFFSET %s"
            params.extend([limit, offset])
        orders = db.execute_query(query, params, fetch=True)
        # Add items for each order
        for order in orders:
            items = db.execute_query(
                """
                SELECT oi.id, oi.order_id, oi.product_id, oi.quantity, oi.price_at_time,
                       p.name, p.image_url FROM order_items oi
                JOIN products p ON oi.product_id = p.id
                WHERE oi.order_id = %s
                """,
                (order['id'],),
                fetch=True,
            )
            order['items'] = items
        return orders

    @classmethod
    def update_status(cls, order_id, status):
        db = Database()
        db.execute_query("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))
        return True

    @classmethod
    def update_payment_status(cls, order_id, payment_status):
        db = Database()
        db.execute_query("UPDATE orders SET payment_status = %s WHERE id = %s", (payment_status, order_id))
        return True

    @classmethod
    def count(cls, status=None):
        db = Database()
        query = "SELECT COUNT(*) as count FROM orders WHERE 1=1"
        params = []
        if status:
            query += " AND status = %s"
            params.append(status)
        res = db.execute_query(query, params, fetch=True, fetchone=True)
        return res['count'] if res else 0

