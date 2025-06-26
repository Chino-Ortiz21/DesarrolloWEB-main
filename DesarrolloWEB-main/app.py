from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash # Importar para hash de contraseñas
import json
import os # Para la clave secreta
import re # Para validación de email

from db_config import DATABASE_CONFIG 

app = Flask(__name__)

# Configuración de la conexión a la base de datos SQL Server
conn_str = (
    f"mssql+pyodbc://@{DATABASE_CONFIG['server']}/{DATABASE_CONFIG['database']}"
    f"?driver={DATABASE_CONFIG['driver'].replace(' ', '+')}&trusted_connection=yes"
)

app.config['SQLALCHEMY_DATABASE_URI'] = conn_str
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración de la clave secreta para la gestión de sesiones
# Es CRUCIAL que esta clave sea una cadena aleatoria y compleja en un entorno de producción.
# Puedes generarla con `os.urandom(24)` y guardarla en una variable de entorno.
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'your_super_secret_key_here_change_this_in_production_!!!')

db = SQLAlchemy(app)

# Definición del modelo de Usuario
class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id_usuario = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False) # Nombre de usuario único y no nulo
    email = db.Column(db.String(100), unique=True, nullable=False)  # Email único y no nulo
    celular = db.Column(db.String(20), nullable=False) # `nullable=False` si la columna en DB es NOT NULL
    contrasena = db.Column(db.String(255), nullable=False) # Mayor longitud para almacenar el hash de la contraseña

    def __repr__(self):
        return f"<Usuario {self.nombre}>"

# --- Rutas de API para Autenticación ---

@app.route('/api/register', methods=['POST'])
def api_register():
    """
    Ruta para el registro de nuevos usuarios.
    Recibe los datos de registro (nombre, email, contraseña, confirmación, y celular).
    Valida los datos, hashea la contraseña y guarda el usuario en la DB.
    """
    print("[DEBUG] Solicitud de registro recibida.")
    try:
        data = request.get_json()
        print(f"[DEBUG] Datos recibidos para registro: {data}")

        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        celular = data.get('celular') 

        # Añadir 'celular' a la validación de campos requeridos
        if not username or not email or not password or not confirm_password or not celular:
            print("[DEBUG] Error: Faltan campos requeridos en el registro (incluyendo celular).")
            return jsonify({'success': False, 'message': 'Todos los campos son requeridos (Nombre de usuario, Email, Contraseña y Celular).'}), 400

        # Validación de que las contraseñas coincidan
        if password != confirm_password:
            print("[DEBUG] Error: Las contraseñas no coinciden.")
            return jsonify({'success': False, 'message': 'Las contraseñas no coinciden.'}), 400

        # Validación de formato de email
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email): 
            print(f"[DEBUG] Error: Email inválido: {email}")
            return jsonify({'success': False, 'message': 'Por favor, ingresa un email válido.'}), 400
        
        # Opcional: Validación de formato de celular (ej. solo números, longitud)
        if not re.match(r'^\+56\s?9\d{8}$', celular):
            print(f"[DEBUG] Error: Formato de celular inválido: {celular}")
            return jsonify({'success': False, 'message': 'Por favor, ingresa un número de celular válido. Formato: +56 912345678.'}), 400

        # Validación de reglas de contraseña (reflejando la lógica del frontend)
        if not (6 <= len(password) <= 12 and
                any(char.isdigit() for char in password) and
                any(char.isalpha() for char in password) and
                any(not char.isalnum() for char in password)):
            print("[DEBUG] Error: La contraseña no cumple con los requisitos.")
            return jsonify({'success': False, 'message': 'La contraseña no cumple con los requisitos: 6-12 caracteres, al menos un número, una letra y un carácter especial.'}), 400

        # Verificar si el nombre de usuario o email ya existen en la base de datos
        existing_user_username = Usuario.query.filter_by(nombre=username).first()
        existing_user_email = Usuario.query.filter_by(email=email).first()

        if existing_user_username:
            print(f"[DEBUG] Error: Nombre de usuario '{username}' ya existe.")
            return jsonify({'success': False, 'message': 'El nombre de usuario ya existe.'}), 409 # 409 Conflict
        if existing_user_email:
            print(f"[DEBUG] Error: Email '{email}' ya registrado.")
            return jsonify({'success': False, 'message': 'El email ya está registrado.'}), 409

        # Hashear la contraseña antes de guardarla (CRUCIAL PARA LA SEGURIDAD)
        hashed_password = generate_password_hash(password)
        print("[DEBUG] Contraseña hasheada correctamente.")

        # Crear una nueva instancia de Usuario
        new_user = Usuario(
            nombre=username,
            email=email,
            celular=celular, 
            contrasena=hashed_password
        )

        db.session.add(new_user) 
        db.session.commit() 
        print(f"[DEBUG] Usuario '{username}' registrado y guardado en la DB.")
        return jsonify({'success': True, 'message': '¡Registro exitoso! Ya puedes iniciar sesión.'}), 201 # 201 Created
    except Exception as e:
        db.session.rollback() # Revertir la transacción en caso de error
        print(f"[ERROR] Error al registrar usuario: {e}") 
        if "IntegrityError" in str(e):
            message = "Error al registrar el usuario. Es posible que el nombre de usuario, email o celular ya existan, o hay un problema con los datos."
        else:
            message = f'Error interno del servidor al registrar el usuario: {str(e)}' 
        return jsonify({'success': False, 'message': message}), 500

