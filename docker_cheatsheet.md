# The Ultimate Docker Cheat Sheet

Here are the essential Docker commands and concepts you need to know to manage this project effectively.

## 1. Starting & Stopping the System

> [!TIP]
> The `-d` flag stands for "detached mode", meaning it runs in the background so you can keep using your terminal!

*   **Start everything in the background:** 
    ```bash
    docker compose up -d
    ```
*   **Stop everything safely (leaves your data intact):**
    ```bash
    docker compose down
    ```
*   **See what is currently running:**
    ```bash
    docker compose ps
    ```

## 2. Running Scripts

When you want to run a specific Python script (like the AI pipeline or visualization) using the environment we built:

*   **Run the main pipeline:**
    ```bash
    docker compose run --rm app python run_cameras.py
    ```
*   **Run the visualization script:**
    ```bash
    docker compose run --rm app python visualize.py
    ```
> [!NOTE]
> `--rm` tells Docker to instantly delete the temporary container as soon as the Python script finishes running, keeping your computer clean.

## 3. Checking Logs (Debugging)

If something crashes in the background (like the Web Server), you need to check the logs.

*   **View Web Server logs (live streaming):**
    ```bash
    docker compose logs -f web
    ```
*   **View Database logs (live streaming):**
    ```bash
    docker compose logs -f db
    ```
*(Press `Ctrl+C` to stop watching the logs).*

## 4. Entering a Container

Sometimes you just want to open a bash terminal *inside* the container to poke around, check files, or run tests.

*   **Open a terminal inside the Web Server:**
    ```bash
    docker compose exec web /bin/bash
    ```
*   **Run a raw SQL command directly inside the Postgres database:**
    ```bash
    docker compose exec db psql -U admin -d traffic -c "SELECT * FROM cameras;"
    ```

## 5. What Happens When Code Changes?

### Situation A: A Teammate Edits Python or HTML Code
Because we mounted the folder using `volumes: - ./:/app` in the compose file, **Docker automatically syncs code edits instantly!**
*   If your frontend guy edits `static/index.html`, you just refresh your browser. No Docker commands needed.
*   If your AI guy edits `run_cameras.py`, the next time you run `docker compose run --rm app python run_cameras.py`, it will use the new code instantly.

### Situation B: A Teammate Installs a New Library
If someone adds a new library (like `pip install some-speed-library`) to the `requirements.txt` file, or edits the `Dockerfile`:
*   The instant sync trick above won't work for system-level dependencies. You MUST tell Docker to completely rebuild the container from scratch.
*   **The Command:**
    ```bash
    docker compose up -d --build
    ```
    *(The `--build` flag forces Docker to read the new `requirements.txt` and install the new libraries before starting).*

> [!CAUTION]
> If a teammate says "my code works on my machine but crashes on yours," 99% of the time it is because they added a new dependency and you forgot to run the command with the `--build` flag!
