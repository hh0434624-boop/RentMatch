#!/usr/bin/env python3
"""
========================================================================================
 RentMatch – Smart Rental Finder (Tumakuru, Karnataka)
 Complete All-In-One Single-File Web Application
 
 Department of Computer Science — B.Sc. Data Science Project
 
 This single file contains:
  1. Embedded SQLite Database & Schema (Zero setup, auto-initializing)
  2. Realistic Tumakuru Seed Data (Localities, Amenities, Houses, Accounts, Enquiries)
  3. Data Science Recommendation Engine (Multi-Attribute Utility + Cosine Similarity)
  4. Complete Flask Web Application & Role Controllers (Admin, Owner, Tenant)
  5. Embedded HTML/CSS/JS Templates (Bootstrap 5, modern UI, AJAX favourites)
  6. Automatic Browser Launcher

 Run with:
     python rentmatch_all_in_one.py
 Then open in browser: http://127.0.0.1:5000
========================================================================================
"""

import os
import sys
import math
import sqlite3
import webbrowser
import threading
from datetime import datetime
from jinja2 import DictLoader
from flask import Flask, request, redirect, url_for, session, flash, jsonify, render_template
from werkzeug.security import generate_password_hash, check_password_hash

# Try importing scikit-learn / pandas, with pure-Python mathematical fallback
try:
    import numpy as np
    import pandas as pd
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.feature_extraction.text import TfidfVectorizer
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

# ========================================================================================
# CONFIGURATION & FLASK APP
# ========================================================================================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_FILE = os.path.join(BASE_DIR, "rentmatch_allinone.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("RENTMATCH_SECRET_KEY", "rentmatch-dev-key-change-before-deployment")

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# ========================================================================================
# DATABASE INITIALIZATION & TUMAKURU SEED DATA
# ========================================================================================

