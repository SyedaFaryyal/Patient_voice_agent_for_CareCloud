"""
Server-side validation - independent of whatever the voice agent already
checked, per spec ("do not rely solely on the voice agent for validation").
"""
import re
from datetime import date, datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, field_validator, EmailStr

US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC",
}

NAME_RE = re.compile(r"^[A-Za-z'\-\s]{1,50}$")
PHONE_RE = re.compile(r"^\d{10}$")
ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")


class Sex(str, Enum):
    male = "Male"
    female = "Female"
    other = "Other"
    decline = "Decline to Answer"


class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: str  # YYYY-MM-DD
    sex: Sex
    phone_number: str
    email: Optional[EmailStr] = None
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    state: str
    zip_code: str
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = "English"
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def valid_name(cls, v):
        if not NAME_RE.match(v):
            raise ValueError("Name must be 1-50 alphabetic characters, hyphens, or apostrophes.")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def valid_dob(cls, v):
        try:
            d = datetime.strptime(v, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("date_of_birth must be in YYYY-MM-DD format.")
        if d > date.today():
            raise ValueError("date_of_birth cannot be in the future.")
        return v

    @field_validator("phone_number", "emergency_contact_phone")
    @classmethod
    def valid_phone(cls, v):
        if v is None:
            return v
        digits = re.sub(r"\D", "", v)
        if not PHONE_RE.match(digits):
            raise ValueError("Phone number must be a valid 10-digit U.S. number.")
        return digits

    @field_validator("state")
    @classmethod
    def valid_state(cls, v):
        v = v.upper()
        if v not in US_STATES:
            raise ValueError("state must be a valid 2-letter U.S. state abbreviation.")
        return v

    @field_validator("zip_code")
    @classmethod
    def valid_zip(cls, v):
        if not ZIP_RE.match(v):
            raise ValueError("zip_code must be 5 digits or ZIP+4 format.")
        return v

    @field_validator("city")
    @classmethod
    def valid_city(cls, v):
        if not (1 <= len(v) <= 100):
            raise ValueError("city must be 1-100 characters.")
        return v


class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    sex: Optional[Sex] = None
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
