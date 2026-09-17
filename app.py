import os
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'dreamnest_surat_key_highly_secure'

DB_PATH = os.path.join(os.path.dirname(__file__), 'data.db')
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static/uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- Database Helpers ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    # Enable foreign keys
    db.execute("PRAGMA foreign_keys = ON;")
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id

# --- Custom Jinja Filters ---
@app.template_filter('price_str')
def format_price_filter(price, category='buy'):
    try:
        price = int(price)
    except (ValueError, TypeError):
        return price
        
    if category == 'rent':
        if price >= 100000:
            return f"₹{price/100000:.2f} Lakh / mo"
        return f"₹{price:,} / mo"
    else:
        if price >= 10000000:
            return f"₹{price/10000000:.2f} Crore"
        if price >= 100000:
            return f"₹{price/100000:.2f} Lakh"
        return f"₹{price:,}"

# --- Authentication Decorators ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Administrator access required.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Frontend Routes ---

@app.route('/')
def index():
    user_id = session.get('user_id')
    # Get 3 featured properties
    if user_id:
        properties = query_db("""
            SELECT p.*, (SELECT 1 FROM favorites f WHERE f.user_id = ? AND f.property_id = p.id) as is_favorite 
            FROM properties p LIMIT 3
        """, [user_id])
    else:
        properties = query_db("SELECT p.*, 0 as is_favorite FROM properties p LIMIT 3")
        
    # Map formatted price strings
    props = []
    for row in properties:
        p = dict(row)
        p['price_str'] = format_price_filter(p['price'], p['category'])
        props.append(p)
        
    return render_template('index.html', current_page='home', properties=props)

@app.route('/about')
def about():
    return render_template('about.html', current_page='about')

@app.route('/buy')
def buy():
    return render_template('buy.html', current_page='buy')

@app.route('/rent')
def rent():
    return render_template('rent.html', current_page='rent')

@app.route('/insights')
def insights():
    return render_template('insights.html', current_page='insights')

@app.route('/faq')
def faq():
    return render_template('faq.html', current_page='faq')

@app.route('/agents')
def agents():
    agents_list = query_db("SELECT * FROM agents")
    return render_template('agents.html', current_page='agents', agents=agents_list)

@app.route('/contact')
def contact():
    return render_template('contact.html', current_page='contact')

# --- Properties catalog & HTMX filter ---

@app.route('/properties')
def properties():
    category = request.args.get('tab', 'buy')
    location = request.args.get('location', '')
    type_ = request.args.get('type', '')
    price_range = request.args.get('price', '')
    query = request.args.get('q', '')

    props = get_filtered_properties(category, location, type_, price_range, query)
    return render_template('properties.html', current_page='properties', 
                           properties=props, category=category, location=location, 
                           type=type_, price_range=price_range, query=query)

@app.route('/properties/filter')
def properties_filter():
    category = request.args.get('category', 'buy')
    location = request.args.get('location', '')
    type_ = request.args.get('type', '')
    price_range = request.args.get('price_range', '')
    query = request.args.get('q', '')

    props = get_filtered_properties(category, location, type_, price_range, query)
    return render_template('partials/properties_grid.html', properties=props)

def get_filtered_properties(category, location, type_, price_range, query):
    user_id = session.get('user_id')
    
    sql = "SELECT p.*, "
    if user_id:
        sql += "(SELECT 1 FROM favorites f WHERE f.user_id = ? AND f.property_id = p.id) as is_favorite "
        params = [user_id]
    else:
        sql += "0 as is_favorite "
        params = []
        
    sql += "FROM properties p WHERE p.category = ?"
    params.append(category)

    if location:
        sql += " AND p.location = ?"
        params.append(location)
    if type_:
        sql += " AND p.type = ?"
        params.append(type_)
    if query:
        sql += " AND (p.title LIKE ? OR p.tag LIKE ?)"
        params.extend([f"%{query}%", f"%{query}%"])
        
    # Budget Filters
    if price_range:
        if category == 'buy':
            if price_range == 'budget':
                sql += " AND p.price < 7500000"
            elif price_range == 'mid':
                sql += " AND p.price BETWEEN 7500000 AND 15000000"
            elif price_range == 'premium':
                sql += " AND p.price BETWEEN 15000000 AND 30000000"
            elif price_range == 'luxury':
                sql += " AND p.price > 30000000"
        else: # rent
            if price_range == 'budget':
                sql += " AND p.price < 35000"
            elif price_range == 'mid':
                sql += " AND p.price BETWEEN 35000 AND 75000"
            elif price_range == 'premium':
                sql += " AND p.price > 75000"

    sql += " ORDER BY p.id DESC"
    
    rows = query_db(sql, params)
    props = []
    for r in rows:
        p = dict(r)
        p['price_str'] = format_price_filter(p['price'], p['category'])
        props.append(p)
    return props

