from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Response, status, Header
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings
from app.core.schema import ErrorResponse, RegisterEmailRequest
from app.models.user import get_user, update_user_email
from app.models.app_session import parse_bearer, validate

router = APIRouter()

# security settings
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# mock user database
fake_users_db = {
    "admin": {
        "username": "admin",
        "hashed_password": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYBq7xWLWu6",  # admin@123
        "disabled": False,
    }
}

def require_session(
    authorization: str = Header(..., alias="Authorization"),
    device_id: str = Header(..., alias="X-Device-Id"),
    platform: str = Header(..., alias="X-Platform"),
    app_version: str = Header(..., alias="X-App-Version"),
    os_version: str = Header(..., alias="X-OS-Version"),
):
    token = parse_bearer(authorization)
    rec = validate(token, device_id=device_id)
    return rec

# verify password
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# authenticate user
def authenticate_user(fake_db, username: str, password: str):
    user = fake_db.get(username)
    if not user or not verify_password(password, user["hashed_password"]):
        return False
    return user

# create access token
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

# get current user
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="failed to validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None or username not in fake_users_db:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return fake_users_db[username]

# login and get access token
@router.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register-email", status_code=204, responses={401: {"model": ErrorResponse}})
async def register_email(payload: RegisterEmailRequest, session=Depends(require_session)) -> Response:
    user = get_user(session.app_user_id)
    if not user:
        raise HTTPException(status_code=400, detail="user_not_found")

    update_user_email(session.app_user_id, payload.email)
    return Response(status_code=status.HTTP_204_NO_CONTENT)