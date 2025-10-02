"""
Web application for viewing gym capacity data
"""

from flask import Flask, render_template, jsonify, request
from database import GymDatabase
import json
from datetime import datetime, timedelta
import config
import logging
import os
from gym_capacity_logger import PlanetFitnessLogger
import threading

app = Flask(__name__)

# Setup logging for web app
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('WebApp')

# Initialize database with absolute path
db = GymDatabase()
logger.info(f"Database initialized at: {db.db_path}")

# Track ongoing fetch operations
fetch_in_progress = False
last_fetch_result = None


@app.route('/')
def dashboard():
    """Main dashboard showing current gym capacities"""
    return render_template('dashboard.html')


@app.route('/api/current-capacity')
def api_current_capacity():
    """API endpoint for current capacity data"""
    try:
        data = db.get_latest_capacity_data()
        # Sort by capacity (highest to lowest)
        data.sort(key=lambda x: x['users_count'], reverse=True)
        return jsonify({
            'status': 'success',
            'data': data,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/gym-history/<gym_name>')
def api_gym_history(gym_name):
    """API endpoint for gym historical data"""
    try:
        # Check if custom date range is provided
        date_from = request.args.get('from')
        date_to = request.args.get('to')
        
        if date_from and date_to:
            # Use custom date range
            data = db.get_gym_history_by_date_range(gym_name, date_from, date_to)
        else:
            # Use days parameter
            days = request.args.get('days', 7, type=int)
            data = db.get_gym_history(gym_name, days)
        
        return jsonify({
            'status': 'success',
            'gym_name': gym_name,
            'data': data
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/stats')
def api_stats():
    """API endpoint for database statistics"""
    try:
        days = request.args.get('days', 7, type=int)
        my_gyms_only = request.args.get('my_gyms', 'false').lower() == 'true'
        
        if my_gyms_only:
            stats = db.get_capacity_stats(days, gym_names=config.MY_GYMS)
        else:
            stats = db.get_capacity_stats(days)
        
        return jsonify({
            'status': 'success',
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/gyms')
def api_gyms():
    """API endpoint for list of all gyms"""
    try:
        gyms = db.get_all_gyms()
        return jsonify({
            'status': 'success',
            'gyms': gyms
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/gym/<gym_name>')
def gym_detail(gym_name):
    """Detailed view for a specific gym"""
    # Check for enhanced parameter to use new template
    use_enhanced = request.args.get('enhanced', 'true').lower() == 'true'
    template = 'gym_detail_enhanced.html' if use_enhanced else 'gym_detail.html'
    return render_template(template, gym_name=gym_name)


@app.route('/api/force-fetch', methods=['POST'])
def api_force_fetch():
    """API endpoint to manually trigger data collection"""
    global fetch_in_progress, last_fetch_result

    if fetch_in_progress:
        return jsonify({
            'status': 'error',
            'message': 'A fetch operation is already in progress. Please wait...'
        }), 429

    # Try to get credentials from database first, fall back to environment variables
    creds = db.get_credentials()
    if creds:
        email = creds['email']
        password = creds['password']
    else:
        email = os.getenv('PF_EMAIL')
        password = os.getenv('PF_PASSWORD')

    if not email or not password or email == 'your-email@example.com':
        return jsonify({
            'status': 'error',
            'message': 'Please configure your Planet Fitness credentials in Settings first'
        }), 400

    def fetch_data_async():
        """Run the data fetch in a background thread"""
        global fetch_in_progress, last_fetch_result

        try:
            logger.info("Manual data fetch triggered from web UI")
            pf_logger = PlanetFitnessLogger()
            success = pf_logger.run_data_collection(email, password, triggered_by='manual')

            last_fetch_result = {
                'success': success,
                'timestamp': datetime.now().isoformat(),
                'message': 'Data collection completed successfully' if success else 'Data collection failed'
            }

            logger.info(f"Manual fetch completed: {last_fetch_result['message']}")

        except Exception as e:
            logger.error(f"Error during manual fetch: {e}")
            last_fetch_result = {
                'success': False,
                'timestamp': datetime.now().isoformat(),
                'message': f'Error: {str(e)}'
            }
        finally:
            fetch_in_progress = False

    # Start the fetch in a background thread
    fetch_in_progress = True
    thread = threading.Thread(target=fetch_data_async, daemon=True)
    thread.start()

    return jsonify({
        'status': 'success',
        'message': 'Data fetch started. This may take a few seconds...'
    })


@app.route('/api/fetch-status')
def api_fetch_status():
    """API endpoint to check the status of the last fetch operation"""
    global fetch_in_progress, last_fetch_result

    return jsonify({
        'status': 'success',
        'fetch_in_progress': fetch_in_progress,
        'last_result': last_fetch_result
    })


@app.route('/api/credentials', methods=['GET', 'POST', 'DELETE'])
def api_credentials():
    """API endpoint to manage Planet Fitness credentials"""
    if request.method == 'GET':
        # Check if credentials exist (don't return the actual password)
        has_creds = db.has_credentials()
        creds = db.get_credentials() if has_creds else None

        return jsonify({
            'status': 'success',
            'has_credentials': has_creds,
            'email': creds['email'] if creds else None
        })

    elif request.method == 'POST':
        # Save credentials
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({
                'status': 'error',
                'message': 'Email and password are required'
            }), 400

        success = db.save_credentials(email, password)

        if success:
            logger.info(f"Credentials saved for email: {email}")
            return jsonify({
                'status': 'success',
                'message': 'Credentials saved successfully'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to save credentials'
            }), 500

    elif request.method == 'DELETE':
        # Delete credentials
        success = db.delete_credentials()

        if success:
            logger.info("Credentials deleted")
            return jsonify({
                'status': 'success',
                'message': 'Credentials deleted successfully'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to delete credentials'
            }), 500


@app.route('/settings')
def settings():
    """Settings page for managing credentials"""
    return render_template('settings.html')


@app.route('/api/scheduler-info')
def api_scheduler_info():
    """API endpoint to get scheduler information"""
    interval = int(os.getenv('LOG_INTERVAL', '15'))
    last_sync = db.get_last_successful_sync()

    return jsonify({
        'status': 'success',
        'interval_minutes': interval,
        'interval_formatted': f"{interval} minutes" if interval != 1 else "1 minute",
        'scheduler_running': True,
        'last_successful_sync': last_sync
    })


@app.route('/api/sync-history')
def api_sync_history():
    """API endpoint to get sync history"""
    limit = request.args.get('limit', 20, type=int)
    history = db.get_sync_history(limit=limit)

    return jsonify({
        'status': 'success',
        'history': history
    })


if __name__ == '__main__':
    # Get configuration from environment variables
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', '5000'))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

    print(f"🚀 Starting Planet Fitness Tracker...")
    print(f"📊 Dashboard will be available at: http://{host}:{port}")
    app.run(debug=debug, host=host, port=port)