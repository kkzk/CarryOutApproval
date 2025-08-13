# Django Backend Setup Script

Write-Host "Setting up Django Backend..." -ForegroundColor Green

# Create virtual environment at project root
Write-Host "Creating virtual environment with uv..." -ForegroundColor Yellow
uv venv

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
.\.venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
uv pip install -r django\requirements.txt

# Change to django directory
Set-Location "django"

# Run migrations
Write-Host "Running database migrations..." -ForegroundColor Yellow
python manage.py migrate

# Create test users
Write-Host "Creating test users..." -ForegroundColor Yellow
python manage.py create_test_users

# Collect static files
Write-Host "Collecting static files..." -ForegroundColor Yellow
python manage.py collectstatic --noinput

Write-Host ""
Write-Host "Django Backend setup completed!" -ForegroundColor Green
Write-Host "To start the server, run: .\start-django.ps1" -ForegroundColor Cyan
