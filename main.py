import os
<<<<<<< HEAD

from flask import Flask, send_file

app = Flask(__name__)

@app.route("/")
def index():
    return send_file('src/index.html')

def main():
    app.run(port=int(os.environ.get('PORT', 80)))
=======
from dotenv import load_dotenv

from flask import Flask, render_template, url_for, redirect, session, request
from authlib.integrations.flask_client import OAuth
from database import db, User, Poll, Choice, Vote, LibraryOption, LibraryOptionTag

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///project.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['GOOGLE_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET')

db.init_app(app)

with app.app_context():
    db.create_all()

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=app.config["GOOGLE_CLIENT_ID"],
    client_secret=app.config["GOOGLE_CLIENT_SECRET"],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

@app.route("/")
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    redirect_uri = url_for('auth', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/auth')
def auth():
    token = google.authorize_access_token()
    user_info = token['userinfo']
    session['user'] = user_info
    
    user = User.query.filter_by(username=user_info['email']).first()
    if not user:
        user = User(username=user_info['email'])
        db.session.add(user)
        db.session.commit()
        
    return redirect('/')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

@app.route("/polls")
def polls():
    if 'user' not in session:
        return redirect(url_for('login'))

    user_info = session['user']
    user = User.query.filter_by(username=user_info['email']).first()

    # Polls created by the user
    user_polls = Poll.query.filter_by(user_id=user.id).all()

    # Polls the user can vote in (not created by them and not yet voted in)
    voted_poll_ids = [v.choice.poll_id for v in user.votes]

    votable_polls = Poll.query.filter(
        Poll.user_id != user.id,
        ~Poll.id.in_(voted_poll_ids)
    ).all()

    return render_template("polls.html", user_polls=user_polls, votable_polls=votable_polls)

@app.route('/polls/<int:poll_id>')
def poll_view(poll_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    poll = Poll.query.get_or_404(poll_id)
    user_info = session['user']
    user = User.query.filter_by(username=user_info['email']).first()

    user_has_voted = Vote.query.join(Choice).filter(
        Vote.user_id == user.id,
        Choice.poll_id == poll_id
    ).first() is not None

    return render_template('poll_view.html', poll=poll, user_has_voted=user_has_voted)

@app.route("/create_poll", methods=["GET", "POST"])
def create_poll():
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == "POST":
        user_info = session['user']
        user = User.query.filter_by(username=user_info['email']).first()
        question = request.form.get("question")
        
        if not question:
            return "Question is required.", 400

        new_poll = Poll(question=question, user_id=user.id)
        db.session.add(new_poll)

        choices = request.form.getlist("choice")
        library_choices = request.form.getlist("library_choice")

        all_choices = choices + library_choices

        for choice_text in all_choices:
            if choice_text:
                new_choice = Choice(text=choice_text, poll=new_poll)
                db.session.add(new_choice)
        
        db.session.commit()
        return redirect(url_for('polls'))

    library_options = LibraryOption.query.all()
    return render_template("create_poll.html", library_options=library_options)

@app.route("/add_library_option", methods=["POST"])
def add_library_option():
    if 'user' not in session:
        return redirect(url_for('login'))

    option_text = request.form.get("option_text")
    if option_text and not LibraryOption.query.filter_by(text=option_text).first():
        new_option = LibraryOption(text=option_text)
        db.session.add(new_option)
        db.session.commit()

    return redirect(url_for('create_poll'))

def main():
    # Use 127.0.0.1 and a specific port for local development
    app.run(host='127.0.0.1', port=8080, debug=True)
>>>>>>> 822b8b5 (Initial commit to overwrite FirebaseStudio repo)

if __name__ == "__main__":
    main()
