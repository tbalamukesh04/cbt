# JEECBTify — JEE Exam Practice Environment

Welcome to **CBTify**, the ultimate platform designed to transform standard text-based JEE PDF question papers into realistic, interactive Computer-Based Tests (CBT).

Whether you are an institute, a tutor, or a student preparing for the Joint Entrance Examination (JEE), CBTify lets you practice in an environment that perfectly mimics the actual examination screen.

---

## 🚀 Key Features

* **Instant Document Processing:** Upload any standard, text-based JEE question paper (up to 50MB) and let the platform dynamically generate an entire online test in seconds.
* **Realistic Exam Interface:** The examination page perfectly mirrors the real JEE UI. Practice under exam-like conditions using the exact navigation palette, color coding (Answered, Marked for Review, Not Visited), and tabbed subjects you will encounter on test day.
* **Automated Grading & Real-time Insights:** Once you submit your exam, upload the matching solutions PDF. CBTify instantly checks your answers and calculates your score.
* **Intelligent Scorecards & Analytics:** View detailed section-by-section analytics (Physics, Chemistry, Mathematics), including time-spent per question, correct/incorrect splits, and detailed question-by-question review screens.
* **Beautiful, Modern Aesthetics:** Sleek, accessible UI featuring integrated dark/light modes and responsive data visualization tools.

---

## 📋 How It Works

1. **Upload Question Paper:** Drag and drop your JEE question paper PDF directly onto the CBTify homepage.
2. **Attempt Exam:** CBTify launches the practice environment. Manage your time across sections, flag questions for review, and submit when you are ready or when the clock runs out.
3. **Upload Solutions:** After submitting the exam or when the timer ends, you will be prompted to upload the corresponding solutions PDF. CBTify automatically extracts the answer keys and maps them to your test.
4. **Review Results:** Analyze your detailed scorecard, view your calculated marks, instantly filter by wrong or unattempted answers, and pull up specific questions with their original diagrams to review exactly where you went wrong.

---

## 💻 Running CBTify Locally

CBTify is incredibly simple to spin up using Docker.

### Prerequisites
* Docker Desktop installed on your machine.

### Installation & Startup

1. Open your terminal in the root CBTify directory.
2. Build the Docker image:
   ```bash
   docker build -t cbtify .
   ```
3. Run the container:
   ```bash
   docker run -p 7860:7860 cbtify
   ```
4. Open your web browser and navigate to:
   ```text
   http://127.0.0.1:7860
   ```

*(Note: Ensure you are uploading valid, text-selectable PDFs for optimal performance.)*

---

**Empower your JEE preparation with CBTify today!**
