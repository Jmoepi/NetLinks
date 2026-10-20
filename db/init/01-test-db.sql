-- Runs once on first start of the db container (empty pgdata volume).
-- Enables pgvector in the main database and creates the integration-test database.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE DATABASE netlinks_test;

\connect netlinks_test
CREATE EXTENSION IF NOT EXISTS vector;
