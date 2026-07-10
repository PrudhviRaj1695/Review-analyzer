-- Products table
CREATE TABLE products (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL,
  price DECIMAL(10, 2) NOT NULL,
  rating DECIMAL(3, 2)
);

-- Reviews table with foreign key constraint
CREATE TABLE reviews (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  product_id INTEGER NOT NULL,
  text TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

-- Example data
INSERT INTO products (name, price, rating) VALUES
  ('Laptop', 999.99, 4.5),
  ('Mouse', 29.99, 4.2),
  ('Keyboard', 79.99, 4.7);

INSERT INTO reviews (product_id, text) VALUES
  (1, 'Excellent laptop, very fast!'),
  (1, 'Battery life could be better'),
  (2, 'Great mouse for the price'),
  (3, 'Best keyboard I have used');
