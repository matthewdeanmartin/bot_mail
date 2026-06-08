FROM python:3.12-slim

LABEL maintainer="matthewdeanmartin@gmail.com"
LABEL description="A shell app for bot mail"

WORKDIR /app

# Non-root user for runtime isolation
RUN useradd --create-home --shell /bin/bash appuser

# Install the package as root so the venv is system-wide, then drop to appuser
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir bot_mail

# Drop privileges
USER appuser

# Default: show help.
ENTRYPOINT ["bot_mail"]
CMD ["--help"]
