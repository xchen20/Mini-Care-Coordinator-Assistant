import os

class Config:
    """Base configuration class. Contains default configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'a-very-secret-key-that-you-should-change')
    
    # Path Configurations
    # These paths are absolute inside the container, based on docker-compose volumes.
    DATABASE_PATH = '/app/db_data/patients.db'
    DATA_SHEET_PATH = '/app/data_sheet.json'
    VECTOR_DB_PATH = '/app/vector_db'
    SCHEMA_PATH = '/app/schema.sql'
    PATIENT_SHEET_PATH = '/app/patient_sheet.json'

    # AI/Model Configurations
    VECTOR_DB_COLLECTION_NAME = "care_assistant_rag"
    EMBEDDING_MODEL = "text-embedding-3-small"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")