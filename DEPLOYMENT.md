# ChatterTTS Deployment Guide

This guide covers how to deploy the ChatterTTS application using Docker and automated CI/CD with GitHub Actions.

## 🚀 Quick Start

### Local Development with Docker

```bash
# Build and run the application
docker-compose up --build

# Run in detached mode
docker-compose up -d

# View logs
docker-compose logs -f chatter-tts

# Stop the application
docker-compose down
```

The application will be available at `http://localhost:8000`

### Production Deployment with Nginx

```bash
# Start with nginx reverse proxy
docker-compose --profile production up -d

# The application will be available at http://localhost
```

## 🔧 Docker Configuration

### Environment Variables

You can customize the deployment using environment variables:

```bash
# Create a .env file
echo "PYTHONUNBUFFERED=1" > .env
echo "TORCH_DEVICE=cuda" >> .env  # or 'cpu'
```

### Volume Mounts

The application uses volumes for persistent data:
- `./data:/app/data` - Audio files and generated content

## 🏗️ GitHub Actions CI/CD

### Prerequisites

Before using the automated GitHub Actions workflow, you need to set up the following:

#### 1. Docker Hub Account and Repository

1. Create a [Docker Hub](https://hub.docker.com) account
2. Create a new repository: `hareeshbabu82ns/chatter-tts-app`
3. Generate an access token:
   - Go to Account Settings → Security → New Access Token
   - Give it a descriptive name like "GitHub Actions"
   - Copy the token (you'll need it for GitHub secrets)

#### 2. GitHub Repository Secrets

Add the following secrets to your GitHub repository:

1. Go to your GitHub repository
2. Navigate to Settings → Secrets and variables → Actions
3. Add the following secrets:

```
DOCKER_USERNAME: your-docker-hub-username
DOCKER_PASSWORD: your-docker-hub-access-token
```

### 🏷️ Creating Releases

The GitHub Actions workflow is triggered when you create a release with tags. Here's how:

#### Method 1: GitHub Web Interface

1. Go to your GitHub repository
2. Click on "Releases" in the right sidebar
3. Click "Create a new release"
4. Choose a tag version (e.g., `v1.0.0`, `v1.1.0`)
5. Fill in release title and description
6. Click "Publish release"

#### Method 2: Command Line

```bash
# Create and push a tag
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# Or create a release using GitHub CLI
gh release create v1.0.0 --title "v1.0.0" --notes "Release notes here"
```

### 🔄 Automated Workflow

When you create a release, the GitHub Actions workflow will:

1. **Build** the Docker image for multiple architectures (amd64, arm64)
2. **Tag** the image with:
   - The exact version tag (e.g., `v1.0.0`)
   - Semantic version patterns (`1.0.0`, `1.0`, `1`)
   - Git SHA for traceability
3. **Push** to Docker Hub
4. **Update** the Docker Hub repository description

### 📋 Image Tags

Your Docker images will be available with the following tags:
- `hareeshbabu82ns/chatter-tts-app:v1.0.0` (exact version)
- `hareeshbabu82ns/chatter-tts-app:1.0.0` (semantic version)
- `hareeshbabu82ns/chatter-tts-app:1.0` (minor version)
- `hareeshbabu82ns/chatter-tts-app:1` (major version)
- `hareeshbabu82ns/chatter-tts-app:sha-abc1234` (git commit)

## 🐳 Using Published Docker Images

### Pull and Run

```bash
# Pull the latest release
docker pull hareeshbabu82ns/chatter-tts-app:latest

# Run the container
docker run -d \
  --name chatter-tts \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  hareeshbabu82ns/chatter-tts-app:latest
```

### Docker Compose with Published Image

```yaml
version: '3.8'
services:
  chatter-tts:
    image: hareeshbabu82ns/chatter-tts-app:v1.0.0
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

## 🔒 Production Considerations

### Security

1. **Use specific image tags** instead of `latest` in production
2. **Enable HTTPS** by configuring SSL certificates in nginx
3. **Set up firewalls** to restrict access to necessary ports only
4. **Regular updates** - monitor for security updates

### Performance

1. **Resource limits** - Set appropriate CPU/memory limits
2. **Load balancing** - Use multiple replicas behind a load balancer
3. **Caching** - Implement caching strategies for frequently accessed content

### Monitoring

1. **Health checks** - Use the built-in `/health` endpoint
2. **Logging** - Configure centralized logging
3. **Metrics** - Monitor application performance and resource usage

## 🛠️ Troubleshooting

### Common Issues

1. **Port conflicts**: Change the port mapping in docker-compose.yml
2. **Permission issues**: Ensure the `data` directory is writable
3. **Memory issues**: Increase Docker memory limits for large models

### Debug Commands

```bash
# View container logs
docker logs chatter-tts

# Execute commands in running container
docker exec -it chatter-tts bash

# Check container health
docker inspect chatter-tts | grep Health -A 10
```

## 📞 Support

For issues and questions:
1. Check the [GitHub Issues](https://github.com/hareeshbabu82ns/chatter-tts-app/issues)
2. Review the application logs
3. Ensure all prerequisites are met
