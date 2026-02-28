# vrc-world-engine
### VRChat World Analytics & Actuarial Engine

**Status:** Actively in development

A quantitative data pipeline and statistical analysis engine that tracks the lifecycles, engagement volatility, and "mortality" rates of public VRChat worlds. 

By treating virtual worlds as active assets, this project ingests time-series data via the VRChat API to model player retention, calculate the survival probabilities of trending worlds, and perform correlation studies between world capacity and concurrent occupancy. 

This project places a heavy emphasis on data integrity, ethical API usage, and automated pipeline stability.

---

## 📊 Core Features 
- **Time-Series Data Ingestion:** Automated, scheduled scraping of active VRChat worlds to track engagement metrics (concurrent players, favorites) over time.
- **Bulletproof Data Pipeline:** Features custom rate-limit handling (HTTP 429 catching), strict hard-throttling, and SQLite connection safety to ensure zero server stress and absolute data integrity.
- **Actuarial Modeling (In Progress):** - **Survival Analysis:** Tracking how long worlds stay on the "Trending" or "Active" pages before dropping off (asset mortality/churn).
  - **Forecasting:** Predicting peak weekend occupancy based on weekday baseline data.
  - **Correlation Studies:** Analyzing the statistical relationship between hard-coded lobby capacities and long-term player retention.
- **Data Exporting:** Automated extraction of normalized relational data to CSV for exploratory data analysis (EDA) in Pandas or Excel.

---

## 🛠 Tech Stack
**Data Engineering / Pipeline**
- **Python** (Core Logic)
- **SQLite** (Relational Database, Time-Series Storage)
- **VRChat API Client / Requests** (Session handling and Cookie management)

**Quantitative Analysis / Statistics**
- **Pandas & NumPy** (Data wrangling and statistical calculations)
- **Matplotlib / Seaborn** (Data visualization)
- *(Planned)* **Lifelines / Statsmodels** (Survival analysis and regression modeling)

---

## ⚙️ Installation

1. **Clone the repository**
   ```bash
   git clone [https://github.com/yourusername/vrc-world-engine.git](https://github.com/yourusername/vrc-world-engine.git)
   cd vrc-world-engine

2. **Create and activate a virtual environment**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Mac/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Setup**
   Copy the example environment file and add your VRChat credentials:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in `VRC_USERNAME` and `VRC_PASSWORD`.

## Usage

> **Note:** The application is currently under active development.

**Running the Application**
The project is currently operated via a central Python orchestrator.

Running the Data Pipeline
To launch the scraper or export current datasets to CSV, run the main orchestrator from the root directory:
python main.pypython main.py
Note: The scraper is configured to run respectfully, pulling bulk data with built-in delays to adhere strictly to VRChat's API terms of service.

Data Analysis
(Scripts for Pandas-driven EDA and actuarial modeling are currently located in the src/analytics/ directory - coming soon).

## ⚖️ Project Ethics & Data Sourcing
This project accesses publicly available metadata via the VRChat API. It is designed with strict adherence to rate limits, utilizing 10-second request delays and automatic HTTP 429 backoff protocols to ensure no undue stress is placed on the host servers.

No private user data is collected, and the application does not automate interactions on the platform.

## 🎯 Project Goals
Showcase end-to-end data pipeline construction and database management.

Apply actuarial methodologies (survival analysis, risk forecasting) to non-traditional datasets.

Demonstrate clean, object-oriented Python architecture and ethical API consumption.

Disclaimer: This project is for educational and portfolio purposes only and is not affiliated with, maintained, or endorsed by VRChat Inc.

## Disclaimer
This project is for educational purposes only and is not affiliated with VRChat Inc.
