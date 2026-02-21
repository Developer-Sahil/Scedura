import os
import json
import firebase_admin
from firebase_admin import credentials, auth
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db, User

# Ensure you have the service account key (credentials.json)
cred = credentials.Certificate("credentials.json")

try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(cred)

security = HTTPBearer()

def verify_token(
    creds: HTTPAuthorizationCredentials = Security(security), 
    db: Session = Depends(get_db)
):
    """
    Verifies the Firebase ID token and ensures a User record exists.
    Returns the User object.
    """
    token = creds.credentials
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token["uid"]
        email = decoded_token.get("email")

        # Sync user to local DB
        user = db.query(User).filter(User.firebase_uid == uid).first()
        if not user:
            user = User(firebase_uid=uid, email=email)
            db.add(user)
            db.commit()
            db.refresh(user)
        
        return user

    except Exception as e:
        raise HTTPException(
            status_code=401, 
            detail=f"Invalid authentication credentials: {str(e)}"
        )
