import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Изолируем окружение теста.
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_KEY", "test-bootstrap")

    # Создаём отдельную in-memory БД и подменяем dependency get_db.
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    import app.auth as auth_module
    import app.db as db_module
    import app.main as main_module
    import app.models  # noqa: F401  # важно импортнуть модели, чтобы они зарегистрировались в metadata

    db_module.Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[db_module.get_db] = override_get_db
    main_module.app.dependency_overrides[auth_module.get_db] = override_get_db

    return TestClient(main_module.app)

