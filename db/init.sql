-- As a superuser (e.g. postgres), first create the user
CREATE USER root WITH PASSWORD 'Admin123';

-- Give access to the database
GRANT CONNECT, TEMP ON DATABASE sentinel TO root;

-- Switch to the sentinel database
\c sentinel

-- Create the table (as superuser or owner of the DB)
CREATE TABLE IF NOT EXISTS stream (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    stream_url TEXT NOT NULL,
    quality VARCHAR(50),
    type VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Now grant privileges on the schema + table + sequence
GRANT USAGE, CREATE ON SCHEMA public TO root;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO root;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO root;

-- Optional: make future tables/sequences automatically grant privileges
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT ALL PRIVILEGES ON TABLES TO root;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT ALL PRIVILEGES ON SEQUENCES TO root;
