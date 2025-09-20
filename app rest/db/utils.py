# db/utils_rest.py
import streamlit as st
import requests

SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["anon_key"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# ---------------------------
# Helper to query any table
# ---------------------------
def fetch_table(table_name: str, filters: str = "", limit: int = 100) -> list[dict]:
    """
    Fetch rows from a Supabase table using REST.
    filters: optional query string, e.g., 'username=eq.admin'
    """
    url = f"{SUPABASE_URL}/rest/v1/{table_name}?limit={limit}"
    if filters:
        url += f"&{filters}"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def insert_row(table_name: str, data: dict) -> dict:
    """
    Insert a row into a Supabase table.
    """
    url = f"{SUPABASE_URL}/rest/v1/{table_name}"
    resp = requests.post(url, headers=HEADERS, json=data)
    resp.raise_for_status()
    return resp.json()


def update_row(table_name: str, row_id_name: str, row_id_value, data: dict) -> dict:
    """
    Update a row in a Supabase table by id.
    """
    url = f"{SUPABASE_URL}/rest/v1/{table_name}?{row_id_name}=eq.{row_id_value}"
    resp = requests.patch(url, headers=HEADERS, json=data)
    resp.raise_for_status()
    return resp.json()


def delete_row(table_name: str, row_id_name: str, row_id_value) -> None:
    """
    Delete a row from a Supabase table by id.
    """
    url = f"{SUPABASE_URL}/rest/v1/{table_name}?{row_id_name}=eq.{row_id_value}"
    resp = requests.delete(url, headers=HEADERS)
    resp.raise_for_status()