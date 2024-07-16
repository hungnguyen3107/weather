from flask import Flask, request, jsonify, render_template, url_for, session
from flask_cors import CORS
from services.weather_service import WeatherService
from utils.email_service import EmailService
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
import logging
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
from flask_session import Session
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Cấu hình Gmail SMTP server với mật khẩu ứng dụng
app.config['MAIL_SERVER'] = os.getenv('EMAIL_HOST')
app.config['MAIL_PORT'] = int(os.getenv('EMAIL_PORT'))
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_HOST_USER')
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_HOST_PASSWORD')
app.config['MAIL_USE_TLS'] = os.getenv('EMAIL_USE_TLS') == 'True'
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('EMAIL_HOST_USER')  # Thêm dòng này

mail = Mail(app)

app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = 'supersecretkey'
Session(app)

# Cấu hình SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///subscribers.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Khởi tạo EmailService
email_service = EmailService(app)
logging.basicConfig(level=logging.DEBUG)

api_key = "053caec69c8d49df998224235241607"
weather_service = WeatherService(api_key)  # Initialize the WeatherService

class Subscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/weather', methods=['POST'])
def get_weather():
    data = request.get_json()
    location = data.get('location')
    page = int(data.get('page', 1))  # Ensure page is an integer, default to 1
    
    # Example: Assuming weather_data contains your weather API response
    weather_data = weather_service.get_weather_data(location)
    
    if not weather_data:
        return jsonify({'error': 'Weather data not available'}), 404
    
    forecast_days = weather_data['forecast']['forecastday']
    start_index = (page - 1) * 4
    end_index = start_index + 5
    
    if start_index >= len(forecast_days):
        return jsonify({'error': 'No more forecast data available'}), 404
    
    forecast_data = forecast_days[start_index:end_index]
    
    return jsonify({
        'location': weather_data['location'],
        'current': weather_data['current'],
        'forecast': {
            'forecastday': forecast_data
        }
    })


@app.route('/weather/history', methods=['GET'])
def weather_history():
    try:
        if 'weather_data' in session and session['weather_data']:
            weather_data = session['weather_data']
            app.logger.info(f"Retrieved weather history data: {weather_data}")
            return jsonify(weather_data)
        else:
            app.logger.warning("No weather history data found in session")
            return jsonify([])
    except Exception as e:
        app.logger.error(f"Error fetching weather history: {str(e)}")
        return jsonify({'error': 'Failed to load weather history'}), 500


@app.route('/subscribe', methods=['POST'])
def subscribe():
    data = request.get_json()
    email = data.get('email')
    location = data.get('location')

    if email and location:
        # Kiểm tra xem email đã tồn tại chưa
        existing_subscriber = Subscriber.query.filter_by(email=email).first()
        if existing_subscriber:
            return jsonify({"message": "Email already subscribed!"}), 200
        
        # Thêm email vào cơ sở dữ liệu
        new_subscriber = Subscriber(email=email)
        db.session.add(new_subscriber)
        db.session.commit()
        
        # Gửi email thông báo
        subject = "Subscription Confirmation"
        weather_data = weather_service.get_weather_data(location)
        if weather_data:
            forecast_info = "4-Day Forecast:\n"
            for day in weather_data['forecast']['forecastday']:
                forecast_info += f"Date: {day['date']}\nTemperature: {day['day']['avgtemp_c']}°C\nCondition: {day['day']['condition']['text']}\n\n"
            wind_speed = weather_data['current']['wind_kph']
            humidity = weather_data['current']['humidity']
            message = f"You have subscribed to weather updates for {location}.\n\nHere is the weather forecast:\n\n{forecast_info}\nWind Speed: {wind_speed} km/h\nHumidity: {humidity}%"
        else:
            message = f"You have subscribed to weather updates for {location}, but weather data could not be retrieved at this moment."
        
        logging.debug(f"Attempting to send email to {email}")
        email_service.send_email(subject, [email], message)
        logging.debug(f"Email sent to {email}")
        return jsonify({"message": "Subscription successful!"}), 200
    else:
        logging.error("Invalid input: email or location missing")
        return jsonify({"error": "Invalid input"}), 400



