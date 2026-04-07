FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Prevent python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy project
COPY . .

# Run server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]