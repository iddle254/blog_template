from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor, CKEditorField
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Table, Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, EmailField, PasswordField
from wtforms.validators import DataRequired
from flask_gravatar import Gravatar
from functools import wraps
import bleach
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap(app)

##CONNECT TO DB
app.config['DATABASE_URL1'] = 'postgresql://zojdjexcsjoszw:be7ade603d7dd95f7896c803f39f4c0ac047b25dc1d4b423c4d94551497a0634@ec2-52-73-155-171.compute-1.amazonaws.com:5432/d8f9fel7q0ecbq'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL1",  "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = 'login.html'
login_manager.init_app(app)


##models
class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
    blog_posts = relationship("BlogPost", back_populates="user")
    comments = relationship("Comment", back_populates="user")

##CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(250), nullable=False)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    #one to many
    comments = relationship("Comment", back_populates="blog_posts")
    #many to one
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship("User", back_populates="blog_posts")

##CONFIGURE TABLES
class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    comment = db.Column(db.Text, nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship("User", back_populates="comments")
    blogpost_id = Column(Integer, ForeignKey('blog_posts.id'))
    blog_posts = relationship("BlogPost", back_populates="comments")

db.create_all()

#forms
class RegisterForm(FlaskForm):
    name = StringField('Enter your first name', validators=[DataRequired()])
    email = StringField('Enter your email', validators=[DataRequired()])
    password = PasswordField('Enter your password', validators=[DataRequired()])
    submit = SubmitField('Submit')

##WTForm
class CommentForm(FlaskForm):
    comment = CKEditorField("Your comment", validators=[DataRequired()])
    submit = SubmitField("Comment")


@login_manager.user_loader
def load_user(user_id):
    # since the user_id is just the primary key of our user table, use it in the query for the user
    return User.query.get(int(user_id))

#wrappers
def admin_only(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)

        return func(*args, **kwargs)
    return decorated_function

#routes
@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=["POST", "GET"])
async def register():
    form = RegisterForm()
    if form.validate_on_submit():
        # creates a row of data
        new_user = User()  # when creating the id is optional and can be autogenerated
        new_user.name = form.name.data
        new_user.email = form.email.data
        new_user.password = form.password.data

        user = User.query.filter_by(
            email=new_user.email).first()  # if this returns a user, then the email already exists in database
        if not user:
            new_user.password = generate_password_hash(new_user.password, method='pbkdf2:sha256', salt_length=8)

            # to enter the data into the database
            db.session.add(new_user)
            db.session.commit()

            login_user(new_user)
            name = current_user.name

            return redirect(url_for('get_all_posts', name=name))
        else:
            flash('A user with that email address already exists')
            return redirect(url_for('login'))

    return render_template("register.html", form=form)


class LoginForm(FlaskForm):
    email = StringField('Enter your email', validators=[DataRequired()])
    password = PasswordField('Enter your password', validators=[DataRequired()])
    submit = SubmitField('Submit')

@app.route('/login', methods=['POST', 'GET'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        user = User.query.filter_by(email=email).first()

        # check if the user actually exists
        # take the user-supplied password, hash it, and compare it to the hashed password in the database
        if not user or not check_password_hash(user.password, password):
            flash('Please check your login details and try again.')
            return redirect(url_for('login'))  # if the user doesn't exist or password is wrong, reload the page
            # if the above check passes, then we know the user has the right credentials
        login_user(user)
        return redirect(url_for('get_all_posts'))
    return render_template('login.html', form=form)

@login_required
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))

def get_comments():
    return db.session.query(Comment).all()

## strips invalid tags/attributes
def strip_invalid_html(content):
    allowed_tags = ['a', 'abbr', 'acronym', 'address', 'b', 'br', 'div', 'dl', 'dt',
                    'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img',
                    'li', 'ol', 'p', 'pre', 'q', 's', 'small', 'strike',
                    'span', 'sub', 'sup', 'table', 'tbody', 'td', 'tfoot', 'th',
                    'thead', 'tr', 'tt', 'u', 'ul']

    allowed_attrs = {
        'a': ['href', 'target', 'title'],
        'img': ['src', 'alt', 'width', 'height'],
    }

    cleaned = bleach.clean(content,
                           tags=allowed_tags,
                           attributes=allowed_attrs,
                           strip=True)

    return cleaned

@app.route("/post/<int:post_id>", methods=["POST", "GET"])
def show_post(post_id):
    form = CommentForm()
    requested_post = BlogPost.query.get(post_id)
    comments = get_comments()
    if form.validate_on_submit():
        comment = strip_invalid_html(form.comment.data)
        new_comment = Comment(comment=comment)
        # to enter the data into the database
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for('show_post', post_id=post_id))

    return render_template("post.html", post=requested_post, form=form, comments=comments, gravatar=Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")

@login_required
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user.name,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)

@login_required
@app.route("/edit-post/<int:post_id>")
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )

    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)

@login_required
@admin_only
@app.route("/delete/<int:post_id>")
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