def init_and_seed_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(100) NOT NULL,
        email VARCHAR(120) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        phone VARCHAR(20) NOT NULL,
        role VARCHAR(20) NOT NULL DEFAULT 'tenant',
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(100) UNIQUE NOT NULL,
        description TEXT,
        pincode VARCHAR(10)
    );
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS properties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL,
        title VARCHAR(200) NOT NULL,
        description TEXT NOT NULL,
        property_type VARCHAR(50) NOT NULL,
        location_id INTEGER NOT NULL,
        address TEXT NOT NULL,
        landmark VARCHAR(150),
        bhk VARCHAR(20) NOT NULL,
        bhk_num REAL NOT NULL,
        size_sqft INTEGER NOT NULL,
        bedrooms INTEGER NOT NULL,
        bathrooms INTEGER NOT NULL,
        balconies INTEGER DEFAULT 1,
        floor_num INTEGER DEFAULT 1,
        total_floors INTEGER DEFAULT 2,
        parking VARCHAR(50) NOT NULL,
        furnishing VARCHAR(50) NOT NULL,
        monthly_rent INTEGER NOT NULL,
        advance_amount INTEGER NOT NULL,
        preferred_tenant VARCHAR(50) DEFAULT 'Any',
        available_from DATE,
        is_verified BOOLEAN DEFAULT 1,
        is_featured BOOLEAN DEFAULT 0,
        status VARCHAR(20) DEFAULT 'Available',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE
    );
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS property_images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER NOT NULL,
        image_url VARCHAR(255) NOT NULL,
        is_primary BOOLEAN DEFAULT 0,
        FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
    );
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS amenities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(100) UNIQUE NOT NULL,
        icon VARCHAR(50) NOT NULL
    );
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS property_amenities (
        property_id INTEGER NOT NULL,
        amenity_id INTEGER NOT NULL,
        PRIMARY KEY (property_id, amenity_id),
        FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
        FOREIGN KEY (amenity_id) REFERENCES amenities(id) ON DELETE CASCADE
    );
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS favourites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        property_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (user_id, property_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
    );
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS enquiries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER NOT NULL,
        tenant_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        preferred_move_in DATE,
        phone VARCHAR(20),
        status VARCHAR(30) DEFAULT 'Pending',
        owner_reply TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
        FOREIGN KEY (tenant_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    conn.commit()

    # Check if already seeded
    user_count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if user_count > 0:
        conn.close()
        return

    print("[RentMatch] Seeding initial Tumakuru localities, users, and properties...")

    # 1. Localities
    locations = [
        ("SS Puram", "Prime residential and educational area in Tumakuru, close to markets.", "572102"),
        ("Kyathsandra", "Vibrant area near Siddaganga Math and National Highway 48.", "572104"),
        ("SIT Extension", "Adjacent to Siddaganga Institute of Technology campus.", "572103"),
        ("Batwadi", "Close to KSRTC Bus Stand and Railway Station with high connectivity.", "572101"),
        ("Ashok Nagar", "Quiet, green, upscale residential layout preferred by families.", "572102"),
        ("Sapthagiri Extension", "Modern residential layout with newly constructed independent houses.", "572105"),
        ("Melekote", "Fast-growing residential zone near Ring Road with standalone homes.", "572105"),
        ("Gubbi Gate", "Historical commercial and residential neighborhood.", "572101"),
        ("Mandipet", "Bustling central commercial and trading hub with compact apartments.", "572101"),
        ("Belagumba", "Peaceful locality with scenic greenery and pocket-friendly homes.", "572103")
    ]
    c.executemany("INSERT INTO locations (name, description, pincode) VALUES (?, ?, ?)", locations)

    # 2. Amenities
    amenities = [
        ("24/7 Kaveri & Borewell Water", "fa-faucet-drip"),
        ("Covered Two-Wheeler Parking", "fa-motorcycle"),
        ("Covered Car Parking", "fa-car"),
        ("Power Backup / Inverter", "fa-bolt"),
        ("Gated Security & CCTV", "fa-shield-halved"),
        ("Solar Water Heater", "fa-sun"),
        ("High-Speed Wi-Fi Ready", "fa-wifi"),
        ("Lift / Elevator", "fa-elevator"),
        ("Balcony with Scenic View", "fa-tree"),
        ("Pet Friendly", "fa-paw"),
        ("Modular Kitchen & Chimney", "fa-kitchen-set"),
        ("Wardrobes & Storage Cabinets", "fa-boxes-stacked")
    ]
    c.executemany("INSERT INTO amenities (name, icon) VALUES (?, ?)", amenities)

    # 3. Users (password: password123)
    pwd = generate_password_hash("password123")
    users = [
        ("RentMatch Administrator", "admin@rentmatch.com", pwd, "9880123450", "admin", 1),
        ("Suresh Gowda", "suresh.gowda@gmail.com", pwd, "9845112233", "owner", 1),
        ("Lakshmi Devi", "lakshmi.devi@gmail.com", pwd, "9448223344", "owner", 1),
        ("Prof. Ramachandraiah", "ramachandra.sit@gmail.com", pwd, "9900334455", "owner", 1),
        ("Manjunath Swamy", "manju.swamy@yahoo.com", pwd, "9844556677", "owner", 1),
        ("Rohan Sharma (Student)", "rohan.student@gmail.com", pwd, "8971001122", "tenant", 1),
        ("Dr. Ananya Rao", "ananya.rao@gmail.com", pwd, "8861223344", "tenant", 1)
    ]
    c.executemany("INSERT INTO users (name, email, password_hash, phone, role, is_active) VALUES (?, ?, ?, ?, ?, ?)", users)
    conn.commit()

    loc_map = {r['name']: r['id'] for r in c.execute("SELECT id, name FROM locations").fetchall()}
    user_map = {r['email']: r['id'] for r in c.execute("SELECT id, email FROM users").fetchall()}
    amen_map = {r['name']: r['id'] for r in c.execute("SELECT id, name FROM amenities").fetchall()}

    # 4. Realistic Houses in Tumakuru
    props = [
        {
            "owner": "suresh.gowda@gmail.com",
            "title": "Spacious 2 BHK Independent Ground Floor House near SS Puram Main Road",
            "desc": "Well-ventilated ground floor house located in a serene residential cross near SS Puram Main Road. Features spacious pooja room, modular kitchen, large hall, two bedrooms with attached western bathrooms, and reliable 24/7 Kaveri water supply. Ideal for families and working professionals.",
            "type": "Independent House", "loc": "SS Puram", "addr": "No. 42, 5th Cross, SS Puram Main Road, Near Sri Krishna Temple",
            "land": "Near Sri Krishna Temple & SS Puram Circle", "bhk": "2 BHK", "bhk_num": 2.0, "sqft": 1150, "bed": 2, "bath": 2, "balc": 1,
            "floor": 0, "tot_floor": 2, "park": "Car & Bike", "furn": "Semi-Furnished", "rent": 12500, "adv": 80000, "tenant": "Family",
            "feat": 1, "img": "https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=800&q=80",
            "amens": ["24/7 Kaveri & Borewell Water", "Covered Car Parking", "Wardrobes & Storage Cabinets", "Solar Water Heater"]
        },
        {
            "owner": "ramachandra.sit@gmail.com",
            "title": "Comfortable 1 BHK Apartment for Students / Bachelors near SIT Main Gate",
            "desc": "Very convenient 1 BHK flat situated within 3 minutes walking distance to Siddaganga Institute of Technology (SIT campus). Comes with study desk, wardrobes, high-speed Wi-Fi readiness, geyser, and dedicated two-wheeler parking. Safe and disciplined environment.",
            "type": "Apartment", "loc": "SIT Extension", "addr": "Flat 203, Vidya Nivas, 2nd Main, SIT Extension",
            "land": "Opposite SIT Girls Hostel Gate", "bhk": "1 BHK", "bhk_num": 1.0, "sqft": 580, "bed": 1, "bath": 1, "balc": 1,
            "floor": 2, "tot_floor": 4, "park": "Bike Only", "furn": "Semi-Furnished", "rent": 6500, "adv": 35000, "tenant": "Students",
            "feat": 1, "img": "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?auto=format&fit=crop&w=800&q=80",
            "amens": ["24/7 Kaveri & Borewell Water", "Covered Two-Wheeler Parking", "High-Speed Wi-Fi Ready", "Solar Water Heater", "Gated Security & CCTV"]
        },
        {
            "owner": "lakshmi.devi@gmail.com",
            "title": "Modern 3 BHK Luxury Flat in Gated Society, Ashok Nagar",
            "desc": "Premium 3 BHK apartment featuring designer woodwork, granite flooring, spacious master bedroom with balcony, modular chimney kitchen, and 100% power backup. Located in quiet Ashok Nagar with lift access, dedicated car parking, and 24-hour security.",
            "type": "Apartment", "loc": "Ashok Nagar", "addr": "A-304, Green Palms Residency, Ashok Nagar 3rd Cross",
            "land": "Near Rotary Children Park", "bhk": "3 BHK", "bhk_num": 3.0, "sqft": 1650, "bed": 3, "bath": 3, "balc": 2,
            "floor": 3, "tot_floor": 5, "park": "Covered Car", "furn": "Fully Furnished", "rent": 21000, "adv": 150000, "tenant": "Family",
            "feat": 1, "img": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=800&q=80",
            "amens": ["24/7 Kaveri & Borewell Water", "Covered Car Parking", "Power Backup / Inverter", "Lift / Elevator", "Gated Security & CCTV", "Modular Kitchen & Chimney"]
        },
        {
            "owner": "manju.swamy@yahoo.com",
            "title": "Pocket-Friendly 1 RK Single Room for Working Professionals in Batwadi",
            "desc": "Compact and clean 1 Room-Kitchen (1 RK) unit near Batwadi Circle. Walking distance to Tumakuru KSRTC bus stand and railway station. Perfect for single professionals or job seekers looking for low rent and easy commute.",
            "type": "Studio Room", "loc": "Batwadi", "addr": "Door No 18, Opp. Vinayaka Hospital, Batwadi",
            "land": "Near Tumkur Bus Stand Ring Road", "bhk": "1 RK", "bhk_num": 0.5, "sqft": 320, "bed": 1, "bath": 1, "balc": 0,
            "floor": 1, "tot_floor": 3, "park": "Bike Only", "furn": "Unfurnished", "rent": 4200, "adv": 25000, "tenant": "Bachelors",
            "feat": 0, "img": "https://images.unsplash.com/photo-1598928506311-c55ded91a20c?auto=format&fit=crop&w=800&q=80",
            "amens": ["24/7 Kaveri & Borewell Water", "Covered Two-Wheeler Parking"]
        },
        {
            "owner": "suresh.gowda@gmail.com",
            "title": "Independent Duplex 3 BHK Villa with Private Garden in Melekote",
            "desc": "Spacious duplex villa situated in a quiet residential layout at Melekote. Offers private open terrace, garden area, car porch, marble flooring, and ample natural light. Very close to the Tumkur Outer Ring Road for easy Bangalore highway access.",
            "type": "Villa", "loc": "Melekote", "addr": "Plot 112, Sri Siddharoodha Layout, Melekote Ring Road",
            "land": "Behind Melekote Government School", "bhk": "3 BHK", "bhk_num": 3.0, "sqft": 1950, "bed": 3, "bath": 3, "balc": 2,
            "floor": 0, "tot_floor": 2, "park": "Car & Bike", "furn": "Semi-Furnished", "rent": 18500, "adv": 120000, "tenant": "Family",
            "feat": 1, "img": "https://images.unsplash.com/photo-1613977257363-707ba9348227?auto=format&fit=crop&w=800&q=80",
            "amens": ["24/7 Kaveri & Borewell Water", "Covered Car Parking", "Solar Water Heater", "Balcony with Scenic View", "Pet Friendly"]
        },
        {
            "owner": "lakshmi.devi@gmail.com",
            "title": "Newly Built 2 BHK First Floor House in Sapthagiri Extension",
            "desc": "Freshly constructed 2 BHK unit on the 1st floor with modern false ceiling, LED fixtures, modular kitchen, and two western bathrooms. 100% Vaastu compliant with East-facing entrance. Peaceful neighborhood with nearby parks.",
            "type": "Independent House", "loc": "Sapthagiri Extension", "addr": "House No 55, 4th Cross, Sapthagiri Extension West",
            "land": "Near Sapthagiri Ganapathi Temple", "bhk": "2 BHK", "bhk_num": 2.0, "sqft": 1050, "bed": 2, "bath": 2, "balc": 1,
            "floor": 1, "tot_floor": 2, "park": "Car & Bike", "furn": "Semi-Furnished", "rent": 11000, "adv": 75000, "tenant": "Any",
            "feat": 0, "img": "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=800&q=80",
            "amens": ["24/7 Kaveri & Borewell Water", "Covered Two-Wheeler Parking", "Modular Kitchen & Chimney", "Solar Water Heater"]
        },
        {
            "owner": "ramachandra.sit@gmail.com",
            "title": "Affordable 2 BHK House near Siddaganga Math, Kyathsandra",
            "desc": "Quiet independent house with 2 bedrooms, spacious hall, separate dining, and utility area. Located in Kyathsandra with fast access to NH-48 and Siddaganga Math. Abundant borewell water supply and quiet green surroundings.",
            "type": "Independent House", "loc": "Kyathsandra", "addr": "Shree Nilaya, Old Bangalore Road, Kyathsandra",
            "land": "Near Siddaganga Math Arch", "bhk": "2 BHK", "bhk_num": 2.0, "sqft": 980, "bed": 2, "bath": 1, "balc": 1,
            "floor": 1, "tot_floor": 2, "park": "Bike Only", "furn": "Unfurnished", "rent": 8500, "adv": 50000, "tenant": "Family",
            "feat": 0, "img": "https://images.unsplash.com/photo-1570129477492-45c003ed2be1?auto=format&fit=crop&w=800&q=80",
            "amens": ["24/7 Kaveri & Borewell Water", "Covered Two-Wheeler Parking", "Solar Water Heater"]
        },
        {
            "owner": "manju.swamy@yahoo.com",
            "title": "Well-Maintained 2 BHK Central Apartment in Mandipet Market Area",
            "desc": "Prime commercial and residential center. 2 BHK flat on the second floor of a commercial-residential complex. Step right out into city shopping, grocery markets, and Tumakuru Town Police Station road.",
            "type": "Apartment", "loc": "Mandipet", "addr": "301, Sri Manjunatha Complex, Mandipet Main Road",
            "land": "Above Canara Bank Mandipet", "bhk": "2 BHK", "bhk_num": 2.0, "sqft": 900, "bed": 2, "bath": 2, "balc": 1,
            "floor": 2, "tot_floor": 3, "park": "Bike Only", "furn": "Semi-Furnished", "rent": 10000, "adv": 60000, "tenant": "Any",
            "feat": 0, "img": "https://images.unsplash.com/photo-1502005229762-ee1b2da97e06?auto=format&fit=crop&w=800&q=80",
            "amens": ["24/7 Kaveri & Borewell Water", "Covered Two-Wheeler Parking", "Wardrobes & Storage Cabinets"]
        },
        {
            "owner": "suresh.gowda@gmail.com",
            "title": "Serene 1 BHK House with Terrace Access in Belagumba Greenery",
            "desc": "Clean and budget-friendly 1 BHK home in peaceful Belagumba. Ideal for retirees, nature lovers, or small families seeking fresh air away from traffic noise. Terrace access with panoramic hills view.",
            "type": "Independent House", "loc": "Belagumba", "addr": "No 88, Belagumba Village Road, Near Lake View",
            "land": "Near Belagumba Gram Panchayat Office", "bhk": "1 BHK", "bhk_num": 1.0, "sqft": 650, "bed": 1, "bath": 1, "balc": 1,
            "floor": 1, "tot_floor": 1, "park": "Car & Bike", "furn": "Unfurnished", "rent": 5500, "adv": 30000, "tenant": "Any",
            "feat": 0, "img": "https://images.unsplash.com/photo-1588880331179-bc9b93a8cb5e?auto=format&fit=crop&w=800&q=80",
            "amens": ["24/7 Kaveri & Borewell Water", "Covered Two-Wheeler Parking", "Pet Friendly", "Balcony with Scenic View"]
        }
    ]

    for p in props:
        oid = user_map[p["owner"]]
        lid = loc_map[p["loc"]]
        c.execute("""
            INSERT INTO properties (
                owner_id, title, description, property_type, location_id, address, landmark,
                bhk, bhk_num, size_sqft, bedrooms, bathrooms, balconies, floor_num, total_floors,
                parking, furnishing, monthly_rent, advance_amount, preferred_tenant,
                is_verified, is_featured, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 'Available')
        """, (oid, p["title"], p["desc"], p["type"], lid, p["addr"], p["land"], p["bhk"], p["bhk_num"],
              p["sqft"], p["bed"], p["bath"], p["balc"], p["floor"], p["tot_floor"], p["park"], p["furn"],
              p["rent"], p["adv"], p["tenant"], p["feat"]))
        pid = c.lastrowid
        c.execute("INSERT INTO property_images (property_id, image_url, is_primary) VALUES (?, ?, 1)", (pid, p["img"]))
        for aname in p["amens"]:
            if aname in amen_map:
                c.execute("INSERT INTO property_amenities (property_id, amenity_id) VALUES (?, ?)", (pid, amen_map[aname]))

    # Seed an inquiry from Rohan (Student) to SIT house
    rohan_id = user_map["rohan.student@gmail.com"]
    p_sit = c.execute("SELECT id FROM properties WHERE title LIKE '%SIT Main Gate%'").fetchone()[0]
    p_ssp = c.execute("SELECT id FROM properties WHERE title LIKE '%SS Puram Main Road%'").fetchone()[0]
    c.execute("INSERT INTO favourites (user_id, property_id) VALUES (?, ?)", (rohan_id, p_sit))
    c.execute("INSERT INTO favourites (user_id, property_id) VALUES (?, ?)", (rohan_id, p_ssp))
    c.execute("""
        INSERT INTO enquiries (property_id, tenant_id, message, preferred_move_in, phone, status, owner_reply)
        VALUES (?, ?, ?, ?, ?, 'Contacted', ?)
    """, (p_sit, rohan_id, "Hello Sir, I am a B.Sc Data Science student at SIT/Tumkur University. Is this flat available for visit this Saturday?",
          "2026-10-15", "8971001122", "Yes Rohan, please visit between 2 PM and 5 PM. Call 9900334455 upon arrival."))

    conn.commit()
    conn.close()
    print("[RentMatch] Seed completed successfully.")

# ========================================================================================
# DATA ACCESS & MODELS
# ========================================================================================

def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    conn.close()
    
    if not u or not u['is_active']:
        session.clear()
        return None
    return dict(u)

@app.context_processor
def inject_global_data():
    conn = get_db()
    locs = [dict(r) for r in conn.execute("SELECT * FROM locations ORDER BY name ASC").fetchall()]
    conn.close()
    return {'current_user': current_user(), 'all_locations': locs}

def get_all_properties(filters=None, limit=None):
    conn = get_db()
    query = """
        SELECT p.*, l.name AS location_name, l.pincode, u.name AS owner_name
        FROM properties p
        JOIN locations l ON p.location_id = l.id
        JOIN users u ON p.owner_id = u.id
        WHERE p.status = 'Available'
    """
    params = []
    if filters:
        if filters.get('location_id'):
            query += " AND p.location_id = ?"
            params.append(filters['location_id'])
        if filters.get('bhk') and filters['bhk'] != 'Any':
            query += " AND p.bhk = ?"
            params.append(filters['bhk'])
        if filters.get('property_type') and filters['property_type'] != 'Any':
            query += " AND p.property_type = ?"
            params.append(filters['property_type'])
        if filters.get('furnishing') and filters['furnishing'] != 'Any':
            query += " AND p.furnishing = ?"
            params.append(filters['furnishing'])
        if filters.get('parking') and filters['parking'] != 'Any':
            query += " AND p.parking LIKE ?"
            params.append(f"%{filters['parking']}%")
        if filters.get('tenant_type') and filters['tenant_type'] != 'Any':
            query += " AND (p.preferred_tenant = ? OR p.preferred_tenant = 'Any')"
            params.append(filters['tenant_type'])
        if filters.get('min_rent'):
            query += " AND p.monthly_rent >= ?"
            params.append(filters['min_rent'])
        if filters.get('max_rent'):
            query += " AND p.monthly_rent <= ?"
            params.append(filters['max_rent'])
        if filters.get('search_keyword'):
            kw = f"%{filters['search_keyword'].strip()}%"
            query += " AND (p.title LIKE ? OR p.description LIKE ? OR l.name LIKE ? OR p.address LIKE ?)"
            params.extend([kw, kw, kw, kw])

    sort_by = filters.get('sort_by') if filters else None
    if sort_by == 'price_low':
        query += " ORDER BY p.monthly_rent ASC"
    elif sort_by == 'price_high':
        query += " ORDER BY p.monthly_rent DESC"
    elif sort_by == 'size_large':
        query += " ORDER BY p.size_sqft DESC"
    else:
        query += " ORDER BY p.is_featured DESC, p.id DESC"

    if limit:
        query += f" LIMIT {int(limit)}"

    rows = conn.execute(query, params).fetchall()
    properties = []
    for r in rows:
        p_dict = dict(r)
        img = conn.execute("SELECT image_url FROM property_images WHERE property_id = ? ORDER BY is_primary DESC LIMIT 1", (p_dict['id'],)).fetchone()
        p_dict['primary_image'] = img['image_url'] if img else 'https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=800&q=80'
        pa = conn.execute("""
            SELECT a.id, a.name, a.icon FROM amenities a
            JOIN property_amenities m ON a.id = m.amenity_id WHERE m.property_id = ?
        """, (p_dict['id'],)).fetchall()
        p_dict['amenities'] = [dict(a) for a in pa]
        p_dict['amenity_ids'] = [a['id'] for a in pa]
        properties.append(p_dict)
    conn.close()
    return properties

def get_property_by_id(pid):
    conn = get_db()
    prop = conn.execute("""
        SELECT p.*, l.name AS location_name, l.pincode, u.name AS owner_name, u.phone AS owner_phone, u.email AS owner_email
        FROM properties p
        JOIN locations l ON p.location_id = l.id
        JOIN users u ON p.owner_id = u.id
        WHERE p.id = ?
    """, (pid,)).fetchone()
    if not prop:
        conn.close()
        return None
    p_dict = dict(prop)
    imgs = conn.execute("SELECT * FROM property_images WHERE property_id = ?", (pid,)).fetchall()
    p_dict['images'] = [dict(img) for img in imgs]
    p_dict['primary_image'] = p_dict['images'][0]['image_url'] if p_dict['images'] else 'https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=800&q=80'
    amenities = conn.execute("""
        SELECT a.* FROM amenities a JOIN property_amenities pa ON a.id = pa.amenity_id WHERE pa.property_id = ?
    """, (pid,)).fetchall()
    p_dict['amenities'] = [dict(a) for a in amenities]
    p_dict['amenity_ids'] = [a['id'] for a in p_dict['amenities']]
    conn.close()
    return p_dict

# ========================================================================================
# DATA SCIENCE RECOMMENDATION ENGINE (COSINE SIMILARITY & MULTI-ATTRIBUTE UTILITY)
# ========================================================================================

def pure_cosine_similarity(vec_a, vec_b):
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

def bhk_to_num(bhk_str):
    s = str(bhk_str or '').upper()
    if 'RK' in s: return 0.5
    if '1' in s: return 1.0
    if '2' in s: return 2.0
    if '3' in s: return 3.0
    if '4' in s or '5' in s: return 4.0
    return 2.0

def recommend_properties(properties, preferences, all_amenities):
    if not properties:
        return []

    pref_loc_id = preferences.get('location_id')
    pref_bhk = preferences.get('bhk')
    pref_bhk_num = bhk_to_num(pref_bhk) if pref_bhk else 2.0
    max_rent = float(preferences.get('max_rent') or 0)
    min_sqft = float(preferences.get('min_sqft') or 0)
    pref_furn = preferences.get('furnishing')
    pref_park = preferences.get('parking')
    pref_tenant = preferences.get('tenant_type')
    pref_amenities = preferences.get('amenities', [])
    all_amen_ids = [a['id'] for a in all_amenities] if all_amenities else []

    scored = []
    for prop in properties:
        p = dict(prop)
        reasons = []

        # 1. Location (Weight: 25%)
        if pref_loc_id and str(pref_loc_id) not in ('', 'Any'):
            if int(p.get('location_id', -1)) == int(pref_loc_id):
                loc_score = 1.0
                reasons.append(f"Located in requested area: {p.get('location_name')}")
            else:
                loc_score = 0.35
        else:
            loc_score = 1.0

        # 2. Budget (Weight: 25%)
        rent = float(p.get('monthly_rent', 0))
        if max_rent > 0:
            if rent <= max_rent:
                budget_score = max(0.8, min(1.0, 1.0 - (rent / max_rent * 0.1)))
                reasons.append(f"Within budget: ₹{int(rent):,}/mo (Max: ₹{int(max_rent):,})")
            else:
                over = (rent - max_rent) / max_rent
                budget_score = max(0.05, min(0.79, 1.0 - (over * 2.0)))
                reasons.append(f"Slightly above budget (₹{int(rent):,}/mo)")
        else:
            budget_score = 1.0

        # 3. BHK & Space (Weight: 20%)
        bhk_diff = abs(p.get('bhk_num', 2.0) - pref_bhk_num)
        if bhk_diff == 0:
            bhk_score = 1.0
            reasons.append(f"Exact {p.get('bhk')} match")
        elif bhk_diff <= 0.5: bhk_score = 0.85
        elif bhk_diff <= 1.0: bhk_score = 0.60
        else: bhk_score = 0.25

        sqft = float(p.get('size_sqft', 0))
        area_score = 1.0 if min_sqft <= 0 or sqft >= min_sqft else max(0.2, sqft / min_sqft)
        bhk_space = (0.7 * bhk_score) + (0.3 * area_score)

        # 4. Convenience (Weight: 15%)
        furn_score = 1.0 if not pref_furn or pref_furn == 'Any' or p.get('furnishing') == pref_furn else 0.6
        park_score = 1.0 if not pref_park or pref_park == 'Any' or p.get('parking') == pref_park else 0.5
        convenience = (0.5 * furn_score) + (0.5 * park_score)
        if pref_furn and pref_furn != 'Any' and p.get('furnishing') == pref_furn:
            reasons.append(f"{p.get('furnishing')} setup")

        # 5. Amenities Cosine Similarity (Weight: 15%)
        prop_amen_ids = p.get('amenity_ids', [])
        if pref_amenities and all_amen_ids:
            v_u = [1 if aid in pref_amenities else 0 for aid in all_amen_ids]
            v_p = [1 if aid in prop_amen_ids else 0 for aid in all_amen_ids]
            if HAS_SKLEARN:
                amen_sim = float(cosine_similarity([v_u], [v_p])[0][0])
            else:
                amen_sim = pure_cosine_similarity(v_u, v_p)
            match_count = sum(1 for aid in pref_amenities if aid in prop_amen_ids)
            if match_count > 0:
                reasons.append(f"Matches {match_count} requested amenities")
        else:
            amen_sim = 1.0

        # Weighted Total Score
        total = (
            (loc_score * 0.25) +
            (budget_score * 0.25) +
            (bhk_space * 0.20) +
            (convenience * 0.15) +
            (amen_sim * 0.15)
        ) * 100.0

        final_score = round(max(15.0, min(100.0, total)), 1)
        if final_score >= 85: bclass, btext = "success", "High Match"
        elif final_score >= 65: bclass, btext = "primary", "Good Match"
        elif final_score >= 50: bclass, btext = "warning", "Moderate Match"
        else: bclass, btext = "secondary", "Low Match"

        p['match_score'] = final_score
        p['badge_class'] = bclass
        p['badge_text'] = btext
        p['reasons'] = reasons[:4]
        p['subscores'] = {
            'Location': int(loc_score * 100),
            'Budget': int(budget_score * 100),
            'Space & BHK': int(bhk_space * 100),
            'Convenience': int(convenience * 100),
            'Amenities': int(amen_sim * 100)
        }
        scored.append(p)

    scored.sort(key=lambda x: x['match_score'], reverse=True)
    return scored

def find_similar_properties(target_id, all_properties, top_n=3):
    if len(all_properties) <= 1:
        return []
    target = next((p for p in all_properties if p['id'] == target_id), None)
    if not target:
        return []

    sim_list = []
    for p in all_properties:
        if p['id'] == target_id:
            continue
        # Cosine distance on numerical features [rent, sqft, bhk, bath]
        v1 = [target['monthly_rent']/1000.0, target['size_sqft']/100.0, target['bhk_num'], target['bathrooms']]
        v2 = [p['monthly_rent']/1000.0, p['size_sqft']/100.0, p['bhk_num'], p['bathrooms']]
        sim = pure_cosine_similarity(v1, v2)
        if p['location_id'] == target['location_id']:
            sim += 0.2
        sim_list.append((sim, p))

    sim_list.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in sim_list[:top_n]]

