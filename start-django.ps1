# Django Backend Setup and Start Script

Write-Host "Django Backend Starting..." -ForegroundColor Green

# Activate virtual environment from project root
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    .\.venv\Scripts\Activate.ps1
} else {
    Write-Host "Virtual environment not found. Creating new one..." -ForegroundColor Yellow
    uv venv
    .\.venv\Scripts\Activate.ps1
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    uv pip install -r django\requirements.txt
}

# Change to django directory
Set-Location "django"

# Run migrations
Write-Host "Running migrations..." -ForegroundColor Yellow
python manage.py migrate --noinput

# Create test users if they don't exist
Write-Host "Creating test users..." -ForegroundColor Yellow
python manage.py create_test_users

# Collect static files
Write-Host "Collecting static files..." -ForegroundColor Yellow
python manage.py collectstatic --noinput

# Start Django development server
Write-Host "Starting Django development server on http://localhost:8000" -ForegroundColor Green
Write-Host "Kanban Board available at http://localhost:8000" -ForegroundColor Cyan
Write-Host "Admin panel available at http://localhost:8000/admin" -ForegroundColor Cyan
Write-Host "API documentation available at http://localhost:8000/api/" -ForegroundColor Cyan
Write-Host ""
Write-Host "Test users:" -ForegroundColor White
Write-Host "  admin / admin123 (superuser)" -ForegroundColor Cyan
Write-Host "  user001 / password123 (general user)" -ForegroundColor Cyan
Write-Host "  user002 / password123 (general user)" -ForegroundColor Cyan
Write-Host "  user003 / password123 (general user)" -ForegroundColor Cyan
Write-Host ""

python manage.py runserver 8000