@app.route('/api/login', methods=['POST'])
def api_login():
    """
    Ruta para el inicio de sesión de usuarios.
    Recibe el identificador (nombre de usuario o email) y la contraseña.
    Verifica las credenciales y establece una sesión si son válidas.
    """
    print("[DEBUG] Solicitud de login recibida.")
    try:
        data = request.get_json()
        print(f"[DEBUG] Datos recibidos para login: {data}")

        identifier = data.get('identifier') # Puede ser nombre de usuario o email
        password = data.get('password')

        if not identifier or not password:
            print("[DEBUG] Error: Faltan credenciales en el login.")
            return jsonify({'success': False, 'message': 'Ingresa tu nombre de usuario/email y contraseña.'}), 400

        # Buscar al usuario por nombre de usuario o por email
        user = Usuario.query.filter(
            (Usuario.nombre == identifier) | (Usuario.email == identifier)
        ).first()

        if user:
            print(f"[DEBUG] Usuario encontrado en la DB: {user.nombre}")
            # Verificar si la contraseña es correcta (usando el hash)
            if check_password_hash(user.contrasena, password):
                # Establecer la sesión del usuario
                session['user_id'] = user.id_usuario
                session['username'] = user.nombre
                print(f"[DEBUG] Sesión establecida para usuario: {session.get('username')}")
                return jsonify({'success': True, 'message': 'Inicio de sesión exitoso.'}), 200
            else:
                print("[DEBUG] Error: Contraseña incorrecta para el usuario encontrado.")
                return jsonify({'success': False, 'message': 'Usuario o contraseña incorrectos.'}), 401 
        else:
            print(f"[DEBUG] Error: Usuario '{identifier}' no encontrado en la DB.")
            return jsonify({'success': False, 'message': 'Usuario o contraseña incorrectos.'}), 401 
    except Exception as e:
        print(f"[ERROR] Error durante el login: {e}")
        return jsonify({'success': False, 'message': f'Error interno del servidor durante el login: {str(e)}'}), 500


@app.route('/api/logout', methods=['POST'])
def api_logout():
    """
    Ruta para cerrar la sesión del usuario.
    Elimina la información del usuario de la sesión.
    """
    print("[DEBUG] Solicitud de logout recibida.")
    session.pop('user_id', None) 
    session.pop('username', None) 
    print("[DEBUG] Sesión cerrada.")
    return jsonify({'success': True, 'message': 'Sesión cerrada exitosamente.'}), 200

# --- Rutas de Renderizado de Páginas HTML ---

@app.route("/")
def home():
    # Obtener el nombre de usuario de la sesión, si existe. Si no, es 'Invitado'.
    username = session.get('username', 'Invitado')
    print(f"[DEBUG] Accediendo a la página de inicio. Usuario actual: {username}")
    return render_template("home.html", username=username)

# Rutas para las páginas de supermercados
# Ahora incluyen manejo de errores para FileNotFoundError
@app.route("/lider")
def lider():
    print("[DEBUG] Accediendo a Lider.")
    username = session.get('username', 'Invitado')
    productos = [] # Inicializa como lista vacía
    try:
        with open("static/data/productos_lider.json", "r", encoding="utf-8") as f:
            productos = json.load(f)
    except FileNotFoundError:
        print("[ERROR] Archivo productos_lider.json no encontrado en static/data/. La página se cargará sin productos.")
    return render_template("lider.html", productos=productos, username=username)

@app.route('/jumbo')
def jumbo():
    print("[DEBUG] Accediendo a Jumbo.")
    username = session.get('username', 'Invitado')
    productos = [] # Inicializa como lista vacía
    try:
        with open("static/data/productos_jumbo.json", "r", encoding="utf-8") as f:
            productos = json.load(f)
    except FileNotFoundError:
        print("[ERROR] Archivo productos_jumbo.json no encontrado en static/data/. La página se cargará sin productos.")
    return render_template("jumbo.html", productos=productos, username=username)

@app.route('/santaisabel')
def santaisabel():
    print("[DEBUG] Accediendo a Santa Isabel.")
    username = session.get('username', 'Invitado')
    productos = [] # Inicializa como lista vacía
    try:
        with open("static/data/productos_santa_isabel_selenium.json", "r", encoding="utf-8") as f:
            productos = json.load(f)
    except FileNotFoundError:
        print("[ERROR] Archivo productos_santa_isabel_selenium.json no encontrado en static/data/. La página se cargará sin productos.")
    return render_template("santaisabel.html", productos=productos, username=username)

