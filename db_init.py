import os
import sqlite3
from werkzeug.security import generate_password_hash

# Resolve absolute path for data.db
DB_PATH = os.path.join(os.path.dirname(__file__), 'data.db')

def init_db():
    print(f"Initializing database at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. Create Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user'
    );
    """)

    # 2. Create Agents Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        bio TEXT,
        image TEXT
    );
    """)

    # 3. Create Properties Table
    # Extended to include 'tag' and 'category' (buy/rent) matching frontend templates.
    # Storing bedrooms/bathrooms/area as TEXT/INTEGER as needed.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS properties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        price INTEGER NOT NULL,
        location TEXT NOT NULL,
        type TEXT NOT NULL,
        bedrooms TEXT NOT NULL,
        bathrooms TEXT NOT NULL,
        area TEXT NOT NULL,
        image TEXT NOT NULL,
        tag TEXT NOT NULL,
        description TEXT,
        category TEXT NOT NULL,
        agent_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (agent_id) REFERENCES agents (id) ON DELETE SET NULL
    );
    """)

    # 4. Create Inquiries Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inquiries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER,
        name TEXT NOT NULL,
        email TEXT,
        phone TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (property_id) REFERENCES properties (id) ON DELETE SET NULL
    );
    """)

    # 5. Create Favorites Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        property_id INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (property_id) REFERENCES properties (id) ON DELETE CASCADE
    );
    """)

    # --- Seeding Initial Data ---

    # A. Seed Default Admin and Users
    # Password hashed for 'admin' and 'user'
    cursor.execute("SELECT id FROM users WHERE email = 'admin@dreamnest.com'")
    if not cursor.fetchone():
        admin_pass = generate_password_hash('admin')
        user_pass = generate_password_hash('password')
        cursor.executemany("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)", [
            ('Administrator', 'admin@dreamnest.com', admin_pass, 'admin'),
            ('Test Customer', 'customer@dreamnest.com', user_pass, 'user')
        ])
        print("Seeded default users (admin@dreamnest.com / admin, customer@dreamnest.com / password)")

    # B. Seed Default Agents
    cursor.execute("SELECT COUNT(*) FROM agents")
    if cursor.fetchone()[0] == 0:
        agents_data = [
            ('Preeti Patel', 'preeti@dreamnestsurat.com', '+91 98765 43211', 'Vesu & Pal Luxury Specialist', 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=300&q=80'),
            ('Amit Mehta', 'amit@dreamnestsurat.com', '+91 98765 43212', 'Commercial Hubs Partner', 'https://images.unsplash.com/photo-1560250097-0b93528c311a?auto=format&fit=crop&w=300&q=80'),
            ('Sameer Deshmukh', 'sameer@dreamnestsurat.com', '+91 98765 43213', 'NRI Acquisition Desk Lead', 'https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?auto=format&fit=crop&w=300&q=80'),
            ('Vikram Shah', 'vikram@dreamnestsurat.com', '+91 98765 43214', 'Suburban Housing Consultant', 'https://images.unsplash.com/photo-1560518883-ce09059eeffa?auto=format&fit=crop&w=300&q=80')
        ]
        cursor.executemany("INSERT INTO agents (name, email, phone, bio, image) VALUES (?, ?, ?, ?, ?)", agents_data)
        print("Seeded default agents.")

    # C. Seed Default Properties
    # Map them to Preeti Patel (agent_id = 1) or Amit Mehta (agent_id = 2)
    cursor.execute("SELECT id FROM agents WHERE name = 'Preeti Patel'")
    preeti_id = cursor.fetchone()[0]
    cursor.execute("SELECT id FROM agents WHERE name = 'Amit Mehta'")
    amit_id = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM properties")
    if cursor.fetchone()[0] == 0:
        # Note: image stores comma-separated URLs to support image galleries in property details.
        properties_data = [
            (
                'The Aurelia Penthouse', 38500000, 'vesu', 'apartment', '4 BHK', '4 Baths', '4,200 sq ft',
                'https://images.unsplash.com/photo-1613490493576-7fde63acd811?auto=format&fit=crop&w=1200&q=80,https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=800&q=80,https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=800&q=80,https://images.unsplash.com/photo-1600566753376-12c8ab7fb75b?auto=format&fit=crop&w=800&q=80',
                'Luxury Penthouse',
                'Introducing The Aurelia, Vesu\'s crowning residential jewel. This custom-built 4 BHK penthouse offers a seamless blend of grand scale and high sophistication. Featuring double-height ceilings, a private infinity pool overlooking Surat\'s expanding skyline, Italian Carrara marble flooring throughout, and a smart automation suite powered by Alpine.js protocols. Ideal for high-profile business families looking for security, luxury, and unmatched status.',
                'buy', preeti_id
            ),
            (
                'Palacio Luxury Villa', 52000000, 'pal', 'villa', '5 BHK', '6 Baths', '5,800 sq ft',
                'https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=1200&q=80,https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=800&q=80,https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=800&q=80,https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?auto=format&fit=crop&w=800&q=80',
                'Premium Mansion',
                'The Palacio Villa represents state-of-the-art living. Located in a secure gated township in Pal, this architectural masterpiece boasts 5 ultra-luxury bedrooms, a modular island kitchen, custom walk-in closets, and landscaped lawns. A dedicated climate-controlled home theater, personal gymnasium, and fully integrated smart-lighting system makes this home a private sanctuary for you and your family.',
                'buy', preeti_id
            ),
            (
                'Rajhans Corporate Suite', 14500000, 'viproad', 'commercial', 'Furnished', '2 Parking Slots', '1,650 sq ft',
                'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=1200&q=80,https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=800&q=80,https://images.unsplash.com/photo-1497215728101-856f4ea42174?auto=format&fit=crop&w=800&q=80,https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?auto=format&fit=crop&w=800&q=80',
                'Corporate Office',
                'Position your business in Surat\'s premier commercial high-rise on VIP Road. This premium office suite is fully fitted with acoustic glass partitions, centralized VRF climate control, 15 executive workspaces, a modular pantry, and a dedicated 8-person boardroom. Boasts high footfall and seamless road access to Vesu, Bhatar, and Surat airport.',
                'buy', amit_id
            ),
            (
                'Gold Coast Residency', 21000000, 'piplod', 'apartment', '3 BHK', '3 Baths', '2,400 sq ft',
                'https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&w=800&q=80',
                'River View Flat',
                'Elegant high-rise flat with views of Tapi River. High-quality construction, modular fittings, and close to recreational hubs in Piplod.',
                'buy', preeti_id
            ),
            (
                'Green Meadows Plot', 18000000, 'althan', 'plot', 'N/A', 'N/A', '3,600 sq ft',
                'https://images.unsplash.com/photo-1564013799919-ab600027ffc6?auto=format&fit=crop&w=800&q=80',
                'Premium Plot',
                'Fully developed residential plot in secure gated township in Althan. Ready for immediate construction.',
                'buy', preeti_id
            ),
            (
                'Shreepad HighStreet Shop', 6500000, 'adajan', 'commercial', 'Retail', '1 slot', '800 sq ft',
                'https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=800&q=80',
                'Commercial Shop',
                'Ground floor retail space in premium commercial hub of Adajan. High footfall area.',
                'buy', amit_id
            ),
            (
                'Dumas Road High-Rise Plaza', 42000000, 'dumasroad', 'commercial', 'Bare Shell', '5 slots', '4,500 sq ft',
                'https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?auto=format&fit=crop&w=800&q=80',
                'Showroom Space',
                'Premium showroom space on main Dumas Road. Unrestricted views, excellent branding opportunities, and dedicated visitor parking.',
                'buy', amit_id
            ),
            (
                'Vesu Executive Rental Flat', 45000, 'vesu', 'apartment', '3 BHK', '3 Baths', '2,100 sq ft',
                'https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=800&q=80',
                'Furnished Apartment',
                'Fully furnished 3 BHK flat ready to move in Vesu. Premium interiors, modular kitchen, and modern appliances included.',
                'rent', preeti_id
            ),
            (
                'Adajan Shared Cowork Suite', 28000, 'adajan', 'commercial', 'Plug-Play', 'Shared', '950 sq ft',
                'https://images.unsplash.com/photo-1497215728101-856f4ea42174?auto=format&fit=crop&w=800&q=80',
                'Office Space',
                'Fully managed plug-and-play office rental in Adajan. High speed internet, shared meeting rooms, and receptionist services.',
                'rent', amit_id
            ),
            (
                'Althan Luxury Rental Villa', 120000, 'althan', 'villa', '4 BHK', '5 Baths', '4,600 sq ft',
                'https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=800&q=80',
                'Modern Bungalow',
                'Modern 4 BHK bungalow with private garden in Althan. Located in a peaceful and secure neighborhood, perfect for corporate executives.',
                'rent', preeti_id
            )
        ]
        cursor.executemany("""
        INSERT INTO properties (title, price, location, type, bedrooms, bathrooms, area, image, tag, description, category, agent_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, properties_data)
        print("Seeded default properties.")

    # D. Seed Default Inquiries
    cursor.execute("SELECT COUNT(*) FROM inquiries")
    if cursor.fetchone()[0] == 0:
        cursor.execute("SELECT id FROM properties WHERE title = 'The Aurelia Penthouse'")
        aurelia_id = cursor.fetchone()[0]
        inquiries_data = [
            (aurelia_id, 'Rajesh Shah', 'rajesh@example.com', '+91 98251 12345', 'Tour Request: The Aurelia Penthouse - 24th June at 04:00 PM (In-Person)'),
            (None, 'Nikhil Mehta', 'nikhil@example.com', '+91 99099 54321', 'General Query: Interested in retail shop listings under 1 Crore in Pal.')
        ]
        cursor.executemany("INSERT INTO inquiries (property_id, name, email, phone, message) VALUES (?, ?, ?, ?, ?)", inquiries_data)
        print("Seeded default inquiries.")

    conn.commit()
    conn.close()
    print("Database initialisation completed successfully!")

if __name__ == '__main__':
    init_db()
