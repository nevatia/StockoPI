# StockoPI - Unofficial Trading API Wrapper for Stocko (Formerly SASOnline Ltd.)

Carrying forward the great work of Algo2t/alphatrade. This repository provides an unofficial Python API wrapper for Stocko, designed to simplify interaction with their trading platform. Follow the steps below to set up and use the library.
Discussion forum :- https://t.me/sasonlineunofficial

---

## **Steps to Set Up**

### **1. Clone the Repository**

Clone the repository to your local machine:

```bash
git clone https://github.com/nevatia/StockoPI.git
```

---

### **2. Create a Virtual Environment**

Set up a virtual environment to isolate dependencies:

```bash
python -m pip install virtualenv
python -m venv stocko
```

Activate the environment:

- **On Windows:**
  ```bash
  stocko\Scripts\activate
  ```
- **On macOS/Linux:**
  ```bash
  source stocko/bin/activate
  ```

---

### **3. Install Required Packages**

Install the dependencies listed in `requirements.txt`:

```bash
python -m pip install -r requirements.txt
```

---

### **4. Configure Your Credentials**

Navigate to the root of the cloned repository and open the `config.py` file. Enter your login details:

```python
login_id = "your_login_id"
password = "your_password"
Totp= "your_totp_secret_key"
client_secret = "your client secret received from support"
```







> **Note:** The `totp_secret_key` should be the **SECRET key** for generating 2FA codes, **not** the 6-digit TOTP.

---

## **Usage**

Once set up, you can use the Stocko API wrapper to interact with the trading platform. Refer to the examples in the repository (stockomain.py) to get started.

---

## **Disclaimer**

This is an unofficial library for educational and personal use. Use it at your own risk. The authors are not affiliated with Stocko or SASOnline.

