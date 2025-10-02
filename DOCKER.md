# Docker Deployment Guide

This guide explains how to deploy the Gym Capacity Logger using Docker.

## Quick Start

1. **Clone the repository** (or copy your files to the deployment server)

2. **Create a `.env` file** with your Planet Fitness credentials:
```bash
PF_EMAIL=your-email@example.com
PF_PASSWORD=your-password
```

3. **Build and run with Docker Compose**:
```bash
docker-compose up -d
```

4. **Access the dashboard** at `http://localhost:5000`

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PF_EMAIL` | Planet Fitness login email | Required |
| `PF_PASSWORD` | Planet Fitness password | Required |
| `FLASK_HOST` | Web server host | 0.0.0.0 |
| `FLASK_PORT` | Web server port | 5000 |
| `LOG_INTERVAL` | Data collection interval (minutes) | 15 |
| `TZ` | Timezone | Australia/Brisbane |

### Docker Compose

The `docker-compose.yml` file includes:
- Automatic restart on failure
- Volume mounts for data persistence
- Health checks for monitoring
- Timezone configuration

## Manual Docker Commands

If you prefer not to use Docker Compose:

### Build the image:
```bash
docker build -t gym-capacity-logger .
```

### Run the container:
```bash
docker run -d \
  --name gym-capacity-logger \
  --restart unless-stopped \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e PF_EMAIL="your-email@example.com" \
  -e PF_PASSWORD="your-password" \
  -e TZ="Australia/Brisbane" \
  gym-capacity-logger
```

## Data Persistence

Data is stored in Docker volumes:
- `/app/data` - SQLite database and exported files
- `/app/logs` - Application logs

These are mapped to local directories:
- `./data` - Database files
- `./logs` - Log files

## Monitoring

### View logs:
```bash
docker-compose logs -f gym-capacity-logger
```

### Check health status:
```bash
docker-compose ps
```

### Access the container:
```bash
docker-compose exec gym-capacity-logger bash
```

## Updating

To update the application:

1. Pull latest changes (if using git)
2. Rebuild the image:
```bash
docker-compose build
```
3. Restart the container:
```bash
docker-compose up -d
```

## Troubleshooting

### Container won't start
- Check logs: `docker-compose logs gym-capacity-logger`
- Verify environment variables are set correctly
- Ensure ports aren't already in use

### No data being collected
- Verify Planet Fitness credentials are correct
- Check scheduler logs in `./logs/scheduler.log`
- Ensure network connectivity to Planet Fitness API

### Web interface not accessible
- Verify port 5000 is accessible
- Check firewall rules
- Confirm Flask is running: `docker-compose logs | grep Flask`

## Security Notes

- Never commit `.env` files to version control
- Use Docker secrets in production environments
- Consider using a reverse proxy (nginx/traefik) with SSL for internet exposure
- Regularly update the base image for security patches

## Deployment Examples

### Deploy to a VPS
```bash
# On your VPS
git clone <your-repo>
cd gym-capacity-logger
cp .env.example .env
# Edit .env with your credentials
docker-compose up -d
```

### Deploy to a Raspberry Pi
The same steps apply, just ensure Docker is installed on your Pi first.

### Deploy with Custom Network
```yaml
# Add to docker-compose.yml
networks:
  web:
    external: true
```

## Backup

To backup your data:
```bash
# Backup database
docker-compose exec gym-capacity-logger cp /app/data/gym_capacity.db /app/data/backup_$(date +%Y%m%d).db

# Or from host
cp ./data/gym_capacity.db ./data/backup_$(date +%Y%m%d).db
```