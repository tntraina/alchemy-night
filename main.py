
import os
import json

from dotenv import load_dotenv

from flask import Flask, render_template, url_for, redirect, session, request
from authlib.integrations.flask_client import OAuth
from database import db, User, Poll, Choice, Vote, Tag

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
    print(f"DEBUG: User is {user}")

    # Polls created by the user
    user_polls = Poll.query.filter_by(user_id=user.id).all()
    print(f"DEBUG: Polls are {user_polls}")

    # Polls the user can vote in (not created by them and not yet voted in)
#   voted_poll_ids = [v.choice.poll_id for v in user.votes]

#    votable_polls = Poll.query.filter(
#        Poll.user_id != user.id,
#        ~Poll.id.in_(voted_poll_ids)
#    ).all()

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
        data = request.get_json()
        poll_name = data.get("title")
        options = data.get("questions")

        print(poll_name)
        print(options)
        print(user)

        new_poll = Poll(question=poll_name, user_id=user.id)

        db.session.add(new_poll)

        for choice_text in options:
            if choice_text:
                choice = Choice.query.filter_by(text=choice_text).first()
                if not choice:
                    choice = Choice(text=choice_text)
                    db.session.add(choice)
                new_poll.choices.append(choice)

        db.session.commit()

        return redirect(url_for('polls'))

    options = [getattr(x, 'text') for x in Choice.query.all()]
    tags = {}
    for ch in Choice.query.all():
        tags[ch.text] = [getattr(x, 'text') for x in ch.tags]

    xdata_lines = []

    xdata_lines.append("options: ['" + "', '".join(options) + "'],")
    xdata_lines.append("tags : {")
    for tk, tv in tags.items():
        xdata_lines.append(f"'{tk}': ['" + "', '".join(tv) + "'],")

    xdata_lines.append("}")

    final_xdata = "\n".join(xdata_lines)

    return render_template("create_poll.html", xdata=final_xdata)




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
    app.run(host='0.0.0.0', port=8080, debug=True)

if __name__ == "__main__":
    main()
