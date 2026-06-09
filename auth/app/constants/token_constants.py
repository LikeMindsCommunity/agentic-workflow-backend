ACCESS_TOKEN_COOKIE_NAME = "access_token"
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"

# Access token expiry in minutes
PROD_ACCESS_TOKEN_EXPIRY_MINUTES = 15
BETA_ACCESS_TOKEN_EXPIRY_MINUTES = 30

# Refresh token expiry in days
REFRESH_TOKEN_EXPIRY_DAYS = 30

# JWT claim keys
CLAIM_ACCESS_UUID = "access_uuid"
CLAIM_REFRESH_UUID = "refresh_uuid"
CLAIM_USER_ID = "user_id"
CLAIM_EXP = "exp"
CLAIM_DATA = "data"

# Redis keys
OTP_ATTEMPTS_KEY = "otp_attempts:{email}"

MAX_OTP_ATTEMPTS = 5
OTP_BLOCK_TTL_SECONDS = 30 * 60  # 30 minutes
