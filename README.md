# Planet Fitness Tracker

A Python-based system for tracking and visualizing gym occupancy data from Planet Fitness locations in Australia. Features automated data collection, web dashboard, and Docker deployment.

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Flask](https://img.shields.io/badge/flask-2.3+-green.svg)
![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Features

- 🏋️ Automated gym capacity data collection every 15 minutes
- 📊 Real-time web dashboard with interactive charts
- 📈 Historical data tracking and analysis
- 🐳 Docker containerization for easy deployment
- 📱 Responsive design for mobile and desktop
- 🗄️ SQLite database with JSON/CSV export options
- 🔄 Automatic retry logic for API failures

## Quick Start with Docker

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/planet-fitness-tracker.git
cd planet-fitness-tracker
```

2. **Run with Docker Compose**
```bash
docker-compose up -d
```

3. **Access the dashboard**
Open http://localhost:5000 in your browser

4. **Configure credentials**
- Navigate to the **Settings** page
- Enter your Planet Fitness email and password
- Click "Save Credentials"
- The scheduler will automatically start collecting data

## Manual Installation

### Prerequisites
- Python 3.9+
- Planet Fitness account

### Setup

1. **Install dependencies**
```bash
pip install -r requirements.txt
```

2. **Run the scheduler**
```bash
python scheduler.py
```

3. **Start the web dashboard**
In a separate terminal:
```bash
python web_app.py
```

4. **Configure credentials**
- Open http://localhost:5000 in your browser
- Navigate to the **Settings** page
- Enter your Planet Fitness email and password
- Click "Save Credentials"

## Configuration

### Credentials Setup

Planet Fitness credentials can be configured in two ways:

#### Option 1: Web Interface (Recommended)
1. Start the application
2. Navigate to **Settings** page from the dashboard
3. Enter your Planet Fitness email and password
4. Click "Save Credentials"

Credentials are stored securely in the SQLite database (`credentials` table) and persist between restarts.

#### Option 2: Environment Variables (Fallback)
If no credentials are found in the database, the application will use environment variables:

```bash
export PF_EMAIL="your-email@example.com"
export PF_PASSWORD="your-password"
```

Or create a `.env` file:
```bash
cp .env.example .env
# Edit .env with your credentials
```

**Note:** Database credentials take priority over environment variables.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PF_EMAIL` | Planet Fitness login email (fallback) | Optional |
| `PF_PASSWORD` | Planet Fitness password (fallback) | Optional |
| `LOG_INTERVAL` | Data collection interval (minutes) | 15 |
| `FLASK_HOST` | Web server host | 0.0.0.0 |
| `FLASK_PORT` | Web server port | 5000 |

### Tracked Gyms

By default, the system tracks all available Planet Fitness locations. To track specific gyms only, modify the `MY_GYMS` list in `config.py`:

```python
MY_GYMS = ['BETHANIA', 'Springwood']  # Your preferred gyms
```

## Project Structure

```
gym-capacity-logger/
├── gym_capacity_logger.py  # Core data collection logic
├── scheduler.py            # Scheduling service
├── web_app.py             # Flask web application
├── database.py            # Database operations
├── config.py              # Configuration settings
├── templates/             # HTML templates
│   ├── dashboard.html
│   └── gym_detail_enhanced.html
├── static/               # CSS and JavaScript
├── Dockerfile            # Docker image definition
├── docker-compose.yml    # Docker Compose configuration
└── docker-entrypoint.sh  # Container startup script
```

## API Endpoints

The web application provides several REST API endpoints:

### Data Endpoints
- `GET /api/current-capacity` - Current capacity for all gyms
- `GET /api/gym-history/<gym_name>` - Historical data for specific gym
- `GET /api/stats` - Database statistics
- `GET /api/gyms` - List of all tracked gyms

### Credentials Management
- `GET /api/credentials` - Check if credentials are configured (returns email, not password)
- `POST /api/credentials` - Save/update credentials (JSON: `{email, password}`)
- `DELETE /api/credentials` - Delete stored credentials

### Data Collection
- `POST /api/force-fetch` - Manually trigger data collection
- `GET /api/fetch-status` - Check status of ongoing/last fetch operation
- `GET /api/scheduler-info` - Get scheduler configuration and status
- `GET /api/sync-history` - Get recent synchronization history

## Data Storage

- **SQLite Database**: Primary storage at `gym_capacity.db`
- **JSON Export**: Available at `gym_capacity_data.json`
- **CSV Export**: Available at `gym_capacity_data.csv`

When using Docker, data persists in mounted volumes:
- `./data` - Database and exports
- `./logs` - Application logs

## Development

### Running Tests
```bash
python -m pytest tests/
```

### Database Schema

**gyms table**
- `id`: Primary key
- `club_name`: Gym name (unique)
- `club_address`: Location address
- `created_at`: Timestamp

**capacity_logs table**
- `id`: Primary key
- `gym_id`: Foreign key to gyms
- `users_count`: Current visitors
- `users_limit`: Maximum capacity
- `timestamp`: Log timestamp
- `created_at`: Record creation time

**credentials table**
- `id`: Primary key
- `email`: Planet Fitness email
- `password`: Planet Fitness password (stored in plaintext)
- `created_at`: Timestamp
- `updated_at`: Last update timestamp

**sync_history table**
- `id`: Primary key
- `started_at`: Sync start time
- `completed_at`: Sync completion time
- `status`: 'success', 'failed', or 'in_progress'
- `gyms_fetched`: Number of gyms fetched
- `error_message`: Error details (if failed)
- `duration_seconds`: Sync duration
- `triggered_by`: 'manual' or 'scheduler'

## Deployment Options

### Docker (Recommended)
See [DOCKER.md](DOCKER.md) for detailed Docker deployment instructions.

### VPS Deployment
```bash
# On your VPS
git clone <repository>
cd gym-capacity-logger
docker-compose up -d
```

### Raspberry Pi
Same as VPS deployment. Ensure Docker is installed first.

## Troubleshooting

### No data being collected
- Verify Planet Fitness credentials are configured in Settings page
- Check if credentials exist: Look for "Configured ✓" status in Settings
- Check scheduler logs: `docker-compose logs scheduler`
- Ensure network connectivity to Planet Fitness API
- Try manually triggering a fetch from the Settings page

### Web interface not loading
- Check if port 5000 is available
- Verify Flask is running: `docker-compose ps`
- Check firewall settings

### Database locked errors
- The application handles database locking automatically
- If persistent, restart the container: `docker-compose restart`

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool is for personal use only. Please respect Planet Fitness's terms of service and API usage guidelines. The authors are not responsible for any misuse of this software.

## Acknowledgments

- Planet Fitness for providing the PerfectGym API
- Flask community for the excellent web framework
- Chart.js for data visualization