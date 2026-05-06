from sqlalchemy import Column, Integer, String

from db import KeyBase


class ApiKeyRecord(KeyBase):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, index=True)
    key_alias = Column(String, index=True)
    encrypted_raw_key = Column(String)