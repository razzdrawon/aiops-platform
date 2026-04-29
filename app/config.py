from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://aiops_user:aiops_pass@localhost:5432/aiops"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Pinecone
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX_NAME: str = "aiops-runbooks"
    PINECONE_CLOUD: str = "aws"
    PINECONE_REGION: str = "us-east-1"
    OPENAI_EMBEDDING_DIM: int = 1536
    RAG_MATCH_DISTANCE_MAX: float = 0.45

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPIC_EVENTS: str = "ecommerce.events"
    KAFKA_TOPIC_CORRELATED: str = "incidents.correlated"
    CORRELATION_FLUSH_EVENTS: int = 2


settings = Settings()
