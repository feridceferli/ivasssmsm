Here’s an updated version of the README.md with your requested changes, including a warning against re-uploading to GitHub without proper credit to @ISmartCoder, a recommendation to fork instead, and some cool emojis! 😎🚀



# IVAS SMS Panel API 🎉

Welcome to the IVAS SMS Panel API, a powerful Flask-based application designed to interact with the IVAS SMS service programmatically. This API allows you to retrieve OTP messages and SMS statistics efficiently. 🌟

- **Repository**: [github.com/TheSmartDevs/IvasSMSPanelAPI](https://github.com/TheSmartDevs/IvasSMSPanelAPI)
- **Project Owner**: [@ISmartCoder](https://github.com/abirxdhack)

## Features ✨

- **OTP Retrieval**: Fetch OTP messages for specified phone ranges and date ranges.
- **SMS Statistics**: Retrieve counts of SMS (total, paid, unpaid) and revenue data.
- **Cookie-Based Authentication**: Secure login using stored cookies to maintain sessions.
- **Flexible Querying**: Support for custom date ranges and limits on OTP retrieval.
- **Robust Error Handling**: Detailed logging and error messages for debugging.
- **Response Compression**: Handles gzip and brotli encoded responses seamlessly.

## Requirements 📋

- A fresh, valid `cookies.json` file with authentication cookies for IVAS SMS Panel.
  - **Note**: Cookies must be updated regularly as they may expire. The API includes an alert system to notify about potential cookie expiration but does not log out to preserve the session.
- Python 3.x
- Required packages (listed in `requirements.txt`)

## Installation 🛠️

1. Clone the repository:
   ```bash
   git clone https://github.com/TheSmartDevs/IvasSMSPanelAPI.git
   cd IvasSMSPanelAPI
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Update `cookies.json` with valid authentication cookies.

4. Run the application:
   ```bash
   python app.py
   ```

## Hosting on Vercel 🌐

1. Fork the repository on GitHub.
2. Update the `cookies.json` file with valid authentication cookies.
3. Go to [vercel.com](https://vercel.com), sign in, and select the forked repository.
4. Deploy the project. Vercel will automatically handle the build and deployment process.

## API Endpoints 📡

- **Welcome Endpoint**:
  - URL: `/`
  - Method: `GET`
  - Response Type: `application/json`
  - Example Response:
    ```json
    {
      "message": "Welcome to the IVAS SMS API",
      "status": "API is alive",
      "endpoints": {
        "/sms": "Get OTP messages for a specific date (format: DD/MM/YYYY) with optional limit. Example: /sms?date=01/05/2025&limit=10"
      }
    }
    ```

- **SMS Retrieval Endpoint**:
  - URL: `/sms`
  - Method: `GET`
  - Query Parameters:
    - `date` (required): Date in `DD/MM/YYYY` format.
    - `to_date` (optional): End date in `DD/MM/YYYY` format.
    - `limit` (optional): Maximum number of OTP messages to return.
  - Response Type: `application/json`
  - Example Response:
    ```json
    {
      "status": "success",
      "from_date": "01/05/2025",
      "to_date": "Not specified",
      "limit": "Not specified",
      "sms_stats": {
        "count_sms": "50",
        "paid_sms": "30",
        "unpaid_sms": "20",
        "revenue": "25.50"
      },
      "otp_messages": [
        {
          "range": "+1",
          "phone_number": "+1234567890",
          "otp_message": "Your OTP is 123456"
        }
      ]
    }
    ```

## Important Notice ⚠️

- **Do not re-upload this code to GitHub**! If you must share or use it elsewhere, please provide proper credit to the original author, [@ISmartCoder](https://github.com/ISmartCoder). 🚫
- **Forking Recommended**: Instead of re-uploading, fork this repository to contribute or use it for your projects. This helps maintain the integrity of the original work. 🙌

## Contributing 🤝

Contributions are welcome! Please fork the repository and submit pull requests. For major changes, please open an issue first to discuss what you would like to change.

## License 📜

This project is open-source. For more details, see the `LICENSE` file (if included).

