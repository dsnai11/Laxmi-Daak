from app import create_app, socketio

# The app uses Socket.IO async_mode='threading' (see app/__init__.py), so no
# eventlet monkey-patching here: eventlet isn't installed, and patching on top of
# threading mode lets blocking calls (SQLite, bcrypt, SMTP) freeze the whole server.
app = create_app()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