# ========================================================================================
# EMBEDDED JINJA2 TEMPLATES (ALL-IN-ONE)
# ========================================================================================

TEMPLATES = {
'base.html': """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}RentMatch – Smart Rental Finder | Tumakuru{% endblock %}</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        body { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #f8fafc; color: #334155; min-height: 100vh; display: flex; flex-direction: column; }
        main { flex: 1; }
        .navbar-brand { font-weight: 800; font-size: 1.35rem; color: #2563eb !important; }
        .brand-icon { background: linear-gradient(135deg, #2563eb, #0ea5e9); color: white; width: 36px; height: 36px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; margin-right: 8px; }
        .hero-section { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: white; padding: 4rem 0 3rem 0; }
        .property-card { background: #fff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; height: 100%; display: flex; flex-direction: column; transition: transform .2s, box-shadow .2s; }
        .property-card:hover { transform: translateY(-4px); box-shadow: 0 10px 20px -5px rgba(0,0,0,0.1); }
        .card-img-wrap { height: 200px; position: relative; background: #e2e8f0; overflow: hidden; }
        .card-img-wrap img { width: 100%; height: 100%; object-fit: cover; }
        .price-tag { position: absolute; bottom: 10px; left: 10px; background: rgba(15,23,42,0.85); color: #fff; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 1.05rem; }
        .fav-btn-badge { position: absolute; top: 10px; right: 10px; background: white; width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: none; cursor: pointer; color: #94a3b8; }
        .fav-btn-badge.active, .fav-btn-badge:hover { color: #ef4444; }
        .match-score-badge { position: absolute; top: 10px; left: 10px; background: #10b981; color: white; font-weight: 800; font-size: 0.8rem; padding: 4px 10px; border-radius: 20px; }
        .amenity-chip { background: #f1f5f9; border-radius: 8px; padding: 6px 12px; font-size: 0.85rem; display: inline-flex; align-items: center; gap: 6px; margin: 4px; }
        .locality-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 1.2rem; text-decoration: none; color: inherit; display: block; transition: all .2s; }
        .locality-card:hover { border-color: #2563eb; background: #f0f7ff; }
        .stat-card { background: #fff; border-radius: 12px; border: 1px solid #e2e8f0; padding: 1.25rem; display: flex; align-items: center; gap: 1rem; }
        .stat-icon { width: 48px; height: 48px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.4rem; }
        footer { background: #0f172a; color: #94a3b8; padding: 2.5rem 0 1.5rem 0; margin-top: auto; }
        footer a { color: #cbd5e1; text-decoration: none; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg bg-white border-bottom sticky-top py-2 shadow-sm">
        <div class="container">
            <a class="navbar-brand d-flex align-items-center" href="{{ url_for('index') }}">
                <div class="brand-icon"><i class="fa-solid fa-house-chimney-user"></i></div>
                <span>RentMatch</span>
                <span class="badge bg-primary-subtle text-primary border border-primary-subtle fs-6 py-0 px-2 fw-normal ms-2 d-none d-md-inline">Tumakuru</span>
            </a>
            <button class="navbar-toggler border-0" type="button" data-bs-toggle="collapse" data-bs-target="#navContent">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navContent">
                <ul class="navbar-nav me-auto mb-2 mb-lg-0 ms-lg-3">
                    <li class="nav-item"><a class="nav-link fw-semibold" href="{{ url_for('index') }}">Home</a></li>
                    <li class="nav-item"><a class="nav-link fw-semibold" href="{{ url_for('properties') }}">Explore Houses</a></li>
                    <li class="nav-item"><a class="nav-link fw-bold text-primary" href="{{ url_for('recommend') }}"><i class="fa-solid fa-wand-magic-sparkles text-warning me-1"></i> Smart Match Recommender</a></li>
                </ul>
                <ul class="navbar-nav align-items-lg-center">
                    {% if current_user %}
                        {% if current_user.role in ['owner', 'admin'] %}
                            <li class="nav-item me-2"><a href="{{ url_for('new_property') }}" class="btn btn-sm btn-outline-primary rounded-pill px-3"><i class="fa-solid fa-plus me-1"></i> Post House</a></li>
                        {% endif %}
                        <li class="nav-item dropdown">
                            <a class="nav-link dropdown-toggle fw-semibold" href="#" role="button" data-bs-toggle="dropdown">
                                <i class="fa-solid fa-circle-user text-primary me-1"></i> {{ current_user.name.split()[0] }} ({{ current_user.role }})
                            </a>
                            <ul class="dropdown-menu dropdown-menu-end shadow border-0">
                                <li><a class="dropdown-item" href="{{ url_for('dashboard') }}"><i class="fa-solid fa-gauge me-2"></i> Dashboard</a></li>
                                <li><hr class="dropdown-divider"></li>
                                <li><a class="dropdown-item text-danger" href="{{ url_for('logout') }}"><i class="fa-solid fa-arrow-right-from-bracket me-2"></i> Logout</a></li>
                            </ul>
                        </li>
                    {% else %}
                        <li class="nav-item me-2"><a class="nav-link fw-semibold" href="{{ url_for('login') }}">Sign In</a></li>
                        <li class="nav-item"><a class="btn btn-primary rounded-pill px-4 fw-semibold" href="{{ url_for('register') }}">Register Free</a></li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </nav>

    <div class="container mt-3">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show border-0 shadow-sm" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
    </div>

    <main>{% block content %}{% endblock %}</main>

    <footer>
        <div class="container">
            <div class="row g-4 mb-3">
                <div class="col-md-6">
                    <h5 class="text-white fw-bold"><i class="fa-solid fa-house-chimney-user text-primary me-2"></i>RentMatch – Smart Rental Finder</h5>
                    <p class="small text-secondary mb-1">Centralized rental discovery and requirement-based recommendation system for Tumakuru, Karnataka.</p>
                    <span class="small text-muted">B.Sc. Data Science Final Year Project &bull; Python Flask &bull; Scikit-Learn Cosine Similarity</span>
                </div>
                <div class="col-md-3">
                    <h6 class="text-white fw-bold mb-2">Key Areas in Tumakuru</h6>
                    <ul class="list-unstyled small">
                        <li><a href="{{ url_for('properties', location_id=1) }}">SS Puram</a></li>
                        <li><a href="{{ url_for('properties', location_id=3) }}">SIT Extension</a></li>
                        <li><a href="{{ url_for('properties', location_id=2) }}">Kyathsandra</a></li>
                        <li><a href="{{ url_for('properties', location_id=4) }}">Batwadi Bus Stand</a></li>
                    </ul>
                </div>
                <div class="col-md-3">
                    <h6 class="text-white fw-bold mb-2">Demo Roles</h6>
                    <span class="small text-secondary d-block">Admin: admin@rentmatch.com</span>
                    <span class="small text-secondary d-block">Owner: suresh.gowda@gmail.com</span>
                    <span class="small text-secondary d-block">Tenant: rohan.student@gmail.com</span>
                    <span class="small text-info d-block mt-1">Password for all: password123</span>
                </div>
            </div>
            <hr class="border-secondary border-opacity-25 my-3">
            <div class="text-center small text-secondary">&copy; 2026 RentMatch Tumakuru &bull; Single-File Standalone Edition</div>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
    document.querySelectorAll('.fav-toggle-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault(); e.stopPropagation();
            const pid = btn.getAttribute('data-property-id');
            const res = await fetch('/api/favourite/toggle', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({property_id: pid})
            });
            if (res.status === 401) { window.location.href = '/login'; return; }
            const data = await res.json();
            if (data.success) {
                btn.classList.toggle('active', data.is_saved);
                const icon = btn.querySelector('i');
                if (data.is_saved) { icon.className = 'fa-solid fa-heart text-danger'; }
                else { icon.className = 'fa-regular fa-heart'; }
            }
        });
    });
    </script>
</body>
</html>""",

'index.html': """{% extends 'base.html' %}
{% block content %}
<section class="hero-section">
    <div class="container">
        <div class="row align-items-center g-4">
            <div class="col-lg-7">
                <span class="badge bg-primary px-3 py-2 rounded-pill mb-3"><i class="fa-solid fa-sparkles text-warning me-1"></i> Data-Driven Recommender</span>
                <h1 class="display-5 fw-bold mb-3">Find Your Ideal Rental House in <span class="text-primary text-decoration-underline">Tumakuru</span></h1>
                <p class="lead text-secondary mb-4">Discover verified houses across SS Puram, SIT, Kyathsandra, Batwadi, and Ashok Nagar. Match houses using your exact budget and living preferences.</p>
                <div class="d-flex flex-wrap gap-3">
                    <a href="{{ url_for('recommend') }}" class="btn btn-warning text-dark fw-bold rounded-pill px-4 py-2"><i class="fa-solid fa-wand-magic-sparkles me-2"></i> Launch Smart Match Wizard</a>
                    <a href="{{ url_for('properties') }}" class="btn btn-outline-light rounded-pill px-4 py-2">Explore All Houses</a>
                </div>
            </div>
            <div class="col-lg-5">
                <div class="bg-white p-4 rounded-4 shadow text-dark">
                    <h5 class="fw-bold mb-3"><i class="fa-solid fa-magnifying-glass text-primary me-2"></i> Quick Search</h5>
                    <form action="{{ url_for('properties') }}" method="GET">
                        <div class="mb-3">
                            <label class="form-label small fw-bold text-muted">Locality in Tumakuru</label>
                            <select name="location_id" class="form-select">
                                <option value="">All Tumakuru Areas</option>
                                {% for loc in all_locations %}<option value="{{ loc.id }}">{{ loc.name }}</option>{% endfor %}
                            </select>
                        </div>
                        <div class="row g-2 mb-3">
                            <div class="col-6">
                                <label class="form-label small fw-bold text-muted">BHK Config</label>
                                <select name="bhk" class="form-select">
                                    <option value="Any">Any BHK</option>
                                    <option value="1 RK">1 RK</option>
                                    <option value="1 BHK">1 BHK</option>
                                    <option value="2 BHK">2 BHK</option>
                                    <option value="3 BHK">3 BHK</option>
                                </select>
                            </div>
                            <div class="col-6">
                                <label class="form-label small fw-bold text-muted">Max Rent</label>
                                <select name="max_rent" class="form-select">
                                    <option value="">Any Budget</option>
                                    <option value="7000">Up to ₹7,000</option>
                                    <option value="12000">Up to ₹12,000</option>
                                    <option value="16000">Up to ₹16,000</option>
                                    <option value="25000">Up to ₹25,000</option>
                                </select>
                            </div>
                        </div>
                        <button type="submit" class="btn btn-primary w-100 fw-bold py-2 rounded-3">Search Houses</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
</section>

<section class="py-5">
    <div class="container">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h3 class="fw-bold mb-1">Featured Rental Houses</h3>
                <p class="text-muted small mb-0">Verified properties in Tumakuru ready for immediate move-in.</p>
            </div>
            <a href="{{ url_for('properties') }}" class="btn btn-outline-primary rounded-pill px-4">View All</a>
        </div>
        <div class="row g-4">
            {% for prop in properties %}
                <div class="col-md-6 col-lg-4">
                    <div class="property-card">
                        <div class="card-img-wrap">
                            <img src="{{ prop.primary_image }}" alt="{{ prop.title }}" onerror="this.src='https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=800&q=80'">
                            <div class="price-tag">₹{{ "{:,}".format(prop.monthly_rent) }}<small>/mo</small></div>
                            <button class="fav-btn-badge fav-toggle-btn" data-property-id="{{ prop.id }}"><i class="fa-regular fa-heart"></i></button>
                        </div>
                        <div class="p-3 d-flex flex-column justify-content-between flex-grow-1">
                            <div>
                                <div class="d-flex gap-2 mb-2">
                                    <span class="badge bg-primary-subtle text-primary">{{ prop.bhk }}</span>
                                    <span class="badge bg-secondary-subtle text-secondary">{{ prop.property_type }}</span>
                                    <span class="small text-muted ms-auto"><i class="fa-solid fa-location-dot text-danger me-1"></i>{{ prop.location_name }}</span>
                                </div>
                                <h6 class="fw-bold text-dark text-truncate" title="{{ prop.title }}"><a href="{{ url_for('property_detail', property_id=prop.id) }}" class="text-decoration-none text-dark">{{ prop.title }}</a></h6>
                                <p class="text-muted small mb-2" style="height:36px; overflow:hidden;">{{ prop.description }}</p>
                                <div class="small text-muted mb-2">{{ prop.size_sqft }} sq.ft &bull; {{ prop.furnishing }} &bull; {{ prop.parking }}</div>
                            </div>
                            <div class="d-flex justify-content-between align-items-center pt-2 border-top mt-2">
                                <span class="small text-muted">Adv: ₹{{ "{:,}".format(prop.advance_amount) }}</span>
                                <a href="{{ url_for('property_detail', property_id=prop.id) }}" class="btn btn-sm btn-primary rounded-pill px-3">View Details</a>
                            </div>
                        </div>
                    </div>
                </div>
            {% endfor %}
        </div>
    </div>
</section>

<section class="py-5 bg-white border-top">
    <div class="container">
        <h4 class="fw-bold mb-3 text-center">Tumakuru Localities</h4>
        <div class="row g-3">
            {% for loc in all_locations %}
                <div class="col-md-3 col-sm-6">
                    <a href="{{ url_for('properties', location_id=loc.id) }}" class="locality-card">
                        <h6 class="fw-bold mb-1">{{ loc.name }}</h6>
                        <span class="small text-muted">{{ loc.description }}</span>
                    </a>
                </div>
            {% endfor %}
        </div>
    </div>
</section>
{% endblock %}""",

'properties.html': """{% extends 'base.html' %}
{% block content %}
<div class="container py-4">
    <div class="row g-4">
        <div class="col-lg-3">
            <div class="bg-white p-3 rounded-3 shadow-sm border sticky-top" style="top: 80px;">
                <div class="d-flex justify-content-between align-items-center mb-3 border-bottom pb-2">
                    <h6 class="fw-bold mb-0"><i class="fa-solid fa-sliders text-primary me-2"></i>Filters</h6>
                    <a href="{{ url_for('properties') }}" class="small text-danger text-decoration-none">Reset</a>
                </div>
                <form action="{{ url_for('properties') }}" method="GET">
                    <div class="mb-3">
                        <label class="form-label small fw-bold">Search</label>
                        <input type="text" name="q" class="form-control form-control-sm" placeholder="Area, landmark..." value="{{ filters.search_keyword or '' }}">
                    </div>
                    <div class="mb-3">
                        <label class="form-label small fw-bold">Locality</label>
                        <select name="location_id" class="form-select form-select-sm">
                            <option value="">All Areas</option>
                            {% for loc in all_locations %}
                                <option value="{{ loc.id }}" {% if filters.location_id == loc.id %}selected{% endif %}>{{ loc.name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="mb-3">
                        <label class="form-label small fw-bold">BHK</label>
                        <select name="bhk" class="form-select form-select-sm">
                            <option value="Any">Any BHK</option>
                            <option value="1 RK" {% if filters.bhk == '1 RK' %}selected{% endif %}>1 RK</option>
                            <option value="1 BHK" {% if filters.bhk == '1 BHK' %}selected{% endif %}>1 BHK</option>
                            <option value="2 BHK" {% if filters.bhk == '2 BHK' %}selected{% endif %}>2 BHK</option>
                            <option value="3 BHK" {% if filters.bhk == '3 BHK' %}selected{% endif %}>3 BHK</option>
                        </select>
                    </div>
                    <div class="mb-3">
                        <label class="form-label small fw-bold">Max Monthly Rent (₹)</label>
                        <input type="number" name="max_rent" class="form-control form-control-sm" placeholder="E.g. 15000" value="{{ filters.max_rent or '' }}">
                    </div>
                    <div class="mb-3">
                        <label class="form-label small fw-bold">Furnishing</label>
                        <select name="furnishing" class="form-select form-select-sm">
                            <option value="Any">Any</option>
                            <option value="Unfurnished" {% if filters.furnishing == 'Unfurnished' %}selected{% endif %}>Unfurnished</option>
                            <option value="Semi-Furnished" {% if filters.furnishing == 'Semi-Furnished' %}selected{% endif %}>Semi-Furnished</option>
                            <option value="Fully Furnished" {% if filters.furnishing == 'Fully Furnished' %}selected{% endif %}>Fully Furnished</option>
                        </select>
                    </div>
                    <button type="submit" class="btn btn-primary btn-sm w-100 fw-bold">Apply Filters</button>
                </form>
            </div>
        </div>

        <div class="col-lg-9">
            <div class="d-flex justify-content-between align-items-center bg-white p-3 rounded-3 shadow-sm mb-3 border">
                <span class="fw-bold">{{ total_count }} Houses Available in Tumakuru</span>
                <a href="{{ url_for('recommend') }}" class="btn btn-sm btn-warning text-dark fw-bold rounded-pill"><i class="fa-solid fa-wand-magic-sparkles me-1"></i> Smart Match Wizard</a>
            </div>

            <div class="row g-3">
                {% for prop in properties %}
                    <div class="col-md-6">
                        <div class="property-card">
                            <div class="card-img-wrap">
                                <img src="{{ prop.primary_image }}" alt="{{ prop.title }}" onerror="this.src='https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=800&q=80'">
                                <div class="price-tag">₹{{ "{:,}".format(prop.monthly_rent) }}<small>/mo</small></div>
                                <button class="fav-btn-badge fav-toggle-btn" data-property-id="{{ prop.id }}"><i class="fa-regular fa-heart"></i></button>
                            </div>
                            <div class="p-3 d-flex flex-column justify-content-between flex-grow-1">
                                <div>
                                    <div class="d-flex gap-2 mb-1">
                                        <span class="badge bg-primary-subtle text-primary">{{ prop.bhk }}</span>
                                        <span class="small text-muted ms-auto"><i class="fa-solid fa-location-dot text-danger me-1"></i>{{ prop.location_name }}</span>
                                    </div>
                                    <h6 class="fw-bold mb-1 text-truncate"><a href="{{ url_for('property_detail', property_id=prop.id) }}" class="text-decoration-none text-dark">{{ prop.title }}</a></h6>
                                    <p class="small text-muted mb-2" style="height:34px; overflow:hidden;">{{ prop.description }}</p>
                                    <div class="small text-muted">{{ prop.size_sqft }} sq.ft &bull; {{ prop.furnishing }} &bull; {{ prop.parking }}</div>
                                </div>
                                <div class="d-flex justify-content-between align-items-center pt-2 border-top mt-2">
                                    <span class="small text-muted">Adv: ₹{{ "{:,}".format(prop.advance_amount) }}</span>
                                    <a href="{{ url_for('property_detail', property_id=prop.id) }}" class="btn btn-sm btn-primary rounded-pill px-3">View</a>
                                </div>
                            </div>
                        </div>
                    </div>
                {% else %}
                    <div class="col-12 text-center py-5 bg-white rounded-3">
                        <p class="text-muted">No houses match your filters. Try resetting filters.</p>
                    </div>
                {% endfor %}
            </div>
        </div>
    </div>
</div>
{% endblock %}""",

'property_detail.html': """{% extends 'base.html' %}
{% block content %}
<div class="container py-4">
    <div class="row g-4">
        <div class="col-lg-8">
            <div class="card border-0 shadow-sm rounded-4 overflow-hidden mb-4">
                <img src="{{ property.primary_image }}" alt="{{ property.title }}" style="width:100%; height:380px; object-fit:cover;" onerror="this.src='https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=800&q=80'">
                <div class="p-4">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="badge bg-primary fs-6">{{ property.bhk }} &bull; {{ property.property_type }}</span>
                        <button class="btn btn-outline-danger btn-sm rounded-pill fav-toggle-btn {% if is_fav %}active{% endif %}" data-property-id="{{ property.id }}">
                            <i class="{% if is_fav %}fa-solid{% else %}fa-regular{% endif %} fa-heart me-1"></i> Save
                        </button>
                    </div>
                    <h3 class="fw-bold mb-2">{{ property.title }}</h3>
                    <p class="text-muted small"><i class="fa-solid fa-location-dot text-danger me-1"></i> {{ property.address }} &bull; {{ property.location_name }} &bull; PIN: {{ property.pincode }}</p>
                    
                    <h5 class="fw-bold mt-4 mb-2">Specifications</h5>
                    <div class="row g-2 mb-4">
                        <div class="col-3 p-2 bg-light rounded text-center"><small class="text-muted d-block">Size</small><strong>{{ property.size_sqft }} sq.ft</strong></div>
                        <div class="col-3 p-2 bg-light rounded text-center"><small class="text-muted d-block">Baths</small><strong>{{ property.bathrooms }}</strong></div>
                        <div class="col-3 p-2 bg-light rounded text-center"><small class="text-muted d-block">Furnishing</small><strong>{{ property.furnishing }}</strong></div>
                        <div class="col-3 p-2 bg-light rounded text-center"><small class="text-muted d-block">Parking</small><strong>{{ property.parking }}</strong></div>
                    </div>

                    <h5 class="fw-bold mb-2">About the Property</h5>
                    <p class="text-muted">{{ property.description }}</p>

                    <h5 class="fw-bold mt-4 mb-2">Amenities</h5>
                    <div>
                        {% for a in property.amenities %}
                            <span class="amenity-chip"><i class="fa-solid {{ a.icon }} text-primary"></i> {{ a.name }}</span>
                        {% endfor %}
                    </div>
                </div>
            </div>

            {% if similar_properties %}
                <h5 class="fw-bold mb-3">Similar Houses in Tumakuru (Cosine Match)</h5>
                <div class="row g-3">
                    {% for sp in similar_properties %}
                        <div class="col-md-4">
                            <div class="property-card">
                                <div class="card-img-wrap" style="height:140px;">
                                    <img src="{{ sp.primary_image }}" alt="{{ sp.title }}" onerror="this.src='https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=800&q=80'">
                                    <div class="price-tag" style="font-size:0.9rem;">₹{{ "{:,}".format(sp.monthly_rent) }}</div>
                                </div>
                                <div class="p-2">
                                    <h6 class="small fw-bold text-truncate mb-1"><a href="{{ url_for('property_detail', property_id=sp.id) }}" class="text-dark text-decoration-none">{{ sp.title }}</a></h6>
                                    <span class="small text-muted">{{ sp.location_name }} &bull; {{ sp.bhk }}</span>
                                </div>
                            </div>
                        </div>
                    {% endfor %}
                </div>
            {% endif %}
        </div>

        <div class="col-lg-4">
            <div class="card border-0 shadow-sm rounded-4 p-4 sticky-top" style="top: 85px;">
                <span class="text-muted small">Monthly Rent</span>
                <h2 class="fw-bold text-primary mb-1">₹{{ "{:,}".format(property.monthly_rent) }}<small class="fs-6 text-muted">/mo</small></h2>
                <div class="small text-muted mb-3">Security Deposit / Advance: <strong>₹{{ "{:,}".format(property.advance_amount) }}</strong></div>

                <div class="p-3 bg-light rounded-3 mb-3">
                    <span class="small text-muted d-block">House Owner:</span>
                    <h6 class="fw-bold mb-1">{{ property.owner_name }}</h6>
                    <span class="small text-muted"><i class="fa-solid fa-phone me-1"></i> {{ property.owner_phone }}</span>
                </div>

                <h6 class="fw-bold mb-2">Send Inquiry to Owner</h6>
                <form action="{{ url_for('enquire_property', property_id=property.id) }}" method="POST">
                    <div class="mb-2">
                        <label class="form-label small fw-semibold">Phone Number</label>
                        <input type="tel" name="phone" class="form-control form-control-sm" value="{{ current_user.phone if current_user else '' }}" placeholder="10-digit number" required>
                    </div>
                    <div class="mb-2">
                        <label class="form-label small fw-semibold">Move-in Date</label>
                        <input type="date" name="preferred_move_in" class="form-control form-control-sm" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label small fw-semibold">Message</label>
                        <textarea name="message" class="form-control form-control-sm" rows="3" placeholder="Hello, I am interested in visiting..." required></textarea>
                    </div>
                    <button type="submit" class="btn btn-primary w-100 fw-bold">Submit Enquiry</button>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}""",

'recommend.html': """{% extends 'base.html' %}
{% block content %}
<div class="bg-white border-bottom py-3 mb-4">
    <div class="container">
        <span class="badge bg-primary px-3 py-1 rounded-pill mb-1">B.Sc. Data Science Recommendation Engine</span>
        <h3 class="fw-bold mb-0">Smart Requirement Matching Wizard</h3>
        <p class="text-muted small mb-0">Enter your living preferences to compute multi-criteria utility and Cosine Similarity scores against all Tumakuru houses.</p>
    </div>
</div>

<div class="container mb-5">
    <div class="row g-4">
        <div class="col-lg-4">
            <div class="bg-white p-4 rounded-4 shadow-sm border sticky-top" style="top: 85px;">
                <h5 class="fw-bold mb-3 border-bottom pb-2"><i class="fa-solid fa-sliders text-primary me-2"></i>Your Preferences</h5>
                <form action="{{ url_for('recommend') }}" method="POST">
                    <div class="mb-3">
                        <label class="form-label small fw-bold">Preferred Locality</label>
                        <select name="location_id" class="form-select form-select-sm">
                            <option value="">Any Area in Tumakuru</option>
                            {% for loc in locations %}
                                <option value="{{ loc.id }}" {% if preferences.location_id|string == loc.id|string %}selected{% endif %}>{{ loc.name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="mb-3">
                        <label class="form-label small fw-bold">BHK Config</label>
                        <select name="bhk" class="form-select form-select-sm">
                            <option value="Any">Any BHK</option>
                            <option value="1 RK" {% if preferences.bhk == '1 RK' %}selected{% endif %}>1 RK (Single)</option>
                            <option value="1 BHK" {% if preferences.bhk == '1 BHK' %}selected{% endif %}>1 BHK</option>
                            <option value="2 BHK" {% if preferences.bhk == '2 BHK' %}selected{% endif %}>2 BHK</option>
                            <option value="3 BHK" {% if preferences.bhk == '3 BHK' %}selected{% endif %}>3 BHK</option>
                        </select>
                    </div>
                    <div class="mb-3">
                        <label class="form-label small fw-bold">Max Monthly Budget (₹)</label>
                        <input type="number" name="max_rent" class="form-control form-control-sm" value="{{ preferences.max_rent or 15000 }}">
                    </div>
                    <div class="mb-3">
                        <label class="form-label small fw-bold">Furnishing</label>
                        <select name="furnishing" class="form-select form-select-sm">
                            <option value="Any">Any</option>
                            <option value="Unfurnished" {% if preferences.furnishing == 'Unfurnished' %}selected{% endif %}>Unfurnished</option>
                            <option value="Semi-Furnished" {% if preferences.furnishing == 'Semi-Furnished' %}selected{% endif %}>Semi-Furnished</option>
                            <option value="Fully Furnished" {% if preferences.furnishing == 'Fully Furnished' %}selected{% endif %}>Fully Furnished</option>
                        </select>
                    </div>
                    <div class="mb-3">
                        <label class="form-label small fw-bold">Desired Amenities (Cosine Vector)</label>
                        <div class="p-2 border rounded bg-light" style="max-height: 120px; overflow-y:auto;">
                            {% for a in amenities %}
                                <div class="form-check small mb-1">
                                    <input class="form-check-input" type="checkbox" name="amenities" value="{{ a.id }}" id="am_{{ a.id }}" {% if a.id in preferences.amenities %}checked{% endif %}>
                                    <label class="form-check-label" for="am_{{ a.id }}">{{ a.name }}</label>
                                </div>
                            {% endfor %}
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary w-100 fw-bold py-2 rounded-3"><i class="fa-solid fa-wand-magic-sparkles me-1"></i> Compute Best Matches</button>
                </form>
            </div>
        </div>

        <div class="col-lg-8">
            {% if has_searched %}
                <h5 class="fw-bold mb-3">Ranked Matching Houses</h5>
                <div class="row g-3">
                    {% for prop in results %}
                        <div class="col-12">
                            <div class="card border-0 shadow-sm rounded-4 overflow-hidden p-3 bg-white">
                                <div class="row g-3 align-items-center">
                                    <div class="col-md-4 position-relative">
                                        <img src="{{ prop.primary_image }}" alt="{{ prop.title }}" class="rounded-3 w-100" style="height:160px; object-fit:cover;" onerror="this.src='https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=800&q=80'">
                                        <span class="match-score-badge bg-{{ prop.badge_class }}">{{ prop.match_score }}% Match</span>
                                    </div>
                                    <div class="col-md-8">
                                        <div class="d-flex justify-content-between">
                                            <span class="badge bg-primary-subtxet text-primary">{{ prop.bhk }} &bull; {{ prop.location_name }}</span>
                                            <span class="fw-bold text-primary fs-5">₹{{ "{:,}".format(prop.monthly_rent) }}/mo</span>
                                        </div>
                                        <h6 class="fw-bold my-1"><a href="{{ url_for('property_detail', property_id=prop.id) }}" class="text-dark text-decoration-none">{{ prop.title }}</a></h6>
                                        <div class="mb-2">
                                            {% for r in prop.reasons %}
                                                <span class="badge bg-success-subtle text-success border border-success-subtle small me-1"><i class="fa-solid fa-check"></i> {{ r }}</span>
                                            {% endfor %}
                                        </div>
                                        <div class="d-flex justify-content-between align-items-center pt-2 border-top">
                                            <span class="small text-muted">Loc: {{ prop.subscores.Location }}% &bull; Budget: {{ prop.subscores.Budget }}% &bull; Space: {{ prop.subscores['Space & BHK'] }}%</span>
                                            <a href="{{ url_for('property_detail', property_id=prop.id) }}" class="btn btn-sm btn-primary rounded-pill px-3">View House</a>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    {% endfor %}
                </div>
            {% else %}
                <div class="p-5 text-center bg-white rounded-4 shadow-sm border">
                    <i class="fa-solid fa-wand-magic-sparkles text-primary display-4 mb-3"></i>
                    <h5 class="fw-bold">Ready to Match Houses?</h5>
                    <p class="text-muted small">Choose your preferences on the left and click "Compute Best Matches" to run the Data Science Recommender.</p>
                </div>
            {% endif %}
        </div>
    </div>
</div>
{% endblock %}""",

'login.html': """{% extends 'base.html' %}
{% block content %}
<div class="container py-5">
    <div class="row justify-content-center">
        <div class="col-md-5">
            <div class="card border-0 shadow-sm rounded-4 p-4 bg-white">
                <h4 class="fw-bold text-center mb-1">Sign In</h4>
                <p class="text-muted small text-center mb-4">RentMatch Tumakuru Platform</p>
                <form action="{{ url_for('login') }}" method="POST">
                    <div class="mb-3">
                        <label class="form-label small fw-bold">Email Address</label>
                        <input type="email" id="emailIn" name="email" class="form-control" placeholder="name@example.com" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label small fw-bold">Password</label>
                        <input type="password" id="pwdIn" name="password" class="form-control" placeholder="••••••••" required>
                    </div>
                    <button type="submit" class="btn btn-primary w-100 fw-bold py-2 rounded-3">Sign In</button>
                </form>
                <div class="mt-4 p-3 bg-light rounded-3 border">
                    <span class="small fw-bold text-muted d-block text-center mb-2">1-CLICK DEMO LOGIN</span>
                    <div class="d-flex gap-2 justify-content-center">
                        <button type="button" class="btn btn-xs btn-outline-primary small py-1" onclick="fill('rohan.student@gmail.com')">Tenant</button>
                        <button type="button" class="btn btn-xs btn-outline-success small py-1" onclick="fill('suresh.gowda@gmail.com')">Owner</button>
                        <button type="button" class="btn btn-xs btn-outline-danger small py-1" onclick="fill('admin@rentmatch.com')">Admin</button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
<script>
function fill(email){
    document.getElementById('emailIn').value = email;
    document.getElementById('pwdIn').value = 'password123';
}
</script>
{% endblock %}""",

'register.html': """{% extends 'base.html' %}
{% block content %}
<div class="container py-5">
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card border-0 shadow-sm rounded-4 p-4 bg-white">
                <h4 class="fw-bold text-center mb-3">Create RentMatch Account</h4>
                <form action="{{ url_for('register') }}" method="POST">
                    <div class="mb-3">
                        <label class="form-label small fw-bold">I am joining as:</label>
                        <div class="d-flex gap-3">
                            <div class="form-check"><input class="form-check-input" type="radio" name="role" id="r1" value="tenant" checked><label class="form-check-label" for="r1">Tenant</label></div>
                            <div class="form-check"><input class="form-check-input" type="radio" name="role" id="r2" value="owner"><label class="form-check-label" for="r2">House Owner</label></div>
                        </div>
                    </div>
                    <div class="mb-3"><label class="form-label small fw-bold">Full Name</label><input type="text" name="name" class="form-control" required></div>
                    <div class="mb-3"><label class="form-label small fw-bold">Email</label><input type="email" name="email" class="form-control" required></div>
                    <div class="mb-3"><label class="form-label small fw-bold">Phone</label><input type="tel" name="phone" class="form-control" required></div>
                    <div class="mb-3"><label class="form-label small fw-bold">Password</label><input type="password" name="password" class="form-control" required></div>
                    <button type="submit" class="btn btn-primary w-100 fw-bold py-2 rounded-3">Register</button>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}""",

'owner_dashboard.html': """{% extends 'base.html' %}
{% block content %}
<div class="container py-4">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <div><h4 class="fw-bold mb-0">Owner Dashboard</h4><span class="text-muted small">Welcome, {{ current_user.name }}</span></div>
        <a href="{{ url_for('new_property') }}" class="btn btn-primary rounded-pill px-4"><i class="fa-solid fa-plus me-1"></i> Add Property</a>
    </div>

    <h5 class="fw-bold mb-3">My Properties ({{ properties|length }})</h5>
    <div class="card border-0 shadow-sm rounded-4 overflow-hidden mb-5">
        <table class="table table-hover align-middle mb-0">
            <thead class="table-light small">
                <tr><th>Title</th><th>Locality</th><th>Rent</th><th>Status</th><th>Actions</th></tr>
            </thead>
            <tbody>
                {% for p in properties %}
                    <tr>
                        <td class="fw-semibold">{{ p.title }}</td>
                        <td>{{ p.location_name }}</td>
                        <td>₹{{ "{:,}".format(p.monthly_rent) }}</td>
                        <td><span class="badge bg-success">{{ p.status }}</span></td>
                        <td>
                            <a href="{{ url_for('property_detail', property_id=p.id) }}" class="btn btn-sm btn-outline-secondary rounded-pill me-1">View</a>
                            <a href="{{ url_for('edit_property', property_id=p.id) }}" class="btn btn-sm btn-outline-primary rounded-pill me-1">Edit</a>
                            <form action="{{ url_for('delete_property', property_id=p.id) }}" method="POST" class="d-inline" onsubmit="return confirm('Delete this property?');">
                                <button type="submit" class="btn btn-sm btn-outline-danger rounded-pill">Delete</button>
                            </form>
                        </td>
                    </tr>
                {% else %}
                    <tr><td colspan="5" class="text-center py-4 text-muted">No properties posted yet.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <h5 class="fw-bold mb-3">Tenant Inquiries ({{ enquiries|length }})</h5>
    <div class="card border-0 shadow-sm rounded-4 p-3 bg-white">
        {% for e in enquiries %}
            <div class="p-3 bg-light rounded-3 mb-2">
                <div class="d-flex justify-content-between">
                    <span class="fw-bold">{{ e.tenant_name }} &bull; {{ e.property_title }}</span>
                    <span class="badge bg-info text-dark">Move-in: {{ e.preferred_move_in }}</span>
                </div>
                <p class="small text-muted my-1">"{{ e.message }}"</p>
                <small class="text-muted">Phone: {{ e.phone }} &bull; Email: {{ e.tenant_email }}</small>
            </div>
        {% else %}
            <p class="text-muted small mb-0">No inquiries received yet.</p>
        {% endfor %}
    </div>
</div>
{% endblock %}""",

'property_form.html': """{% extends 'base.html' %}
{% block content %}
<div class="container py-4">
    <div class="card border-0 shadow-sm rounded-4 p-4 bg-white max-w-700 mx-auto" style="max-width:700px;">
        <h4 class="fw-bold mb-3">{% if is_edit %}Edit Property Listing{% else %}Post a Rental House in Tumakuru{% endif %}</h4>
        <form action="{% if is_edit %}{{ url_for('edit_property', property_id=prop.id) }}{% else %}{{ url_for('new_property') }}{% endif %}" method="POST">
            <div class="mb-3"><label class="form-label small fw-bold">Title *</label><input type="text" name="title" class="form-control" value="{{ prop.title or '' }}" required></div>
            <div class="row g-2 mb-3">
                <div class="col-6">
                    <label class="form-label small fw-bold">Type</label>
                    <select name="property_type" class="form-select">
                        <option value="Independent House" {% if prop.property_type == 'Independent House' %}selected{% endif %}>Independent House</option>
                        <option value="Apartment" {% if prop.property_type == 'Apartment' %}selected{% endif %}>Apartment</option>
                        <option value="Villa" {% if prop.property_type == 'Villa' %}selected{% endif %}>Villa</option>
                        <option value="Studio Room" {% if prop.property_type == 'Studio Room' %}selected{% endif %}>Studio Room</option>
                    </select>
                </div>
                <div class="col-6">
                    <label class="form-label small fw-bold">Locality *</label>
                    <select name="location_id" class="form-select">
                        {% for loc in locations %}
                            <option value="{{ loc.id }}" {% if prop.location_id == loc.id %}selected{% endif %}>{{ loc.name }}</option>
                        {% endfor %}
                    </select>
                </div>
            </div>
            <div class="mb-3"><label class="form-label small fw-bold">Address *</label><input type="text" name="address" class="form-control" value="{{ prop.address or '' }}" required></div>
            <div class="row g-2 mb-3">
                <div class="col-4">
                    <label class="form-label small fw-bold">BHK</label>
                    <select name="bhk" class="form-select">
                        <option value="1 RK" {% if prop.bhk == '1 RK' %}selected{% endif %}>1 RK</option>
                        <option value="1 BHK" {% if prop.bhk == '1 BHK' %}selected{% endif %}>1 BHK</option>
                        <option value="2 BHK" {% if prop.bhk == '2 BHK' or not prop.bhk %}selected{% endif %}>2 BHK</option>
                        <option value="3 BHK" {% if prop.bhk == '3 BHK' %}selected{% endif %}>3 BHK</option>
                    </select>
                </div>
                <div class="col-4"><label class="form-label small fw-bold">Rent (₹/mo) *</label><input type="number" name="monthly_rent" class="form-control" value="{{ prop.monthly_rent or '' }}" required></div>
                <div class="col-4"><label class="form-label small fw-bold">Advance (₹) *</label><input type="number" name="advance_amount" class="form-control" value="{{ prop.advance_amount or '' }}" required></div>
            </div>
            <div class="row g-2 mb-3">
                <div class="col-4"><label class="form-label small fw-bold">Size (sq.ft)</label><input type="number" name="size_sqft" class="form-control" value="{{ prop.size_sqft or 1000 }}" required></div>
                <div class="col-4">
                    <label class="form-label small fw-bold">Furnishing</label>
                    <select name="furnishing" class="form-select">
                        <option value="Unfurnished" {% if prop.furnishing == 'Unfurnished' %}selected{% endif %}>Unfurnished</option>
                        <option value="Semi-Furnished" {% if prop.furnishing == 'Semi-Furnished' %}selected{% endif %}>Semi-Furnished</option>
                        <option value="Fully Furnished" {% if prop.furnishing == 'Fully Furnished' %}selected{% endif %}>Fully Furnished</option>
                    </select>
                </div>
                <div class="col-4">
                    <label class="form-label small fw-bold">Parking</label>
                    <select name="parking" class="form-select">
                        <option value="Car & Bike" {% if prop.parking == 'Car & Bike' %}selected{% endif %}>Car & Bike</option>
                        <option value="Bike Only" {% if prop.parking == 'Bike Only' %}selected{% endif %}>Bike Only</option>
                        <option value="None" {% if prop.parking == 'None' %}selected{% endif %}>None</option>
                    </select>
                </div>
            </div>
            <div class="mb-3"><label class="form-label small fw-bold">Description *</label><textarea name="description" class="form-control" rows="3" required>{{ prop.description or '' }}</textarea></div>
            <div class="mb-3"><label class="form-label small fw-bold">Photo URL</label><input type="url" name="image_url" class="form-control" placeholder="https://images.unsplash.com/..." value=""></div>
            <button type="submit" class="btn btn-primary w-100 fw-bold py-2">Publish Property</button>
        </form>
    </div>
</div>
{% endblock %}""",

'tenant_dashboard.html': """{% extends 'base.html' %}
{% block content %}
<div class="container py-4">
    <h4 class="fw-bold mb-3">Tenant Portal</h4>
    <div class="row g-4">
        <div class="col-md-6">
            <h5 class="fw-bold mb-3">Saved Properties ({{ favourites|length }})</h5>
            {% for p in favourites %}
                <div class="p-3 bg-white border rounded-3 mb-2 d-flex justify-content-between align-items-center">
                    <div>
                        <h6 class="fw-bold mb-0"><a href="{{ url_for('property_detail', property_id=p.id) }}" class="text-dark text-decoration-none">{{ p.title }}</a></h6>
                        <span class="small text-muted">{{ p.location_name }} &bull; ₹{{ "{:,}".format(p.monthly_rent) }}/mo</span>
                    </div>
                    <a href="{{ url_for('property_detail', property_id=p.id) }}" class="btn btn-sm btn-outline-primary rounded-pill">View</a>
                </div>
            {% else %}
                <p class="text-muted small">No saved properties yet.</p>
            {% endfor %}
        </div>
        <div class="col-md-6">
            <h5 class="fw-bold mb-3">My Inquiries & Replies ({{ enquiries|length }})</h5>
            {% for e in enquiries %}
                <div class="p-3 bg-white border rounded-3 mb-2">
                    <span class="fw-bold d-block">{{ e.property_title }}</span>
                    <span class="small text-muted">Status: <span class="badge bg-primary">{{ e.status }}</span></span>
                    <p class="small text-muted my-1">My Msg: "{{ e.message }}"</p>
                    {% if e.owner_reply %}
                        <div class="p-2 bg-success-subtle rounded small text-success">Reply: {{ e.owner_reply }}</div>
                    {% endif %}
                </div>
            {% else %}
                <p class="text-muted small">No inquiries sent yet.</p>
            {% endfor %}
        </div>
    </div>
</div>
{% endblock %}""",

'admin_dashboard.html': """{% extends 'base.html' %}
{% block content %}
<div class="container py-4">
    <h4 class="fw-bold mb-3">Platform Administration Overview</h4>
    <div class="row g-3 mb-4">
        <div class="col-md-3"><div class="stat-card"><div class="stat-icon bg-primary-subtle text-primary"><i class="fa-solid fa-users"></i></div><div><small class="text-muted d-block">Users</small><h4 class="fw-bold mb-0">{{ stats.total_users }}</h4></div></div></div>
        <div class="col-md-3"><div class="stat-card"><div class="stat-icon bg-success-subtle text-success"><i class="fa-solid fa-building"></i></div><div><small class="text-muted d-block">Listings</small><h4 class="fw-bold mb-0">{{ stats.total_properties }}</h4></div></div></div>
        <div class="col-md-3"><div class="stat-card"><div class="stat-icon bg-warning-subtle text-warning"><i class="fa-solid fa-comments"></i></div><div><small class="text-muted d-block">Enquiries</small><h4 class="fw-bold mb-0">{{ stats.total_enquiries }}</h4></div></div></div>
        <div class="col-md-3"><div class="stat-card"><div class="stat-icon bg-info-subtle text-info"><i class="fa-solid fa-map-pin"></i></div><div><small class="text-muted d-block">Localities</small><h4 class="fw-bold mb-0">{{ all_locations|length }}</h4></div></div></div>
    </div>

    <h5 class="fw-bold mb-3">Users Management</h5>
    <div class="card border-0 shadow-sm rounded-4 overflow-hidden mb-4">
        <table class="table table-hover align-middle mb-0">
            <thead class="table-light small"><tr><th>ID</th><th>User</th><th>Role</th><th>Phone</th><th>Status</th><th>Toggle</th></tr></thead>
            <tbody>
                {% for u in users %}
                    <tr>
                        <td>#{{ u.id }}</td>
                        <td><strong>{{ u.name }}</strong><br><small class="text-muted">{{ u.email }}</small></td>
                        <td><span class="badge bg-secondary text-uppercase">{{ u.role }}</span></td>
                        <td>{{ u.phone }}</td>
                        <td><span class="badge bg-{% if u.is_active %}success{% else %}danger{% endif %}">{% if u.is_active %}Active{% else %}Suspended{% endif %}</span></td>
                        <td>
                            {% if u.role != 'admin' %}
                                <form action="{{ url_for('admin_toggle_user', user_id=u.id) }}" method="POST">
                                    <button class="btn btn-xs btn-outline-secondary rounded-pill">Toggle</button>
                                </form>
                            {% endif %}
                        </td>
                    </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endblock %}"""
}

