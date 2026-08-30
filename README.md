# Sifdine Discord Bot 🤖

A modular, asynchronous Discord bot engineered in Python using `discord.py`. The bot is designed around a fully dynamic and decoupled event-driven model, offering high performance, persistence, and server-side utilities.

---

## 🛠️ Technical Stack & Key Libraries

- **Language:** Python 3.10+
- **Core API Wrapper:** `discord.py` v2.x (Asynchronous gateway communication)
- **Database Engine:** SQLite managed via `aiosqlite` (Asynchronous non-blocking database operations)
- **System Monitoring:** `psutil` (Low-level hardware/system resource utilization metrics)

---

## ⚙️ System Architecture & Code Design

### 1. Dynamic Extension Loading (Cog System)
The codebase uses a fully decoupled modular architecture. All functionality is grouped into separate Python files (extensions) contained within the designated folder. On launch, the bot scans the directory and registers each extension dynamically using `bot.load_extension()`. This setup allows developers to easily scale the bot's features or add new files without editing the core bot initialization loop.

### 2. Custom Entities & Extensions
*   **Fuzzy Target Matching (`converters.py`):** Integrates custom command converters subclassing `commands.Converter`. The bot utilizes matching algorithms (such as Python's standard `difflib.SequenceMatcher`) to automatically resolve server members based on similarity ratings when exact IDs or mentions are not supplied.
*   **Asynchronous Database State:** Persistent data is handled through local SQLite tables. Upon boot, the bot establishes an asynchronous thread pool via `aiosqlite` and builds schema infrastructure for config mappings, user states, and authorization layers.

---

## 🚀 Setup & Execution

### 1. Repository Setup
```bash
git clone https://github.com/ayoubanlouf/SifdineDiscordBot.git
cd SifdineDiscordBot
pip install -r requirements.txt
```

### 2. Environment Variables Configuration
Create a `.env` file in the root directory by copying the provided template:
```bash
cp .env.example .env
```
Then, edit the `.env` file and fill in your required credentials and API keys.

The `ENVIRONMENT` variable dictates the bot's operating mode:
- `prod`: The bot operates in full production mode, using default prefixes (such as `sat` and `ahya`) as well as server-specific custom prefixes.
- `dev`: The bot switches to development-only mode, where it only responds to the `dev` prefix. This prevents command conflicts with the production instance and allows for safe testing.

### 3. Lifecycle & Boot Stages
```bash
python main.py
```
Upon execution, the bot follows this precise startup lifecycle:
1. Opens an asynchronous connection pool to the SQLite state database.
2. Initializes necessary database schemas and tables if they are absent.
3. Recursively loads all functional extensions from the dynamic loader directory.
4. Spawns the main gateway client process.