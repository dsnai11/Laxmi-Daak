from app import create_app, socketio

# AWS Elastic Beanstalk looks for 'application' variable by default
application = create_app()

if __name__ == '__main__':
    socketio.run(application, host='0.0.0.0', port=5001, debug=True, allow_unsafe_werkzeug=True)
