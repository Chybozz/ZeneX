from decimal import Decimal
import mysql.connector
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from fastapi.staticfiles import StaticFiles

# FastAPI setup
app = FastAPI(title="ZeneX API")
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS (keep this)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# database connection setup (example)
db_config = {
    "host": os.getenv("MYSQLHOST"),
    "user": os.getenv("MYSQLUSER"),
    "password": os.getenv("MYSQLPASSWORD"),
    "database": os.getenv("MYSQLDATABASE"),
    "port": int(os.getenv("MYSQLPORT", 3306))
}
# 'user': 'root',
# 'password': 'Onuchukwu12!',
# 'host': '127.0.0.1',
# 'database': 'zenexDB'

# Function to convert Naira string to Kobo integer (e.g., "₦50.25" -> 5025)
def naira_to_kobo(amount: str) -> int:
    amount = amount.replace("₦", "").replace(",", "").strip() # Clean the input (remove currency symbol and commas)
    value = Decimal(amount)
    if value <= 0:
        raise ValueError("Amount must be greater than zero")
    return int(value * 100) # Convert to kobo


# Function to perform money transfer between two wallets
def transfer_money(conn, sender_id, receiver_id, amount_kobo):
    cursor = conn.cursor()

    # Lock sender wallet for update
    cursor.execute(
        "SELECT balance FROM wallets WHERE user_id = %s FOR UPDATE",
        (sender_id,)
    )
    sender = cursor.fetchone()
    if not sender:
        raise Exception("Sender wallet not found")

    # Check sufficient funds (the sender must have at least the amount to transfer, no negative balance allowed)
    if sender[0] < amount_kobo:
        raise Exception("Insufficient funds")

    # Lock receiver wallet for update
    cursor.execute(
        "SELECT balance FROM wallets WHERE user_id = %s FOR UPDATE",
        (receiver_id,)
    )
    receiver = cursor.fetchone()
    if not receiver:
        raise Exception("Receiver wallet not found")

    # Debit sender
    cursor.execute(
        "UPDATE wallets SET balance = balance - %s WHERE user_id = %s",
        (amount_kobo, sender_id)
    )

    # Credit receiver
    cursor.execute(
        "UPDATE wallets SET balance = balance + %s WHERE user_id = %s",
        (amount_kobo, receiver_id)
    )
    

# Idempotency check function
def chk_transfer(conn, transaction_ref):
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT status FROM transactions WHERE transaction_ref = %s",
        (transaction_ref,)
    )
    existing = cursor.fetchone()

    if existing:
        conn.rollback()  # ROLLBACK TRANSACTION IF ALREADY PROCESSED
        return {
            "status": "success",
            "message": "Transfer Already Successful", # changed from "Transfer Successful which was in the first one i send." Old logic message (Can be changed to "Transfer already processed")
        }
    return None


# Log transaction
def log_transaction(conn, transaction_ref, sender_id, receiver_id, amount_kobo, status):
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO transactions
        (transaction_ref, sender_id, receiver_id, amount, status)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            transaction_ref,
            sender_id,
            receiver_id,
            amount_kobo,
            status
        )
    )


# This is the main execution block (running script)

# Normal script execution without FastAPI
""" if __name__ == "__main__":
    # database connection
    conn = mysql.connector.connect(**db_config)

    try:
        # START TRANSACTION
        conn.start_transaction()
        # Idempotency check 
        duplicate = chk_transfer(conn, "TXN-014")
        if duplicate:
            conn.rollback()
            print(duplicate)
        else:
            # Perform transfer
            amount = naira_to_kobo("₦50.25") # Edit the amount you want to transfer from here
            transfer_money(conn, 1, 2, amount)
            # Log transaction
            log_transaction(conn, "TXN-014", 1, 2, amount, "SUCCESS")
        # COMMIT TRANSACTION
        conn.commit()
        print("Transaction successful")
    except Exception as e:
        conn.rollback() # ROLLBACK TRANSACTION IF FAILED
        print(f"Transaction failed: {e}")
    finally:
        conn.close() """


class TransferRequest(BaseModel):
    sender_id: int
    receiver_id: int
    amount: str  # e.g. "₦50.25"
    transaction_ref: str

# API endpoint for money transfer
@app.post("/transfer")
def transfer(req: TransferRequest):
    conn = mysql.connector.connect(**db_config)

    try:
        # START TRANSACTION
        conn.start_transaction()

        # Idempotency check 
        duplicate = chk_transfer(conn, req.transaction_ref)
        if duplicate:
            conn.rollback()
            return duplicate
        
        # Normalize amount
        amount_kobo = naira_to_kobo(req.amount)

        # Perform transfer
        transfer_money(
            conn,
            req.sender_id,
            req.receiver_id,
            amount_kobo
        )

        # Log transaction
        log_transaction(
            conn,
            req.transaction_ref,
            req.sender_id,
            req.receiver_id,
            amount_kobo,
            "SUCCESS"
        )
        # COMMIT TRANSACTION
        conn.commit()

        return {"status": "success", "message": "Transfer successful"}

    except Exception as e:
        conn.rollback() # ROLLBACK TRANSACTION IF FAILED
        raise HTTPException(status_code=400, detail=str(e))

    finally:
        conn.close()


# Wallet balance route
@app.get("/wallet/{user_id}")
def get_wallet(user_id: int):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT balance FROM wallets WHERE user_id = %s",
        (user_id,)
    )
    wallet = cursor.fetchone()
    conn.close()

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    return {
        "balance": wallet["balance"] / 100  # convert kobo → naira
    }


# Transaction history route
@app.get("/transactions/{user_id}")
def get_transactions(user_id: int):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT transaction_ref, amount, status, created_at
        FROM transactions
        WHERE receiver_id = %s
        ORDER BY created_at DESC
        LIMIT 10
        """,
        (user_id,)
    )

    txns = cursor.fetchall()
    conn.close()

    return [
        {
            "ref": t["transaction_ref"],
            "amount": f"{t['amount'] / 100:.2f}",  # convert kobo → naira and format as string
            "status": t["status"],
            "date": t["created_at"]
        }
        for t in txns
    ]


# Dashboard route
@app.get("/")
def dashboard():
    # return FileResponse(os.path.join(BASE_DIR, "dashboard.html"))
    return FileResponse("dashboard.html")

# Payment route
@app.get("/payment")
def payment():
    return FileResponse("payment.html")