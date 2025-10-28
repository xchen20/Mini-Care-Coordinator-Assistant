DROP TABLE IF EXISTS patients;

CREATE TABLE patients (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    dob TEXT NOT NULL,
    pcp TEXT,
    ehrId TEXT,
    insurance TEXT,
    referred_providers TEXT, -- Stored as JSON string
    appointments TEXT -- Stored as JSON string
);