app.jinja_loader = DictLoader(TEMPLATES)

# ========================================================================================
# FLASK WEB CONTROLLERS & ROUTES
# ========================================================================================

@app.route('/')
def index():
    featured = get_all_properties({'sort_by': 'featured'}, limit=6)
    return render_template('index.html', properties=featured)

def safe_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def safe_float(value, default=None):
    try:
        result = float(value)
        return result if result >= 0 else default
    except (TypeError, ValueError):
        return default


@app.route('/properties')
def properties():
    loc_id = request.args.get('location_id', '')
    bhk = request.args.get('bhk', 'Any')
    prop_type = request.args.get('property_type', 'Any')
    furnishing = request.args.get('furnishing', 'Any')
    parking = request.args.get('parking', 'Any')
    tenant_type = request.args.get('tenant_type', 'Any')
    min_rent = request.args.get('min_rent', '')
    max_rent = request.args.get('max_rent', '')
    kw = request.args.get('q', '')
    sort_by = request.args.get('sort_by', 'newest')

    filters = {
        'location_id': safe_int(loc_id) if loc_id and loc_id != 'Any' else None,
        'bhk': bhk, 'property_type': prop_type, 'furnishing': furnishing,
        'parking': parking, 'tenant_type': tenant_type,
        'min_rent': safe_int(min_rent) if min_rent else None,
        'max_rent': safe_int(max_rent) if max_rent else None,
        'search_keyword': kw, 'sort_by': sort_by
    }
    props = get_all_properties(filters)
    return render_template('properties.html', properties=props, filters=filters, total_count=len(props))

