INSERT INTO customers (full_name, email, country, status, created_at) VALUES
('Anna Keller', 'anna@example.com', 'Germany', 'active', '2025-01-10'),
('Marco Rossi', 'marco@example.com', 'Italy', 'active', '2025-03-04'),
('Sofia Martin', 'sofia@example.com', 'France', 'active', '2025-05-11'),
('Lena Novak', 'lena@example.com', 'Austria', 'inactive', '2025-07-01'),
('Omid Rahimi', 'omid@example.com', 'Germany', 'active', '2026-01-15'),
('Eva Jensen', 'eva@example.com', 'Denmark', 'active', '2026-02-20');

INSERT INTO products (sku, name, category, unit_price, active) VALUES
('KB-100', 'Mechanical Keyboard', 'Accessories', 129.00, true),
('MS-200', 'Wireless Mouse', 'Accessories', 69.00, true),
('MN-300', '27-inch Monitor', 'Displays', 349.00, true),
('DS-400', 'USB-C Dock', 'Accessories', 179.00, true),
('HP-500', 'Studio Headphones', 'Audio', 219.00, true),
('WC-600', '4K Webcam', 'Video', 159.00, true);

INSERT INTO orders (customer_id, status, ordered_at, currency) VALUES
(1, 'paid',      '2026-01-05 10:00:00+00', 'EUR'),
(2, 'shipped',   '2026-01-12 14:30:00+00', 'EUR'),
(1, 'shipped',   '2026-02-03 09:15:00+00', 'EUR'),
(3, 'paid',      '2026-02-17 17:45:00+00', 'EUR'),
(5, 'shipped',   '2026-03-02 11:20:00+00', 'EUR'),
(6, 'paid',      '2026-03-21 08:00:00+00', 'EUR'),
(2, 'cancelled', '2026-04-01 19:00:00+00', 'EUR'),
(5, 'paid',      '2026-04-11 12:10:00+00', 'EUR'),
(3, 'shipped',   '2026-05-04 16:00:00+00', 'EUR'),
(1, 'paid',      '2026-05-18 13:35:00+00', 'EUR');

INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
(1, 1, 1, 129.00), (1, 2, 1, 69.00),
(2, 3, 2, 349.00),
(3, 4, 1, 179.00), (3, 2, 2, 69.00),
(4, 5, 1, 219.00),
(5, 3, 1, 349.00), (5, 4, 1, 179.00),
(6, 6, 2, 159.00),
(7, 1, 1, 129.00),
(8, 1, 2, 129.00), (8, 5, 1, 219.00),
(9, 3, 1, 349.00), (9, 6, 1, 159.00),
(10, 4, 2, 179.00), (10, 2, 1, 69.00);
