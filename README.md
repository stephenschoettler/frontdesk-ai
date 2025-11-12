# **Front Desk: AI Receptionist**

Front Desk is an open-source, real-time, conversational AI receptionist built to run on a local server. It uses Pipecat to orchestrate multiple AI services and connects to a public phone number via Twilio.

This project is designed to be a foundation for a fully-featured AI agent that can be customized to handle real-world business tasks, such as calendar management and lead capture.

### **Core Tech Stack**

* **Orchestration:** [Pipecat](https://www.google.com/search?q=https://pipecat.ai/)  
* **Web Server:** [FastAPI](https://fastapi.tiangolo.com/) & Uvicorn  
* **Telephony:** [Twilio](https://www.twilio.com/) (Voice Webhooks)  
* **Database:** [Supabase](https://supabase.com/) (Postgres)  
* **Tunneling (Dev):** [ngrok](https://ngrok.com/)  
* **AI Services:**  
  * **LLM:** [OpenRouter](https://openrouter.ai/) (for access to Grok, Llama, GPT, etc.)  
  * **STT:** [Deepgram](https://deepgram.com/) (Real-time transcription)  
  * **TTS:** [ElevenLabs](https://elevenlabs.io/) (Real-time voice generation)  
  * **Calendar:** [Google Calendar API](https://developers.google.com/calendar/api)

## **1\. Service Provisioning (The "Gathering" Phase)**

Before you can run this application, you must sign up for all of the following services and acquire the necessary API keys and credentials.

### **☐ 1.1. Twilio (The Phone Number)**

1. **Create Account:** Sign up for a [Twilio](https://www.twilio.com/) account.  
2. **Upgrade Account:** You **must** upgrade from a trial account by adding a payment method and a starting balance (e.g., $20). This is required to remove the "trial account" message from calls.  
3. **Buy a Number:** Navigate to "Phone Numbers" \-\> "Manage" \-\> "Buy a number" and purchase a local number with **Voice** capability.  
4. **Get Credentials:** From your main Account Dashboard, find and save your:  
   * TWILIO\_ACCOUNT\_SID  
   * TWILIO\_AUTH\_TOKEN  
   * TWILIO\_PHONE\_NUMBER (the number you just bought, in \+1... format)

### **☐ 1.2. Supabase (The "Memory")**

1. **Create Project:** Sign up at [Supabase](https://supabase.com/) and create a new project.  
2. **Get Credentials:** Go to your project's **Settings** \-\> **API**:  
   * Find the **Project ID** (e.g., your-project-id). Your URL is https://\[your-project-id\].supabase.co.  
   * Find the **anon public Key**.  
   * Save both for your .env file.  
3. **Create Tables:** Go to the **SQL Editor** in your project, paste the contents of setup.sql (see below), and click **RUN**.

#### **setup.sql**

\-- 1\. Create the 'users' table (your clients)  
CREATE TABLE users (  
    id UUID PRIMARY KEY DEFAULT gen\_random\_uuid(),  
    full\_name TEXT,  
    calendar\_id TEXT NOT NULL,  
    twilio\_phone TEXT NOT NULL UNIQUE,  
    forward\_phone TEXT NOT NULL,  
    created\_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()  
);

\-- 2\. Create the 'contacts' table (your clients' callers)  
CREATE TABLE contacts (  
    id UUID PRIMARY KEY DEFAULT gen\_random\_uuid(),  
    phone\_number TEXT NOT NULL UNIQUE,  
    full\_name TEXT,  
    address TEXT,  
    last\_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW()  
);

\-- 3\. Create the 'conversations' table (the call logs)  
CREATE TABLE conversations (  
    id UUID PRIMARY KEY DEFAULT gen\_random\_uuid(),  
    user\_id UUID REFERENCES users(id),  
    contact\_id UUID REFERENCES contacts(id),  
    transcript JSONB,  
    summary TEXT,  
    created\_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()  
);

\-- 4\. Enable Row Level Security (RLS)  
ALTER TABLE users ENABLE ROW LEVEL SECURITY;  
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;  
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

\-- 5\. Create basic "allow all" policies for development  
CREATE POLICY "Allow anon access"  
ON users FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow anon access"  
ON contacts FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow anon access"  
ON conversations FOR ALL USING (true) WITH CHECK (true);

### **☐ 1.3. Google Calendar (The "Tool")**

1. **Create Project:** Go to the [Google Cloud Console](https://console.cloud.google.com/) and create a new project.  
2. **Enable API:** In "APIs & Services," enable the **Google Calendar API**.  
3. **Create Service Account:**  
   * Go to "Credentials" and create a **Service Account**.  
   * Select your new service account and go to its **KEYS** tab.  
   * Click **"ADD KEY"** \-\> **"Create new key"** \-\> **"JSON"** and download the file.  
4. **Save Key:** Place this JSON key file in your project directory (e.g., google-service-key.json).  
5. **Grant Permissions:**  
   * Open the JSON file and copy the client\_email address (e.g., ...gserviceaccount.com).  
   * Go to your Google Calendar settings and share your calendar with this email, granting it **"Make changes to events"** permissions.

### **☐ 1.4. AI Services (The "Brains")**

Sign up for the following services and get an API key from each:

* [**OpenRouter**](https://openrouter.ai/) (for the LLM)  
* [**Deepgram**](https://deepgram.com/) (for STT)  
* [**ElevenLabs**](https://elevenlabs.io/) (for TTS)

### **☐ 1.5. ngrok (The "Tunnel")**

1. **Create Account:** Sign up for a free account at [ngrok](https://ngrok.com/).  
2. **Get Authtoken:** Follow the "Getting Started" steps to get your authtoken.  
3. **Configure ngrok:** Authenticate your ngrok CLI (this is a one-time setup):  
   ngrok config add-authtoken \<YOUR\_NGROK\_AUTHTOKEN\>

## **2\. Project Installation & Setup**

1. **Clone the Repo:**  
   git clone \[https://github.com/your-username/frontdesk-ai.git\](https://github.com/your-username/frontdesk-ai.git)  
   cd frontdesk-ai

2. **Create Virtual Environment:**  
   python \-m venv venv  
   source venv/bin/activate

3. **Install Dependencies:**  
   pip install \-r requirements.txt

4. Create .gitignore:  
   Create a file named .gitignore and add the following to protect your keys:  
   .env  
   venv/  
   \_\_pycache\_\_/  
   \*.pyc  
   \*.json  
   app.log

5. Create .env File:  
   Create a file named .env and fill it with all the credentials you gathered in Step 1\.  
   \# OpenRouter  
   OPENROUTER\_API\_KEY="YOUR\_OPENROUTER\_KEY"

   \# Deepgram  
   DEEPGRAM\_API\_KEY="YOUR\_DEEPGRAM\_KEY"

   \# ElevenLabs  
   ELEVENLABS\_API\_KEY="YOUR\_ELEVENLABS\_KEY"

   \# Twilio (Must be upgraded account)  
   TWILIO\_ACCOUNT\_SID="YOUR\_TWILIO\_SID"  
   TWILIO\_AUTH\_TOKEN="YOUR\_TWILIO\_TOKEN"  
   TWILIO\_PHONE\_NUMBER="+1..."

   \# Supabase  
   SUPABASE\_URL="https://\[YOUR-PROJECT-ID\].supabase.co"  
   SUPABASE\_ANON\_KEY="YOUR\_SUPABASE\_ANON\_KEY"

   \# Google Calendar  
   \# Use the filename of the key you downloaded  
   GOOGLE\_SERVICE\_ACCOUNT\_FILE\_PATH="google-service-key.json"

## **3\. Running the Receptionist**

This requires two terminals running at the same time.

### **Terminal 1: Run the Server**

In your project directory, activate your environment and run the app:

source venv/bin/activate  
python main.py

The server is now running on http://localhost:8000.

### **Terminal 2: Run ngrok**

In a **new** terminal, start ngrok to expose your server to the internet:

ngrok http 8000

**Troubleshooting:** If Twilio fails to connect (you get an "application error" but see no traffic in your ngrok terminal), ngrok might have assigned you a URL that Twilio can't reach. Stop ngrok (Ctrl+C) and restart it using a different region to get a new URL:

ngrok http 8000 \--region eu

ngrok will give you a public "Forwarding" URL. Copy the https URL.  
Example: https://abcd-1234.ngrok-free.dev

### **Final Step: Configure Twilio**

1. Go to your **Twilio Console** \-\> **Phone Numbers** \-\> **Active numbers**.  
2. Click on your phone number.  
3. Scroll to the **"Voice Configuration"** section.  
4. Under **"A CALL COMES IN"**:  
   * Set the first dropdown to **"Webhook"**.  
   * In the URL box, paste your ngrok URL and add /voice at the end.  
   * **Full URL Example:** https://abcd-1234.ngrok-free.dev/voice  
   * Set the method to **HTTP POST**.  
5. Click **"Save"**.

### **You are LIVE.**

Call your Twilio number. Your AI receptionist will answer.