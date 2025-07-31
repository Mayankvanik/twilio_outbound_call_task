# 📞 Twilio Outbound Call Task

This project demonstrates how to make outbound interactive calls using Twilio, with a simple FastAPI-based web interface.

---

## 🚀 Getting Started

Follow the steps below to set up and run the project locally.

### 1. 📦 Clone the Repository

```bash
git clone https://github.com/Mayankvanik/twilio_outbound_call_task
cd twilio_outbound_call_task
```

### 2. ⚙️ Set Up Environment Variables

Copy the sample `.env` file and update it with your Twilio credentials:

```bash
cp sample.env .env
```

Edit `.env` and set:

* `TWILIO_ACCOUNT_SID`
* `TWILIO_AUTH_TOKEN`
* `TWILIO_PHONE_NUMBER`

---

### 3. 📥 Install Dependencies

Use [`uv`](https://github.com/astral-sh/uv) to install all required packages:

```bash
uv sync
```

> Make sure `uv` is installed. If not, install via:
>
> ```bash
> pip install uv
> ```

---

### 4. ▶️ Run the Project

```bash
uv run main.py
```

The app will start on: `http://localhost:8000`

---

## 🌐 URL Endpoints

### 🛠️ Configure Twilio Credentials

```
http://localhost:8000/config/twilio-config-form
```

### 📲 Make Outbound Call

```
http://localhost:8000/api/make_interactive_call_form
```

### 📚 API Documentation (Swagger)

```
http://localhost:8000/docs
```

---

## 🌍 Tunnel with Ngrok (Optional)

To expose the app for external access (e.g., for Twilio callbacks):

```bash
ngrok http 8000
```

---

## 🎥 Demo

[▶️ Video Walkthrough](https://drive.google.com/file/d/1HHBciaRXhj916u24lqwdf5oJLoC1cpDY/view?usp=sharing)