import streamlit as st
import hashlib
import json
import os
import base64
from cryptography.fernet import Fernet, InvalidToken
from datetime import datetime, timedelta

# -------------------------------------------------
# STREAMLIT PAGE CONFIGURATION MUST BE FIRST!
# -------------------------------------------------
st.set_page_config(page_title="Secure Data App", page_icon="🔐")

# ---------------------------
# ADD BACKGROUND IMAGE
# ---------------------------
def add_bg_from_local(image_file):
    with open(image_file, "rb") as f:
        encoded_string = base64.b64encode(f.read()).decode()
    css = f"""
    <style>
    .stApp {{
        background-image: url("data:image/png;base64,{encoded_string}");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;        
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# Apply background image from local file
add_bg_from_local("image.png")

# ---------------------------
# FERNET KEY MANAGEMENT
# ---------------------------
KEY_FILE = "secret.key"
DATA_FILE = "data.json"
USERS_FILE = "users.json"  # file for storing user credentials

def load_key():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
        return key

KEY = load_key()
cipher = Fernet(KEY)

# ---------------------------
# GLOBAL STATE
# ---------------------------
stored_data = {}
failed_attempts = 0
lockout_until = None
LOCKOUT_DURATION = 30  # seconds

# ---------------------------
# DATA PERSISTENCE FOR ENCRYPTED DATA
# ---------------------------
def load_data():
    global stored_data
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                stored_data = json.load(f)
            except json.JSONDecodeError:
                stored_data = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(stored_data, f)

load_data()

# ---------------------------
# USER MANAGEMENT
# ---------------------------
users = {}

def load_users():
    global users
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            try:
                users = json.load(f)
            except json.JSONDecodeError:
                users = {}
    else:
        users = {}
        save_users()

def save_users():
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

load_users()

# ---------------------------
# ENCRYPTION HELPERS
# ---------------------------
def hash_passkey(passkey):
    """
    Hash the provided passkey using PBKDF2_HMAC.
    For production, use a unique salt per user/passkey.
    """
    salt = b'static_salt'
    return hashlib.pbkdf2_hmac('sha256', passkey.encode(), salt, 100000).hex()

def encrypt_data(text, passkey):
    """Encrypt the provided text using Fernet encryption."""
    return cipher.encrypt(text.encode()).decode()

def decrypt_data(encrypted_text, passkey):
    """
    Attempt to decrypt the text if the hash of the provided passkey matches.
    Implements a lockout after 3 failed attempts.
    """
    global failed_attempts, lockout_until

    if lockout_until and datetime.now() < lockout_until:
        return "LOCKED"

    hashed_pass = hash_passkey(passkey)
    if encrypted_text in stored_data:
        record = stored_data[encrypted_text]
        if record["passkey"] == hashed_pass:
            try:
                decrypted = cipher.decrypt(encrypted_text.encode()).decode()
                failed_attempts = 0
                return decrypted
            except InvalidToken:
                return None

    failed_attempts += 1
    if failed_attempts >= 3:
        lockout_until = datetime.now() + timedelta(seconds=LOCKOUT_DURATION)
    return None

# ---------------------------
# STREAMLIT USER INTERFACE
# ---------------------------
st.title("🔐 Advanced Secure Data Encryption System")

# Navigation menu includes "Sign Up"
menu = ["Home", "Store Data", "Retrieve Data", "Login", "Sign Up"]

if "nav" in st.session_state:
    default_index = menu.index(st.session_state["nav"])
    choice = st.sidebar.selectbox("Navigation", menu, index=default_index)
    del st.session_state["nav"]
else:
    choice = st.sidebar.selectbox("Navigation", menu)

# ---------------------------
# UI PAGES
# ---------------------------
if choice == "Home":
    st.subheader("🏠 Welcome")
    st.markdown("""
    This system allows you to:
    - 🔐 Encrypt and store data securely
    - 🧠 Use passkeys (hashed, never stored)
    - 🕵️ Retrieve data using a dropdown selection
    - 🚫 Prevent brute-force via lockouts
    - 📥 Download decrypted data
    - 📝 **Sign Up** for an account and then login to access your account
    """)

elif choice == "Store Data":
    st.subheader("📦 Store Data")
    title = st.text_input("🔖 Label this data")
    user_data = st.text_area("📄 Your data")
    passkey = st.text_input("🔑 Passkey", type="password")

    if st.button("🔒 Encrypt & Save"):
        if title and user_data and passkey:
            hashed = hash_passkey(passkey)
            encrypted = encrypt_data(user_data, passkey)
            stored_data[encrypted] = {
                "title": title,
                "encrypted_text": encrypted,
                "passkey": hashed
            }
            save_data()
            st.success("✅ Data stored successfully!")
        else:
            st.error("⚠️ All fields are required!")

elif choice == "Retrieve Data":
    st.subheader("🔍 Retrieve Stored Data")

    if lockout_until and datetime.now() < lockout_until:
        remaining = int((lockout_until - datetime.now()).total_seconds())
        st.warning(f"🔒 Too many failed attempts! Try again in {remaining}s.")
    else:
        if stored_data:
            options = [f"{v['title']} - {k[:10]}..." for k, v in stored_data.items()]
            selected = st.selectbox("📁 Select Encrypted Entry", options)
            encrypted_text = next(
                (k for k, v in stored_data.items() if f"{v['title']} - {k[:10]}..." == selected),
                None,
            )
            st.code(encrypted_text, language="plaintext")
            passkey = st.text_input("🔑 Passkey", type="password")
            if st.button("🔓 Decrypt"):
                if encrypted_text and passkey:
                    result = decrypt_data(encrypted_text, passkey)
                    if result == "LOCKED":
                        remaining = int((lockout_until - datetime.now()).total_seconds())
                        st.warning(f"🔒 Wait {remaining}s before trying again.")
                    elif result is not None:
                        st.success("✅ Decryption successful!")
                        st.text_area("📜 Decrypted Data", result, height=150)
                        st.download_button("⬇️ Download", result, file_name="decrypted.txt")
                    else:
                        attempts_left = max(0, 3 - failed_attempts)
                        st.error(f"❌ Incorrect passkey or corrupted token. Attempts left: {attempts_left}")
                else:
                    st.error("⚠️ Missing data or passkey.")
        else:
            st.info("ℹ️ No encrypted entries found.")

elif choice == "Login":
    st.subheader("🔑 Login")
    if lockout_until and datetime.now() < lockout_until:
        remaining = int((lockout_until - datetime.now()).total_seconds())
        st.warning(f"🔒 Too many failed login attempts! Try again in {remaining}s.")
    else:
        login_username = st.text_input("Username")
        login_password = st.text_input("Enter Password:", type="password")
        if st.button("Login"):
            if login_username in users:
                if hash_passkey(login_password) == users[login_username]:
                    failed_attempts = 0
                    lockout_until = None
                    st.session_state["nav"] = "Retrieve Data"
                    st.success("✅ Access granted. Redirecting...")
                    if hasattr(st, "rerun"):
                        st.rerun()  # Automatically refresh the app (if available)
                    else:
                        st.info("Please refresh the page to continue.")
                else:
                    failed_attempts += 1
                    st.error("❌ Incorrect password.")
            else:
                st.error("❌ Username not found.")
            if failed_attempts >= 3:
                st.warning("🔒 Too many failed attempts!")

elif choice == "Sign Up":
    st.subheader("📝 Sign Up")
    new_username = st.text_input("Choose a Username:")
    new_password = st.text_input("Choose a Password:", type="password")
    confirm_password = st.text_input("Confirm Password:", type="password")
    if st.button("Sign Up"):
        if new_username and new_password and confirm_password:
            if new_password != confirm_password:
                st.error("❌ Passwords do not match.")
            elif new_username in users:
                st.error("❌ Username already exists.")
            else:
                # Create new user account and save
                users[new_username] = hash_passkey(new_password)
                save_users()
                st.success("✅ Account created successfully! Please go to Login to access your account.")
        else:
            st.error("⚠️ All fields are required!")
