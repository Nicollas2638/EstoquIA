from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from flask_mysqldb import MySQL
import MySQLdb.cursors
from chat_logic import processar_mensagem

app = Flask(__name__)
app.secret_key = 'senha123'

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'estoquia'

mysql = MySQL(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

class Usuario(UserMixin):
    def __init__(self, id, nome, email, nivel):
        self.id = id
        self.nome = nome
        self.email = email
        self.nivel = nivel

@login_manager.user_loader
def load_user(user_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM usuarios WHERE id = %s', (user_id,))
    usuario = cursor.fetchone()
    if usuario:
        return Usuario(usuario['id'], usuario['nome'], usuario['email'], usuario['nivel'])
    return None

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM usuarios WHERE email = %s', (email,))
        usuario = cursor.fetchone()

        if usuario and usuario['senha'] == senha:
            user = Usuario(usuario['id'], usuario['nome'], usuario['email'], usuario['nivel'])
            login_user(user)
            return redirect(url_for('painel_operador'))
        else:
            flash('Credenciais inválidas.', 'danger')

    return render_template('login.html')

@app.route('/painel-operador')
@login_required
def painel_operador():
    return render_template('index.html', nome=current_user.nome)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/mensagem', methods=['POST'])
@login_required
def mensagem():
    texto = request.json.get('mensagem')
    user_id = current_user.id

    cursor = mysql.connection.cursor()
    cursor.execute("INSERT INTO mensagens (usuario_id, remetente, mensagem) VALUES (%s, %s, %s)", (user_id, 'usuario', texto))
    mysql.connection.commit()

    resposta = processar_mensagem(texto, user_id, mysql)

    cursor.execute("INSERT INTO mensagens (usuario_id, remetente, mensagem) VALUES (%s, %s, %s)", (user_id, 'bot', resposta))
    mysql.connection.commit()

    return jsonify({'resposta': resposta})

@app.route('/historico')
@login_required
def historico():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
        SELECT remetente, mensagem, DATE_FORMAT(data, '%%d/%%m/%%Y %%H:%%i:%%s') as data
        FROM mensagens
        WHERE usuario_id = %s
        ORDER BY data DESC
        LIMIT 10
    """, (current_user.id,))
    mensagens = cursor.fetchall()
    return jsonify(mensagens)

if __name__ == '__main__':
    app.run(debug=True)
