AI Business Idea Generator
This project is a full-stack application that combines a sophisticated multi-agent Python backend with a dynamic, user-friendly frontend to replicate the "Gold Mining Framework" for discovering business ideas. It takes a broad user-provided topic, analyzes it to find promising sub-niches, validates them, gathers user pain points, and finally generates a complete business concept with landing page copy.

Features
Multi-Agent Backend: Uses LangGraph to create a robust, sequential workflow of specialized AI agents (Market Analyst, Researcher, Idea Generator).

Dynamic Frontend: A clean, responsive interface built with HTML and Tailwind CSS that guides the user through the idea generation process.

Google Authentication: Secure user login powered by Firebase Authentication.

Structured AI Responses: Leverages Gemini's JSON mode to ensure reliable, structured data flow between the frontend and the AI.

Downloadable Reports: Allows users to download the complete, formatted results of their session as a text file.

Prerequisites
Before you begin, ensure you have the following installed:

Python 3.8+

pip (Python package installer)

A web browser (Chrome, Firefox, etc.)

A code editor (like VS Code)

Setup Instructions
You will need to configure both the backend and the frontend with the necessary API keys.

1. Backend Setup (Python & LangGraph)
The backend is a Flask server that runs the multi-agent workflow.

A. Create Project Folder:
Create a new folder for your project and navigate into it.

B. Set up a Virtual Environment (Recommended):

python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

C. Install Dependencies:
Create a requirements.txt file with the content from the artifact above and run:

pip install -r requirements.txt

D. Create .env File:
Create a file named .env in your project's root directory and add your secret keys. You will need to get these from their respective developer consoles.

# .env
GROK_API="your_groq_api_key"
GOOGLE_SEARCH_API_KEY="your_google_search_api_key"
GOOGLE_SEARCH_CSE_ID="your_google_custom_search_engine_id"

E. Create Backend Script:
Save the final Python script (the one using LangGraph and Flask) as app.py.

2. Frontend Setup (HTML & Firebase)
The frontend is a single index.html file that needs to be hosted.

A. Get Firebase Configuration:

Go to the Firebase Console.

Create a new project (or use an existing one).

In your project, go to Project Settings (the gear icon).

Under the "General" tab, scroll down to "Your apps".

Click the web icon (</>) to create a new web app.

Follow the steps, and Firebase will give you a firebaseConfig object.

B. Get Google AI API Key:

Go to Google AI Studio.

Create a new API key.

C. Update the HTML File:

Save the HTML code from the Canvas as index.html.

Open index.html and find the <script> section at the bottom.

Replace the placeholder firebaseConfig object with the one you got from your Firebase project.

Replace the placeholder YOUR_GEMINI_API_KEY with your key from Google AI Studio.

Running the Application
Host the Frontend: For the Firebase Google login to work, the index.html file must be served from a web server. The easiest free option is Netlify Drop. Simply drag and drop your configured index.html file onto the page, and it will give you a live URL.

Run the Backend Server (Optional - for backend integration): If you are connecting the frontend to the Python backend, you would run the Flask server from your terminal:

python app.py

Use the App: Open the live URL from your hosting provider (e.g., Netlify) in your browser, log in with Google, and start generating ideas!