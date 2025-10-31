from app.services.database import Database

class Cart:
    """Cart model to manage user's cart items"""

    @classmethod
    def add_item(cls, user_id, product_id, quantity=1):
        db = Database()
        # Upsert: if exists, update quantity
        existing = cls.get_item(user_id, product_id)
        if existing:
            new_qty = existing['quantity'] + quantity
            query = "UPDATE cart SET quantity = %s WHERE id = %s"
            db.execute_query(query, (new_qty, existing['id']))
            return True
        query = "INSERT INTO cart (user_id, product_id, quantity) VALUES (%s, %s, %s)"
        db.execute_query(query, (user_id, product_id, quantity))
        return True

    @classmethod
    def update_item(cls, cart_id, quantity):
        db = Database()
        if quantity <= 0:
            return cls.remove_item_by_id(cart_id)
        query = "UPDATE cart SET quantity = %s WHERE id = %s"
        db.execute_query(query, (quantity, cart_id))
        return True

    @classmethod
    def remove_item(cls, user_id, product_id):
        db = Database()
        query = "DELETE FROM cart WHERE user_id = %s AND product_id = %s"
        db.execute_query(query, (user_id, product_id))
        return True

    @classmethod
    def remove_item_by_id(cls, cart_id):
        db = Database()
        query = "DELETE FROM cart WHERE id = %s"
        db.execute_query(query, (cart_id,))
        return True

    @classmethod
    def clear_cart(cls, user_id):
        db = Database()
        query = "DELETE FROM cart WHERE user_id = %s"
        db.execute_query(query, (user_id,))
        return True

    @classmethod
    def get_item(cls, user_id, product_id):
        db = Database()
        query = "SELECT * FROM cart WHERE user_id = %s AND product_id = %s"
        return db.execute_query(query, (user_id, product_id), fetch=True, fetchone=True)

    @classmethod
    def get_user_cart(cls, user_id):
        db = Database()
        query = '''
            SELECT c.*, p.name, p.price, p.image_url, p.seller_id
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = %s
        '''
        return db.execute_query(query, (user_id,), fetch=True)

    @classmethod
    def get_total(cls, user_id):
        items = cls.get_user_cart(user_id)
        total = 0.0
        for item in items:
            total += float(item['price']) * item['quantity']
        return round(total, 2)