@app.route('/confirm', methods=['GET'])
def confirm_email():
    email = request.args.get('email')
    location = request.args.get('location')
    if not email:
        return render_template('confirmation.html', message='Invalid or expired link')

    existing_subscriber = Subscriber.query.filter_by(email=email).first()
    if existing_subscriber:
        logging.debug(f"Email {email} already confirmed")
        return render_template('confirmation.html', message='Email already confirmed')

    try:
        new_subscriber = Subscriber(email=email)
        db.session.add(new_subscriber)
        db.session.commit()
        
        logging.debug(f"New subscriber added: {email}")

        # Gửi email chào mừng và thông tin dự báo thời tiết
        weather_data = weather_service.get_weather_data(location)
        if weather_data:
            forecast_info = "4-Day Forecast:\n"
            for day in weather_data['forecast']['forecastday']:
                forecast_info += f"Date: {day['date']}\nTemperature: {day['day']['avgtemp_c']}°C\nCondition: {day['day']['condition']['text']}\n\n"
            wind_speed = weather_data['current']['wind_kph']
            humidity = weather_data['current']['humidity']
            email_body = f'Thank you for subscribing to our service!\n\nHere is the weather forecast for {location}:\n{forecast_info}\nWind Speed: {wind_speed} km/h\nHumidity: {humidity}%'
        else:
            email_body = f'Thank you for subscribing to our service!\n\nWeather data could not be retrieved.'

        logging.debug(f"Sending welcome email to: {email}")
        email_service.send_email('Welcome!', [email], email_body)
        logging.debug("Welcome email sent successfully")

        return render_template('confirmation.html', message='Subscription confirmed')
    except Exception as e:
        logging.error(f"Error during email confirmation: {str(e)}")
        return render_template('confirmation.html', message='An error occurred during confirmation')



@app.route('/unsubscribe', methods=['POST'])
def unsubscribe():
    try:
        data = request.get_json()
        email = data.get('email')

        if not email:
            logging.debug('Email not provided')
            return jsonify({'error': 'Email not provided'}), 400

        subscriber = Subscriber.query.filter_by(email=email).first()
        if not subscriber:
            logging.debug(f"Email {email} not found in subscription list")
            return jsonify({'error': 'Email not found in subscription list'}), 400

        logging.debug(f"Deleting subscriber: {email}")
        db.session.delete(subscriber)
        db.session.commit()

        subject = "Unsubscription Confirmation"
        message = f"You have been successfully unsubscribed from weather updates.\n\nDetails:\nEmail: {email}"
        msg = Message(subject, recipients=[email], body=message)
        
        try:
            mail.send(msg)
            logging.info(f"Unsubscribe confirmation email sent to {email}")
        except Exception as e:
            logging.error(f"Failed to send unsubscribe confirmation email to {email}: {str(e)}")

        return jsonify({'message': 'Unsubscribed successfully'}), 200

    except Exception as e:
        logging.error(f"Error during unsubscribe: {str(e)}")
        return jsonify({'error': 'An error occurred during unsubscription'}), 500





# Gửi email hàng ngày cho các subscriber
def send_daily_emails():
    subscribers = Subscriber.query.all()
    for subscriber in subscribers:
        email = subscriber.email
        location = subscriber.location  # Giả sử bạn đã lưu trữ vị trí người dùng trong cơ sở dữ liệu
        weather_data = weather_service.get_weather_data(location)
        if weather_data:
            forecast_info = "4-Day Forecast:\n"
            for day in weather_data['forecast']['forecastday']:
                forecast_info += f"Date: {day['date']}\nTemperature: {day['day']['avgtemp_c']}°C\nCondition: {day['day']['condition']['text']}\n\n"
            wind_speed = weather_data['current']['wind_kph']
            humidity = weather_data['current']['humidity']
            email_body = f'Good morning! Here is the weather forecast for {location}:\n\n{forecast_info}\nWind Speed: {wind_speed} km/h\nHumidity: {humidity}%'
            email_service.send_email('Daily Weather Forecast', [email], email_body)
        else:
            email_body = f'Good morning! Unfortunately, weather data for {location} could not be retrieved at this time.'
            email_service.send_email('Daily Weather Forecast', [email], email_body)


# Lập lịch để gửi email hàng ngày
scheduler = BackgroundScheduler()
scheduler.add_job(func=send_daily_emails, trigger="interval", days=1)
scheduler.start()

# Đảm bảo scheduler được dừng khi ứng dụng dừng
atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Tạo bảng nếu chưa tồn tại
    app.run(debug=True)