@app.route('/unimarc')
def unimarc():
    print("[DEBUG] Accediendo a Unimarc.")
    username = session.get('username', 'Invitado')
    productos = [] # Inicializa como lista vacía
    try:
        with open("static/data/productos_unimarc.json", "r", encoding="utf-8") as f:
            productos = json.load(f)
    except FileNotFoundError:
        print("[ERROR] Archivo productos_unimarc.json no encontrado en static/data/. La página se cargará sin productos.")
    return render_template("unimarc.html", productos=productos, username=username)

@app.route('/tottus')
def tottus():
    print("[DEBUG] Accediendo a Tottus.")
    username = session.get('username', 'Invitado')
    productos = [] # Inicializa como lista vacía
    try:
        with open("static/data/productos_tottus.json", "r", encoding="utf-8") as f:
            productos = json.load(f)
    except FileNotFoundError:
        print("[ERROR] Archivo productos_tottus.json no encontrado en static/data/. La página se cargará sin productos.")
    return render_template("tottus.html", productos=productos, username=username)

@app.route('/mayorista10')
def mayorista10():
    print("[DEBUG] Accediendo a Mayorista 10.")
    username = session.get('username', 'Invitado')
    productos = [] # Inicializa como lista vacía
    try:
        with open("static/data/productos_mayorista10.json", "r", encoding="utf-8") as f:
            productos = json.load(f)
    except FileNotFoundError:
        print("[ERROR] Archivo productos_mayorista10.json no encontrado en static/data/. La página se cargará sin productos.")
    return render_template("mayorista10.html", productos=productos, username=username)

@app.route('/alvi')
def alvi():
    print("[DEBUG] Accediendo a Alvi.")
    username = session.get('username', 'Invitado')
    productos = [] # Inicializa como lista vacía
    try:
        with open("static/data/productos_alvi.json", "r", encoding="utf-8") as f:
            productos = json.load(f)
    except FileNotFoundError:
        print("[ERROR] Archivo productos_alvi.json no encontrado en static/data/. La página se cargará sin productos.")
    return render_template("alvi.html", productos=productos, username=username)

@app.route('/oxxo')
def oxxo():
    print("[DEBUG] Accediendo a Oxxo.")
    username = session.get('username', 'Invitado')
    productos = [] # Inicializa como lista vacía
    try:
        with open("static/data/productos_oxxo.json", "r", encoding="utf-8") as f:
            productos = json.load(f)
    except FileNotFoundError:
        print("[ERROR] Archivo productos_oxxo.json no encontrado en static/data/. La página se cargará sin productos.")
    return render_template("oxxo.html", productos=productos, username=username)

"""para pruebas"""
@app.route('/ofertas')
def ofertas():
    print("[DEBUG] Accediendo a Ofertas.")
    username = session.get('username', 'Invitado') # Pasa el username a la plantilla
    productos = [] # Inicializa como lista vacía
    try:
        with open("static/data/productos_santa_isabel_selenium.json", "r", encoding="utf-8") as f:
            productos = json.load(f)
    except FileNotFoundError:
        print("[ERROR] Archivo productos_santa_isabel_selenium.json no encontrado en static/data/ para /ofertas. La página se cargará sin productos.")
    return render_template("ofertas.html", productos=productos, username=username)

# Ruta para la página de login
@app.route('/login', endpoint='login')
def login_page():
    print("[DEBUG] Accediendo a la página de login.")
    # Si el usuario ya está logueado y intenta ir a /login, redirigirlo a home
    if 'user_id' in session:
        print("[DEBUG] Usuario ya autenticado, redirigiendo a home.")
        return redirect(url_for('home'))
    return render_template('login.html')

# Ruta para 'Mi Cuenta'
@app.route('/mi_cuenta')
def mi_cuenta():
    print("[DEBUG] Accediendo a la página de 'Mi Cuenta'.")
    # Proteger esta ruta: si no hay sesión, redirigir al login
    if 'user_id' not in session:
        print("[DEBUG] Usuario no autenticado intentó acceder a 'Mi Cuenta'. Redirigiendo a login.")
        return redirect(url_for('login'))

    username = session.get('username')
    # Aquí podrías obtener más datos del usuario de la DB si los necesitas
    # user_info = Usuario.query.get(session['user_id'])
    # ... y pasarlos a la plantilla

    return render_template('mi_cuenta.html', username=username)

# Bloque de ejecución principal
if __name__ == "__main__":
    with app.app_context():
        # Crea las tablas de la base de datos si no existen
        db.create_all()
        print("[DEBUG] Se verificó la creación de tablas en la base de datos.")
    
    # --- Solución temporal para el problema de sesión iniciada al inicio (solo para depuración) ---
    # Este bloque solo debería usarse durante el desarrollo.
    # En producción, no querrías borrar las sesiones al reiniciar el servidor.
    with app.test_request_context(): 
        session.clear()
        print("[DEBUG] Sesión limpiada al iniciar la aplicación (solo para depuración).")
    # --- Fin de la solución temporal ---

    print("[DEBUG] La aplicación Flask está iniciando en modo depuración.")
    app.run(debug=True) # Ejecuta la aplicación en modo depuración (no usar en producción)