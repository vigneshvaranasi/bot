from sqlalchemy.orm import Session
import sys
import os
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.api.db_models import Role, Permission, Base
from sqlalchemy import create_engine

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)

permissions_data = [
    "Access to Chat",
    "Configure Settings",
    "User Management",
    "Super Access"
]

roles_data = {
    "L1 Support Engineer": ["Access to Chat"],
    "Admin": permissions_data,
    "Support Manager": [p for p in permissions_data if p != "Super Access"]
}

def main():
    with Session(engine) as session:
        permissions = {}
        for perm_name in permissions_data:
            perm = session.query(Permission).filter_by(name=perm_name).first()
            if not perm:
                perm = Permission(name=perm_name)
                session.add(perm)
            permissions[perm_name] = perm

        session.flush()

        for role_name, perms in roles_data.items():
            role = session.query(Role).filter_by(name=role_name).first()
            if not role:
                role = Role(name=role_name)
                session.add(role)
            role.permissions = [permissions[p] for p in perms]

        session.commit()
        print("Database Initialized")

if __name__ == "__main__":
    main()