# Telegram Bot for Volunteer and Beneficiary Management

## Overview
This project is a Telegram bot designed to facilitate interaction between volunteers, beneficiaries, and moderators. The bot provides functionalities such as application management, user authentication, and category creation.

## Features
- **User Authentication**: Registration and authorization for volunteers, beneficiaries, and moderators.
- **Application Handling**:
  - Volunteers can accept, cancel, close applications, and edit profiles.
  - Beneficiaries can create, delete, and confirm applications.
  - Moderators can verify users, create and delete categories, and deactivate applications.
- **Profile Management**: Users can delete their profiles if needed.
- **Task Management**: Users can view available tasks and their statuses.
- **Admin Controls**: Moderators can manage categories and verify users.

## Project Structure
```
handlers/
    authorization/
    beneficiary/
    moderator/
    volunteer/
services/
src/
tg_bot/
.dockerignore
.env
.gitignore
.gitlab-ci.yml
docker-compose.yml
Dockerfile
main.py
requirements.txt
```

### Key Files
- `main.py`: Entry point of the bot.
- `handlers/`: Contains all the command handlers for different user types.
- `services/`: Contains helper services like API client and token refresh.
- `.env`: Stores environment variables (e.g., Telegram bot token).
- `Dockerfile`: Defines the Docker image setup.
- `docker-compose.yml`: Configuration for running the bot in a Docker container.
- `requirements.txt`: Lists all dependencies needed to run the bot.

## Installation
### Prerequisites
- Python 3.8+
- Telegram bot token (set in `.env` file)

### Setup
1. Clone the repository:
   ```sh
   git clone https://github.com/MLokatsiun/tg_bot_volunteer.git
   cd telegram-bot
   ```
2. Create and activate a virtual environment:
   ```sh
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```
3. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
4. Set up environment variables in a `.env` file:
   ```
   TELEGRAM_TOKEN=your-telegram-bot-token
   ```
5. Run the bot:
   ```sh
   python main.py
   ```

## Running with Docker
1. Build the Docker image:
   ```sh
   docker build -t telegram-bot .
   ```
2. Run the container:
   ```sh
   docker-compose up -d
   ```

## Usage
- Start the bot on Telegram and register as a volunteer, beneficiary, or moderator.
- Use commands to create and manage applications.
- Moderators can verify users and manage categories.

## Contributing
Feel free to fork the repository and submit pull requests with improvements.

## License
This project is licensed under the MIT License.

