# 1. Use the official Tryton image as the base
FROM tryton/tryton:latest

# 2. Switch to root to handle file permissions and installations
USER root

# 3. Install any system-level dependencies your modules might need
# (e.g., git, build-essential, or postgresql-client)
RUN apt-get update && apt-get install -y \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# 4. Set the working directory where Tryton looks for modules
WORKDIR /var/lib/trytond

# 5. Copy your custom modules folder from your PC into the container
# This assumes your local folder is named 'tryton-modules'
COPY ./tryton-modules /var/lib/trytond/modules

# 6. (Optional) If you have a requirements.txt for extra python libraries
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# 7. Ensure the 'tryton' user owns the files so it can run the server
RUN chmod -R 777 /var/lib/trytond/modules
# 8. Switch back to the non-root 'tryton' user for security
USER tryton

# 9. The entrypoint is already defined in the base image, 
# so we don't need to add a CMD unless we want to override it.