@app.route('/properties/<int:id>')
def property_details(id):
    user_id = session.get('user_id')
    if user_id:
        p_row = query_db("""
            SELECT p.*, (SELECT 1 FROM favorites f WHERE f.user_id = ? AND f.property_id = p.id) as is_favorite 
            FROM properties p WHERE p.id = ?
        """, [user_id, id], one=True)
    else:
        p_row = query_db("SELECT p.*, 0 as is_favorite FROM properties p WHERE p.id = ?", [id], one=True)
        
    if not p_row:
        flash("Property listing not found.", "error")
        return redirect(url_for('properties'))
        
    p = dict(p_row)
    p['price_str'] = format_price_filter(p['price'], p['category'])
    
    # Get assigned agent details
    agent = query_db("SELECT * FROM agents WHERE id = ?", [p['agent_id']], one=True)
    if not agent:
        # Fallback to default first agent
        agent = query_db("SELECT * FROM agents LIMIT 1", one=True)
        
    return render_template('property-details.html', property=p, agent=agent)

# --- Client Form submission ---

@app.route('/inquiries/submit', methods=['POST'])
@app.route('/inquiries/submit/<int:property_id>', methods=['POST'])
def submit_inquiry(property_id=None):
    type_ = request.form.get('type', 'General Query')
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    
    # Assemble messages
    if type_ == 'Tour Request':
        date = request.form.get('date')
        time = request.form.get('time')
        tour_type = request.form.get('tour_type', 'In-Person')
        message = f"Tour Booking: {date} at {time} ({tour_type})"
    elif type_ == 'Rental Application':
        company = request.form.get('company')
        move_in = request.form.get('move_in_date')
        occupants = request.form.get('occupants')
        message = f"Rental App | Move-in: {move_in} | Company: {company or 'N/A'} | Occupants: {occupants}"
    elif type_ == 'Broker Application':
        rera = request.form.get('rera')
        specialty = request.form.get('specialty')
        exp = request.form.get('experience')
        message = f"Broker Partner Onboarding | RERA: {rera} | Spec: {specialty} | Exp: {exp} Years"
    else:
        message = request.form.get('message', 'General Query')

    # Save to SQLite Inquiries
    execute_db("""
        INSERT INTO inquiries (property_id, name, email, phone, message)
        VALUES (?, ?, ?, ?, ?)
    """, [property_id, name, email, phone, message])

    # HTMX success response replaces form with details
    success_html = f"""
    <div class="p-6 bg-green-500/10 border border-green-500/20 text-green-400 rounded-xl text-center space-y-2">
      <i data-lucide="check-circle" class="w-8 h-8 mx-auto text-green-400"></i>
      <h4 class="font-bold text-white text-md">Request Submitted!</h4>
      <p class="text-xs text-slate-300">Thank you, {name}. Our real estate coordinator will connect with you shortly.</p>
    </div>
    <script>lucide.createIcons();</script>
    """
    return success_html