@app.route('/property/<int:property_id>')
def property_detail(property_id):
    prop = get_property_by_id(property_id)
    viewer = current_user()
    if prop and prop.get('status') != 'Available' and not (viewer and (viewer['role'] == 'admin' or viewer['id'] == prop['owner_id'])):
        prop = None
    if not prop:
        flash("Property not found or no longer available.", "danger")
        return redirect(url_for('properties'))

    u = current_user()
    is_fav = False
    if u:
        conn = get_db()
        is_fav = bool(conn.execute("SELECT id FROM favourites WHERE user_id = ? AND property_id = ?", (u['id'], property_id)).fetchone())
        conn.close()

    all_props = get_all_properties()
    sim_props = find_similar_properties(property_id, all_props, top_n=3)
    return render_template('property_detail.html', property=prop, is_fav=is_fav, similar_properties=sim_props)

@app.route('/recommend', methods=['GET', 'POST'])
def recommend():
    conn = get_db()
    locs = [dict(r) for r in conn.execute("SELECT * FROM locations ORDER BY name ASC").fetchall()]
    amens = [dict(r) for r in conn.execute("SELECT * FROM amenities ORDER BY name ASC").fetchall()]
    conn.close()

    if request.method == 'POST':
        loc_id = request.form.get('location_id')
        bhk = request.form.get('bhk', 'Any')
        max_rent = request.form.get('max_rent')
        furnishing = request.form.get('furnishing', 'Any')
        selected_amens = [int(a) for a in request.form.getlist('amenities') if str(a).isdigit()]

        prefs = {
            'location_id': loc_id if loc_id and loc_id != 'Any' else None,
            'bhk': bhk,
            'max_rent': safe_float(max_rent),
            'furnishing': furnishing,
            'amenities': selected_amens
        }
        all_props = get_all_properties()
        recs = recommend_properties(all_props, prefs, amens)
        return render_template('recommend.html', locations=locs, amenities=amens, results=recs, preferences=prefs, has_searched=True)

    default_prefs = {'location_id': '', 'bhk': '2 BHK', 'max_rent': 15000, 'furnishing': 'Any', 'amenities': []}
    return render_template('recommend.html', locations=locs, amenities=amens, results=[], preferences=default_prefs, has_searched=False)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        conn = get_db()
        u = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        if not u or not check_password_hash(u['password_hash'], password):
            flash("Invalid email or password.", "danger")
            return render_template('login.html')
        if not u['is_active']:
            flash("Account is suspended. Please contact admin.", "danger")
            return render_template('login.html')

        session['user_id'] = u['id']
        session['user_name'] = u['name']
        session['user_role'] = u['role']
        flash(f"Welcome, {u['name']}!", "success")
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone')
        pwd = request.form.get('password')
        # Public registration must never allow users to self-assign the admin role.
        requested_role = request.form.get('role', 'tenant')
        role = requested_role if requested_role in ('tenant', 'owner') else 'tenant'
        name = (name or '').strip()
        email = (email or '').strip().lower()
        phone = (phone or '').strip()
        pwd = pwd or ''
        if not name or len(name) > 100 or not email or len(email) > 120 or not phone or len(phone) > 20 or len(pwd) < 8:
            flash("Please provide a name, valid email, phone number and password of at least 8 characters.", "danger")
            return render_template('register.html')

        conn = get_db()
        try:
            conn.execute("INSERT INTO users (name, email, password_hash, phone, role) VALUES (?, ?, ?, ?, ?)",
                         (name, email, generate_password_hash(pwd), phone, role))
            conn.commit()
            conn.close()
            flash("Registration successful! Please sign in.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            conn.close()
            flash("Email already registered or invalid.", "danger")
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    u = current_user()
    if not u: return redirect(url_for('login'))
    if u['role'] == 'admin': return redirect(url_for('admin_dashboard'))
    if u['role'] == 'owner': return redirect(url_for('owner_dashboard'))
    return redirect(url_for('tenant_dashboard'))

@app.route('/owner/dashboard')
def owner_dashboard():
    u = current_user()
    if not u or u['role'] not in ['owner', 'admin']: return redirect(url_for('login'))
    conn = get_db()
    props = conn.execute("SELECT p.*, l.name AS location_name FROM properties p JOIN locations l ON p.location_id = l.id WHERE p.owner_id = ?", (u['id'],)).fetchall()
    enqs = conn.execute("""
        SELECT e.*, p.title AS property_title, u.name AS tenant_name, u.email AS tenant_email
        FROM enquiries e JOIN properties p ON e.property_id = p.id JOIN users u ON e.tenant_id = u.id
        WHERE p.owner_id = ?
    """, (u['id'],)).fetchall()
    conn.close()
    return render_template('owner_dashboard.html', properties=[dict(p) for p in props], enquiries=[dict(e) for e in enqs])

@app.route('/owner/property/new', methods=['GET', 'POST'])
def new_property():
    u = current_user()
    if not u or u['role'] not in ['owner', 'admin']: return redirect(url_for('login'))
    conn = get_db()
    locs = [dict(r) for r in conn.execute("SELECT * FROM locations").fetchall()]
    if request.method == 'POST':
        c = conn.cursor()
        title = (request.form.get('title') or '').strip()
        ptype = request.form.get('property_type', 'Independent House')
        lid = safe_int(request.form.get('location_id'))
        addr = (request.form.get('address') or '').strip()
        bhk = request.form.get('bhk', '2 BHK')
        rent = safe_int(request.form.get('monthly_rent'))
        adv = safe_int(request.form.get('advance_amount'), 0)
        sqft = safe_int(request.form.get('size_sqft'), 1000)
        furn = request.form.get('furnishing', 'Unfurnished')
        park = request.form.get('parking', 'Bike Only')
        desc = (request.form.get('description') or '').strip()
        img_url = (request.form.get('image_url') or 'https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=800&q=80').strip()
        if not title or not addr or not desc or lid is None or rent is None or rent < 1 or adv is None or adv < 0 or sqft is None or sqft < 1:
            conn.close()
            flash("Complete all required fields and enter valid rent, advance and area values.", "danger")
            return render_template('property_form.html', locations=locs, is_edit=False, prop=request.form)
        if ptype not in ('Independent House','Apartment','Villa','Studio Room') or bhk not in ('1 RK','1 BHK','2 BHK','3 BHK','4 BHK'):
            conn.close()
            flash("Choose a valid property type and BHK configuration.", "danger")
            return render_template('property_form.html', locations=locs, is_edit=False, prop=request.form)

        c.execute("""
            INSERT INTO properties (
                owner_id, title, description, property_type, location_id, address,
                bhk, bhk_num, size_sqft, bedrooms, bathrooms, parking, furnishing,
                monthly_rent, advance_amount, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 2, 2, ?, ?, ?, ?, 'Available')
        """, (u['id'], title, desc, ptype, lid, addr, bhk, bhk_to_num(bhk), sqft, park, furn, rent, adv))
        pid = c.lastrowid
        c.execute("INSERT INTO property_images (property_id, image_url, is_primary) VALUES (?, ?, 1)", (pid, img_url))
        conn.commit()
        conn.close()
        flash("Property listed successfully!", "success")
        return redirect(url_for('owner_dashboard'))
    conn.close()
    return render_template('property_form.html', locations=locs, is_edit=False, prop={})

@app.route('/owner/property/edit/<int:property_id>', methods=['GET', 'POST'])
def edit_property(property_id):
    u = current_user()
    if not u: return redirect(url_for('login'))
    conn = get_db()
    prop = conn.execute("SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
    if not prop or (prop['owner_id'] != u['id'] and u['role'] != 'admin'):
        conn.close()
        return redirect(url_for('owner_dashboard'))
    locs = [dict(r) for r in conn.execute("SELECT * FROM locations").fetchall()]

    if request.method == 'POST':
        conn.execute("""
            UPDATE properties SET title = ?, property_type = ?, location_id = ?, address = ?,
            bhk = ?, bhk_num = ?, monthly_rent = ?, advance_amount = ?, size_sqft = ?,
            furnishing = ?, parking = ?, description = ? WHERE id = ?
        """, (request.form.get('title'), request.form.get('property_type'), int(request.form.get('location_id')),
              request.form.get('address'), request.form.get('bhk'), bhk_to_num(request.form.get('bhk')),
              int(request.form.get('monthly_rent')), int(request.form.get('advance_amount')),
              int(request.form.get('size_sqft')), request.form.get('furnishing'), request.form.get('parking'),
              request.form.get('description'), property_id))
        conn.commit()
        conn.close()
        flash("Property updated successfully!", "success")
        return redirect(url_for('owner_dashboard'))
    conn.close()
    return render_template('property_form.html', locations=locs, is_edit=True, prop=dict(prop))

@app.route('/owner/property/delete/<int:property_id>', methods=['POST'])
def delete_property(property_id):
    u = current_user()
    if u:
        conn = get_db()
        conn.execute("DELETE FROM properties WHERE id = ? AND (owner_id = ? OR ? = 'admin')", (property_id, u['id'], u['role']))
        conn.commit()
        conn.close()
    return redirect(url_for('owner_dashboard'))

@app.route('/tenant/dashboard')
def tenant_dashboard():
    u = current_user()
    if not u: return redirect(url_for('login'))
    conn = get_db()
    favs = conn.execute("""
        SELECT p.*, l.name AS location_name FROM favourites f
        JOIN properties p ON f.property_id = p.id JOIN locations l ON p.location_id = l.id
        WHERE f.user_id = ?
    """, (u['id'],)).fetchall()
    enqs = conn.execute("""
        SELECT e.*, p.title AS property_title FROM enquiries e
        JOIN properties p ON e.property_id = p.id WHERE e.tenant_id = ?
    """, (u['id'],)).fetchall()
    conn.close()
    return render_template('tenant_dashboard.html', favourites=[dict(f) for f in favs], enquiries=[dict(e) for e in enqs])

@app.route('/property/<int:property_id>/enquire', methods=['POST'])
def enquire_property(property_id):
    u = current_user()
    if not u:
        flash("Please log in to contact the owner.", "warning")
        return redirect(url_for('login'))
    if u['role'] != 'tenant':
        flash("Only tenant accounts can send property enquiries.", "warning")
        return redirect(url_for('property_detail', property_id=property_id))
    msg = (request.form.get('message') or '').strip()
    phone = (request.form.get('phone') or '').strip()
    move_in = (request.form.get('preferred_move_in') or '').strip() or None
    prop = get_property_by_id(property_id)
    if not prop or prop.get('status') != 'Available' or len(msg) < 5 or len(msg) > 2000 or not phone or len(phone) > 20:
        flash("The property is unavailable or the enquiry details are invalid.", "danger")
        return redirect(url_for('property_detail', property_id=property_id))
    conn = get_db()
    conn.execute("INSERT INTO enquiries (property_id, tenant_id, message, preferred_move_in, phone) VALUES (?, ?, ?, ?, ?)",
                 (property_id, u['id'], msg, move_in, phone))
    conn.commit()
    conn.close()
    flash("Enquiry sent to the property owner!", "success")
    return redirect(url_for('property_detail', property_id=property_id))

@app.route('/api/favourite/toggle', methods=['POST'])
def api_favourite_toggle():
    u = current_user()
    if not u: return jsonify({'success': False, 'error': 'login_required'}), 401
    if u['role'] != 'tenant': return jsonify({'success': False, 'error': 'tenant_account_required'}), 403
    payload = request.get_json(silent=True) or {}
    pid = safe_int(payload.get('property_id'))
    if pid is None: return jsonify({'success': False, 'error': 'invalid_property_id'}), 400
    prop = get_property_by_id(pid)
    if not prop or prop.get('status') != 'Available': return jsonify({'success': False, 'error': 'property_unavailable'}), 404
    conn = get_db()
    fav = conn.execute("SELECT id FROM favourites WHERE user_id = ? AND property_id = ?", (u['id'], pid)).fetchone()
    if fav:
        conn.execute("DELETE FROM favourites WHERE id = ?", (fav['id'],))
        saved = False
    else:
        conn.execute("INSERT INTO favourites (user_id, property_id) VALUES (?, ?)", (u['id'], pid))
        saved = True
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'is_saved': saved, 'saved': saved})

