BRIEF EXPLANATION of "ALL-OR-NOTHING LOGIC"
The transactions (transfer) runs inside MySQL database transaction. I lock both wallet rows using "SELECT FOR UPDATE" to ensure isolation. If any validation or update fails, the roll back is triggered, which restores the sender’s balance automatically. Only when both debit and credit succeed do I commit, ensuring atomicity, consistency, isolation, and durability.

INSTALL DEPENDENCY:
pip install mysql-connector-python
pip install fastapi uvicorn

CREATE DATABASE AND TABLES:
CREATE DATABASE zenexDB
USE zenexDB;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE wallets (
    user_id INT PRIMARY KEY,
    balance INT NOT NULL CHECK (balance >= 0),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transaction_ref VARCHAR(100) NOT NULL UNIQUE,
    sender_id INT NOT NULL,
    receiver_id INT NOT NULL,
    amount INT NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

Manually inserts this data's:
INSERT INTO users (name) VALUES ('Alice'), ('Bob');

INSERT INTO wallets (user_id, balance)
VALUES
(1, 10050), -- ₦100.50
(2, 0);

Make sure to edit the database config in the app.py to your details (i.e db_config)

1. To run as API Script, in your terminal run;
python -m uvicorn app:app --reload

you will see;
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.

Open your browser and paste;
http://127.0.0.1:8000/docs
CLick POST/transfer
click Try it out
Copy and paste the below (you can change the amount below)
{
  "sender_id": 1,
  "receiver_id": 2,
  "amount": "₦50.25", (edit the amount)
  "transaction_ref": "TXN-008" (edit the transaction reference)
}
then click execute
you should get;
{
  "status": "success",
  "message": "Transfer successful"
}


2. To run not as an API script, Comment the below code in app.py;
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
and from FastAPI setup downwards

then, uncomment the;
Normal script execution without FastAPI code

in your terminal run;
python app.py