# --- User Account & Auth Routing ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = query_db("SELECT * FROM users WHERE email = ?", [email], one=True)
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['role'] = user['role']
            flash('Session authenticated successfully!', 'success')
            
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid login credentials. Hint: use admin@dreamnest.com / admin', 'error')
            
    return render_template('login.html', current_page='login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if email exists
        exists = query_db("SELECT id FROM users WHERE email = ?", [email], one=True)
        if exists:
            flash('An account with this email already exists.', 'error')
        else:
            pass_hash = generate_password_hash(password)
            execute_db("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'user')", [
                name, email, pass_hash
            ])
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
            
    return render_template('register.html', current_page='register')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def user_dashboard():
    user_id = session['user_id']
    favorites_rows = query_db("""
        SELECT p.* FROM properties p
        JOIN favorites f ON f.property_id = p.id
        WHERE f.user_id = ?
    """, [user_id])
    
    favs = []
    for r in favorites_rows:
        p = dict(r)
        p['price_str'] = format_price_filter(p['price'], p['category'])
        favs.append(p)
        
    return render_template('dashboard.html', properties=favs)

@app.route('/toggle-favorite/<int:id>', methods=['POST'])
@login_required
def toggle_favorite(id):
    user_id = session['user_id']
    # Check if already wishlisted
    exists = query_db("SELECT id FROM favorites WHERE user_id = ? AND property_id = ?", [user_id, id], one=True)
    if exists:
        execute_db("DELETE FROM favorites WHERE user_id = ? AND property_id = ?", [user_id, id])
        return jsonify({"status": "removed"})
    else:
        execute_db("INSERT INTO favorites (user_id, property_id) VALUES (?, ?)", [user_id, id])
        return jsonify({"status": "added"})

# --- Admin Dashboard & CRUD ---

@app.route('/admin')
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    properties_count = query_db("SELECT COUNT(*) FROM properties", one=True)[0]
    inquiries_count = query_db("SELECT COUNT(*) FROM inquiries", one=True)[0]
    agents_count = query_db("SELECT COUNT(*) FROM agents", one=True)[0]
    
    # Statistics calculations
    return render_template('admin/dashboard.html', current_admin_page='dashboard',
                           p_count=properties_count, i_count=inquiries_count, a_count=agents_count)

@app.route('/admin/properties', methods=['GET', 'POST'])
@admin_required
def admin_properties():
    db = get_db()
    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        location = request.form.get('location')
        price = int(request.form.get('price'))
        type_ = request.form.get('type')
        beds = request.form.get('bedrooms', 'N/A')
        baths = request.form.get('bathrooms', 'N/A')
        area = request.form.get('area')
        tag = request.form.get('tag', 'Exclusive Listing')
        desc = request.form.get('description', '')
        agent_id = request.form.get('agent_id')
        
        # Image handles
        img_url = request.form.get('image_url')
        file = request.files.get('image_file')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            img_url = url_for('static', filename='uploads/' + filename)
        
        if not img_url:
            img_url = 'https://images.unsplash.com/photo-1564013799919-ab600027ffc6?auto=format&fit=crop&w=800&q=80'
            
        execute_db("""
            INSERT INTO properties (title, price, location, type, bedrooms, bathrooms, area, image, tag, description, category, agent_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [title, price, location, type_, beds, baths, area + " sq ft", img_url, tag, desc, category, agent_id])
        flash('Property listing added successfully!', 'success')
        return redirect(url_for('admin_properties'))
        
    properties = query_db("SELECT p.*, a.name as agent_name FROM properties p LEFT JOIN agents a ON p.agent_id = a.id ORDER BY p.id DESC")
    agents = query_db("SELECT id, name FROM agents")
    
    props = []
    for r in properties:
        p = dict(r)
        p['price_str'] = format_price_filter(p['price'], p['category'])
        props.append(p)
        
    return render_template('admin/properties.html', current_admin_page='properties', properties=props, agents=agents)

@app.route('/admin/properties/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def admin_properties_edit(id):
    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        location = request.form.get('location')
        price = int(request.form.get('price'))
        type_ = request.form.get('type')
        beds = request.form.get('bedrooms', 'N/A')
        baths = request.form.get('bathrooms', 'N/A')
        area = request.form.get('area')
        tag = request.form.get('tag', 'Exclusive Listing')
        desc = request.form.get('description', '')
        agent_id = request.form.get('agent_id')
        
        img_url = request.form.get('image_url')
        file = request.files.get('image_file')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            img_url = url_for('static', filename='uploads/' + filename)
            
        if img_url:
            execute_db("""
                UPDATE properties SET title=?, price=?, location=?, type=?, bedrooms=?, bathrooms=?, area=?, image=?, tag=?, description=?, category=?, agent_id=?
                WHERE id = ?
            """, [title, price, location, type_, beds, baths, area, img_url, tag, desc, category, agent_id, id])
        else:
            execute_db("""
                UPDATE properties SET title=?, price=?, location=?, type=?, bedrooms=?, bathrooms=?, area=?, tag=?, description=?, category=?, agent_id=?
                WHERE id = ?
            """, [title, price, location, type_, beds, baths, area, tag, desc, category, agent_id, id])
            
        flash('Property listing updated successfully!', 'success')
        return redirect(url_for('admin_properties'))
        
    p = query_db("SELECT * FROM properties WHERE id = ?", [id], one=True)
    agents = query_db("SELECT id, name FROM agents")
    return render_template('admin/properties_edit_modal.html', property=p, agents=agents)

@app.route('/admin/properties/delete/<int:id>', methods=['POST', 'DELETE'])
@admin_required
def admin_properties_delete(id):
    execute_db("DELETE FROM properties WHERE id = ?", [id])
    if request.headers.get('HX-Request'):
        # Return empty response for HTMX removal
        return ""
    flash('Property deleted successfully.', 'success')
    return redirect(url_for('admin_properties'))

# --- Agent Management CRUD ---

@app.route('/admin/agents', methods=['GET', 'POST'])
@admin_required
def admin_agents():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        bio = request.form.get('bio')
        
        img_url = request.form.get('image_url')
        file = request.files.get('image_file')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            img_url = url_for('static', filename='uploads/' + filename)
            
        if not img_url:
            img_url = 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=200&q=80'
            
        execute_db("INSERT INTO agents (name, email, phone, bio, image) VALUES (?, ?, ?, ?, ?)", [
            name, email, phone, bio, img_url
        ])
        flash('Agent listing added successfully!', 'success')
        return redirect(url_for('admin_agents'))
        
    agents = query_db("SELECT * FROM agents ORDER BY id DESC")
    return render_template('admin/agents.html', current_admin_page='agents', agents=agents)

@app.route('/admin/agents/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def admin_agents_edit(id):
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        bio = request.form.get('bio')
        
        img_url = request.form.get('image_url')
        file = request.files.get('image_file')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            img_url = url_for('static', filename='uploads/' + filename)
            
        if img_url:
            execute_db("UPDATE agents SET name=?, email=?, phone=?, bio=?, image=? WHERE id=?", [
                name, email, phone, bio, img_url, id
            ])
        else:
            execute_db("UPDATE agents SET name=?, email=?, phone=?, bio=? WHERE id=?", [
                name, email, phone, bio, id
            ])
        flash('Agent profile updated successfully!', 'success')
        return redirect(url_for('admin_agents'))
        
    a = query_db("SELECT * FROM agents WHERE id = ?", [id], one=True)
    return render_template('admin/agents_edit_modal.html', agent=a)

@app.route('/admin/agents/delete/<int:id>', methods=['POST', 'DELETE'])
@admin_required
def admin_agents_delete(id):
    execute_db("DELETE FROM agents WHERE id = ?", [id])
    if request.headers.get('HX-Request'):
        return ""
    flash('Agent deleted successfully.', 'success')
    return redirect(url_for('admin_agents'))

# --- Inquiries Management ---

@app.route('/admin/inquiries')
@admin_required
def admin_inquiries():
    inquiries = query_db("""
        SELECT i.*, p.title as property_title 
        FROM inquiries i 
        LEFT JOIN properties p ON i.property_id = p.id 
        ORDER BY i.id DESC
    """)
    return render_template('admin/inquiries.html', current_admin_page='inquiries', inquiries=inquiries)

@app.route('/admin/inquiries/clear', methods=['POST'])
@admin_required
def admin_inquiries_clear():
    execute_db("DELETE FROM inquiries")
    flash('All inquiries have been cleared.', 'success')
    return redirect(url_for('admin_inquiries'))

@app.route('/admin/inquiries/delete/<int:id>', methods=['POST', 'DELETE'])
@admin_required
def admin_inquiries_delete(id):
    execute_db("DELETE FROM inquiries WHERE id = ?", [id])
    if request.headers.get('HX-Request'):
         return ""
    flash('Inquiry deleted successfully.', 'success')
    return redirect(url_for('admin_inquiries'))

# --- User Management ---

@app.route('/admin/users', methods=['GET', 'POST'])
@admin_required
def admin_users():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        role = request.form.get('role')
        execute_db("UPDATE users SET role = ? WHERE id = ?", [role, user_id])
        flash('User role updated successfully.', 'success')
        return redirect(url_for('admin_users'))
        
    users = query_db("SELECT id, name, email, role FROM users ORDER BY id DESC")
    return render_template('admin/users.html', current_admin_page='users', users=users)

if __name__ == '__main__':
    app.run(debug=True)