@app.route('/admin/dashboard')
def admin_dashboard():
    u = current_user()
    if not u or u['role'] != 'admin': return redirect(url_for('login'))
    conn = get_db()
    stats = {
        'total_users': conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        'total_properties': conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0],
        'total_enquiries': conn.execute("SELECT COUNT(*) FROM enquiries").fetchone()[0]
    }
    users = conn.execute("SELECT * FROM users ORDER BY id ASC").fetchall()
    conn.close()
    return render_template('admin_dashboard.html', stats=stats, users=[dict(usr) for usr in users])

@app.route('/admin/user/toggle/<int:user_id>', methods=['POST'])
def admin_toggle_user(user_id):
    u = current_user()
    if u and u['role'] == 'admin' and user_id != u['id']:
        conn = get_db()
        usr = conn.execute("SELECT is_active FROM users WHERE id = ?", (user_id,)).fetchone()
        if usr:
            new_s = 0 if usr['is_active'] else 1
            conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_s, user_id))
            conn.commit()
        conn.close()
    return redirect(url_for('admin_dashboard'))

# ========================================================================================
# AUTO-LAUNCHER & MAIN EXECUTION
# ========================================================================================

def open_browser():
    webbrowser.open("http://127.0.0.1:5000")

if __name__ == '__main__':
    print("=" * 70)
    print(" RentMatch – Smart Rental Finder (Tumakuru)")
    print(" Department of Computer Science — B.Sc. Data Science")
    print(" Standalone All-In-One Application")
    print("=" * 70)
    init_and_seed_db()
    print("Starting web server at: http://127.0.0.1:5000")
    print("Press CTRL+C to stop the server.")
    
    # Launch browser after 1 second delay
    threading.Timer(1.2, open_browser).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
