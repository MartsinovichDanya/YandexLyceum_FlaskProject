from flask import Flask, render_template, redirect, session
import json

from Forms import LoginForm, AddNoteForm, RegistrationForm, ParamForm, MoreButton
from Models import UserModel, NoteModel, ParamModel, VacModel
from DB import DB
from API_kicker import get_vac, count_sred_zp
from emailer import send_email

from Alice import main

app = Flask(__name__)
app.config['SECRET_KEY'] = 'yandexlyceum_secret_key'
db = DB('jfe.db')


@app.route('/login', methods=['POST', 'GET'])
def login():
    if 'username' in session:
        return redirect('/index')
    form = LoginForm()
    if form.validate_on_submit():
        user_name = form.username.data
        password = form.password.data
        user_model = UserModel(db.get_connection())
        exists = user_model.exists(user_name, password)
        if exists[0]:
            session['username'] = user_name
            session['user_id'] = exists[1]
            session['admin_privilege'] = exists[2]
            return redirect("/index")
    return render_template('login.html', title='Авторизация', form=form)


@app.route('/logout')
def logout():
    session.pop('username', 0)
    session.pop('user_id', 0)
    session.pop('admin_privilege', 0)
    return redirect('/login')


@app.route('/registration', methods=['POST', 'GET'])
def registration():
    if 'username' in session:
        return redirect('/index')
    form = RegistrationForm()
    user_model = UserModel(db.get_connection())
    all_users = [el[1] for el in user_model.get_all()]
    with open("all_users.json", "w", encoding='utf8') as f:
        json.dump(all_users, f)
    if form.validate_on_submit():
        user_name = form.username.data
        password = form.password.data
        email = form.email.data
        user_model.insert(user_name, password, email)
        return redirect('/login')
    return render_template('registration.html', title='Регистрация', form=form)


@app.route('/notes', methods=['GET', 'POST'])
def notes():
    if 'username' not in session:
        return redirect('/login')
    form = AddNoteForm()
    nm = NoteModel(db.get_connection())
    notes_list = list(reversed(nm.get_all(session['user_id'])))
    if form.validate_on_submit():
        content = form.content.data
        nm.insert(content, session['user_id'])
        return redirect("/notes")
    return render_template('notes.html', username=session['username'],
                           notes=notes_list, title="Заметки", form=form)


@app.route('/delete_note/<int:note_id>', methods=['GET'])
def delete_note(note_id):
    if 'username' not in session:
        return redirect('/login')
    nm = NoteModel(db.get_connection())
    nm.delete(note_id)
    return redirect("/notes")


@app.route('/settings', methods=['POST', 'GET'])
def settings():
    if 'username' not in session:
        return redirect('/login')
    form = ParamForm()
    if form.validate_on_submit():
        search_words = form.search_words.data
        search_area = form.search_area.data
        pm = ParamModel(db.get_connection())
        if not pm.get(session['user_id']):
            pm.insert(search_words, search_area, session['user_id'])
        else:
            pm.update(search_words, search_area, session['user_id'])
        vm = VacModel(db.get_connection())
        vac_list = get_vac(search_words, search_area)
        for el in vac_list:
            vm.insert(*el, user_id=str(session['user_id']))
        return redirect('/index')
    return render_template('settings.html', title='Настройки поиска', form=form)


@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
def index():
    if 'username' not in session:
        return redirect('/login')
    form = MoreButton()
    pm = ParamModel(db.get_connection())
    if not pm.get(session['user_id']):
        return redirect('/settings')
    vm = VacModel(db.get_connection())
    vacancies_list = vm.get_all(str(session['user_id']))
    vacancies_list = sorted(vacancies_list, key=lambda n: -int(n[4].replace('-', '')))
    print(vacancies_list)
    if form.validate_on_submit():
        params = pm.get(session['user_id'])
        vac_list = get_vac(params[1], params[2])
        exist_vac = [el[1] for el in vm.get_all(str(session['user_id']))]
        for el in vac_list:
            if int(el[0]) not in exist_vac:
                vm.insert(*el, user_id=str(session['user_id']))
        return redirect('/index')
    return render_template('index.html', username=session['username'],
                           vacancies=vacancies_list, title="Главная", form=form)


@app.route('/delete_vacancy/<int:vac_id>', methods=['GET'])
def delete_vacancy(vac_id):
    if 'username' not in session:
        return redirect('/login')
    vm = VacModel(db.get_connection())
    vm.delete(vac_id)
    return redirect("/index")


@app.route('/admin')
def admin():
    if 'username' not in session:
        return redirect('/login')
    if not session['admin_privilege']:
        return redirect('/index')
    um = UserModel(db.get_connection())
    users = um.get_all()
    user_data = []
    for user in users:
        user_data.append((user[0], user[1], user[3]))
    return render_template('admin_page.html', username=session['username'],
                           users=user_data, title="Страница администратора")


@app.route('/delete_user/<int:user_id>', methods=['GET'])
def delete_user(user_id):
    if 'username' not in session:
        return redirect('/login')
    if not session['admin_privilege']:
        return redirect('/index')
    um = UserModel(db.get_connection())
    pm = ParamModel(db.get_connection())
    vm = VacModel(db.get_connection())
    nm = NoteModel(db.get_connection())
    um.delete(user_id)
    pm.delete_for_user(user_id)
    vm.delete_for_user(user_id)
    nm.delete_for_user(user_id)
    return redirect("/admin")


@app.route('/make_admin/<int:user_id>', methods=['GET'])
def make_admin(user_id):
    if 'username' not in session:
        return redirect('/login')
    if not session['admin_privilege']:
        return redirect('/index')
    um = UserModel(db.get_connection())
    um.make_admin(user_id)
    return redirect("/admin")


@app.route('/sred_zp', methods=['GET', 'POST'])
def sred_zp():
    if 'username' not in session:
        return redirect('/login')
    pm = ParamModel(db.get_connection())
    if not pm.get(session['user_id']):
        return redirect('/settings')
    params = pm.get(session['user_id'])
    data = [params[1], params[2], count_sred_zp(params[1], params[2])]
    return render_template('sred_zp.html', username=session['username'],
                           data=data, title="Рассчет средней З/П")


@app.route('/send_mail', methods=['GET'])
def send_mail():
    if 'username' not in session:
        return redirect('/login')
    um = UserModel(db.get_connection())
    vm = VacModel(db.get_connection())
    user_data = um.get(session['user_id'])
    vacancies = vm.get_all(str(session['user_id']))
    text = '\n'.join([f'{el[2]} - {el[5]}' for el in vacancies])
    send_email(user_data[4], text)
    return redirect('/index')


app.route('/post', methods=['POST'])(main)


if __name__ == '__main__':
    app.run(port=8080, host='127.0.0.1')
