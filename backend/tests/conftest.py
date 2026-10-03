import pytest
from lab.app import app
from lab.auth import require_user

@pytest.fixture(autouse=True)
def authenticated_lab():
    # Audio tests exercise DSP/API independently of the account database.
    app.dependency_overrides[require_user]=lambda: {'id':1,'username':'test','email':'test@example.invalid'}
    yield
    app.dependency_overrides.clear()
