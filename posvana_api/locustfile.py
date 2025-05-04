from locust import HttpUser, task, between
import random

class WebsiteUser(HttpUser):
    wait_time = between(1, 3)

    registered_users = [
        {"email": "dian@mail.com", "password": "12345678"},
        {"email": "tes@gmail.com", "password": "123456"},
    ]

    initialized = False

    def on_start(self):
        # Hanya dijalankan sekali per worker untuk tambah dua akun baru
        if not WebsiteUser.initialized:
            user1 = {"email": "user1@mail.com", "password": "password123", "name": "User Satu"}
            user2 = {"email": "user2@mail.com", "password": "password456", "name": "User Dua"}

            self.client.post("/api/user_auth/register-customer/", json=user1)
            self.client.post("/api/user_auth/register-customer/", json=user2)

            WebsiteUser.registered_users.append({"email": user1["email"], "password": user1["password"]})
            WebsiteUser.registered_users.append({"email": user2["email"], "password": user2["password"]})

            WebsiteUser.initialized = True

    @task
    def login_user(self):
        # Pilih salah satu user secara acak dari 4 user yang tersedia
        user = random.choice(WebsiteUser.registered_users)
        payload = {
            "email": user["email"],
            "password": user["password"]
        }
        self.client.post("/api/user_auth/login_user/", json=payload)
