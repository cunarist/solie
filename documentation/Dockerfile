FROM python:3.13-slim

WORKDIR /docs

# Copy pyproject.toml and install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy documentation source files
COPY source/ source/

# Build the documentation
RUN sphinx-build -b html source/ build/html

# Use a lightweight web server to serve the built documentation
FROM nginx:alpine

# Copy the built HTML documentation from the builder stage
COPY --from=0 /docs/build/html /usr/share/nginx/html

# Expose port 80
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
