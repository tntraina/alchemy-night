from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)

class Poll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('polls', lazy=True))
    choices = db.relationship('Choice', secondary=poll_choices, lazy='subquery', backref=db.backref('polls', lazy=True))

choice_tags = db.Table('choice_tags',
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True),
    db.Column('choice_id', db.Integer, db.ForeignKey('choice.id'), primary_key=True)
)

poll_choices = db.Table('poll_choices',
    db.Column('poll_id', db.Integer, db.ForeignKey('poll.id'), primary_key=True),
    db.Column('choice_id', db.Integer, db.ForeignKey('choice.id'), primary_key=True)
)

class Choice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(100), nullable=False)
    tags = db.relationship('Tag', secondary=choice_tags, lazy='subquery',
        backref=db.backref('choices', lazy=True))

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    choice_id = db.Column(db.Integer, db.ForeignKey('choice.id'), nullable=False)
    rank = db.Column(db.Integer, nullable=False)
    user = db.relationship('User', backref=db.backref('votes', lazy=True))
    choice = db.relationship('Choice', backref=db.backref('votes', lazy=True))

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(100), nullable=False, unique=True)
