# AI-Enhanced-Group-Chat

## Android Application (Trusted Web Activity)

This project includes an Android application built using Trusted Web Activity (TWA) to wrap the web-based group chat into a native mobile experience. The app loads the deployed web application securely using an HTTPS domain.

### Features
Launches the web app inside an Android container using LauncherActivity
Real-time chat powered by FastAPI backend and WebSockets
AI responses generated using Llama 3 (Ollama)
Domain verification using Digital Asset Links

### HTTPS Deployment

Since TWA requires a secure origin, ngrok is used to expose the local FastAPI backend as a public HTTPS URL:

uvicorn app:app --host 0.0.0.0 --port 8000
ngrok http 8000

### Asset Links Verification

To enable TWA:

Generated SHA-256 fingerprint using keytool
Created and hosted:
frontend/.well-known/assetlinks.json
Configured asset_statements and intent filters in AndroidManifest.xml

Verification confirmed using:

adb shell pm get-app-links "your_ApplicationID from android studio"

## Running the Application

Follow these steps to run the full system (Backend + LLM + Android App):

### LLM Setup (Llama 3 using Ollama)
Install Ollama from: https://ollama.com/download

Verify installation:
```
ollama --version
```
Verify installed models:
```
ollama list
```
Pull the Llama 3 model:
```
ollama pull llama3:instruct
```
Run the model:
```
ollama run llama3:instruct
```

Ollama runs a local API server at:

http://localhost:11434
The FastAPI backend connects to this endpoint to generate AI responses.

###  Start Ollama (LLM)

Make sure Ollama is installed and the model is available:

```bash
ollama run llama3:instruct
```

---

###  Start Backend (FastAPI)

Navigate to the backend folder and run:

```bash
cd backend
uvicorn app:app --host 0.0.0.0 --port 8000
```

---

###  Install and Start ngrok (HTTPS Tunnel)

Install Ngrok from


Open a new terminal and navigate to the folder where `ngrok.exe` is located:

```bash
cd C:\Users\"enter_the_location_of_grok.exe"
ngrok.exe http 8000
```

Copy the generated HTTPS URL (e.g., `https://xxxxx.ngrok-free.dev`)

---

###  Update Android App URL

In:

```
res/values/strings.xml
```

Set:

```xml
<string name="defaultUrl">https://your-ngrok-url/</string>
```

In:

```
app/manifest/AndroidManifest.xml
```

Uncomment lines 35 to 38 and 
Set:

``` 
android:host="your_host_name"
```

---

###  Run Android App

* Open project in Android Studio
* Build and run the app on a physical device
* Ensure backend and ngrok are running, and llama3:instruct is running as well to generate the resposnses

---

###  Important Notes

* ngrok URL changes every time it restarts
* Backend and ngrok must be running simultaneously
* Ollama must be active to generate AI responses

---

This setup enables the Android app to securely connect to the locally hosted backend via HTTPS.
