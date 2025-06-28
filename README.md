
# ElevateHR

**ElevateHR** is a cutting-edge Human Resource Management Information System (HRMIS) built using Django, enhanced with Generative AI capabilities to revolutionize recruitment and HR operations.

---

## 🚀 Features

- 🔐 Employee Registration, Profile Management & Role Assignment  
- 🏢 Department Creation & Integration  
- 📊 Dashboard with Quick Access Links  
- 🤖 **AI-Powered Resume Screening with Gemini & RAG**  
- 🧠 Conversational CV Assistant using Langchain (PDF-based)  
- 🏆 Candidate Ranking based on Job Description Prompts  
- 📋 Feedback & Survey Modules  
- 🔎 Searchable Employee Directory  
- 📂 Secure Data Handling & Admin Controls

---

## 🧠 Generative AI Capabilities

ElevateHR integrates powerful generative AI using the **Gemini API** and an **Agentic RAG (Retrieval-Augmented Generation)** model to provide:

- Conversational insights from uploaded CVs (PDFs)
- Intelligent ranking of candidates against the company's job descriptions
- Human-like interactions via Langchain's conversational agents

Frameworks and Libraries:
- Gemini API (Google)
- Langchain
- FAISS for embedding-based CV search
- OpenAI-compatible LLM support (fallback)

---

## 🛠️ Tech Stack

- **Backend**: Django (Python)  
- **Database**: SQLite (default) / PostgreSQL (optional)  
- **Frontend**: HTML, CSS (Bootstrap or Tailwind)  
- **AI Tools**: Gemini, Langchain, RAG, FAISS  
- **Icons/UI**: Font Awesome  

---

## ⚙️ Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/elevatehr.git
   cd elevatehr
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv env
   source env/bin/activate  # On Windows: env\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run migrations**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

5. **Start the development server**
   ```bash
   python manage.py runserver
   ```

6. **Access the system**
   Open your browser and navigate to:  
   `http://127.0.0.1:8000/`

---

## 📁 Project Structure

```plaintext
elevatehr/
│
├── ElevateHRApp/       # Core Django app with models, views, templates
    ├── templates/          # HTML Templates
    ├── static/             # CSS, JS, images
    ├── ai/                 # Langchain RAG modules, embeddings, agents
    ├── db.sqlite3          # Default database
    ├── manage.py
    └── README.md
```

---

## ✨ Future Enhancements

- ✅ Role-based access control  
- 📱 Mobile-friendly layout  
- 📅 Leave and Attendance Management  
- 📈 HR Analytics Dashboard  
- 🔄 API Integration with Payroll/CRM  
- 🌍 Multilingual Support for CV Screening

---

## 🙌 Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you'd like to change.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## 👤 Author

**Your Name**  
[GitHub](https://github.com/antonie-riziki) • [LinkedIn](https://linkedin.com/in/antonie-riziki)
